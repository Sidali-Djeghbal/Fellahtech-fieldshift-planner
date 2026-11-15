"""Structured JSON logging with UTC timestamps and PII/secret redaction."""

from __future__ import annotations

import logging
import re
import sys
from collections.abc import MutableMapping
from typing import Any

import structlog

_REDACTED = "***REDACTED***"

_ALWAYS_SENSITIVE_KEY_PARTS: tuple[str, ...] = (
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "authorization",
    "x-ml-api-key",
    "x-guest-token",
    "input_snapshot",
    "raw_farm",
    "raw_field",
)

_INFO_PLUS_PII_KEYS: frozenset[str] = frozenset(
    {
        "email",
        "user_email",
        "full_name",
    }
)

_BEARER_RE = re.compile(r"(Bearer\s+)[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE)
_GUEST_TOKEN_RE = re.compile(r"\bgst_[0-9a-fA-F]{16,}\b")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def _is_sensitive_key(key: str, *, include_pii: bool) -> bool:
    lowered = key.lower()
    if any(part in lowered for part in _ALWAYS_SENSITIVE_KEY_PARTS):
        return True
    if include_pii and lowered in _INFO_PLUS_PII_KEYS:
        return True
    return False


def _scrub_string(value: str, *, include_pii: bool) -> str:
    scrubbed = _BEARER_RE.sub(rf"\1{_REDACTED}", value)
    scrubbed = _GUEST_TOKEN_RE.sub(f"gst_{_REDACTED}", scrubbed)
    if include_pii:
        scrubbed = _EMAIL_RE.sub(_REDACTED, scrubbed)
    return scrubbed


def _sanitize_value(value: Any, *, include_pii: bool) -> Any:
    if isinstance(value, str):
        return _scrub_string(value, include_pii=include_pii)
    if isinstance(value, dict):
        return {
            k: _REDACTED
            if _is_sensitive_key(str(k), include_pii=include_pii)
            else _sanitize_value(v, include_pii=include_pii)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_sanitize_value(item, include_pii=include_pii) for item in value]
    if isinstance(value, tuple):
        return tuple(_sanitize_value(item, include_pii=include_pii) for item in value)
    return value


def redact_sensitive_data(
    _logger: Any,
    method_name: str,
    event_dict: MutableMapping[str, Any],
) -> MutableMapping[str, Any]:
    """Structlog processor removing secrets and INFO+-level PII before serialization."""
    include_pii = method_name.lower() in {"info", "warning", "error", "critical", "exception"}
    for key in list(event_dict.keys()):
        if _is_sensitive_key(str(key), include_pii=include_pii):
            event_dict[key] = _REDACTED
        else:
            event_dict[key] = _sanitize_value(event_dict[key], include_pii=include_pii)
    return event_dict


def configure_logging(log_level: str = "INFO") -> None:
    """Configure stdlib + structlog JSON logging with UTC timestamps and redaction."""
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=numeric_level, force=True)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            redact_sensitive_data,
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        cache_logger_on_first_use=False,
    )
