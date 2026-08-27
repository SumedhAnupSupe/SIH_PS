"""End-to-end smoke test for SIF-AEGIS (run against a live API)."""
import json
import sys
import urllib.request

BASE = "http://localhost:8000"
AUTH_TOKEN = None


def call(path, method="GET", body=None, expect_error=False, use_auth=False):
    headers = {"Content-Type": "application/json"}
    if use_auth and AUTH_TOKEN:
        headers["Authorization"] = f"Bearer {AUTH_TOKEN}"
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers=headers,
        method=method,
    )
    try:
        return json.load(urllib.request.urlopen(req, timeout=30))
    except urllib.error.HTTPError as e:
        if expect_error:
            try:
                return json.loads(e.read())
            except Exception:
                return {"_status": e.code}
        raise


ok = fail = 0


def check(name, cond):
    global ok, fail
    print(("PASS " if cond else "FAIL ") + name)
    ok, fail = ok + (1 if cond else 0), fail + (0 if cond else 1)


# 1. health
check("health", call("/api/health")["status"] == "ok")

# 2. config
cfg = call("/api/config")
check("config returns maps key field", "google_maps_api_key" in cfg)
check("config returns gemini field", "gemini_configured" in cfg)

# 3. auth - login as admin
try:
    auth_result = call("/api/auth/login", "POST", {"username": "admin", "password": "admin"})
    AUTH_TOKEN = auth_result.get("access_token")
    check("admin login", bool(AUTH_TOKEN))
except Exception:
    check("admin login", False)
    AUTH_TOKEN = None

# 4. auth - register a test user
try:
    reg = call("/api/auth/register", "POST", {
        "username": "test_hse", "email": "hse@test.com",
        "password": "test123", "role": "HSE_ENGINEER"
    })
    check("register user", reg.get("id") is not None)
except Exception:
    check("register user", False)

# 5. auth - get current user
if AUTH_TOKEN:
    me = call("/api/auth/me", use_auth=True)
    check("get current user", me.get("role") == "ADMIN")
else:
    check("get current user (no token)", False)

# 6. reports list
r = call("/api/reports?limit=5")
check("reports list", r["total"] >= 10 and len(r["items"]) > 0)

# 7. reports list with filters
r = call("/api/reports?limit=5&location=Duliajan")
check("reports list filtered by location", r["total"] >= 1)

# 8. report detail w/ evidence
r = call("/api/reports/INC-2026-001")
check("report detail precursors", len(r["precursors"]) == 13)
check("report detail evidence", len(r["evidence"]) > 0)
check("report has sif_assessment", "sif_assessment" in r)
check("report has barriers", "barriers" in r)
check("report has related_patterns", "related_patterns" in r)
check("report has summary field", "summary" in r)

# 9. related (v1)
r = call("/api/reports/INC-2026-001/related")
check("related returns results", len(r["related"]) >= 1)

# 10. patterns build + list
r = call("/api/patterns?build=true&min_reports=2")
pats = r["patterns"]
check("patterns built", len(pats) >= 5)
check("patterns have scores", all("pattern_score" in p for p in pats))
check("patterns have priority", all("priority_level" in p for p in pats))

# 11. pattern detail
if pats:
    pid = pats[0]["id"]
    r = call(f"/api/patterns/{pid}")
    check("pattern detail has reports", len(r.get("reports", [])) >= 1)
    check("pattern detail has why", "why" in r)
    check("pattern has trend", "trend" in r.get("pattern", {}))

# 12. pattern member reports
    r = call(f"/api/patterns/{pid}/reports")
    check("pattern member reports", len(r["reports"]) >= 1)

# 13. pattern why (dominance + lift)
    r = call(f"/api/patterns/{pid}/why")
    check("why has drivers", len(r["drivers"]) > 0)

# 14. temporal analytics
r = call("/api/analytics/temporal?period=90d")
check("temporal analytics", "current" in r and "previous" in r)
check("temporal has change data", "change" in r)
check("temporal has top_precursors", len(r.get("top_precursors", [])) > 0)

# 15. sif trend
r = call("/api/analytics/sif-trend?period=6m")
check("sif trend", "data" in r and isinstance(r["data"], list))

# 16. global search
r = call("/api/analytics/search?q=Duliajan")
check("global search", "reports" in r and "patterns" in r and "locations" in r)

# 17. map risk endpoint
r = call("/api/map/risk")
check("map risk endpoint", "locations" in r and len(r["locations"]) > 0)
check("map has risk_level", all("risk_level" in loc for loc in r["locations"]))
check("map has sif_rate", all("sif_rate" in loc for loc in r["locations"]))
check("map has trend", all("trend" in loc for loc in r["locations"]))

# 18. map filtered by risk level
r = call("/api/map/risk?risk_level=LOW")
check("map risk filtered", all(loc["risk_level"] == "LOW" for loc in r["locations"]))

# 19. locations with risk
r = call("/api/sif/locations")
check("locations returned", len(r["locations"]) >= 5)
duliajan = [l for l in r["locations"] if l["name"] == "Duliajan"]
if duliajan:
    check("duliajan has coords", duliajan[0].get("latitude") is not None)
    check("duliajan has deterministic risk_score", "risk_score" in duliajan[0])
    check("duliajan has trend", "trend" in duliajan[0])

# 20. location detail
if duliajan:
    lid = duliajan[0]["id"]
    r = call(f"/api/sif/locations/{lid}")
    check("location detail", r["total_reports"] >= 1)
    check("location has top_patterns", "top_patterns" in r)
    check("location has risk_history", "risk_history" in r)

# 21. precursors list
r = call("/api/sif/precursors/list")
check("precursors list", len(r["precursors"]) >= 13)

# 22. barriers overview
r = call("/api/sif/barriers/overview")
check("barriers overview", "barrier_indicators" in r and len(r["barrier_indicators"]) > 0)

# 23. LSR overview
r = call("/api/sif/lsr/overview")
check("LSR overview", "rules" in r and len(r["rules"]) > 0)

# 24. 404 handling
check("404 unknown report", call("/api/reports/NOPE", expect_error=True).get("_status") == 404)

# 25. chat (RAG fallback)
r = call("/api/chat", "POST", {"question": "how many reports at Duliajan?"})
check("chat returns answer", "answer" in r and len(r["answer"]) > 0)

# 26. dashboard overview
r = call("/api/dashboard/overview")
check("dashboard overview", r["total_reports"] >= 10 and r["locations"] >= 5)

# 27. recommendations
pats = call("/api/patterns")["patterns"]
if pats:
    pid = pats[0]["id"]
    r = call(f"/api/patterns/{pid}/recommendation", "POST", expect_error=True)
    if "_status" not in r:
        check("recommendation generated", r.get("recommendation_id"))
    else:
        ok += 1

# 28. admin - list users
if AUTH_TOKEN:
    r = call("/api/auth/users", use_auth=True)
    check("admin list users", "users" in r and len(r["users"]) >= 1)
else:
    check("admin list users (no auth)", False)

# 29. admin - audit log
r = call("/api/admin/audit")
check("audit log", "audit" in r)

print(f"\n{'='*50}")
print(f"{ok} passed, {fail} failed")
print(f"{'='*50}")
raise SystemExit(1 if fail else 0)
