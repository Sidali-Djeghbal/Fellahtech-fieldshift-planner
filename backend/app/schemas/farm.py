"""Farm API request and response schemas matching `openapi.yaml`."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator

from app.schemas.common import PaginatedResponse, sanitize_free_text

CleanText = Annotated[str, BeforeValidator(sanitize_free_text)]


class FarmWriteRequest(BaseModel):
    """Create or full-replace farm payload (`FarmWriteRequest`)."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    farm_name: CleanText = Field(min_length=1, max_length=120)
    country: CleanText = Field(min_length=1, max_length=80)
    region: CleanText = Field(min_length=1, max_length=80)
    commune: CleanText | None = Field(default=None, max_length=120)


class FarmPatchRequest(BaseModel):
    """Partial farm update payload (`FarmPatchRequest`)."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    farm_name: CleanText | None = Field(default=None, min_length=1, max_length=120)
    country: CleanText | None = Field(default=None, min_length=1, max_length=80)
    region: CleanText | None = Field(default=None, min_length=1, max_length=80)
    commune: CleanText | None = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def _reject_explicit_nulls(self) -> FarmPatchRequest:
        for field_name in ("farm_name", "country", "region"):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null.")
        return self


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


class FarmPage(PaginatedResponse[FarmPublic]):
    """Cursor-paginated farm list (`openapi.yaml#/components/schemas/FarmPage`)."""
