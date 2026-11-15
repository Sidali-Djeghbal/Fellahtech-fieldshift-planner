"""Asyncio worker runner: SKIP LOCKED claims, advisory bulkhead `1001..1008`, cancel & retries."""

from __future__ import annotations

import asyncio
import contextlib
import gzip
import json
import random
import signal
import time
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.errors import ErrorCode
from app.core.logging import configure_logging
from app.core.metrics import (
    ANALYSIS_REQUESTS_TOTAL,
    ML_REQUEST_DURATION_SECONDS,
    WORKER_ACTIVE_LEASES,
    WORKER_BULKHEAD_INFLIGHT,
)
from app.core.rate_limit import AsyncRedisLike, create_redis_client, sync_guest_quota_after_refund
from app.db.session import create_db_engine, create_sessionmaker, pinned_connection
from app.ml_client.base import MLClientError
from app.ml_client.manager import AsyncRedisStatusStore, MLProviderManager
from app.repositories import analysis as analysis_repo
from app.repositories import catalog as catalog_repo
from app.worker.jobs import (
    DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
    GZIP_COMPRESS_THRESHOLD_BYTES,
    PayloadTrimError,
    ResultVerifier,
    RetryBudgetState,
    classify_ml_error_policy,
    extract_payload_crop_ids,
    serialize_compact_json,
    trim_analysis_payload_for_size,
    verify_analysis_result_basic,
)

BULKHEAD_START_SLOT = 1001
_DEFAULT_BULKHEAD_PROBE_INTERVAL_S = 0.05
_DEFAULT_POLL_INTERVAL_S = 0.5
_DEFAULT_REAP_INTERVAL_S = 15.0
_CATALOG_SYNC_LOCK_ID_SQL = "hashtext('catalog_sync')"
_REAPER_LOCK_ID_SQL = "hashtext('reaper')"

_TRY_SLOT_LOCK_SQL = text("SELECT pg_try_advisory_lock(:slot)")
_UNLOCK_SLOT_LOCK_SQL = text("SELECT pg_advisory_unlock(:slot)")
_TRY_CATALOG_SYNC_LOCK_SQL = text(f"SELECT pg_try_advisory_lock({_CATALOG_SYNC_LOCK_ID_SQL})")
_UNLOCK_CATALOG_SYNC_LOCK_SQL = text(f"SELECT pg_advisory_unlock({_CATALOG_SYNC_LOCK_ID_SQL})")
_TRY_REAPER_LOCK_SQL = text(f"SELECT pg_try_advisory_lock({_REAPER_LOCK_ID_SQL})")
_UNLOCK_REAPER_LOCK_SQL = text(f"SELECT pg_advisory_unlock({_REAPER_LOCK_ID_SQL})")


@dataclass(frozen=True, slots=True)
class JobExecutionSummary:
    """Compact execution outcome returned by `WorkerRunner` for tests & logs."""

    request_id: str
    outcome: str
    analysis_id: str | None = None
    error_code: str | None = None
    refunded_quarters: int = 0
    bulkhead_slot: int | None = None
    retries_used: int = 0


async def _await_task_shielded_sequential(coro_task: asyncio.Task[None]) -> None:
    """Finish a single sequential cleanup task without concurrent connection operations."""
    pending_cancel: asyncio.CancelledError | None = None
    while not coro_task.done():
        try:
            await asyncio.shield(coro_task)
        except asyncio.CancelledError as exc:
            pending_cancel = exc
    if pending_cancel is not None:
        raise pending_cancel


async def _release_advisory_lock_conn(
    conn: AsyncConnection,
    *,
    unlock_sql: Any,
    unlock_params: dict[str, Any] | None,
) -> None:
    """Unlock PostgreSQL session advisory lock cleanly or invalidate socket on failure."""

    async def _cleanup() -> None:
        unlocked = False
        try:
            res = await asyncio.wait_for(
                conn.execute(unlock_sql, unlock_params or {}),
                timeout=2.0,
            )
            unlocked = bool(res.scalar_one())
        except BaseException:
            unlocked = False
        try:
            if not unlocked:
                await conn.invalidate()
        finally:
            with contextlib.suppress(BaseException):
                await conn.close()

    cleanup_task: asyncio.Task[None] = asyncio.create_task(_cleanup())
    await _await_task_shielded_sequential(cleanup_task)


@asynccontextmanager
async def acquire_ml_bulkhead_slot(
    engine: AsyncEngine,
    *,
    max_concurrent: int,
    start_slot: int = BULKHEAD_START_SLOT,
    probe_interval_seconds: float = _DEFAULT_BULKHEAD_PROBE_INTERVAL_S,
) -> AsyncIterator[int]:
    """Pin one DB session holding `pg_try_advisory_lock(1001..1000+N)` across ML HTTP+sleeps."""
    if max_concurrent < 1:
        raise ValueError("max_concurrent must be >= 1")
    slots = [start_slot + offset for offset in range(max_concurrent)]

    while True:
        offset = random.randrange(len(slots))
        ordered_slots = slots[offset:] + slots[:offset]

        lock_conn = await engine.connect()
        acquired_slot: int | None = None
        try:
            for candidate in ordered_slots:
                row_val = (await lock_conn.execute(_TRY_SLOT_LOCK_SQL, {"slot": candidate}))
                if bool(row_val.scalar_one()):
                    acquired_slot = candidate
                    break
        except BaseException:
            await _release_advisory_lock_conn(
                lock_conn,
                unlock_sql=_UNLOCK_SLOT_LOCK_SQL,
                unlock_params={"slot": acquired_slot},
            )
            raise

        if acquired_slot is None:
            await lock_conn.close()
            await asyncio.sleep(probe_interval_seconds)
            continue

        WORKER_BULKHEAD_INFLIGHT.inc()
        try:
            yield acquired_slot
        finally:
            WORKER_BULKHEAD_INFLIGHT.dec()
            await _release_advisory_lock_conn(
                lock_conn,
                unlock_sql=_UNLOCK_SLOT_LOCK_SQL,
                unlock_params={"slot": acquired_slot},
            )
        return


async def sync_catalog_under_advisory_lock(
    *,
    engine: AsyncEngine,
    sessionmaker: async_sessionmaker[AsyncSession],
    ml_manager: MLProviderManager,
    rejected_version: str | None = None,
    max_wait_seconds: float = 3.0,
) -> str | None:
    """Acquire `pg_try_advisory_lock(hashtext('catalog_sync'))`, sync `/v1/catalog`, & unlock."""
    deadline = time.monotonic() + max_wait_seconds
    async with pinned_connection(engine) as lock_conn:
        acquired = False
        while True:
            acquired = bool((await lock_conn.execute(_TRY_CATALOG_SYNC_LOCK_SQL)).scalar_one())
            if acquired or time.monotonic() >= deadline:
                break
            await asyncio.sleep(0.1)

        if not acquired:
            async with sessionmaker() as db:
                latest = await catalog_repo.get_latest_catalog_version_meta(db)
            return latest[0] if latest is not None else None

        try:
            async with sessionmaker() as check_db:
                latest_before = await catalog_repo.get_latest_catalog_version_meta(check_db)
            if (
                rejected_version is not None
                and latest_before is not None
                and latest_before[0] != rejected_version
            ):
                return latest_before[0]

            payload = await ml_manager.get_catalog()
            async with sessionmaker() as write_db:
                synced_version = await catalog_repo.upsert_catalog_and_prune(
                    write_db,
                    payload=payload,
                    synced_at=datetime.now(UTC),
                    retain_versions=2,
                )
                await write_db.commit()
            return synced_version
        finally:
            unlock_task: asyncio.Task[None] = asyncio.create_task(
                _unlock_catalog_sync_best_effort(lock_conn)
            )
            await _await_task_shielded_sequential(unlock_task)


async def _unlock_catalog_sync_best_effort(lock_conn: AsyncConnection) -> None:
    unlocked = False
    try:
        res = await asyncio.wait_for(lock_conn.execute(_UNLOCK_CATALOG_SYNC_LOCK_SQL), timeout=2.0)
        unlocked = bool(res.scalar_one())
    except BaseException:
        unlocked = False
    if not unlocked:
        with contextlib.suppress(BaseException):
            await lock_conn.invalidate()


class WorkerRunner:
    """Multi-slot asyncio worker implementing `W2` claim, bulkhead, cancel, retries & reaper."""

    def __init__(
        self,
        *,
        settings: Settings,
        engine: AsyncEngine,
        sessionmaker: async_sessionmaker[AsyncSession],
        redis_client: AsyncRedisLike | None,
        ml_manager: MLProviderManager,
        verifier: ResultVerifier | None = None,
        worker_concurrency: int | None = None,
        heartbeat_interval_seconds: float = DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
        poll_interval_seconds: float = _DEFAULT_POLL_INTERVAL_S,
        reap_interval_seconds: float = _DEFAULT_REAP_INTERVAL_S,
        bulkhead_probe_interval_seconds: float = _DEFAULT_BULKHEAD_PROBE_INTERVAL_S,
        jitter_fn: Callable[[], float] | None = None,
    ) -> None:
        self._settings = settings
        self._engine = engine
        self._sessionmaker = sessionmaker
        self._redis_client = redis_client
        self._ml_manager = ml_manager
        self._verifier: ResultVerifier = verifier or verify_analysis_result_basic
        self._concurrency = (
            worker_concurrency if worker_concurrency is not None else settings.WORKER_CONCURRENCY
        )
        self._heartbeat_interval_s = heartbeat_interval_seconds
        self._poll_interval_s = poll_interval_seconds
        self._reap_interval_s = reap_interval_seconds
        self._bulkhead_probe_interval_s = bulkhead_probe_interval_seconds
        self._jitter_fn = jitter_fn
        self._logger = structlog.get_logger("app.worker.runner")

    async def _sync_redis_refund_if_needed(
        self,
        *,
        guest_token_hash: str | None,
        refunded_quarters: int,
    ) -> None:
        if guest_token_hash is not None and refunded_quarters > 0:
            await sync_guest_quota_after_refund(
                self._redis_client,
                guest_token_hash=guest_token_hash,
                delta=refunded_quarters,
            )

    async def _finalize_failure(
        self,
        *,
        request_id: str,
        error_code: ErrorCode,
        start_monotonic: float,
        provider_name: str,
        bulkhead_slot: int | None = None,
        retries_used: int = 0,
        stop_heartbeat: asyncio.Event | None = None,
    ) -> JobExecutionSummary:
        now = datetime.now(UTC)
        duration_ms = int((time.monotonic() - start_monotonic) * 1000)
        async with self._sessionmaker() as db:
            fin = await analysis_repo.finalize_worker_failure(
                db,
                request_id=request_id,
                error_code=error_code,
                duration_ms=duration_ms,
                max_guest_ml_refunds=self._settings.GUEST_MAX_ML_REFUNDS,
                now=now,
            )
            if stop_heartbeat is not None:
                stop_heartbeat.set()
            await db.commit()

        await self._sync_redis_refund_if_needed(
            guest_token_hash=fin.guest_token_hash,
            refunded_quarters=fin.refunded_quarters,
        )
        if fin.outcome == "cancelled":
            ANALYSIS_REQUESTS_TOTAL.labels(status="cancelled", error_code="none").inc()
            ML_REQUEST_DURATION_SECONDS.labels(provider=provider_name, outcome="cancelled").observe(
                max(0.0, time.monotonic() - start_monotonic)
            )
        elif fin.outcome == "failed":
            ANALYSIS_REQUESTS_TOTAL.labels(status="failed", error_code=error_code.value).inc()
            ML_REQUEST_DURATION_SECONDS.labels(provider=provider_name, outcome="failed").observe(
                max(0.0, time.monotonic() - start_monotonic)
            )
        return JobExecutionSummary(
            request_id=request_id,
            outcome=fin.outcome,
            error_code=fin.final_error_code,
            refunded_quarters=fin.refunded_quarters,
            bulkhead_slot=bulkhead_slot,
            retries_used=retries_used,
        )

    async def _finalize_cancelled(
        self,
        *,
        request_id: str,
        start_monotonic: float,
        provider_name: str,
        bulkhead_slot: int | None = None,
        retries_used: int = 0,
        stop_heartbeat: asyncio.Event | None = None,
    ) -> JobExecutionSummary:
        async with self._sessionmaker() as db:
            fin = await analysis_repo.finalize_worker_cancelled(
                db,
                request_id=request_id,
            )
            if stop_heartbeat is not None:
                stop_heartbeat.set()
            await db.commit()

        await self._sync_redis_refund_if_needed(
            guest_token_hash=fin.guest_token_hash,
            refunded_quarters=fin.refunded_quarters,
        )
        if fin.outcome == "cancelled":
            ANALYSIS_REQUESTS_TOTAL.labels(status="cancelled", error_code="none").inc()
            ML_REQUEST_DURATION_SECONDS.labels(provider=provider_name, outcome="cancelled").observe(
                max(0.0, time.monotonic() - start_monotonic)
            )
        return JobExecutionSummary(
            request_id=request_id,
            outcome=fin.outcome,
            refunded_quarters=fin.refunded_quarters,
            bulkhead_slot=bulkhead_slot,
            retries_used=retries_used,
        )

    async def _heartbeat_watcher(
        self,
        *,
        request_id: str,
        stop_event: asyncio.Event,
        cancel_requested: asyncio.Event,
        job_task: asyncio.Task[JobExecutionSummary],
        lease_refreshed_at: list[float],
    ) -> None:
        while not stop_event.is_set():
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=self._heartbeat_interval_s)
                return
            except TimeoutError:
                pass

            if stop_event.is_set():
                return
            async with self._sessionmaker() as db:
                still_running, cancelled_at = await analysis_repo.heartbeat_and_check_cancel(
                    db,
                    request_id=request_id,
                    now=datetime.now(UTC),
                    lease_seconds=self._settings.JOB_LEASE_SECONDS,
                )
                await db.commit()
            if stop_event.is_set():
                return
            if not still_running or cancelled_at is not None:
                cancel_requested.set()
                job_task.cancel()
                return
            lease_refreshed_at[0] = time.monotonic()

    async def _execute_job_body(
        self,
        *,
        request_id: str,
        start_monotonic: float,
        lease_refreshed_at: list[float],
        stop_heartbeat: asyncio.Event,
    ) -> JobExecutionSummary:
        provider_name = self._ml_manager.active_provider_name
        async with self._sessionmaker() as db:
            loaded = await analysis_repo.get_job_dispatch_row(db, request_id=request_id)
        if loaded is None:
            stop_heartbeat.set()
            return JobExecutionSummary(request_id=request_id, outcome="vanished")

        req_snapshot, _ = loaded
        if req_snapshot.cancelled_at is not None:
            return await self._finalize_cancelled(
                request_id=request_id,
                start_monotonic=start_monotonic,
                provider_name=provider_name,
                stop_heartbeat=stop_heartbeat,
            )
        if req_snapshot.status != "running":
            stop_heartbeat.set()
            return JobExecutionSummary(request_id=request_id, outcome="skipped")

        try:
            if req_snapshot.input_snapshot_gz is None:
                raise ValueError("Missing input_snapshot_gz")
            raw_json_str = gzip.decompress(req_snapshot.input_snapshot_gz).decode("utf-8")
            parsed_raw = json.loads(raw_json_str)
            if not isinstance(parsed_raw, dict):
                raise ValueError("Decompressed input snapshot is not a JSON object")
            input_snapshot: dict[str, Any] = parsed_raw
        except (OSError, ValueError, UnicodeDecodeError):
            await self._logger.aerror("worker_corrupt_input_snapshot", request_id=request_id)
            return await self._finalize_failure(
                request_id=request_id,
                error_code=ErrorCode.INTERNAL_ERROR,
                start_monotonic=start_monotonic,
                provider_name=provider_name,
                stop_heartbeat=stop_heartbeat,
            )

        payload_to_send: dict[str, Any] = dict(input_snapshot)
        payload_bytes = serialize_compact_json(payload_to_send)
        if len(payload_bytes) > self._settings.ML_MAX_PAYLOAD_BYTES:
            try:
                trimmed = trim_analysis_payload_for_size(
                    payload_to_send,
                    max_bytes=self._settings.ML_MAX_PAYLOAD_BYTES,
                )
                payload_to_send = trimmed.payload
                payload_bytes = trimmed.raw_bytes
                await self._logger.awarning(
                    "ml_payload_pretrimmed",
                    request_id=request_id,
                    trimmed_entries=trimmed.trimmed_entries,
                    trimmed_bytes=len(payload_bytes),
                )
            except PayloadTrimError:
                await self._logger.aerror(
                    "ml_payload_untrimmable_before_dispatch",
                    request_id=request_id,
                    payload_bytes=len(payload_bytes),
                )
                return await self._finalize_failure(
                    request_id=request_id,
                    error_code=ErrorCode.INTERNAL_ERROR,
                    start_monotonic=start_monotonic,
                    provider_name=provider_name,
                    stop_heartbeat=stop_heartbeat,
                )

        async with acquire_ml_bulkhead_slot(
            self._engine,
            max_concurrent=self._settings.ML_MAX_CONCURRENT_REQUESTS,
            probe_interval_seconds=self._bulkhead_probe_interval_s,
        ) as bulkhead_slot:
            async with self._sessionmaker() as dispatch_db:
                action, refunded, tok = await analysis_repo.lock_and_mark_dispatched(
                    dispatch_db,
                    request_id=request_id,
                    now=datetime.now(UTC),
                )
                await dispatch_db.commit()

            if action == "cancelled":
                stop_heartbeat.set()
                await self._sync_redis_refund_if_needed(
                    guest_token_hash=tok,
                    refunded_quarters=refunded,
                )
                ANALYSIS_REQUESTS_TOTAL.labels(status="cancelled", error_code="none").inc()
                return JobExecutionSummary(
                    request_id=request_id,
                    outcome="cancelled",
                    refunded_quarters=refunded,
                    bulkhead_slot=bulkhead_slot,
                )
            if action != "proceed":
                stop_heartbeat.set()
                return JobExecutionSummary(
                    request_id=request_id,
                    outcome="skipped",
                    bulkhead_slot=bulkhead_slot,
                )

            retries_used = RetryBudgetState()
            raw_result: dict[str, Any] | None = None

            while True:
                provider_name = self._ml_manager.active_provider_name
                try:
                    raw_result = await self._ml_manager.analyze(
                        payload_bytes,
                        idempotency_key=request_id,
                        compress=len(payload_bytes) >= GZIP_COMPRESS_THRESHOLD_BYTES,
                    )
                    break
                except MLClientError as exc:
                    elapsed_since_hb = max(0.0, time.monotonic() - lease_refreshed_at[0])
                    remaining_lease = max(
                        0.0, float(self._settings.JOB_LEASE_SECONDS) - elapsed_since_hb
                    )
                    decision = classify_ml_error_policy(
                        exc,
                        settings=self._settings,
                        remaining_lease_seconds=remaining_lease,
                        retries_used=retries_used,
                        jitter_fn=self._jitter_fn,
                    )
                    if decision.action == "retry_backoff":
                        retries_used.transient_retries_used += 1
                        delay = decision.delay_seconds or 0.0
                        await self._logger.awarning(
                            "ml_request_retrying",
                            request_id=request_id,
                            ml_error_code=exc.ml_error_code,
                            delay_seconds=delay,
                        )
                        await asyncio.sleep(delay)
                        continue

                    if decision.action == "retry_rate_limit":
                        retries_used.rate_limit_retries_used += 1
                        delay = decision.delay_seconds or 0.0
                        await self._logger.awarning(
                            "ml_rate_limited_retrying",
                            request_id=request_id,
                            delay_seconds=delay,
                        )
                        await asyncio.sleep(delay)
                        continue

                    if decision.action == "retry_catalog_sync":
                        retries_used.catalog_sync_retries_used += 1
                        synced_version = await self._handle_catalog_mismatch_sync(
                            payload_to_send=payload_to_send
                        )
                        if synced_version is None:
                            return await self._finalize_failure(
                                request_id=request_id,
                                error_code=ErrorCode.CATALOG_VERSION_MISMATCH,
                                start_monotonic=start_monotonic,
                                provider_name=provider_name,
                                bulkhead_slot=bulkhead_slot,
                                retries_used=self._total_retries(retries_used),
                                stop_heartbeat=stop_heartbeat,
                            )
                        payload_to_send = dict(payload_to_send)
                        payload_to_send["catalog_version"] = synced_version
                        payload_bytes = serialize_compact_json(payload_to_send)
                        continue

                    if decision.action == "retry_trim_payload":
                        retries_used.payload_trim_retries_used += 1
                        try:
                            trimmed = trim_analysis_payload_for_size(
                                payload_to_send,
                                max_bytes=self._settings.ML_MAX_PAYLOAD_BYTES,
                                force_shrink=True,
                            )
                            payload_to_send = trimmed.payload
                            payload_bytes = trimmed.raw_bytes
                            await self._logger.awarning(
                                "ml_payload_trimmed_after_413",
                                request_id=request_id,
                                trimmed_entries=trimmed.trimmed_entries,
                                trimmed_bytes=len(payload_bytes),
                            )
                            continue
                        except PayloadTrimError:
                            await self._logger.aerror(
                                "ml_payload_413_untrimmable",
                                request_id=request_id,
                            )
                            return await self._finalize_failure(
                                request_id=request_id,
                                error_code=ErrorCode.INTERNAL_ERROR,
                                start_monotonic=start_monotonic,
                                provider_name=provider_name,
                                bulkhead_slot=bulkhead_slot,
                                retries_used=self._total_retries(retries_used),
                                stop_heartbeat=stop_heartbeat,
                            )

                    log_fn = (
                        self._logger.acritical if decision.critical_alert else self._logger.awarning
                    )
                    await log_fn(
                        "ml_request_failed_terminal",
                        request_id=request_id,
                        backend_error_code=decision.backend_error_code.value,
                        ml_error_code=exc.ml_error_code,
                        status_code=exc.status_code,
                        trips_breaker=decision.trips_breaker,
                    )
                    return await self._finalize_failure(
                        request_id=request_id,
                        error_code=decision.backend_error_code,
                        start_monotonic=start_monotonic,
                        provider_name=provider_name,
                        bulkhead_slot=bulkhead_slot,
                        retries_used=self._total_retries(retries_used),
                        stop_heartbeat=stop_heartbeat,
                    )

            assert raw_result is not None
            verification = await self._verifier(
                raw_result,
                expected_dataset_version=req_snapshot.dataset_version,
                input_snapshot=input_snapshot,
            )
            raw_ds_used = raw_result.get("dataset_version_used")
            raw_eng_ver = raw_result.get("ml_engine_version")
            ds_used = (
                str(raw_ds_used) if isinstance(raw_ds_used, str) and raw_ds_used else "unknown"
            )
            eng_ver = (
                str(raw_eng_ver) if isinstance(raw_eng_ver, str) and raw_eng_ver else "unknown"
            )

            duration_ms = int((time.monotonic() - start_monotonic) * 1000)
            catalog_ver_used = (
                str(payload_to_send["catalog_version"])
                if payload_to_send.get("catalog_version") != req_snapshot.catalog_version
                else None
            )
            async with self._sessionmaker() as fin_db:
                fin = await analysis_repo.finalize_worker_success(
                    fin_db,
                    request_id=request_id,
                    result_status=verification.result_status,
                    dataset_version_used=ds_used,
                    ml_engine_version=eng_ver,
                    result_json=raw_result,
                    validation_passed=verification.valid,
                    validation_errors=verification.validation_errors,
                    failure_error_code=verification.error_code,
                    duration_ms=duration_ms,
                    catalog_version_used=catalog_ver_used,
                    max_guest_ml_refunds=self._settings.GUEST_MAX_ML_REFUNDS,
                    now=datetime.now(UTC),
                )
                stop_heartbeat.set()
                await fin_db.commit()

            await self._sync_redis_refund_if_needed(
                guest_token_hash=fin.guest_token_hash,
                refunded_quarters=fin.refunded_quarters,
            )

            if fin.outcome == "cancelled":
                ANALYSIS_REQUESTS_TOTAL.labels(status="cancelled", error_code="none").inc()
            elif fin.outcome == "completed":
                ANALYSIS_REQUESTS_TOTAL.labels(
                    status=fin.final_status or verification.result_status,
                    error_code="none",
                ).inc()
                ML_REQUEST_DURATION_SECONDS.labels(
                    provider=provider_name,
                    outcome=fin.final_status or verification.result_status,
                ).observe(max(0.0, time.monotonic() - start_monotonic))
            elif fin.outcome == "failed":
                err_val = fin.final_error_code or ErrorCode.ML_INVALID_RESPONSE.value
                ANALYSIS_REQUESTS_TOTAL.labels(status="failed", error_code=err_val).inc()
                ML_REQUEST_DURATION_SECONDS.labels(
                    provider=provider_name, outcome="failed"
                ).observe(max(0.0, time.monotonic() - start_monotonic))

            return JobExecutionSummary(
                request_id=request_id,
                outcome=fin.outcome,
                analysis_id=fin.analysis_id,
                error_code=fin.final_error_code,
                refunded_quarters=fin.refunded_quarters,
                bulkhead_slot=bulkhead_slot,
                retries_used=self._total_retries(retries_used),
            )

    @staticmethod
    def _total_retries(state: RetryBudgetState) -> int:
        return (
            state.transient_retries_used
            + state.rate_limit_retries_used
            + state.catalog_sync_retries_used
            + state.payload_trim_retries_used
        )

    async def _handle_catalog_mismatch_sync(
        self,
        *,
        payload_to_send: dict[str, Any],
    ) -> str | None:
        rejected_version = str(payload_to_send.get("catalog_version", ""))
        try:
            synced_version = await sync_catalog_under_advisory_lock(
                engine=self._engine,
                sessionmaker=self._sessionmaker,
                ml_manager=self._ml_manager,
                rejected_version=rejected_version or None,
            )
        except MLClientError as exc:
            await self._logger.awarning(
                "worker_409_catalog_sync_failed",
                ml_error_code=exc.ml_error_code,
            )
            return None

        if synced_version is None:
            return None

        crop_ids = extract_payload_crop_ids(payload_to_send)
        if crop_ids:
            async with self._sessionmaker() as db:
                missing = await catalog_repo.find_missing_crop_ids(
                    db,
                    catalog_version=synced_version,
                    crop_ids=crop_ids,
                )
            if missing:
                await self._logger.awarning(
                    "worker_409_catalog_crops_invalid_after_sync",
                    catalog_version=synced_version,
                    missing_crop_ids=missing,
                )
                return None
        return synced_version

    async def execute_claimed_job(self, request_id: str) -> JobExecutionSummary:
        """Execute an already-claimed job with cooperative heartbeat cancel & clean unlock."""
        start_monotonic = time.monotonic()
        lease_refreshed_at = [start_monotonic]
        cancel_requested = asyncio.Event()
        stop_heartbeat = asyncio.Event()
        WORKER_ACTIVE_LEASES.inc()

        job_task: asyncio.Task[JobExecutionSummary] = asyncio.create_task(
            self._execute_job_body(
                request_id=request_id,
                start_monotonic=start_monotonic,
                lease_refreshed_at=lease_refreshed_at,
                stop_heartbeat=stop_heartbeat,
            )
        )
        hb_task: asyncio.Task[None] = asyncio.create_task(
            self._heartbeat_watcher(
                request_id=request_id,
                stop_event=stop_heartbeat,
                cancel_requested=cancel_requested,
                job_task=job_task,
                lease_refreshed_at=lease_refreshed_at,
            )
        )

        try:
            return await job_task
        except asyncio.CancelledError:
            if cancel_requested.is_set() and not stop_heartbeat.is_set():
                return await self._finalize_cancelled(
                    request_id=request_id,
                    start_monotonic=start_monotonic,
                    provider_name=self._ml_manager.active_provider_name,
                    stop_heartbeat=stop_heartbeat,
                )
            if not job_task.done():
                job_task.cancel()
                with contextlib.suppress(BaseException):
                    await job_task
            raise
        finally:
            stop_heartbeat.set()
            if not hb_task.done():
                hb_task.cancel()
            with contextlib.suppress(BaseException):
                await hb_task
            WORKER_ACTIVE_LEASES.dec()

    async def run_once(self) -> JobExecutionSummary | None:
        """Atomically claim one pending/stale job via `SKIP LOCKED` and process it."""
        now = datetime.now(UTC)
        async with self._sessionmaker() as db:
            request_id = await analysis_repo.claim_next_analysis_job(
                db,
                now=now,
                lease_seconds=self._settings.JOB_LEASE_SECONDS,
                max_attempts=self._settings.MAX_JOB_ATTEMPTS,
            )
            await db.commit()
        if request_id is None:
            return None
        return await self.execute_claimed_job(request_id)

    async def drain_until_idle(
        self,
        *,
        max_jobs: int | None = None,
    ) -> list[JobExecutionSummary]:
        """Execute queued jobs sequentially until none are claimable or `max_jobs` reached."""
        outcomes: list[JobExecutionSummary] = []
        while max_jobs is None or len(outcomes) < max_jobs:
            summary = await self.run_once()
            if summary is None:
                break
            outcomes.append(summary)
        return outcomes

    async def reap_stale_jobs_once(self) -> int:
        """Leader-elected sweep failing exhausted leases (`attempts >= MAX`) or dead cancels."""
        async with pinned_connection(self._engine) as lock_conn:
            acquired = bool((await lock_conn.execute(_TRY_REAPER_LOCK_SQL)).scalar_one())
            if not acquired:
                return 0
            try:
                now = datetime.now(UTC)
                async with self._sessionmaker() as read_db:
                    candidates = await analysis_repo.list_reaper_stale_candidates(
                        read_db,
                        now=now,
                        max_attempts=self._settings.MAX_JOB_ATTEMPTS,
                    )

                swept = 0
                for rid, is_cancelled in candidates:
                    async with self._sessionmaker() as write_db:
                        if is_cancelled:
                            fin = await analysis_repo.finalize_worker_cancelled(
                                write_db,
                                request_id=rid,
                                require_stale_before=now,
                            )
                        else:
                            fin = await analysis_repo.finalize_worker_failure(
                                write_db,
                                request_id=rid,
                                error_code=ErrorCode.INTERNAL_ERROR,
                                duration_ms=0,
                                max_guest_ml_refunds=self._settings.GUEST_MAX_ML_REFUNDS,
                                now=now,
                                require_stale_before=now,
                            )
                        await write_db.commit()

                    await self._sync_redis_refund_if_needed(
                        guest_token_hash=fin.guest_token_hash,
                        refunded_quarters=fin.refunded_quarters,
                    )
                    if fin.outcome in ("cancelled", "failed"):
                        swept += 1
                        if fin.outcome == "cancelled":
                            ANALYSIS_REQUESTS_TOTAL.labels(
                                status="cancelled", error_code="none"
                            ).inc()
                        else:
                            ANALYSIS_REQUESTS_TOTAL.labels(
                                status="failed",
                                error_code=fin.final_error_code or ErrorCode.INTERNAL_ERROR.value,
                            ).inc()
                return swept
            finally:
                with contextlib.suppress(BaseException):
                    await lock_conn.execute(_UNLOCK_REAPER_LOCK_SQL)

    async def _worker_loop(self, worker_slot: int, stop_event: asyncio.Event) -> None:
        await self._logger.ainfo("worker_slot_started", worker_slot=worker_slot)
        try:
            while not stop_event.is_set():
                try:
                    processed = await self.run_once()
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    await self._logger.aexception(
                        "worker_loop_iteration_failed",
                        worker_slot=worker_slot,
                        error_type=type(exc).__name__,
                    )
                    processed = None

                if processed is None:
                    with contextlib.suppress(TimeoutError):
                        await asyncio.wait_for(stop_event.wait(), timeout=self._poll_interval_s)
        finally:
            await self._logger.ainfo("worker_slot_stopped", worker_slot=worker_slot)

    async def _publish_provider_status_best_effort(self) -> None:
        status_store = (
            self._redis_client
            if isinstance(self._redis_client, AsyncRedisStatusStore)
            else None
        )
        await self._ml_manager.refresh_provider_status(
            publish_redis=status_store is not None,
            redis_client=status_store,
        )

    async def _maintenance_loop(self, stop_event: asyncio.Event) -> None:
        last_catalog_sync = 0.0
        catalog_interval_s = float(self._settings.ML_CATALOG_SYNC_HOURS * 3600)
        while not stop_event.is_set():
            with contextlib.suppress(Exception):
                await self._publish_provider_status_best_effort()
            with contextlib.suppress(Exception):
                await self.reap_stale_jobs_once()

            now_mono = time.monotonic()
            if (now_mono - last_catalog_sync) >= catalog_interval_s:
                with contextlib.suppress(Exception):
                    await sync_catalog_under_advisory_lock(
                        engine=self._engine,
                        sessionmaker=self._sessionmaker,
                        ml_manager=self._ml_manager,
                        max_wait_seconds=0.1,
                    )
                last_catalog_sync = now_mono

            wait_s = min(
                self._reap_interval_s,
                float(self._settings.ML_HEALTH_CHECK_INTERVAL_SECONDS),
            )
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop_event.wait(), timeout=wait_s)

    async def run(self, stop_event: asyncio.Event | None = None) -> None:
        """Start concurrent worker pool and maintenance loops until `stop_event` is set."""
        active_stop = stop_event or asyncio.Event()
        with contextlib.suppress(Exception):
            await self._publish_provider_status_best_effort()

        tasks: list[asyncio.Task[None]] = [
            asyncio.create_task(self._worker_loop(idx, active_stop))
            for idx in range(self._concurrency)
        ]
        tasks.append(asyncio.create_task(self._maintenance_loop(active_stop)))

        try:
            await active_stop.wait()
        finally:
            active_stop.set()
            await asyncio.gather(*tasks, return_exceptions=True)


async def run_worker_service(settings: Settings | None = None) -> None:
    """Standalone CLI entrypoint powering `python -m app.worker.runner`."""
    cfg = settings if settings is not None else Settings()
    configure_logging()
    engine = create_db_engine(cfg, role="worker")
    sessionmaker = create_sessionmaker(engine)
    redis_client = create_redis_client(cfg)
    ml_manager = MLProviderManager(cfg, redis_client=redis_client)

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig_name in ("SIGINT", "SIGTERM"):
        sig = getattr(signal, sig_name, None)
        if sig is not None:
            with contextlib.suppress(NotImplementedError):
                loop.add_signal_handler(sig, stop_event.set)

    runner = WorkerRunner(
        settings=cfg,
        engine=engine,
        sessionmaker=sessionmaker,
        redis_client=redis_client,
        ml_manager=ml_manager,
    )
    try:
        await runner.run(stop_event)
    finally:
        await ml_manager.aclose()
        await redis_client.aclose()
        await engine.dispose()


def main() -> int:
    try:
        asyncio.run(run_worker_service())
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
