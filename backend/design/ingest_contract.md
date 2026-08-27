# Ingestion Contract (for the NLP-pipeline owner)

This documents the exact output your pipeline produces that the downstream **Safety
Intelligence Layer** consumes. The downstream layer merges two artifacts per report and
stores them in PostgreSQL + pgvector. **Do not change the existing fields** — add the new
SIF block only.

## 1. Files consumed (per report)

| Artifact | Path | Contains |
|----------|------|----------|
| Analysis JSON | `outputs/analyses/INC-*.json` | structured meaning: metadata, 13 behavioral precursors (status/confidence/evidence), hazards, task_types, work_changes, worker_info |
| Feature CSV | `outputs/sif_features_raw.csv` / `_encoded.csv` | 70 numeric/flag columns, incl. `barrier_failure_present`, `control_failure_present`, `missing_control_present`, `control_deviation_present` |
| Summary text | `outputs/summaries/INC-*.txt` | human-readable per-report summary |
| Cleaned raw | `outputs/report_cleaned_*.txt` | the cleaned original report text (stored as `raw_text`) |

## 2. What is parsed from the analysis JSON

- `metadata.incident_id`, `metadata.incident_date`, `metadata.location`, `metadata.injury_severity`
- `precursor_analysis.*` → each precursor key: `status` (`PRESENT`/`AMBIGUOUS`/`NOT_MENTIONED`),
  `confidence`, `evidence_count`, plus `present_evidence[]` and `absent_evidence[]`
  (each item `{text, source_sentence_id}`) → stored with traceability to the original sentence.
- `hazards[]` → `{hazard_type, evidence[]}`
- `task_types[]` → `{task_type, evidence[]}`
- `work_changes{}` → booleans (`work_plan_changed`, `unexpected_condition`, ...)
- `worker_info`, `environment`, `report_statistics`

## 3. Requested addition — SIF score (optional, backward-compatible)

To give the system a real SIF dimension, please add one top-level key to the analysis JSON.
If absent, the downstream layer simply stores NULL — nothing breaks.

```json
"sif": {
  "score": 0.87,
  "class": "HIGH",        // LOW | MEDIUM | HIGH
  "method": "rule_weights"
}
```

`score` is 0..1. It should reflect the cumulative risk from the dominant precursors
(PRESENT/AMBIGUOUS), control-failure and barrier-failure flags. The downstream layer maps
this to `reports.sif_score` / `reports.sif_class`.

## 4. Stability rules (for correct downstream aggregation)

1. `incident_id` must be globally unique and stable across the JSON, CSV and summary files.
2. Precursor `status` uses exactly the set {`PRESENT`, `AMBIGUOUS`, `NOT_MENTIONED`}.
3. Avoid changing the 13-precursor vocabulary — the feature CSV columns are keyed on them
   (39 columns = 13 × {status_num, confidence, evidence_count}).
4. Keep `source_sentence_id` int, if defined; downstream uses it for explainability links.