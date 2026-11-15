"""Background analysis worker package (`SKIP LOCKED`, bulkhead, cancellation, ML errors)."""

from __future__ import annotations

from app.worker.breaker import (
    BreakerDispatchDecision,
    BreakerSnapshot,
    BreakerStateLiteral,
    BreakerTransitionResult,
    acquire_breaker_dispatch,
    read_breaker_snapshot,
    record_breaker_failure,
    record_breaker_non_failure,
    release_aborted_half_open_probe,
)
from app.worker.jobs import (
    DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
    MLErrorDecision,
    PayloadTrimError,
    PayloadTrimResult,
    ResultVerificationOutcome,
    ResultVerifier,
    RetryBudgetState,
    classify_ml_error_policy,
    trim_analysis_payload_for_size,
    verify_analysis_result_basic,
)
from app.worker.runner import JobExecutionSummary, WorkerRunner, acquire_ml_bulkhead_slot

__all__ = [
    "DEFAULT_HEARTBEAT_INTERVAL_SECONDS",
    "BreakerDispatchDecision",
    "BreakerSnapshot",
    "BreakerStateLiteral",
    "BreakerTransitionResult",
    "JobExecutionSummary",
    "MLErrorDecision",
    "PayloadTrimError",
    "PayloadTrimResult",
    "ResultVerificationOutcome",
    "ResultVerifier",
    "RetryBudgetState",
    "WorkerRunner",
    "acquire_breaker_dispatch",
    "acquire_ml_bulkhead_slot",
    "classify_ml_error_policy",
    "read_breaker_snapshot",
    "record_breaker_failure",
    "record_breaker_non_failure",
    "release_aborted_half_open_probe",
    "trim_analysis_payload_for_size",
    "verify_analysis_result_basic",
]
