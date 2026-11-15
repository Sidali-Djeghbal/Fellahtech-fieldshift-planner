"""Targeted unit tests for defensive error, heartbeat, mock ML HTTP, and helper branches (`M12`)."""

from __future__ import annotations

import asyncio
import base64
import gzip
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy.exc import DataError, IntegrityError

from app.core.errors import (
    ErrorCode,
    FieldShiftError,
    _format_pydantic_errors,
    _map_http_status_to_error_code,
    register_exception_handlers,
    resolve_request_id,
)
from app.ml_client.base import MLClientError
from app.ml_client.mock_adapter import MockMLAdapter
from app.ml_client.mock_server import create_mock_ml_app
from app.models.analysis import AnalysisRequest, AnalysisSelection
from app.repositories.analysis import _is_analysis_id_unique_violation
from app.services.analysis import (
    _is_idempotency_conflict_error,
    _normalize_idempotency_key,
    _parse_warnings_json,
    _reconstruct_degraded_mode,
    _sync_guest_quarters_best_effort,
    merge_selections_into_result,
)
from app.services.fields import _translate_field_db_error
from app.services.worker_heartbeat import (
    clear_worker_heartbeat,
    count_active_workers,
    publish_worker_heartbeat,
)
from app.worker.runner import (
    _await_task_shielded_sequential,
    _release_advisory_lock_conn,
    acquire_ml_bulkhead_slot,
)

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"


class _FakeSqlOrig(Exception):
    def __init__(self, sqlstate: str, constraint_name: str | None = None) -> None:
        super().__init__(sqlstate)
        self.sqlstate = sqlstate
        self.constraint_name = constraint_name


@pytest.mark.asyncio
async def test_worker_heartbeat_defensive_branches() -> None:
    """Cover non-Redis objects, naive timestamps, multi-cursor SCAN, and Redis outages."""
    assert await publish_worker_heartbeat(None, worker_id="w1", ttl_seconds=30) is False
    await clear_worker_heartbeat(None, worker_id="w1")
    assert await count_active_workers(None) == 0

    recorded_sets: list[tuple[str, bytes, int]] = []

    class _WorkingRedis:
        async def get(self, key: str) -> bytes | None:
            del key
            return None

        async def set(self, key: str, value: bytes | str, ex: int | None = None) -> Any:
            val_b = value if isinstance(value, bytes) else value.encode("utf-8")
            recorded_sets.append((key, val_b, int(ex or 0)))
            return True

        async def delete(self, key: str) -> Any:
            del key
            return 1

        async def scan(
            self,
            *,
            cursor: int | bytes | str = 0,
            match: str | None = None,
            count: int | None = None,
        ) -> tuple[int, list[Any]]:
            del match, count
            if int(cursor) == 0:
                return 7, [b"worker:heartbeat:a"]
            return 0, ["worker:heartbeat:b"]

    naive_dt = datetime(2026, 11, 15, 12, 0, 0)  # noqa: DTZ001
    ok = await publish_worker_heartbeat(
        _WorkingRedis(), worker_id="w-naive", ttl_seconds=1, now=naive_dt
    )
    assert ok is True
    assert recorded_sets[0][0] == "worker:heartbeat:w-naive"
    assert b"+00:00" in recorded_sets[0][1]
    assert recorded_sets[0][2] == 5
    await clear_worker_heartbeat(_WorkingRedis(), worker_id="w-naive")
    assert await count_active_workers(_WorkingRedis()) == 2

    class _FailingRedis:
        async def get(self, key: str) -> bytes | None:
            del key
            return None

        async def set(self, key: str, value: bytes | str, ex: int | None = None) -> Any:
            del key, value, ex
            raise RedisConnectionError("redis set failed")

        async def delete(self, key: str) -> Any:
            del key
            raise RedisConnectionError("redis delete failed")

        async def scan(
            self,
            *,
            cursor: int | bytes | str = 0,
            match: str | None = None,
            count: int | None = None,
        ) -> tuple[int, list[Any]]:
            del cursor, match, count
            raise RedisConnectionError("redis scan failed")

    ok_fail = await publish_worker_heartbeat(_FailingRedis(), worker_id="w-err", ttl_seconds=15)
    assert ok_fail is False
    await clear_worker_heartbeat(_FailingRedis(), worker_id="w-err")
    assert await count_active_workers(_FailingRedis()) == 0


@pytest.mark.asyncio
async def test_errors_resolution_mapping_and_handler_edges() -> None:
    """Cover header request_id fallback, overlong header rejection, and status mappings."""
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/hdr-test")
    async def _hdr_endpoint(request: Request) -> JSONResponse:
        return JSONResponse({"rid": resolve_request_id(request)})

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        r_valid = await client.get("/hdr-test", headers={"x-request-id": "  req-abc-123  "})
        assert r_valid.json()["rid"] == "req-abc-123"
        r_long = await client.get("/hdr-test", headers={"x-request-id": "x" * 200})
        assert r_long.json()["rid"] is None

    assert _format_pydantic_errors(["raw-string-error"]) == [
        {"field": "", "reason": "raw-string-error", "type": "validation_error"}
    ]
    assert _map_http_status_to_error_code(415) is ErrorCode.INVALID_INPUT
    assert _map_http_status_to_error_code(502) is ErrorCode.INTERNAL_ERROR


@pytest.mark.asyncio
async def test_mock_ml_server_auth_faults_and_malformed_requests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise MockML HTTP server env keys, fault headers, gzip, and catalog/health errors."""
    f91 = json.loads((FIXTURES_DIR / "fixture_9_1_input.json").read_text(encoding="utf-8"))
    f91["request_id"] = str(uuid.uuid4())

    monkeypatch.setenv("ML_SERVICE_API_KEY", "primary-key-secret")
    monkeypatch.setenv("ML_SERVICE_PREVIOUS_API_KEY", "previous-key-secret")
    app_env_keys = create_mock_ml_app(adapter=MockMLAdapter())

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app_env_keys),
        base_url="http://mockml",
    ) as client:
        # Missing & wrong key -> 401
        r_unauth = await client.get("/v1/health")
        assert r_unauth.status_code == 401
        r_prev = await client.get("/v1/health", headers={"X-ML-API-Key": "previous-key-secret"})
        assert r_prev.status_code == 200

        # Unknown X-Mock-Fault on analyze/catalog/health -> 400
        h_ok = {"X-ML-API-Key": "primary-key-secret"}
        assert (
            await client.post(
                "/v1/analyze",
                headers={**h_ok, "X-Mock-Fault": "nonexistent_fault"},
                json=f91,
            )
        ).status_code == 400
        assert (
            await client.get("/v1/catalog", headers={**h_ok, "X-Mock-Fault": "nonexistent_fault"})
        ).status_code == 400
        assert (
            await client.get("/v1/health", headers={**h_ok, "X-Mock-Fault": "nonexistent_fault"})
        ).status_code == 400

        # Bad gzip & malformed JSON on /v1/analyze -> 400
        r_bad_gz = await client.post(
            "/v1/analyze",
            headers={**h_ok, "Content-Encoding": "gzip"},
            content=b"not-valid-gzip",
        )
        assert r_bad_gz.status_code == 400
        r_bad_json = await client.post(
            "/v1/analyze",
            headers=h_ok,
            content=b"{broken-json",
        )
        assert r_bad_json.status_code == 400

        # Valid fault mode triggers MLClientError on /v1/catalog and offline -> 503 on /v1/health
        r_cat_off = await client.get("/v1/catalog", headers={**h_ok, "X-Mock-Fault": "offline"})
        assert r_cat_off.status_code == 503
        r_hlth_off = await client.get("/v1/health")
        assert r_hlth_off.status_code == 401
        r_hlth_unreach = await client.get("/v1/health", headers=h_ok)
        assert r_hlth_unreach.status_code == 503

        # Open mode when env keys empty allows anonymous requests
        monkeypatch.setenv("ML_SERVICE_API_KEY", "")
        monkeypatch.setenv("ML_SERVICE_PREVIOUS_API_KEY", "")
        r_open = await client.get("/v1/health", headers={"X-Mock-Fault": "none"})
        assert r_open.status_code == 200

    assert MLClientError(
        "unavailable", backend_error_code=ErrorCode.ML_UNAVAILABLE, retryable=True
    ).retryable is True


def test_field_and_analysis_pure_helper_branches() -> None:
    """Cover _translate_field_db_error and pure analysis/repository helper edge paths."""
    dup_hist = IntegrityError(
        "stmt",
        {},
        _FakeSqlOrig("23505", "field_crop_history_field_id_year_season_key"),
    )
    with pytest.raises(FieldShiftError) as e_dup:
        _translate_field_db_error(dup_hist, field_id="F1")
    assert e_dup.value.code is ErrorCode.CONFLICT

    chk_err = IntegrityError("stmt", {}, _FakeSqlOrig("23514"))
    with pytest.raises(FieldShiftError) as e_chk:
        _translate_field_db_error(chk_err, field_id="F1")
    assert e_chk.value.code is ErrorCode.INVALID_INPUT

    data_err = DataError("stmt", {}, _FakeSqlOrig("22000"))
    with pytest.raises(FieldShiftError) as e_data:
        _translate_field_db_error(data_err, field_id="F1")
    assert e_data.value.code is ErrorCode.INVALID_INPUT

    other_err = IntegrityError("stmt", {}, _FakeSqlOrig("23503"))
    with pytest.raises(IntegrityError):
        _translate_field_db_error(other_err, field_id="F1")

    with pytest.raises(FieldShiftError) as e_idemp:
        _normalize_idempotency_key("   ")
    assert e_idemp.value.code is ErrorCode.INVALID_INPUT

    assert _is_idempotency_conflict_error(
        IntegrityError("stmt", {}, _FakeSqlOrig("23505", "uq_analysis_idempotency"))
    )
    assert _is_analysis_id_unique_violation(
        IntegrityError("stmt", {}, _FakeSqlOrig("23505", "uq_analysis_results_analysis_id"))
    )
    assert _parse_warnings_json("not-a-list") == []

    sel = AnalysisSelection(
        field_id="F1",
        strategy_id="S1",
        selection_status="selected",
    )
    merged = merge_selections_into_result(
        {
            "field_plans": [
                "invalid-not-dict",
                {"field_id": 123},
                {
                    "field_id": "F1",
                    "strategies": [
                        "invalid-strat",
                        {"strategy_id": None},
                        {
                            "strategy_id": "S1",
                            "seasons": [{"selection_status": "suggested"}],
                        },
                    ],
                },
            ]
        },
        [sel],
    )
    assert merged["field_plans"][2]["strategies"][2]["seasons"][0]["selection_status"] == "selected"
    assert isinstance(base64.b64decode(base64.b64encode(gzip.compress(b"{}"))), bytes)


@pytest.mark.asyncio
async def test_analysis_and_worker_async_helper_branches() -> None:
    """Cover _reconstruct_degraded_mode, _sync_guest_quarters_best_effort, and bulkhead edges."""
    req_bad_status = AnalysisRequest(
        request_id=str(uuid.uuid4()),
        farm_id=1,
        schema_version="5.0",
        catalog_version="2026.11",
        dataset_version="2026.11-guelma-v1",
        language="en",
        status="failed",
        error_code="last_good_replay:analysis_1",
        input_hash="a" * 64,
        full_input_hash="b" * 64,
        input_snapshot_gz=b"x",
        warnings=[],
    )
    req_empty_replay = AnalysisRequest(
        request_id=str(uuid.uuid4()),
        farm_id=1,
        schema_version="5.0",
        catalog_version="2026.11",
        dataset_version="2026.11-guelma-v1",
        language="en",
        status="ok",
        error_code="last_good_replay:   ",
        input_hash="a" * 64,
        full_input_hash="b" * 64,
        input_snapshot_gz=b"x",
        warnings=[],
    )
    assert await _reconstruct_degraded_mode(
        None, req=req_bad_status, now=datetime.now(UTC)  # type: ignore[arg-type]
    ) is None
    assert await _reconstruct_degraded_mode(
        None, req=req_empty_replay, now=datetime.now(UTC)  # type: ignore[arg-type]
    ) is None

    class _BoomRedis:
        async def get(self, name: str) -> bytes | None:
            del name
            return None

        async def eval(self, script: str, numkeys: int, *keys_and_args: str) -> Any:
            del script, numkeys, keys_and_args
            raise RedisConnectionError("boom")

        async def delete(self, *names: str) -> Any:
            del names
            raise RedisConnectionError("boom")

        async def ping(self) -> Any:
            return True

        async def aclose(self) -> None:
            return None

    await _sync_guest_quarters_best_effort(
        None, guest_token_hash="0" * 64, delta=4, fallback_total=4, ttl_seconds=60
    )
    await _sync_guest_quarters_best_effort(
        _BoomRedis(), guest_token_hash="0" * 64, delta=4, fallback_total=4, ttl_seconds=60
    )

    with pytest.raises(ValueError, match="max_concurrent"):
        async with acquire_ml_bulkhead_slot(None, max_concurrent=0):  # type: ignore[arg-type]
            pass

    async def _slow_cleanup() -> None:
        await asyncio.sleep(0.05)

    t = asyncio.create_task(_slow_cleanup())
    with pytest.raises(asyncio.CancelledError):
        waiter = asyncio.create_task(_await_task_shielded_sequential(t))
        await asyncio.sleep(0.01)
        waiter.cancel()
        await waiter
    assert t.done()

    class _FakeConn:
        def __init__(self) -> None:
            self.invalidated = False
            self.closed = False

        async def execute(self, sql: Any, params: Any = None) -> Any:
            del sql, params
            raise RuntimeError("unlock failed")

        async def invalidate(self) -> None:
            self.invalidated = True

        async def close(self) -> None:
            self.closed = True

    conn = _FakeConn()
    await _release_advisory_lock_conn(
        conn, unlock_sql="SELECT 1", unlock_params={"slot": 1001}  # type: ignore[arg-type]
    )
    assert conn.invalidated is True and conn.closed is True
