"""Pipeline orchestrator: end-to-end execution for the attention model.

v3.0.0: Unified SIF Classification Tree, barrier assessment, 22 precursors,
clusters, density, high-energy, direct control, and consistency.
"""

from __future__ import annotations
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import numpy as np

from .config import MODEL_VERSION
from .input_loader import InputLoader
from .feature_engineer import AttentionFeatureEngineer
from .rule_engine import RuleEngine
from .barrier_assessment import BarrierAssessment
from .trainer import AttentionModelTrainer
from .inference_engine import InferenceEngine
from .output_generator import OutputGenerator
from .schemas import UpstreamInputs, IncidentPrediction

logger = logging.getLogger(__name__)


class AttentionPipeline:
    """End-to-end pipeline for the SIF Attention Prioritization Model.

    Modes:
      - Cold-start (rule-based): No trained ML models; uses rule engine only.
      - Hybrid ML: Trained models + rule engine + safety overrides.
    """

    def __init__(
        self,
        upstream_output_dir: str,
        downstream_output_dir: str = "outputs",
        models_dir: str = "models",
        load_trained_models: bool = True,
    ):
        self.input_loader = InputLoader(upstream_output_dir)
        self.feature_engineer = AttentionFeatureEngineer()
        self.rule_engine = RuleEngine()
        self.barrier_assessor = BarrierAssessment()
        self.trainer = AttentionModelTrainer(output_dir=models_dir)
        self.inference_engine = InferenceEngine(
            rule_engine=self.rule_engine,
            feature_engineer=self.feature_engineer,
            barrier_assessor=self.barrier_assessor,
        )
        self.output_generator = OutputGenerator(output_dir=downstream_output_dir)

        if load_trained_models:
            loaded = self.trainer.load_models()
            if loaded:
                self.inference_engine.set_ml_models(self.trainer)
                logger.info("Loaded trained ML models -- hybrid mode")
            else:
                logger.info("No trained models found -- rule-based cold-start mode")

    def run(self, upstream_output_dir: Optional[str] = None) -> Dict[str, Any]:
        if upstream_output_dir:
            self.input_loader = InputLoader(upstream_output_dir)

        logger.info("Loading upstream outputs...")
        inputs = self.input_loader.load_all()
        if not inputs:
            logger.warning("No inputs found")
            return {"predictions": [], "dashboard": {}}

        logger.info("Building derived features...")
        feature_df = self.feature_engineer.build_dataframe(inputs)

        if self.inference_engine.prediction_mode == "HYBRID_ML":
            feature_cols = [c for c in feature_df.columns if c != "incident_id"]
            X_ref = feature_df[feature_cols].values.astype(float)
            self.inference_engine.fit_ood_reference(X_ref)

        logger.info("Running inference for %d incidents...", len(inputs))
        predictions = self.inference_engine.predict_batch(inputs, feature_df)

        logger.info("Generating outputs...")
        for pred in predictions:
            self.output_generator.generate_assessment_json(pred)
            self.output_generator.generate_summary_text(pred)

        df_path = self.output_generator.save_prediction_dataframe(predictions)
        dashboard = self.output_generator.generate_dashboard_data(predictions)
        self.output_generator.save_similar_incidents(predictions)

        logger.info("Pipeline complete. %d incidents processed.", len(predictions))

        return {
            "predictions": predictions,
            "feature_df": feature_df,
            "dashboard": dashboard,
            "output_dir": str(self.output_generator.output_dir),
            "prediction_csv": str(df_path),
        }

    def run_single(self, incident_id: str) -> IncidentPrediction:
        inputs = self.input_loader.load_all()
        inp = next((i for i in inputs if i.incident_id == incident_id), None)
        if inp is None:
            raise ValueError(f"Incident {incident_id} not found")

        feature_df = self.feature_engineer.build_dataframe([inp])
        feature_cols = [c for c in feature_df.columns if c != "incident_id"]
        feature_vector = feature_df[feature_cols].iloc[0].values.astype(float)
        features = self.feature_engineer.build_features(inp.feature_row)

        pred = self.inference_engine.predict_single(
            features=features,
            feature_vector=feature_vector,
            incident_id=incident_id,
            analysis=inp.analysis_json,
            summary_text=inp.summary_text,
        )

        self.output_generator.generate_assessment_json(pred)
        self.output_generator.generate_summary_text(pred)

        return pred
