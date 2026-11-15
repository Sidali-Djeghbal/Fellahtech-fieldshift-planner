"""Password hashing (Argon2id), HS256 dual-key JWTs, and SHA-256 token helpers."""

from __future__ import annotations

import hashlib
import re
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache

import anyio
import jwt
from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from jwt import InvalidSignatureError, PyJWTError

from app.core.config import Settings
from app.core.errors import ErrorCode, FieldShiftError

_PASSWORD_HASHER = PasswordHasher(type=Type.ID)

_EMAIL_LOCAL_RE = re.compile(
    r"^[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*$"
)
_EMAIL_LABEL_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")
_GUEST_TOKEN_RE = re.compile(r"^gst_[0-9a-f]{24}$")


@dataclass(frozen=True, slots=True)
class AccessTokenClaims:
    """Validated claims extracted from an HS256 Bearer access token."""

    user_id: int
    family_id: uuid.UUID
    expires_at: datetime
    issued_at: datetime


@lru_cache(maxsize=1)
def _dummy_password_hash() -> str:
    return _PASSWORD_HASHER.hash("fieldshift-constant-time-dummy-password")


def normalize_and_validate_email(raw_email: str) -> str:
    """Validate RFC-style email format (`<= 254` chars) and normalize to lowercase."""
    candidate = raw_email.strip()
    if not candidate or len(candidate) > 254 or any(ch.isspace() for ch in candidate):
        raise ValueError("Invalid email address format.")
    if candidate.count("@") != 1:
        raise ValueError("Invalid email address format.")

    local_part, domain_part = candidate.split("@", 1)
    if not local_part or len(local_part) > 64 or not _EMAIL_LOCAL_RE.match(local_part):
        raise ValueError("Invalid email local-part format.")

    if not domain_part or len(domain_part) > 253 or "." not in domain_part:
        raise ValueError("Invalid email domain format.")

    labels = domain_part.split(".")
    if any(not _EMAIL_LABEL_RE.match(label) for label in labels):
        raise ValueError("Invalid email domain label.")
    tld = labels[-1]
    if len(tld) < 2 or not (tld.isalpha() or tld.lower().startswith("xn--")):
        raise ValueError("Invalid email top-level domain.")

    return candidate.lower()


def hash_password(plain_password: str) -> str:
    """Hash a plaintext password using Argon2id."""
    return _PASSWORD_HASHER.hash(plain_password)


def verify_password(password_hash: str, plain_password: str) -> bool:
    """Verify a plaintext password against an Argon2id hash without raising."""
    try:
        return bool(_PASSWORD_HASHER.verify(password_hash, plain_password))
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def dummy_verify_password(plain_password: str) -> None:
    """Run an Argon2id verification against a constant dummy hash on missing users."""
    verify_password(_dummy_password_hash(), plain_password)


async def hash_password_async(plain_password: str) -> str:
    """Hash password in a worker thread so Argon2id CPU work does not block asyncio."""
    return await anyio.to_thread.run_sync(hash_password, plain_password)


async def verify_password_async(password_hash: str, plain_password: str) -> bool:
    """Verify password in a worker thread so Argon2id CPU work does not block asyncio."""
    return await anyio.to_thread.run_sync(verify_password, password_hash, plain_password)


async def dummy_verify_password_async(plain_password: str) -> None:
    """Execute constant-time missing-user password verification off the event loop."""
    await anyio.to_thread.run_sync(dummy_verify_password, plain_password)


def hash_token(raw_token: str) -> str:
    """Return lowercase 64-char SHA-256 hex digest of a raw guest or refresh token."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def generate_guest_token() -> tuple[str, str]:
    """Generate `(raw_token, token_hash)` where raw token uses `gst_<24hex>` format."""
    raw_token = f"gst_{secrets.token_hex(12)}"
    return raw_token, hash_token(raw_token)


def is_valid_guest_token_format(raw_token: str) -> bool:
    """Return True when raw guest token matches `gst_<24hex>` contract format."""
    return bool(_GUEST_TOKEN_RE.match(raw_token))


def generate_refresh_token() -> tuple[str, str]:
    """Generate opaque high-entropy `(raw_refresh_token, sha256_hex)` pair."""
    raw_token = f"rt_{secrets.token_urlsafe(40)}"
    return raw_token, hash_token(raw_token)


def create_access_token(
    *,
    user_id: int,
    family_id: uuid.UUID,
    settings: Settings,
    now: datetime | None = None,
) -> str:
    """Mint an HS256 access JWT including `sub`, `fid` (`IMPL-014`), `typ`, `iat`, and `exp`."""
    issued_at = (now or datetime.now(UTC)).astimezone(UTC)
    expires_at = issued_at + timedelta(seconds=settings.JWT_ACCESS_EXPIRES_SECONDS)
    payload = {
        "sub": str(user_id),
        "fid": str(family_id),
        "typ": "access",
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
        "jti": str(uuid.uuid4()),
    }
    encoded = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm="HS256")
    return str(encoded)


def _decode_with_secret(token: str, secret: str) -> dict[str, object]:
    payload = jwt.decode(
        token,
        secret,
        algorithms=["HS256"],
        options={
            "require": ["exp", "iat", "sub", "fid", "typ"],
            "verify_signature": True,
            "verify_exp": True,
            "verify_iat": False,
        },
    )
    if not isinstance(payload, dict):
        raise FieldShiftError(ErrorCode.UNAUTHORIZED, "Invalid access token payload.")
    return payload


def decode_access_token(token: str, settings: Settings) -> AccessTokenClaims:
    """Verify an HS256 access JWT with strict `alg=HS256` pinning and dual-key fallback."""
    if not token or not token.strip():
        raise FieldShiftError(ErrorCode.UNAUTHORIZED, "Missing access token.")

    try:
        header = jwt.get_unverified_header(token)
    except PyJWTError as exc:
        raise FieldShiftError(ErrorCode.UNAUTHORIZED, "Invalid access token.") from exc

    if header.get("alg") != "HS256":
        raise FieldShiftError(ErrorCode.UNAUTHORIZED, "Invalid access token algorithm.")

    payload: dict[str, object]
    try:
        payload = _decode_with_secret(token, settings.JWT_SECRET_KEY)
    except InvalidSignatureError as exc:
        previous_key = settings.JWT_PREVIOUS_SECRET_KEY.strip()
        if not previous_key or previous_key == settings.JWT_SECRET_KEY:
            raise FieldShiftError(
                ErrorCode.UNAUTHORIZED,
                "Invalid access token signature.",
            ) from exc
        try:
            payload = _decode_with_secret(token, previous_key)
        except PyJWTError as prev_exc:
            raise FieldShiftError(
                ErrorCode.UNAUTHORIZED,
                "Invalid or expired access token.",
            ) from prev_exc
    except PyJWTError as exc:
        raise FieldShiftError(ErrorCode.UNAUTHORIZED, "Invalid or expired access token.") from exc

    if payload.get("typ") != "access":
        raise FieldShiftError(ErrorCode.UNAUTHORIZED, "Invalid access token type.")

    try:
        raw_sub = payload["sub"]
        user_id = int(str(raw_sub))
        if user_id <= 0 or str(user_id) != str(raw_sub):
            raise ValueError("Invalid user subject claim")
        family_id = uuid.UUID(str(payload["fid"]))
        iat_ts = int(str(payload["iat"]))
        exp_ts = int(str(payload["exp"]))
    except (KeyError, ValueError, TypeError) as exc:
        raise FieldShiftError(ErrorCode.UNAUTHORIZED, "Malformed access token claims.") from exc

    return AccessTokenClaims(
        user_id=user_id,
        family_id=family_id,
        issued_at=datetime.fromtimestamp(iat_ts, tz=UTC),
        expires_at=datetime.fromtimestamp(exp_ts, tz=UTC),
    )
