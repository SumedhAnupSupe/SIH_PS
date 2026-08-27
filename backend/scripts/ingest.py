"""Ingest NLP pipeline output + attention model output into the Safety Intelligence Layer.

Usage:
    DATABASE_URL=... ANALYSES_DIR=... FEATURES_DIR=... python -m scripts.ingest

Reads `outputs/analyses/INC-*.json`, `outputs/sif_features_encoded.csv`
(falls back to `_raw`), plus per-report `report_cleaned_*.txt` /
`summaries/INC-*.txt`; optionally loads attention model assessment JSONs
from `models/sif_attention_model/outputs/assessments/`.
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import pandas as pd

from app.config import settings
from app.db import apply_schema, engine
from app.services.ingest_service import ingest_report

# Attention model assessment directory (sibling of backend/)
ATTENTION_ASSESSMENTS_DIR = (
    pathlib.Path(__file__).resolve().parent.parent.parent
    / "models" / "sif_attention_model" / "outputs" / "assessments"
)


def _read_file(*paths: pathlib.Path) -> str:
    for p in paths:
        if p and p.is_file():
            try:
                return p.read_text()
            except Exception:
                continue
    return ""


def main():
    apply_schema()
    analyses_dir = pathlib.Path(settings.analyses_dir)
    features_dir = pathlib.Path(settings.features_dir)
    if not analyses_dir.is_dir():
        print(f"[ingest] analyses dir not found: {analyses_dir}")
        return

    feats_map = {}
    for name in ("sif_features_encoded.csv", "sif_features_raw.csv"):
        p = features_dir / name
        if p.exists():
            for _, row in pd.read_csv(p, dtype=str).iterrows():
                feats_map[str(row.get("incident_id"))] = row.to_dict()
            print(f"[ingest] loaded {name}: {len(feats_map)} feature rows")
            break

    summaries_dir = analyses_dir.parent / "summaries"

    # Load attention model assessments if available
    attention_map = {}
    if ATTENTION_ASSESSMENTS_DIR.is_dir():
        for af in ATTENTION_ASSESSMENTS_DIR.glob("attention_assessment_*.json"):
            try:
                adata = json.loads(af.read_text())
                aid = adata.get("incident_id")
                if aid:
                    attention_map[aid] = adata
            except Exception:
                pass
        print(f"[ingest] loaded {len(attention_map)} attention assessments")

    json_files = sorted(analyses_dir.glob("*.json"))
    print(f"[ingest] {len(json_files)} analysis JSONs")

    n = 0
    with engine.begin() as conn:
        for jf in json_files:
            analysis = json.loads(jf.read_text())
            meta = analysis.get("metadata", {}) or {}
            iid = meta.get("incident_id") or analysis.get("incident_id")
            feats = feats_map.get(iid, {})
            raw_text = _read_file(analyses_dir.parent / f"report_cleaned_{iid}.txt")
            summary = _read_file(
                summaries_dir / f"{iid}.txt", summaries_dir / f"summary_{iid}.txt"
            ) or analysis.get("summary", "")
            attention_output = attention_map.get(iid)
            rid = ingest_report(conn, analysis, feats, raw_text, summary, attention_output=attention_output)
            if rid:
                n += 1
    print(f"[ingest] done: {n} reports ingested")


if __name__ == "__main__":
    main()