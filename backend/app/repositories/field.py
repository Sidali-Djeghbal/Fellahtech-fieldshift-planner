"""PostgreSQL/PostGIS repositories for spatial parcels (`fields`) and crop history."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, case, delete, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from app.models.demo import DemoLocation
from app.models.field import Field, FieldCropHistory
from app.schemas.field import CropHistoryWriteItem


@dataclass(frozen=True, slots=True)
class LockedFieldState:
    """Row-locked `Field` ORM instance paired with current WGS84 point coordinates."""

    field: Field
    latitude: float
    longitude: float


def select_field_projections(*, demo_location_id: int | None = None) -> Select[*tuple[Any, ...]]:
    """Build reusable PostGIS projection query with coverage flag for one or many fields."""
    location_filter = (
        DemoLocation.id == demo_location_id
        if demo_location_id is not None
        else DemoLocation.code == "guelma"
    )
    return select(
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
    ).outerjoin(
        DemoLocation,
        and_(location_filter, DemoLocation.is_active.is_(True)),
    )


async def list_fields_for_farm(
    db: AsyncSession,
    *,
    farm_pk: int,
    limit: int,
    after_id: int | None,
    soil_type: str | None = None,
    water_availability: str | None = None,
    demo_location_id: int | None = None,
) -> list[dict[str, Any]]:
    """Fetch `limit + 1` projected fields belonging to `farm_pk` ordered by PK."""
    stmt = select_field_projections(demo_location_id=demo_location_id).where(
        Field.farm_id == farm_pk
    )
    if soil_type is not None:
        stmt = stmt.where(Field.soil_type == soil_type)
    if water_availability is not None:
        stmt = stmt.where(Field.water_availability == water_availability)
    if after_id is not None:
        stmt = stmt.where(Field.id > after_id)

    stmt = stmt.order_by(Field.id.asc()).limit(limit + 1)
    return [dict(row) for row in (await db.execute(stmt)).mappings().all()]


async def get_field_projection(
    db: AsyncSession,
    *,
    farm_pk: int,
    external_field_id: str,
    demo_location_id: int | None = None,
) -> dict[str, Any] | None:
    """Load one projected field row with PostGIS coordinates, GeoJSON, and coverage check."""
    stmt = select_field_projections(demo_location_id=demo_location_id).where(
        Field.farm_id == farm_pk,
        Field.external_field_id == external_field_id,
    )
    row = (await db.execute(stmt)).mappings().one_or_none()
    return dict(row) if row is not None else None


async def get_field_for_update(
    db: AsyncSession,
    *,
    farm_pk: int,
    external_field_id: str,
) -> LockedFieldState | None:
    """Acquire `FOR UPDATE` on a field row along with its current WGS84 `(lat, lon)`."""
    stmt = (
        select(
            Field,
            func.ST_Y(Field.geom_point).label("latitude"),
            func.ST_X(Field.geom_point).label("longitude"),
        )
        .where(
            Field.farm_id == farm_pk,
            Field.external_field_id == external_field_id,
        )
        .with_for_update(of=Field)
    )
    row: Any = (await db.execute(stmt)).one_or_none()
    if row is None:
        return None
    return LockedFieldState(
        field=row[0],
        latitude=float(row[1]),
        longitude=float(row[2]),
    )


async def get_crop_history_for_field(
    db: AsyncSession,
    *,
    field_pk: int,
) -> list[FieldCropHistory]:
    """Load crop history rows ordered deterministically by `(year DESC, season ASC)`."""
    stmt = (
        select(FieldCropHistory)
        .where(FieldCropHistory.field_id == field_pk)
        .order_by(FieldCropHistory.year.desc(), FieldCropHistory.season.asc())
    )
    return list((await db.execute(stmt)).scalars().all())


def _build_crop_history_models(
    *,
    field_pk: int,
    crop_history: Sequence[CropHistoryWriteItem],
) -> list[FieldCropHistory]:
    return [
        FieldCropHistory(
            field_id=field_pk,
            season=item.season.value,
            year=item.year,
            planting_month=item.planting_month,
            catalog_version=None,
            crop_id=item.crop_id,
            crop_name_raw=item.crop_name_raw,
            yield_tons_per_hectare=(
                Decimal(str(item.yield_tons_per_hectare))
                if item.yield_tons_per_hectare is not None
                else None
            ),
            notes=item.notes,
        )
        for item in crop_history
    ]


async def create_field(
    db: AsyncSession,
    *,
    farm_pk: int,
    external_field_id: str,
    field_name: str,
    is_unverified_demo_parcel: bool,
    latitude: float,
    longitude: float,
    boundary_geojson: str | None,
    area_hectares: Decimal,
    elevation_m: Decimal | None,
    soil_type: str,
    soil_source: str,
    soil_ph: Decimal | None,
    organic_matter_percent: Decimal | None,
    soil_test_date: date | None,
    water_availability: str,
    water_source: str,
    water_source_other: str | None,
    irrigation_system: str,
    crop_history: Sequence[CropHistoryWriteItem],
) -> int:
    """Insert a spatial parcel (`POINT` + optional `POLYGON`) and its initial crop history."""
    geom_point_expr = func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326)
    geom_polygon_expr = (
        func.ST_SetSRID(func.ST_GeomFromGeoJSON(boundary_geojson), 4326)
        if boundary_geojson is not None
        else None
    )

    stmt = (
        insert(Field)
        .values(
            farm_id=farm_pk,
            external_field_id=external_field_id,
            field_name=field_name,
            is_unverified_demo_parcel=is_unverified_demo_parcel,
            geom_point=geom_point_expr,
            geom_polygon=geom_polygon_expr,
            area_hectares=area_hectares,
            elevation_m=elevation_m,
            soil_type=soil_type,
            soil_source=soil_source,
            soil_ph=soil_ph,
            organic_matter_percent=organic_matter_percent,
            soil_test_date=soil_test_date,
            water_availability=water_availability,
            water_source=water_source,
            water_source_other=water_source_other,
            irrigation_system=irrigation_system,
        )
        .returning(Field.id)
    )
    field_pk = int((await db.execute(stmt)).scalar_one())
    db.add_all(_build_crop_history_models(field_pk=field_pk, crop_history=crop_history))
    await db.flush()
    return field_pk


async def update_field(
    db: AsyncSession,
    *,
    field_pk: int,
    values: dict[str, Any],
    latitude: float | None = None,
    longitude: float | None = None,
    update_polygon: bool = False,
    boundary_geojson: str | None = None,
    crop_history: Sequence[CropHistoryWriteItem] | None = None,
    updated_at: datetime,
) -> None:
    """Update columns/PostGIS geometries and optionally replace crop history atomically."""
    update_values: dict[str, Any] = dict(values)
    update_values["updated_at"] = updated_at
    if latitude is not None and longitude is not None:
        update_values["geom_point"] = func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326)
    if update_polygon:
        update_values["geom_polygon"] = (
            func.ST_SetSRID(func.ST_GeomFromGeoJSON(boundary_geojson), 4326)
            if boundary_geojson is not None
            else None
        )

    await db.execute(update(Field).where(Field.id == field_pk).values(**update_values))

    if crop_history is not None:
        # Flush DELETE before INSERT so replaced (year, season) pairs never collide.
        await db.execute(delete(FieldCropHistory).where(FieldCropHistory.field_id == field_pk))
        await db.flush()
        db.add_all(_build_crop_history_models(field_pk=field_pk, crop_history=crop_history))
        await db.flush()


async def delete_owned_field(
    db: AsyncSession,
    *,
    farm_pk: int,
    external_field_id: str,
) -> bool:
    """Delete a field belonging to an owned farm; cascades to `field_crop_history`."""
    stmt = (
        delete(Field)
        .where(
            Field.farm_id == farm_pk,
            Field.external_field_id == external_field_id,
        )
        .returning(Field.id)
    )
    return (await db.execute(stmt)).scalar_one_or_none() is not None
