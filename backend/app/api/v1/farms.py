"""Owner-scoped farm management endpoints (`/api/v1/farms`)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response, status

from app.api.deps import ActorPrincipalDep, DbSessionDep, SettingsDep
from app.core.pagination import PaginationParams, get_pagination_params
from app.schemas.farm import FarmPage, FarmPatchRequest, FarmPublic, FarmWriteRequest
from app.services import farms as farm_service

router = APIRouter(prefix="/farms", tags=["Farms"])

PaginationDep = Annotated[PaginationParams, Depends(get_pagination_params)]
FarmIdPathDep = Annotated[str, Path(pattern=r"^farm_[0-9]+$")]


@router.get(
    "",
    response_model=FarmPage,
    status_code=status.HTTP_200_OK,
    operation_id="listFarms",
)
async def list_farms(
    principal: ActorPrincipalDep,
    db: DbSessionDep,
    pagination: PaginationDep,
    country: Annotated[str | None, Query(max_length=80)] = None,
    region: Annotated[str | None, Query(max_length=80)] = None,
    search: Annotated[str | None, Query(max_length=120)] = None,
) -> FarmPage:
    """List farms owned by the caller with cursor pagination and optional filters."""
    return await farm_service.list_farms(
        db,
        principal=principal,
        pagination=pagination,
        country=country,
        region=region,
        search=search,
    )


@router.post(
    "",
    response_model=FarmPublic,
    status_code=status.HTTP_201_CREATED,
    operation_id="createFarm",
)
async def create_farm(
    payload: FarmWriteRequest,
    principal: ActorPrincipalDep,
    db: DbSessionDep,
    settings: SettingsDep,
) -> FarmPublic:
    """Create a farm owned by the caller, enforcing row-locked guest quotas."""
    return await farm_service.create_farm(
        db,
        principal=principal,
        payload=payload,
        settings=settings,
    )


@router.get(
    "/{farm_id}",
    response_model=FarmPublic,
    status_code=status.HTTP_200_OK,
    operation_id="getFarm",
)
async def get_farm(
    farm_id: FarmIdPathDep,
    principal: ActorPrincipalDep,
    db: DbSessionDep,
) -> FarmPublic:
    """Return one owned farm or `404 NOT_FOUND`."""
    return await farm_service.get_farm(db, principal=principal, farm_id=farm_id)


@router.put(
    "/{farm_id}",
    response_model=FarmPublic,
    status_code=status.HTTP_200_OK,
    operation_id="replaceFarm",
)
async def replace_farm(
    farm_id: FarmIdPathDep,
    payload: FarmWriteRequest,
    principal: ActorPrincipalDep,
    db: DbSessionDep,
) -> FarmPublic:
    """Replace an owned farm's attributes."""
    return await farm_service.replace_farm(
        db,
        principal=principal,
        farm_id=farm_id,
        payload=payload,
    )


@router.patch(
    "/{farm_id}",
    response_model=FarmPublic,
    status_code=status.HTTP_200_OK,
    operation_id="patchFarm",
)
async def patch_farm(
    farm_id: FarmIdPathDep,
    payload: FarmPatchRequest,
    principal: ActorPrincipalDep,
    db: DbSessionDep,
) -> FarmPublic:
    """Partially update an owned farm."""
    return await farm_service.patch_farm(
        db,
        principal=principal,
        farm_id=farm_id,
        payload=payload,
    )


@router.delete(
    "/{farm_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="deleteFarm",
)
async def delete_farm(
    farm_id: FarmIdPathDep,
    principal: ActorPrincipalDep,
    db: DbSessionDep,
) -> Response:
    """Delete an owned farm and cascade-delete all dependent fields and analyses."""
    await farm_service.delete_farm(db, principal=principal, farm_id=farm_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
