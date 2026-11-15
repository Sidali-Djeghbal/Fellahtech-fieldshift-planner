"""PostgreSQL/PostGIS repositories for demo locations, boundaries, and guest usage."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis import AnalysisRequest
from app.models.demo import DemoLocation, GuestSession
from app.models.farm import Farm
from app.models.field import Field


@dataclass(frozen=True, slots=True)
class DemoBoundaryRow:
    """Active demo location metadata plus GeoJSON geometry and `[xmin, ymin, xmax, ymax]` bbox."""

    id: int
    code: str
    name: str
    geometry: dict[str, Any]
    bbox: list[float]


@dataclass(frozen=True, slots=True)
class GuestSessionUsageBundle:
    """Loaded active guest session, bound demo zone, and canonical PostgreSQL resource counts."""

    guest_session: GuestSession
    demo_location: DemoLocation
    farms_count: int
    fields_count: int
    analysis_quarters: int


async def list_active_demo_locations(
    db: AsyncSession,
    *,
    limit: int,
    after_id: int | None,
) -> list[DemoLocation]:
    """Fetch `limit + 1` active demo locations ordered by primary key for cursor pagination."""
    stmt = select(DemoLocation).where(DemoLocation.is_active.is_(True))
    if after_id is not None:
        stmt = stmt.where(DemoLocation.id > after_id)

    stmt = stmt.order_by(DemoLocation.id.asc()).limit(limit + 1)
    return list((await db.execute(stmt)).scalars().all())


async def get_active_demo_location_boundary(
    db: AsyncSession,
    *,
    demo_location_id: int,
) -> DemoBoundaryRow | None:
    """Return parsed GeoJSON MultiPolygon geometry (`[lon, lat]`) and bbox for an active zone."""
    stmt = select(
        DemoLocation.id,
        DemoLocation.code,
        DemoLocation.name,
        func.ST_AsGeoJSON(DemoLocation.boundary).label("boundary_geojson"),
        func.ST_XMin(DemoLocation.boundary).label("xmin"),
        func.ST_YMin(DemoLocation.boundary).label("ymin"),
        func.ST_XMax(DemoLocation.boundary).label("xmax"),
        func.ST_YMax(DemoLocation.boundary).label("ymax"),
    ).where(
        DemoLocation.id == demo_location_id,
        DemoLocation.is_active.is_(True),
    )
    row = (await db.execute(stmt)).mappings().one_or_none()
    if row is None:
        return None

    geometry = json.loads(str(row["boundary_geojson"]))
    return DemoBoundaryRow(
        id=int(row["id"]),
        code=str(row["code"]),
        name=str(row["name"]),
        geometry=geometry,
        bbox=[
            float(row["xmin"]),
            float(row["ymin"]),
            float(row["xmax"]),
            float(row["ymax"]),
        ],
    )


async def get_guest_session_usage_bundle(
    db: AsyncSession,
    *,
    guest_token_hash: str,
    now: datetime,
) -> GuestSessionUsageBundle | None:
    """Load guest session, demo zone, and canonical PostgreSQL usage counters without join bloat."""
    session_stmt = (
        select(GuestSession, DemoLocation)
        .join(DemoLocation, DemoLocation.id == GuestSession.demo_location_id)
        .where(
            GuestSession.guest_token == guest_token_hash,
            GuestSession.expires_at > now,
        )
    )
    session_row = (await db.execute(session_stmt)).one_or_none()
    if session_row is None:
        return None

    guest_session, demo_location = session_row
    farms_subq = (
        select(func.count(Farm.id))
        .where(Farm.guest_session_token == guest_token_hash)
        .scalar_subquery()
    )
    fields_subq = (
        select(func.count(Field.id))
        .select_from(Field)
        .join(Farm, Farm.id == Field.farm_id)
        .where(Farm.guest_session_token == guest_token_hash)
        .scalar_subquery()
    )
    quarters_subq = (
        select(func.coalesce(func.sum(AnalysisRequest.quota_units), 0))
        .select_from(AnalysisRequest)
        .join(Farm, Farm.id == AnalysisRequest.farm_id)
        .where(Farm.guest_session_token == guest_token_hash)
        .scalar_subquery()
    )
    counts_stmt = select(
        farms_subq.label("farms_count"),
        fields_subq.label("fields_count"),
        quarters_subq.label("analysis_quarters"),
    )
    counts_row = (await db.execute(counts_stmt)).mappings().one()
    return GuestSessionUsageBundle(
        guest_session=guest_session,
        demo_location=demo_location,
        farms_count=int(counts_row["farms_count"]),
        fields_count=int(counts_row["fields_count"]),
        analysis_quarters=int(counts_row["analysis_quarters"]),
    )


async def delete_guest_session_by_hash(
    db: AsyncSession,
    *,
    guest_token_hash: str,
) -> bool:
    """Delete guest session row, cascading farms, fields, crop history, and analyses."""
    stmt = (
        delete(GuestSession)
        .where(GuestSession.guest_token == guest_token_hash)
        .returning(GuestSession.guest_token)
    )
    deleted = (await db.execute(stmt)).scalar_one_or_none()
    return deleted is not None


async def is_point_covered_by_demo_location(
    db: AsyncSession,
    *,
    latitude: float,
    longitude: float,
    demo_location_id: int | None = None,
    location_code: str = "guelma",
) -> bool:
    """Evaluate `ST_Covers(demo_locations.boundary, ST_SetSRID(ST_MakePoint(lon, lat), 4326))`."""
    # PostGIS ST_MakePoint expects (longitude, latitude) axis order (X, Y) under SRID 4326.
    point = func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326)
    stmt = select(func.ST_Covers(DemoLocation.boundary, point)).where(
        DemoLocation.is_active.is_(True)
    )
    if demo_location_id is not None:
        stmt = stmt.where(DemoLocation.id == demo_location_id)
    else:
        stmt = stmt.where(DemoLocation.code == location_code)

    covered = (await db.execute(stmt)).scalar_one_or_none()
    return bool(covered)
