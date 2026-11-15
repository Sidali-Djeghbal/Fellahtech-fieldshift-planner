"""Auth, guest session, token pair, export, and guest claim DTOs (`openapi.yaml`)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.security import normalize_and_validate_email
from app.schemas.common import Language
from app.schemas.demo import DemoLocationSummary
from app.schemas.farm import FarmPublic
from app.schemas.field import FieldDetailPublic


class GuestStartRequest(BaseModel):
    """Request payload for `POST /api/v1/auth/guest`."""

    model_config = ConfigDict(extra="forbid")

    demo_location_id: int = Field(ge=1)


class GuestSessionStartResponse(BaseModel):
    """Response payload for `POST /api/v1/auth/guest` (`201`)."""

    model_config = ConfigDict(extra="forbid")

    guest_token: str
    expires_at: datetime
    demo_location: DemoLocationSummary


class RegisterRequest(BaseModel):
    """Request payload for `POST /api/v1/auth/register`."""

    model_config = ConfigDict(extra="forbid")

    email: str = Field(max_length=254)
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=120)
    preferred_lang: Language = Language.EN

    @field_validator("email")
    @classmethod
    def _validate_email(cls, value: str) -> str:
        return normalize_and_validate_email(value)

    @field_validator("password")
    @classmethod
    def _validate_password_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Password cannot be blank.")
        return value

    @field_validator("full_name")
    @classmethod
    def _validate_full_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned or len(cleaned) > 120:
            raise ValueError("full_name must be between 1 and 120 characters.")
        return cleaned


class LoginRequest(BaseModel):
    """Request payload for `POST /api/v1/auth/login`."""

    model_config = ConfigDict(extra="forbid")

    email: str = Field(max_length=254)
    password: str = Field(min_length=1)

    @field_validator("email")
    @classmethod
    def _validate_email(cls, value: str) -> str:
        return normalize_and_validate_email(value)


class RefreshRequest(BaseModel):
    """Request payload for `POST /api/v1/auth/refresh`."""

    model_config = ConfigDict(extra="forbid")

    refresh_token: str = Field(min_length=1)

    @field_validator("refresh_token")
    @classmethod
    def _validate_non_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("refresh_token cannot be blank.")
        return cleaned


class LogoutRequest(BaseModel):
    """Optional request payload for `POST /api/v1/auth/logout`."""

    model_config = ConfigDict(extra="forbid")

    refresh_token: str | None = None


class UserProfile(BaseModel):
    """Public user account profile (`UserProfile`, integer `id` per DI-16)."""

    model_config = ConfigDict(extra="forbid")

    id: int
    email: str
    full_name: str
    preferred_lang: Language
    created_at: datetime


class TokenPairResponse(BaseModel):
    """Issued access + rotating refresh token pair (`TokenPairResponse`)."""

    model_config = ConfigDict(extra="forbid")

    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class RegisterResponse(TokenPairResponse):
    """Account registration response (`RegisterResponse`)."""

    user: UserProfile


class ClaimGuestResponse(BaseModel):
    """Response payload for `POST /api/v1/auth/claim-guest`."""

    model_config = ConfigDict(extra="forbid")

    claimed_farms_count: int = Field(ge=0)


class UserDataExport(BaseModel):
    """Portability JSON export strictly omitting hashes and `input_snapshot_gz`."""

    model_config = ConfigDict(extra="forbid")

    exported_at: datetime
    user: UserProfile
    farms: list[FarmPublic]
    fields: list[FieldDetailPublic]
    analysis_requests: list[dict[str, Any]]
    analysis_results: list[dict[str, Any]]
    analysis_selections: list[dict[str, Any]]
