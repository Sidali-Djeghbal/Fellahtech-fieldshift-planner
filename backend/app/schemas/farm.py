"""Farm API public representation (`openapi.yaml#/components/schemas/FarmPublic`)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class FarmPublic(BaseModel):
    """Serialized public farm record with `farm_<id>` prefix formatting."""

    model_config = ConfigDict(extra="forbid")

    farm_id: str = Field(pattern=r"^farm_[0-9]+$")
    farm_name: str
    country: str
    region: str
    commune: str | None
    field_count: int = Field(ge=0)
    created_at: datetime
