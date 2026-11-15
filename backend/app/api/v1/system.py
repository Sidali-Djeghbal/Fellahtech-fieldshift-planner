"""Operational endpoints: `/api/v1/health` and `/api/v1/metrics` (`M11`)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.schemas.system import HealthCheckMode, HealthResponse
from app.services.health import probe_health, sync_api_breaker_gauge_best_effort

router = APIRouter(tags=["System"])


@router.get(
    "/health",
    operation_id="getHealth",
    response_model=HealthResponse,
    summary="Liveness & readiness probe covering PG/PostGIS, Redis, dataset, catalog, worker & ML",
)
async def get_health(
    request: Request,
    check: Annotated[HealthCheckMode, Query()] = "dependencies",
) -> HealthResponse:
    """Probe API and cluster dependencies cleanly without leaking secrets."""
    return await probe_health(
        check=check,
        sessionmaker=getattr(request.app.state, "db_sessionmaker", None),
        redis_client=getattr(request.app.state, "redis", None),
        ml_manager=getattr(request.app.state, "ml_provider_manager", None),
        settings=getattr(request.app.state, "settings", None),
    )


@router.get(
    "/metrics",
    operation_id="getMetrics",
    response_class=Response,
    openapi_extra={"x-internal-only": True},
    summary="Prometheus text metrics endpoint (restricted to internal network / proxy ACL)",
)
async def get_metrics(request: Request) -> Response:
    """Expose Prometheus text exposition format for internal scrapers (`# TODO(OQ-1)`)."""
    await sync_api_breaker_gauge_best_effort(
        getattr(request.app.state, "db_sessionmaker", None)
    )
    payload = generate_latest()
    return Response(content=payload, media_type=CONTENT_TYPE_LATEST)
