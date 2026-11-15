"""Auth, session rotation, account lifecycle, and guest-claim endpoints (`/api/v1/auth`)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Request, Response, status

from app.api.deps import (
    BearerNoRateLimitDep,
    BearerPrincipalDep,
    DbSessionDep,
    GuestNoRateLimitDep,
    RedisDep,
    SettingsDep,
    enforce_crud_rate_limit,
)
from app.core.rate_limit import (
    build_guest_create_ip_check,
    check_rate_limits,
    get_client_ip_from_request,
)
from app.schemas.auth import (
    ClaimGuestResponse,
    GuestSessionStartResponse,
    GuestStartRequest,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    TokenPairResponse,
    UserDataExport,
    UserProfile,
)
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/guest",
    response_model=GuestSessionStartResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="startGuestSession",
)
async def start_guest_session(
    request: Request,
    payload: GuestStartRequest,
    db: DbSessionDep,
    redis_client: RedisDep,
    settings: SettingsDep,
) -> GuestSessionStartResponse:
    """Create a 7-day anonymous guest session bound to Guelma MVP boundary."""
    client_ip = get_client_ip_from_request(request, settings)
    ip_check = build_guest_create_ip_check(client_ip, settings)
    await check_rate_limits(redis_client, [ip_check], fail_closed=settings.REDIS_FAIL_CLOSED)

    return await auth_service.start_guest_session(
        db,
        demo_location_id=payload.demo_location_id,
        settings=settings,
    )


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="registerUser",
)
async def register_user(
    payload: RegisterRequest,
    db: DbSessionDep,
    settings: SettingsDep,
) -> RegisterResponse:
    """Register a user account and issue access + rotating refresh tokens."""
    return await auth_service.register_user(db, payload=payload, settings=settings)


@router.post(
    "/login",
    response_model=TokenPairResponse,
    status_code=status.HTTP_200_OK,
    operation_id="loginUser",
)
async def login_user(
    payload: LoginRequest,
    db: DbSessionDep,
    settings: SettingsDep,
) -> TokenPairResponse:
    """Authenticate with email and password."""
    return await auth_service.login_user(db, payload=payload, settings=settings)


@router.post(
    "/refresh",
    response_model=TokenPairResponse,
    status_code=status.HTTP_200_OK,
    operation_id="refreshToken",
)
async def refresh_token(
    payload: RefreshRequest,
    db: DbSessionDep,
    settings: SettingsDep,
) -> TokenPairResponse:
    """Rotate refresh token and revoke entire token family on replay."""
    return await auth_service.refresh_tokens(
        db,
        raw_refresh_token=payload.refresh_token,
        settings=settings,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="logoutUser",
)
async def logout_user(
    principal: BearerPrincipalDep,
    db: DbSessionDep,
    payload: Annotated[LogoutRequest | None, Body()] = None,
) -> Response:
    """Revoke target refresh token family (`body.refresh_token` or JWT `fid`)."""
    assert principal.user_id is not None and principal.family_id is not None
    await auth_service.logout_user(
        db,
        user_id=principal.user_id,
        token_family_id=principal.family_id,
        raw_refresh_token=payload.refresh_token if payload is not None else None,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/me",
    response_model=UserProfile,
    status_code=status.HTTP_200_OK,
    operation_id="getMe",
)
async def get_me(
    principal: BearerPrincipalDep,
    db: DbSessionDep,
) -> UserProfile:
    """Return authenticated user profile."""
    assert principal.user_id is not None
    return await auth_service.get_me_profile(db, user_id=principal.user_id)


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="deleteMe",
)
async def delete_me(
    principal: BearerPrincipalDep,
    db: DbSessionDep,
) -> Response:
    """Hard-delete authenticated user account and cascade-purge all owned records."""
    assert principal.user_id is not None
    await auth_service.delete_me_account(db, user_id=principal.user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/me/export",
    response_model=UserDataExport,
    status_code=status.HTTP_200_OK,
    operation_id="exportMeData",
)
async def export_me_data(
    principal: BearerPrincipalDep,
    db: DbSessionDep,
) -> UserDataExport:
    """Export all personal data owned by the authenticated user without binary/hash fields."""
    assert principal.user_id is not None
    return await auth_service.export_me_data(db, user_id=principal.user_id)


@router.post(
    "/claim-guest",
    response_model=ClaimGuestResponse,
    status_code=status.HTTP_200_OK,
    operation_id="claimGuestSession",
)
async def claim_guest_session(
    bearer_principal: BearerNoRateLimitDep,
    guest_principal: GuestNoRateLimitDep,
    db: DbSessionDep,
    redis_client: RedisDep,
    settings: SettingsDep,
) -> ClaimGuestResponse:
    """Transfer guest farms and analysis history into authenticated account and delete session."""
    assert bearer_principal.user_id is not None and guest_principal.guest_token_hash is not None
    await enforce_crud_rate_limit(
        principal=bearer_principal,
        settings=settings,
        redis_client=redis_client,
    )
    return await auth_service.claim_guest_session(
        db,
        redis_client,
        user_id=bearer_principal.user_id,
        guest_token_hash=guest_principal.guest_token_hash,
    )
