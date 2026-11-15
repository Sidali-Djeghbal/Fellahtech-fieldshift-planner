"""Shared Prometheus instrumentation counters, histograms, and gauges (`ENDPOINTS B.9`)."""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

ANALYSIS_REQUESTS_TOTAL = Counter(
    "analysis_requests_total",
    "Total terminal analysis request outcomes recorded by the worker",
    labelnames=("status", "error_code"),
)

ML_REQUEST_DURATION_SECONDS = Histogram(
    "ml_request_duration_seconds",
    "End-to-end External ML execution duration per job in seconds",
    labelnames=("provider", "outcome"),
)

WORKER_ACTIVE_LEASES = Gauge(
    "worker_active_leases",
    "Current active worker job leases held by this worker process",
)

WORKER_BULKHEAD_INFLIGHT = Gauge(
    "worker_bulkhead_inflight",
    "Current PostgreSQL advisory-lock ML bulkhead slots held by this worker process",
)

ML_BREAKER_STATE_GAUGE = Gauge(
    "ml_breaker_state",
    "Circuit breaker state (0=closed, 1=open, 2=half_open)",
)

ML_UNKNOWN_FIELDS_OBSERVED_TOTAL = Counter(
    "ml_unknown_fields_observed_total",
    "Total unknown tolerant-reader fields observed in ML 5.x responses",
)
