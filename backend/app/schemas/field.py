"""Field and crop history public DTOs matching `openapi.yaml`."""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.common import (
    IrrigationSystem,
    Season,
    SoilSource,
    SoilType,
    WarningNotice,
    WaterAvailability,
    WaterSource,
)


class CropHistoryWriteItem(BaseModel):
    """Historical field cropping item (`CropHistoryWriteItem`)."""

    model_config = ConfigDict(extra="forbid")

    season: Season
    year: int = Field(ge=1980, le=2100)
    planting_month: int | None = Field(default=None, ge=1, le=12)
    crop_id: str | None = Field(default=None, min_length=1, max_length=64)
    crop_name_raw: str | None = Field(default=None, min_length=1, max_length=120)
    yield_tons_per_hectare: float | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _require_crop_identifier(self) -> CropHistoryWriteItem:
        if self.crop_id is None and self.crop_name_raw is None:
            raise ValueError("Either crop_id or crop_name_raw must be provided.")
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
