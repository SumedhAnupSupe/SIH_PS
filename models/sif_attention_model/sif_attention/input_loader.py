"""Input loader and validator for upstream pipeline outputs.

v3.0.0: Unified SIF Classification Tree, 22 precursors, barrier assessment.
"""

from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from .schemas import ReportAnalysis, UpstreamInputs
from .config import (
    PRECURSOR_STATUS_COLS,
    PRECURSOR_CONFIDENCE_COLS,
    PRECURSOR_EVIDENCE_COLS,
    PRECURSOR_EVIDENCE_STRENGTH_COLS,
    WORK_CHANGE_COLS,
    WORKER_COLS,
    CONTROL_COLS,
    MISSING_INFO_COLS,
    TEXT_STAT_COLS,
    HIGH_ENERGY_COLS,
    DIRECT_CONTROL_COLS,
    DENSITY_COLS,
    CLUSTER_COLS,
    CONSISTENCY_COLS,
    LSR_RULES,
    TREE_FEATURE_COLS,
    SIF_SCORE_FEATURE_COLS,
)

logger = logging.getLogger(__name__)

LSR_STATUS_COLS = [f"lsr_{r}_status" for r in LSR_RULES]
LSR_CONFIDENCE_COLS = [f"lsr_{r}_confidence" for r in LSR_RULES]

REQUIRED_FEATURE_COLUMNS = (
    ["incident_id", "task_type", "hazard_count"]
    + PRECURSOR_STATUS_COLS
    + PRECURSOR_CONFIDENCE_COLS
    + PRECURSOR_EVIDENCE_COLS
    + WORK_CHANGE_COLS
    + WORKER_COLS
    + CONTROL_COLS
    + MISSING_INFO_COLS
    + TEXT_STAT_COLS
)

OPTIONAL_FEATURE_COLUMNS = (
    PRECURSOR_EVIDENCE_STRENGTH_COLS
    + HIGH_ENERGY_COLS
    + DIRECT_CONTROL_COLS
    + DENSITY_COLS
    + CLUSTER_COLS
    + CONSISTENCY_COLS
    + ["life_saving_rule_broken_count", "life_saving_rule_broken"]
    + LSR_STATUS_COLS
    + LSR_CONFIDENCE_COLS
    + TREE_FEATURE_COLS
    + SIF_SCORE_FEATURE_COLS
)


class InputLoader:
    """Loads and validates upstream pipeline outputs."""

    def __init__(self, upstream_output_dir: str):
        self.upstream_dir = Path(upstream_output_dir)
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def load_encoded_csv(self) -> pd.DataFrame:
        csv_path = self.upstream_dir / "sif_features_encoded.csv"
        if not csv_path.exists():
            raise FileNotFoundError(f"Encoded CSV not found: {csv_path}")
        df = pd.read_csv(csv_path)
        logger.info("Loaded encoded CSV: %d rows, %d columns", len(df), len(df.columns))
        return df

    def load_analysis_json(self, incident_id: str) -> Optional[ReportAnalysis]:
        json_path = self.upstream_dir / "analyses" / f"{incident_id}.json"
        if not json_path.exists():
            self.warnings.append(f"Analysis JSON not found for {incident_id}")
            return None
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        try:
            return ReportAnalysis(**data)
        except Exception as e:
            self.errors.append(f"Failed to parse analysis JSON for {incident_id}: {e}")
            return None

    def load_summary_text(self, incident_id: str) -> str:
        summary_path = self.upstream_dir / "summaries" / f"{incident_id}.txt"
        if not summary_path.exists():
            return ""
        return summary_path.read_text(encoding="utf-8")

    def validate_features(self, df: pd.DataFrame) -> List[str]:
        errors = []
        for col in REQUIRED_FEATURE_COLUMNS:
            if col not in df.columns:
                errors.append(f"Missing required column: {col}")

        if "incident_id" not in df.columns:
            errors.append("Missing incident_id column")
            return errors

        if df["incident_id"].duplicated().any():
            dupes = df[df["incident_id"].duplicated()]["incident_id"].tolist()
            errors.append(f"Duplicate incident IDs: {dupes}")

        for col in PRECURSOR_CONFIDENCE_COLS:
            if col in df.columns:
                vals = df[col]
                bad = vals[(vals < 0.0) | (vals > 1.0)]
                if len(bad) > 0:
                    errors.append(f"Confidence values outside [0,1] in {col}")

        for col in PRECURSOR_STATUS_COLS:
            if col in df.columns:
                bad = df[~df[col].isin([-1, 0, 1, 2, 3])]
                if len(bad) > 0:
                    errors.append(f"Invalid precursor status in {col}: {bad[col].unique().tolist()}")

        if "sif_score" in df.columns:
            bad = df[(df["sif_score"] < 0.0) | (df["sif_score"] > 1.0)]
            if len(bad) > 0:
                errors.append("sif_score values outside [0,1]")

        if "unified_tree_confidence" in df.columns:
            bad = df[(df["unified_tree_confidence"] < 0.0) | (df["unified_tree_confidence"] > 1.0)]
            if len(bad) > 0:
                errors.append("unified_tree_confidence values outside [0,1]")

        return errors

    def load_all(self) -> List[UpstreamInputs]:
        df = self.load_encoded_csv()
        validation_errors = self.validate_features(df)
        if validation_errors:
            for err in validation_errors:
                logger.error("Schema validation error: %s", err)
            raise ValueError(f"Upstream CSV validation failed with {len(validation_errors)} errors")

        inputs: List[UpstreamInputs] = []
        for _, row in df.iterrows():
            incident_id = str(row["incident_id"])
            feature_row = row.to_dict()
            analysis = self.load_analysis_json(incident_id)
            summary = self.load_summary_text(incident_id)

            inputs.append(UpstreamInputs(
                incident_id=incident_id,
                feature_row=feature_row,
                analysis_json=analysis,
                summary_text=summary,
            ))

        logger.info("Loaded %d incident inputs", len(inputs))
        return inputs

    def load_for_single_incident(self, incident_id: str) -> UpstreamInputs:
        df = self.load_encoded_csv()
        row = df[df["incident_id"] == incident_id]
        if row.empty:
            raise ValueError(f"Incident {incident_id} not found in encoded CSV")
        feature_row = row.iloc[0].to_dict()
        analysis = self.load_analysis_json(incident_id)
        summary = self.load_summary_text(incident_id)
        return UpstreamInputs(
            incident_id=incident_id,
            feature_row=feature_row,
            analysis_json=analysis,
            summary_text=summary,
        )
