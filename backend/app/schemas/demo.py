"""Demo location DTOs (`openapi.yaml`)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class DemoLocationSummary(BaseModel):
    """Summary metadata for a seeded MVP demo zone (`DemoLocationSummary`)."""

    model_config = ConfigDict(extra="forbid")

    id: int
    code: str
    name: str
    country: str
    region: str
