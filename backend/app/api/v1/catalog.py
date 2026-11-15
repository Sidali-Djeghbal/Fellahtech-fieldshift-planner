"""Catalog REST endpoint (`GET /api/v1/catalog`)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import ActorPrincipalDep, DbSessionDep, MLProviderManagerDep
from app.core.pagination import PaginationParams, get_pagination_params
from app.schemas.catalog import CatalogPage
from app.schemas.common import CropCategory, CropRole, Language
from app.services import catalog as catalog_service

router = APIRouter(prefix="/catalog", tags=["Catalog"])

PaginationDep = Annotated[PaginationParams, Depends(get_pagination_params)]


@router.get(
    "",
    response_model=CatalogPage,
    status_code=status.HTTP_200_OK,
    operation_id="getCatalog",
)
async def get_catalog(
    _principal: ActorPrincipalDep,
    db: DbSessionDep,
    ml_manager: MLProviderManagerDep,
    pagination: PaginationDep,
    category: Annotated[CropCategory | None, Query()] = None,
    role: Annotated[CropRole | None, Query()] = None,
    lang: Annotated[Language | None, Query()] = None,
    version: Annotated[str | None, Query(min_length=1, max_length=64)] = None,
) -> CatalogPage:
    """Query paginated local `crop_catalog` with `?lang` display projection and cold-start sync."""
    return await catalog_service.get_catalog_page(
        db,
        ml_manager,
        pagination=pagination,
        category=category,
        role=role,
        lang=lang,
        version=version,
    )
