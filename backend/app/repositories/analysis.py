"""PostgreSQL repositories for `analysis_requests`, `analysis_results`, & `analysis_selections`."""

from __future__ import annotations

import json
import uuid
from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, delete, select, tuple_, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

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
