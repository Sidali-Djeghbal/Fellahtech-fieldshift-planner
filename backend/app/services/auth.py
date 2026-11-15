"""Authentication, token rotation, data portability export, and guest-claim services."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import ErrorCode, FieldShiftError
from app.core.rate_limit import AsyncRedisLike, clear_guest_quota_cache
from app.core.security import (
    create_access_token,
    dummy_verify_password_async,
    generate_guest_token,
    generate_refresh_token,
    hash_password_async,
    hash_token,
    verify_password_async,
)
from app.models.user import User
from app.repositories import user as user_repo
from app.schemas.auth import (
    ClaimGuestResponse,
    GuestSessionStartResponse,
    LoginRequest,
    RegisterRequest,
    RegisterResponse,
    TokenPairResponse,
    UserDataExport,
    UserProfile,
)
from app.schemas.common import (
    DEMO_PARCEL_UNVERIFIED_MESSAGE,
    MVP_OUTSIDE_COVERAGE_MESSAGE,
    IrrigationSystem,
    Language,
    Season,
    SoilSource,
    SoilType,
    WarningCode,
    WarningNotice,
    WaterAvailability,
    WaterSource,
)
from app.schemas.demo import DemoLocationSummary
from app.schemas.farm import FarmPublic
from app.schemas.field import (
    CropHistoryWriteItem,
    FieldDetailPublic,
    FieldLocationPublic,
    FieldSoilPublic,
    FieldWaterPublic,
)


def _to_user_profile(user: User) -> UserProfile:
    return UserProfile(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        preferred_lang=Language(user.preferred_lang),
        created_at=user.created_at,
    )


async def _issue_token_family(
    db: AsyncSession,
    *,
    user_id: int,
    settings: Settings,
    now: datetime,
    family_id: uuid.UUID | None = None,
) -> TokenPairResponse:
    target_family = family_id or uuid.uuid4()
    raw_refresh, refresh_hash = generate_refresh_token()
    refresh_expires = now + timedelta(seconds=settings.JWT_REFRESH_EXPIRES_SECONDS)
    await user_repo.create_refresh_token(
        db,
        user_id=user_id,
        family_id=target_family,
        token_hash=refresh_hash,
        expires_at=refresh_expires,
    )
    access_token = create_access_token(
        user_id=user_id,
        family_id=target_family,
        settings=settings,
        now=now,
    )
    return TokenPairResponse(
        access_token=access_token,
        refresh_token=raw_refresh,
        token_type="bearer",
        expires_in=settings.JWT_ACCESS_EXPIRES_SECONDS,
    )


async def start_guest_session(
    db: AsyncSession,
    *,
    demo_location_id: int,
    settings: Settings,
    now: datetime | None = None,
) -> GuestSessionStartResponse:
    """Create a 7-day hashed guest session bound to an active demo boundary (`IMPL-012/023`)."""
    demo_loc = await user_repo.get_active_demo_location(db, demo_location_id)
    if demo_loc is None:
        raise FieldShiftError(ErrorCode.NOT_FOUND, "Demo location not found.")

    current_now = now or datetime.now(UTC)
    expires_at = current_now + timedelta(days=settings.GUEST_SESSION_DAYS)
    raw_token, token_hash = generate_guest_token()

    await user_repo.create_guest_session(
        db,
        guest_token_hash=token_hash,
        demo_location_id=demo_loc.id,
        expires_at=expires_at,
    )
    await db.commit()

    return GuestSessionStartResponse(
        guest_token=raw_token,
        expires_at=expires_at,
        demo_location=DemoLocationSummary(
            id=demo_loc.id,
            code=demo_loc.code,
            name=demo_loc.name,
            country=demo_loc.country,
            region=demo_loc.region,
        ),
    )


async def register_user(
    db: AsyncSession,
    *,
    payload: RegisterRequest,
    settings: Settings,
    now: datetime | None = None,
) -> RegisterResponse:
    """Register a user with Argon2id password hash and mint initial refresh family."""
    existing = await user_repo.get_user_by_email_lower(db, payload.email)
    if existing is not None:
        raise FieldShiftError(ErrorCode.CONFLICT, "An account with this email already exists.")

    current_now = now or datetime.now(UTC)
    pw_hash = await hash_password_async(payload.password)

    try:
        user = await user_repo.create_user(
            db,
            email=payload.email,
            password_hash=pw_hash,
            full_name=payload.full_name,
            preferred_lang=payload.preferred_lang.value,
        )
        token_pair = await _issue_token_family(
            db,
            user_id=user.id,
            settings=settings,
            now=current_now,
        )
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise FieldShiftError(
            ErrorCode.CONFLICT,
            "An account with this email already exists.",
        ) from exc

    return RegisterResponse(
        user=_to_user_profile(user),
        access_token=token_pair.access_token,
        refresh_token=token_pair.refresh_token,
        token_type="bearer",
        expires_in=token_pair.expires_in,
    )


async def login_user(
    db: AsyncSession,
    *,
    payload: LoginRequest,
    settings: Settings,
    now: datetime | None = None,
) -> TokenPairResponse:
    """Authenticate credentials and issue an independent multi-device refresh family."""
    user = await user_repo.get_user_by_email_lower(db, payload.email)
    if user is None:
        await dummy_verify_password_async(payload.password)
        raise FieldShiftError(ErrorCode.UNAUTHORIZED, "Invalid email or password.")

    valid = await verify_password_async(user.password_hash, payload.password)
    if not valid:
        raise FieldShiftError(ErrorCode.UNAUTHORIZED, "Invalid email or password.")

    current_now = now or datetime.now(UTC)
    token_pair = await _issue_token_family(
        db,
        user_id=user.id,
        settings=settings,
        now=current_now,
    )
    await db.commit()
    return token_pair


async def refresh_tokens(
    db: AsyncSession,
    *,
    raw_refresh_token: str,
    settings: Settings,
    now: datetime | None = None,
) -> TokenPairResponse:
    """Atomically rotate refresh token; commit family revocation before 401 on replay."""
    current_now = now or datetime.now(UTC)
    token_hash = hash_token(raw_refresh_token)

    claimed = await user_repo.atomic_claim_refresh_token(
        db,
        token_hash=token_hash,
        now=current_now,
    )
    if claimed is None:
        existing = await user_repo.get_refresh_token_by_hash(db, token_hash=token_hash)
        if existing is not None and (
            existing.used_at is not None or existing.revoked_at is not None
        ):
            # Commit family revocation in its own durable tx BEFORE raising 401 (Pitfall #2).
            revoked_count = await user_repo.revoke_refresh_family(
                db,
                family_id=existing.family_id,
                now=current_now,
            )
            await db.commit()
            logger = structlog.get_logger("app.auth")
            await logger.awarning(
                "refresh_token_replay_detected",
                user_id=existing.user_id,
                family_id=str(existing.family_id),
                revoked_tokens_count=revoked_count,
            )
        raise FieldShiftError(
            ErrorCode.UNAUTHORIZED,
            "Invalid, expired, or reused refresh token.",
        )

    token_pair = await _issue_token_family(
        db,
        user_id=claimed.user_id,
        settings=settings,
        now=current_now,
        family_id=claimed.family_id,
    )
    await db.commit()
    return token_pair


async def logout_user(
    db: AsyncSession,
    *,
    user_id: int,
    token_family_id: uuid.UUID,
    raw_refresh_token: str | None,
    now: datetime | None = None,
) -> None:
    """Revoke target refresh family (body refresh_token if supplied, else JWT `fid` claim)."""
    current_now = now or datetime.now(UTC)
    target_family_id = token_family_id

    if raw_refresh_token is not None:
        cleaned = raw_refresh_token.strip()
        if not cleaned:
            raise FieldShiftError(ErrorCode.UNAUTHORIZED, "Invalid refresh token.")
        row = await user_repo.get_refresh_token_by_hash(db, token_hash=hash_token(cleaned))
        if row is None or row.user_id != user_id:
            raise FieldShiftError(ErrorCode.UNAUTHORIZED, "Invalid refresh token.")
        target_family_id = row.family_id

    await user_repo.revoke_refresh_family(
        db,
        family_id=target_family_id,
        user_id=user_id,
        now=current_now,
    )
    await db.commit()


async def get_me_profile(db: AsyncSession, *, user_id: int) -> UserProfile:
    """Fetch authenticated user profile (`DI-16` integer `id`)."""
    user = await user_repo.get_user_by_id(db, user_id)
    if user is None:
        raise FieldShiftError(ErrorCode.UNAUTHORIZED, "User account no longer exists.")
    return _to_user_profile(user)


async def delete_me_account(db: AsyncSession, *, user_id: int) -> None:
    """Hard-delete authenticated user and cascade-purge all personal data (`Pitfall #13`)."""
    deleted = await user_repo.hard_delete_user(db, user_id=user_id)
    if not deleted:
        await db.rollback()
        raise FieldShiftError(ErrorCode.UNAUTHORIZED, "User account no longer exists.")
    await db.commit()


def _format_iso_opt(value: datetime | None) -> str | None:
    return value.astimezone(UTC).isoformat() if value is not None else None


def _build_export_field_detail(
    row: dict[str, Any],
    history_items: list[Any],
) -> FieldDetailPublic:
    boundary_raw = row["boundary_geojson"]
    boundary = json.loads(boundary_raw) if isinstance(boundary_raw, str) else None

    warnings: list[WarningNotice] = []
    if bool(row["is_unverified_demo_parcel"]):
        warnings.append(
            WarningNotice(
                code=WarningCode.DEMO_PARCEL_UNVERIFIED,
                message=DEMO_PARCEL_UNVERIFIED_MESSAGE,
            )
        )
    if not bool(row["in_guelma_boundary"]):
        warnings.append(
            WarningNotice(
                code=WarningCode.MVP_OUTSIDE_COVERAGE,
                message=MVP_OUTSIDE_COVERAGE_MESSAGE,
            )
        )

    return FieldDetailPublic(
        farm_id=f"farm_{int(row['farm_id'])}",
        field_id=str(row["external_field_id"]),
        field_name=str(row["field_name"]),
        is_unverified_demo_parcel=bool(row["is_unverified_demo_parcel"]),
        location=FieldLocationPublic(
            latitude=float(row["latitude"]),
            longitude=float(row["longitude"]),
            boundary=boundary,
        ),
        area_hectares=float(row["area_hectares"]),
        elevation_m=float(row["elevation_m"]) if row["elevation_m"] is not None else None,
        soil=FieldSoilPublic(
            soil_type=SoilType(str(row["soil_type"])),
            source=SoilSource(str(row["soil_source"])),
            soil_ph=float(row["soil_ph"]) if row["soil_ph"] is not None else None,
            organic_matter_percent=(
                float(row["organic_matter_percent"])
                if row["organic_matter_percent"] is not None
                else None
            ),
            soil_test_date=row["soil_test_date"],
        ),
        water=FieldWaterPublic(
            availability=WaterAvailability(str(row["water_availability"])),
            source=WaterSource(str(row["water_source"])),
            source_other=row["water_source_other"],
            irrigation_system=IrrigationSystem(str(row["irrigation_system"])),
        ),
        crop_history=[
            CropHistoryWriteItem(
                season=Season(item.season),
                year=item.year,
                planting_month=item.planting_month,
                crop_id=item.crop_id,
                crop_name_raw=item.crop_name_raw,
                yield_tons_per_hectare=(
                    float(item.yield_tons_per_hectare)
                    if item.yield_tons_per_hectare is not None
                    else None
                ),
                notes=item.notes,
            )
            for item in history_items
        ],
        warnings=warnings,
    )


async def export_me_data(
    db: AsyncSession,
    *,
    user_id: int,
    now: datetime | None = None,
) -> UserDataExport:
    """Assemble portability export strictly omitting hashes, refresh tokens, and gzip blobs."""
    bundle = await user_repo.load_user_export_bundle(db, user_id=user_id)
    if bundle is None:
        raise FieldShiftError(ErrorCode.UNAUTHORIZED, "User account no longer exists.")

    farms_public = [
        FarmPublic(
            farm_id=f"farm_{farm.id}",
            farm_name=farm.farm_name,
            country=farm.country,
            region=farm.region,
            commune=farm.commune,
            field_count=field_count,
            created_at=farm.created_at,
        )
        for farm, field_count in bundle.farms
    ]

    fields_public = [
        _build_export_field_detail(
            row,
            bundle.crop_history_by_field_pk.get(int(row["pk"]), []),
        )
        for row in bundle.fields
    ]

    safe_requests: list[dict[str, Any]] = [
        {
            "request_id": row["request_id"],
            "farm_id": f"farm_{int(row['farm_id'])}",
            "idempotency_key": row["idempotency_key"],
            "parent_request_id": row["parent_request_id"],
            "schema_version": row["schema_version"],
            "catalog_version": row["catalog_version"],
            "dataset_version": row["dataset_version"],
            "language": row["language"],
            "quota_units": int(row["quota_units"]),
            "input_hash": row["input_hash"],
            "full_input_hash": row["full_input_hash"],
            "warnings": row["warnings"],
            "status": row["status"],
            "error_code": row["error_code"],
            "attempts": int(row["attempts"]),
            "cancelled_at": _format_iso_opt(row["cancelled_at"]),
            "sent_at": _format_iso_opt(row["sent_at"]),
            "received_at": _format_iso_opt(row["received_at"]),
            "duration_ms": row["duration_ms"],
            "created_at": _format_iso_opt(row["created_at"]),
        }
        for row in bundle.analysis_requests
    ]

    safe_results: list[dict[str, Any]] = [
        {
            "analysis_id": row["analysis_id"],
            "request_id": row["request_id"],
            "status": row["status"],
            "dataset_version_used": row["dataset_version_used"],
            "ml_engine_version": row["ml_engine_version"],
            "result_json": row["result_json"],
            "validation_passed": bool(row["validation_passed"]),
            "validation_errors": row["validation_errors"],
            "created_at": _format_iso_opt(row["created_at"]),
        }
        for row in bundle.analysis_results
    ]

    safe_selections: list[dict[str, Any]] = [
        {
            "analysis_id": row["analysis_id"],
            "field_id": row["field_id"],
            "strategy_id": row["strategy_id"],
            "selection_status": row["selection_status"],
            "updated_at": _format_iso_opt(row["updated_at"]),
        }
        for row in bundle.analysis_selections
    ]

    return UserDataExport(
        exported_at=now or datetime.now(UTC),
        user=_to_user_profile(bundle.user),
        farms=farms_public,
        fields=fields_public,
        analysis_requests=safe_requests,
        analysis_results=safe_results,
        analysis_selections=safe_selections,
    )


async def claim_guest_session(
    db: AsyncSession,
    redis_client: AsyncRedisLike | None,
    *,
    user_id: int,
    guest_token_hash: str,
    now: datetime | None = None,
) -> ClaimGuestResponse:
    """Atomically transfer guest farms to authenticated user before deleting guest session."""
    current_now = now or datetime.now(UTC)
    claimed_count = await user_repo.claim_guest_farms_and_delete_session(
        db,
        user_id=user_id,
        guest_token_hash=guest_token_hash,
        now=current_now,
    )
    await db.commit()
    await clear_guest_quota_cache(redis_client, guest_token_hash=guest_token_hash)
    return ClaimGuestResponse(claimed_farms_count=claimed_count)
