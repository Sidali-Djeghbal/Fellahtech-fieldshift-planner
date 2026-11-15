"""Field and crop history request/response DTOs matching `openapi.yaml`."""

from __future__ import annotations

import math
from datetime import date
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator, model_validator

from app.schemas.common import (
    IrrigationSystem,
    PaginatedResponse,
    Season,
    SoilSource,
    SoilType,
    WarningNotice,
    WaterAvailability,
    WaterSource,
    sanitize_free_text,
)

CleanText = Annotated[str, BeforeValidator(sanitize_free_text)]

_MAX_POLYGON_RINGS = 64
_MAX_POLYGON_VERTICES = 10_000


def _reject_explicit_nulls(model: BaseModel, non_nullable: tuple[str, ...]) -> None:
    for field_name in non_nullable:
        if field_name in model.model_fields_set and getattr(model, field_name) is None:
            raise ValueError(f"{field_name} cannot be null.")


def _validate_area_hectares_scale(value: float) -> float:
    if round(value, 4) <= 0:
        raise ValueError("area_hectares must be at least 0.0001 hectares.")
    return value


def _validate_geojson_polygon(boundary: dict[str, Any] | None) -> dict[str, Any] | None:
    """Validate that an optional field boundary is a closed GeoJSON Polygon in WGS84 bounds."""
    if boundary is None:
        return None
    if not isinstance(boundary, dict):
        raise ValueError("location.boundary must be a GeoJSON Polygon object.")
    unexpected_keys = set(boundary.keys()) - {"type", "coordinates", "bbox"}
    if unexpected_keys or boundary.get("type") != "Polygon":
        raise ValueError("location.boundary must have GeoJSON type 'Polygon'.")

    coords = boundary.get("coordinates")
    if not isinstance(coords, list) or not coords or len(coords) > _MAX_POLYGON_RINGS:
        raise ValueError("location.boundary.coordinates must be a non-empty list of rings.")

    total_vertices = 0
    for ring in coords:
        if not isinstance(ring, list) or len(ring) < 4:
            raise ValueError("Each GeoJSON Polygon ring must contain at least 4 positions.")
        total_vertices += len(ring)
        if total_vertices > _MAX_POLYGON_VERTICES:
            raise ValueError("location.boundary exceeds maximum supported vertex count.")

        for pos in ring:
            if not isinstance(pos, (list, tuple)) or len(pos) not in (2, 3):
                raise ValueError("GeoJSON Polygon positions must be [longitude, latitude] pairs.")
            lon, lat = pos[0], pos[1]
            if (
                isinstance(lon, bool)
                or isinstance(lat, bool)
                or not isinstance(lon, (int, float))
                or not isinstance(lat, (int, float))
                or not math.isfinite(lon)
                or not math.isfinite(lat)
                or not (-180.0 <= lon <= 180.0)
                or not (-90.0 <= lat <= 90.0)
            ):
                raise ValueError("GeoJSON Polygon coordinates must be finite WGS84 lon/lat pairs.")
            if len(pos) == 3 and (
                isinstance(pos[2], bool)
                or not isinstance(pos[2], (int, float))
                or not math.isfinite(pos[2])
            ):
                raise ValueError("GeoJSON Polygon altitude coordinate must be finite.")

        if ring[0][0] != ring[-1][0] or ring[0][1] != ring[-1][1]:
            raise ValueError("GeoJSON Polygon ring must be closed (first position == last).")

    return boundary


class CropHistoryWriteItem(BaseModel):
    """Historical field cropping item (`CropHistoryWriteItem`)."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    season: Season
    year: int = Field(ge=1980, le=2100)
    planting_month: int | None = Field(default=None, ge=1, le=12)
    crop_id: CleanText | None = Field(default=None, min_length=1, max_length=64)
    crop_name_raw: CleanText | None = Field(default=None, min_length=1, max_length=120)
    yield_tons_per_hectare: float | None = Field(default=None, ge=0, le=99999.999)
    notes: CleanText | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _require_crop_identifier(self) -> CropHistoryWriteItem:
        if self.crop_id is None and self.crop_name_raw is None:
            raise ValueError("Either crop_id or crop_name_raw must be provided.")
        return self


class FieldLocationWrite(BaseModel):
    """Field coordinates and optional GeoJSON polygon (`FieldWriteRequest.location`)."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)
    boundary: dict[str, Any] | None = None

    @field_validator("boundary")
    @classmethod
    def _check_boundary(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        return _validate_geojson_polygon(value)


class FieldLocationPatch(BaseModel):
    """Strict partial location update payload (`FieldPatchRequest.location`, `IMPL-019`)."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    latitude: float | None = Field(default=None, ge=-90.0, le=90.0)
    longitude: float | None = Field(default=None, ge=-180.0, le=180.0)
    boundary: dict[str, Any] | None = None

    @field_validator("boundary")
    @classmethod
    def _check_boundary(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        return _validate_geojson_polygon(value)

    @model_validator(mode="after")
    def _check_non_nullable(self) -> FieldLocationPatch:
        _reject_explicit_nulls(self, ("latitude", "longitude"))
        return self


class FieldSoilWrite(BaseModel):
    """Field soil profile input (`FieldWriteRequest.soil`)."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    soil_type: SoilType
    soil_ph: float | None = Field(default=None, ge=3.0, le=11.0)
    organic_matter_percent: float | None = Field(default=None, ge=0.0, le=100.0)
    soil_test_date: date | None = None


class FieldSoilPatch(BaseModel):
    """Strict partial soil update payload (`FieldPatchRequest.soil`, `IMPL-019`)."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    soil_type: SoilType | None = None
    soil_ph: float | None = Field(default=None, ge=3.0, le=11.0)
    organic_matter_percent: float | None = Field(default=None, ge=0.0, le=100.0)
    soil_test_date: date | None = None

    @model_validator(mode="after")
    def _check_non_nullable(self) -> FieldSoilPatch:
        _reject_explicit_nulls(self, ("soil_type",))
        return self


class FieldWaterWrite(BaseModel):
    """Field water profile input (`FieldWriteRequest.water`)."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    availability: WaterAvailability
    source: WaterSource
    source_other: CleanText | None = Field(default=None, max_length=200)
    irrigation_system: IrrigationSystem


class FieldWaterPatch(BaseModel):
    """Strict partial water update payload (`FieldPatchRequest.water`, `IMPL-019`)."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    availability: WaterAvailability | None = None
    source: WaterSource | None = None
    source_other: CleanText | None = Field(default=None, max_length=200)
    irrigation_system: IrrigationSystem | None = None

    @model_validator(mode="after")
    def _check_non_nullable(self) -> FieldWaterPatch:
        _reject_explicit_nulls(self, ("availability", "source", "irrigation_system"))
        return self


class FieldWriteRequest(BaseModel):
    """Create or replace spatial parcel payload (`FieldWriteRequest`)."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    field_id: CleanText = Field(min_length=1, max_length=64)
    field_name: CleanText = Field(min_length=1, max_length=120)
    is_unverified_demo_parcel: bool = False
    location: FieldLocationWrite
    area_hectares: float = Field(gt=0.0, le=10000.0)
    elevation_m: float | None = Field(default=None, ge=-500.0, le=9000.0)
    soil: FieldSoilWrite
    water: FieldWaterWrite
    crop_history: list[CropHistoryWriteItem] = Field(min_length=1, max_length=30)

    @field_validator("area_hectares")
    @classmethod
    def _check_area_scale(cls, value: float) -> float:
        return _validate_area_hectares_scale(value)


class FieldPatchRequest(BaseModel):
    """Partial parcel update payload (`FieldPatchRequest`)."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    field_name: CleanText | None = Field(default=None, min_length=1, max_length=120)
    location: FieldLocationPatch | None = None
    area_hectares: float | None = Field(default=None, gt=0.0, le=10000.0)
    elevation_m: float | None = Field(default=None, ge=-500.0, le=9000.0)
    soil: FieldSoilPatch | None = None
    water: FieldWaterPatch | None = None
    crop_history: list[CropHistoryWriteItem] | None = Field(
        default=None,
        min_length=1,
        max_length=30,
    )

    @field_validator("area_hectares")
    @classmethod
    def _check_area_scale(cls, value: float | None) -> float | None:
        if value is not None:
            return _validate_area_hectares_scale(value)
        return None

    @model_validator(mode="after")
    def _check_non_nullable(self) -> FieldPatchRequest:
        _reject_explicit_nulls(
            self,
            ("field_name", "location", "area_hectares", "soil", "water", "crop_history"),
        )
        return self


class FieldLocationPublic(BaseModel):
    """Serialized parcel location including optional GeoJSON polygon."""

    model_config = ConfigDict(extra="forbid")

    latitude: float
    longitude: float
    boundary: dict[str, Any] | None


class FieldSoilPublic(BaseModel):
    """Serialized parcel soil profile and farmer provenance."""

    model_config = ConfigDict(extra="forbid")

    soil_type: SoilType
    source: SoilSource
    soil_ph: float | None
    organic_matter_percent: float | None
    soil_test_date: date | None


class FieldWaterPublic(BaseModel):
    """Serialized parcel water availability and irrigation details."""

    model_config = ConfigDict(extra="forbid")

    availability: WaterAvailability
    source: WaterSource
    source_other: str | None
    irrigation_system: IrrigationSystem


class FieldPublic(BaseModel):
    """Serialized parcel summary (`openapi.yaml#/components/schemas/FieldPublic`)."""

    model_config = ConfigDict(extra="forbid")

    farm_id: str = Field(pattern=r"^farm_[0-9]+$")
    field_id: str
    field_name: str
    is_unverified_demo_parcel: bool
    location: FieldLocationPublic
    area_hectares: float
    elevation_m: float | None
    soil: FieldSoilPublic
    water: FieldWaterPublic
    warnings: list[WarningNotice]


class FieldDetailPublic(FieldPublic):
    """Serialized full parcel including historical crops (`FieldDetailPublic`)."""

    crop_history: list[CropHistoryWriteItem]


class FieldPage(PaginatedResponse[FieldPublic]):
    """Cursor-paginated field list (`openapi.yaml#/components/schemas/FieldPage`)."""
