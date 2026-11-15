"""PostgreSQL repositories for users, refresh tokens, guest sessions, and export bundles."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import and_, case, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ErrorCode, FieldShiftError
from app.models.analysis import AnalysisRequest, AnalysisResult, AnalysisSelection
from app.models.demo import DemoLocation, GuestSession
from app.models.farm import Farm
from app.models.field import Field, FieldCropHistory
from app.models.user import RefreshToken, User


@dataclass(frozen=True, slots=True)
class ClaimedRefreshRow:
    """Row returned atomically when claiming an unused active refresh token."""

    id: int
    user_id: int
    family_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class UserExportBundle:
    """Structured database rows assembled for `GET /auth/me/export` without binary/hash data."""

    user: User
    farms: list[tuple[Farm, int]]
    fields: list[dict[str, Any]]
    crop_history_by_field_pk: dict[int, list[FieldCropHistory]]
    analysis_requests: list[dict[str, Any]]
    analysis_results: list[dict[str, Any]]
    analysis_selections: list[dict[str, Any]]


async def get_active_demo_location(
    db: AsyncSession,
    demo_location_id: int,
) -> DemoLocation | None:
    """Return active seeded DemoLocation by id."""
    stmt = select(DemoLocation).where(
        DemoLocation.id == demo_location_id,
        DemoLocation.is_active.is_(True),
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def create_guest_session(
    db: AsyncSession,
    *,
    guest_token_hash: str,
    demo_location_id: int,
    expires_at: datetime,
) -> GuestSession:
    """Insert a new hashed guest session row."""
    guest = GuestSession(
        guest_token=guest_token_hash,
        demo_location_id=demo_location_id,
        expires_at=expires_at,
    )
    db.add(guest)
    await db.flush()
    return guest


async def get_active_guest_session(
    db: AsyncSession,
    *,
    guest_token_hash: str,
    now: datetime,
    for_update: bool = False,
) -> GuestSession | None:
    """Return non-expired GuestSession by hashed token."""
    stmt = select(GuestSession).where(
        GuestSession.guest_token == guest_token_hash,
        GuestSession.expires_at > now,
    )
    if for_update:
        stmt = stmt.with_for_update()
    return (await db.execute(stmt)).scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: int) -> User | None:
    """Fetch registered user by primary key."""
    stmt = select(User).where(User.id == user_id)
    return (await db.execute(stmt)).scalar_one_or_none()


async def get_user_by_email_lower(db: AsyncSession, normalized_email: str) -> User | None:
    """Fetch user case-insensitively matching `uq_users_email_lower`."""
    stmt = select(User).where(func.lower(User.email) == normalized_email)
    return (await db.execute(stmt)).scalar_one_or_none()


async def create_user(
    db: AsyncSession,
    *,
    email: str,
    password_hash: str,
    full_name: str,
    preferred_lang: str,
) -> User:
    """Insert user row and flush to obtain primary key and created_at."""
    user = User(
        email=email,
        password_hash=password_hash,
        full_name=full_name,
        preferred_lang=preferred_lang,
    )
    db.add(user)
    await db.flush()
    return user


async def create_refresh_token(
    db: AsyncSession,
    *,
    user_id: int,
    family_id: uuid.UUID,
    token_hash: str,
    expires_at: datetime,
) -> RefreshToken:
    """Insert hashed refresh token belonging to a login device family."""
    row = RefreshToken(
        user_id=user_id,
        family_id=family_id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db.add(row)
    await db.flush()
    return row


async def atomic_claim_refresh_token(
    db: AsyncSession,
    *,
    token_hash: str,
    now: datetime,
) -> ClaimedRefreshRow | None:
    """Atomically mark an unused, unrevoked, unexpired refresh token as used."""
    stmt = (
        update(RefreshToken)
        .where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.used_at.is_(None),
            RefreshToken.revoked_at.is_(None),
            RefreshToken.expires_at > now,
        )
        .values(used_at=now)
        .returning(RefreshToken.id, RefreshToken.user_id, RefreshToken.family_id)
    )
    row = (await db.execute(stmt)).first()
    if row is None:
        return None
    return ClaimedRefreshRow(
        id=int(row.id),
        user_id=int(row.user_id),
        family_id=uuid.UUID(str(row.family_id)),
    )


async def get_refresh_token_by_hash(
    db: AsyncSession,
    *,
    token_hash: str,
) -> RefreshToken | None:
    """Look up refresh token metadata by SHA-256 digest."""
    stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    return (await db.execute(stmt)).scalar_one_or_none()


async def revoke_refresh_family(
    db: AsyncSession,
    *,
    family_id: uuid.UUID,
    now: datetime,
    user_id: int | None = None,
) -> int:
    """Revoke all unrevoked tokens within `family_id` (optionally scoped to `user_id`)."""
    conditions = [
        RefreshToken.family_id == family_id,
        RefreshToken.revoked_at.is_(None),
    ]
    if user_id is not None:
        conditions.append(RefreshToken.user_id == user_id)

    stmt = update(RefreshToken).where(*conditions).values(revoked_at=now).returning(RefreshToken.id)
    rows: Sequence[Any] = (await db.execute(stmt)).all()
    return len(rows)


async def hard_delete_user(db: AsyncSession, *, user_id: int) -> bool:
    """Hard-delete a user row, triggering PostgreSQL ON DELETE CASCADE purge."""
    stmt = delete(User).where(User.id == user_id).returning(User.id)
    deleted_id = (await db.execute(stmt)).scalar_one_or_none()
    return deleted_id is not None


async def claim_guest_farms_and_delete_session(
    db: AsyncSession,
    *,
    user_id: int,
    guest_token_hash: str,
    now: datetime,
) -> int:
    """Lock guest session FOR UPDATE, reassign farms before deleting session (`IMPL-021`)."""
    guest = await get_active_guest_session(
        db,
        guest_token_hash=guest_token_hash,
        now=now,
        for_update=True,
    )
    if guest is None:
        raise FieldShiftError(
            ErrorCode.UNAUTHORIZED,
            "Invalid or expired guest session.",
        )

    reassign_stmt = (
        update(Farm)
        .where(Farm.guest_session_token == guest_token_hash)
        .values(user_id=user_id, guest_session_token=None)
        .returning(Farm.id)
    )
    claimed_ids = (await db.execute(reassign_stmt)).all()

    await db.execute(delete(GuestSession).where(GuestSession.guest_token == guest_token_hash))
    return len(claimed_ids)


async def load_user_export_bundle(
    db: AsyncSession,
    *,
    user_id: int,
) -> UserExportBundle | None:
    """Load all owned entities for `GET /auth/me/export` without loading `input_snapshot_gz`."""
    user = await get_user_by_id(db, user_id)
    if user is None:
        return None

    farm_stmt = (
        select(Farm, func.count(Field.id).label("field_count"))
        .outerjoin(Field, Field.farm_id == Farm.id)
        .where(Farm.user_id == user_id)
        .group_by(Farm.id)
        .order_by(Farm.id.asc())
    )
    farm_rows = [(row[0], int(row[1])) for row in (await db.execute(farm_stmt)).all()]
    farm_ids = [farm.id for farm, _ in farm_rows]

    if not farm_ids:
        return UserExportBundle(
            user=user,
            farms=[],
            fields=[],
            crop_history_by_field_pk={},
            analysis_requests=[],
            analysis_results=[],
            analysis_selections=[],
        )

    field_stmt = (
        select(
            Field.id.label("pk"),
            Field.farm_id,
            Field.external_field_id,
            Field.field_name,
            Field.is_unverified_demo_parcel,
            func.ST_Y(Field.geom_point).label("latitude"),
            func.ST_X(Field.geom_point).label("longitude"),
            func.ST_AsGeoJSON(Field.geom_polygon).label("boundary_geojson"),
            Field.area_hectares,
            Field.elevation_m,
            Field.soil_type,
            Field.soil_source,
            Field.soil_ph,
            Field.organic_matter_percent,
            Field.soil_test_date,
            Field.water_availability,
            Field.water_source,
            Field.water_source_other,
            Field.irrigation_system,
            case(
                (DemoLocation.id.is_(None), True),
                else_=func.ST_Covers(DemoLocation.boundary, Field.geom_point),
            ).label("in_guelma_boundary"),
        )
        .outerjoin(
            DemoLocation,
            and_(DemoLocation.code == "guelma", DemoLocation.is_active.is_(True)),
        )
        .where(Field.farm_id.in_(farm_ids))
        .order_by(Field.farm_id.asc(), Field.id.asc())
    )
    field_rows = [dict(row) for row in (await db.execute(field_stmt)).mappings().all()]
    field_pks = [int(row["pk"]) for row in field_rows]

    history_by_field: dict[int, list[FieldCropHistory]] = {}
    if field_pks:
        hist_stmt = (
            select(FieldCropHistory)
            .where(FieldCropHistory.field_id.in_(field_pks))
            .order_by(
                FieldCropHistory.field_id.asc(),
                FieldCropHistory.year.desc(),
                FieldCropHistory.season.asc(),
            )
        )
        for item in (await db.execute(hist_stmt)).scalars().all():
            history_by_field.setdefault(item.field_id, []).append(item)

    req_stmt = (
        select(
            AnalysisRequest.request_id,
            AnalysisRequest.farm_id,
            AnalysisRequest.idempotency_key,
            AnalysisRequest.parent_request_id,
            AnalysisRequest.schema_version,
            AnalysisRequest.catalog_version,
            AnalysisRequest.dataset_version,
            AnalysisRequest.language,
            AnalysisRequest.quota_units,
            AnalysisRequest.input_hash,
            AnalysisRequest.full_input_hash,
            AnalysisRequest.warnings,
            AnalysisRequest.status,
            AnalysisRequest.error_code,
            AnalysisRequest.attempts,
            AnalysisRequest.cancelled_at,
            AnalysisRequest.sent_at,
            AnalysisRequest.received_at,
            AnalysisRequest.duration_ms,
            AnalysisRequest.created_at,
        )
        .where(AnalysisRequest.farm_id.in_(farm_ids))
        .order_by(AnalysisRequest.created_at.asc(), AnalysisRequest.request_id.asc())
    )
    req_rows = [dict(row) for row in (await db.execute(req_stmt)).mappings().all()]

    res_stmt = (
        select(
            AnalysisResult.analysis_id,
            AnalysisResult.request_id,
            AnalysisResult.status,
            AnalysisResult.dataset_version_used,
            AnalysisResult.ml_engine_version,
            AnalysisResult.result_json,
            AnalysisResult.validation_passed,
            AnalysisResult.validation_errors,
            AnalysisResult.created_at,
        )
        .join(AnalysisRequest, AnalysisRequest.request_id == AnalysisResult.request_id)
        .where(AnalysisRequest.farm_id.in_(farm_ids))
        .order_by(AnalysisResult.created_at.asc(), AnalysisResult.analysis_id.asc())
    )
    res_rows = [dict(row) for row in (await db.execute(res_stmt)).mappings().all()]

    sel_stmt = (
        select(
            AnalysisSelection.analysis_id,
            AnalysisSelection.field_id,
            AnalysisSelection.strategy_id,
            AnalysisSelection.selection_status,
            AnalysisSelection.updated_at,
        )
        .join(AnalysisResult, AnalysisResult.analysis_id == AnalysisSelection.analysis_id)
        .join(AnalysisRequest, AnalysisRequest.request_id == AnalysisResult.request_id)
        .where(AnalysisRequest.farm_id.in_(farm_ids))
        .order_by(
            AnalysisSelection.analysis_id.asc(),
            AnalysisSelection.field_id.asc(),
            AnalysisSelection.strategy_id.asc(),
        )
    )
    sel_rows = [dict(row) for row in (await db.execute(sel_stmt)).mappings().all()]

    return UserExportBundle(
        user=user,
        farms=farm_rows,
        fields=field_rows,
        crop_history_by_field_pk=history_by_field,
        analysis_requests=req_rows,
        analysis_results=res_rows,
        analysis_selections=sel_rows,
    )
