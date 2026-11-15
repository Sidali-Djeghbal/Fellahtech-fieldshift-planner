"""Unit tests for Argon2id password hashing, dual-key HS256 JWTs, and token digests."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.config import Settings
from app.core.errors import ErrorCode, FieldShiftError
from app.core.security import (
    create_access_token,
    decode_access_token,
    generate_guest_token,
    generate_refresh_token,
    hash_password,
    hash_token,
    is_valid_guest_token_format,
    normalize_and_validate_email,
    verify_password,
)


def _security_settings(*, previous_key: str = "") -> Settings:
    return Settings(
        _env_file=None,
        APP_ENV="test",
        DATABASE_URL="postgresql+asyncpg://fieldshift:secret@db:5432/fieldshift",
        DB_PASSWORD="secret",
        ML_DATASET_DB_URL="postgresql://ml_reader:secret2@db:5432/fieldshift",
        ML_READER_PASSWORD="secret2",
        JWT_SECRET_KEY="current-jwt-secret-key-at-least-48-bytes-long-ok!",
        JWT_PREVIOUS_SECRET_KEY=previous_key,
        JWT_ACCESS_EXPIRES_SECONDS=3600,
        ML_SERVICE_API_KEY="ml-secret-key",
    )


def test_argon2id_hashing_and_verification() -> None:
    pw_hash = hash_password("AgronomyPass!2026")
    assert pw_hash.startswith("$argon2id$")
    assert verify_password(pw_hash, "AgronomyPass!2026") is True
    assert verify_password(pw_hash, "WrongPassword!2026") is False
    assert verify_password("not-a-valid-argon2-hash", "AgronomyPass!2026") is False


def test_email_normalization_and_validation() -> None:
    assert normalize_and_validate_email("  Amina.Benali@Example.DZ  ") == "amina.benali@example.dz"

    invalid_emails = [
        "",
        "plainaddress",
        "missingdomain@",
        "@missinglocal.dz",
        "two@@example.dz",
        "space user@example.dz",
        "bad@localhost",
        "user@.invalid.dz",
        f"{'a' * 250}@example.dz",
    ]
    for bad in invalid_emails:
        with pytest.raises(ValueError):
            normalize_and_validate_email(bad)


def test_token_hashing_and_guest_format() -> None:
    raw_guest, guest_hash = generate_guest_token()
    assert is_valid_guest_token_format(raw_guest) is True
    assert len(guest_hash) == 64
    assert hash_token(raw_guest) == guest_hash

    raw_refresh, refresh_hash = generate_refresh_token()
    assert raw_refresh != refresh_hash
    assert len(refresh_hash) == 64
    assert hash_token(raw_refresh) == refresh_hash


def test_jwt_issuance_fid_claim_and_dual_key_rotation() -> None:
    prev_secret = "previous-jwt-secret-key-at-least-32b!!"
    curr_settings = _security_settings(previous_key=prev_secret)
    prev_only_settings = Settings(
        _env_file=None,
        APP_ENV="test",
        DATABASE_URL=curr_settings.DATABASE_URL,
        DB_PASSWORD=curr_settings.DB_PASSWORD,
        ML_DATASET_DB_URL=curr_settings.ML_DATASET_DB_URL,
        ML_READER_PASSWORD=curr_settings.ML_READER_PASSWORD,
        JWT_SECRET_KEY=prev_secret,
        JWT_PREVIOUS_SECRET_KEY="",
        ML_SERVICE_API_KEY="ml-secret-key",
    )

    fid = uuid.uuid4()
    token_curr = create_access_token(user_id=42, family_id=fid, settings=curr_settings)
    claims_curr = decode_access_token(token_curr, curr_settings)
    assert claims_curr.user_id == 42
    assert claims_curr.family_id == fid

    # Token minted before secret rotation still validates under JWT_PREVIOUS_SECRET_KEY.
    token_old = create_access_token(user_id=99, family_id=fid, settings=prev_only_settings)
    claims_rotated = decode_access_token(token_old, curr_settings)
    assert claims_rotated.user_id == 99
    assert claims_rotated.family_id == fid

    # Disabling JWT_PREVIOUS_SECRET_KEY invalidates tokens signed with old key immediately.
    no_prev_settings = _security_settings(previous_key="")
    with pytest.raises(FieldShiftError) as exc_info:
        decode_access_token(token_old, no_prev_settings)
    assert exc_info.value.code is ErrorCode.UNAUTHORIZED
    assert exc_info.value.status_code == 401


def test_jwt_rejects_alg_none_wrong_alg_expired_and_malformed_claims() -> None:
    settings = _security_settings(previous_key="previous-jwt-secret-key-at-least-32b!!")
    fid = str(uuid.uuid4())
    now = datetime.now(UTC)

    unsigned_none = jwt.encode(
        {
            "sub": "12",
            "fid": fid,
            "typ": "access",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
        },
        "",
        algorithm="none",
    )
    wrong_alg = jwt.encode(
        {
            "sub": "12",
            "fid": fid,
            "typ": "access",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
        },
        settings.JWT_SECRET_KEY,
        algorithm="HS384",
    )
    expired = create_access_token(
        user_id=12,
        family_id=uuid.UUID(fid),
        settings=settings,
        now=now - timedelta(hours=2),
    )
    wrong_typ = jwt.encode(
        {
            "sub": "12",
            "fid": fid,
            "typ": "refresh",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
        },
        settings.JWT_SECRET_KEY,
        algorithm="HS256",
    )
    bad_sub = jwt.encode(
        {
            "sub": "not-an-int",
            "fid": fid,
            "typ": "access",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
        },
        settings.JWT_SECRET_KEY,
        algorithm="HS256",
    )

    for candidate in ("", "not.a.jwt", unsigned_none, wrong_alg, expired, wrong_typ, bad_sub):
        with pytest.raises(FieldShiftError) as exc_info:
            decode_access_token(candidate, settings)
        assert exc_info.value.code is ErrorCode.UNAUTHORIZED
        assert exc_info.value.status_code == 401
