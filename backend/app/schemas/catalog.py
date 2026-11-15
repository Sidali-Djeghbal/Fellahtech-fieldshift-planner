"""Crop catalog DTOs matching `openapi.yaml` `CatalogPage` and `schema-v5.0.json`."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    model_serializer,
    model_validator,
)

from app.schemas.common import CropCategory, CropRole


class CropNames(BaseModel):
    """Localized crop names matching `schema-v5.0.json#/$defs/CropItem.names`."""

    model_config = ConfigDict(extra="allow")

    en: str = Field(min_length=1)
    fr: str = Field(min_length=1)
    ar: str = Field(min_length=1)


class CropItem(BaseModel):
    """Catalog entry matching `schema-v5.0.json#/$defs/CropItem` & `IMPL-016`."""

    model_config = ConfigDict(extra="allow")

    crop_id: str = Field(min_length=1)
    display_name: str | None = Field(default=None, min_length=1)
    names: CropNames
    category: CropCategory
    roles: list[CropRole] = Field(min_length=1)
    family: str = Field(min_length=1)

    @model_serializer(mode="wrap")
    def _serialize_omit_none_display_name(
        self,
        handler: SerializerFunctionWrapHandler,
    ) -> dict[str, Any]:
        # Schema defines `display_name` as optional non-null string; omit when unset.
        data: dict[str, Any] = handler(self)
        if data.get("display_name") is None:
            data.pop("display_name", None)
        return data


class MLCatalogPayload(BaseModel):
    """Upstream `GET {ML_SERVICE_URL}/v1/catalog` payload (`CropCatalog`)."""

    model_config = ConfigDict(extra="allow")

    catalog_version: str = Field(min_length=1, max_length=64)
    synced_at: datetime | None = None
    next_cursor: str | None = None
    has_more: bool | None = None
    crops: list[CropItem] = Field(min_length=1)

    @model_validator(mode="after")
    def _reject_disjoint_root_keys(self) -> MLCatalogPayload:
        extras = self.model_extra or {}
        if "fields" in extras or "field_plans" in extras:
            raise ValueError("CropCatalog payload cannot contain 'fields' or 'field_plans'.")
        return self


class CatalogPage(BaseModel):
    """Paginated `GET /api/v1/catalog` response (`openapi.yaml` `CatalogPage`)."""

    model_config = ConfigDict(extra="forbid")

    catalog_version: str
    synced_at: datetime
    items: list[CropItem]
    next_cursor: str | None = None
    has_more: bool
