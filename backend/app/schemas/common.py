"""Common OpenAPI response envelopes: errors, non-blocking warnings, and cursor pages."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    model_serializer,
)

from app.core.errors import ErrorCode

DEMO_PARCEL_UNVERIFIED_MESSAGE = (
    "This demo parcel is marked unverified; "
    "its real field measurements have not yet been studied and may need verification."
)
MVP_OUTSIDE_COVERAGE_MESSAGE = (
    "Field coordinates fall outside the Guelma MVP boundary. "
    "Saved under registered account; dataset coverage for this zone is unverified."
)


class Language(StrEnum):
    """Supported API/ML response localization codes."""

    EN = "en"
    FR = "fr"
    AR = "ar"


class Season(StrEnum):
    """Agronomic seasons for field history and rotation planning."""

    SPRING = "spring"
    SUMMER = "summer"
    AUTUMN = "autumn"
    WINTER = "winter"


class SoilType(StrEnum):
    """Soil texture classifications."""

    SANDY = "sandy"
    CLAY = "clay"
    LOAMY = "loamy"
    SILTY = "silty"
    UNKNOWN = "unknown"


class SoilSource(StrEnum):
    """Authoritative provenance for field soil measurements."""

    FARMER = "farmer"
    UNKNOWN = "unknown"


class WaterAvailability(StrEnum):
    """Qualitative parcel water availability."""

    ABUNDANT = "abundant"
    MODERATE = "moderate"
    LIMITED = "limited"
    VERY_LIMITED = "very_limited"
    RAINFED_ONLY = "rainfed_only"


class WaterSource(StrEnum):
    """Primary parcel water source."""

    RAINWATER = "rainwater"
    GROUNDWATER = "groundwater"
    WELL = "well"
    DAM_RESERVOIR = "dam_reservoir"
    IRRIGATION_NETWORK = "irrigation_network"
    OTHER = "other"
    UNKNOWN = "unknown"


class IrrigationSystem(StrEnum):
    """Installed parcel irrigation system."""

    RAINFED = "rainfed"
    DRIP = "drip"
    SPRINKLER = "sprinkler"
    FLOOD = "flood"
    OTHER = "other"
    UNKNOWN = "unknown"


class ErrorBody(BaseModel):
    """Structured error body matching openapi.yaml#/components/schemas/ErrorEnvelope."""

    model_config = ConfigDict(extra="forbid")

    code: ErrorCode
    message: str
    details: list[dict[str, Any]] = Field(default_factory=list)
    request_id: str | None = None


class ErrorEnvelope(BaseModel):
    """Top-level error response envelope across all API routes."""

    model_config = ConfigDict(extra="forbid")

    error: ErrorBody


class WarningCode(StrEnum):
    """Non-blocking warning codes emitted on guest demo / outside-coverage fields."""

    MVP_OUTSIDE_COVERAGE = "MVP_OUTSIDE_COVERAGE"
    DEMO_PARCEL_UNVERIFIED = "DEMO_PARCEL_UNVERIFIED"


class WarningNotice(BaseModel):
    """Non-blocking notice matching openapi.yaml#/components/schemas/WarningNotice."""

    model_config = ConfigDict(extra="forbid")

    code: WarningCode
    message: str
    fields: list[str] | None = None

    @model_serializer(mode="wrap")
    def _serialize_omit_none_fields(
        self,
        handler: SerializerFunctionWrapHandler,
    ) -> dict[str, Any]:
        # OpenAPI WarningNotice.fields is `type: array` (non-nullable), so omit when unset.
        data: dict[str, Any] = handler(self)
        if data.get("fields") is None:
            data.pop("fields", None)
        return data


class PaginatedResponse[T](BaseModel):
    """Opaque cursor-paginated response envelope matching OpenAPI `*Page` schemas."""

    model_config = ConfigDict(extra="forbid")

    items: list[T]
    next_cursor: str | None = None
    has_more: bool
