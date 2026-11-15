"""Demo location listing, GeoJSON boundaries, and guest session inspection/deletion."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import ErrorCode, FieldShiftError
from app.core.pagination import PaginationParams, decode_cursor, slice_keyset_page
from app.core.rate_limit import AsyncRedisLike, clear_guest_quota_cache
from app.repositories import demo as demo_repo
from app.schemas.demo import (
    BoundaryFeature,
    DemoLocationPage,
    DemoLocationSummary,
    GuestLimits,
    GuestSessionInfo,
    GuestUsage,
)


def _decode_location_cursor(cursor: str | None) -> int | None:
    if cursor is None:
        return None
    payload = decode_cursor(cursor, required_keys=("id",))
    raw_id = payload["id"]
    if isinstance(raw_id, bool) or not isinstance(raw_id, int) or raw_id < 1:
        raise FieldShiftError(
            ErrorCode.INVALID_INPUT,
            "Invalid pagination cursor.",
            details=[{"field": "cursor", "reason": "invalid_cursor_id"}],
        )
    return int(raw_id)


async def list_demo_locations(
    db: AsyncSession,
    *,
    pagination: PaginationParams,
) -> DemoLocationPage:
    """List active demo zones ordered by id using opaque Base64 keyset cursor pagination."""
    after_id = _decode_location_cursor(pagination.cursor)
    rows = await demo_repo.list_active_demo_locations(
        db,
        limit=pagination.limit,
        after_id=after_id,
    )
    sliced_rows, next_cursor, has_more = slice_keyset_page(
        rows,
        limit=pagination.limit,
        cursor_key_fn=lambda loc: {"id": loc.id},
    )
    return DemoLocationPage(
        items=[
            DemoLocationSummary(
                id=loc.id,
                code=loc.code,
                name=loc.name,
                country=loc.country,
                region=loc.region,
            )
            for loc in sliced_rows
        ],
        next_cursor=next_cursor,
        has_more=has_more,
    )


async def get_demo_location_boundary(
    db: AsyncSession,
    *,
    demo_location_id: int,
) -> BoundaryFeature:
    """Return GeoJSON Feature (`MultiPolygon` `[lon, lat]` and `bbox`) for an active zone."""
    row = await demo_repo.get_active_demo_location_boundary(
        db,
        demo_location_id=demo_location_id,
    )
    if row is None:
        raise FieldShiftError(
            ErrorCode.NOT_FOUND,
            "Demo location not found.",
            details=[{"demo_location_id": demo_location_id}],
        )

    return BoundaryFeature(
        type="Feature",
        properties={
            "id": row.id,
            "code": row.code,
            "name": row.name,
        },
        geometry=row.geometry,
        bbox=row.bbox,
    )


async def get_guest_session_info(
    db: AsyncSession,
    *,
    guest_token_hash: str,
    settings: Settings,
    now: datetime | None = None,
) -> GuestSessionInfo:
    """Inspect active guest session limits, canonical PostgreSQL usage, and demo location."""
    current_now = now or datetime.now(UTC)
    bundle = await demo_repo.get_guest_session_usage_bundle(
        db,
        guest_token_hash=guest_token_hash,
        now=current_now,
    )
    if bundle is None:
        raise FieldShiftError(
            ErrorCode.UNAUTHORIZED,
            "Invalid or expired guest session.",
        )

    quarters = bundle.analysis_quarters
    return GuestSessionInfo(
        demo_location=DemoLocationSummary(
            id=bundle.demo_location.id,
            code=bundle.demo_location.code,
            name=bundle.demo_location.name,
            country=bundle.demo_location.country,
            region=bundle.demo_location.region,
        ),
        created_at=bundle.guest_session.created_at,
        expires_at=bundle.guest_session.expires_at,
        limits=GuestLimits(
            max_farms=settings.GUEST_MAX_FARMS,
            max_fields_per_farm=settings.GUEST_MAX_FIELDS_PER_FARM,
            max_analyses=settings.GUEST_MAX_ANALYSES,
            max_analysis_quarters=settings.GUEST_MAX_ANALYSES * 4,
        ),
        usage=GuestUsage(
            farms=bundle.farms_count,
            fields=bundle.fields_count,
            analysis_quarters=quarters,
            analyses=quarters / 4.0,
        ),
    )


async def delete_guest_session(
    db: AsyncSession,
    redis_client: AsyncRedisLike | None,
    *,
    guest_token_hash: str,
) -> None:
    """Cascade-delete guest session in PostgreSQL and clean cached Redis quarter quota."""
    deleted = await demo_repo.delete_guest_session_by_hash(
        db,
        guest_token_hash=guest_token_hash,
    )
    if not deleted:
        await db.rollback()
        raise FieldShiftError(
            ErrorCode.UNAUTHORIZED,
            "Invalid or expired guest session.",
        )
    await db.commit()
    await clear_guest_quota_cache(
        redis_client,
        guest_token_hash=guest_token_hash,
    )
