"""Cluster-wide PostgreSQL circuit breaker for External ML calls (`public.ml_breaker_state`)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.metrics import ML_BREAKER_STATE_GAUGE
from app.models.breaker import MlBreakerState

BreakerStateLiteral = Literal["closed", "open", "half_open"]

_STATE_METRIC_MAP: dict[BreakerStateLiteral, float] = {
    "closed": 0.0,
    "open": 1.0,
    "half_open": 2.0,
}

_LOGGER = structlog.get_logger(__name__)


def _ensure_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


def _normalize_state(raw: str) -> BreakerStateLiteral:
    if raw == "open":
        return "open"
    if raw == "half_open":
        return "half_open"
    return "closed"


def sync_breaker_gauge(state: BreakerStateLiteral) -> None:
    """Publish current breaker state to the Prometheus `ml_breaker_state` gauge."""
    ML_BREAKER_STATE_GAUGE.set(_STATE_METRIC_MAP[state])


@dataclass(frozen=True, slots=True)
class BreakerSnapshot:
    """Read-only view of singleton row `public.ml_breaker_state (id=1)`."""

    state: BreakerStateLiteral
    consecutive_failures: int
    opened_at: datetime | None
    half_open_probe_at: datetime | None
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class BreakerDispatchDecision:
    """Gate decision returned before dispatching a request to the External ML service."""

    allowed: bool
    state: BreakerStateLiteral
    is_half_open_probe: bool
    consecutive_failures: int
    opened_at: datetime | None


@dataclass(frozen=True, slots=True)
class BreakerTransitionResult:
    """Committed post-call transition outcome for `public.ml_breaker_state`."""

    state: BreakerStateLiteral
    consecutive_failures: int
    opened_at: datetime | None
    half_open_probe_at: datetime | None
    tripped: bool = False
    recovered: bool = False


async def _lock_breaker_singleton(
    db: AsyncSession,
    *,
    now: datetime,
) -> MlBreakerState:
    """Acquire `SELECT ... FOR UPDATE` on singleton `ml_breaker_state (id=1)`."""
    stmt = select(MlBreakerState).where(MlBreakerState.id == 1).with_for_update()
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is not None:
        return row

    current_now = _ensure_utc(now)
    seed_stmt = (
        pg_insert(MlBreakerState)
        .values(
            id=1,
            state="closed",
            consecutive_failures=0,
            opened_at=None,
            half_open_probe_at=None,
            updated_at=current_now,
        )
        .on_conflict_do_nothing(index_elements=[MlBreakerState.id])
    )
    await db.execute(seed_stmt)
    return (await db.execute(stmt)).scalar_one()


async def read_breaker_snapshot(db: AsyncSession) -> BreakerSnapshot:
    """Fetch current `ml_breaker_state (id=1)` snapshot without locking."""
    row = (
        await db.execute(select(MlBreakerState).where(MlBreakerState.id == 1))
    ).scalar_one_or_none()
    if row is None:
        now = datetime.now(UTC)
        return BreakerSnapshot(
            state="closed",
            consecutive_failures=0,
            opened_at=None,
            half_open_probe_at=None,
            updated_at=now,
        )
    return BreakerSnapshot(
        state=_normalize_state(row.state),
        consecutive_failures=int(row.consecutive_failures),
        opened_at=_ensure_utc(row.opened_at) if row.opened_at is not None else None,
        half_open_probe_at=(
            _ensure_utc(row.half_open_probe_at) if row.half_open_probe_at is not None else None
        ),
        updated_at=_ensure_utc(row.updated_at),
    )


async def acquire_breaker_dispatch(
    db: AsyncSession,
    *,
    now: datetime,
    cooldown_seconds: int,
    probe_stale_after_seconds: float,
) -> BreakerDispatchDecision:
    """Acquire breaker dispatch permission under row-level singleton lock."""
    current_now = _ensure_utc(now)
    row = await _lock_breaker_singleton(db, now=current_now)
    cur_state = _normalize_state(row.state)

    if cur_state == "closed":
        return BreakerDispatchDecision(
            allowed=True,
            state="closed",
            is_half_open_probe=False,
            consecutive_failures=int(row.consecutive_failures),
            opened_at=_ensure_utc(row.opened_at) if row.opened_at is not None else None,
        )

    if cur_state == "open":
        opened_at = _ensure_utc(row.opened_at) if row.opened_at is not None else None
        cooldown = timedelta(seconds=max(1, cooldown_seconds))
        if opened_at is None or (current_now - opened_at) >= cooldown:
            row.state = "half_open"
            row.half_open_probe_at = current_now
            row.updated_at = current_now
            return BreakerDispatchDecision(
                allowed=True,
                state="half_open",
                is_half_open_probe=True,
                consecutive_failures=int(row.consecutive_failures),
                opened_at=opened_at,
            )
        return BreakerDispatchDecision(
            allowed=False,
            state="open",
            is_half_open_probe=False,
            consecutive_failures=int(row.consecutive_failures),
            opened_at=opened_at,
        )

    # `half_open`: enforce single-flight probe unless an earlier probe has gone stale.
    probe_at = _ensure_utc(row.half_open_probe_at) if row.half_open_probe_at is not None else None
    stale_delta = timedelta(seconds=max(0.05, float(probe_stale_after_seconds)))
    if probe_at is None or (current_now - probe_at) >= stale_delta:
        row.half_open_probe_at = current_now
        row.updated_at = current_now
        return BreakerDispatchDecision(
            allowed=True,
            state="half_open",
            is_half_open_probe=True,
            consecutive_failures=int(row.consecutive_failures),
            opened_at=_ensure_utc(row.opened_at) if row.opened_at is not None else None,
        )

    return BreakerDispatchDecision(
        allowed=False,
        state="half_open",
        is_half_open_probe=False,
        consecutive_failures=int(row.consecutive_failures),
        opened_at=_ensure_utc(row.opened_at) if row.opened_at is not None else None,
    )


async def record_breaker_non_failure(
    db: AsyncSession,
    *,
    now: datetime,
    was_half_open_probe: bool,
    reset_closed_failures: bool,
) -> BreakerTransitionResult:
    """Close `half_open -> closed` on valid probe response or reset failures on `200 OK`."""
    current_now = _ensure_utc(now)
    row = await _lock_breaker_singleton(db, now=current_now)
    cur_state = _normalize_state(row.state)

    if cur_state == "half_open" and was_half_open_probe:
        row.state = "closed"
        row.consecutive_failures = 0
        row.opened_at = None
        row.half_open_probe_at = None
        row.updated_at = current_now
        return BreakerTransitionResult(
            state="closed",
            consecutive_failures=0,
            opened_at=None,
            half_open_probe_at=None,
            recovered=True,
        )

    if cur_state == "closed" and reset_closed_failures:
        if row.consecutive_failures != 0 or row.opened_at is not None:
            row.consecutive_failures = 0
            row.opened_at = None
            row.half_open_probe_at = None
            row.updated_at = current_now
        return BreakerTransitionResult(
            state="closed",
            consecutive_failures=0,
            opened_at=None,
            half_open_probe_at=None,
        )

    return BreakerTransitionResult(
        state=cur_state,
        consecutive_failures=int(row.consecutive_failures),
        opened_at=_ensure_utc(row.opened_at) if row.opened_at is not None else None,
        half_open_probe_at=(
            _ensure_utc(row.half_open_probe_at) if row.half_open_probe_at is not None else None
        ),
    )


async def record_breaker_failure(
    db: AsyncSession,
    *,
    now: datetime,
    failure_threshold: int,
    was_half_open_probe: bool,
) -> BreakerTransitionResult:
    """Increment outage failure count or reopen `half_open -> open` (`IMPL-017`)."""
    current_now = _ensure_utc(now)
    row = await _lock_breaker_singleton(db, now=current_now)
    cur_state = _normalize_state(row.state)
    threshold = max(1, failure_threshold)

    if cur_state == "half_open" or was_half_open_probe:
        # Both failed probe attempts and late half-open failures restore full cooldown (`IMPL-017`).
        row.state = "open"
        row.consecutive_failures = max(threshold, int(row.consecutive_failures) + 1)
        row.opened_at = current_now
        row.half_open_probe_at = None
        row.updated_at = current_now
        return BreakerTransitionResult(
            state="open",
            consecutive_failures=int(row.consecutive_failures),
            opened_at=current_now,
            half_open_probe_at=None,
            tripped=True,
        )

    if cur_state == "closed":
        next_failures = int(row.consecutive_failures) + 1
        row.consecutive_failures = next_failures
        row.updated_at = current_now
        if next_failures >= threshold:
            row.state = "open"
            row.opened_at = current_now
            row.half_open_probe_at = None
            return BreakerTransitionResult(
                state="open",
                consecutive_failures=next_failures,
                opened_at=current_now,
                half_open_probe_at=None,
                tripped=True,
            )
        return BreakerTransitionResult(
            state="closed",
            consecutive_failures=next_failures,
            opened_at=None,
            half_open_probe_at=None,
        )

    # Already `open`: preserve active cooldown start timestamp unless missing.
    row.consecutive_failures = int(row.consecutive_failures) + 1
    resolved_opened_at = (
        _ensure_utc(row.opened_at) if row.opened_at is not None else current_now
    )
    row.opened_at = resolved_opened_at
    row.half_open_probe_at = None
    row.updated_at = current_now
    return BreakerTransitionResult(
        state="open",
        consecutive_failures=int(row.consecutive_failures),
        opened_at=resolved_opened_at,
        half_open_probe_at=None,
    )


async def release_aborted_half_open_probe(
    db: AsyncSession,
    *,
    now: datetime,
) -> BreakerTransitionResult:
    """Release `half_open_probe_at` if a probe job cancelled/aborted before calling ML."""
    current_now = _ensure_utc(now)
    row = await _lock_breaker_singleton(db, now=current_now)
    cur_state = _normalize_state(row.state)
    if cur_state == "half_open" and row.half_open_probe_at is not None:
        row.half_open_probe_at = None
        row.updated_at = current_now
    return BreakerTransitionResult(
        state=_normalize_state(row.state),
        consecutive_failures=int(row.consecutive_failures),
        opened_at=_ensure_utc(row.opened_at) if row.opened_at is not None else None,
        half_open_probe_at=(
            _ensure_utc(row.half_open_probe_at) if row.half_open_probe_at is not None else None
        ),
    )


async def run_acquire_breaker_dispatch(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    now: datetime,
    settings: Settings,
    probe_stale_after_seconds: float | None = None,
) -> BreakerDispatchDecision:
    """Commit pre-dispatch breaker check and publish Prometheus gauge."""
    stale_s = (
        float(probe_stale_after_seconds)
        if probe_stale_after_seconds is not None
        else float(max(settings.ML_BREAKER_COOLDOWN_SECONDS, settings.JOB_LEASE_SECONDS))
    )
    async with sessionmaker() as db:
        decision = await acquire_breaker_dispatch(
            db,
            now=now,
            cooldown_seconds=settings.ML_BREAKER_COOLDOWN_SECONDS,
            probe_stale_after_seconds=stale_s,
        )
        await db.commit()
    sync_breaker_gauge(decision.state)
    if decision.state == "half_open" and decision.is_half_open_probe:
        await _LOGGER.ainfo(
            "ml_circuit_breaker_half_open_probe_started",
            consecutive_failures=decision.consecutive_failures,
        )
    return decision


async def run_record_breaker_non_failure(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    now: datetime,
    was_half_open_probe: bool,
    reset_closed_failures: bool,
) -> BreakerTransitionResult:
    """Commit breaker success / non-breaker-4xx probe recovery and update gauge."""
    async with sessionmaker() as db:
        res = await record_breaker_non_failure(
            db,
            now=now,
            was_half_open_probe=was_half_open_probe,
            reset_closed_failures=reset_closed_failures,
        )
        await db.commit()
    sync_breaker_gauge(res.state)
    if res.recovered:
        await _LOGGER.ainfo("ml_circuit_breaker_closed_recovered")
    return res


async def run_record_breaker_failure(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    now: datetime,
    failure_threshold: int,
    was_half_open_probe: bool,
) -> BreakerTransitionResult:
    """Commit breaker outage failure increment / trip and update gauge."""
    async with sessionmaker() as db:
        res = await record_breaker_failure(
            db,
            now=now,
            failure_threshold=failure_threshold,
            was_half_open_probe=was_half_open_probe,
        )
        await db.commit()
    sync_breaker_gauge(res.state)
    if res.tripped:
        await _LOGGER.aerror(
            "ml_circuit_breaker_tripped_open",
            consecutive_failures=res.consecutive_failures,
            was_half_open_probe=was_half_open_probe,
        )
    return res


async def run_release_aborted_probe(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    now: datetime,
) -> BreakerTransitionResult:
    """Commit release of an aborted half-open probe slot and update gauge."""
    async with sessionmaker() as db:
        res = await release_aborted_half_open_probe(db, now=now)
        await db.commit()
    sync_breaker_gauge(res.state)
    return res
