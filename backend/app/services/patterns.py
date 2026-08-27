"""Pattern engine: build and explain patterns, plus analogous report grouping.

Two complementary mechanisms:
  * structured  - SQL GROUP BY (location x precursor x time), using the CSV flags
  * semantic    - HDBSCAN over report embeddings (lazy; can be enabled later)
The "why" of a pattern uses dominance + lift:
    lift(factor) = in-pattern share / global share
so only the distinctive drivers actually pop out.
"""
from collections import Counter

from sqlalchemy import text


# ---------------- pattern construction ----------------

def build_sql_patterns(db, min_reports: int = 2) -> list[dict]:
    """Group reports by (location, task, precursor PRESENT/AMBIGUOUS)."""
    rows = db.execute(
        text(
            """
            SELECT r.location, tt.code AS task, p.name AS precursor, rp.status, p.id AS precursor_id,
                   COUNT(*) AS n,
                   SUM(CASE WHEN r.location IS NOT NULL AND r.event_date IS NOT NULL THEN 1 ELSE 0 END) AS dated
            FROM report_precursors rp
            JOIN reports r  ON r.id=rp.report_id
            JOIN precursors p ON p.id=rp.precursor_id
            LEFT JOIN task_types tt ON tt.id IN (
                SELECT task_type_id FROM report_task_types rt WHERE rt.report_id=r.id LIMIT 1
            )
            WHERE rp.status IN ('PRESENT','AMBIGUOUS')
            GROUP BY 1,2,3,4,5
            HAVING COUNT(*) >= :m
            ORDER BY COUNT(*) DESC
            """
        ),
        {"m": min_reports},
    ).fetchall()
    return [dict(r._mapping) for r in rows]


def build_lsr_patterns(db, min_reports: int = 2) -> list[dict]:
    """Group reports by (location, LSR BROKEN/UNCERTAIN)."""
    rows = db.execute(
        text(
            """
            SELECT r.location, lsr.rule_id, lsr.name AS lsr_name, rlsr.status, lsr.id AS lsr_id,
                   COUNT(*) AS n
            FROM report_life_saving_rules rlsr
            JOIN reports r ON r.id=rlsr.report_id
            JOIN life_saving_rules lsr ON lsr.id=rlsr.lsr_id
            WHERE rlsr.status IN ('BROKEN','UNCERTAIN')
            GROUP BY 1,2,3,4,5
            HAVING COUNT(*) >= :m
            ORDER BY COUNT(*) DESC
            """
        ),
        {"m": min_reports},
    ).fetchall()
    return [dict(r._mapping) for r in rows]


def persist_patterns(db, groups: list[dict], pattern_type: str = 'precursor'):
    """Store each group as a pattern row and link its member reports."""
    for g in groups:
        if pattern_type == 'precursor':
            pid = db.execute(
                text(
                    "INSERT INTO patterns (title, description, pattern_type, location, activity, precursor_id, report_count) "
                    "VALUES (:t,:d,'sql_agg',:loc,:act,:pid,:n) RETURNING id"
                ),
                {
                    "t": f"{g['precursor']} @ {g['location'] or 'all'} / {g['task'] or 'any'}",
                    "d": f"{g['precursor']} reported {g['status'].lower()} in {g['n']} reports "
                         f"({g['location'] or 'all locations'})",
                    "loc": g["location"], "act": g["task"], "pid": g["precursor_id"], "n": g["n"],
                },
            ).scalar()

            member_ids = db.execute(
                text(
                    """
                    SELECT rp.report_id FROM report_precursors rp
                    JOIN reports r ON r.id=rp.report_id
                    WHERE rp.precursor_id=(SELECT id FROM precursors WHERE name=:prec)
                      AND rp.status=:st
                      AND (:loc IS NULL OR r.location=:loc)
                    """
                ),
                {"prec": g["precursor"], "st": g["status"], "loc": g["location"]},
            ).scalars().all()
        else:  # lsr pattern
            pid = db.execute(
                text(
                    "INSERT INTO patterns (title, description, pattern_type, location, lsr_id, report_count) "
                    "VALUES (:t,:d,'sql_agg',:loc,:lsr,:n) RETURNING id"
                ),
                {
                    "t": f"{g['lsr_name']} @ {g['location'] or 'all'}",
                    "d": f"{g['lsr_name']} reported {g['status'].lower()} in {g['n']} reports "
                         f"({g['location'] or 'all locations'})",
                    "loc": g["location"], "lsr": g["lsr_id"], "n": g["n"],
                },
            ).scalar()

            member_ids = db.execute(
                text(
                    """
                    SELECT rlsr.report_id FROM report_life_saving_rules rlsr
                    JOIN reports r ON r.id=rlsr.report_id
                    WHERE rlsr.lsr_id=:lsr
                      AND rlsr.status=:st
                      AND (:loc IS NULL OR r.location=:loc)
                    """
                ),
                {"lsr": g["lsr_id"], "st": g["status"], "loc": g["location"]},
            ).scalars().all()
        
        for rid in member_ids:
            db.execute(
                text(
                    "INSERT INTO pattern_reports (pattern_id, report_id, similarity) "
                    "VALUES (:p,:r,NULL) ON CONFLICT (pattern_id, report_id) DO NOTHING"
                ),
                {"p": pid, "r": rid},
            )
    db.commit()


# ---------------- the "why" (dominance + lift) ----------------

def pattern_why(db, pattern_id: int, member_ids: list[int]) -> dict:
    """Explain a pattern with dominance + lift.

    lift(factor) = (count inside pattern / member_count) / (global count / all reports).
    Drivers with lift >= 1 are distinctive enough to surface as the "why".
    """
    if not member_ids:
        return {"pattern_id": pattern_id, "members": 0, "reports": [], "drivers": []}

    n = len(member_ids)
    placeholders = ",".join([":" + str(i) for i in range(n)])
    params = {str(i): m for i, m in enumerate(member_ids)}

    prec = db.execute(
        text(
            f"SELECT p.name, rp.status, COUNT(*) FROM report_precursors rp "
            f"JOIN precursors p ON p.id=rp.precursor_id "
            f"WHERE rp.report_id IN ({placeholders}) AND rp.status IN ('PRESENT','AMBIGUOUS') "
            f"GROUP BY 1,2 ORDER BY 3 DESC LIMIT 8"
        ),
        params,
    ).fetchall()
    haz = db.execute(
        text(
            f"SELECT h.code, COUNT(*) FROM report_hazards rh JOIN hazards h ON h.id=rh.hazard_id "
            f"WHERE rh.report_id IN ({placeholders}) GROUP BY 1 ORDER BY 2 DESC LIMIT 5"
        ),
        params,
    ).fetchall()
    loc = db.execute(
        text(
            f"SELECT location, COUNT(*) FROM reports WHERE id IN ({placeholders}) "
            f"GROUP BY 1 ORDER BY 2 DESC LIMIT 5"
        ),
        params,
    ).fetchall()
    bf = db.execute(
        text(
            f"SELECT COUNT(*) FROM report_features WHERE report_id IN ({placeholders}) AND barrier_failure_present = TRUE"
        ),
        params,
    ).scalar() or 0
    
    # LSR drivers
    lsr = db.execute(
        text(
            f"SELECT lsr.rule_id, lsr.name, rlsr.status, COUNT(*) FROM report_life_saving_rules rlsr "
            f"JOIN life_saving_rules lsr ON lsr.id=rlsr.lsr_id "
            f"WHERE rlsr.report_id IN ({placeholders}) AND rlsr.status IN ('BROKEN','UNCERTAIN') "
            f"GROUP BY 1,2,3 ORDER BY 4 DESC LIMIT 5"
        ),
        params,
    ).fetchall()

    total_reports = db.execute(text("SELECT count(*) FROM reports")).scalar() or 1

    drivers = []
    for name, status, cnt in prec:
        global_cnt = db.execute(text(
            "SELECT COUNT(*) FROM report_precursors rp JOIN precursors p ON p.id=rp.precursor_id "
            "WHERE p.name=:nm AND rp.status=:st"
        ), {"nm": name, "st": status}).scalar() or 0
        gs = global_cnt / total_reports
        ms = cnt / n
        lift = (ms / gs) if gs else None
        drivers.append({"kind": "precursor", "name": name, "status": status,
                        "count": cnt, "lift": round(lift, 2) if lift else None})

    for code, cnt in haz:
        global_cnt = db.execute(text(
            "SELECT COUNT(*) FROM report_hazards rh JOIN hazards h ON h.id=rh.hazard_id WHERE h.code=:c"
        ), {"c": code}).scalar() or 0
        gs = global_cnt / total_reports
        ms = cnt / n
        lift = (ms / gs) if gs else None
        drivers.append({"kind": "hazard", "name": code, "count": cnt,
                        "lift": round(lift, 2) if lift else None})
    
    for rule_id, name, status, cnt in lsr:
        global_cnt = db.execute(text(
            "SELECT COUNT(*) FROM report_life_saving_rules rlsr JOIN life_saving_rules lsr ON lsr.id=rlsr.lsr_id "
            "WHERE lsr.rule_id=:rid AND rlsr.status=:st"
        ), {"rid": rule_id, "st": status}).scalar() or 0
        gs = global_cnt / total_reports
        ms = cnt / n
        lift = (ms / gs) if gs else None
        drivers.append({"kind": "lsr", "name": f"{rule_id}: {name}", "status": status, "count": cnt,
                        "lift": round(lift, 2) if lift else None})

    return {
        "pattern_id": pattern_id,
        "members": n,
        "barrier_failure_rate": round(bf / n, 3) if n else 0,
        "locations": [{"name": l[0], "count": l[1]} for l in loc],
        "dominant_precursors": [{"name": p[0], "status": p[1], "count": p[2]} for p in prec],
        "dominant_hazards": [{"name": h[0], "count": h[1]} for h in haz],
        "dominant_lsr": [{"rule_id": l[0], "name": l[1], "status": l[2], "count": l[3]} for l in lsr],
        "drivers": [d for d in drivers if d["lift"] is None or d["lift"] >= 1.0],
    }