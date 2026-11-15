"""Owner-scoped farm CRUD service with row-locked guest quotas (`IMPL-019`)."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal
from app.core.config import Settings
from app.core.errors import ErrorCode, FieldShiftError
from app.core.pagination import PaginationParams, decode_id_cursor, slice_keyset_page
from app.models.farm import Farm
from app.repositories import farm as farm_repo
from app.repositories import user as user_repo
from app.schemas.farm import FarmPage, FarmPatchRequest, FarmPublic, FarmWriteRequest

_FARM_ID_PATTERN = re.compile(r"^farm_([0-9]+)$")
_MAX_INT64 = 9_223_372_036_854_775_807


def parse_farm_id(raw_farm_id: str) -> int:
    """Parse `^farm_[0-9]+$` into a positive PostgreSQL BIGINT or raise 400/404."""
    match = _FARM_ID_PATTERN.fullmatch(raw_farm_id)
    if match is None:
        raise FieldShiftError(
            ErrorCode.INVALID_INPUT,
            "Invalid farm_id format; expected 'farm_<id>'.",
            details=[{"field": "farm_id", "reason": "invalid_format"}],
        )
    parsed = int(match.group(1))
    if parsed < 1 or parsed > _MAX_INT64:
        raise FieldShiftError(
            ErrorCode.NOT_FOUND,
            "Farm not found.",
            details=[{"farm_id": raw_farm_id}],
        )
    return parsed


def format_farm_id(farm_pk: int) -> str:
    """Format an internal farm BIGINT primary key as public `farm_<id>`."""
    return f"farm_{farm_pk}"


def to_farm_public(farm: Farm, *, field_count: int) -> FarmPublic:
    """Map `Farm` ORM row and field count to public schema."""
    return FarmPublic(
        farm_id=format_farm_id(farm.id),
        farm_name=farm.farm_name,
        country=farm.country,
        region=farm.region,
        commune=farm.commune,
        field_count=field_count,
        created_at=farm.created_at,
    )


async def list_farms(
    db: AsyncSession,
    *,
    principal: Principal,
    pagination: PaginationParams,
    country: str | None = None,
    region: str | None = None,
    search: str | None = None,
) -> FarmPage:
    """List caller-owned farms with cursor pagination and optional filters."""
    after_id = decode_id_cursor(pagination.cursor, key="id")
    rows = await farm_repo.list_farms_for_actor(
        db,
        user_id=principal.user_id,
        guest_token_hash=principal.guest_token_hash,
        limit=pagination.limit,
        after_id=after_id,
        country=country.strip() if country else None,
        region=region.strip() if region else None,
        search=search.strip() if search else None,
    )
    sliced, next_cursor, has_more = slice_keyset_page(
        rows,
        limit=pagination.limit,
        cursor_key_fn=lambda item: {"id": item.farm.id},
    )
    return FarmPage(
        items=[to_farm_public(item.farm, field_count=item.field_count) for item in sliced],
        next_cursor=next_cursor,
        has_more=has_more,
    )


async def create_farm(
    db: AsyncSession,
    *,
    principal: Principal,
    payload: FarmWriteRequest,
    settings: Settings,
    now: datetime | None = None,
) -> FarmPublic:
    """Create a farm owned by caller, enforcing row-locked guest limit (`GUEST_MAX_FARMS`)."""
    current_now = now or datetime.now(UTC)
    if principal.is_guest:
        assert principal.guest_token_hash is not None
        guest = await user_repo.get_active_guest_session(
            db,
            guest_token_hash=principal.guest_token_hash,
            now=current_now,
            for_update=True,
        )
        if guest is None:
            await db.rollback()
            raise FieldShiftError(ErrorCode.UNAUTHORIZED, "Guest session expired or revoked.")

        existing_count = await farm_repo.count_farms_for_guest(
            db,
            guest_token_hash=principal.guest_token_hash,
        )
        if existing_count >= settings.GUEST_MAX_FARMS:
            await db.rollback()
            raise FieldShiftError(
                ErrorCode.GUEST_LIMIT_REACHED,
                f"Guest sessions may create at most {settings.GUEST_MAX_FARMS} farms.",
                details=[
                    {
                        "resource": "farms",
                        "limit": settings.GUEST_MAX_FARMS,
                        "current": existing_count,
                    }
                ],
            )

    farm = await farm_repo.create_farm(
        db,
        user_id=principal.user_id,
        guest_token_hash=principal.guest_token_hash,
        farm_name=payload.farm_name,
        country=payload.country,
        region=payload.region,
        commune=payload.commune,
    )
    await db.commit()
    return to_farm_public(farm, field_count=0)


async def get_farm(
    db: AsyncSession,
    *,
    principal: Principal,
    farm_id: str,
) -> FarmPublic:
    """Fetch one caller-owned farm or raise `404 NOT_FOUND`."""
    farm_pk = parse_farm_id(farm_id)
    bundle = await farm_repo.get_owned_farm_with_count(
        db,
        farm_pk=farm_pk,
        user_id=principal.user_id,
        guest_token_hash=principal.guest_token_hash,
    )
    if bundle is None:
        raise FieldShiftError(
            ErrorCode.NOT_FOUND,
            "Farm not found.",
            details=[{"farm_id": farm_id}],
        )
    return to_farm_public(bundle.farm, field_count=bundle.field_count)


async def replace_farm(
    db: AsyncSession,
    *,
    principal: Principal,
    farm_id: str,
    payload: FarmWriteRequest,
) -> FarmPublic:
    """Replace mutable attributes on an owned farm (`PUT /farms/{farm_id}`)."""
    farm_pk = parse_farm_id(farm_id)
    farm = await farm_repo.get_owned_farm(
        db,
        farm_pk=farm_pk,
        user_id=principal.user_id,
        guest_token_hash=principal.guest_token_hash,
        for_update=True,
    )
    if farm is None:
        await db.rollback()
        raise FieldShiftError(
            ErrorCode.NOT_FOUND,
            "Farm not found.",
            details=[{"farm_id": farm_id}],
        )

    farm.farm_name = payload.farm_name
    farm.country = payload.country
    farm.region = payload.region
    farm.commune = payload.commune
    field_count = await farm_repo.count_fields_for_farm(db, farm_pk=farm_pk)
    await db.commit()
    await db.refresh(farm)
    return to_farm_public(farm, field_count=field_count)


async def patch_farm(
    db: AsyncSession,
    *,
    principal: Principal,
    farm_id: str,
    payload: FarmPatchRequest,
) -> FarmPublic:
    """Partially update an owned farm (`PATCH /farms/{farm_id}`)."""
    farm_pk = parse_farm_id(farm_id)
    farm = await farm_repo.get_owned_farm(
        db,
        farm_pk=farm_pk,
        user_id=principal.user_id,
        guest_token_hash=principal.guest_token_hash,
        for_update=True,
    )
    if farm is None:
        await db.rollback()
        raise FieldShiftError(
            ErrorCode.NOT_FOUND,
            "Farm not found.",
            details=[{"farm_id": farm_id}],
        )

    fields_set = payload.model_fields_set
    if "farm_name" in fields_set and payload.farm_name is not None:
        farm.farm_name = payload.farm_name
    if "country" in fields_set and payload.country is not None:
        farm.country = payload.country
    if "region" in fields_set and payload.region is not None:
        farm.region = payload.region
    if "commune" in fields_set:
        farm.commune = payload.commune

    field_count = await farm_repo.count_fields_for_farm(db, farm_pk=farm_pk)
    await db.commit()
    await db.refresh(farm)
    return to_farm_public(farm, field_count=field_count)


async def delete_farm(
    db: AsyncSession,
    *,
    principal: Principal,
    farm_id: str,
) -> None:
    """Hard-delete an owned farm and cascade-delete its fields, history, and analyses."""
    farm_pk = parse_farm_id(farm_id)
    deleted = await farm_repo.delete_owned_farm(
        db,
        farm_pk=farm_pk,
        user_id=principal.user_id,
        guest_token_hash=principal.guest_token_hash,
    )
    if not deleted:
        await db.rollback()
        raise FieldShiftError(
            ErrorCode.NOT_FOUND,
            "Farm not found.",
            details=[{"farm_id": farm_id}],
        )
    await db.commit()
