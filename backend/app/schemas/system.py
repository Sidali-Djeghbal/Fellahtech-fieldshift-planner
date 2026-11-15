"""Pydantic schemas for `/api/v1/health` matching `openapi.yaml` `HealthResponse`."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

HealthCheckMode = Literal["live", "ready", "dependencies"]
HealthOverallStatus = Literal["ok", "degraded"]
BreakerStateName = Literal["closed", "open", "half_open"]


class _StrictSystemModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DbHealthStatus(_StrictSystemModel):
    """PostgreSQL/PostGIS probe status nested inside `HealthResponse`."""

    connected: bool
    postgis_version: str


class DatasetHealthStatus(_StrictSystemModel):
    """Active agronomic dataset registry status nested inside `HealthResponse`."""

    active_version: str | None
    loaded_at: datetime | None


class CatalogHealthStatus(_StrictSystemModel):
    """Synced crop catalog status nested inside `HealthResponse`."""

    version: str | None
    synced_at: datetime | None


class WorkerQueueHealthStatus(_StrictSystemModel):
    """Live worker daemon heartbeats & job queue backlog counts."""

    active_workers: int
    pending_jobs: int
    stale_leases: int


class MLServiceHealthStatus(_StrictSystemModel):
    """External ML reachability, cluster breaker state, and active engine version."""

    reachable: bool
    circuit_breaker: BreakerStateName
    consecutive_failures: int
    ml_engine_version: str | None


class HealthResponse(_StrictSystemModel):
    """Canonical `GET /api/v1/health` payload (`openapi.yaml#HealthResponse`)."""

    status: HealthOverallStatus
    db: DbHealthStatus
    dataset: DatasetHealthStatus
    catalog: CatalogHealthStatus
    worker_queue: WorkerQueueHealthStatus
    ml_service: MLServiceHealthStatus
