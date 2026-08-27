"""Model trainer for the downstream attention prediction system.

Trains three separate model families:
  1. Urgency model -- ordinal classification into IMMEDIATE/SHORT_TERM/PLANNED/MONITOR
  2. Action model -- multi-label classification for recommended actions
  3. Systemic attention model -- classification into NONE/LOW/MODERATE/HIGH

Each model family evaluates multiple algorithms and selects the best based on
safety-relevant metrics (high recall for IMMEDIATE, calibration, false-negative cost).
"""

from __future__ import annotations
import logging
import json
import pickle
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import (
    f1_score,
    balanced_accuracy_score,
    precision_recall_fscore_support,
    classification_report,
    hamming_loss,
    make_scorer,
)
from sklearn.preprocessing import LabelEncoder
from sklearn.utils.class_weight import compute_class_weight

from .config import (
    AttentionLevel,
    SystemicLevel,
    URGENCY_ORDER,
    URGENCY_DECODE,
    SYSTEMIC_ORDER,
    SYSTEMIC_DECODE,
    ACTION_LABELS,
    ACTION_COLUMNS,
    COST_MATRIX,
    CalibrationConfig,
    MODEL_VERSION,
)

logger = logging.getLogger(__name__)

try:
    import xgboost as xgb
    HAS_XGB = True
except ImportError:
    HAS_XGB = False

try:
    import lightgbm as lgb
    HAS_LGBM = True
except ImportError:
    HAS_LGBM = False

try:
    import catboost as cb
    HAS_CB = True
except ImportError:
    HAS_CB = False


# ---------------------------------------------------------------------------
# Cost-sensitive sample weights
# ---------------------------------------------------------------------------

def compute_urgency_sample_weights(
    y: np.ndarray, cost_matrix: Any = COST_MATRIX
) -> np.ndarray:
    """Compute per-sample weights based on the asymmetric cost matrix.

    Samples belonging to rarer/higher-cost classes get higher weight.
    """
    classes = np.unique(y)
    weights_map = {}
    for cls in classes:
        # Weight based on the average FN cost for this class
        cls_name = URGENCY_DECODE.get(cls, str(cls))
        total_cost = 0.0
        count = 0
        for other_cls in classes:
            if other_cls != cls:
                other_name = URGENCY_DECODE.get(other_cls, str(other_cls))
                total_cost += cost_matrix.weight_for(cls_name, other_name)
                count += 1
        weights_map[cls] = total_cost / max(count, 1) + 1.0

    sample_weights = np.array([weights_map[yi] for yi in y])
    return sample_weights


# ---------------------------------------------------------------------------
# Model Trainers
# ---------------------------------------------------------------------------

class UrgencyTrainer:
    """Trains and compares urgency classification models."""

    def __init__(self, random_state: int = 42):
        self.random_state = random_state
        self.best_model = None
        self.best_model_name = ""
        self.label_encoder = LabelEncoder()
        self.calibrator = None
        self.cv_results: Dict[str, Any] = {}

    def _build_candidates(self) -> Dict[str, Any]:
        candidates = {
            "logistic_regression": LogisticRegression(
                max_iter=1000,
                class_weight="balanced",
                multi_class="multinomial",
                random_state=self.random_state,
            ),
            "random_forest": RandomForestClassifier(
                n_estimators=200,
                max_depth=10,
                class_weight="balanced",
                random_state=self.random_state,
                n_jobs=-1,
            ),
            "gradient_boosting": GradientBoostingClassifier(
                n_estimators=200,
                max_depth=5,
                learning_rate=0.1,
                random_state=self.random_state,
            ),
        }
        if HAS_XGB:
            candidates["xgboost"] = xgb.XGBClassifier(
                n_estimators=200,
                max_depth=5,
                learning_rate=0.1,
                objective="multi:softprob",
                use_label_encoder=False,
                eval_metric="mlogloss",
                random_state=self.random_state,
                n_jobs=-1,
            )
        if HAS_LGBM:
            candidates["lightgbm"] = lgb.LGBMClassifier(
                n_estimators=200,
                max_depth=5,
                learning_rate=0.1,
                objective="multiclass",
                class_weight="balanced",
                random_state=self.random_state,
                n_jobs=-1,
                verbose=-1,
            )
        if HAS_CB:
            candidates["catboost"] = cb.CatBoostClassifier(
                iterations=200,
                depth=5,
                learning_rate=0.1,
                loss_function="MultiClass",
                verbose=0,
                random_seed=self.random_state,
            )
        return candidates

    def train(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Train and evaluate all urgency model candidates.

        Returns a comparison report and sets self.best_model.
        """
        y_encoded = self.label_encoder.fit_transform(y)
        classes = self.label_encoder.classes_
        class_names = [URGENCY_DECODE.get(c, str(c)) for c in classes]

        # Compute sample weights
        sample_weights = compute_urgency_sample_weights(y_encoded)

        candidates = self._build_candidates()
        results = {}

        skf = StratifiedKFold(n_splits=min(5, len(y)), shuffle=True, random_state=self.random_state)

        for name, model in candidates.items():
            try:
                y_pred = cross_val_predict(model, X, y_encoded, cv=skf, method="predict")
                macro_f1 = f1_score(y_encoded, y_pred, average="macro", zero_division=0)
                bal_acc = balanced_accuracy_score(y_encoded, y_pred)

                # Per-class recall
                _, _, recall, _ = precision_recall_fscore_support(
                    y_encoded, y_pred, average=None, labels=range(len(classes)), zero_division=0
                )
                per_class_recall = {
                    class_names[i]: float(recall[i]) for i in range(len(class_names))
                }

                # IMMEDIATE class recall
                immediate_idx = None
                for i, c in enumerate(classes):
                    if URGENCY_DECODE.get(c, "") == AttentionLevel.IMMEDIATE.value:
                        immediate_idx = i
                        break
                immediate_recall = float(recall[immediate_idx]) if immediate_idx is not None else 0.0

                # Cost-weighted score
                cost_weighted_score = 0.0
                for actual_cls_idx, pred_cls_idx in zip(y_encoded, y_pred):
                    actual_name = URGENCY_DECODE.get(actual_cls_idx, str(actual_cls_idx))
                    pred_name = URGENCY_DECODE.get(pred_cls_idx, str(pred_cls_idx))
                    cost_weighted_score += COST_MATRIX.weight_for(actual_name, pred_name)
                avg_cost = cost_weighted_score / len(y_encoded)

                results[name] = {
                    "macro_f1": macro_f1,
                    "balanced_accuracy": bal_acc,
                    "immediate_recall": immediate_recall,
                    "per_class_recall": per_class_recall,
                    "avg_misclassification_cost": avg_cost,
                    "classification_report": classification_report(
                        y_encoded, y_pred, target_names=class_names, zero_division=0
                    ),
                }
            except Exception as e:
                logger.warning("Model %s failed: %s", name, e)
                results[name] = {"error": str(e)}

        self.cv_results = results

        # Select best model: prioritize immediate recall, then macro F1, then cost
        valid_results = {k: v for k, v in results.items() if "error" not in v}
        if not valid_results:
            raise RuntimeError("All urgency model candidates failed")

        best_name = max(
            valid_results.keys(),
            key=lambda k: (
                valid_results[k]["immediate_recall"] * 10
                + valid_results[k]["macro_f1"]
                - valid_results[k]["avg_misclassification_cost"] * 0.5
            ),
        )

        # Train the best model on full data
        self.best_model = candidates[best_name]
        self.best_model.fit(X, y_encoded, sample_weight=sample_weights)
        self.best_model_name = best_name

        logger.info(
            "Best urgency model: %s (macro_f1=%.3f, immediate_recall=%.3f)",
            best_name,
            valid_results[best_name]["macro_f1"],
            valid_results[best_name]["immediate_recall"],
        )

        return {
            "best_model": best_name,
            "all_results": results,
        }

    def predict(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Predict urgency classes and probabilities.

        Returns (predicted_labels, probability_matrix).
        """
        if self.best_model is None:
            raise RuntimeError("Model not trained. Call train() first.")

        y_pred_encoded = self.best_model.predict(X)
        y_pred = self.label_encoder.inverse_transform(y_pred_encoded)

        if hasattr(self.best_model, "predict_proba"):
            proba = self.best_model.predict_proba(X)
        else:
            proba = np.zeros((len(X), len(self.label_encoder.classes_)))

        return y_pred, proba


class ActionTrainer:
    """Trains multi-label action recommendation models."""

    def __init__(self, random_state: int = 42):
        self.random_state = random_state
        self.models: Dict[str, Any] = {}
        self.thresholds: Dict[str, float] = {}
        self.action_labels = ACTION_LABELS
        self.cv_results: Dict[str, Any] = {}

    def train(
        self,
        X: np.ndarray,
        Y: np.ndarray,
        feature_names: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Train one-vs-rest models for each action label.

        Y shape: (n_samples, n_actions) binary matrix.
        """
        n_actions = Y.shape[1]
        results = {}

        # Filter to actions that appear in the training data
        active_actions = []
        active_indices = []
        for i in range(n_actions):
            if Y[:, i].sum() > 0:
                active_actions.append(self.action_labels[i])
                active_indices.append(i)

        if not active_actions:
            logger.warning("No active action labels in training data")
            return {"error": "No active action labels"}

        for idx, action_idx in enumerate(active_indices):
            action_name = self.action_labels[action_idx]
            y_binary = Y[:, action_idx]

            # Skip if too few positive samples for CV
            n_pos = y_binary.sum()
            if n_pos < 2:
                self.models[action_name] = GradientBoostingClassifier(
                    n_estimators=100, max_depth=3, random_state=self.random_state
                )
                self.models[action_name].fit(X, y_binary)
                self.thresholds[action_name] = 0.5
                continue

            # Train with threshold optimization
            model = GradientBoostingClassifier(
                n_estimators=150, max_depth=4, learning_rate=0.1,
                random_state=self.random_state,
            )

            n_splits = min(5, int(n_pos))
            skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=self.random_state)

            # Get cross-validated probabilities for threshold tuning
            y_proba = cross_val_predict(model, X, y_binary, cv=skf, method="predict_proba")

            # Optimize threshold for F1 (or recall-prioritized for safety)
            best_threshold = 0.5
            best_f1 = 0.0
            for t in np.arange(0.1, 0.9, 0.05):
                preds = (y_proba[:, 1] >= t).astype(int)
                f1 = f1_score(y_binary, preds, zero_division=0)
                if f1 > best_f1:
                    best_f1 = f1
                    best_threshold = t

            self.thresholds[action_name] = best_threshold

            # Train final model on full data
            model.fit(X, y_binary)
            self.models[action_name] = model

            results[action_name] = {
                "threshold": best_threshold,
                "f1_at_threshold": best_f1,
                "positive_count": int(n_pos),
            }

        self.cv_results = results
        logger.info("Trained action models for %d actions", len(self.models))
        return results

    def predict(
        self, X: np.ndarray
    ) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
        """Predict action recommendations.

        Returns (binary_action_matrix, per_action_probabilities).
        """
        n_samples = X.shape[0]
        binary_matrix = np.zeros((n_samples, len(self.action_labels)), dtype=int)
        proba_dict: Dict[str, np.ndarray] = {}

        for action_name, model in self.models.items():
            action_idx = self.action_labels.index(action_name)
            if hasattr(model, "predict_proba"):
                proba = model.predict_proba(X)[:, 1]
            else:
                proba = model.predict(X).astype(float)

            proba_dict[action_name] = proba
            threshold = self.thresholds.get(action_name, 0.5)
            binary_matrix[:, action_idx] = (proba >= threshold).astype(int)

        return binary_matrix, proba_dict


class SystemicAttentionTrainer:
    """Trains the systemic attention classification model."""

    def __init__(self, random_state: int = 42):
        self.random_state = random_state
        self.best_model = None
        self.best_model_name = ""
        self.label_encoder = LabelEncoder()
        self.cv_results: Dict[str, Any] = {}

    def train(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Train and compare systemic attention models."""
        y_encoded = self.label_encoder.fit_transform(y)
        classes = self.label_encoder.classes_
        class_names = [SYSTEMIC_DECODE.get(c, str(c)) for c in classes]

        candidates = {
            "logistic_regression": LogisticRegression(
                max_iter=1000, class_weight="balanced",
                multi_class="multinomial", random_state=self.random_state,
            ),
            "random_forest": RandomForestClassifier(
                n_estimators=200, max_depth=8, class_weight="balanced",
                random_state=self.random_state, n_jobs=-1,
            ),
            "gradient_boosting": GradientBoostingClassifier(
                n_estimators=200, max_depth=4, learning_rate=0.1,
                random_state=self.random_state,
            ),
        }

        if HAS_XGB:
            candidates["xgboost"] = xgb.XGBClassifier(
                n_estimators=200, max_depth=4, learning_rate=0.1,
                objective="multi:softprob", use_label_encoder=False,
                eval_metric="mlogloss", random_state=self.random_state, n_jobs=-1,
            )

        results = {}
        skf = StratifiedKFold(n_splits=min(5, len(y)), shuffle=True, random_state=self.random_state)

        for name, model in candidates.items():
            try:
                y_pred = cross_val_predict(model, X, y_encoded, cv=skf, method="predict")
                macro_f1 = f1_score(y_encoded, y_pred, average="macro", zero_division=0)
                bal_acc = balanced_accuracy_score(y_encoded, y_pred)
                results[name] = {
                    "macro_f1": macro_f1,
                    "balanced_accuracy": bal_acc,
                    "classification_report": classification_report(
                        y_encoded, y_pred, target_names=class_names, zero_division=0
                    ),
                }
            except Exception as e:
                logger.warning("Systemic model %s failed: %s", name, e)
                results[name] = {"error": str(e)}

        self.cv_results = results
        valid_results = {k: v for k, v in results.items() if "error" not in v}
        if not valid_results:
            raise RuntimeError("All systemic model candidates failed")

        best_name = max(valid_results.keys(), key=lambda k: valid_results[k]["macro_f1"])
        self.best_model = candidates[best_name]
        self.best_model.fit(X, y_encoded)
        self.best_model_name = best_name

        logger.info("Best systemic model: %s (macro_f1=%.3f)", best_name, valid_results[best_name]["macro_f1"])
        return {"best_model": best_name, "all_results": results}

    def predict(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        if self.best_model is None:
            raise RuntimeError("Model not trained")
        y_pred_encoded = self.best_model.predict(X)
        y_pred = self.label_encoder.inverse_transform(y_pred_encoded)
        proba = self.best_model.predict_proba(X) if hasattr(self.best_model, "predict_proba") else np.zeros((len(X), len(self.label_encoder.classes_)))
        return y_pred, proba


# ---------------------------------------------------------------------------
# Combined Trainer
# ---------------------------------------------------------------------------

class AttentionModelTrainer:
    """Orchestrates training of all three model families."""

    def __init__(self, output_dir: str = "models", random_state: int = 42):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.random_state = random_state

        self.urgency_trainer = UrgencyTrainer(random_state)
        self.action_trainer = ActionTrainer(random_state)
        self.systemic_trainer = SystemicAttentionTrainer(random_state)

    def train_all(
        self,
        X: np.ndarray,
        y_urgency: np.ndarray,
        y_actions: np.ndarray,
        y_systemic: np.ndarray,
        feature_names: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Train all three model families."""
        results = {}

        logger.info("Training urgency model...")
        results["urgency"] = self.urgency_trainer.train(X, y_urgency, feature_names)

        logger.info("Training action model...")
        results["actions"] = self.action_trainer.train(X, y_actions, feature_names)

        logger.info("Training systemic attention model...")
        results["systemic"] = self.systemic_trainer.train(X, y_systemic, feature_names)

        return results

    def save_models(self, version: str = MODEL_VERSION) -> None:
        """Persist all trained models to disk."""
        model_dir = self.output_dir / version
        model_dir.mkdir(parents=True, exist_ok=True)

        with open(model_dir / "urgency_model.pkl", "wb") as f:
            pickle.dump({
                "model": self.urgency_trainer.best_model,
                "model_name": self.urgency_trainer.best_model_name,
                "label_encoder": self.urgency_trainer.label_encoder,
                "cv_results": self.urgency_trainer.cv_results,
            }, f)

        with open(model_dir / "action_models.pkl", "wb") as f:
            pickle.dump({
                "models": self.action_trainer.models,
                "thresholds": self.action_trainer.thresholds,
                "cv_results": self.action_trainer.cv_results,
            }, f)

        with open(model_dir / "systemic_model.pkl", "wb") as f:
            pickle.dump({
                "model": self.systemic_trainer.best_model,
                "model_name": self.systemic_trainer.best_model_name,
                "label_encoder": self.systemic_trainer.label_encoder,
                "cv_results": self.systemic_trainer.cv_results,
            }, f)

        # Save metadata
        meta = {
            "version": version,
            "urgency_model": self.urgency_trainer.best_model_name,
            "action_models": list(self.action_trainer.models.keys()),
            "systemic_model": self.systemic_trainer.best_model_name,
            "n_features": None,
        }
        with open(model_dir / "metadata.json", "w") as f:
            json.dump(meta, f, indent=2)

        logger.info("Models saved to %s", model_dir)

    def load_models(self, version: str = MODEL_VERSION) -> bool:
        """Load trained models from disk. Returns True if successful."""
        model_dir = self.output_dir / version
        urgency_path = model_dir / "urgency_model.pkl"
        if not urgency_path.exists():
            return False

        with open(urgency_path, "rb") as f:
            data = pickle.load(f)
            self.urgency_trainer.best_model = data["model"]
            self.urgency_trainer.best_model_name = data["model_name"]
            self.urgency_trainer.label_encoder = data["label_encoder"]
            self.urgency_trainer.cv_results = data.get("cv_results", {})

        action_path = model_dir / "action_models.pkl"
        if action_path.exists():
            with open(action_path, "rb") as f:
                data = pickle.load(f)
                self.action_trainer.models = data["models"]
                self.action_trainer.thresholds = data["thresholds"]
                self.action_trainer.cv_results = data.get("cv_results", {})

        systemic_path = model_dir / "systemic_model.pkl"
        if systemic_path.exists():
            with open(systemic_path, "rb") as f:
                data = pickle.load(f)
                self.systemic_trainer.best_model = data["model"]
                self.systemic_trainer.best_model_name = data["model_name"]
                self.systemic_trainer.label_encoder = data["label_encoder"]
                self.systemic_trainer.cv_results = data.get("cv_results", {})

        logger.info("Models loaded from %s", model_dir)
        return True
