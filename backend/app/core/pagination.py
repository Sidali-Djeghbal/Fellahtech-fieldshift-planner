"""Opaque URL-safe Base64 keyset cursor pagination utilities."""

from __future__ import annotations

import base64
import binascii
import json
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import Query

from app.core.errors import ErrorCode, FieldShiftError

MAX_CURSOR_LENGTH = 512
DEFAULT_PAGE_LIMIT = 20
MAX_PAGE_LIMIT = 100


@dataclass(frozen=True, slots=True)
class PaginationParams:
    """Validated query parameters matching OpenAPI LimitParam & CursorParam."""

    limit: int = DEFAULT_PAGE_LIMIT
    cursor: str | None = None


def get_pagination_params(
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_LIMIT)] = DEFAULT_PAGE_LIMIT,
    cursor: Annotated[str | None, Query(min_length=1, max_length=MAX_CURSOR_LENGTH)] = None,
) -> PaginationParams:
    """FastAPI dependency validating `limit` (1..100, default 20) and optional `cursor`."""
    return PaginationParams(limit=limit, cursor=cursor)


def encode_cursor(payload: Mapping[str, Any]) -> str:
    """Encode a keyset cursor payload into an unpadded URL-safe Base64 string."""
    raw_json = json.dumps(dict(payload), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw_json).decode("ascii").rstrip("=")


def decode_cursor(
    cursor: str,
    *,
    required_keys: Iterable[str] = (),
) -> dict[str, Any]:
    """Decode and validate an opaque Base64 cursor, raising 400 INVALID_INPUT on tampering."""
    if not cursor or len(cursor) > MAX_CURSOR_LENGTH:
        raise FieldShiftError(
            ErrorCode.INVALID_INPUT,
            "Invalid pagination cursor.",
            details=[{"field": "cursor", "reason": "malformed_cursor"}],
        )
    try:
        cursor.encode("ascii")
        padded = cursor + "=" * (-len(cursor) % 4)
        decoded_bytes = base64.urlsafe_b64decode(padded.encode("ascii"))
        # Reject non-canonical base64url strings containing padding/whitespace garbage.
        reencoded = base64.urlsafe_b64encode(decoded_bytes).decode("ascii").rstrip("=")
        if reencoded != cursor.rstrip("="):
            raise ValueError("non-canonical base64url cursor")
        parsed = json.loads(decoded_bytes.decode("utf-8"))
    except (UnicodeError, binascii.Error, ValueError, json.JSONDecodeError) as exc:
        raise FieldShiftError(
            ErrorCode.INVALID_INPUT,
            "Invalid pagination cursor.",
            details=[{"field": "cursor", "reason": "malformed_cursor"}],
        ) from exc

    if not isinstance(parsed, dict):
        raise FieldShiftError(
            ErrorCode.INVALID_INPUT,
            "Invalid pagination cursor.",
            details=[{"field": "cursor", "reason": "malformed_cursor"}],
        )

    for key in required_keys:
        if key not in parsed:
            raise FieldShiftError(
                ErrorCode.INVALID_INPUT,
                "Invalid pagination cursor.",
                details=[{"field": "cursor", "reason": "missing_cursor_key"}],
            )
    return parsed


def slice_keyset_page[T](
    rows: Sequence[T],
    *,
    limit: int,
    cursor_key_fn: Callable[[T], Mapping[str, Any]],
) -> tuple[list[T], str | None, bool]:
    """Split a `limit + 1` query batch into `(items, next_cursor, has_more)`."""
    has_more = len(rows) > limit
    items = list(rows[:limit])
    next_cursor = encode_cursor(cursor_key_fn(items[-1])) if has_more and items else None
    return items, next_cursor, has_more
