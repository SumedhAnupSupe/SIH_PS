"""Deterministic barrier failure rate assessment.

Computes barrier failure rate from upstream Model 1 outputs.
This is a calculated metric, NOT a prediction by Model 2.

Formula:
  BFR = (DC_fail * w1) + (cluster_barrier_density * w2) +
        (CCV_fail * w3) + (EI_fail * w4) + (stop_work_absent * w5)

Where DC=direct control, CCV=critical control verification, EI=energy isolation.
"""

from __future__ import annotations
from typing import Any, Dict

from .config import BARRIER_FAILURE_RATE_CONFIG, BarrierFailureRateConfig


class BarrierAssessment:
    """Computes barrier failure rate deterministically."""

    def __init__(self, config: BarrierFailureRateConfig = None):
        self.config = config or BARRIER_FAILURE_RATE_CONFIG

    def compute(self, feature_row: Dict[str, Any]) -> Dict[str, float]:
        """Compute barrier failure rate from feature row.

        Returns dict with failure_rate and component contributions.
        """
        # Direct control failure contribution
        dc_failed = float(feature_row.get("direct_control_failed", 0))
        dc_missing = float(feature_row.get("direct_control_missing", 0))
        dc_signal = max(dc_failed, dc_missing)
        dc_contrib = dc_signal * self.config.direct_control_failure_weight

        # Barrier cluster density contribution
        barrier_density = float(feature_row.get("cluster_barrier_density", 0.0))
        barrier_contrib = barrier_density * self.config.barrier_cluster_density_weight

        # Critical control verification failure contribution
        ccv_precursor = float(feature_row.get("critical_control_verification_failure", 0))
        ccv_signal = 1.0 if ccv_precursor == 3 else (0.5 if ccv_precursor == 2 else 0.0)
        ccv_contrib = ccv_signal * self.config.critical_control_verification_weight

        # Energy isolation failure contribution
        ei_precursor = float(feature_row.get("energy_isolation_failure", 0))
        ei_signal = 1.0 if ei_precursor == 3 else (0.5 if ei_precursor == 2 else 0.0)
        ei_contrib = ei_signal * self.config.energy_isolation_failure_weight

        # Stop work absence contribution
        sw_precursor = float(feature_row.get("stop_work_execution", 0))
        sw_signal = 1.0 if sw_precursor == 1 else (0.5 if sw_precursor == 2 else 0.0)
        sw_contrib = sw_signal * self.config.stop_work_absence_weight

        # Weighted sum
        failure_rate = min(1.0, max(0.0,
            dc_contrib + barrier_contrib + ccv_contrib + ei_contrib + sw_contrib
        ))

        return {
            "failure_rate": round(failure_rate, 4),
            "direct_control_failure_contrib": round(dc_contrib, 4),
            "barrier_cluster_contrib": round(barrier_contrib, 4),
            "critical_control_verification_contrib": round(ccv_contrib, 4),
            "energy_isolation_contrib": round(ei_contrib, 4),
            "stop_work_contrib": round(sw_contrib, 4),
            "calculation_method": "deterministic_weighted_sum",
        }

    def validate(self, result: Dict[str, float]) -> list:
        errors = []
        fr = result.get("failure_rate", -1.0)
        if not (0.0 <= fr <= 1.0):
            errors.append(f"Barrier failure rate out of range: {fr}")

        components = [
            "direct_control_failure_contrib",
            "barrier_cluster_contrib",
            "critical_control_verification_contrib",
            "energy_isolation_contrib",
            "stop_work_contrib",
        ]
        for comp in components:
            val = result.get(comp, -1.0)
            if not (0.0 <= val <= 1.0):
                errors.append(f"{comp} out of range: {val}")

        total = sum(result.get(c, 0) for c in components)
        if abs(total - fr) > 0.02:
            errors.append(f"Component sum ({total:.4f}) != failure_rate ({fr:.4f})")

        return errors
