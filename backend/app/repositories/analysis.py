"""PostgreSQL repositories for `analysis_requests`, `analysis_results`, & `analysis_selections`."""

from __future__ import annotations

import json
import secrets
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, Literal

from sqlalchemy import and_, delete, func, or_, select, text, tuple_, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ErrorCode
from app.models.analysis import AnalysisRequest, AnalysisResult, AnalysisSelection
from app.models.demo import GuestSession
from app.models.farm import Farm
from app.models.field import Field, FieldCropHistory
from app.repositories.field import select_field_projections
from app.services.analysis_input import AssembledAnalysisField, FieldProjectionData


def _row_to_field_projection(row: Any) -> FieldProjectionData:
    field_obj = Field(
        id=int(row["pk"]),
        farm_id=int(row["farm_id"]),
        external_field_id=str(row["external_field_id"]),
        field_name=str(row["field_name"]),
        is_unverified_demo_parcel=bool(row["is_unverified_demo_parcel"]),
        area_hectares=Decimal(str(row["area_hectares"])),
        soil_type=str(row["soil_type"]),
        soil_source=str(row["soil_source"]),
        soil_ph=Decimal(str(row["soil_ph"])) if row["soil_ph"] is not None else None,
        organic_matter_percent=(
            Decimal(str(row["organic_matter_percent"]))
            if row["organic_matter_percent"] is not None
            else None
        ),
        soil_test_date=row["soil_test_date"],
        water_availability=str(row["water_availability"]),
        water_source=str(row["water_source"]),
        water_source_other=row["water_source_other"],
        irrigation_system=str(row["irrigation_system"]),
        elevation_m=(
            Decimal(str(row["elevation_m"])) if row["elevation_m"] is not None else None
        ),
    )
    raw_boundary = row["boundary_geojson"]
    boundary = json.loads(str(raw_boundary)) if raw_boundary is not None else None
    return FieldProjectionData(
        field=field_obj,
        latitude=float(row["latitude"]),
        longitude=float(row["longitude"]),
        boundary=boundary,
        outside_mvp_coverage=not bool(row["in_guelma_boundary"]),
    )


async def get_owned_analysis_fields(
    db: AsyncSession,
    *,
    farm_pk: int,
    requested_field_ids: Sequence[str],
    demo_location_id: int | None = None,
) -> list[AssembledAnalysisField] | None:
    """Load owned projected fields + crop histories matching `requested_field_ids`."""
    unique_ids = list(dict.fromkeys(requested_field_ids))
    if not unique_ids:
        return None

    stmt = select_field_projections(demo_location_id=demo_location_id).where(
        Field.farm_id == farm_pk,
        Field.external_field_id.in_(unique_ids),
    )
    rows = (await db.execute(stmt)).mappings().all()
    if len(rows) != len(unique_ids):
        return None

    proj_by_ext_id: dict[str, FieldProjectionData] = {}
    field_pks: list[int] = []
    for row in rows:
        proj = _row_to_field_projection(row)
        proj_by_ext_id[proj.field.external_field_id] = proj
        field_pks.append(int(proj.field.id))

    history_stmt = (
        select(FieldCropHistory)
        .where(FieldCropHistory.field_id.in_(field_pks))
        .order_by(FieldCropHistory.year.desc(), FieldCropHistory.season.asc())
    )
    history_rows = (await db.execute(history_stmt)).scalars().all()
    history_by_field_pk: dict[int, list[FieldCropHistory]] = {}
    for ch in history_rows:
        history_by_field_pk.setdefault(int(ch.field_id), []).append(ch)

    return [
        AssembledAnalysisField(
            projection=proj_by_ext_id[ext_id],
            crop_history=tuple(history_by_field_pk.get(int(proj_by_ext_id[ext_id].field.id), ())),
        )
        for ext_id in unique_ids
    ]


async def get_guest_demo_location_id(
    db: AsyncSession,
    *,
    guest_token_hash: str,
    now: datetime,
) -> int | None:
    """Return active guest session's bound `demo_location_id`, or None if expired/missing."""
    stmt = select(GuestSession.demo_location_id).where(
        GuestSession.guest_token == guest_token_hash,
        GuestSession.expires_at > now,
    )
    val = (await db.execute(stmt)).scalar_one_or_none()
    return int(val) if val is not None else None


async def get_request_by_idempotency_key(
    db: AsyncSession,
    *,
    farm_pk: int,
    idempotency_key: str,
) -> AnalysisRequest | None:
    """Fetch existing `analysis_requests` row for `(farm_id, idempotency_key)`."""
    stmt = select(AnalysisRequest).where(
        AnalysisRequest.farm_id == farm_pk,
        AnalysisRequest.idempotency_key == idempotency_key,
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def clear_stale_idempotency_key(
    db: AsyncSession,
    *,
    request_id: str,
) -> None:
    """Detach expired (>24h) idempotency key so the same key can be cleanly reused (`IMPL-002`)."""
    await db.execute(
        update(AnalysisRequest)
        .where(AnalysisRequest.request_id == request_id)
        .values(idempotency_key=None)
    )
    await db.flush()


async def find_recent_what_if_parent(
    db: AsyncSession,
    *,
    farm_pk: int,
    input_hash: str,
    cutoff: datetime,
) -> AnalysisRequest | None:
    """Find latest active/completed request matching `input_hash` within 24h on the same farm."""
    stmt = (
        select(AnalysisRequest)
        .where(
            AnalysisRequest.farm_id == farm_pk,
            AnalysisRequest.input_hash == input_hash,
            AnalysisRequest.created_at >= cutoff,
            AnalysisRequest.status.in_(("pending", "running", "ok", "partial")),
        )
        .order_by(AnalysisRequest.created_at.desc())
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def insert_analysis_request(
    db: AsyncSession,
    *,
    request_id: uuid.UUID,
    farm_pk: int,
    idempotency_key: str | None,
    parent_request_id: str | None,
    schema_version: str,
    catalog_version: str,
    dataset_version: str,
    language: str,
    quota_units: int,
    input_hash: str,
    full_input_hash: str,
    input_snapshot_gz: bytes,
    warnings: list[dict[str, Any]],
) -> AnalysisRequest:
    """Insert pending `analysis_requests` row and flush within active transaction/savepoint."""
    row = AnalysisRequest(
        request_id=str(request_id),
        farm_id=farm_pk,
        idempotency_key=idempotency_key,
        parent_request_id=parent_request_id,
        schema_version=schema_version,
        catalog_version=catalog_version,
        dataset_version=dataset_version,
        language=language,
        quota_units=quota_units,
        input_hash=input_hash,
        full_input_hash=full_input_hash,
        input_snapshot_gz=input_snapshot_gz,
        warnings=warnings,
        status="pending",
        attempts=0,
    )
    db.add(row)
    await db.flush()
    await db.refresh(row)
    return row


def _owner_filter(
    *,
    user_id: int | None,
    guest_token_hash: str | None,
) -> Any:
    if (user_id is None) == (guest_token_hash is None):
        raise ValueError("Exactly one of user_id or guest_token_hash must be provided")
    if user_id is not None:
        return Farm.user_id == user_id
    return Farm.guest_session_token == guest_token_hash


async def get_owned_analysis_request(
    db: AsyncSession,
    *,
    request_id: uuid.UUID,
    user_id: int | None,
    guest_token_hash: str | None,
    for_update: bool = False,
) -> AnalysisRequest | None:
    """Fetch owner-scoped `AnalysisRequest` (`404` when missing or foreign-owned)."""
    stmt = (
        select(AnalysisRequest)
        .join(Farm, Farm.id == AnalysisRequest.farm_id)
        .where(
            AnalysisRequest.request_id == str(request_id),
            _owner_filter(user_id=user_id, guest_token_hash=guest_token_hash),
        )
    )
    if for_update:
        stmt = stmt.with_for_update(of=AnalysisRequest)
    return (await db.execute(stmt)).scalar_one_or_none()


async def get_result_for_request(
    db: AsyncSession,
    *,
    request_id: str,
    validated_only: bool = True,
) -> AnalysisResult | None:
    """Fetch `AnalysisResult` associated with `request_id`."""
    stmt = select(AnalysisResult).where(AnalysisResult.request_id == request_id)
    if validated_only:
        stmt = stmt.where(
            AnalysisResult.validation_passed.is_(True),
            AnalysisResult.status.in_(("ok", "partial")),
        )
    else:
        stmt = stmt.order_by(AnalysisResult.id.desc()).limit(1)
    return (await db.execute(stmt)).scalar_one_or_none()


async def get_owned_analysis_result(
    db: AsyncSession,
    *,
    analysis_id: str,
    user_id: int | None,
    guest_token_hash: str | None,
    for_update: bool = False,
) -> tuple[AnalysisResult, AnalysisRequest] | None:
    """Fetch owner-scoped validated `AnalysisResult` + parent `AnalysisRequest`."""
    stmt = (
        select(AnalysisResult, AnalysisRequest)
        .join(AnalysisRequest, AnalysisRequest.request_id == AnalysisResult.request_id)
        .join(Farm, Farm.id == AnalysisRequest.farm_id)
        .where(
            AnalysisResult.analysis_id == analysis_id,
            AnalysisResult.validation_passed.is_(True),
            AnalysisResult.status.in_(("ok", "partial")),
            _owner_filter(user_id=user_id, guest_token_hash=guest_token_hash),
        )
    )
    if for_update:
        stmt = stmt.with_for_update(of=AnalysisResult)
    row = (await db.execute(stmt)).one_or_none()
    if row is None:
        return None
    return row[0], row[1]


async def get_replay_source_meta(
    db: AsyncSession,
    *,
    source_analysis_id: str,
) -> tuple[datetime, str] | None:
    """Fetch `(created_at, dataset_version_used)` for `last_good_replay` reconstruction."""
    stmt = select(
        AnalysisResult.created_at,
        AnalysisResult.dataset_version_used,
    ).where(
        AnalysisResult.analysis_id == source_analysis_id,
        AnalysisResult.validation_passed.is_(True),
    )
    row = (await db.execute(stmt)).one_or_none()
    if row is None:
        return None
    return row[0], str(row[1])


async def list_selections_for_analysis(
    db: AsyncSession,
    *,
    analysis_id: str,
) -> list[AnalysisSelection]:
    """Load persisted user strategy selections for read-time merging."""
    stmt = select(AnalysisSelection).where(AnalysisSelection.analysis_id == analysis_id)
    return list((await db.execute(stmt)).scalars().all())


async def upsert_analysis_selection(
    db: AsyncSession,
    *,
    analysis_id: str,
    field_id: str,
    strategy_id: str,
    selection_status: str,
    now: datetime,
) -> None:
    """Persist selection cleanly under parent `AnalysisResult` lock (`IMPL-020`)."""
    if selection_status == "selected":
        await db.execute(
            delete(AnalysisSelection).where(
                AnalysisSelection.analysis_id == analysis_id,
                AnalysisSelection.field_id == field_id,
                AnalysisSelection.strategy_id != strategy_id,
                AnalysisSelection.selection_status == "selected",
            )
        )

    insert_stmt = pg_insert(AnalysisSelection).values(
        analysis_id=analysis_id,
        field_id=field_id,
        strategy_id=strategy_id,
        selection_status=selection_status,
        updated_at=now,
    )
    upsert_stmt = insert_stmt.on_conflict_do_update(
        index_elements=[
            AnalysisSelection.analysis_id,
            AnalysisSelection.field_id,
            AnalysisSelection.strategy_id,
        ],
        set_={
            "selection_status": selection_status,
            "updated_at": now,
        },
    )
    await db.execute(upsert_stmt)


async def list_farm_analyses(
    db: AsyncSession,
    *,
    farm_pk: int,
    limit: int,
    after_created_at: datetime | None,
    after_request_id: str | None,
    status_filter: str | None,
) -> list[tuple[AnalysisRequest, str | None, str | None]]:
    """Fetch `limit + 1` farm analyses ordered newest first (`created_at DESC, request_id DESC`)."""
    stmt = (
        select(
            AnalysisRequest,
            AnalysisResult.analysis_id,
            AnalysisResult.ml_engine_version,
        )
        .outerjoin(
            AnalysisResult,
            and_(
                AnalysisResult.request_id == AnalysisRequest.request_id,
                AnalysisResult.validation_passed.is_(True),
                AnalysisResult.status.in_(("ok", "partial")),
            ),
        )
        .where(AnalysisRequest.farm_id == farm_pk)
    )
    if status_filter is not None:
        stmt = stmt.where(AnalysisRequest.status == status_filter)
    if after_created_at is not None and after_request_id is not None:
        stmt = stmt.where(
            tuple_(AnalysisRequest.created_at, AnalysisRequest.request_id)
            < (after_created_at, after_request_id)
        )
    stmt = stmt.order_by(
        AnalysisRequest.created_at.desc(),
        AnalysisRequest.request_id.desc(),
    ).limit(limit + 1)

    rows = (await db.execute(stmt)).all()
    return [
        (
            row[0],
            str(row[1]) if row[1] is not None else None,
            str(row[2]) if row[2] is not None else None,
        )
        for row in rows
    ]


_REFUNDABLE_ML_CODES: frozenset[str] = frozenset(
    {
        ErrorCode.ML_UNAVAILABLE.value,
        ErrorCode.ML_TIMEOUT.value,
        ErrorCode.ML_INVALID_RESPONSE.value,
        ErrorCode.ML_CONTRACT_ERROR.value,
        ErrorCode.DATASET_VERSION_UNAVAILABLE.value,
        ErrorCode.ML_DATASET_ERROR.value,
        ErrorCode.INTERNAL_ERROR.value,
    }
)

_CLAIM_NEXT_JOB_SQL = text(
    """
    WITH next_job AS (
        SELECT request_id
        FROM public.analysis_requests
        WHERE cancelled_at IS NULL
          AND (
              status = 'pending'
              OR (
                  status = 'running'
                  AND lease_until IS NOT NULL
                  AND lease_until < :now
                  AND attempts < :max_attempts
              )
          )
        ORDER BY created_at ASC, request_id ASC
        FOR UPDATE SKIP LOCKED
        LIMIT 1
    )
    UPDATE public.analysis_requests AS ar
    SET
        status = 'running',
        lease_until = :lease_until,
        heartbeat_at = :now,
        attempts = ar.attempts + 1
    FROM next_job
    WHERE ar.request_id = next_job.request_id
    RETURNING ar.request_id
    """
)


@dataclass(frozen=True, slots=True)
class WorkerFinalizeOutcome:
    """Outcome summary returned after committing worker terminal state transitions."""

    outcome: Literal["completed", "failed", "cancelled", "vanished", "skipped"]
    analysis_id: str | None = None
    refunded_quarters: int = 0
    guest_token_hash: str | None = None
    final_status: str | None = None
    final_error_code: str | None = None


def _ensure_utc_dt(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


def _is_analysis_id_unique_violation(exc: IntegrityError) -> bool:
    orig = getattr(exc, "orig", None)
    constraint_name = str(
        getattr(orig, "constraint_name", None)
        or getattr(getattr(orig, "__cause__", None), "constraint_name", None)
        or ""
    ).lower()
    if "analysis_id" in constraint_name and "request_id" not in constraint_name:
        return True
    err_str = str(exc).lower()
    return "analysis_id" in err_str and "request_id" not in err_str


async def _lookup_guest_token_hash_for_request(
    db: AsyncSession,
    *,
    request_id: str,
) -> str | None:
    stmt = (
        select(Farm.guest_session_token)
        .select_from(AnalysisRequest)
        .join(Farm, Farm.id == AnalysisRequest.farm_id)
        .where(AnalysisRequest.request_id == request_id)
    )
    tok = (await db.execute(stmt)).scalar_one_or_none()
    return str(tok) if tok is not None else None


async def _lock_guest_and_request(
    db: AsyncSession,
    *,
    request_id: str,
    lock_guest_row: bool,
) -> tuple[AnalysisRequest | None, str | None]:
    if lock_guest_row:
        initial_guest_tok = await _lookup_guest_token_hash_for_request(
            db,
            request_id=request_id,
        )
        if initial_guest_tok is not None:
            await db.execute(
                select(GuestSession.guest_token)
                .where(GuestSession.guest_token == initial_guest_tok)
                .with_for_update()
            )

    req_stmt = (
        select(AnalysisRequest)
        .where(AnalysisRequest.request_id == request_id)
        .with_for_update()
    )
    req = (await db.execute(req_stmt)).scalar_one_or_none()
    if req is None:
        return None, None
    current_guest_tok = await _lookup_guest_token_hash_for_request(
        db,
        request_id=request_id,
    )
    return req, current_guest_tok


async def claim_next_analysis_job(
    db: AsyncSession,
    *,
    now: datetime,
    lease_seconds: int,
    max_attempts: int,
) -> str | None:
    """Atomically claim oldest pending or reclaimable stale job via `FOR UPDATE SKIP LOCKED`."""
    current_now = _ensure_utc_dt(now)
    lease_until = current_now + timedelta(seconds=lease_seconds)
    result = await db.execute(
        _CLAIM_NEXT_JOB_SQL,
        {
            "now": current_now,
            "lease_until": lease_until,
            "max_attempts": max_attempts,
        },
    )
    claimed_id = result.scalar_one_or_none()
    return str(claimed_id) if claimed_id is not None else None


async def heartbeat_and_check_cancel(
    db: AsyncSession,
    *,
    request_id: str,
    now: datetime,
    lease_seconds: int,
) -> tuple[bool, datetime | None]:
    """Extend active lease + heartbeat timestamp and return `(exists_running, cancelled_at)`."""
    current_now = _ensure_utc_dt(now)
    lease_until = current_now + timedelta(seconds=lease_seconds)
    stmt = (
        update(AnalysisRequest)
        .where(
            AnalysisRequest.request_id == request_id,
            AnalysisRequest.status == "running",
        )
        .values(lease_until=lease_until, heartbeat_at=current_now)
        .returning(AnalysisRequest.cancelled_at)
    )
    row = (await db.execute(stmt)).one_or_none()
    if row is None:
        return False, None
    return True, row[0]


async def get_job_dispatch_row(
    db: AsyncSession,
    *,
    request_id: str,
) -> tuple[AnalysisRequest, str | None] | None:
    """Load claimed `AnalysisRequest` paired with optional owning guest token hash."""
    stmt = (
        select(AnalysisRequest, Farm.guest_session_token)
        .join(Farm, Farm.id == AnalysisRequest.farm_id)
        .where(AnalysisRequest.request_id == request_id)
    )
    row = (await db.execute(stmt)).one_or_none()
    if row is None:
        return None
    return row[0], str(row[1]) if row[1] is not None else None


async def lock_and_mark_dispatched(
    db: AsyncSession,
    *,
    request_id: str,
    now: datetime,
) -> tuple[Literal["proceed", "cancelled", "abort"], int, str | None]:
    """Lock `analysis_requests` before ML dispatch, enforcing `cancelled_at IS NULL`."""
    current_now = _ensure_utc_dt(now)
    stmt = (
        select(AnalysisRequest)
        .where(AnalysisRequest.request_id == request_id)
        .with_for_update()
    )
    req = (await db.execute(stmt)).scalar_one_or_none()
    if req is None:
        return "abort", 0, None

    guest_token_hash = await _lookup_guest_token_hash_for_request(
        db,
        request_id=request_id,
    )
    if req.cancelled_at is not None:
        if req.status == "running":
            req.status = "cancelled"
            refunded = int(req.quota_units) if (req.sent_at is None and req.quota_units > 0) else 0
            if refunded > 0:
                req.quota_units = 0
            return "cancelled", refunded, guest_token_hash
        return "cancelled", 0, guest_token_hash

    if req.status != "running":
        return "abort", 0, guest_token_hash

    if req.sent_at is None:
        req.sent_at = current_now
    return "proceed", 0, guest_token_hash


async def count_guest_ml_refunds(
    db: AsyncSession,
    *,
    guest_token_hash: str,
) -> int:
    """Count ML-error refunds already granted to a guest session (`IMPL-011`)."""
    stmt = (
        select(func.count(AnalysisRequest.request_id))
        .select_from(AnalysisRequest)
        .join(Farm, Farm.id == AnalysisRequest.farm_id)
        .where(
            Farm.guest_session_token == guest_token_hash,
            AnalysisRequest.status == "failed",
            AnalysisRequest.sent_at.is_not(None),
            AnalysisRequest.quota_units == 0,
        )
    )
    return int((await db.execute(stmt)).scalar_one())


async def _apply_guest_failure_refund_if_eligible(
    db: AsyncSession,
    *,
    req: AnalysisRequest,
    guest_token_hash: str | None,
    error_code_value: str,
    max_guest_ml_refunds: int,
) -> int:
    if guest_token_hash is None or req.quota_units <= 0:
        return 0
    if req.sent_at is None:
        refunded = int(req.quota_units)
        req.quota_units = 0
        return refunded
    if error_code_value not in _REFUNDABLE_ML_CODES:
        return 0
    prior_refunds = await count_guest_ml_refunds(
        db,
        guest_token_hash=guest_token_hash,
    )
    if prior_refunds < max_guest_ml_refunds:
        refunded = int(req.quota_units)
        req.quota_units = 0
        return refunded
    return 0


async def _insert_analysis_result_with_retry(
    db: AsyncSession,
    *,
    request_id: str,
    status: str,
    dataset_version_used: str,
    ml_engine_version: str,
    result_json: dict[str, Any],
    validation_passed: bool,
    validation_errors: list[dict[str, Any]] | None,
) -> str:
    max_mint_attempts = 8
    for attempt in range(max_mint_attempts):
        candidate_id = f"analysis_{secrets.token_hex(6)}"
        try:
            async with db.begin_nested():
                row = AnalysisResult(
                    analysis_id=candidate_id,
                    request_id=request_id,
                    status=status,
                    dataset_version_used=dataset_version_used,
                    ml_engine_version=ml_engine_version,
                    result_json=result_json,
                    validation_passed=validation_passed,
                    validation_errors=validation_errors,
                )
                db.add(row)
                await db.flush()
            return candidate_id
        except IntegrityError as exc:
            if _is_analysis_id_unique_violation(exc) and attempt + 1 < max_mint_attempts:
                continue
            raise
    raise RuntimeError("Exhausted attempts minting unique analysis_id")


async def finalize_worker_cancelled(
    db: AsyncSession,
    *,
    request_id: str,
    require_stale_before: datetime | None = None,
) -> WorkerFinalizeOutcome:
    """Finalize a cooperatively cancelled running request without writing `analysis_results`."""
    stmt = (
        select(AnalysisRequest)
        .where(AnalysisRequest.request_id == request_id)
        .with_for_update()
    )
    req = (await db.execute(stmt)).scalar_one_or_none()
    if req is None:
        return WorkerFinalizeOutcome(outcome="vanished")
    if req.status != "running":
        return WorkerFinalizeOutcome(outcome="skipped", final_status=req.status)
    if require_stale_before is not None and (
        req.lease_until is None or _ensure_utc_dt(req.lease_until) >= require_stale_before
    ):
        return WorkerFinalizeOutcome(outcome="skipped", final_status=req.status)

    guest_token_hash = await _lookup_guest_token_hash_for_request(
        db,
        request_id=request_id,
    )
    req.status = "cancelled"
    refunded = 0
    if req.sent_at is None and req.quota_units > 0:
        refunded = int(req.quota_units)
        req.quota_units = 0
    return WorkerFinalizeOutcome(
        outcome="cancelled",
        refunded_quarters=refunded,
        guest_token_hash=guest_token_hash,
        final_status="cancelled",
    )


async def finalize_worker_success(
    db: AsyncSession,
    *,
    request_id: str,
    result_status: str,
    dataset_version_used: str,
    ml_engine_version: str,
    result_json: dict[str, Any],
    validation_passed: bool,
    validation_errors: list[dict[str, Any]] | None,
    failure_error_code: ErrorCode | None,
    duration_ms: int,
    catalog_version_used: str | None,
    max_guest_ml_refunds: int,
    now: datetime,
) -> WorkerFinalizeOutcome:
    """Persist result under final `status=='running' AND cancelled_at IS NULL` cascade guard."""
    current_now = _ensure_utc_dt(now)
    req, guest_token_hash = await _lock_guest_and_request(
        db,
        request_id=request_id,
        lock_guest_row=not validation_passed,
    )
    if req is None:
        return WorkerFinalizeOutcome(outcome="vanished")
    if req.cancelled_at is not None:
        refunded = 0
        if req.status == "running":
            req.status = "cancelled"
            if req.sent_at is None and req.quota_units > 0:
                refunded = int(req.quota_units)
                req.quota_units = 0
        return WorkerFinalizeOutcome(
            outcome="cancelled",
            refunded_quarters=refunded,
            guest_token_hash=guest_token_hash,
            final_status=req.status,
        )
    if req.status != "running":
        return WorkerFinalizeOutcome(outcome="skipped", final_status=req.status)

    if catalog_version_used is not None and req.catalog_version != catalog_version_used:
        req.catalog_version = catalog_version_used

    analysis_id = await _insert_analysis_result_with_retry(
        db,
        request_id=request_id,
        status=result_status if validation_passed else "invalid",
        dataset_version_used=dataset_version_used,
        ml_engine_version=ml_engine_version,
        result_json=result_json,
        validation_passed=validation_passed,
        validation_errors=validation_errors if validation_errors else None,
    )
    req.received_at = current_now
    req.duration_ms = max(0, duration_ms)

    if validation_passed:
        req.status = result_status
        req.error_code = None
        return WorkerFinalizeOutcome(
            outcome="completed",
            analysis_id=analysis_id,
            refunded_quarters=0,
            guest_token_hash=guest_token_hash,
            final_status=req.status,
            final_error_code=None,
        )

    err_code = (failure_error_code or ErrorCode.ML_INVALID_RESPONSE).value
    req.status = "failed"
    req.error_code = err_code
    refunded = await _apply_guest_failure_refund_if_eligible(
        db,
        req=req,
        guest_token_hash=guest_token_hash,
        error_code_value=err_code,
        max_guest_ml_refunds=max_guest_ml_refunds,
    )
    return WorkerFinalizeOutcome(
        outcome="failed",
        analysis_id=analysis_id,
        refunded_quarters=refunded,
        guest_token_hash=guest_token_hash,
        final_status="failed",
        final_error_code=err_code,
    )


async def finalize_worker_failure(
    db: AsyncSession,
    *,
    request_id: str,
    error_code: ErrorCode,
    duration_ms: int,
    max_guest_ml_refunds: int,
    now: datetime,
    require_stale_before: datetime | None = None,
) -> WorkerFinalizeOutcome:
    """Persist terminal `failed` request and conditional guest quota refund (`IMPL-011`)."""
    del now
    req, guest_token_hash = await _lock_guest_and_request(
        db,
        request_id=request_id,
        lock_guest_row=True,
    )
    if req is None:
        return WorkerFinalizeOutcome(outcome="vanished")
    if req.status != "running":
        return WorkerFinalizeOutcome(outcome="skipped", final_status=req.status)
    if require_stale_before is not None and (
        req.lease_until is None or _ensure_utc_dt(req.lease_until) >= require_stale_before
    ):
        return WorkerFinalizeOutcome(outcome="skipped", final_status=req.status)

    if req.cancelled_at is not None:
        req.status = "cancelled"
        refunded = 0
        if req.sent_at is None and req.quota_units > 0:
            refunded = int(req.quota_units)
            req.quota_units = 0
        return WorkerFinalizeOutcome(
            outcome="cancelled",
            refunded_quarters=refunded,
            guest_token_hash=guest_token_hash,
            final_status="cancelled",
        )

    err_val = error_code.value
    req.status = "failed"
    req.error_code = err_val
    req.duration_ms = max(0, duration_ms)
    refunded = await _apply_guest_failure_refund_if_eligible(
        db,
        req=req,
        guest_token_hash=guest_token_hash,
        error_code_value=err_val,
        max_guest_ml_refunds=max_guest_ml_refunds,
    )
    return WorkerFinalizeOutcome(
        outcome="failed",
        refunded_quarters=refunded,
        guest_token_hash=guest_token_hash,
        final_status="failed",
        final_error_code=err_val,
    )


async def list_reaper_stale_candidates(
    db: AsyncSession,
    *,
    now: datetime,
    max_attempts: int,
    limit: int = 50,
) -> list[tuple[str, bool]]:
    """Return `(request_id, is_cancelled)` for expired leases past max attempts or cancelled."""
    current_now = _ensure_utc_dt(now)
    stmt = (
        select(AnalysisRequest.request_id, AnalysisRequest.cancelled_at.is_not(None))
        .where(
            AnalysisRequest.status == "running",
            AnalysisRequest.lease_until.is_not(None),
            AnalysisRequest.lease_until < current_now,
            or_(
                AnalysisRequest.cancelled_at.is_not(None),
                AnalysisRequest.attempts >= max_attempts,
            ),
        )
        .order_by(AnalysisRequest.lease_until.asc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()
    return [(str(row[0]), bool(row[1])) for row in rows]

