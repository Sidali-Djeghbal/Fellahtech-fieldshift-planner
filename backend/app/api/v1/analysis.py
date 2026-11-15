"""Analysis REST endpoints (`/api/v1/analysis*` and `/api/v1/farms/{farm_id}/analyses`)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Path, Query, Request, Response, status
from fastapi.responses import JSONResponse

from app.api.deps import (
    ActorNoRateLimitDep,
    ActorPrincipalDep,
    DbSessionDep,
    DbSessionMakerDep,
    MLProviderManagerDep,
    RedisDep,
    SettingsDep,
)
from app.core.errors import ErrorCode, FieldShiftError, resolve_request_id
from app.core.pagination import PaginationParams, get_pagination_params
from app.core.rate_limit import get_client_ip_from_request
from app.schemas.analysis import (
    AnalysisCancelResponse,
    AnalysisEnvelope,
    AnalysisPollEnvelope,
    AnalysisQueuedResponse,
    AnalysisRequestStatus,
    AnalysisSubmitRequest,
    FarmAnalysesPage,
    SelectionResponse,
    SelectionUpdateRequest,
)
from app.services import analysis as analysis_service

router = APIRouter(tags=["Analysis"])

PaginationDep = Annotated[PaginationParams, Depends(get_pagination_params)]
FarmIdPathDep = Annotated[str, Path(pattern=r"^farm_[0-9]+$")]
AnalysisIdPathDep = Annotated[str, Path(pattern=r"^analysis_[0-9a-f]{12}$")]


@router.post(
    "/analysis",
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="submitAnalysis",
    responses={
        status.HTTP_200_OK: {"model": AnalysisEnvelope},
        status.HTTP_202_ACCEPTED: {"model": AnalysisQueuedResponse},
    },
)
async def submit_analysis(
    request: Request,
    payload: AnalysisSubmitRequest,
    principal: ActorNoRateLimitDep,
    db: DbSessionDep,
    sync_sessionmaker: DbSessionMakerDep,
    redis_client: RedisDep,
    settings: SettingsDep,
    ml_manager: MLProviderManagerDep,
    wait: Annotated[bool, Query()] = False,
    idempotency_key: Annotated[
        str | None,
        Header(alias="Idempotency-Key", min_length=1, max_length=128),
    ] = None,
) -> JSONResponse:
    """Enqueue an analysis request (`202`) or execute test-only `?wait=true` (`200`)."""
    client_ip = get_client_ip_from_request(request, settings)
    outcome = await analysis_service.submit_analysis(
        db,
        redis_client,
        principal=principal,
        settings=settings,
        ml_manager=ml_manager,
        payload=payload,
        client_ip=client_ip,
        idempotency_key=idempotency_key,
        wait=wait,
        sync_sessionmaker=sync_sessionmaker,
    )

    headers: dict[str, str] = {}
    req_trace_id = resolve_request_id(request)
    if req_trace_id is not None:
        headers["X-Request-Id"] = req_trace_id

    if outcome.envelope is not None:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=outcome.envelope.model_dump(mode="json"),
            headers=headers,
        )

    assert outcome.queued is not None
    headers["Location"] = outcome.queued.poll_url
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content=outcome.queued.model_dump(mode="json"),
        headers=headers,
    )


@router.get(
    "/analysis/requests/{request_id}",
    response_model=AnalysisPollEnvelope,
    status_code=status.HTTP_200_OK,
    operation_id="pollAnalysisRequest",
)
async def poll_analysis_request(
    request_id: uuid.UUID,
    response: Response,
    principal: ActorNoRateLimitDep,
    db: DbSessionDep,
    redis_client: RedisDep,
    settings: SettingsDep,
) -> AnalysisPollEnvelope:
    """Poll job progress/results under the dedicated `120 req/min` poll bucket."""
    envelope, should_set_retry_after = await analysis_service.poll_analysis_request(
        db,
        redis_client,
        principal=principal,
        settings=settings,
        request_id=request_id,
    )
    if should_set_retry_after:
        response.headers["Retry-After"] = analysis_service.POLL_RETRY_AFTER_HEADER_VALUE
    return envelope


@router.post(
    "/analysis/requests/{request_id}/cancel",
    response_model=AnalysisCancelResponse,
    status_code=status.HTTP_200_OK,
    operation_id="cancelAnalysisRequest",
)
async def cancel_analysis_request(
    request_id: uuid.UUID,
    principal: ActorPrincipalDep,
    db: DbSessionDep,
    redis_client: RedisDep,
) -> AnalysisCancelResponse:
    """Cancel a pending (immediate refund) or running analysis request."""
    return await analysis_service.cancel_analysis_request(
        db,
        redis_client,
        principal=principal,
        request_id=request_id,
    )


@router.get(
    "/analysis/{analysis_id}",
    response_model=AnalysisEnvelope,
    status_code=status.HTTP_200_OK,
    operation_id="getAnalysisResult",
)
async def get_analysis_result(
    analysis_id: AnalysisIdPathDep,
    principal: ActorPrincipalDep,
    db: DbSessionDep,
) -> AnalysisEnvelope:
    """Read a saved validated analysis with read-time merged selections."""
    return await analysis_service.get_analysis_result(
        db,
        principal=principal,
        analysis_id=analysis_id,
    )


@router.patch(
    "/analysis/{analysis_id}/selection",
    response_model=SelectionResponse,
    status_code=status.HTTP_200_OK,
    operation_id="updateAnalysisSelection",
)
async def update_analysis_selection(
    analysis_id: AnalysisIdPathDep,
    payload: SelectionUpdateRequest,
    principal: ActorPrincipalDep,
    db: DbSessionDep,
) -> SelectionResponse:
    """Persist user strategy choice without mutating `analysis_results.result_json`."""
    return await analysis_service.update_analysis_selection(
        db,
        principal=principal,
        analysis_id=analysis_id,
        payload=payload,
    )


@router.get(
    "/farms/{farm_id}/analyses",
    response_model=FarmAnalysesPage,
    status_code=status.HTTP_200_OK,
    operation_id="listFarmAnalyses",
)
async def list_farm_analyses(
    farm_id: FarmIdPathDep,
    principal: ActorPrincipalDep,
    db: DbSessionDep,
    pagination: PaginationDep,
    status_filter: Annotated[AnalysisRequestStatus | None, Query(alias="status")] = None,
) -> FarmAnalysesPage:
    """List paginated analysis history for an owned farm."""
    return await analysis_service.list_farm_analyses(
        db,
        principal=principal,
        farm_id=farm_id,
        pagination=pagination,
        status_filter=status_filter,
    )


__all__ = ["ErrorCode", "FieldShiftError", "router"]
