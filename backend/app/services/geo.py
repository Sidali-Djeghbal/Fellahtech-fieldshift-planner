"""PostGIS spatial boundary evaluation for Wilaya of Guelma MVP gate (`ADR-3`)."""

from __future__ import annotations

import math

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ErrorCode, FieldShiftError
from app.repositories import demo as demo_repo
from app.schemas.common import MVP_OUTSIDE_COVERAGE_MESSAGE, WarningCode, WarningNotice

OUTSIDE_DEMO_BOUNDARY_MESSAGE = (
    "The current MVP version supports the Wilaya of Guelma only. "
    "Please select a field inside the highlighted Guelma boundary or register an account."
)


def _validate_coordinates(*, latitude: float, longitude: float) -> None:
    if not (math.isfinite(latitude) and -90.0 <= latitude <= 90.0):
        raise FieldShiftError(
            ErrorCode.INVALID_INPUT,
            "Invalid latitude coordinate.",
            details=[{"field": "latitude", "reason": "out_of_range"}],
        )
    if not (math.isfinite(longitude) and -180.0 <= longitude <= 180.0):
        raise FieldShiftError(
            ErrorCode.INVALID_INPUT,
            "Invalid longitude coordinate.",
            details=[{"field": "longitude", "reason": "out_of_range"}],
        )


async def is_point_inside_demo_boundary(
    db: AsyncSession,
    *,
    latitude: float,
    longitude: float,
    demo_location_id: int | None = None,
    location_code: str = "guelma",
) -> bool:
    """Return True if `(latitude, longitude)` is covered by the active PostGIS demo boundary."""
    _validate_coordinates(latitude=latitude, longitude=longitude)
    return await demo_repo.is_point_covered_by_demo_location(
        db,
        latitude=latitude,
        longitude=longitude,
        demo_location_id=demo_location_id,
        location_code=location_code,
    )


async def check_field_coordinates_coverage(
    db: AsyncSession,
    *,
    latitude: float,
    longitude: float,
    is_guest: bool,
    demo_location_id: int | None = None,
    field_id: str | None = None,
) -> tuple[bool, WarningNotice | None]:
    """Enforce guest `422 OUTSIDE_DEMO_BOUNDARY` or emit registered `MVP_OUTSIDE_COVERAGE`."""
    covered = await is_point_inside_demo_boundary(
        db,
        latitude=latitude,
        longitude=longitude,
        demo_location_id=demo_location_id,
    )
    if covered:
        return True, None

    if is_guest:
        detail: dict[str, object] = {
            "latitude": latitude,
            "longitude": longitude,
        }
        if field_id is not None:
            detail["field_id"] = field_id
        raise FieldShiftError(
            ErrorCode.OUTSIDE_DEMO_BOUNDARY,
            OUTSIDE_DEMO_BOUNDARY_MESSAGE,
            details=[detail],
        )

    notice = WarningNotice(
        code=WarningCode.MVP_OUTSIDE_COVERAGE,
        message=MVP_OUTSIDE_COVERAGE_MESSAGE,
        fields=[field_id] if field_id is not None else None,
    )
    return False, notice
