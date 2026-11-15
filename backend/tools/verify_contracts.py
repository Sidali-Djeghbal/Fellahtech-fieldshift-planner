"""CI parity verification script for OpenAPI, JSON Schema, fixtures, and env vars."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import jsonschema
import yaml
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import (  # noqa: E402
    COMPANION_SETTINGS_VARS,
    NORMATIVE_ENV_VARS,
    Settings,
)

EXPECTED_ERROR_CODES: tuple[str, ...] = (
    "INVALID_INPUT",
    "UNAUTHORIZED",
    "GUEST_LIMIT_REACHED",
    "NOT_FOUND",
    "CONFLICT",
    "CATALOG_VERSION_MISMATCH",
    "OUTSIDE_DEMO_BOUNDARY",
    "INSUFFICIENT_DATA",
    "RATE_LIMIT_EXCEEDED",
    "INTERNAL_ERROR",
    "ML_UNAVAILABLE",
    "ML_INVALID_RESPONSE",
    "ML_CONTRACT_ERROR",
    "DATASET_VERSION_UNAVAILABLE",
    "ML_DATASET_ERROR",
    "SERVICE_UNAVAILABLE",
    "DATASET_UNAVAILABLE",
    "ML_TIMEOUT",
    "JOB_TIMEOUT",
)

HTTP_METHODS = frozenset({"get", "post", "put", "patch", "delete", "options", "head", "trace"})


def _sha256_16(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def _walk_schema_refs(obj: Any, out: list[str]) -> None:
    if isinstance(obj, dict):
        ref = obj.get("$ref")
        if isinstance(ref, str) and "schema-v5.0.json#/$defs/" in ref:
            out.append(ref.split("#/$defs/")[-1])
        for value in obj.values():
            _walk_schema_refs(value, out)
    elif isinstance(obj, list):
        for item in obj:
            _walk_schema_refs(item, out)


def _parse_env_keys(env_path: Path) -> list[str]:
    keys: list[str] = []
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise AssertionError(f"Malformed line in {env_path}: {line}")
        key = line.split("=", 1)[0].strip()
        keys.append(key)
    return keys


def verify_all() -> str:
    """Run all M0 contract, schema, fixture, Compose, and env parity checks."""
    contracts_dir = BACKEND_DIR / "contracts"
    openapi_path = contracts_dir / "openapi.yaml"
    schema_path = contracts_dir / "schema-v5.0.json"
    if not openapi_path.is_file() or not schema_path.is_file():
        raise AssertionError("Canonical contracts missing in backend/contracts/")

    spec_bp_dir = REPO_ROOT / "SYSTEM DESGIN" / "SYSTEM DESGIN" / "System Architecture Blueprint"
    if spec_bp_dir.is_dir():
        for name in ("openapi.yaml", "schema-v5.0.json"):
            src = spec_bp_dir / name
            dst = contracts_dir / name
            if src.read_bytes() != dst.read_bytes():
                raise AssertionError(
                    f"Contract drift detected: backend/contracts/{name} differs from {src}"
                )

    openapi: dict[str, Any] = yaml.safe_load(openapi_path.read_text(encoding="utf-8"))
    schema: dict[str, Any] = json.loads(schema_path.read_text(encoding="utf-8"))

    paths = openapi.get("paths", {})
    if len(paths) != 24:
        raise AssertionError(f"Expected 24 OpenAPI path templates, got {len(paths)}")

    operations: list[tuple[str, str, dict[str, Any]]] = []
    for path_key, path_item in paths.items():
        for method, operation in path_item.items():
            if method in HTTP_METHODS:
                operations.append((method, path_key, operation))

    if len(operations) != 34:
        raise AssertionError(f"Expected 34 OpenAPI operations, got {len(operations)}")

    rate_limited_count = sum("429" in op["responses"] for _, _, op in operations)
    unavailable_count = sum("503" in op["responses"] for _, _, op in operations)
    if rate_limited_count != 27:
        raise AssertionError(f"Expected 27 routes with 429, got {rate_limited_count}")
    if unavailable_count != 28:
        raise AssertionError(f"Expected 28 routes with 503, got {unavailable_count}")

    post_analysis = paths["/analysis"]["post"]
    if "500" not in post_analysis["responses"]:
        raise AssertionError("POST /analysis missing Option-A 500 InternalError response")
    if "429" not in paths["/analysis/requests/{request_id}"]["get"]["responses"]:
        raise AssertionError("GET /analysis/requests/{request_id} missing Option-A 429 response")

    error_enum: list[str] = openapi["components"]["schemas"]["ErrorCode"]["enum"]
    if tuple(error_enum) != EXPECTED_ERROR_CODES:
        raise AssertionError(
            f"ErrorCode mismatch: expected {EXPECTED_ERROR_CODES}, got {tuple(error_enum)}"
        )

    ml_routes = ("POST {ML_SERVICE_URL}/v1/analyze", "/v1/catalog", "/v1/health")
    endpoints_doc = (
        spec_bp_dir / "FieldShift Planner \u2014 ENDPOINTS api & Database Specification.md"
    )
    if endpoints_doc.is_file():
        endpoints_text = endpoints_doc.read_text(encoding="utf-8")
        for marker in ml_routes:
            if marker not in endpoints_text:
                raise AssertionError(f"Missing external ML route marker in ENDPOINTS: {marker}")

    defs: dict[str, Any] = schema.get("$defs", {})
    if len(defs) != 39:
        raise AssertionError(f"Expected 39 $defs in schema-v5.0.json, got {len(defs)}")

    refs: list[str] = []
    _walk_schema_refs(openapi, refs)
    unique_refs = sorted(set(refs))
    missing_refs = [name for name in unique_refs if name not in defs]
    if missing_refs:
        raise AssertionError(f"Unresolved schema $defs referenced by OpenAPI: {missing_refs}")
    if len(refs) != 25 or len(unique_refs) != 14:
        raise AssertionError(
            "Expected 25 $ref occurrences targeting 14 unique $defs, "
            f"got {len(refs)} -> {len(unique_refs)}"
        )

    schema_id = str(schema.get("$id", "urn:fieldshift:schema"))
    registry = Registry().with_resource(
        schema_id,
        Resource.from_contents(schema, default_specification=DRAFT202012),
    )
    fixtures_dir = BACKEND_DIR / "tests" / "fixtures"
    fixture_targets = (
        ("fixture_9_1_input.json", "FarmAnalysisInput"),
        ("fixture_9_2_input_setif.json", "FarmAnalysisInput"),
        ("fixture_9_3_output.json", "AnalysisResult"),
        ("fixture_9_4_catalog.json", "CropCatalog"),
    )
    for fname, def_name in fixture_targets:
        payload = json.loads((fixtures_dir / fname).read_text(encoding="utf-8"))
        validator = jsonschema.Draft202012Validator(
            {"$ref": f"{schema_id}#/$defs/{def_name}"},
            registry=registry,
        )
        errors = list(validator.iter_errors(payload))
        if errors:
            raise AssertionError(f"Fixture {fname} failed validation: {errors[0].message}")

    output_validator = jsonschema.Draft202012Validator(
        {"$ref": f"{schema_id}#/$defs/AnalysisResult"},
        registry=registry,
    )
    output_base = json.loads((fixtures_dir / "fixture_9_3_output.json").read_text(encoding="utf-8"))
    v51_payload = dict(output_base)
    v51_payload["schema_version"] = "5.1"
    v51_payload["extra_tolerant_reader_field"] = {"unknown": True}
    if list(output_validator.iter_errors(v51_payload)):
        raise AssertionError("Unknown-field schema_version=5.1 mutation should pass Draft 2020-12")

    v60_payload = dict(output_base)
    v60_payload["schema_version"] = "6.0"
    if not list(output_validator.iter_errors(v60_payload)):
        raise AssertionError("Major bump schema_version=6.0 mutation must fail Draft 2020-12")

    # Env var & Companion Settings parity
    if len(NORMATIVE_ENV_VARS) != 40:
        raise AssertionError(f"Expected 40 NORMATIVE_ENV_VARS, got {len(NORMATIVE_ENV_VARS)}")
    if len(COMPANION_SETTINGS_VARS) != 7:
        raise AssertionError(
            f"Expected 7 COMPANION_SETTINGS_VARS, got {len(COMPANION_SETTINGS_VARS)}"
        )

    settings_fields = set(Settings.model_fields.keys())
    expected_all = set(NORMATIVE_ENV_VARS) | set(COMPANION_SETTINGS_VARS)
    if settings_fields != expected_all:
        raise AssertionError(
            f"Settings field mismatch: extra={settings_fields - expected_all}, "
            f"missing={expected_all - settings_fields}"
        )

    env_example = REPO_ROOT / ".env.example"
    if env_example.is_file():
        env_keys = _parse_env_keys(env_example)
        if len(env_keys) != len(set(env_keys)):
            raise AssertionError("Duplicate environment variable detected in .env.example")
        if set(env_keys) != expected_all:
            raise AssertionError(
                f".env.example mismatch: extra={set(env_keys) - expected_all}, "
                f"missing={expected_all - set(env_keys)}"
            )

    compose_path = REPO_ROOT / "docker-compose.yml"
    if compose_path.is_file():
        compose = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
        services = compose.get("services", {})
        for svc in ("api", "worker"):
            deps = services.get(svc, {}).get("depends_on", {})
            if deps.get("redis", {}).get("condition") != "service_healthy":
                raise AssertionError(
                    f"docker-compose.yml service '{svc}' missing redis: service_healthy depends_on"
                )

    return (
        f"34 routes (Option A 429/500/503; openapi SHA256_16={_sha256_16(openapi_path)}), "
        f"3 ML routes, 19 error codes, 25 refs targeting 14 unique $defs "
        f"(schema SHA256_16={_sha256_16(schema_path)}), 4 fixtures valid, "
        f"40/40 normative env vars (+ 7 companion settings)"
    )


def main() -> int:
    summary = verify_all()
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
