# SIF Attention Prioritization Model v3.0.0 - Summary

## Overview

The **SIF Attention Prioritization Model** (Model 2) is a downstream decision-support system that consumes outputs from the upstream SIF NLP Evidence-to-Feature pipeline (Model 1). It determines what needs attention, how urgently, and what intervention categories are appropriate for safety incidents.

This document summarizes the model after adaptation to the v3.0.0 upstream, which uses the **Unified SIF Classification Tree** with 22 precursors, clusters, density, high-energy analysis, direct control assessment, barrier failure rate, and consistency features.

---

## Architecture

```
                         Model 1 Outputs
                               |
           +-------------------+-------------------+
           |                   |                   |
           v                   v                   v
       Structured CSV     Evidence JSON       Summary Text
           |
           v
    Feature preprocessing
           |
           +-------------------------+
           |                         |
           v                         v
   Structured tabular model     Text embedding branch
           |                         |
           |                 Similar incident retrieval
           |                 Similar action retrieval
           |                         |
           +------------+------------+
                        |
                        v
              Multi-task prediction
                   /          \
                  /            \
                 v              v
           Urgency head      Action heads
                               |
                               v
                    Safety Guard Layer
                               |
                               v
                    Barrier Assessment
                               |
                               v
                      Final Output
```

---

## Upstream Integration

### Current Upstream Model 1 Outputs (v3.0.0)

The upstream pipeline produces:

```
report_cleaned_{ID}.txt
summaries/{ID}.txt
analyses/{ID}.json
sif_features_encoded.csv
sif_features_raw.csv
sif_features.parquet
```

### Key Change: Unified SIF Classification Tree

The upstream model now evaluates incidents through the **Unified SIF Classification Tree** (`unified_sif_tree_v1`) with 8 nodes (Q1-Q8) and produces:

| Classification | Tier | Description |
|---------------|------|-------------|
| `ACTUAL_SIF_FATALITY` | 1 | Fatality occurred |
| `ACTUAL_SIF_SERIOUS_INJURY` | 1 | Life-threatening/altering injury |
| `HSIF` | 2 | High-severity SIF - no direct control |
| `PSIF` | 2 | Potential SIF - no direct control |
| `LSIF` | 2 | Low-severity SIF with direct control |
| `CAPACITY` | 3 | Capacity/organizational factor |
| `EXPOSURE` | 3 | High energy present, no incident |
| `LOW_SEVERITY` | 3 | Near miss or minor injury |

**Score:** Classification-based with base scores per outcome + precursor evidence adjustment.

---

## Unified SIF Classification Tree (`unified_sif_tree_v1`)

### Tree Nodes

| Node | Question | YES | NO |
|------|----------|-----|-----|
| Q1 | Was there a fatality? | `ACTUAL_SIF_FATALITY` | Q2 |
| Q2 | Was there a life-threatening or life-altering injury? | `ACTUAL_SIF_SERIOUS_INJURY` | Q3 |
| Q3 | Was a high-energy source present? | Q4 | Q8 (low severity) |
| Q4 | Was there a high-energy incident (energy release and worker proximity)? | Q5 | Q6 |
| Q5 | Was there a direct control present? | Outcome-dependent | Outcome-dependent |
| Q6 | Was there a direct control for the high-energy source? | `SUCCESS` | `EXPOSURE` |
| Q7 | Two-IF test: first IF absent AND second IF absent? | `HSIF` | varies |
| Q8 | Low-severity event? | `LOW_SEVERITY` | — |

### Q5 Outcomes

| Direct Control | Sustained SIF | Classification | Tier |
|---------------|---------------|----------------|------|
| Present | Yes | `LSIF` | 2 |
| Present | No | `CAPACITY` | 3 |
| Missing/Failed | Yes | `HSIF` | 2 |
| Missing/Failed | No | `PSIF` | 2 |

---

## Input Features

### Group A: SIF Precursor Signals (88 columns)

For each of 22 precursors: `<precursor>`, `<precursor>_confidence`, `<precursor>_evidence_count`, `<precursor>_evidence_strength`

| Precursor | Status Encoding |
|-----------|----------------|
| safe_work_procedure | -1=NOT_APPLICABLE, 0=NOT_MENTIONED, 1=ABSENT, 2=AMBIGUOUS, 3=PRESENT |
| ... (13 EEI precursors) | |
| critical_control_failure | |
| high_energy_exposure | |
| energy_isolation_failure | |
| line_of_fire_exposure | |
| critical_control_verification_failure | |
| management_of_change_gap | |
| competency_supervision_gap | |
| work_authorization_gap | |
| simops_or_concurrent_operations | |

### Group B: General Incident Features

Task type, hazard count, control failure indicators.

### Group C: Environmental/Work-Change Features (9 columns)

Environmental change, unexpected condition, work plan changed, task changed, equipment changed, procedure changed, work sequence changed, reassessment performed/missing.

### Group D: Worker/Readiness Features (6 columns)

Worker training known, experience known, hazard awareness, safety engagement, supervision present, communication issue.

### Group E: Missing-Information Features (5 columns)

Procedure info missing, pre-task plan info missing, worker experience info missing, hazard info missing, stop work info missing.

### Group F: High-Energy Features (12 columns)

| Feature | Description |
|---------|-------------|
| `high_energy_present` | High-energy source detected |
| `high_energy_incident` | High-energy incident occurred |
| `high_energy_source_count` | Number of energy source categories |
| `high_energy_mechanical` through `high_energy_biological` | Per-category flags |

### Group G: Direct Control Features (4 columns)

| Feature | Description |
|---------|-------------|
| `direct_control_present` | Direct control present and effective |
| `direct_control_failed` | Direct control present but failed |
| `direct_control_missing` | No direct control in place |
| `direct_control_confidence` | Assessment confidence [0,1] |

### Group H: Cluster Features (24 columns)

Per cluster (personnel, planning, equipment, barrier, organizational, environment):
- `cluster_<name>_contribution_score`
- `cluster_<name>_density`
- `cluster_<name>_evidence_coverage`
- `cluster_<name>_present_count`

### Group I: Density Features (5 columns)

| Feature | Description |
|---------|-------------|
| `precursor_density_raw` | present_count / applicable_count |
| `precursor_density_evidence_weighted` | Severity-weighted density |
| `precursor_applicable_count` | Non-NOT_APPLICABLE precursors |
| `precursor_present_count` | PRESENT precursors |
| `precursor_evidence_strength` | Average evidence strength |

### Group J: Barrier Density Features (3 columns)

| Feature | Description |
|---------|-------------|
| `barrier_density` | Barrier cluster density |
| `barrier_evidence_coverage` | Barrier evidence coverage |
| `barrier_present_count` | Present barrier precursors |

### Group K: Consistency Features (4 columns)

| Feature | Description |
|---------|-------------|
| `hazard_consistency` | Consistency between tree classification and precursor density |
| `barrier_consistency` | Consistency between direct control and barrier cluster |
| `energy_consistency` | Consistency between high energy and tree path |
| `intra_model_consistency` | Average of above three |

### Group L: Interaction Features (5 columns)

| Feature | Description |
|---------|-------------|
| `hazard_energy_x_control_failure` | High energy × control failure |
| `departure_x_reassessment_missing` | Routine departure × no reassessment |
| `productivity_x_risk_normalization` | Productivity pressure × risk normalization |
| `energy_isolation_x_broken_lsr` | Energy isolation failure × stop work absent |
| `stop_work_x_continued_work` | Stop work ambiguous × work continued |

### Group M: IOGP Life-Saving Rule Features (20 columns)

For each of 9 LSR rules: `lsr_<rule>_status`, `lsr_<rule>_confidence`

**Note:** IOGP LSR features are retained for backward compatibility but are NOT used as predictive features by Model 2. They remain available as independent reporting signals.

### Group N: Unified Tree Features (11 columns)

| Feature | Description |
|---------|-------------|
| `unified_tree_confidence` | Overall tree confidence [0,1] |
| `unified_tree_tier` | 1, 2, or 3 |
| `unified_tree_terminal_node` | Q1-Q8 terminal node |
| `tree_Q1_confidence` through `tree_Q8_confidence` | Per-node confidence |

### Group O: Derived Downstream Features

| Feature | Description |
|---------|-------------|
| `present_precursor_count` | Count of precursors with status=PRESENT |
| `ambiguous_precursor_count` | Count of precursors with status=AMBIGUOUS |
| `not_applicable_precursor_count` | Count of NOT_APPLICABLE precursors |
| `high_confidence_present_precursor_count` | PRESENT precursors with conf >= 0.7 |
| `mean_precursor_confidence` | Mean confidence of non-zero precursors |
| `total_evidence_count` | Sum of all precursor evidence counts |
| `evidence_strength` | relevant_sentence_count / sentence_count |
| `control_failure_density` | Count of control failure types |
| `work_change_density` | Count of work change types |
| `missing_information_count` | Count of missing information types |
| `reassessment_gap` | Work changed but no reassessment |
| `tree_hsif_x_high_energy` | Interaction: HSIF × high energy |
| `tree_hsif_x_control_failure` | Interaction: HSIF × control failure |
| `density_x_high_energy` | Interaction: density × high energy |
| `barrier_x_direct_control` | Interaction: barrier × direct control failure |

---

## Downstream Outputs

### 1. Attention Urgency (Multi-class Classification)

| Label | Definition |
|-------|------------|
| `IMMEDIATE` | Active/recent condition; intervene now or before work resumes |
| `SHORT_TERM` | Material weakness; correct within hours / next shift |
| `PLANNED` | Systemic/procedural weakness; scheduled corrective action |
| `MONITOR` | No strong evidence for intervention; routine handling |

### 2. Recommended Actions (Multi-label)

25 action categories with time horizons (NOW, NEXT_SHIFT_OR_HOURS, DAYS_TO_WEEKS, LONGER_TERM, MONITOR).

### 3. Systemic Attention

| Level | Description |
|-------|-------------|
| `NONE` | No systemic concern identified |
| `LOW` | Minor systemic signal |
| `MODERATE` | Multiple systemic indicators |
| `HIGH` | Strong systemic pattern detected |

### 4. Barrier Failure Rate (Deterministic)

Calculated from 5 weighted components:

| Component | Weight | Source |
|-----------|--------|--------|
| Direct control failure | 0.30 | `direct_control_failed` or `direct_control_missing` |
| Barrier cluster density | 0.25 | `cluster_barrier_density` |
| Critical control verification failure | 0.20 | `critical_control_verification_failure` precursor |
| Energy isolation failure | 0.15 | `energy_isolation_failure` precursor |
| Stop work absence | 0.10 | `stop_work_execution` precursor |

**Formula:** `BFR = Σ(component × weight)`, clamped to [0, 1]

---

## Rule Engine

### Deterministic Safety Rules

The rule engine provides cold-start predictions and safety overrides. Extended with unified tree and v3.0.0 rules:

| Rule ID | Condition | Output |
|---------|-----------|--------|
| `RULE_ENERGY_ISOLATION_BROKEN` | Energy isolation LSR BROKEN + high energy | IMMEDIATE, STOP_WORK |
| `RULE_HIGH_ENERGY_CONTROL_FAILURE` | High energy + control failure | IMMEDIATE, STOP_WORK |
| `RULE_REASSESSMENT_GAP` | Work changed + no reassessment | SHORT_TERM |
| `RULE_STOP_WORK_NOT_EXERCISED` | Stop-work absent + 2+ precursors | SHORT_TERM |
| `RULE_LSR_BROKEN` | Any single LSR BROKEN | SHORT_TERM |
| `RULE_MULTIPLE_LSR_BROKEN` | 2+ LSR BROKEN | IMMEDIATE |
| `RULE_MULTIPLE_PRECURSORS` | 3+ precursors PRESENT | HIGH systemic |
| `RULE_TREE_HSIF_ACTIVE_EXPOSURE` | HSIF + active exposure | IMMEDIATE |
| `RULE_TREE_TIER_1` | Tier 1 classification | IMMEDIATE |
| `RULE_TREE_HSIF` | HSIF classification | IMMEDIATE |
| `RULE_TREE_PSIF` | PSIF classification | SHORT_TERM |
| `RULE_TREE_EXPOSURE` | Exposure classification | SHORT_TERM |
| `RULE_BARRIER_DENSITY_HIGH` | Barrier density >= 0.6 | IMMEDIATE |
| `RULE_BARRIER_DENSITY_ELEVATED` | Barrier density >= 0.3 | SHORT_TERM |
| `RULE_HIGH_ENERGY_NO_DC` | High energy + no direct control | IMMEDIATE |
| `RULE_CLUSTER_ORG_HIGH` | Organizational cluster >= 0.6 | HIGH systemic |
| `RULE_CLUSTER_ORG_ELEVATED` | Organizational cluster >= 0.4 | MODERATE systemic |
| `RULE_CLUSTER_BARRIER_DEGRADED` | Barrier cluster >= 0.5 | IMMEDIATE |
| `RULE_LOW_CONSISTENCY` | Consistency < 0.3 | HUMAN_REVIEW_REQUIRED |

### Safety Override Behavior

The rule engine overrides ML predictions when the rule engine identifies a critical condition the model missed. Override only upgrades (never downgrades) urgency.

---

## ML Models

### Algorithm Candidates

| Model Family | Algorithms |
|-------------|------------|
| Urgency | Logistic Regression, Random Forest, Gradient Boosting, XGBoost, LightGBM, CatBoost |
| Actions | One-vs-Rest Gradient Boosting (per action) |
| Systemic | Logistic Regression, Random Forest, Gradient Boosting, XGBoost |

### Model Selection Criteria

Best model selected by weighted combination of:
- IMMEDIATE recall (safety priority)
- Macro F1 score
- Misclassification cost

### Calibration

- Isotonic regression for probability calibration
- Cross-validated threshold optimization for action labels

---

## Evaluation Metrics

### Primary Metrics

| Metric | Purpose |
|--------|---------|
| Macro F1 | Balanced multi-class performance |
| Per-class precision/recall | Class-specific performance |
| Recall(IMMEDIATE) | **Critical**: missing immediate incidents |
| PR-AUC | Class imbalance robustness |
| Confusion matrix | Error pattern analysis |

### Calibration Metrics

| Metric | Purpose |
|--------|---------|
| Brier score | Probability accuracy |
| Log loss | Confidence calibration |
| Expected Calibration Error | Reliability |

### Safety-Specific

| Metric | Purpose |
|--------|---------|
| FN cost matrix | Asymmetric misclassification cost |
| IMMEDIATE recall | Minimum acceptable recall |

---

## Uncertainty and Human Review

The model flags incidents for human review when:

- Tree classification has low confidence
- ML urgency confidence < threshold
- Action probabilities are ambiguous
- Evidence is insufficient
- Feature vector is out-of-distribution
- Safety guard is triggered
- Required critical information is missing
- Model consistency < 0.3 (hazard, barrier, or energy inconsistency)

---

## Output Schema

```json
{
  "incident_id": "INC-2026-001",
  "prediction_mode": "RULE_BASED_COLD_START | HYBRID_ML",
  "risk_potential_score": 0.90,
  "upstream_tree_classification": "HSIF",
  "upstream_tree_tier": 2,
  "upstream_tree_confidence": 0.92,
  "upstream_tree_version": "unified_sif_tree_v1",
  "upstream_tree_node_answers": {
    "Q3": "YES",
    "Q4": "YES",
    "Q5": "NO"
  },
  "upstream_tree_node_confidences": {
    "Q3": 0.85,
    "Q4": 0.80,
    "Q5": 0.75
  },
  "barrier_failure_rate": 0.45,
  "barrier_failure_assessment": {
    "failure_rate": 0.45,
    "direct_control_failure_contrib": 0.30,
    "barrier_cluster_contrib": 0.10,
    "critical_control_verification_contrib": 0.00,
    "energy_isolation_contrib": 0.05,
    "stop_work_contrib": 0.00,
    "calculation_method": "deterministic_weighted_sum"
  },
  "attention": {
    "level": "IMMEDIATE",
    "urgency_score": 0.91,
    "confidence": 0.91,
    "systemic_attention": "MODERATE",
    "systemic_attention_score": 0.67
  },
  "actions": [...],
  "drivers": [...],
  "evidence": [...],
  "uncertainty": {
    "missing_information": [],
    "contradictions": [],
    "out_of_distribution": false,
    "human_review_required": false
  },
  "model_metadata": {
    "upstream_pipeline_version": "3.0.0",
    "feature_schema_version": "2.0.0",
    "urgency_model_version": "3.0.0_gradient_boosting",
    "action_model_version": "3.0.0_ovr",
    "rule_engine_version": "3.0.0",
    "prediction_mode": "RULE_BASED_COLD_START"
  }
}
```

---

## Versioning

| Component | Current Version |
|-----------|----------------|
| Upstream Pipeline | 3.0.0 |
| Unified Classification Tree | `unified_sif_tree_v1` |
| Downstream Model | 3.0.0 |
| Feature Schema | 2.0.0 |
| Rule Engine | 3.0.0 |

---

## Implementation Phases

| Phase | Description |
|-------|-------------|
| 1 | CSV/JSON loader, schema validator, feature preprocessing |
| 2 | Deterministic baseline: urgency rules, action mapping, safety guard, barrier assessment |
| 3 | Expert label creation: attention_level, recommended_actions |
| 4 | ML model training and comparison (XGBoost, LightGBM, CatBoost) |
| 5 | Probability calibration and threshold tuning |
| 6 | SHAP/explainability integration |
| 7 | Embedding-based historical incident retrieval |
| 8 | Fusion of structured prediction + retrieval + safety guards |
| 9 | Deployment with human-review and auditing |

---

## Key Design Principles

1. **Do not replace Model 1** - consumes, does not redefine upstream
2. **Unified tree as primary classifier** - replaces old 7-node tree
3. **22 precursors with clusters** - 6 clusters for systemic pattern detection
4. **Barrier failure rate** - deterministic calculation, NOT a model prediction
5. **IOGP LSR independent** - retained for reporting, NOT used as predictive feature
6. **Consistency checking** - cross-validates tree classification against precursor evidence
7. **High-energy conditional density** - density weighted by energy presence and barrier state
8. **Do not use `sif_score` as direct urgency threshold** - urgency learned separately
9. **Structured CSV as primary representation** - JSON for explanation
10. **Tree node-level features preserved** - different SIF mechanisms imply different actions
11. **Urgency independent from SIF potential** - HSIF != automatically IMMEDIATE
12. **Multi-label actions** - incidents can require multiple interventions
13. **Safety guard layer** - deterministic rules prevent unsafe model behavior
14. **Never invent evidence** - only use upstream-provided evidence with source sentence IDs
15. **Human review / abstention** - model can say "HUMAN_REVIEW_REQUIRED"
16. **Temporal leakage prevention** - no future information in training
17. **Safety-optimized metrics** - recall(IMMEDIATE) prioritized over accuracy
