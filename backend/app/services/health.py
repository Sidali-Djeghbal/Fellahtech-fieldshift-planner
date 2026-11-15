"""Health probes, worker Redis heartbeats, and cluster-aligned dependency checks (`M11`)."""

from __future__ import annotations

import asyncio
import contextlib
from datetime import UTC, datetime, timedelta
from typing import Any

from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.errors import ErrorCode, FieldShiftError
from app.ml_client.base import ProviderKind
from app.ml_client.manager import (
    AsyncRedisStatusStore,
    MLProviderManager,
    read_provider_status,
)
from app.repositories import analysis as analysis_repo
from app.repositories import catalog as catalog_repo
from app.repositories import dataset as dataset_repo
from app.schemas.system import (
    CatalogHealthStatus,
    DatasetHealthStatus,
    DbHealthStatus,
    HealthCheckMode,
    HealthResponse,
    MLServiceHealthStatus,
    WorkerQueueHealthStatus,
)
from app.services.worker_heartbeat import count_active_workers
from app.worker import breaker

_DEFAULT_PROBE_TIMEOUT_SECONDS = 2.5


def _ensure_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


async def _check_redis_ping(redis_client: Any) -> None:
    if redis_client is None:
        raise FieldShiftError(
            ErrorCode.SERVICE_UNAVAILABLE,
            "Redis dependency is not initialized.",
        )
    try:
        pong = await asyncio.wait_for(
            redis_client.ping(),
            timeout=_DEFAULT_PROBE_TIMEOUT_SECONDS,
        )
    except (RedisError, OSError, TimeoutError) as exc:
        raise FieldShiftError(
            ErrorCode.SERVICE_UNAVAILABLE,
            "Redis dependency is unreachable.",
        ) from exc
    if not pong:
        raise FieldShiftError(
            ErrorCode.SERVICE_UNAVAILABLE,
            "Redis dependency ping failed.",
        )


def _live_health_response() -> HealthResponse:
    return HealthResponse(
        status="ok",
        db=DbHealthStatus(connected=False, postgis_version="skipped"),
        dataset=DatasetHealthStatus(active_version=None, loaded_at=None),
        catalog=CatalogHealthStatus(version=None, synced_at=None),
        worker_queue=WorkerQueueHealthStatus(active_workers=0, pending_jobs=0, stale_leases=0),
        ml_service=MLServiceHealthStatus(
            reachable=False,
            circuit_breaker="closed",
            consecutive_failures=0,
            ml_engine_version=None,
        ),
    )


async def _resolve_ml_status(
    *,
    check: HealthCheckMode,
    now: datetime,
    redis_client: Any,
    ml_manager: MLProviderManager | None,
    settings: Settings | None,
) -> tuple[bool, str | None, ProviderKind | None]:
    # TODO(OQ-1): Enforce ML health probe SLA budget once external ML benchmarks are finalized.
    max_age_s = 2 * settings.ML_HEALTH_CHECK_INTERVAL_SECONDS if settings is not None else 60
    status_store = redis_client if isinstance(redis_client, AsyncRedisStatusStore) else None
    redis_snapshot = await read_provider_status(status_store)

    if redis_snapshot is not None and (now - redis_snapshot.checked_at) <= timedelta(
        seconds=max(1, max_age_s)
    ):
        return (
            redis_snapshot.reachable,
            redis_snapshot.ml_engine_version,
            redis_snapshot.provider,
        )

    if check == "dependencies" and ml_manager is not None:
        live_res = await ml_manager.get_health()
        return (
            live_res.reachable,
            live_res.ml_engine_version,
            live_res.provider,
        )

    if ml_manager is not None and ml_manager.last_health is not None:
        cached = ml_manager.last_health
        return cached.reachable, cached.ml_engine_version, cached.provider

    if redis_snapshot is not None:
        return (
            redis_snapshot.reachable,
            redis_snapshot.ml_engine_version,
            redis_snapshot.provider,
        )

    return False, None, None


async def probe_health(
    *,
    check: HealthCheckMode,
    sessionmaker: async_sessionmaker[AsyncSession] | None,
    redis_client: Any,
    ml_manager: MLProviderManager | None,
    settings: Settings | None,
) -> HealthResponse:
    """Execute `/api/v1/health` probe according to requested `check` depth."""
    if check == "live":
        return _live_health_response()

    await _check_redis_ping(redis_client)

    if sessionmaker is None:
        raise FieldShiftError(
            ErrorCode.SERVICE_UNAVAILABLE,
            "PostgreSQL dependency is not initialized.",
        )

    now = datetime.now(UTC)
    try:
        async with sessionmaker() as db:
            postgis_scalar = (
                await asyncio.wait_for(
                    db.execute(text("SELECT PostGIS_Version()")),
                    timeout=_DEFAULT_PROBE_TIMEOUT_SECONDS,
                )
            ).scalar_one_or_none()
            postgis_version = str(postgis_scalar).strip() if postgis_scalar is not None else ""
            if not postgis_version:
                raise FieldShiftError(
                    ErrorCode.SERVICE_UNAVAILABLE,
                    "PostGIS extension is unavailable.",
                )

            dataset_row = await dataset_repo.get_active_dataset(db)
            if dataset_row is None:
                raise FieldShiftError(
                    ErrorCode.DATASET_UNAVAILABLE,
                    "No active dataset version is available in dataset_registry.",
                )

            catalog_meta = await catalog_repo.get_latest_catalog_version_meta(db)
            breaker_snap = await breaker.read_breaker_snapshot(db)
            breaker.sync_breaker_gauge(breaker_snap.state)
            _active_jobs, pending_jobs, stale_leases = await analysis_repo.count_worker_queue_stats(
                db,
                now=now,
            )
    except FieldShiftError:
        raise
    except (SQLAlchemyError, OSError, TimeoutError) as exc:
        raise FieldShiftError(
            ErrorCode.SERVICE_UNAVAILABLE,
            "PostgreSQL/PostGIS dependency is unreachable.",
        ) from exc

    active_workers = await count_active_workers(redis_client)
    ml_reachable, ml_engine_version, _provider = await _resolve_ml_status(
        check=check,
        now=now,
        redis_client=redis_client,
        ml_manager=ml_manager,
        settings=settings,
    )

    overall_status: str = (
        "ok" if (ml_reachable and breaker_snap.state == "closed") else "degraded"
    )
    return HealthResponse(
        status="ok" if overall_status == "ok" else "degraded",
        db=DbHealthStatus(connected=True, postgis_version=postgis_version),
        dataset=DatasetHealthStatus(
            active_version=dataset_row.dataset_version,
            loaded_at=_ensure_utc(dataset_row.loaded_at),
        ),
        catalog=CatalogHealthStatus(
            version=catalog_meta[0] if catalog_meta is not None else None,
            synced_at=_ensure_utc(catalog_meta[1]) if catalog_meta is not None else None,
        ),
        worker_queue=WorkerQueueHealthStatus(
            active_workers=active_workers,
            pending_jobs=pending_jobs,
            stale_leases=stale_leases,
        ),
        ml_service=MLServiceHealthStatus(
            reachable=ml_reachable,
            circuit_breaker=breaker_snap.state,
            consecutive_failures=breaker_snap.consecutive_failures,
            ml_engine_version=ml_engine_version,
        ),
    )


async def sync_api_breaker_gauge_best_effort(
    sessionmaker: async_sessionmaker[AsyncSession] | None,
) -> None:
    """Refresh `ml_breaker_state` gauge inside the API process right before `/metrics` output."""
    if sessionmaker is None:
        return
    with contextlib.suppress(SQLAlchemyError, OSError, TimeoutError):
        async with sessionmaker() as db:
            snap = await breaker.read_breaker_snapshot(db)
        breaker.sync_breaker_gauge(snap.state)
