"""Google Gemini Safety Copilot service for SIF-AEGIS.

Uses google-genai SDK with function/tool calling.
Gemini is the reasoning layer, NOT the analytics engine.
All numerical values come from PostgreSQL via controlled tools.
"""
import json
import os
import traceback
from typing import Any, Optional

from app.config import settings


def _get_client():
    """Lazy-init the Gemini client."""
    if not settings.gemini_api_key:
        return None
    try:
        from google import genai
        return genai.Client(api_key=settings.gemini_api_key)
    except Exception as e:
        print(f"[gemini] init failed: {e}")
        return None


# ---- Tool definitions for Gemini function calling ----

TOOL_DEFINITIONS = [
    {
        "name": "search_reports",
        "description": "Search incident reports by location, precursor, SIF class, date range, or free text. Returns matching report summaries.",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "Filter by location name"},
                "precursor": {"type": "string", "description": "Filter by precursor name"},
                "sif_class": {"type": "string", "description": "Filter by SIF class (HSIF, PSIF, LOW)"},
                "start_date": {"type": "string", "description": "Start date YYYY-MM-DD"},
                "end_date": {"type": "string", "description": "End date YYYY-MM-DD"},
                "limit": {"type": "integer", "description": "Max results (default 10)"},
            },
        },
    },
    {
        "name": "get_report",
        "description": "Get full details of a specific report by incident_id.",
        "parameters": {
            "type": "object",
            "properties": {
                "incident_id": {"type": "string", "description": "Report incident ID like INC-2026-001"},
            },
            "required": ["incident_id"],
        },
    },
    {
        "name": "get_location_risk",
        "description": "Get deterministic risk analytics for locations. Returns risk scores, SIF rates, trends from the database.",
        "parameters": {
            "type": "object",
            "properties": {
                "location_ids": {"type": "array", "items": {"type": "string"}, "description": "Optional location IDs"},
                "start_date": {"type": "string", "description": "Start date YYYY-MM-DD"},
                "end_date": {"type": "string", "description": "End date YYYY-MM-DD"},
            },
            "required": ["start_date", "end_date"],
        },
    },
    {
        "name": "get_patterns",
        "description": "Get safety patterns ranked by score. Patterns are recurring combinations of location, precursor, activity.",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "Filter by location"},
                "precursor": {"type": "string", "description": "Filter by precursor name"},
                "priority": {"type": "string", "description": "Filter by priority: CRITICAL, HIGH, MODERATE, LOW"},
                "limit": {"type": "integer", "description": "Max results (default 10)"},
            },
        },
    },
    {
        "name": "get_temporal_analytics",
        "description": "Get period-over-period analytics: SIF rates, trends, comparisons. Returns exact numerical values from the database.",
        "parameters": {
            "type": "object",
            "properties": {
                "start_date": {"type": "string", "description": "Start date YYYY-MM-DD"},
                "end_date": {"type": "string", "description": "End date YYYY-MM-DD"},
                "location_id": {"type": "string", "description": "Optional location ID"},
                "period": {"type": "string", "description": "Period preset: 7d, 30d, 90d, 6m, 1y"},
            },
            "required": ["start_date", "end_date"],
        },
    },
    {
        "name": "get_recommendations",
        "description": "Get evidence-grounded safety recommendations for patterns.",
        "parameters": {
            "type": "object",
            "properties": {
                "pattern_id": {"type": "integer", "description": "Specific pattern ID"},
                "priority": {"type": "string", "description": "Filter by priority"},
            },
        },
    },
    {
        "name": "search_knowledge",
        "description": "Search the safety knowledge base for domain guidance on topics like energy isolation, confined space, fall protection, etc.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query about safety topics"},
                "limit": {"type": "integer", "description": "Max results (default 5)"},
            },
            "required": ["query"],
        },
    },
]

SYSTEM_PROMPT = """You are SIF-AEGIS Safety Copilot, an expert safety intelligence assistant for HSE engineers.

Your purpose is to help engineers understand SIF (Serious Injury/Fatality) potential, precursors, patterns, locations, trends, and recommendations.

RULES:
1. Never invent report facts or IDs that were not provided by tools.
2. Never invent numerical statistics. All numbers must come from tool results.
3. Never claim evidence that was not provided.
4. Use backend tools for exact analytics - do NOT calculate percentages yourself.
5. Cite supporting records (report IDs, pattern IDs) when available.
6. Clearly distinguish observed facts from your interpretation.
7. If evidence is insufficient, say so honestly.
8. Do not give unsupported safety conclusions.
9. Prefer recent relevant evidence when the user asks about current risk.
10. When discussing locations, include their risk level and SIF rate from tool results.
11. When discussing trends, reference the actual period-over-period change from analytics.
12. Be concise and professional - this is used by industrial safety engineers.

DOMAIN CONTEXT:
- SIF = Serious Injury or Fatality potential
- Precursors are behavioral/hazard indicators that precede SIF events
- Life-Saving Rules (LSRs) are IOGP's 9 critical safety rules
- Barriers are controls that prevent SIF events
- Patterns are recurring combinations of location + precursor + activity
- Risk is calculated deterministically, not subjectively"""


def _execute_tool(tool_name: str, args: dict, db) -> dict:
    """Execute a tool call against the database. Returns structured result."""
    try:
        from app.services import temporal, risk_engine, rag
        from sqlalchemy import text

        if tool_name == "search_reports":
            loc = args.get("location")
            prec = args.get("precursor")
            sif_cls = args.get("sif_class")
            s_date = args.get("start_date")
            e_date = args.get("end_date")
            limit = min(args.get("limit", 10), 20)
            conditions = []
            params = {}
            if loc:
                conditions.append("r.location ILIKE :loc")
                params["loc"] = f"%{loc}%"
            if sif_cls:
                conditions.append("r.sif_class = :cls")
                params["cls"] = sif_cls.upper()
            if s_date:
                conditions.append("r.event_date >= :sd")
                params["sd"] = s_date
            if e_date:
                conditions.append("r.event_date <= :ed")
                params["ed"] = e_date
            if prec:
                conditions.append("EXISTS (SELECT 1 FROM report_precursors rp2 JOIN precursors p2 ON p2.id=rp2.precursor_id WHERE rp2.report_id=r.id AND p2.name ILIKE :prec AND rp2.status IN ('PRESENT','AMBIGUOUS'))")
                params["prec"] = f"%{prec}%"
            where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
            params["lim"] = limit
            rows = db.execute(text(
                f"SELECT r.incident_id, r.location, r.event_date, r.sif_class, r.sif_score, r.summary "
                f"FROM reports r {where} ORDER BY r.event_date DESC NULLS LAST LIMIT :lim"
            ), params).fetchall()
            return {"reports": [dict(r._mapping) for r in rows], "count": len(rows)}

        elif tool_name == "get_report":
            iid = args["incident_id"]
            r = db.execute(text(
                "SELECT incident_id, location, event_date, sif_class, sif_score, summary, raw_text "
                "FROM reports WHERE incident_id=:i"
            ), {"i": iid}).mappings().first()
            if not r:
                return {"error": f"Report {iid} not found"}
            rid = db.execute(text("SELECT id FROM reports WHERE incident_id=:i"), {"i": iid}).scalar()
            prec = db.execute(text(
                "SELECT p.name, rp.status FROM report_precursors rp JOIN precursors p ON p.id=rp.precursor_id "
                "WHERE rp.report_id=:r AND rp.status IN ('PRESENT','AMBIGUOUS')"
            ), {"r": rid}).fetchall()
            lsr = db.execute(text(
                "SELECT lsr.rule_id, lsr.name, rlsr.status FROM report_life_saving_rules rlsr "
                "JOIN life_saving_rules lsr ON lsr.id=rlsr.lsr_id "
                "WHERE rlsr.report_id=:r AND rlsr.status='BROKEN'"
            ), {"r": rid}).fetchall()
            return {
                "report": dict(r._mapping),
                "active_precursors": [{"name": p[0], "status": p[1]} for p in prec],
                "broken_lsr": [{"rule_id": l[0], "name": l[1]} for l in lsr],
            }

        elif tool_name == "get_location_risk":
            start = args.get("start_date", "")
            end = args.get("end_date", "")
            loc_ids = args.get("location_ids", [])
            if loc_ids:
                results = []
                for lid in loc_ids:
                    try:
                        r = risk_engine.calculate_location_risk(db, int(lid))
                        if r:
                            results.append(r)
                    except (ValueError, TypeError):
                        pass
                return {"locations": results}
            else:
                results = risk_engine.calculate_all_location_risks(db)
                return {"locations": results[:15]}

        elif tool_name == "get_patterns":
            loc = args.get("location")
            prec = args.get("precursor")
            priority = args.get("priority")
            limit = min(args.get("limit", 10), 20)
            conditions = []
            params: dict = {}
            if loc:
                conditions.append("p.location ILIKE :loc")
                params["loc"] = f"%{loc}%"
            if prec:
                conditions.append("EXISTS (SELECT 1 FROM precursors pr WHERE pr.id=p.precursor_id AND pr.name ILIKE :prec)")
                params["prec"] = f"%{prec}%"
            if priority:
                conditions.append("p.priority_level = :pri")
                params["pri"] = priority.upper()
            where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
            params["lim"] = limit
            rows = db.execute(text(
                f"SELECT p.id, p.title, p.description, p.pattern_type, p.location, p.activity, "
                f"p.report_count, p.sif_count, p.pattern_score, p.priority_level, p.trend, p.sif_rate "
                f"FROM patterns p {where} ORDER BY p.pattern_score DESC NULLS LAST LIMIT :lim"
            ), params).fetchall()
            return {"patterns": [dict(r._mapping) for r in rows]}

        elif tool_name == "get_temporal_analytics":
            result = temporal.get_temporal_analytics(
                db,
                start_date=args.get("start_date"),
                end_date=args.get("end_date"),
                period=args.get("period"),
                location_id=int(args["location_id"]) if args.get("location_id") else None,
            )
            return result

        elif tool_name == "get_recommendations":
            from app.services import recommendations as rec_svc
            pid = args.get("pattern_id")
            if pid:
                rec = db.execute(text(
                    "SELECT r.*, p.title AS pattern_title FROM recommendations r "
                    "JOIN patterns p ON p.id=r.pattern_id WHERE r.pattern_id=:pid"
                ), {"pid": pid}).mappings().first()
                if rec:
                    return {"recommendation": dict(rec)}
                return {"recommendation": None}
            rows = db.execute(text(
                "SELECT r.id, r.pattern_id, p.title, r.recommendation, r.priority, r.confidence "
                "FROM recommendations r JOIN patterns p ON p.id=r.pattern_id "
                "ORDER BY CASE r.priority WHEN 'CRITICAL' THEN 0 WHEN 'HIGH' THEN 1 WHEN 'MEDIUM' THEN 2 ELSE 3 END "
                "LIMIT 10"
            )).fetchall()
            return {"recommendations": [dict(r._mapping) for r in rows]}

        elif tool_name == "search_knowledge":
            results = rag.knowledge_lookup(db, args["query"], top_k=min(args.get("limit", 5), 10))
            return {"knowledge": results}

        return {"error": f"Unknown tool: {tool_name}"}

    except Exception as e:
        return {"error": str(e), "traceback": traceback.format_exc()[:500]}


def chat_with_gemini(db, user_message: str, conversation_history: list | None = None) -> dict:
    """Main entry point: send user message to Gemini with tools, execute tools, return final answer."""
    client = _get_client()
    if not client:
        return {
            "answer": "Gemini API is not configured. Please set GEMINI_API_KEY environment variable.",
            "sources": [],
            "actions": [],
            "confidence": 0,
            "fallback": True,
        }

    # Build contents with conversation history
    contents = []
    if conversation_history:
        for msg in conversation_history[-6:]:  # keep last 6 messages
            contents.append({"role": msg["role"], "parts": [{"text": msg["content"]}]})
    contents.append({"role": "user", "parts": [{"text": user_message}]})

    all_sources = []
    all_actions = []
    collected_data = {}

    try:
        # Call Gemini with tools
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=contents,
            config={
                "system_instruction": SYSTEM_PROMPT,
                "tools": [{"function_declarations": TOOL_DEFINITIONS}],
                "temperature": 0.3,
                "max_output_tokens": 2048,
            },
        )

        # Process tool calls iteratively
        max_iterations = 5
        for _ in range(max_iterations):
            if not response.candidates:
                break
            candidate = response.candidates[0]
            if not candidate.content or not candidate.content.parts:
                break

            has_tool_calls = False
            for part in candidate.content.parts:
                if hasattr(part, "function_call") and part.function_call:
                    has_tool_calls = True
                    fc = part.function_call
                    tool_name = fc.name
                    tool_args = dict(fc.args) if fc.args else {}

                    # Execute the tool
                    tool_result = _execute_tool(tool_name, tool_args, db)

                    # Track sources
                    if tool_name == "search_reports" and "reports" in tool_result:
                        for rpt in tool_result["reports"][:5]:
                            all_sources.append({
                                "type": "report",
                                "id": rpt.get("incident_id", ""),
                                "title": f"{rpt.get('incident_id')} - {rpt.get('location', 'Unknown')}",
                            })
                    elif tool_name == "get_patterns" and "patterns" in tool_result:
                        for pat in tool_result["patterns"][:5]:
                            all_sources.append({
                                "type": "pattern",
                                "id": str(pat.get("id", "")),
                                "title": pat.get("title", ""),
                            })
                    elif tool_name == "get_location_risk" and "locations" in tool_result:
                        for loc in tool_result["locations"][:5]:
                            all_sources.append({
                                "type": "location",
                                "id": str(loc.get("location_id", "")),
                                "title": loc.get("name", ""),
                            })
                    elif tool_name == "search_knowledge" and "knowledge" in tool_result:
                        for kb in tool_result["knowledge"][:3]:
                            meta = kb.get("metadata", {})
                            all_sources.append({
                                "type": "knowledge",
                                "id": str(meta.get("name", "")),
                                "title": f"{meta.get('source', '')} p.{meta.get('page', '')}",
                            })

                    collected_data[tool_name] = tool_result

                    # Build tool response and continue conversation
                    contents.append({"role": "model", "parts": [{"function_call": {"name": tool_name, "args": tool_args}}]})
                    contents.append({
                        "role": "user",
                        "parts": [{"function_response": {"name": tool_name, "response": tool_result}}],
                    })

                    # Re-call Gemini with tool results
                    response = client.models.generate_content(
                        model=settings.gemini_model,
                        contents=contents,
                        config={
                            "system_instruction": SYSTEM_PROMPT,
                            "tools": [{"function_declarations": TOOL_DEFINITIONS}],
                            "temperature": 0.3,
                            "max_output_tokens": 2048,
                        },
                    )
                    break

            if not has_tool_calls:
                break

        # Extract final answer
        answer_text = ""
        if response.candidates and response.candidates[0].content:
            for part in response.candidates[0].content.parts:
                if hasattr(part, "text") and part.text:
                    answer_text += part.text

        return {
            "answer": answer_text or "I couldn't generate an answer for that question.",
            "sources": all_sources,
            "actions": all_actions,
            "confidence": 0.8,
            "collected_data": collected_data,
        }

    except Exception as e:
        error_msg = str(e)
        if "API_KEY_INVALID" in error_msg or "401" in error_msg:
            return {"answer": "Gemini API key is invalid. Please check your configuration.", "sources": [], "actions": [], "confidence": 0, "error": True}
        return {
            "answer": f"I encountered an error while processing your question: {error_msg[:200]}",
            "sources": [],
            "actions": [],
            "confidence": 0,
            "error": True,
        }
