"""Analysis submission (W1), polling, cancellation, selections, and farm history."""

from __future__ import annotations

import asyncio
import copy
import time
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.deps import Principal
from app.core.config import Settings
from app.core.errors import ERROR_HTTP_STATUS, ErrorCode, FieldShiftError
from app.core.pagination import PaginationParams, decode_cursor, slice_keyset_page
from app.core.rate_limit import (
    REDIS_ERRORS_TOTAL,
    AsyncRedisLike,
    RateLimitGrant,
    build_analysis_checks,
    build_poll_check,
    check_rate_limits,
    get_or_hydrate_guest_quarters,
    increment_guest_quarters,
    rollback_rate_limits,
    sync_guest_quota_after_refund,
)
from app.ml_client.base import MLClientError
from app.ml_client.manager import MLProviderManager
from app.models.analysis import AnalysisRequest, AnalysisResult, AnalysisSelection
from app.repositories import analysis as analysis_repo
from app.repositories import catalog as catalog_repo
from app.repositories import dataset as dataset_repo
from app.repositories import farm as farm_repo
from app.schemas.analysis import (
    AnalysisCancelResponse,
    AnalysisEnvelope,
    AnalysisPollEnvelope,
    AnalysisQueuedResponse,
    AnalysisRequestStatus,
    AnalysisResultStatus,
    AnalysisSubmitRequest,
    DegradedModeMetadata,
    FarmAnalysesPage,
    FarmAnalysisSummary,
    PollErrorObject,
    SelectionResponse,
    SelectionUpdateRequest,
)
from app.schemas.common import Language, WarningNotice
from app.services import geo as geo_service
from app.services.analysis_input import (
    SCHEMA_VERSION,
    AssembledAnalysisField,
    aggregate_field_warnings,
    build_farm_analysis_input,
    compress_analysis_snapshot,
    compute_analysis_hashes,
    validate_input_rules,
    validate_unique_field_ids,
)
from app.services.farms import parse_farm_id

POLL_INTERVAL_MS = 2000
POLL_RETRY_AFTER_HEADER_VALUE = "2"
IDEMPOTENCY_WINDOW_HOURS = 24
WHAT_IF_WINDOW_HOURS = 24
_LAST_GOOD_REPLAY_PREFIX = "last_good_replay:"
_SYNC_WAIT_POLL_SLEEP_SECONDS = 0.05

_CATALOG_SYNC_LOCK_SQL = text("SELECT pg_advisory_xact_lock(hashtext('catalog_sync'))")

_POLL_ERROR_MESSAGES: dict[ErrorCode, str] = {
    ErrorCode.INVALID_INPUT: "Analysis request inputs are invalid.",
    ErrorCode.CATALOG_VERSION_MISMATCH: "Requested crop IDs do not match active catalog.",
    ErrorCode.INSUFFICIENT_DATA: "ML service could not generate plans with provided field data.",
    ErrorCode.INTERNAL_ERROR: "Internal error while processing analysis request.",
    ErrorCode.ML_UNAVAILABLE: "External ML service is unavailable.",
    ErrorCode.ML_INVALID_RESPONSE: "External ML response failed schema or semantic verification.",
    ErrorCode.ML_CONTRACT_ERROR: "External ML service rejected the analysis request contract.",
    ErrorCode.DATASET_VERSION_UNAVAILABLE: "Pinned environmental dataset version is unavailable.",
    ErrorCode.ML_DATASET_ERROR: "External ML service failed querying Schema: dataset.",
    ErrorCode.SERVICE_UNAVAILABLE: "Required backend dependency is unavailable.",
    ErrorCode.DATASET_UNAVAILABLE: "No active environmental dataset version is available.",
    ErrorCode.ML_TIMEOUT: "External ML service request timed out.",
    ErrorCode.JOB_TIMEOUT: "Timed out waiting for analysis completion.",
}


@dataclass(frozen=True, slots=True)
class SubmitAnalysisOutcome:
    """Result of `submit_analysis`: `202 AnalysisQueuedResponse` or `200 AnalysisEnvelope`."""

    queued: AnalysisQueuedResponse | None = None
    envelope: AnalysisEnvelope | None = None


def _ensure_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


def _normalize_idempotency_key(raw_key: str | None) -> str | None:
    if raw_key is None:
        return None
    trimmed = raw_key.strip()
    if not trimmed or len(trimmed) > 128:
        raise FieldShiftError(
            ErrorCode.INVALID_INPUT,
            "Idempotency-Key header must be 1..128 non-whitespace characters.",
            details=[{"field": "Idempotency-Key", "reason": "invalid_idempotency_key"}],
        )
    return trimmed


def _is_idempotency_conflict_error(exc: IntegrityError) -> bool:
    orig = getattr(exc, "orig", None)
    constraint_name = getattr(orig, "constraint_name", None) or getattr(
        getattr(orig, "__cause__", None),
        "constraint_name",
        None,
    )
    if constraint_name == "uq_analysis_idempotency":
        return True
    return "uq_analysis_idempotency" in str(exc)


def _parse_warnings_json(raw_warnings: Any) -> list[WarningNotice]:
    if not isinstance(raw_warnings, list):
        return []
    return [WarningNotice.model_validate(item) for item in raw_warnings]


def merge_selections_into_result(
    result_json: Mapping[str, Any],
    selections: Sequence[AnalysisSelection],
) -> dict[str, Any]:
    """Overlay persisted user `analysis_selections` onto a copy of `result_json`."""
    merged = copy.deepcopy(dict(result_json))
    if not selections:
        return merged

    status_by_pair = {
        (sel.field_id, sel.strategy_id): sel.selection_status
        for sel in selections
    }
    for field_plan in merged.get("field_plans", []):
        if not isinstance(field_plan, dict):
            continue
        fid = field_plan.get("field_id")
        if not isinstance(fid, str):
            continue
        for strategy in field_plan.get("strategies", []):
            if not isinstance(strategy, dict):
                continue
            sid = strategy.get("strategy_id")
            if not isinstance(sid, str):
                continue
            override = status_by_pair.get((fid, sid))
            if override is None:
                continue
            for season in strategy.get("seasons", []):
                if isinstance(season, dict):
                    season["selection_status"] = override
    return merged


async def _reconstruct_degraded_mode(
    db: AsyncSession,
    *,
    req: AnalysisRequest,
    now: datetime,
) -> DegradedModeMetadata | None:
    """Reconstruct `degraded_mode` from `last_good_replay:<analysis_id>` marker (`IMPL-017`)."""
    err_code = req.error_code
    if req.status not in ("ok", "partial") or not isinstance(err_code, str):
        return None
    if not err_code.startswith(_LAST_GOOD_REPLAY_PREFIX):
        return None

    source_analysis_id = err_code[len(_LAST_GOOD_REPLAY_PREFIX) :].strip()
    if not source_analysis_id:
        return None

    source_meta = await analysis_repo.get_replay_source_meta(
        db,
        source_analysis_id=source_analysis_id,
    )
    if source_meta is None:
        return None
    source_created_at_raw, source_dataset_version = source_meta
    source_created_at = _ensure_utc(source_created_at_raw)
    age_seconds = max(0, int((now - source_created_at).total_seconds()))
    return DegradedModeMetadata(
        kind="last_good_replay",
        stale=True,
        source_analysis_id=source_analysis_id,
        created_at=source_created_at,
        dataset_version=source_dataset_version,
        age_seconds=age_seconds,
    )


def _build_poll_error(
    req: AnalysisRequest,
    *,
    diagnostic_result: AnalysisResult | None,
) -> PollErrorObject:
    raw_code = req.error_code or ErrorCode.INTERNAL_ERROR.value
    try:
        err_code = ErrorCode(raw_code)
    except ValueError:
        err_code = ErrorCode.INTERNAL_ERROR

    details: list[dict[str, Any]] = []
    if (
        diagnostic_result is not None
        and isinstance(diagnostic_result.validation_errors, list)
        and diagnostic_result.validation_errors
    ):
        details = [
            item
            for item in diagnostic_result.validation_errors
            if isinstance(item, dict)
        ]
    elif err_code in _POLL_ERROR_MESSAGES:
        details = [{"reason": err_code.value.lower()}]

    message = _POLL_ERROR_MESSAGES.get(err_code, "Analysis request failed.")
    return PollErrorObject(
        code=err_code,
        http_equivalent=ERROR_HTTP_STATUS[err_code],
        message=message,
        details=details,
    )


def _queued_response_from_request(req: AnalysisRequest) -> AnalysisQueuedResponse:
    return AnalysisQueuedResponse(
        request_id=uuid.UUID(req.request_id),
        status="pending",
        poll_url=f"/api/v1/analysis/requests/{req.request_id}",
        poll_interval_ms=POLL_INTERVAL_MS,
        warnings=_parse_warnings_json(req.warnings),
    )


def _compute_hashes_for_payload(
    *,
    farm: Any,
    payload: AnalysisSubmitRequest,
    fields: Sequence[AssembledAnalysisField],
    catalog_version: str,
    dataset_version: str,
) -> tuple[str, str]:
    preview = build_farm_analysis_input(
        request_id=uuid.UUID(int=0),
        catalog_version=catalog_version,
        dataset_version=dataset_version,
        farm=farm,
        payload=payload,
        fields=fields,
    )
    return compute_analysis_hashes(preview)


async def _ensure_catalog_crops_ready(
    db: AsyncSession,
    *,
    sync_sessionmaker: async_sessionmaker[AsyncSession] | None,
    ml_manager: MLProviderManager,
    crop_ids: Sequence[str],
    now: datetime,
) -> str:
    """Verify `crop_ids` exist in active `crop_catalog`, syncing once on miss under lock."""
    latest = await catalog_repo.get_latest_catalog_version_meta(db)
    if latest is not None:
        missing = await catalog_repo.find_missing_crop_ids(
            db,
            catalog_version=latest[0],
            crop_ids=crop_ids,
        )
        if not missing:
            return latest[0]

    had_local_catalog = latest is not None

    async def _run_locked_sync(target_db: AsyncSession, *, commit_changes: bool) -> bool:
        await target_db.execute(_CATALOG_SYNC_LOCK_SQL)
        latest_after = await catalog_repo.get_latest_catalog_version_meta(target_db)
        if latest_after is not None:
            still_missing = await catalog_repo.find_missing_crop_ids(
                target_db,
                catalog_version=latest_after[0],
                crop_ids=crop_ids,
            )
            if not still_missing:
                if commit_changes:
                    await target_db.commit()
                return True

        try:
            catalog_payload = await ml_manager.get_catalog()
        except MLClientError as exc:
            if commit_changes:
                await target_db.rollback()
            if latest_after is None and not had_local_catalog:
                raise FieldShiftError(
                    ErrorCode.ML_UNAVAILABLE,
                    "Crop catalog is empty and upstream ML service is unavailable.",
                ) from exc
            logger = structlog.get_logger("app.services.analysis")
            await logger.awarning(
                "catalog_sync_on_miss_failed",
                ml_provider=ml_manager.active_provider_name,
                ml_error_code=exc.ml_error_code,
            )
            return False

        await catalog_repo.upsert_catalog_and_prune(
            target_db,
            payload=catalog_payload,
            synced_at=now,
            retain_versions=2,
        )
        if commit_changes:
            await target_db.commit()
        return True

    if sync_sessionmaker is not None:
        async with sync_sessionmaker() as sync_db:
            await _run_locked_sync(sync_db, commit_changes=True)
    else:
        async with db.begin_nested():
            await _run_locked_sync(db, commit_changes=False)

    latest_final = await catalog_repo.get_latest_catalog_version_meta(db)
    if latest_final is None:
        raise FieldShiftError(
            ErrorCode.ML_UNAVAILABLE,
            "Crop catalog is empty and could not be synchronized.",
        )

    unresolved = await catalog_repo.find_missing_crop_ids(
        db,
        catalog_version=latest_final[0],
        crop_ids=crop_ids,
    )
    if unresolved:
        raise FieldShiftError(
            ErrorCode.CATALOG_VERSION_MISMATCH,
            (
                f"Unknown crop_id(s) for active catalog version '{latest_final[0]}': "
                f"{', '.join(unresolved)}."
            ),
            details=[
                {
                    "field": "priorities",
                    "reason": "unknown_crop_id",
                    "catalog_version": latest_final[0],
                    "missing_crop_ids": unresolved,
                }
            ],
        )
    return latest_final[0]


async def _sync_guest_quarters_best_effort(
    redis_client: AsyncRedisLike | None,
    *,
    guest_token_hash: str,
    delta: int,
    fallback_total: int,
    ttl_seconds: int,
) -> None:
    if redis_client is None or delta <= 0:
        return
    try:
        await increment_guest_quarters(
            redis_client,
            guest_token_hash=guest_token_hash,
            delta=delta,
            fallback_total=fallback_total,
            ttl_seconds=ttl_seconds,
        )
    except RedisError as exc:
        REDIS_ERRORS_TOTAL.labels(operation="guest_quota_submit_sync").inc()
        logger = structlog.get_logger("app.services.analysis")
        await logger.awarning(
            "redis_guest_quota_submit_sync_failed",
            error_type=type(exc).__name__,
        )


async def _build_analysis_envelope(
    db: AsyncSession,
    *,
    req: AnalysisRequest,
    res: AnalysisResult,
    now: datetime,
) -> AnalysisEnvelope:
    selections = await analysis_repo.list_selections_for_analysis(
        db,
        analysis_id=res.analysis_id,
    )
    merged_result = merge_selections_into_result(res.result_json, selections)
    degraded_mode = await _reconstruct_degraded_mode(db, req=req, now=now)
    return AnalysisEnvelope(
        analysis_id=res.analysis_id,
        request_id=uuid.UUID(req.request_id),
        status=AnalysisResultStatus(res.status),
        dataset_version=res.dataset_version_used,
        warnings=_parse_warnings_json(req.warnings),
        degraded_mode=degraded_mode,
        result=merged_result,
    )


async def _wait_for_analysis_completion(
    db: AsyncSession,
    *,
    principal: Principal,
    request_id: uuid.UUID,
    timeout_seconds: int,
) -> AnalysisEnvelope:
    deadline = time.monotonic() + float(timeout_seconds)
    while True:
        # Close prior READ COMMITTED snapshot so external worker/test commits become visible.
        await db.rollback()
        db.expire_all()
        now = datetime.now(UTC)

        req = await analysis_repo.get_owned_analysis_request(
            db,
            request_id=request_id,
            user_id=principal.user_id,
            guest_token_hash=principal.guest_token_hash,
        )
        if req is None:
            raise FieldShiftError(ErrorCode.NOT_FOUND, "Analysis request was not found.")

        if req.status in ("ok", "partial"):
            res = await analysis_repo.get_result_for_request(
                db,
                request_id=req.request_id,
                validated_only=True,
            )
            if res is None:
                raise FieldShiftError(
                    ErrorCode.INTERNAL_ERROR,
                    "Completed analysis request is missing validated result.",
                )
            return await _build_analysis_envelope(db, req=req, res=res, now=now)

        if req.status == "failed":
            diag = await analysis_repo.get_result_for_request(
                db,
                request_id=req.request_id,
                validated_only=False,
            )
            poll_err = _build_poll_error(req, diagnostic_result=diag)
            raise FieldShiftError(
                poll_err.code,
                poll_err.message,
                status_code=poll_err.http_equivalent,
                details=poll_err.details,
            )

        if req.status == "cancelled":
            raise FieldShiftError(
                ErrorCode.CONFLICT,
                "Analysis request was cancelled before completion.",
                details=[{"request_id": str(request_id), "status": "cancelled"}],
            )

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise FieldShiftError(
                ErrorCode.JOB_TIMEOUT,
                f"Timed out waiting for analysis request '{request_id}'.",
                details=[{"request_id": str(request_id), "timeout_seconds": timeout_seconds}],
            )

        await asyncio.sleep(min(_SYNC_WAIT_POLL_SLEEP_SECONDS, remaining))


async def submit_analysis(
    db: AsyncSession,
    redis_client: AsyncRedisLike | None,
    *,
    principal: Principal,
    settings: Settings,
    ml_manager: MLProviderManager,
    payload: AnalysisSubmitRequest,
    client_ip: str,
    idempotency_key: str | None = None,
    wait: bool = False,
    sync_sessionmaker: async_sessionmaker[AsyncSession] | None = None,
    now_override: datetime | None = None,
) -> SubmitAnalysisOutcome:
    """Execute strict W1 synchronous admission (`POST /api/v1/analysis`)."""
    now = _ensure_utc(now_override or datetime.now(UTC))

    # --- W1 Step 1: Ownership (`404 NOT_FOUND` on missing/foreign farm or fields) ---
    farm_pk = parse_farm_id(payload.farm_id)
    farm = await farm_repo.get_owned_farm(
        db,
        farm_pk=farm_pk,
        user_id=principal.user_id,
        guest_token_hash=principal.guest_token_hash,
    )
    if farm is None:
        raise FieldShiftError(
            ErrorCode.NOT_FOUND,
            f"Farm '{payload.farm_id}' was not found.",
        )

    assembled_fields = await analysis_repo.get_owned_analysis_fields(
        db,
        farm_pk=farm_pk,
        requested_field_ids=payload.field_ids,
        demo_location_id=None,
    )
    if assembled_fields is None:
        raise FieldShiftError(
            ErrorCode.NOT_FOUND,
            "One or more requested field_ids do not belong to this farm.",
        )

    if wait and not settings.ALLOW_SYNC_WAIT:
        raise FieldShiftError(
            ErrorCode.INVALID_INPUT,
            "Synchronous ?wait=true mode is disabled (ALLOW_SYNC_WAIT=false).",
            details=[{"field": "wait", "reason": "sync_wait_disabled"}],
        )

    # --- W1 Step 2: Idempotency (`202` / `409`), Rate Limits (`429`), & Guest Quotas (`403`) ---
    clean_idemp_key = _normalize_idempotency_key(idempotency_key)
    stale_idemp_request_id: str | None = None

    if clean_idemp_key is not None:
        existing_idemp = await analysis_repo.get_request_by_idempotency_key(
            db,
            farm_pk=farm_pk,
            idempotency_key=clean_idemp_key,
        )
        if existing_idemp is not None:
            idemp_cutoff = now - timedelta(hours=IDEMPOTENCY_WINDOW_HOURS)
            if _ensure_utc(existing_idemp.created_at) >= idemp_cutoff:
                _, expected_full_hash = _compute_hashes_for_payload(
                    farm=farm,
                    payload=payload,
                    fields=assembled_fields,
                    catalog_version=existing_idemp.catalog_version,
                    dataset_version=existing_idemp.dataset_version,
                )
                if expected_full_hash != existing_idemp.full_input_hash:
                    raise FieldShiftError(
                        ErrorCode.CONFLICT,
                        "Idempotency-Key was already used with a different analysis payload.",
                        details=[
                            {
                                "field": "Idempotency-Key",
                                "reason": "idempotency_payload_mismatch",
                            }
                        ],
                    )
                if wait:
                    envelope = await _wait_for_analysis_completion(
                        db,
                        principal=principal,
                        request_id=uuid.UUID(existing_idemp.request_id),
                        timeout_seconds=settings.SYNC_WAIT_TIMEOUT_SECONDS,
                    )
                    return SubmitAnalysisOutcome(envelope=envelope)
                return SubmitAnalysisOutcome(queued=_queued_response_from_request(existing_idemp))
            stale_idemp_request_id = existing_idemp.request_id

    latest_cat = await catalog_repo.get_latest_catalog_version_meta(db)
    active_ds = await dataset_repo.get_active_dataset(db)

    provisional_input_hash: str | None = None
    parent_request_id: str | None = None
    quota_units = 4
    if latest_cat is not None and active_ds is not None:
        provisional_input_hash, _ = _compute_hashes_for_payload(
            farm=farm,
            payload=payload,
            fields=assembled_fields,
            catalog_version=latest_cat[0],
            dataset_version=active_ds.dataset_version,
        )
        recent_parent = await analysis_repo.find_recent_what_if_parent(
            db,
            farm_pk=farm_pk,
            input_hash=provisional_input_hash,
            cutoff=now - timedelta(hours=WHAT_IF_WINDOW_HOURS),
        )
        if recent_parent is not None:
            quota_units = 1
            parent_request_id = recent_parent.request_id

    checks = build_analysis_checks(
        client_ip=client_ip,
        quota_units=quota_units,
        settings=settings,
        user_id=principal.user_id,
    )
    rate_limit_grants: list[RateLimitGrant] = await check_rate_limits(
        redis_client,
        checks,
        fail_closed=settings.REDIS_FAIL_CLOSED,
        now_override=int(now.timestamp()) if now_override is not None else None,
    )

    # All Step 2 (403) and Steps 3..5 failures roll back Redis rate increments cleanly (`IMPL-001`).
    try:
        used_quarters = 0
        guest_ttl = 0
        if principal.is_guest:
            assert principal.guest_token_hash is not None
            guest_demo_location_id = await analysis_repo.get_guest_demo_location_id(
                db,
                guest_token_hash=principal.guest_token_hash,
                now=now,
            )
            if guest_demo_location_id is None:
                raise FieldShiftError(
                    ErrorCode.UNAUTHORIZED,
                    "Guest session has expired or is invalid.",
                )
            used_quarters, guest_ttl = await get_or_hydrate_guest_quarters(
                db,
                redis_client,
                guest_token_hash=principal.guest_token_hash,
                now=now,
                lock_pg_row=True,
                fail_closed=settings.REDIS_FAIL_CLOSED,
            )
            max_quarters = settings.GUEST_MAX_ANALYSES * 4
            if used_quarters + quota_units > max_quarters:
                raise FieldShiftError(
                    ErrorCode.GUEST_LIMIT_REACHED,
                    f"Guest analysis limit reached ({used_quarters}/{max_quarters} quarters used).",
                    details=[
                        {
                            "used_quarters": used_quarters,
                            "requested_quarters": quota_units,
                            "max_quarters": max_quarters,
                        }
                    ],
                )
        else:
            guest_demo_location_id = None

        # --- W1 Step 3: PostGIS Boundary (`422`), Warnings, & `INPUT-01..03` (`400`) ---
        projections = [item.projection for item in assembled_fields]
        if principal.is_guest:
            for proj in projections:
                await geo_service.check_field_coordinates_coverage(
                    db,
                    latitude=proj.latitude,
                    longitude=proj.longitude,
                    is_guest=True,
                    demo_location_id=guest_demo_location_id,
                    field_id=proj.field.external_field_id,
                )

        warnings = aggregate_field_warnings(
            projections,
            include_outside_coverage=not principal.is_guest,
        )
        validate_unique_field_ids(payload.field_ids)
        validate_input_rules(payload, projections)

        # --- W1 Step 4: Catalog & Active Dataset Ready (`409` / `502` / `503`) ---
        requested_crops = [
            *payload.priorities.target_crop_ids,
            *payload.priorities.excluded_crop_ids,
        ]
        resolved_catalog_version = await _ensure_catalog_crops_ready(
            db,
            sync_sessionmaker=sync_sessionmaker,
            ml_manager=ml_manager,
            crop_ids=requested_crops,
            now=now,
        )
        resolved_dataset = await dataset_repo.require_active_dataset(db)
        resolved_dataset_version = str(resolved_dataset.dataset_version)

        # --- W1 Step 5: Assemble Zero-PII Snapshot, Hash, Savepoint Insert (`202` / Race) ---
        new_request_id = uuid.uuid4()
        farm_input = build_farm_analysis_input(
            request_id=new_request_id,
            catalog_version=resolved_catalog_version,
            dataset_version=resolved_dataset_version,
            farm=farm,
            payload=payload,
            fields=assembled_fields,
        )
        final_input_hash, final_full_hash = compute_analysis_hashes(farm_input)

        effective_quota_units = quota_units
        effective_parent_id = parent_request_id
        if provisional_input_hash is not None and final_input_hash != provisional_input_hash:
            updated_parent = await analysis_repo.find_recent_what_if_parent(
                db,
                farm_pk=farm_pk,
                input_hash=final_input_hash,
                cutoff=now - timedelta(hours=WHAT_IF_WINDOW_HOURS),
            )
            if updated_parent is not None:
                effective_quota_units = 1
                effective_parent_id = updated_parent.request_id
            else:
                effective_quota_units = 4
                effective_parent_id = None
                if principal.is_guest:
                    max_quarters = settings.GUEST_MAX_ANALYSES * 4
                    if used_quarters + effective_quota_units > max_quarters:
                        raise FieldShiftError(
                            ErrorCode.GUEST_LIMIT_REACHED,
                            (
                                f"Guest analysis limit reached "
                                f"({used_quarters}/{max_quarters} quarters used)."
                            ),
                            details=[
                                {
                                    "used_quarters": used_quarters,
                                    "requested_quarters": effective_quota_units,
                                    "max_quarters": max_quarters,
                                }
                            ],
                        )

        snapshot_gz = compress_analysis_snapshot(farm_input)
        serialized_warnings = [w.model_dump(mode="json", exclude_none=True) for w in warnings]

        try:
            async with db.begin_nested():
                if stale_idemp_request_id is not None:
                    await analysis_repo.clear_stale_idempotency_key(
                        db,
                        request_id=stale_idemp_request_id,
                    )
                created_row = await analysis_repo.insert_analysis_request(
                    db,
                    request_id=new_request_id,
                    farm_pk=farm_pk,
                    idempotency_key=clean_idemp_key,
                    parent_request_id=effective_parent_id,
                    schema_version=SCHEMA_VERSION,
                    catalog_version=resolved_catalog_version,
                    dataset_version=resolved_dataset_version,
                    language=payload.language.value,
                    quota_units=effective_quota_units,
                    input_hash=final_input_hash,
                    full_input_hash=final_full_hash,
                    input_snapshot_gz=snapshot_gz,
                    warnings=serialized_warnings,
                )
        except IntegrityError as exc:
            if clean_idemp_key is None or not _is_idempotency_conflict_error(exc):
                raise
            await db.rollback()
            winner = await analysis_repo.get_request_by_idempotency_key(
                db,
                farm_pk=farm_pk,
                idempotency_key=clean_idemp_key,
            )
            if winner is None:
                raise FieldShiftError(
                    ErrorCode.CONFLICT,
                    "Concurrent Idempotency-Key conflict.",
                ) from exc

            if redis_client is not None and rate_limit_grants:
                await rollback_rate_limits(redis_client, rate_limit_grants)
                rate_limit_grants = []

            if (
                winner.catalog_version == resolved_catalog_version
                and winner.dataset_version == resolved_dataset_version
            ):
                winner_expected_hash = final_full_hash
            else:
                _, winner_expected_hash = compute_analysis_hashes(
                    {
                        **farm_input,
                        "catalog_version": winner.catalog_version,
                        "dataset_version": winner.dataset_version,
                    }
                )
            if winner_expected_hash != winner.full_input_hash:
                raise FieldShiftError(
                    ErrorCode.CONFLICT,
                    "Idempotency-Key was already used with a different analysis payload.",
                    details=[
                        {
                            "field": "Idempotency-Key",
                            "reason": "idempotency_payload_mismatch",
                        }
                    ],
                ) from exc

            if wait:
                envelope = await _wait_for_analysis_completion(
                    db,
                    principal=principal,
                    request_id=uuid.UUID(winner.request_id),
                    timeout_seconds=settings.SYNC_WAIT_TIMEOUT_SECONDS,
                )
                return SubmitAnalysisOutcome(envelope=envelope)
            return SubmitAnalysisOutcome(queued=_queued_response_from_request(winner))

        await db.commit()
    except Exception:
        if redis_client is not None and rate_limit_grants:
            await rollback_rate_limits(redis_client, rate_limit_grants)
        raise

    if principal.is_guest:
        assert principal.guest_token_hash is not None
        await _sync_guest_quarters_best_effort(
            redis_client,
            guest_token_hash=principal.guest_token_hash,
            delta=effective_quota_units,
            fallback_total=used_quarters + effective_quota_units,
            ttl_seconds=guest_ttl,
        )

    if wait:
        envelope = await _wait_for_analysis_completion(
            db,
            principal=principal,
            request_id=new_request_id,
            timeout_seconds=settings.SYNC_WAIT_TIMEOUT_SECONDS,
        )
        return SubmitAnalysisOutcome(envelope=envelope)

    return SubmitAnalysisOutcome(queued=_queued_response_from_request(created_row))


async def poll_analysis_request(
    db: AsyncSession,
    redis_client: AsyncRedisLike | None,
    *,
    principal: Principal,
    settings: Settings,
    request_id: uuid.UUID,
    now_override: datetime | None = None,
) -> tuple[AnalysisPollEnvelope, bool]:
    """Poll job state (`120 req/min` Redis bucket) returning `(envelope, retry_after_flag)`."""
    now = _ensure_utc(now_override or datetime.now(UTC))
    await check_rate_limits(
        redis_client,
        [
            build_poll_check(
                user_id=principal.user_id,
                guest_token_hash=principal.guest_token_hash,
            )
        ],
        fail_closed=settings.REDIS_FAIL_CLOSED,
        now_override=int(now.timestamp()) if now_override is not None else None,
    )
    req = await analysis_repo.get_owned_analysis_request(
        db,
        request_id=request_id,
        user_id=principal.user_id,
        guest_token_hash=principal.guest_token_hash,
    )
    if req is None:
        raise FieldShiftError(
            ErrorCode.NOT_FOUND,
            f"Analysis request '{request_id}' was not found.",
        )

    warnings = _parse_warnings_json(req.warnings)
    req_status = AnalysisRequestStatus(req.status)

    if req_status in (AnalysisRequestStatus.PENDING, AnalysisRequestStatus.RUNNING):
        return (
            AnalysisPollEnvelope(
                request_id=uuid.UUID(req.request_id),
                status=req_status,
                poll_interval_ms=POLL_INTERVAL_MS,
                analysis_id=None,
                warnings=warnings,
                degraded_mode=None,
                error=None,
                result=None,
            ),
            True,
        )

    if req_status == AnalysisRequestStatus.CANCELLED:
        return (
            AnalysisPollEnvelope(
                request_id=uuid.UUID(req.request_id),
                status=req_status,
                poll_interval_ms=None,
                analysis_id=None,
                warnings=warnings,
                degraded_mode=None,
                error=None,
                result=None,
            ),
            False,
        )

    if req_status in (AnalysisRequestStatus.OK, AnalysisRequestStatus.PARTIAL):
        res = await analysis_repo.get_result_for_request(
            db,
            request_id=req.request_id,
            validated_only=True,
        )
        if res is None:
            raise FieldShiftError(
                ErrorCode.INTERNAL_ERROR,
                "Completed analysis request is missing validated result.",
            )
        selections = await analysis_repo.list_selections_for_analysis(
            db,
            analysis_id=res.analysis_id,
        )
        merged_result = merge_selections_into_result(res.result_json, selections)
        degraded_mode = await _reconstruct_degraded_mode(db, req=req, now=now)
        return (
            AnalysisPollEnvelope(
                request_id=uuid.UUID(req.request_id),
                status=req_status,
                poll_interval_ms=None,
                analysis_id=res.analysis_id,
                warnings=warnings,
                degraded_mode=degraded_mode,
                error=None,
                result=merged_result,
            ),
            False,
        )

    diag = await analysis_repo.get_result_for_request(
        db,
        request_id=req.request_id,
        validated_only=False,
    )
    return (
        AnalysisPollEnvelope(
            request_id=uuid.UUID(req.request_id),
            status=AnalysisRequestStatus.FAILED,
            poll_interval_ms=None,
            analysis_id=None,
            warnings=warnings,
            degraded_mode=None,
            error=_build_poll_error(req, diagnostic_result=diag),
            result=None,
        ),
        False,
    )


async def cancel_analysis_request(
    db: AsyncSession,
    redis_client: AsyncRedisLike | None,
    *,
    principal: Principal,
    request_id: uuid.UUID,
    now_override: datetime | None = None,
) -> AnalysisCancelResponse:
    """Cancel pending (immediate refund) or running (cooperative cancel) request (`IMPL-020`)."""
    now = _ensure_utc(now_override or datetime.now(UTC))
    req = await analysis_repo.get_owned_analysis_request(
        db,
        request_id=request_id,
        user_id=principal.user_id,
        guest_token_hash=principal.guest_token_hash,
        for_update=True,
    )
    if req is None:
        raise FieldShiftError(
            ErrorCode.NOT_FOUND,
            f"Analysis request '{request_id}' was not found.",
        )

    if req.status in ("ok", "partial", "failed", "cancelled"):
        raise FieldShiftError(
            ErrorCode.CONFLICT,
            f"Analysis request in terminal status '{req.status}' cannot be cancelled.",
            details=[
                {
                    "request_id": str(request_id),
                    "status": req.status,
                    "reason": "already_terminal",
                }
            ],
        )

    refunded_quarters = 0
    if req.status == "pending":
        refunded_quarters = int(req.quota_units)
        req.status = "cancelled"
        req.cancelled_at = now
        req.quota_units = 0
    elif req.status == "running" and req.cancelled_at is None:
        req.cancelled_at = now

    await db.commit()

    if principal.is_guest and refunded_quarters > 0:
        assert principal.guest_token_hash is not None
        await sync_guest_quota_after_refund(
            redis_client,
            guest_token_hash=principal.guest_token_hash,
            delta=refunded_quarters,
        )

    return AnalysisCancelResponse(request_id=uuid.UUID(req.request_id), status="cancelled")


async def get_analysis_result(
    db: AsyncSession,
    *,
    principal: Principal,
    analysis_id: str,
    now_override: datetime | None = None,
) -> AnalysisEnvelope:
    """Fetch saved validated `AnalysisResult` with read-time merged user selections."""
    now = _ensure_utc(now_override or datetime.now(UTC))
    owned = await analysis_repo.get_owned_analysis_result(
        db,
        analysis_id=analysis_id,
        user_id=principal.user_id,
        guest_token_hash=principal.guest_token_hash,
    )
    if owned is None:
        raise FieldShiftError(
            ErrorCode.NOT_FOUND,
            f"Analysis '{analysis_id}' was not found.",
        )
    res, req = owned
    return await _build_analysis_envelope(db, req=req, res=res, now=now)


def _assert_strategy_in_result(
    result_json: Mapping[str, Any],
    *,
    field_id: str,
    strategy_id: str,
) -> None:
    for field_plan in result_json.get("field_plans", []):
        if isinstance(field_plan, dict) and field_plan.get("field_id") == field_id:
            for strategy in field_plan.get("strategies", []):
                if isinstance(strategy, dict) and strategy.get("strategy_id") == strategy_id:
                    return
            raise FieldShiftError(
                ErrorCode.INVALID_INPUT,
                f"Strategy '{strategy_id}' does not exist for field '{field_id}'.",
                details=[
                    {
                        "field": "strategy_id",
                        "reason": "unknown_analysis_strategy_id",
                        "field_id": field_id,
                        "strategy_id": strategy_id,
                    }
                ],
            )
    raise FieldShiftError(
        ErrorCode.INVALID_INPUT,
        f"Field '{field_id}' does not exist in this analysis result.",
        details=[
            {
                "field": "field_id",
                "reason": "unknown_analysis_field_id",
                "field_id": field_id,
            }
        ],
    )


async def update_analysis_selection(
    db: AsyncSession,
    *,
    principal: Principal,
    analysis_id: str,
    payload: SelectionUpdateRequest,
    now_override: datetime | None = None,
) -> SelectionResponse:
    """Record user strategy selection (`selected`/`rejected`) under parent `FOR UPDATE` lock."""
    now = _ensure_utc(now_override or datetime.now(UTC))
    owned = await analysis_repo.get_owned_analysis_result(
        db,
        analysis_id=analysis_id,
        user_id=principal.user_id,
        guest_token_hash=principal.guest_token_hash,
        for_update=True,
    )
    if owned is None:
        raise FieldShiftError(
            ErrorCode.NOT_FOUND,
            f"Analysis '{analysis_id}' was not found.",
        )
    res, _ = owned
    _assert_strategy_in_result(
        res.result_json,
        field_id=payload.field_id,
        strategy_id=payload.strategy_id,
    )

    await analysis_repo.upsert_analysis_selection(
        db,
        analysis_id=res.analysis_id,
        field_id=payload.field_id,
        strategy_id=payload.strategy_id,
        selection_status=payload.selection_status.value,
        now=now,
    )
    await db.commit()
    return SelectionResponse(
        analysis_id=res.analysis_id,
        field_id=payload.field_id,
        strategy_id=payload.strategy_id,
        selection_status=payload.selection_status,
    )


def _decode_analyses_cursor(cursor: str | None) -> tuple[datetime | None, str | None]:
    if cursor is None:
        return None, None
    payload = decode_cursor(cursor, required_keys=("created_at", "request_id"))
    raw_dt = payload["created_at"]
    raw_rid = payload["request_id"]
    if not isinstance(raw_dt, str) or not isinstance(raw_rid, str):
        raise FieldShiftError(
            ErrorCode.INVALID_INPUT,
            "Invalid pagination cursor.",
            details=[{"field": "cursor", "reason": "malformed_cursor"}],
        )
    try:
        parsed_dt = datetime.fromisoformat(raw_dt)
        if parsed_dt.tzinfo is None:
            parsed_dt = parsed_dt.replace(tzinfo=UTC)
        parsed_rid = str(uuid.UUID(raw_rid))
    except ValueError as exc:
        raise FieldShiftError(
            ErrorCode.INVALID_INPUT,
            "Invalid pagination cursor.",
            details=[{"field": "cursor", "reason": "malformed_cursor"}],
        ) from exc
    return parsed_dt, parsed_rid


async def list_farm_analyses(
    db: AsyncSession,
    *,
    principal: Principal,
    farm_id: str,
    pagination: PaginationParams,
    status_filter: AnalysisRequestStatus | None = None,
) -> FarmAnalysesPage:
    """List paginated analysis history for an owned farm (`GET /farms/{farm_id}/analyses`)."""
    farm_pk = parse_farm_id(farm_id)
    farm = await farm_repo.get_owned_farm(
        db,
        farm_pk=farm_pk,
        user_id=principal.user_id,
        guest_token_hash=principal.guest_token_hash,
    )
    if farm is None:
        raise FieldShiftError(
            ErrorCode.NOT_FOUND,
            f"Farm '{farm_id}' was not found.",
        )

    after_dt, after_rid = _decode_analyses_cursor(pagination.cursor)
    rows = await analysis_repo.list_farm_analyses(
        db,
        farm_pk=farm_pk,
        limit=pagination.limit,
        after_created_at=after_dt,
        after_request_id=after_rid,
        status_filter=status_filter.value if status_filter is not None else None,
    )
    sliced, next_cursor, has_more = slice_keyset_page(
        rows,
        limit=pagination.limit,
        cursor_key_fn=lambda row: {
            "created_at": _ensure_utc(row[0].created_at).isoformat(),
            "request_id": row[0].request_id,
        },
    )
    items = [
        FarmAnalysisSummary(
            request_id=uuid.UUID(req.request_id),
            analysis_id=analysis_id,
            status=AnalysisRequestStatus(req.status),
            language=Language(req.language),
            catalog_version=req.catalog_version,
            dataset_version=req.dataset_version,
            ml_engine_version=ml_engine_version,
            warnings=_parse_warnings_json(req.warnings),
            created_at=_ensure_utc(req.created_at),
            duration_ms=req.duration_ms,
        )
        for req, analysis_id, ml_engine_version in sliced
    ]
    return FarmAnalysesPage(
        items=items,
        next_cursor=next_cursor,
        has_more=has_more,
    )
