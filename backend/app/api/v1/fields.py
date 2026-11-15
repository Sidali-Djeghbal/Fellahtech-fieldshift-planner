"""Owner-scoped spatial field & crop history endpoints (`/api/v1/farms/{farm_id}/fields`)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response, status

from app.api.deps import ActorPrincipalDep, DbSessionDep, SettingsDep
from app.core.pagination import PaginationParams, get_pagination_params
from app.schemas.common import SoilType, WaterAvailability
from app.schemas.field import (
    FieldDetailPublic,
    FieldPage,
    FieldPatchRequest,
    FieldPublic,
    FieldWriteRequest,
)
from app.services import fields as field_service

router = APIRouter(prefix="/farms/{farm_id}/fields", tags=["Fields"])

PaginationDep = Annotated[PaginationParams, Depends(get_pagination_params)]
FarmIdPathDep = Annotated[str, Path(pattern=r"^farm_[0-9]+$")]
FieldIdPathDep = Annotated[str, Path(min_length=1, max_length=64)]


@router.get(
    "",
    response_model=FieldPage,
    status_code=status.HTTP_200_OK,
    operation_id="listFields",
)
async def list_fields(
    farm_id: FarmIdPathDep,
    principal: ActorPrincipalDep,
    db: DbSessionDep,
    pagination: PaginationDep,
    soil_type: Annotated[SoilType | None, Query()] = None,
    water_availability: Annotated[WaterAvailability | None, Query()] = None,
) -> FieldPage:
    """List spatial parcels belonging to an owned farm."""
    return await field_service.list_fields(
        db,
        principal=principal,
        farm_id=farm_id,
        pagination=pagination,
        soil_type=soil_type,
        water_availability=water_availability,
    )


@router.post(
    "",
    response_model=FieldPublic,
    status_code=status.HTTP_201_CREATED,
    operation_id="createField",
)
async def create_field(
    farm_id: FarmIdPathDep,
    payload: FieldWriteRequest,
    principal: ActorPrincipalDep,
    db: DbSessionDep,
    settings: SettingsDep,
) -> FieldPublic:
    """Create a field inside an owned farm with PostGIS boundary gate and guest quota lock."""
    return await field_service.create_field(
        db,
        principal=principal,
        farm_id=farm_id,
        payload=payload,
        settings=settings,
    )


@router.get(
    "/{field_id}",
    response_model=FieldDetailPublic,
    status_code=status.HTTP_200_OK,
    operation_id="getField",
)
async def get_field(
    farm_id: FarmIdPathDep,
    field_id: FieldIdPathDep,
    principal: ActorPrincipalDep,
    db: DbSessionDep,
) -> FieldDetailPublic:
    """Get one field including `crop_history[]` and dynamic notices."""
    return await field_service.get_field(
        db,
        principal=principal,
        farm_id=farm_id,
        field_id=field_id,
    )


@router.put(
    "/{field_id}",
    response_model=FieldDetailPublic,
    status_code=status.HTTP_200_OK,
    operation_id="replaceField",
)
async def replace_field(
    farm_id: FarmIdPathDep,
    field_id: FieldIdPathDep,
    payload: FieldWriteRequest,
    principal: ActorPrincipalDep,
    db: DbSessionDep,
) -> FieldDetailPublic:
    """Replace an owned field and atomically rewrite its crop history."""
    return await field_service.replace_field(
        db,
        principal=principal,
        farm_id=farm_id,
        field_id=field_id,
        payload=payload,
    )


@router.patch(
    "/{field_id}",
    response_model=FieldDetailPublic,
    status_code=status.HTTP_200_OK,
    operation_id="patchField",
)
async def patch_field(
    farm_id: FarmIdPathDep,
    field_id: FieldIdPathDep,
    payload: FieldPatchRequest,
    principal: ActorPrincipalDep,
    db: DbSessionDep,
) -> FieldDetailPublic:
    """Partially update an owned field with deep validation (`IMPL-019`)."""
    return await field_service.patch_field(
        db,
        principal=principal,
        farm_id=farm_id,
        field_id=field_id,
        payload=payload,
    )


@router.delete(
    "/{field_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="deleteField",
)
async def delete_field(
    farm_id: FarmIdPathDep,
    field_id: FieldIdPathDep,
    principal: ActorPrincipalDep,
    db: DbSessionDep,
) -> Response:
    """Delete an owned field and its historical crop records."""
    await field_service.delete_field(
        db,
        principal=principal,
        farm_id=farm_id,
        field_id=field_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
