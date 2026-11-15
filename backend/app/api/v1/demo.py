"""Public demo zone, GeoJSON boundary, and guest session endpoints (`/api/v1/demo`)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Response, status

from app.api.deps import DbSessionDep, GuestPrincipalDep, RedisDep, SettingsDep
from app.core.pagination import PaginationParams, get_pagination_params
from app.schemas.demo import BoundaryFeature, DemoLocationPage, GuestSessionInfo
from app.services import demo as demo_service

router = APIRouter(prefix="/demo", tags=["Demo"])

PaginationDep = Annotated[PaginationParams, Depends(get_pagination_params)]


@router.get(
    "/locations",
    response_model=DemoLocationPage,
    status_code=status.HTTP_200_OK,
    operation_id="listDemoLocations",
)
async def list_demo_locations(
    pagination: PaginationDep,
    db: DbSessionDep,
) -> DemoLocationPage:
    """List active MVP demo zones (paginated via cursor/limit)."""
    return await demo_service.list_demo_locations(db, pagination=pagination)


@router.get(
    "/locations/{id}/boundary",
    response_model=BoundaryFeature,
    status_code=status.HTTP_200_OK,
    operation_id="getDemoLocationBoundary",
)
async def get_demo_location_boundary(
    id: Annotated[int, Path(ge=1)],
    db: DbSessionDep,
) -> BoundaryFeature:
    """Return GeoJSON Feature boundary (`MultiPolygon` `[lon, lat]` + `bbox`) for a demo zone."""
    return await demo_service.get_demo_location_boundary(db, demo_location_id=id)


@router.get(
    "/session",
    response_model=GuestSessionInfo,
    status_code=status.HTTP_200_OK,
    operation_id="getDemoSession",
)
async def get_demo_session(
    principal: GuestPrincipalDep,
    db: DbSessionDep,
    settings: SettingsDep,
) -> GuestSessionInfo:
    """Return guest session expiry, Guelma binding, limits, and canonical quarter usage."""
    assert principal.guest_token_hash is not None
    return await demo_service.get_guest_session_info(
        db,
        guest_token_hash=principal.guest_token_hash,
        settings=settings,
    )


@router.delete(
    "/session",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="deleteDemoSession",
)
async def delete_demo_session(
    principal: GuestPrincipalDep,
    db: DbSessionDep,
    redis_client: RedisDep,
) -> Response:
    """End guest session early and cascade-delete all guest farms, fields, and analyses."""
    assert principal.guest_token_hash is not None
    await demo_service.delete_guest_session(
        db,
        redis_client,
        guest_token_hash=principal.guest_token_hash,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
