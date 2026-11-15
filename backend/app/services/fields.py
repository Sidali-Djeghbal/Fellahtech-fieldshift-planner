"""Owner-scoped spatial field CRUD service with PostGIS gate & row-locked quotas."""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, NoReturn

from sqlalchemy.exc import DataError, DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal
from app.core.config import Settings
from app.core.errors import ErrorCode, FieldShiftError
from app.core.pagination import PaginationParams, decode_id_cursor, slice_keyset_page
from app.models.field import FieldCropHistory
from app.repositories import farm as farm_repo
from app.repositories import field as field_repo
from app.repositories import user as user_repo
from app.schemas.common import (
    DEMO_PARCEL_UNVERIFIED_MESSAGE,
    MVP_OUTSIDE_COVERAGE_MESSAGE,
    IrrigationSystem,
    Season,
    SoilSource,
    SoilType,
    WarningCode,
    WarningNotice,
    WaterAvailability,
    WaterSource,
)
from app.schemas.field import (
    CropHistoryWriteItem,
    FieldDetailPublic,
    FieldLocationPublic,
    FieldPage,
    FieldPatchRequest,
    FieldPublic,
    FieldSoilPublic,
    FieldWaterPublic,
    FieldWriteRequest,
)
from app.services import geo as geo_service
from app.services.farms import format_farm_id, parse_farm_id


def _extract_boundary_and_warnings(
    row: dict[str, Any],
) -> tuple[dict[str, Any] | None, list[WarningNotice]]:
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
    return boundary, warnings


def build_field_public(row: dict[str, Any]) -> FieldPublic:
    """Serialize a projected PostGIS field row into `FieldPublic`."""
    boundary, warnings = _extract_boundary_and_warnings(row)
    return FieldPublic(
        farm_id=format_farm_id(int(row["farm_id"])),
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
        warnings=warnings,
    )


def build_field_detail(
    row: dict[str, Any],
    history_items: Sequence[FieldCropHistory],
) -> FieldDetailPublic:
    """Serialize projected PostGIS field row + ordered crop history as `FieldDetailPublic`."""
    base = build_field_public(row)
    return FieldDetailPublic(
        farm_id=base.farm_id,
        field_id=base.field_id,
        field_name=base.field_name,
        is_unverified_demo_parcel=base.is_unverified_demo_parcel,
        location=base.location,
        area_hectares=base.area_hectares,
        elevation_m=base.elevation_m,
        soil=base.soil,
        water=base.water,
        warnings=base.warnings,
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
    )


def _compute_soil_source(
    *,
    soil_type: SoilType,
    soil_ph: float | Decimal | None,
    organic_matter_percent: float | Decimal | None,
    soil_test_date: date | None,
) -> SoilSource:
    if (
        soil_type != SoilType.UNKNOWN
        or soil_ph is not None
        or organic_matter_percent is not None
        or soil_test_date is not None
    ):
        return SoilSource.FARMER
    return SoilSource.UNKNOWN


def _effective_water_source_other(source: WaterSource, source_other: str | None) -> str | None:
    return source_other if source == WaterSource.OTHER else None


def _validate_unique_crop_history(crop_history: Sequence[CropHistoryWriteItem]) -> None:
    seen: set[tuple[int, str]] = set()
    for item in crop_history:
        key = (item.year, item.season.value)
        if key in seen:
            raise FieldShiftError(
                ErrorCode.CONFLICT,
                f"Duplicate crop_history entry for {item.year} {item.season.value}.",
                details=[
                    {
                        "field": "crop_history",
                        "year": item.year,
                        "season": item.season.value,
                        "reason": "duplicate_year_season",
                    }
                ],
            )
        seen.add(key)


def _to_opt_decimal(value: float | None) -> Decimal | None:
    return Decimal(str(value)) if value is not None else None


def _serialize_boundary(boundary: dict[str, Any] | None) -> str | None:
    return json.dumps(boundary, separators=(",", ":")) if boundary is not None else None


def _translate_field_db_error(exc: DBAPIError, *, field_id: str) -> NoReturn:
    orig = exc.orig
    sqlstate = getattr(orig, "sqlstate", None)
    constraint = getattr(orig, "constraint_name", None) or getattr(
        getattr(orig, "__cause__", None), "constraint_name", None
    )

    if isinstance(exc, IntegrityError):
        if sqlstate == "23505":
            if constraint == "field_crop_history_field_id_year_season_key":
                raise FieldShiftError(
                    ErrorCode.CONFLICT,
                    "Duplicate crop_history entry for the same year and season.",
                    details=[{"field": "crop_history", "reason": "duplicate_year_season"}],
                ) from exc
            raise FieldShiftError(
                ErrorCode.CONFLICT,
                f"Field '{field_id}' already exists in this farm.",
                details=[{"field": "field_id", "field_id": field_id}],
            ) from exc
        if sqlstate == "23514":
            raise FieldShiftError(
                ErrorCode.INVALID_INPUT,
                "Field attributes violate database validation constraints.",
            ) from exc

    if isinstance(exc, DataError):
        raise FieldShiftError(
            ErrorCode.INVALID_INPUT,
            "Invalid field geometry or numeric attribute.",
            details=[{"field": "location.boundary", "reason": "invalid_geometry"}],
        ) from exc

    raise exc


async def _resolve_guest_demo_location_id(
    db: AsyncSession,
    *,
    principal: Principal,
    now: datetime,
    for_update: bool = False,
) -> int | None:
    if not principal.is_guest:
        return None
    assert principal.guest_token_hash is not None
    guest = await user_repo.get_active_guest_session(
        db,
        guest_token_hash=principal.guest_token_hash,
        now=now,
        for_update=for_update,
    )
    if guest is None:
        await db.rollback()
        raise FieldShiftError(ErrorCode.UNAUTHORIZED, "Guest session expired or revoked.")
    return guest.demo_location_id


async def list_fields(
    db: AsyncSession,
    *,
    principal: Principal,
    farm_id: str,
    pagination: PaginationParams,
    soil_type: SoilType | None = None,
    water_availability: WaterAvailability | None = None,
    now: datetime | None = None,
) -> FieldPage:
    """List spatial parcels belonging to an owned farm with optional soil/water filters."""
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
            "Farm not found.",
            details=[{"farm_id": farm_id}],
        )

    demo_location_id = await _resolve_guest_demo_location_id(
        db,
        principal=principal,
        now=now or datetime.now(UTC),
    )
    after_id = decode_id_cursor(pagination.cursor, key="id")
    rows = await field_repo.list_fields_for_farm(
        db,
        farm_pk=farm_pk,
        limit=pagination.limit,
        after_id=after_id,
        soil_type=soil_type.value if soil_type is not None else None,
        water_availability=(
            water_availability.value if water_availability is not None else None
        ),
        demo_location_id=demo_location_id,
    )
    sliced, next_cursor, has_more = slice_keyset_page(
        rows,
        limit=pagination.limit,
        cursor_key_fn=lambda row: {"id": int(row["pk"])},
    )
    return FieldPage(
        items=[build_field_public(row) for row in sliced],
        next_cursor=next_cursor,
        has_more=has_more,
    )


async def create_field(
    db: AsyncSession,
    *,
    principal: Principal,
    farm_id: str,
    payload: FieldWriteRequest,
    settings: Settings,
    now: datetime | None = None,
) -> FieldPublic:
    """Create a field in an owned farm, enforcing row-locked guest limit & PostGIS boundary."""
    farm_pk = parse_farm_id(farm_id)
    _validate_unique_crop_history(payload.crop_history)
    current_now = now or datetime.now(UTC)

    demo_location_id = await _resolve_guest_demo_location_id(
        db,
        principal=principal,
        now=current_now,
    )
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

    if principal.is_guest:
        existing_count = await farm_repo.count_fields_for_farm(db, farm_pk=farm_pk)
        if existing_count >= settings.GUEST_MAX_FIELDS_PER_FARM:
            await db.rollback()
            raise FieldShiftError(
                ErrorCode.GUEST_LIMIT_REACHED,
                (
                    f"Guest farms may contain at most "
                    f"{settings.GUEST_MAX_FIELDS_PER_FARM} fields."
                ),
                details=[
                    {
                        "resource": "fields",
                        "farm_id": farm_id,
                        "limit": settings.GUEST_MAX_FIELDS_PER_FARM,
                        "current": existing_count,
                    }
                ],
            )

    try:
        await geo_service.check_field_coordinates_coverage(
            db,
            latitude=payload.location.latitude,
            longitude=payload.location.longitude,
            is_guest=principal.is_guest,
            demo_location_id=demo_location_id,
            field_id=payload.field_id,
        )
    except FieldShiftError:
        await db.rollback()
        raise

    soil_source = _compute_soil_source(
        soil_type=payload.soil.soil_type,
        soil_ph=payload.soil.soil_ph,
        organic_matter_percent=payload.soil.organic_matter_percent,
        soil_test_date=payload.soil.soil_test_date,
    )
    water_source_other = _effective_water_source_other(
        payload.water.source,
        payload.water.source_other,
    )

    try:
        await field_repo.create_field(
            db,
            farm_pk=farm_pk,
            external_field_id=payload.field_id,
            field_name=payload.field_name,
            is_unverified_demo_parcel=payload.is_unverified_demo_parcel,
            latitude=payload.location.latitude,
            longitude=payload.location.longitude,
            boundary_geojson=_serialize_boundary(payload.location.boundary),
            area_hectares=Decimal(str(payload.area_hectares)),
            elevation_m=_to_opt_decimal(payload.elevation_m),
            soil_type=payload.soil.soil_type.value,
            soil_source=soil_source.value,
            soil_ph=_to_opt_decimal(payload.soil.soil_ph),
            organic_matter_percent=_to_opt_decimal(payload.soil.organic_matter_percent),
            soil_test_date=payload.soil.soil_test_date,
            water_availability=payload.water.availability.value,
            water_source=payload.water.source.value,
            water_source_other=water_source_other,
            irrigation_system=payload.water.irrigation_system.value,
            crop_history=payload.crop_history,
        )
        projected = await field_repo.get_field_projection(
            db,
            farm_pk=farm_pk,
            external_field_id=payload.field_id,
            demo_location_id=demo_location_id,
        )
        await db.commit()
    except (IntegrityError, DataError) as exc:
        await db.rollback()
        _translate_field_db_error(exc, field_id=payload.field_id)

    assert projected is not None
    return build_field_public(projected)


async def get_field(
    db: AsyncSession,
    *,
    principal: Principal,
    farm_id: str,
    field_id: str,
    now: datetime | None = None,
) -> FieldDetailPublic:
    """Fetch full details of an owned field including ordered `crop_history[]` and warnings."""
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
            "Farm not found.",
            details=[{"farm_id": farm_id}],
        )

    demo_location_id = await _resolve_guest_demo_location_id(
        db,
        principal=principal,
        now=now or datetime.now(UTC),
    )
    projected = await field_repo.get_field_projection(
        db,
        farm_pk=farm_pk,
        external_field_id=field_id,
        demo_location_id=demo_location_id,
    )
    if projected is None:
        raise FieldShiftError(
            ErrorCode.NOT_FOUND,
            "Field not found.",
            details=[{"farm_id": farm_id, "field_id": field_id}],
        )

    history = await field_repo.get_crop_history_for_field(
        db,
        field_pk=int(projected["pk"]),
    )
    return build_field_detail(projected, history)


async def replace_field(
    db: AsyncSession,
    *,
    principal: Principal,
    farm_id: str,
    field_id: str,
    payload: FieldWriteRequest,
    now: datetime | None = None,
) -> FieldDetailPublic:
    """Replace an owned field (`PUT`) and atomically rewrite its crop history."""
    farm_pk = parse_farm_id(farm_id)
    if payload.field_id != field_id:
        raise FieldShiftError(
            ErrorCode.INVALID_INPUT,
            "Body field_id must match path field_id.",
            details=[{"field": "field_id", "reason": "path_body_mismatch"}],
        )
    _validate_unique_crop_history(payload.crop_history)
    current_now = now or datetime.now(UTC)

    demo_location_id = await _resolve_guest_demo_location_id(
        db,
        principal=principal,
        now=current_now,
    )
    farm = await farm_repo.get_owned_farm(
        db,
        farm_pk=farm_pk,
        user_id=principal.user_id,
        guest_token_hash=principal.guest_token_hash,
    )
    if farm is None:
        raise FieldShiftError(
            ErrorCode.NOT_FOUND,
            "Farm not found.",
            details=[{"farm_id": farm_id}],
        )

    locked = await field_repo.get_field_for_update(
        db,
        farm_pk=farm_pk,
        external_field_id=field_id,
    )
    if locked is None:
        await db.rollback()
        raise FieldShiftError(
            ErrorCode.NOT_FOUND,
            "Field not found.",
            details=[{"farm_id": farm_id, "field_id": field_id}],
        )

    try:
        await geo_service.check_field_coordinates_coverage(
            db,
            latitude=payload.location.latitude,
            longitude=payload.location.longitude,
            is_guest=principal.is_guest,
            demo_location_id=demo_location_id,
            field_id=field_id,
        )
    except FieldShiftError:
        await db.rollback()
        raise

    soil_source = _compute_soil_source(
        soil_type=payload.soil.soil_type,
        soil_ph=payload.soil.soil_ph,
        organic_matter_percent=payload.soil.organic_matter_percent,
        soil_test_date=payload.soil.soil_test_date,
    )
    water_source_other = _effective_water_source_other(
        payload.water.source,
        payload.water.source_other,
    )

    values: dict[str, Any] = {
        "field_name": payload.field_name,
        "is_unverified_demo_parcel": payload.is_unverified_demo_parcel,
        "area_hectares": Decimal(str(payload.area_hectares)),
        "elevation_m": _to_opt_decimal(payload.elevation_m),
        "soil_type": payload.soil.soil_type.value,
        "soil_source": soil_source.value,
        "soil_ph": _to_opt_decimal(payload.soil.soil_ph),
        "organic_matter_percent": _to_opt_decimal(payload.soil.organic_matter_percent),
        "soil_test_date": payload.soil.soil_test_date,
        "water_availability": payload.water.availability.value,
        "water_source": payload.water.source.value,
        "water_source_other": water_source_other,
        "irrigation_system": payload.water.irrigation_system.value,
    }

    try:
        await field_repo.update_field(
            db,
            field_pk=locked.field.id,
            values=values,
            latitude=payload.location.latitude,
            longitude=payload.location.longitude,
            update_polygon=True,
            boundary_geojson=_serialize_boundary(payload.location.boundary),
            crop_history=payload.crop_history,
            updated_at=current_now,
        )
        projected = await field_repo.get_field_projection(
            db,
            farm_pk=farm_pk,
            external_field_id=field_id,
            demo_location_id=demo_location_id,
        )
        history = await field_repo.get_crop_history_for_field(db, field_pk=locked.field.id)
        await db.commit()
    except (IntegrityError, DataError) as exc:
        await db.rollback()
        _translate_field_db_error(exc, field_id=field_id)

    assert projected is not None
    return build_field_detail(projected, history)


async def patch_field(
    db: AsyncSession,
    *,
    principal: Principal,
    farm_id: str,
    field_id: str,
    payload: FieldPatchRequest,
    now: datetime | None = None,
) -> FieldDetailPublic:
    """Partially update an owned field (`PATCH`) with strict deep-merge and `soil_source` rules."""
    farm_pk = parse_farm_id(farm_id)
    if payload.crop_history is not None:
        _validate_unique_crop_history(payload.crop_history)
    current_now = now or datetime.now(UTC)

    demo_location_id = await _resolve_guest_demo_location_id(
        db,
        principal=principal,
        now=current_now,
    )
    farm = await farm_repo.get_owned_farm(
        db,
        farm_pk=farm_pk,
        user_id=principal.user_id,
        guest_token_hash=principal.guest_token_hash,
    )
    if farm is None:
        raise FieldShiftError(
            ErrorCode.NOT_FOUND,
            "Farm not found.",
            details=[{"farm_id": farm_id}],
        )

    locked = await field_repo.get_field_for_update(
        db,
        farm_pk=farm_pk,
        external_field_id=field_id,
    )
    if locked is None:
        await db.rollback()
        raise FieldShiftError(
            ErrorCode.NOT_FOUND,
            "Field not found.",
            details=[{"farm_id": farm_id, "field_id": field_id}],
        )

    existing = locked.field
    loc = payload.location
    update_point = loc is not None and (loc.latitude is not None or loc.longitude is not None)
    eff_lat = (
        loc.latitude
        if (loc is not None and loc.latitude is not None)
        else locked.latitude
    )
    eff_lon = (
        loc.longitude
        if (loc is not None and loc.longitude is not None)
        else locked.longitude
    )
    update_polygon = loc is not None and "boundary" in loc.model_fields_set
    boundary_geojson = (
        _serialize_boundary(loc.boundary) if (loc is not None and update_polygon) else None
    )

    if loc is not None:
        try:
            await geo_service.check_field_coordinates_coverage(
                db,
                latitude=eff_lat,
                longitude=eff_lon,
                is_guest=principal.is_guest,
                demo_location_id=demo_location_id,
                field_id=field_id,
            )
        except FieldShiftError:
            await db.rollback()
            raise

    soil_patch = payload.soil
    eff_soil_type = (
        soil_patch.soil_type
        if (soil_patch is not None and soil_patch.soil_type is not None)
        else SoilType(existing.soil_type)
    )
    eff_soil_ph: float | Decimal | None = (
        _to_opt_decimal(soil_patch.soil_ph)
        if (soil_patch is not None and "soil_ph" in soil_patch.model_fields_set)
        else existing.soil_ph
    )
    eff_om: float | Decimal | None = (
        _to_opt_decimal(soil_patch.organic_matter_percent)
        if (soil_patch is not None and "organic_matter_percent" in soil_patch.model_fields_set)
        else existing.organic_matter_percent
    )
    eff_test_date: date | None = (
        soil_patch.soil_test_date
        if (soil_patch is not None and "soil_test_date" in soil_patch.model_fields_set)
        else existing.soil_test_date
    )
    eff_soil_source = _compute_soil_source(
        soil_type=eff_soil_type,
        soil_ph=eff_soil_ph,
        organic_matter_percent=eff_om,
        soil_test_date=eff_test_date,
    )

    water_patch = payload.water
    eff_water_av = (
        water_patch.availability
        if (water_patch is not None and water_patch.availability is not None)
        else WaterAvailability(existing.water_availability)
    )
    eff_water_src = (
        water_patch.source
        if (water_patch is not None and water_patch.source is not None)
        else WaterSource(existing.water_source)
    )
    raw_source_other = (
        water_patch.source_other
        if (water_patch is not None and "source_other" in water_patch.model_fields_set)
        else existing.water_source_other
    )
    eff_water_other = _effective_water_source_other(eff_water_src, raw_source_other)
    eff_irrigation = (
        water_patch.irrigation_system
        if (water_patch is not None and water_patch.irrigation_system is not None)
        else IrrigationSystem(existing.irrigation_system)
    )

    fields_set = payload.model_fields_set
    values: dict[str, Any] = {
        "soil_type": eff_soil_type.value,
        "soil_source": eff_soil_source.value,
        "soil_ph": eff_soil_ph,
        "organic_matter_percent": eff_om,
        "soil_test_date": eff_test_date,
        "water_availability": eff_water_av.value,
        "water_source": eff_water_src.value,
        "water_source_other": eff_water_other,
        "irrigation_system": eff_irrigation.value,
    }
    if "field_name" in fields_set and payload.field_name is not None:
        values["field_name"] = payload.field_name
    if "area_hectares" in fields_set and payload.area_hectares is not None:
        values["area_hectares"] = Decimal(str(payload.area_hectares))
    if "elevation_m" in fields_set:
        values["elevation_m"] = _to_opt_decimal(payload.elevation_m)

    try:
        await field_repo.update_field(
            db,
            field_pk=existing.id,
            values=values,
            latitude=eff_lat if update_point else None,
            longitude=eff_lon if update_point else None,
            update_polygon=update_polygon,
            boundary_geojson=boundary_geojson,
            crop_history=payload.crop_history,
            updated_at=current_now,
        )
        projected = await field_repo.get_field_projection(
            db,
            farm_pk=farm_pk,
            external_field_id=field_id,
            demo_location_id=demo_location_id,
        )
        history = await field_repo.get_crop_history_for_field(db, field_pk=existing.id)
        await db.commit()
    except (IntegrityError, DataError) as exc:
        await db.rollback()
        _translate_field_db_error(exc, field_id=field_id)

    assert projected is not None
    return build_field_detail(projected, history)


async def delete_field(
    db: AsyncSession,
    *,
    principal: Principal,
    farm_id: str,
    field_id: str,
) -> None:
    """Hard-delete a field and its crop history from an owned farm."""
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
            "Farm not found.",
            details=[{"farm_id": farm_id}],
        )

    deleted = await field_repo.delete_owned_field(
        db,
        farm_pk=farm_pk,
        external_field_id=field_id,
    )
    if not deleted:
        await db.rollback()
        raise FieldShiftError(
            ErrorCode.NOT_FOUND,
            "Field not found.",
            details=[{"farm_id": farm_id, "field_id": field_id}],
        )
    await db.commit()
