"""Phase M — Pilot Data Collection Structures, Expert Review & Metrics Contracts.

Defines structured validation rules and evaluation metrics calculators for the
planned supervised Guelma Wilaya field pilot without modifying Phases D-L or
fabricating field observations.
"""

from src.pilot.models import (
    ALLOWED_EXPERT_INSTITUTIONS,
    ALLOWED_EXPERT_OUTCOMES,
    ALLOWED_FIELD_SIZE_BANDS,
    ALLOWED_STRATA,
    DISAGREEMENT_CAUSE_CODES,
    FORBIDDEN_FARMER_MEASUREMENT_KEYS,
    ExpertReviewRecord,
    FarmerPilotObservation,
    MeasuredFieldObservation,
    PilotExecutionSession,
    PilotSafetyViolationError,
    PilotSamplingTarget,
    compute_pilot_metrics,
    validate_sampling_plan,
)

__all__ = [
    "ALLOWED_EXPERT_INSTITUTIONS",
    "ALLOWED_EXPERT_OUTCOMES",
    "ALLOWED_FIELD_SIZE_BANDS",
    "ALLOWED_STRATA",
    "DISAGREEMENT_CAUSE_CODES",
    "FORBIDDEN_FARMER_MEASUREMENT_KEYS",
    "ExpertReviewRecord",
    "FarmerPilotObservation",
    "MeasuredFieldObservation",
    "PilotExecutionSession",
    "PilotSafetyViolationError",
    "PilotSamplingTarget",
    "compute_pilot_metrics",
    "validate_sampling_plan",
]
