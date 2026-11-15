"""Unit and wire-level HTTP tests for M6 MLClient adapters, error mapping, and Mock ML server."""

from __future__ import annotations

import asyncio
import contextlib
import copy
import json
import socket
from pathlib import Path
from typing import Any

import httpx
import pytest
import uvicorn

from app.core.config import Settings
from app.core.errors import ErrorCode
from app.ml_client import (
    MLAuthError,
    MLCatalogVersionMismatchError,
    MLContractError,
    MLDatasetError,
    MLDatasetVersionUnavailableError,
    MLInsufficientDataError,
    MLInvalidPayloadError,
    MLPayloadTooLargeError,
    MLRateLimitError,
    MLTimeoutError,
    MLTransportError,
    MLUpstreamServerError,
    MockMLAdapter,
    RealMLAdapter,
    classify_ml_http_error,
    parse_retry_after_header,
    validate_contract_def,
)
from app.ml_client.mock_server import create_mock_ml_app

BACKEND_DIR = Path(__file__).resolve().parents[2]
APP_FIXTURES_DIR = BACKEND_DIR / "app" / "ml_client" / "fixtures"
TEST_FIXTURES_DIR = BACKEND_DIR / "tests" / "fixtures"


def _ml_settings(
    *,
    base_url: str = "http://mock-ml.local:8090",
    api_key: str = "primary-ml-key",
    previous_api_key: str = "",
    timeout_s: int = 5,
) -> Settings:
    return Settings(
        _env_file=None,
        APP_ENV="test",
        DATABASE_URL="postgresql+asyncpg://fieldshift:secret@db:5432/fieldshift",
        DB_PASSWORD="secret",
        ML_DATASET_DB_URL="postgresql://ml_reader:secret2@db:5432/fieldshift",
        ML_READER_PASSWORD="secret2",
        JWT_SECRET_KEY="jwt-secret-key-for-tests-32-chars!!",
        ML_SERVICE_URL=base_url,
        ML_SERVICE_API_KEY=api_key,
        ML_SERVICE_PREVIOUS_API_KEY=previous_api_key,
        ML_TIMEOUT_SECONDS=timeout_s,
        ML_CATALOG_TIMEOUT_SECONDS=timeout_s,
        ML_HEALTH_TIMEOUT_SECONDS=max(1, min(timeout_s, 3)),
    )


def test_parse_retry_after_header() -> None:
    assert parse_retry_after_header(None) is None
    assert parse_retry_after_header("") is None
    assert parse_retry_after_header("abc") is None
    assert parse_retry_after_header("-3") is None
    assert parse_retry_after_header("Wed, 21 Oct 2026 07:28:00 GMT") is None
    assert parse_retry_after_header("0") == 0
    assert parse_retry_after_header("  12 ") == 12


@pytest.mark.parametrize(
    (
        "status_code",
        "body",
        "retry_after",
        "expected_exc",
        "expected_backend_code",
        "expected_retryable",
        "expected_trips_breaker",
    ),
    [
        (
            400,
            {"error": {"code": "INVALID_INPUT", "message": "Bad JSON"}},
            None,
            MLContractError,
            ErrorCode.ML_CONTRACT_ERROR,
            False,
            False,
        ),
        (
            401,
            {"error": {"code": "AUTH_FAILED", "message": "Invalid key"}},
            None,
            MLAuthError,
            ErrorCode.ML_UNAVAILABLE,
            False,
            False,
        ),
        (
            403,
            {"error": {"code": "FORBIDDEN", "message": "Forbidden key"}},
            None,
            MLAuthError,
            ErrorCode.ML_UNAVAILABLE,
            False,
            False,
        ),
        (
            409,
            {"error": {"code": "CATALOG_VERSION_MISMATCH"}},
            None,
            MLCatalogVersionMismatchError,
            ErrorCode.CATALOG_VERSION_MISMATCH,
            True,
            False,
        ),
        (
            409,
            {"error": {"code": "DATASET_VERSION_UNAVAILABLE"}},
            None,
            MLDatasetVersionUnavailableError,
            ErrorCode.DATASET_VERSION_UNAVAILABLE,
            False,
            False,
        ),
        (
            413,
            {"error": {"code": "PAYLOAD_TOO_LARGE"}},
            None,
            MLPayloadTooLargeError,
            ErrorCode.INTERNAL_ERROR,
            True,
            False,
        ),
        (
            422,
            {"error": {"code": "INSUFFICIENT_DATA"}},
            None,
            MLInsufficientDataError,
            ErrorCode.INSUFFICIENT_DATA,
            False,
            False,
        ),
        (
            422,
            {"error": {"code": "DATASET_VERSION_UNAVAILABLE"}},
            None,
            MLDatasetVersionUnavailableError,
            ErrorCode.DATASET_VERSION_UNAVAILABLE,
            False,
            False,
        ),
        (
            429,
            {"error": {"code": "RATE_LIMITED"}},
            "3",
            MLRateLimitError,
            ErrorCode.ML_UNAVAILABLE,
            True,
            False,
        ),
        (
            500,
            {"error": {"code": "ML_DATASET_ERROR"}},
            None,
            MLDatasetError,
            ErrorCode.ML_DATASET_ERROR,
            False,
            True,
        ),
        (
            502,
            {"code": "ML_DATASET_ERROR", "message": "Dataset schema offline"},
            None,
            MLDatasetError,
            ErrorCode.ML_DATASET_ERROR,
            False,
            True,
        ),
        (
            500,
            {"error": {"code": "INTERNAL_ERROR"}},
            None,
            MLUpstreamServerError,
            ErrorCode.ML_UNAVAILABLE,
            True,
            True,
        ),
        (
            503,
            {"error": {"code": "OVERLOADED"}},
            "7",
            MLUpstreamServerError,
            ErrorCode.ML_UNAVAILABLE,
            True,
            True,
        ),
        (
            418,
            {"detail": "Teapot"},
            None,
            MLContractError,
            ErrorCode.ML_CONTRACT_ERROR,
            False,
            False,
        ),
    ],
)
def test_classify_ml_http_error_b10_4_matrix(
    status_code: int,
    body: Any,
    retry_after: str | None,
    expected_exc: type[Exception],
    expected_backend_code: ErrorCode,
    expected_retryable: bool,
    expected_trips_breaker: bool,
) -> None:
    err = classify_ml_http_error(
        status_code,
        body=body,
        retry_after_header=retry_after,
    )
    assert isinstance(err, expected_exc)
    assert err.backend_error_code == expected_backend_code
    assert err.retryable is expected_retryable
    assert err.trips_breaker is expected_trips_breaker
    if retry_after is not None:
        assert err.retry_after_seconds == int(retry_after)


def test_app_ml_client_fixtures_match_test_fixtures() -> None:
    for filename in ("fixture_9_3_output.json", "fixture_9_4_catalog.json"):
        app_payload = json.loads((APP_FIXTURES_DIR / filename).read_text(encoding="utf-8"))
        test_payload = json.loads((TEST_FIXTURES_DIR / filename).read_text(encoding="utf-8"))
        assert app_payload == test_payload


@pytest.mark.asyncio
async def test_mock_ml_adapter_dynamic_analysis_and_catalog_validation() -> None:
    base_input: dict[str, Any] = json.loads(
        (TEST_FIXTURES_DIR / "fixture_9_1_input.json").read_text(encoding="utf-8")
    )
    second_field = copy.deepcopy(base_input["fields"][0])
    second_field["field_id"] = "F2"
    second_field["field_name"] = "South Orchard Ridge"
    second_field["soil"]["soil_type"] = "clay"
    second_field["soil"]["soil_ph"] = 7.4
    second_field["soil"]["organic_matter_percent"] = 2.1
    second_field["water"]["availability"] = "high"

    custom_input = copy.deepcopy(base_input)
    custom_input["request_id"] = "77777777-8888-4999-8aaa-bbbbbbbbbbbb"
    custom_input["language"] = "fr"
    custom_input["planning"]["start_season"] = "autumn"
    custom_input["planning"]["start_year"] = 2027
    custom_input["planning"]["horizon_seasons"] = 6
    custom_input["planning"]["cycle_mode"] = "double_cropping"
    custom_input["planning"]["planting_month"] = 10
    custom_input["priorities"]["target_crop_ids"] = ["chickpea", "barley", "saffron"]
    custom_input["priorities"]["excluded_crop_ids"] = ["barley"]
    custom_input["fields"].append(second_field)

    adapter = MockMLAdapter()
    result = await adapter.analyze(custom_input, idempotency_key="idem-test-1")

    schema_errors = validate_contract_def(result, "AnalysisResult")
    assert schema_errors == []
    assert result["request_id"] == "77777777-8888-4999-8aaa-bbbbbbbbbbbb"
    assert result["dataset_version_used"] == custom_input["dataset_version"]
    assert result["language"] == "fr"
    assert len(result["field_plans"]) == 2

    fp2 = result["field_plans"][1]
    assert fp2["field_id"] == "F2"
    assert fp2["field_name"] == "South Orchard Ridge"
    for strategy in fp2["strategies"]:
        assert len(strategy["seasons"]) == 6
        assert strategy["seasons"][0]["season"] == "autumn"
        assert strategy["seasons"][0]["planting_month"] == 10
        if not strategy["is_existing_rotation"]:
            assert all(slot["crop_id"] != "barley" for slot in strategy["seasons"])
        evidence = strategy["explanation"]["evidence"]
        soil_ev = [e for e in evidence if e.get("parameter") == "soil_type"]
        water_ev = [e for e in evidence if e.get("parameter") == "water_availability"]
        if soil_ev:
            assert soil_ev[0]["observed_value"] == "clay"
        if water_ev:
            assert water_ev[0]["observed_value"] == "high"

    outcomes = {
        item["requested_crop_id"]: item["outcome"] for item in fp2["requested_crop_results"]
    }
    assert outcomes["chickpea"] == "included"
    assert outcomes["barley"] == "excluded"
    assert outcomes["saffron"] == "replaced"

    catalog = await adapter.get_catalog()
    assert catalog.catalog_version == "2026.11"
    assert len(catalog.crops) == 6
    health = await adapter.get_health()
    assert health.reachable is True
    assert health.provider == "mock_ml"


@pytest.mark.asyncio
async def test_mock_ml_adapter_all_fault_modes_and_fifo_sequence() -> None:
    sample_input = json.loads(
        (TEST_FIXTURES_DIR / "fixture_9_1_input.json").read_text(encoding="utf-8")
    )
    adapter = MockMLAdapter()

    with pytest.raises(ValueError, match="Unsupported mock ML fault mode"):
        adapter.set_fault_mode("nonexistent_mode")
    with pytest.raises(ValueError, match="Unsupported mock ML fault mode"):
        adapter.set_fault_sequence(["timeout", "bad_mode"])

    exception_modes: list[tuple[str, type[Exception]]] = [
        ("http_400", MLContractError),
        ("http_401", MLAuthError),
        ("http_409_catalog", MLCatalogVersionMismatchError),
        ("http_409_dataset", MLDatasetVersionUnavailableError),
        ("http_413", MLPayloadTooLargeError),
        ("http_422_dataset", MLDatasetVersionUnavailableError),
        ("http_422_insufficient", MLInsufficientDataError),
        ("http_429", MLRateLimitError),
        ("http_500", MLUpstreamServerError),
        ("http_503", MLUpstreamServerError),
        ("ml_dataset_error", MLDatasetError),
        ("timeout", MLTimeoutError),
        ("offline", MLTransportError),
        ("unavailable", MLTransportError),
        ("corrupt_json", MLInvalidPayloadError),
    ]
    for mode, exc_type in exception_modes:
        adapter.set_fault_mode(mode, retry_after_seconds=4)
        with pytest.raises(exc_type) as exc_info:
            await adapter.analyze(sample_input, idempotency_key="fault-test")
        if mode == "http_429":
            assert getattr(exc_info.value, "retry_after_seconds", None) == 4

    adapter.set_fault_mode("wrong_dataset_version")
    mismatched = await adapter.analyze(sample_input, idempotency_key="mismatch")
    assert mismatched["dataset_version_used"] == "2026.11-guelma-v1-mismatched"

    adapter.set_fault_mode("extra_fields_5_1")
    upgraded = await adapter.analyze(sample_input, idempotency_key="v51")
    assert upgraded["schema_version"] == "5.1"
    assert upgraded["extra_tolerant_reader_metadata"] == {"mock_minor_upgrade": True}

    adapter.set_fault_mode("schema_6_0")
    v6 = await adapter.analyze(sample_input, idempotency_key="v60")
    assert v6["schema_version"] == "6.0"

    # FIFO sequence consumes queued items then reverts to steady-state `none`.
    adapter.set_fault_mode("none")
    adapter.set_fault_sequence(["timeout", "http_503", "none"])
    with pytest.raises(MLTimeoutError):
        await adapter.analyze(sample_input, idempotency_key="seq-1")
    with pytest.raises(MLUpstreamServerError):
        await adapter.analyze(sample_input, idempotency_key="seq-2")
    ok_result = await adapter.analyze(sample_input, idempotency_key="seq-3")
    assert ok_result["schema_version"] == "5.0"

    adapter.set_fault_mode("offline")
    offline_health = await adapter.get_health()
    assert offline_health.reachable is False
    assert offline_health.status == "unavailable"


@pytest.mark.asyncio
async def test_real_ml_adapter_against_mock_server_asgi_wire_contract() -> None:
    sample_input = json.loads(
        (TEST_FIXTURES_DIR / "fixture_9_1_input.json").read_text(encoding="utf-8")
    )
    mock_app = create_mock_ml_app(accepted_api_keys=["rotated-old-key"])

    # Verify primary key rejection + single retry via ML_SERVICE_PREVIOUS_API_KEY succeeds.
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=mock_app),
        base_url="http://mock-ml.local:8090",
    ) as client:
        rotating_adapter = RealMLAdapter(
            _ml_settings(
                api_key="brand-new-primary-key",
                previous_api_key="rotated-old-key",
            ),
            client=client,
        )
        health = await rotating_adapter.get_health()
        assert health.reachable is True
        assert "2026.11-guelma-v1" in health.dataset_versions_supported

        gzip_result = await rotating_adapter.analyze(
            sample_input,
            idempotency_key="req-gzip-1",
            compress=True,
        )
        assert validate_contract_def(gzip_result, "AnalysisResult") == []

        # Enable multi-page catalog responses (2 crops per page across 6 crops = 3 pages).
        mock_app.state.catalog_page_size = 2
        catalog = await rotating_adapter.get_catalog()
        assert len(catalog.crops) == 6
        assert catalog.has_more is False
        assert catalog.next_cursor is None

        # Inject corrupt_json and upstream faults through mock_server.
        mock_app.state.mock_adapter.set_fault_mode("corrupt_json")
        with pytest.raises(MLInvalidPayloadError):
            await rotating_adapter.analyze(sample_input, idempotency_key="corrupt-1")

        mock_app.state.mock_adapter.set_fault_mode("ml_dataset_error")
        with pytest.raises(MLDatasetError) as err_ds:
            await rotating_adapter.analyze(sample_input, idempotency_key="ds-err")
        assert err_ds.value.trips_breaker is True

        mock_app.state.mock_adapter.set_fault_mode("http_429", retry_after_seconds=3)
        with pytest.raises(MLRateLimitError) as err_rl:
            await rotating_adapter.analyze(sample_input, idempotency_key="rl-err")
        assert err_rl.value.retry_after_seconds == 3

        mock_app.state.mock_adapter.set_fault_mode("offline")
        unhealthy = await rotating_adapter.get_health()
        assert unhealthy.reachable is False
        assert unhealthy.status == "unavailable"

        # Verify double authentication failure raises MLAuthError without further retries.
        bad_key_adapter = RealMLAdapter(
            _ml_settings(api_key="wrong-1", previous_api_key="wrong-2"),
            client=client,
        )
        with pytest.raises(MLAuthError):
            await bad_key_adapter.analyze(sample_input, idempotency_key="bad-auth")
        bad_health = await bad_key_adapter.get_health()
        assert bad_health.reachable is False
        assert bad_health.error == "AUTH_FAILED"


@pytest.mark.asyncio
async def test_real_ml_adapter_catalog_pagination_and_schema_guards() -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert request.headers.get("X-ML-API-Key") == "primary-ml-key"
        base_crop = {
            "crop_id": "durum_wheat",
            "names": {"en": "Durum Wheat", "fr": "Ble dur", "ar": "قمح"},
            "category": "cereals",
            "roles": ["main_crop"],
            "family": "Poaceae",
        }
        mode = request.headers.get("X-Test-Scenario", "repeat_cursor")
        if mode == "bad_schema":
            return httpx.Response(200, json={"schema_version": "5.0", "crops": []})
        if mode == "version_drift":
            cursor = request.url.params.get("cursor")
            ver = "2026.11" if cursor is None else "2026.12"
            return httpx.Response(
                200,
                json={
                    "schema_version": "5.0",
                    "catalog_version": ver,
                    "crops": [base_crop],
                    "next_cursor": "c1" if cursor is None else None,
                    "has_more": cursor is None,
                },
            )
        return httpx.Response(
            200,
            json={
                "schema_version": "5.0",
                "catalog_version": "2026.11",
                "crops": [base_crop],
                "next_cursor": "same-cursor",
                "has_more": True,
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://mock-ml.local",
        headers={"X-Test-Scenario": "repeat_cursor"},
    ) as client:
        adapter = RealMLAdapter(_ml_settings(), client=client)
        with pytest.raises(MLInvalidPayloadError, match="repeating pagination cursor"):
            await adapter.get_catalog()
        assert calls == 2

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://mock-ml.local",
        headers={"X-Test-Scenario": "version_drift"},
    ) as client:
        adapter = RealMLAdapter(_ml_settings(), client=client)
        with pytest.raises(MLInvalidPayloadError, match="distinct catalog versions"):
            await adapter.get_catalog()

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://mock-ml.local",
        headers={"X-Test-Scenario": "bad_schema"},
    ) as client:
        adapter = RealMLAdapter(_ml_settings(), client=client)
        with pytest.raises(MLInvalidPayloadError, match="failed schema validation"):
            await adapter.get_catalog()


@pytest.mark.asyncio
async def test_real_ml_adapter_live_tcp_uvicorn_loopback_and_timeout() -> None:
    sample_input = json.loads(
        (TEST_FIXTURES_DIR / "fixture_9_1_input.json").read_text(encoding="utf-8")
    )
    mock_app = create_mock_ml_app(accepted_api_keys=["tcp-ml-key"])
    mock_app.state.catalog_page_size = 4

    @mock_app.middleware("http")
    async def _delay_middleware(request: Any, call_next: Any) -> Any:
        if request.headers.get("X-Slow-Test") == "1":
            await asyncio.sleep(1.3)
        return await call_next(request)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    sock.setblocking(False)
    port = int(sock.getsockname()[1])

    config = uvicorn.Config(mock_app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    serve_task = asyncio.create_task(server.serve(sockets=[sock]))
    try:
        while not server.started:
            await asyncio.sleep(0.01)

        base_url = f"http://127.0.0.1:{port}"
        adapter = RealMLAdapter(_ml_settings(base_url=base_url, api_key="tcp-ml-key"))
        try:
            health = await adapter.get_health()
            assert health.reachable is True
            assert health.provider == "real_ml"

            catalog = await adapter.get_catalog()
            assert len(catalog.crops) == 6

            result = await adapter.analyze(
                sample_input,
                idempotency_key="tcp-loopback-1",
                compress=True,
            )
            assert validate_contract_def(result, "AnalysisResult") == []

            # Simulate real TCP socket read timeout -> MLTimeoutError.
            slow_client = httpx.AsyncClient(
                base_url=base_url,
                headers={"X-Slow-Test": "1"},
            )
            try:
                slow_adapter = RealMLAdapter(
                    _ml_settings(base_url=base_url, api_key="tcp-ml-key", timeout_s=1),
                    client=slow_client,
                )
                with pytest.raises(MLTimeoutError):
                    await slow_adapter.analyze(sample_input, idempotency_key="timeout-tcp")
            finally:
                await slow_client.aclose()

            # Simulate connection refused on unbound port -> MLTransportError.
            closed_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            closed_sock.bind(("127.0.0.1", 0))
            dead_port = int(closed_sock.getsockname()[1])
            closed_sock.close()
            dead_adapter = RealMLAdapter(
                _ml_settings(base_url=f"http://127.0.0.1:{dead_port}", api_key="tcp-ml-key")
            )
            try:
                with pytest.raises(MLTransportError):
                    await dead_adapter.analyze(sample_input, idempotency_key="conn-refused")
            finally:
                await dead_adapter.aclose()
        finally:
            await adapter.aclose()
    finally:
        server.should_exit = True
        with contextlib.suppress(asyncio.CancelledError):
            await serve_task
        sock.close()
