"""Hybrid RAG copilot.

A query router picks one of three retrieval paths, then a narrative builder
turns the structured result into a grounded, cited answer. The LLM wrapper is
optional (RAG_CHAT_BACKEND=llm); by default the endpoint returns structured
evidence so the UI can render a grounded answer without an extra moving part.
"""
import re

from sqlalchemy import text

from app.services.embeddings import embed


def route_query(q: str) -> str:
    ql = q.lower()
    if re.search(r"\b(how many|count|number of|which location|highest|most|trend|percentage|increase|decrease)\b", ql):
        return "sql"
    if re.search(r"\b(similar|like this|related|recall|comparable|find)\b", ql):
        return "vector"
    if re.search(r"\b(control|barrier|isolation|permit|required|should|procedure|prevent)\b", ql):
        return "knowledge"
    if re.search(r"\b(life.saving|lsr|energy.isolation|line.of.fire|confined.space|falling.object|lifting|working.at.height|driving|fall.protection)\b", ql):
        return "sql"  # LSR queries go to SQL for structured data
    return "sql"


def _vec_sql(v) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in v) + "]"


# ---------------- sql path ----------------

def run_sql(db, q: str) -> dict:
    ql = q.lower()
    location = None
    for loc in ["duliajan", "moran", "digboi", "substation alpha", "power plant", "turbine"]:
        if loc in ql:
            location = loc

    cond, params = [], {}
    if location:
        cond.append("r.location ILIKE :loc")
        params["loc"] = f"%{location}%"
    if "sif" in ql:
        cond.append("r.sif_score >= 0.7")
    where = ("WHERE " + " AND ".join(cond)) if cond else ""
    total = db.execute(text(f"SELECT COUNT(*) FROM reports r {where}"), params).scalar() or 0

    breakdown = []
    if re.search(r"\b(which|top|most)\b", ql):
        rows = db.execute(text(
            "SELECT p.name, COUNT(*) FROM report_precursors rp JOIN precursors p ON p.id=rp.precursor_id "
            "WHERE rp.status IN ('PRESENT','AMBIGUOUS') GROUP BY 1 ORDER BY 2 DESC LIMIT 5"
        )).fetchall()
        breakdown = [{"precursor": r[0], "count": r[1]} for r in rows]
    
    # LSR queries
    lsr_breakdown = []
    if re.search(r"\b(life.saving|lsr|energy.isolation|line.of.fire|confined.space|falling.object|lifting|working.at.height|driving|fall.protection)\b", ql):
        rows = db.execute(text(
            "SELECT lsr.rule_id, lsr.name, rlsr.status, COUNT(*) "
            "FROM report_life_saving_rules rlsr JOIN life_saving_rules lsr ON lsr.id=rlsr.lsr_id "
            "WHERE rlsr.status IN ('BROKEN','UNCERTAIN') GROUP BY 1,2,3 ORDER BY 4 DESC LIMIT 5"
        )).fetchall()
        lsr_breakdown = [{"rule_id": r[0], "name": r[1], "status": r[2], "count": r[3]} for r in rows]
    
    return {"count": total, "location": location, "breakdown": breakdown, "lsr_breakdown": lsr_breakdown}


# ---------------- vector path ----------------

def similar_reports(db: object, q: str, top_k: int = 8) -> list[dict]:
    from app.services.embeddings import embed

    # Check if embedding column exists
    has_emb = db.execute(
        text("SELECT EXISTS(SELECT 1 FROM information_schema.columns "
             "WHERE table_name='reports' AND column_name='embedding')")
    ).scalar()

    if not has_emb:
        # Fallback: find reports matching keywords in the query
        return []

    vec = embed([q])[0]
    rows = db.execute(
        text(
            "SELECT incident_id, location, 1-(embedding <=> :v) AS sim FROM reports "
            "WHERE embedding IS NOT NULL ORDER BY embedding <=> :v LIMIT :k"
        ),
        {"v": _vec_sql(vec), "k": top_k},
    ).fetchall()
    return [{"incident_id": r[0], "location": r[1], "similarity": round(float(r[2] or 0), 3)} for r in rows]


# ---------------- knowledge path ----------------

def knowledge_lookup(db, q: str, top_k: int = 5) -> list[dict]:
    from app.services.embeddings import embed

    # Check if knowledge_chunks has embedding column
    has_emb = db.execute(
        text("SELECT EXISTS(SELECT 1 FROM information_schema.columns "
             "WHERE table_name='knowledge_chunks' AND column_name='embedding')")
    ).scalar()
    if not has_emb:
        return []

    vec = embed([q])[0]
    rows = db.execute(
        text(
            "SELECT k.chunk_text, k.metadata, 1-(k.embedding <=> :v) AS sim "
            "FROM knowledge_chunks k WHERE k.embedding IS NOT NULL "
            "ORDER BY k.embedding <=> :v LIMIT :k"
        ),
        {"v": _vec_sql(vec), "k": top_k},
    ).fetchall()
    return [{"text": r[0], "metadata": r[1], "similarity": round(float(r[2] or 0), 3)} for r in rows]


# ---------------- orchestrator ----------------

def compose_narrative(payload: dict) -> str:
    route = payload.get("route")
    if route == "sql":
        s = payload["structured"]
        parts = [f"There are {s['count']} matching report(s)."]
        if s.get("location"):
            parts.insert(0, f"For {s['location']},")
        if s.get("breakdown"):
            top = s["breakdown"][0]["precursor"]
            parts.append(f"Most common precursor: {top}.")
        if s.get("lsr_breakdown"):
            top_lsr = s["lsr_breakdown"][0]
            parts.append(f"Top Life-Saving Rule violation: {top_lsr['rule_id']} ({top_lsr['name']}) — {top_lsr['status']} ({top_lsr['count']} reports).")
        return " ".join(parts)
    if route == "vector":
        rel = payload.get("related", [])
        if not rel:
            return "No closely similar reports found."
        top = rel[0]
        return f"Closest match is {top['incident_id']} at {top['location'] or 'unknown'} (similarity {top['similarity']})."
    if route == "knowledge":
        kb = payload.get("knowledge", [])
        if not kb:
            return "No regulatory/guidance chunk matched."
        return "Top guidance: " + (kb[0]["text"][:220] if kb[0]["text"] else "n/a")
    return "No answer."


def answer(db, question: str, top_k: int = 8) -> dict:
    route = route_query(question)
    payload = {"question": question, "route": route}
    if route == "sql":
        payload["structured"] = run_sql(db, question)
    elif route == "vector":
        payload["related"] = similar_reports(db, question, top_k=top_k)
    else:
        payload["knowledge"] = knowledge_lookup(db, question, top_k=3)
    payload["narrative"] = compose_narrative(payload)
    return payload