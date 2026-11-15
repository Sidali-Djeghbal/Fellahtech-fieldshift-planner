"""Demo location, GeoJSON boundary, and guest session DTOs (`openapi.yaml`)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import PaginatedResponse


class DemoLocationSummary(BaseModel):
    """Summary metadata for a seeded MVP demo zone (`DemoLocationSummary`)."""

    model_config = ConfigDict(extra="forbid")

    id: int
    code: str
    name: str
    country: str
    region: str


class DemoLocationPage(PaginatedResponse[DemoLocationSummary]):
    """Cursor-paginated list of active demo locations (`DemoLocationPage`)."""


class BoundaryFeature(BaseModel):
    """GeoJSON Feature for an active MVP zone boundary (`BoundaryFeature`)."""

    model_config = ConfigDict(extra="allow")

    type: Literal["Feature"] = "Feature"
    properties: dict[str, Any]
    geometry: dict[str, Any]
    bbox: list[float] = Field(min_length=4, max_length=4)


class GuestLimits(BaseModel):
    """Configured guest quota ceilings (`GuestSessionInfo.limits`)."""

    model_config = ConfigDict(extra="forbid")

    max_farms: int
    max_fields_per_farm: int
    max_analyses: int
    max_analysis_quarters: int


class GuestUsage(BaseModel):
    """Canonical guest resource usage (`GuestSessionInfo.usage`)."""

    model_config = ConfigDict(extra="forbid")

    farms: int
    fields: int
    analysis_quarters: int
    analyses: float


class GuestSessionInfo(BaseModel):
    """Current guest session state without server demo_parcel stubs (`IMPL-023`)."""

    model_config = ConfigDict(extra="forbid")

    demo_location: DemoLocationSummary
    created_at: datetime
    expires_at: datetime
    limits: GuestLimits
    usage: GuestUsage
