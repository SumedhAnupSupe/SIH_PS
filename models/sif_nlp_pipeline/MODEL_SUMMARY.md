# SIF NLP Pipeline v3.0.0 — Model Summary

## Overview

The **SIF NLP Pipeline** is an evidence-to-feature transformation system that processes raw safety incident reports and produces structured, machine-readable outputs for Safety-Incident-Free (SIF) precursor analysis. It is designed for the oil and gas industry and follows the EEI (Energy Institute) SIF precursor framework extended with oil-and-gas-specific precursors, the Unified SIF Classification Tree, and IOGP Report 459 Life-Saving Rules.

The pipeline accepts `.txt` incident reports and produces:
- Cleaned text files
- Human-readable SIF analysis summaries
- Structured JSON analysis outputs
- ML-ready encoded and raw CSV DataFrames
- Parquet output (optional)

---

## Architecture

```
                         RAW REPORT (.txt)
                              |
                              v
                     ┌─────────────────┐
                     │   PREPROCESSOR   │  TextPreprocessor
                     │  (Cleaning +     │  - Read raw text
                     │   Segmentation)  │  - Normalize whitespace/encoding
                     └────────┬────────┘  - Segment sentences & paragraphs
                              |           - Extract metadata (ID, date, location)
                              v
                     ┌─────────────────┐
                     │ EVIDENCE         │  EvidenceExtractor
                     │ EXTRACTOR        │  - Keyword/pattern matching
                     └────────┬────────┘  - Precursor evidence (22 precursors)
                              |           - High-energy analysis (9 categories)
                              |           - Direct control assessment
                              |           - Outcome evidence (fatality, SIF injury)
                              |           - Two-IF test evaluation
               ┌──────────────┼──────────────┐
               |              |              |
               v              v              v
     ┌──────────────┐ ┌─────────────┐ ┌──────────────────┐
     │  PRECURSOR   │ │    IOGP     │ │    UNIFIED SIF   │
     │   MAPPER     │ │   459 LSR   │ │  CLASSIFICATION  │
     │  (22 EEI+OG  │ │   MAPPER    │ │     TREE         │
     │  Precursors) │ │  (9 Rules)  │ │  (Q1-Q8 nodes)   │
     └──────┬───────┘ └──────┬──────┘ └──────┬───────────┘
            |                |               |
            v                |               v
     ┌──────────────┐        |        ┌──────────────────┐
     │   CLUSTERS   │        |        │   UNIFIED SIF    │
     │   DENSITY    │        |        │  SCORE ENGINE    │
     │ INTERACTIONS │        |        │ (classification- │
     └──────┬───────┘        |        │  based scoring)  │
            |                |        └──────┬───────────┘
            |                |               |
            +────────────────┼───────────────+
                             |
                             v
                     ┌─────────────────┐
                     │ FEATURE ENGINEER│  Builds single-row DataFrame
                     └────────┬────────┘  (~180+ features)
                              |
                              v
                     ┌─────────────────┐
                     │   SUMMARIZER    │  Human-readable summary + JSON
                     └────────┬────────┘
                              |
                              v
                     ┌─────────────────┐
                     │  OUTPUT BUILDER │  Saves all artifacts
                     └─────────────────┘
```

---

## Pipeline Stages

### 1. TextPreprocessor (`preprocessor.py` — 93 lines)

Cleans and segments raw incident report text.

| Method | Description |
|--------|-------------|
| `read_report(file_path)` | Reads raw text from file |
| `clean(raw_text)` | Removes page numbers, confidential headers, normalizes whitespace, strips non-ASCII |
| `segment_sentences(text)` | Splits into sentence dicts with `sentence_id`, `text`, `is_heading` |
| `segment_paragraphs(text)` | Splits into paragraph blocks with `paragraph_id`, `text`, `sentence_count` |
| `extract_metadata(text)` | Regex extraction of incident_date, incident_id, location, worker_count, injury_severity |
| `preprocess(file_path)` | Orchestrates all steps, returns structured dict |

### 2. EvidenceExtractor (`evidence_extractor.py`)

Extracts SIF-relevant evidence using keyword and regex pattern matching against preprocessed sentences. Extended with high-energy, outcome, direct control, and two-IF test extraction.

| Method | Description |
|--------|-------------|
| `_match_keywords(text, keyword_groups)` | Generic regex matcher over keyword dictionaries |
| `_match_precursor_evidence(sentences)` | Scans all 22 precursor present/absent keyword sets per sentence |
| `_extract_task_type(sentences)` | Matches against 12 task categories |
| `_extract_hazards(sentences)` | Matches against 9 hazard categories |
| `_extract_controls(sentences)` | Matches control_present, control_missing, control_failed |
| `_extract_worker_info(sentences)` | Matches training_known, experience_known, supervision, communication_issue |
| `_extract_environment(sentences)` | Matches weather_change, lighting_issue, site_condition_change |
| `_extract_work_changes(sentences)` | 8 work condition change indicators |
| `_extract_high_energy_evidence(sentences)` | 9 energy source categories + 8 exposure categories |
| `_extract_outcome_evidence(sentences)` | Fatality, life-threatening, life-altering, minor injury, near miss, sustained SIF |
| `_extract_direct_control_assessment(sentences)` | Direct control present/failed/missing state |
| `_extract_two_if_test(sentences)` | First IF (prevention) and second IF (protection) assessment |
| `_extract_equipment_evidence(sentences)` | Equipment malfunction, mechanical failure, guarding, instrumentation |
| `extract_all(preprocessed_data)` | Orchestrates all extraction, returns complete evidence dict |

### 3. PrecursorMapper (`precursor_mapper.py`)

Maps extracted evidence to the 22 SIF precursor categories (13 EEI + 9 oil-and-gas).

| Precursor | Category | Description |
|-----------|----------|-------------|
| `safe_work_procedure` | EEI | Safe Work Procedure adherence |
| `hazard_recognition` | EEI | Hazard recognition/awareness |
| `departure_from_routine` | EEI | Departure from routine conditions |
| `plan_to_address_work_change` | EEI | Plan to address work change |
| `safety_attitudes` | EEI | Safety attitudes and prioritization |
| `rules_and_procedures` | EEI | Rules and procedures compliance |
| `familiarity_with_task` | EEI | Familiarity with task |
| `risk_normalization` | EEI | Risk normalization/complacency |
| `productivity_pressure` | EEI | Productivity/schedule pressure |
| `perceived_safety_culture` | EEI | Perceived safety culture |
| `stop_work_execution` | EEI | Stop-work authority execution |
| `workers_inactive_in_safety` | EEI | Workers inactive in safety |
| `pre_task_plan` | EEI | Pre-task planning |
| `critical_control_failure` | OG | Critical control failure |
| `high_energy_exposure` | OG | High energy exposure |
| `energy_isolation_failure` | OG | Energy isolation failure |
| `line_of_fire_exposure` | OG | Line of fire exposure |
| `critical_control_verification_failure` | OG | Critical control verification failure |
| `management_of_change_gap` | OG | Management of change gap |
| `competency_supervision_gap` | OG | Competency/supervision gap |
| `work_authorization_gap` | OG | Work authorization gap |
| `simops_or_concurrent_operations` | OG | Simultaneous operations |

**Status values:** NOT_APPLICABLE (-1), NOT_MENTIONED (0), ABSENT (1), AMBIGUOUS (2), PRESENT (3)

**Output per precursor:**
- `status` (IntEnum)
- `status_label` (human-readable string)
- `confidence` (0.0–1.0)
- `evidence_count`
- `evidence_strength` (0.0–1.0, ratio of evidence to total sentences)
- `present_evidence` (list of evidence items)
- `absent_evidence` (same structure)

### 4. Precursor Clusters

22 precursors are grouped into 6 clusters for aggregate analysis:

| Cluster | Members | Description |
|---------|---------|-------------|
| `personnel` | hazard_recognition, safety_attitudes, familiarity_with_task, risk_normalization, productivity_pressure, perceived_safety_culture, workers_inactive_in_safety, competency_supervision_gap | Human factors and readiness |
| `planning` | safe_work_procedure, departure_from_routine, plan_to_address_work_change, pre_task_plan, management_of_change_gap, work_authorization_gap | Planning and procedure adequacy |
| `equipment` | rules_and_procedures, critical_control_failure, energy_isolation_failure, critical_control_verification_failure | Equipment and control failures |
| `barrier` | stop_work_execution, critical_control_failure, energy_isolation_failure, critical_control_verification_failure | Safety barrier degradation |
| `organizational` | perceived_safety_culture, risk_normalization, productivity_pressure, management_of_change_gap, competency_supervision_gap, work_authorization_gap, simops_or_concurrent_operations | Systemic/organizational factors |
| `environment` | high_energy_exposure, line_of_fire_exposure, departure_from_routine, simops_or_concurrent_operations | Environmental and exposure conditions |

**Per-cluster output:** contribution_score, density, evidence_coverage, present_count, applicable_count

### 5. Precursor Density Metrics

| Metric | Description |
|--------|-------------|
| `raw` | present_count / applicable_count |
| `evidence_weighted` | Weighted by severity, confidence, and evidence strength |
| `high_energy_conditional` | evidence_weighted × high_energy_factor × barrier_degradation_factor |
| `evidence_strength` | Average evidence strength across all precursors |

### 6. Precursor Interactions

| Interaction | Left Precursor | Right Precursor |
|-------------|---------------|-----------------|
| `hazard_energy_x_control_failure` | high_energy_exposure | critical_control_failure |
| `departure_x_reassessment_missing` | departure_from_routine | management_of_change_gap |
| `productivity_x_risk_normalization` | productivity_pressure | risk_normalization |
| `energy_isolation_x_broken_lsr` | energy_isolation_failure | stop_work_execution |
| `stop_work_x_continued_work` | stop_work_execution | productivity_pressure |

### 7. Unified SIF Classification Tree (`unified_sif_classifier.py` — NEW)

Replaces the old 7-node tree with the Unified SIF Classification Tree for Oil & Gas.

| Node | Question | YES → | NO → |
|------|----------|-------|------|
| Q1 | Was there a fatality? | **ACTUAL_SIF_FATALITY** | Q2 |
| Q2 | Was there a life-threatening or life-altering injury? | **ACTUAL_SIF_SERIOUS_INJURY** | Q3 |
| Q3 | Was a high-energy source present? | Q4 | **Q8** (low severity) |
| Q4 | Was there a high-energy incident? | Q5 | Q6 |
| Q5 | Was there a direct control present? | Outcome-dependent | Outcome-dependent |
| Q6 | Was there a direct control for high energy? | **SUCCESS** | **EXPOSURE** |
| Q7 | Two-IF test: first IF absent AND second IF absent? | **HSIF** | varies |
| Q8 | Low-severity event? | **LOW_SEVERITY** | — |

**Q5 outcomes based on direct control × sustained SIF:**

| Direct Control | Sustained SIF | Classification | Tier |
|---------------|---------------|----------------|------|
| Present | Yes | **LSIF** | 2 |
| Present | No | **CAPACITY** | 3 |
| Missing/Failed | Yes | **HSIF** | 2 |
| Missing/Failed | No | **PSIF** | 2 |

**Output:**
```json
{
  "classification": "HSIF|PSIF|LSIF|CAPACITY|EXPOSURE|LOW_SEVERITY|ACTUAL_SIF_FATALITY|ACTUAL_SIF_SERIOUS_INJURY",
  "tier": 1,
  "tree_version": "unified_sif_tree_v1",
  "confidence": 0.92,
  "path": [{ "node_id", "question", "answer", "confidence", "evidence", "reason" }],
  "terminal_node": "Q5",
  "reason": "...",
  "evidence": [...]
}
```

### 8. Unified SIF Score Engine (`unified_sif_score_engine.py` — REPLACES `sif_scorer.py`)

Converts tree classification into a continuous [0, 1] SIF score with documented limitations.

| Classification | Base Score |
|---------------|------------|
| ACTUAL_SIF_FATALITY | 1.00 |
| ACTUAL_SIF_SERIOUS_INJURY | 0.95 |
| HSIF | 0.90 |
| LSIF | 0.85 |
| PSIF | 0.80 |
| SIF_POTENTIAL | 0.70 |
| EXPOSURE | 0.60 |
| CAPACITY | 0.50 |
| LOW_SEVERITY | 0.20 |
| NO_SIF_POTENTIAL | 0.10 |

Adjusted by precursor evidence presence ratio (+0–0.15).

### 9. IOGP 459 LSRMapper (`lsr_mapper.py` — 210 lines)

Maps structured evidence to the 9 IOGP Report 459 Life-Saving Rules. **Retained as independent reporting branch, NOT used as predictive feature by Model 2.**

**Status values:** BROKEN, NOT_BROKEN, UNCERTAIN, NOT_APPLICABLE

### 10. FeatureEngineer (`feature_engineer.py`)

Builds a single-row ML-ready pandas DataFrame from all pipeline results.

**Feature groups:**

| Group | Columns | Count |
|-------|---------|-------|
| Precursor features | `precursor_name`, `_confidence`, `_evidence_count`, `_evidence_strength` per precursor | 88 |
| Cluster features | `cluster_<name>_contribution_score`, `_density`, `_evidence_coverage`, `_present_count` per cluster | 24 |
| Density features | raw, evidence_weighted, applicable_count, present_count, evidence_strength | 5 |
| Interaction features | 5 interaction features | 5 |
| Unified tree features | confidence, tier, terminal_node, Q1-Q8 confidences | 11 |
| General features | task_type, hazard_count, control indicators | 6 |
| Environment features | 9 work-change indicators | 9 |
| Worker features | 6 worker readiness indicators | 6 |
| High-energy features | present, incident, source_count, 9 category flags | 12 |
| Direct-control features | present, failed, missing, confidence | 4 |
| Barrier density features | density, evidence_coverage, present_count | 3 |
| Missing info features | 5 missing information indicators | 5 |
| Text stats | report_length, sentence_count, relevant_count, relevance_ratio | 4 |
| Consistency features | hazard_consistency, barrier_consistency, energy_consistency, intra_model_consistency | 4 |
| LSR features | broken_count, broken_list, 9× status, 9× confidence | 20 |
| Score features | sif_score, method, weight_source | 3 |
| **Total** | | **~200+** |

### 11. SIFSummarizer (`summarizer.py`)

Generates human-readable summaries and structured JSON analysis.

**Summary sections:**
1. Report Overview (length, sentence count)
2. Unified SIF Classification Tree (classification, tier, confidence, path)
3. High-Energy Analysis (present, incident, sources, exposure categories)
4. Direct Control Assessment (state, confidence, evidence)
5. SIF Precursor Analysis (22 precursors grouped by PRESENT/ABSENT/AMBIGUOUS/NOT_APPLICABLE/NOT_MENTIONED)
6. Precursor Cluster Analysis (6 clusters with density, contribution, coverage)
7. Precursor Density (raw, evidence-weighted)
8. Model Consistency (hazard, barrier, energy, overall)
9. Supporting Evidence Details
10. Identified Hazards
11. Work Condition Changes
12. Summary Assessment (precursor density + classification)
13. IOGP Report 459 Life-Saving Rules
14. SIF Score (score, method, limitations)

**JSON analysis includes:**
- incident_id, summary, metadata, report_statistics
- unified_tree (full classification result)
- high_energy, direct_control, outcome, two_if_test
- precursor_analysis (all 22 with evidence and strength)
- cluster_analysis (6 clusters)
- density, interaction_features, consistency
- hazards, task_types, controls, environment, work_changes, worker_info
- life_saving_rules (full analysis)
- sif_score (classification-based score object)

### 12. SIFPipeline (`pipeline.py`)

Orchestrates the full pipeline.

**Processing order:**
1. Preprocess report
2. Extract evidence (22 precursors, high-energy, outcome, direct control, two-IF)
3. Map precursors (22 precursors, NOT_APPLICABLE status)
4. Compute clusters (6 clusters)
5. Compute density (raw, evidence-weighted, high-energy conditional)
6. Compute interactions (5 interactions)
7. Classify via unified tree (Q1-Q8)
8. Compute unified SIF score
9. Map IOGP LSR
10. Build features (~200+ columns)
11. Validate all outputs
12. Generate summary and JSON
13. Save outputs

---

## Configuration

All configurable parameters live in `config.py`:

| Parameter | Value | Description |
|-----------|-------|-------------|
| `UNIFIED_TREE_VERSION` | `"unified_sif_tree_v1"` | Tree version identifier |
| `PrecursorStatus` | IntEnum(-1 to 3) | Precursor status levels |
| `SIFClassification` | String constants | 10 classification outcomes |
| `SIF_CLASSIFICATION_TIER` | Dict | Classification → tier mapping |
| `SIF_PRECURSORS` | 22 precursors | EEI + oil-and-gas precursor keys |
| `PRECURSOR_CLUSTERS` | 6 clusters | Precursor groupings |
| `PRECURSOR_INTERACTIONS` | 5 interactions | Precursor interaction pairs |
| `IOGP_LSR_RULES` | 9 rules | IOGP Report 459 rule keys |

---

## Dependencies

| Package | Usage |
|---------|-------|
| `pandas` | DataFrame construction, CSV/Parquet I/O |
| `re` (stdlib) | All regex pattern matching |
| `json` (stdlib) | JSON output serialization |
| `enum` (stdlib) | PrecursorStatus, SIFClassification |
| `pathlib` (stdlib) | File path handling |
| `typing` (stdlib) | Type hints |

No external NLP libraries, ML frameworks, or heavy dependencies required.

---

## Validation

The pipeline validates at every stage:

| Validator | Checks |
|-----------|--------|
| `FeatureEngineer.validate()` | Schema completeness, column types, value ranges (0–1 for confidence/score), binary columns, LSR status validity, no data leakage |
| `UnifiedSIFClassifier.validate()` | Valid classification, tier 1–3, confidence 0–1, path non-empty |
| `UnifiedSIFScoreEngine.validate()` | Score in [0,1], classification valid, tree confidence recorded |
| `LSRMapper.validate()` | 9 rules, valid statuses, confidence ranges, BROKEN has evidence, count consistency |
| `PrecursorMapper.compute_clusters()` | Cluster density, contribution score, evidence coverage |
| `PrecursorMapper.compute_density()` | Raw and evidence-weighted density within [0,1] |

---

## Design Principles

1. **Single source of evidence** — All downstream analysis consumes the same extracted evidence layer
2. **Traceability** — Every tree decision and score links back to source sentence IDs
3. **22 precursors with oil-and-gas extensions** — 13 EEI + 9 industry-specific
4. **NOT_APPLICABLE status** — Precursors not relevant to a report are excluded from density
5. **Cluster-based aggregate analysis** — 6 clusters for systemic pattern detection
6. **High-energy conditional density** — Density weighted by energy presence and barrier state
7. **Consistency checking** — Hazard, barrier, and energy consistency between tree and precursors
8. **Two-IF test** — Prevention and protection barrier assessment for HSIF determination
9. **Barrier failure rate** — Deterministic calculation for Model 2 consumption
10. **IOGP LSR independent** — Retained as reporting branch, not predictive feature
11. **Configurability** — All parameters are project-level configuration
12. **No ML classifiers** — Rule-based classification only
