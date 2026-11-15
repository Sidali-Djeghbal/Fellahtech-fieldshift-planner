# Phase 3 — Backend Implementation Plan (`02-implementation-plan.md`)

> **Baseline:** `SYSTEM DESGIN/` (`v3.2` — Local-Dataset Edition, uncommitted Option-A `openapi.yaml` + spec reconciliations awaiting user review) + Approved Decisions (`IMPL-001`..`IMPL-021`) + Second-Audit Hardening (`#1–#5`)
> **Constraint:** **STOP after Phase 3.** Zero application code under `backend/` may be written until the user explicitly approves this plan.

---

## 1. Technology Choices & Justification

All core components are fixed by `Blueprint §1, §3, §6.1` and `ADR-1..ADR-9`; companion engineering libraries are selected below:

| Layer | Choice | Justification & Spec Alignment |
| :--- | :--- | :--- |
| **Language** | Python `3.12` | Async-first performance (`asyncio.TaskGroup`, typed `3.12` ergonomics) matching Blueprint `Python 3.11+` |
| **API Framework** | FastAPI `0.110+` + Pydantic `v2` + Uvicorn | Async ASGI, dependency injection, strict Pydantic models; custom validation exception handler overrides default `422` into `400 INVALID_INPUT` with `{error:{code,message,details[],request_id}}` |
| **Database & Spatial** | PostgreSQL `16` + PostGIS `3.4` (`postgis/postgis:16-3.4`) | Authoritative `13`-table `public` schema + isolated `Schema: dataset` (`ml_reader`) + `ST_Covers` spatial checks + `FOR UPDATE SKIP LOCKED` + session advisory locks (`1001..1008`) |
| **ORM & Migrations** | SQLAlchemy `2.x` async (`asyncpg`) + GeoAlchemy2 + Alembic | Native `asyncpg` driver (`postgresql+asyncpg://`); Alembic runs exclusively via one-shot `migrate` service (`restart: "no"`) before `api`/`worker` start |
| **Rate Limiting & Cache** | Redis `7` (`redis:7-alpine`) + `redis.asyncio` | Backend-only (`REDIS_URL`, never exposed to Frontend); interpolated integer two-bucket sliding-window Lua throttles (`429`) across all 6 buckets (incl. `120/min` poll bucket) + clamped `EXISTS`-guarded `DECRBY >= 0`/`DEL` refunds + hashed IP/token keys + PG-hydrated 7-day guest quarter mirror (`IMPL-001`) |
| **HTTP Client (ML)** | `httpx.AsyncClient` | Async HTTP/gzip transport, split timeouts (`ML_CONNECT` / `ML_TIMEOUT_SECONDS=60` / catalog `5s` / health `3s`), immediate stream close on cooperative cancellation (`IMPL-006`) |
| **Contract Validation** | `jsonschema` (`Draft202012Validator` + `referencing`) | Full Draft 2020-12 compilation with local file registry resolving relative `./schema-v5.0.json#/$defs/...` from `openapi.yaml`; supports `additionalProperties: true` unknown-field walker |
| **Auth & Crypto** | `argon2-cffi`, `PyJWT`, Python `secrets` + `hashlib.sha256` | Argon2id password hashing; HS256 dual-key verification (`JWT_SECRET_KEY` + fallback `JWT_PREVIOUS_SECRET_KEY`), strict alg whitelist; 64-char SHA-256 hex digest at rest for `refresh_tokens` & `guest_sessions` |
| **Observability** | `structlog` (JSON logs) + `prometheus-client` | PII-free JSON structured logging (`request_id`, `farm_id`, `ml_provider`); internal `/metrics` exposition |
| **QA & Contract Testing** | `pytest`, `pytest-asyncio`, `ruff`, `mypy`, `schemathesis` / `openapi-core` | Tested strictly against **real PostgreSQL 16 + PostGIS 3.4** and **real Redis 7** containers (no SQLite/in-memory DB substitutes) |

---

## 2. Repository Layout (`Blueprint §10` + Clean Modular Layers)

```text
fieldshift-planner/
├── SYSTEM DESGIN/                         # Spec pack (v3.2 — Local-Dataset Edition)
├── docs/
│   └── impl/
│       ├── 00-spec-digest.md              # Phase 1 digestible reference
│       ├── 01-audit-and-gaps.md           # Phase 2 audit + resolved gaps G1–G21
│       ├── 02-implementation-plan.md      # Phase 3 milestone plan (this file)
│       ├── TRACEABILITY.md                # Requirement -> Module -> Test matrix
│       ├── DECISIONS.md                   # IMPL-001..IMPL-021 ADRs
│       ├── DESIGN_ISSUES.md               # Cross-spec notes DI-01..DI-17
│       ├── RUNBOOK.md                     # M13 operational runbook (rotate keys, migrate, inspect breaker)
│       └── BACKLOG.md                     # Future enhancements out of 34-route MVP scope
├── docker-compose.yml                     # Services: db, redis, migrate, api, worker (+ profile dev/test mock-ml); both api & worker depend on redis
├── .env.example                           # All 40 normative spec env vars + 7 documented Companion Settings
├── README.md                              # Windows PowerShell & Docker Compose run/test guide
└── backend/
    ├── Dockerfile                         # Python 3.12-slim + curl (for API healthcheck) + non-root user
    ├── pyproject.toml                     # Dependencies, ruff, mypy, pytest-asyncio config
    ├── alembic.ini
    ├── contracts/                         # Canonical copies of openapi.yaml & schema-v5.0.json
    │   ├── openapi.yaml                   # SHA256_16: 034dce2ee08fc521 (63,659 bytes, Option A)
    │   └── schema-v5.0.json               # SHA256_16: 9945a473276e28b8 (34,115 bytes)
    ├── tools/
    │   └── verify_contracts.py            # CI parity script: 34 routes (incl. Option A 429/500/503), 19 errors, 25 $refs -> 14 $defs, fixtures 9.1-9.4, 40 env vars
    ├── app/
    │   ├── __init__.py
    │   ├── main.py                        # FastAPI lifespan, middleware (CORS, X-Request-Id), error handlers, routers
    │   ├── core/
    │   │   ├── config.py                  # Pydantic BaseSettings loading all 40 normative env vars + 7 Companion Settings (APP_ENV=production fail-safe; ValueError if production+mock)
    │   │   ├── logging.py                 # structlog JSON formatter + secret/PII redaction filter
    │   │   ├── security.py                # Argon2id, HS256 dual-key JWT (+ fid claim), SHA-256 token digest
    │   │   ├── errors.py                  # FieldShiftError hierarchy + 19 ErrorCode enum + FastAPI exception handlers
    │   │   ├── rate_limit.py              # Redis atomic Lua sliding-window rate limiter (429 + Retry-After, 6 buckets, fail-closed 503) + PG->Redis guest quota hydration
    │   │   └── metrics.py                 # Prometheus metrics + internal /metrics registry
    │   ├── db/
    │   │   ├── session.py                 # AsyncEngine (pool budgeted for worker + bulkhead + heartbeats), pinned-connection helper for advisory locks
    │   │   ├── migrations/                # Alembic env.py + versions/ (001_initial_schema.py, 002_seed_reference_data.py)
    │   │   └── seed.py                    # Idempotent reference seed (Guelma boundary OQ-D7, 2026.11-guelma-v1, breaker id=1; omits unconditional crop_catalog seed)
    │   ├── models/                        # SQLAlchemy 2.x ORM models for all 13 public tables
    │   ├── repositories/                  # Data-access repositories (users, refresh_tokens, demo, farms, fields, catalog, analysis, breaker)
    │   ├── schemas/                       # Pydantic v2 request/response DTOs matching openapi.yaml 1:1
    │   ├── services/                      # Business logic (auth, demo, farms, fields, analysis, catalog, validation INPUT-01..03 / SEM-01..07, canonical_hash)
    │   ├── api/
    │   │   ├── deps.py                    # BearerAuth, GuestTokenAuth, Principal, DB/Redis deps
    │   │   └── v1/                        # FastAPI routers: auth.py, demo.py, farms.py, fields.py, analysis.py, catalog.py, system.py
    │   ├── ml_client/                     # Mandatory ML Adapter Architecture (ADR-4, IMPL-008)
    │   │   ├── base.py                    # MLAdapter ABC (analyze, get_catalog, get_health, provider_name) + ML exceptions
    │   │   ├── real_adapter.py            # RealMLAdapter: httpx /v1/* client, dual X-ML-API-Key, gzip, timeouts
    │   │   ├── mock_adapter.py            # MockMLAdapter: deterministic Fixture 9.3/9.4 generator + test fault modes
    │   │   ├── manager.py                 # MLProviderManager: auto dev/test fallback, periodic /v1/health check & auto-promotion, provider logging
    │   │   └── mock_server.py             # Optional ASGI HTTP server wrapping MockMLAdapter (Compose profile dev/test)
    │   └── worker/
    │       ├── runner.py                  # Async worker: SKIP LOCKED loop, lease/heartbeat, advisory-lock bulkhead (1001..1008), cancel watcher
    │       ├── breaker.py                 # PostgreSQL row-locked ml_breaker_state state machine (closed/open/half_open)
    │       ├── jobs.py                    # Reclaim stale leases, periodic catalog_sync & guest/idempotency reaper (advisory locks)
    │       └── healthcheck.py             # Docker HEALTHCHECK entrypoint (`python -m app.worker.healthcheck`)
    └── tests/
        ├── conftest.py                    # Real PostGIS 16-3.4 + Redis 7 fixtures, DB transaction cleanup, async TestClient
        ├── fixtures/                      # Verified JSON fixtures extracted from Visual I/O §9.1–9.4
        ├── unit/                          # INPUT-01..03, SEM-01..07, canonical hash, quota quarters, Lua rate logic, ML error mapping, JWT/token
        ├── migration/                     # Alembic upgrade/downgrade/upgrade, schema introspection vs DDL, ml_reader SELECT/isolation tests
        ├── contract/                      # 34 OpenAPI routes + 19 ErrorCodes + Draft 2020-12 unknown-field policy (`5.1` pass / `6.0` fail)
        ├── integration/                   # End-to-end W1–W4 workflows, claim-guest, DELETE /auth/me, GET /auth/me/export, MockML <-> RealML switchover
        ├── concurrency/                   # Multi-worker SKIP LOCKED race, 8-slot advisory bulkhead saturation, refresh-token race, idempotency race
        └── golden/                        # 15-scenario golden suite harness + OQ-6 labeled sample runner
```

---

## 3. Detailed Milestone Breakdown (`M0`–`M13`)

### `M0` — Project Scaffolding, Contracts Copy, Config (`40` + `7` Companion), Compose (`db` + `redis`) & CI Verification
- **Scope:** Directory structure, `backend/pyproject.toml`, `backend/Dockerfile` (with `curl`), `docker-compose.yml` (`db: postgis/postgis:16-3.4`, `redis: redis:7-alpine`, `migrate`, `api`, `worker`, optional `mock-ml` ASGI container under `profiles: ["dev", "test"]`; **both `api` and `worker` declare `depends_on: redis: condition: service_healthy`** matching updated `Blueprint §6.1`), `.env.example` (**40** normative vars from `ENDPOINTS C` + separate documented **7** Companion Settings section per `IMPL-018`), fail-fast `app/core/config.py` (defaulting `APP_ENV=production` fail-safe; raising startup **`ValueError`** when `APP_ENV=production` and `ML_PROVIDER_MODE=mock`; validating `https://` `ML_SERVICE_URL` in production), `db/session.py` pool sizing helper (`WORKER_CONCURRENCY + ML_MAX_CONCURRENT_REQUESTS` + heartbeat headroom), `structlog` PII-safe logger, `X-Request-Id` middleware, `backend/contracts/`, and `backend/tools/verify_contracts.py` (checking `40/40` env parity, `25 $ref` occurrences targeting `14` unique `$defs`, and Option-A `429`/`500`/`503` response contracts in `openapi.yaml`).
- **Key Spec Refs:** `Blueprint §6.1, §10`, `ENDPOINTS C`, `ADR-2, ADR-8`, `IMPL-001, IMPL-008, IMPL-018`.
- **Pitfalls Handled:** Windows PowerShell friendly Compose commands; non-empty required secrets validation (`JWT_SECRET_KEY`, `ML_SERVICE_API_KEY`, `DB_PASSWORD`, `ML_READER_PASSWORD`); `REDIS_URL` strictly backend-only; fail-safe `APP_ENV=production` raises startup `ValueError` if `ML_PROVIDER_MODE=mock` and never activates `MockMLAdapter` accidentally.
- **Acceptance Gate:** `docker compose config` valid (`worker -> redis` healthy dependency present); `python backend/tools/verify_contracts.py` reports `34 routes (Option A 429/500/503), 3 ML routes, 19 error codes, 25 $refs targeting 14 unique $defs, 4 fixtures valid, 40/40 normative env vars`; `ruff` + `mypy` + config unit tests pass (incl. `APP_ENV=production` + `ML_PROVIDER_MODE=mock` `ValueError` fail-fast tests).

### `M1` — Alembic Migrations (`13` `public` Tables + `Schema: dataset` + `ml_reader`) & Minimal Seeds
- **Scope:** Initial Alembic migration creating `postgis` & `pgcrypto` extensions, exact **13** `public` tables matching `ENDPOINTS A.4` column-by-column, all `CHECK`/`UNIQUE`/partial unique indexes and GiST indexes, `CREATE SCHEMA IF NOT EXISTS dataset`, and safe idempotent `ml_reader` provisioning (`IMPL-005`: pre-flight role/extension capability checks, secret-redacted logs, `REVOKE ALL ON SCHEMA public`, `GRANT USAGE/SELECT ON dataset`, `ALTER DEFAULT PRIVILEGES IN SCHEMA dataset GRANT SELECT ON TABLES TO ml_reader` + optional `FOR ROLE <ML_DATASET_OWNER_ROLE>`). Seed migration `002` (`IMPL-009` Revised + `IMPL-023`) populates **only** `demo_locations` (`id=1, code='guelma'`, 10-vertex Polygon `# TODO(OQ-D7)`, without any backend default parcel), `dataset_registry` (`2026.11-guelma-v1`, `is_active=true`), and `ml_breaker_state` (`id=1`). **`public.crop_catalog` is NOT pre-seeded unconditionally** so `GET /catalog -> 502` cold-start contract tests remain valid.
- **Key Spec Refs:** `ENDPOINTS A.1–A.5, B.8`, `ADR-2, ADR-3, ADR-9`, `IMPL-005, IMPL-009`.
- **Pitfalls Handled:** `alembic` downgrade removes objects cleanly; SQL `ml_reader` migration never logs `ML_READER_PASSWORD`; `ALTER DEFAULT PRIVILEGES` covers external ML dataset loader role when configured; PostGIS `(lon, lat)` axis order verified; `field_crop_history` has deliberately NO FK to `crop_catalog` (`Pitfall #10`).
- **Acceptance Gate:** `alembic upgrade head` -> `downgrade base` -> `upgrade head` succeeds on clean `postgis/postgis:16-3.4`; schema introspection proves exact 13-table DDL match & empty initial `crop_catalog`; test connecting as `ml_reader` (including table created by simulated `ML_DATASET_OWNER_ROLE`) proves `SELECT` works on `dataset.*` while `public.*` & `CREATE` raise `InsufficientPrivilege`.

### `M2` — Cross-Cutting Layer: 19 Error Codes, Envelope, Redis Sliding-Window Limiter, Pagination & Handlers
- **Scope:** `app/core/errors.py` (`ErrorCode` enum of exact 19 codes, `FieldShiftError`, overriding FastAPI `RequestValidationError` & Pydantic errors to **`400 INVALID_INPUT`** — never `422` — matching `X-Request-Id`), `app/core/rate_limit.py` (interpolated integer two-bucket Lua **sliding-window** counters returning incremented `bucket_key`s across all `6` buckets including **`120 req/min` poll bucket** per `openapi.yaml` L829, Lua `if EXISTS == 1` clamped `DECRBY >= 0` [preserving TTL] / `DEL` rollback helper so missing/expired keys never leave negative `TTL = -1` keys, hashed IP/token digests `rl:*:{sha256}`, `TRUSTED_PROXY_CIDRS`-gated `X-Forwarded-For` extraction, `REDIS_FAIL_CLOSED=true` returning `503 SERVICE_UNAVAILABLE` + `Retry-After: 5` on Redis outage, and atomic PG->Redis guest quarter cache hydration via `SET ... NX EX`), plus opaque Base64 cursor pagination helper.
- **Key Spec Refs:** `ENDPOINTS B.1`, `openapi.yaml` (Option A `429`/`500`/`503`), `IMPL-001`, `Pitfall #3, #12, #16`.
- **Acceptance Gate:** Unit & Redis integration tests verify all 19 codes serialize cleanly, `400 INVALID_INPUT` overrides FastAPI `422`, interpolated two-bucket sliding window eliminates `2x` boundary bursts, clamped `EXISTS`-guarded `DECRBY`/`DEL` never creates persistent negative `TTL = -1` keys, spoofed `X-Forwarded-For` from untrusted peer is ignored, Redis downtime fails closed (`503`), and Redis key miss rehydrates cleanly from PG `guest_sessions FOR UPDATE`.

### `M3` — Auth Lifecycle, Refresh Family Reuse Detection, Export Safety & Guest Claim
- **Scope:** Implement all **9** Auth endpoints:
  - `POST /auth/guest` (`201`, Redis `GUEST_CREATE_PER_IP_HOUR=5`, returns `gst_<24hex>` once, persists SHA-256 hex in `guest_sessions.guest_token`, returns `demo_location` only; frontend defines and sends demo farms/fields dynamically per `IMPL-012, IMPL-023`).
  - `POST /auth/register` (`201`, Argon2id, case-insensitive unique email `409 CONFLICT`, issues access JWT + refresh family), `POST /auth/login` (`200`).
  - `POST /auth/refresh` (`200`, atomic `UPDATE ... WHERE used_at IS NULL AND revoked_at IS NULL RETURNING ...`; replay detection commits full `family_id` revocation in its own committed transaction **before** raising `401 UNAUTHORIZED` — `Pitfall #2`!).
  - `POST /auth/logout` (`204`, revokes body `refresh_token` family or access JWT `fid` claim — `IMPL-014`).
  - `GET /auth/me` (`200`, schema integer `id` per `DI-16`), `DELETE /auth/me` (`204`, single-transaction hard cascade delete across all user data incl. `input_snapshot_gz` — `Pitfall #13`).
  - `GET /auth/me/export` (`200 UserDataExport` — `IMPL-021`: explicit schema mapper **excluding `input_snapshot_gz` (`bytea`), `password_hash`, and `token_hash`**, formatting `fields[]` via `FieldDetailPublic`).
  - `POST /auth/claim-guest` (`200` — `IMPL-021`: locks `guest_sessions FOR UPDATE`, executes `UPDATE farms SET user_id = :uid, guest_session_token = NULL` **before** `DELETE FROM guest_sessions` so `ON DELETE CASCADE` never deletes claimed farms, and deletes Redis quota key).
  - FastAPI auth deps (`BearerAuth`, `GuestTokenAuth`, `EitherAuth`, enforcing `GUEST_BURST_PER_MIN=30` / `RATE_LIMIT_CRUD_PER_MIN=60`; poll route uses `120 req/min` bucket separately).
- **Key Spec Refs:** `ENDPOINTS B.3`, `ADR-5, ADR-6`, `IMPL-001, IMPL-012, IMPL-014, IMPL-021, IMPL-023`.
- **Cross-Milestone Dependency (`E4`):** Route CRUD & empty-farm `export`/`claim-guest` pass in `M3`; full `claim-guest` & `export` assertions with populated farms, fields, crop history, and analysis snapshots are re-verified after `M5` & `M7`.
- **Acceptance Gate:** Concurrent refresh race test, `alg=none`/dual-key JWT tests, full `DELETE /auth/me` cascade, JSON serialization safety of `GET /auth/me/export` (zero binary/hash fields), and `claim-guest` farm survival pass against real Postgres + Redis.

### `M4` — Demo Endpoints & PostGIS Spatial Boundary Gate
- **Scope:** Implement all **4** Demo endpoints (`GET /demo/locations`, `GET /demo/locations/{id}/boundary` returning `BoundaryFeature` MultiPolygon GeoJSON `[lon, lat]`, `GET /demo/session` reporting canonical `analysis_quarters` & `analyses = quarters / 4.0` without `demo_parcel`, `DELETE /demo/session` cascading cleanup) and shared PostGIS spatial service evaluating `ST_Covers(demo_locations.boundary, ST_SetSRID(ST_MakePoint(lon, lat), 4326))` (`Pitfall #4`).
- **Key Spec Refs:** `ENDPOINTS B.4`, `ADR-3`, `Visual I/O §4–§5`.
- **Acceptance Gate:** Guelma point `(36.52, 7.52)` inside -> `true`; Setif point `(36.19, 5.41)` outside -> `false`; OpenAPI conformance tests on all 4 `/demo/*` routes pass.

### `M5` — Farms & Fields CRUD (with Row-Locked Guest Quotas, Deep Patch Validation & Crop History)
- **Scope:** Implement all **6** Farms endpoints (`GET/POST /farms`, `GET/PUT/PATCH/DELETE /farms/{farm_id}`) and all **6** Fields endpoints (`GET/POST /farms/{farm_id}/fields`, `GET/PUT/PATCH/DELETE /farms/{farm_id}/fields/{field_id}`). Enforce `"farm_" || id` public ID formatting (`Pitfall #14`), foreign owner `404 NOT_FOUND` everywhere (never `403`), **row-locked PostgreSQL guest quotas (`IMPL-019`)** (`POST /farms` acquires `guest_sessions FOR UPDATE` for `GUEST_MAX_FARMS=3`; `POST /farms/{id}/fields` acquires `farms FOR UPDATE` for `GUEST_MAX_FIELDS_PER_FARM=5` -> `403 GUEST_LIMIT_REACHED`), PostGIS boundary gate on field write (`422 OUTSIDE_DEMO_BOUNDARY` for guests; `201`/`200` + `MVP_OUTSIDE_COVERAGE` notice for registered users), `is_unverified_demo_parcel` notice (`DEMO_PARCEL_UNVERIFIED`), **`FieldPatchRequest` strict nested sub-models (`FieldLocationPatch`, `FieldSoilPatch`, `FieldWaterPatch` with `extra="forbid"`, recomputing `soil_source`, clearing `water_source_other` when `source != 'other'`, and atomic `crop_history[]` replacement rejecting duplicates `IMPL-019`)**, and `(field_id, year, season)` crop history management (`PUT` full replacement vs `PATCH` partial semantics).
- **Key Spec Refs:** `ENDPOINTS B.5–B.6`, `Visual I/O §5`, `ADR-3, ADR-5`, `IMPL-019`.
- **Acceptance Gate:** All 12 endpoints pass OpenAPI validation; foreign access returns `404`; concurrent guest 4th farm / 6th field races serialize cleanly and return `403 GUEST_LIMIT_REACHED`; partial `PATCH` rejects invalid lab metrics / invalid water enums (`400 INVALID_INPUT` rather than DB `CHECK` `500`), recomputes `soil_source`, and works for both Guelma & Setif paths.

### `M6` — ML Adapter Architecture (`MLAdapter` + `RealMLAdapter` + `MockMLAdapter` + `MLProviderManager`) & Catalog/Dataset Registry
- **Scope:** Build `app/ml_client/` strictly following `ADR-4` & `IMPL-008`:
  - `base.py`: `MLAdapter` ABC (`analyze`, `get_catalog`, `get_health`, `provider_name`) and structured transport/contract exceptions.
  - `real_adapter.py`: HTTP client to `{ML_SERVICE_URL}` with `X-ML-API-Key`, automatic 1x retry with `ML_SERVICE_PREVIOUS_API_KEY` on `401`/`403`, optional `Content-Encoding: gzip`, and per-route timeouts (`60s` analyze, `5s` catalog, `3s` health).
  - `mock_adapter.py`: Deterministic in-process provider seeded with Fixtures `9.3` & `9.4` (dynamically preserving `request_id`, `dataset_version`, requested `field_id`s, `horizon_seasons`, `target_crop_ids`, and excluded crops) + full fault-injection switches (companion `mock_server.py` ASGI HTTP server runs under Compose `profiles: ["dev", "test"]` strictly for wire-level `RealMLAdapter` HTTP/gzip/timeout verification — `E2`).
  - `manager.py`: `MLProviderManager` honoring `APP_ENV` (`production` fail-safe default `IMPL-018`) & `ML_PROVIDER_MODE` (`auto` \| `real` \| `mock`): **`MockMLAdapter` is NEVER selected or fallen back to in `APP_ENV=production` or `ML_PROVIDER_MODE=real`** ("Zero Pretend Precision"). Only in `development`/`test` with `mode=auto` may offline `/v1/health` select `MockMLAdapter`; `worker` publishes active provider snapshot to Redis `ml:provider_status` (`2 * ML_HEALTH_CHECK_INTERVAL_SECONDS` TTL) for cross-container `/health` agreement; **zero** silent fallback on in-flight errors (`4xx`, `5xx`, timeout, or validation errors).
  - Implement `GET /api/v1/catalog` (`crop_catalog` cursor pagination, filters, `display_name` localization `IMPL-016`, `N`/`N-1` catalog versions; authentic cold-start bootstrap via `MLProviderManager.get_catalog()`, raising **`502 ML_UNAVAILABLE`** when catalog empty and real ML offline `IMPL-009`) and `dataset_registry` active lookup (`503 DATASET_UNAVAILABLE`).
- **Key Spec Refs:** `ENDPOINTS B.8, B.10`, `ADR-4, ADR-9`, `IMPL-008, IMPL-009, IMPL-016, IMPL-018`.
- **Cross-Milestone Dependency (`E4`):** Breaker interaction under real/simulated `5xx` outages is finalized with `M10`.
- **Acceptance Gate:** Unit + integration tests verify `APP_ENV=production` strict no-mock isolation, `development`/`test` `MockMLAdapter` <-> `RealMLAdapter` switchover, `mock_server.py` HTTP wire/gzip/key-rotation/timeout verification (in-process ASGI/loopback during `M6`–`M10`; full `mock-ml` container E2E in `M11`/`M13`), empty-catalog `GET /catalog -> 502 ML_UNAVAILABLE`, and catalog `N`/`N-1` retention.

### `M7` — Analysis REST Endpoints (`6` Routes), `INPUT-01..03`, Canonical Hashing, Non-Burning Quotas & Idempotency
- **Scope:** Implement all **6** Analysis endpoints:
  - `POST /api/v1/analysis` strictly following **W1 check order** (`1. Auth/Ownership 404` -> `2. Idempotency 24h [with savepoint/UniqueViolation race guard IMPL-002] / interpolated two-bucket Redis sliding-window hourly limits 429 [returning incremented bucket_key] / locked PG guest_sessions FOR UPDATE quarters check 403` -> `3. PostGIS Guelma + INPUT-01..03 422/400 + aggregated WarningNotice.fields[] IMPL-019` -> `4. Catalog + Active dataset_registry 409/503` -> `5. Assemble allowlisted FarmAnalysisInput, validate schema-v5.0.json, gzip into input_snapshot_gz, insert pending row -> commit -> update Redis guest quarter mirror -> 202 Accepted` or optional test `?wait=true` polling until `SYNC_WAIT_TIMEOUT_SECONDS=58` translating terminal failures via `PollErrorObject.http_equivalent` `IMPL-020` and returning `500 INTERNAL_ERROR` on unexpected server failures per Option A). **Wrap Step 2 `403 GUEST_LIMIT_REACHED` AND Steps 3–5 errors inside the Lua `if EXISTS == 1` clamped `DECRBY >= 0` / `DEL` rollback handler** (`IMPL-001`) so neither `403` nor `400`/`422`/`409`/`503` ever burns hourly IP or guest quotas or creates negative `TTL = -1` keys.
  - Deterministic canonical SHA-256 hashing (`IMPL-003`) for `input_hash` (what-if `1` quarter within 24h on same `farm_id`, auto-linking `parent_request_id`) and `full_input_hash`.
  - `GET /analysis/requests/{request_id}` (governed by **`120 req/min` Redis poll bucket** `IMPL-001`, documented in `openapi.yaml`, returns `Retry-After: 2` while `pending`/`running`, merges `analysis_selections`, reconstructs `DegradedModeMetadata` via `req.error_code = 'last_good_replay:...'` `IMPL-017`).
  - `POST /analysis/requests/{request_id}/cancel` (`IMPL-020`: locks row `FOR UPDATE`; if `pending`, immediately sets `status='cancelled', cancelled_at=now(), quota_units=0` & decrements Redis via the clamped `EXISTS`-guarded Lua helper; if `running`, sets `cancelled_at=now()` for worker abort; `409 CONFLICT` on terminal states).
  - `GET /analysis/{analysis_id}` (with read-time `degraded_mode` reconstruction), `PATCH /analysis/{analysis_id}/selection` (**locks parent `public.analysis_results WHERE analysis_id = :aid FOR UPDATE`**, NOT `analysis_selections`, before deleting any prior `'selected'` row for a different `strategy_id` and upserting, eliminating 0-row phantom lock races against `idx_one_selected_strategy_per_field` — `IMPL-020`), `GET /farms/{farm_id}/analyses`.
- **Key Spec Refs:** `ENDPOINTS B.7`, `Blueprint §4 W1, W3`, `Visual I/O §6, §10`, `IMPL-001, IMPL-002, IMPL-003, IMPL-013, IMPL-017, IMPL-019, IMPL-020`.
- **Cross-Milestone Dependency (`E4`):** HTTP routes & queue insertion pass in `M7`; end-to-end `?wait=true` execution (success & error translation) + replay selection switching are completed after `M8`/`M9`/`M10`.
- **Acceptance Gate:** Exact W1 failure precedence + non-burning `403` & validation error tests (using clamped Lua rollback without `TTL = -1` leak), concurrent idempotency double-submit race test, `pending` cancel immediate refund test, concurrent 0-row strategy switch `selected`->other `selected` test (`analysis_results FOR UPDATE`), `120 req/min` poll bucket test, and zero-PII `input_snapshot_gz` assertion.

### `M8` — Worker Core, `SKIP LOCKED`, Advisory-Lock Bulkhead, Cancellation & ML Error Mapping
- **Scope:** Implement `app/worker/runner.py` and `jobs.py`:
  - Explicit DB connection pool sizing (`E4`): `pool_size + max_overflow` budgeted `>= WORKER_CONCURRENCY + ML_MAX_CONCURRENT_REQUESTS + 4` heartbeat/reaper connections so advisory-lock pinned sessions never exhaust worker pools.
  - `FOR UPDATE SKIP LOCKED` single-statement claim (`status='running'`, `lease_until = now() + 90s`, `heartbeat_at = now()`, `attempts = attempts + 1`), heartbeats every `2s`, stale lease reclaim up to `MAX_JOB_ATTEMPTS=2` (`Pitfall #5`).
  - **Pre-dispatch & final cancellation checks (`IMPL-006`):** Right before acquiring ML call / setting `sent_at = now()`, lock row `FOR UPDATE` and verify `cancelled_at IS NULL AND status = 'running'`; if already cancelled, mark `cancelled`, refund `quota_units = 0` cleanly (without consuming `GUEST_MAX_ML_REFUNDS=3`), and sync Redis. Before persisting `analysis_results` in the final cascade guard, re-lock `analysis_requests` and verify **both `status == 'running' AND cancelled_at IS NULL`** (transitioning to `cancelled` + `quota_units = 0` + clamped Redis decrement if `cancelled_at IS NOT NULL`).
  - Pinned dedicated DB connection holding `pg_try_advisory_lock(1001..1008)` for the entire ML call + retry backoff sleep (`2s+jitter`, `Retry-After <= 5s`) wrapped inside a cancellable `asyncio.Task`, with guaranteed `pg_advisory_unlock(slot)` in `finally:` (`IMPL-006`, `Pitfall #1`).
  - Complete ML error-mapping table (`ENDPOINTS B.10.4`), and guest ML-error refund tracking up to `GUEST_MAX_ML_REFUNDS=3` (`worker` commits PG `quota_units = 0` unconditionally and executes the clamped `EXISTS`-guarded Redis `DECRBY`/`DEL` helper, logging non-fatal warning if Redis is briefly offline `IMPL-001, IMPL-011`).
- **Key Spec Refs:** `Blueprint §4 W2, §8`, `ENDPOINTS A.3, B.10.4`, `IMPL-001, IMPL-006, IMPL-011`.
- **Acceptance Gate:** Multi-worker race test (`N` workers, 0 duplicate runs), 8-slot bulkhead saturation + pool-headroom test, killed-worker stale lease reclaim, pre-dispatch / backoff-sleep / final-cascade (`cancelled_at IS NULL`) cancel abort + unlock tests, and every row of `ENDPOINTS B.10.4` error table unit/integration tested.

### `M9` — Stage 1 (`schema-v5.0.json`) & Stage 2 (`SEM-01..07`) Verifier & Immutable Storage
- **Scope:** Two-stage validator inside `app/services/verification.py`:
  - Stage 1: `Draft202012Validator` against `#/$defs/AnalysisResult` (`^5\.[0-9]+$` accepted, `6.0` rejected, unknown-field recursive tree walker logging `WARNING` & incrementing `ml_unknown_fields_observed_total` without failing).
  - Stage 2: Exact enforcement of `SEM-01` through `SEM-07` (`dataset_version_used == dataset_version`, `SEM-04` numeric tolerance `SEM04_NUMERIC_TOLERANCE` `# TODO(OQ-3)` against `input_snapshot_gz`).
  - Backend-mints `analysis_<12hex>` (retrying `UniqueViolation` — `Pitfall #15`), persists write-once `result_json` even on `validation_passed=false`, and applies exact `IMPL-007` status mapping (`ML_INVALID_RESPONSE` vs `DATASET_VERSION_UNAVAILABLE`).
- **Key Spec Refs:** `Blueprint §4 W4`, `ADR-5, ADR-6, ADR-9`, `Visual I/O §8, §10`, `IMPL-007, IMPL-018`.
- **Acceptance Gate:** Positive + negative tests for Stage 1, unknown fields `5.1` (passes & increments counter), `6.0` (fails), and all 7 `SEM-01..07` rules; DB assertion confirms raw JSON saved with `validation_passed=false` on invalid responses.

### `M10` — Shared Circuit Breaker (`ml_breaker_state`) & 13-Table Honest Degraded Mode (`last_good_replay`)
- **Scope:** `app/worker/breaker.py` managing singleton row `id = 1` with `SELECT ... FOR UPDATE` (`closed` -> `open` after `ML_CIRCUIT_BREAKER_THRESHOLD=5` 5xx/timeout/`ML_DATASET_ERROR` failures; `4xx` does **not** increment when `closed`; single-flight `half_open` probe lock after `ML_BREAKER_COOLDOWN_SECONDS=30` via `half_open_probe_at`; **valid ML `4xx` on a `half_open` probe transitions `half_open -> closed` (`consecutive_failures=0, half_open_probe_at=NULL`)**, whereas `5xx`/timeout/`ML_DATASET_ERROR` on a `half_open` probe resets `state = 'open'`, `opened_at = now()`, `half_open_probe_at = NULL` for full cooldown `IMPL-017`**).
  - **`last_good_replay` Persistence & Reconstruction (`IMPL-017`):** Query latest matching `req_src.farm_id`, `req_src.full_input_hash`, **`req_src.received_at IS NOT NULL`** (non-chaining), `res_src.validation_passed = true` within `DEGRADED_MODE_MAX_AGE_HOURS=72`; insert self-contained `res_new` copy into `analysis_results` (preserving isolated `analysis_selections` per `analysis_id`), update `req_new` with `status = res_src.status`, **`received_at = NULL`**, and **`error_code = 'last_good_replay:' || res_src.analysis_id`**; reconstruct `degraded_mode: {kind: "last_good_replay", stale: true, source_analysis_id, created_at, dataset_version, age_seconds}` on read (`GET /analysis/requests/{id}`, `GET /analysis/{analysis_id}`, `POST /analysis?wait=true`).
- **Key Spec Refs:** `ADR-8`, `ENDPOINTS A.4`, `Visual I/O §10 #8`, `IMPL-017`.
- **Acceptance Gate:** Fault-injection suite proves 5 ML 5xx errors open breaker -> 6th request serves `last_good_replay` (`stale: true`, non-chaining, independent `analysis_selections`, surviving subsequent `GET /analysis/{id}` fetch) or fails `502 ML_UNAVAILABLE` -> 30s single-flight `half_open` probe failure re-opens breaker for full 30s -> valid ML `4xx` or `200` probe transitions `half_open -> closed`.

### `M11` — Ops, `/health`, `/metrics`, Reaper, Catalog Sync, Graceful Shutdown & Audit Logging
- **Scope:** Implement `GET /api/v1/health` (`live`, `ready`, `dependencies` checks: **`503 SERVICE_UNAVAILABLE` if Postgres or Redis unreachable**, `503 DATASET_UNAVAILABLE` if active dataset absent; **`200 ok`/`degraded` reads `ml:provider_status` written to Redis by `worker`** alongside `ml_breaker_state` so `api` & `worker` report identical ML health `IMPL-008`), `GET /api/v1/metrics` (`x-internal-only: true` Prometheus exposition), `python -m app.worker.healthcheck`, leader-elected `reaper` & `catalog_sync` (`IMPL-010`), clean SIGTERM graceful drain, and log-redaction audit tests ensuring zero secrets/PII appear in logs.
- **Key Spec Refs:** `ENDPOINTS B.9`, `Blueprint §6.1, §12.1`, `IMPL-001, IMPL-008, IMPL-010`, `Pitfall #16`.
- **Acceptance Gate:** `GET /health?check=dependencies` returns `503` when Postgres or Redis is stopped (even when Postgres is up!), `503 DATASET_UNAVAILABLE` if `dataset_registry` empty, `200 degraded` if DB+Redis up while real ML offline in production mode; worker reaper cleans expired guest sessions & >24h idempotency keys cleanly; plus initial **Container Bring-up & Compose E2E** verification building/starting `migrate`, `api`, `worker`, and `mock-ml` with passing container `healthcheck`s.

### `M12` — Full Fixture, Golden Suite Harness, Concurrency, Security & Fault-Injection Suite
- **Scope:** Complete test matrix across all 8 layers (`§6` below):
  - All 4 Fixtures (`9.1–9.4`) & all `Visual I/O §10` cases (`1`–`8`) + Redis `429` (all 6 buckets incl. `120 req/min` poll bucket + sliding-window + Redis outage `503`) vs PG `403` + `MLProviderManager` `production` strictness & `dev/test` switchover + cross-milestone `M3`/`M5`/`M7` `claim-guest`/`?wait=true`/`export` end-to-end tests.
  - Golden-set runner under `backend/tests/golden/` built cleanly around the 15-scenario framework (`# TODO(OQ-6)`).
  - OpenAPI `schemathesis` / response schema checks across all **34** endpoints (enforcing Option-A `429`/`500`/`503` response contracts directly from `openapi.yaml`).
  - Security regression suite (foreign `404`, `TRUSTED_PROXY_CIDRS` spoofed `X-Forwarded-For`, SQLi, JWT forgery/`alg=none`, refresh reuse race, forbidden keys absent from ML wire payload, Redis concurrency).
- **Key Spec Refs:** `Blueprint §4.5`, `Visual I/O §9–§11`, Master Prompt `§8`.
- **Acceptance Gate:** Zero failing or unexplained skipped tests; `>= 90%` line/branch coverage on `auth`, `validators/SEM`, `worker`, `breaker`, `ml_client`, `rate_limit`.

### `M13` — Hardening, Documentation, Final Traceability & Conformance Report
- **Scope:** Update `README.md` (exact Windows PowerShell & `docker compose` run/test/migrate/key-rotation/Redis-inspection instructions), write `docs/impl/RUNBOOK.md` & `docs/impl/BACKLOG.md`, mark all statuses in `docs/impl/TRACEABILITY.md`, execute the final **Container Bring-up & Compose E2E** verification (building `migrate`, `api`, `worker`, `mock-ml`, validating config & `.env`, checking container `healthcheck`s, and starting cleanly from fresh Docker volumes), and run final end-to-end conformance verification reporting **`34/34` routes, `13/13` tables, `19/19` error codes, `40/40` normative env vars (+ `7` Companion Settings), `3/3` `INPUT` rules, `7/7` `SEM` rules**, coverage metrics, and open `OQ-*` checklist.
- **Acceptance Gate:** Clean git history (`M0`..`M13` commits on feature branch), `ruff`, `mypy`, `verify_contracts.py`, full `pytest`, and full Compose E2E (`migrate`, `api`, `worker`, `mock-ml`) green from fresh Docker volumes.

---

## 4. Risk Register & Open Questions Status

- **Blocking Questions at Phase 3 Gate:** **None (`0`)** in implementation logic — all `21` audit gaps/revisions (`G1`–`G21`, closing `C1`–`C5`, `D1`–`D8`, `E1`–`E4`), Option A (`DI-13` `openapi.yaml` + spec reconciliations), and Second-Audit Hardening Findings `#1–#5` are resolved across [`DECISIONS.md`](DECISIONS.md) & [`DESIGN_ISSUES.md`](DESIGN_ISSUES.md). (The uncommitted `SYSTEM DESGIN/` Option-A edits remain unstaged on `backend-system` for user review before committing/starting Phase 4.)
- **Top Technical Risks & Mitigations:**
  1. **Session Advisory Lock & DB Pool Saturation (`E4`):** Pinned session advisory locks (`1001..1008`) hold connections across long ML I/O; mitigate with pinned async connections (`finally: pg_advisory_unlock` + close) and explicit pool sizing `>= WORKER_CONCURRENCY + ML_MAX_CONCURRENT_REQUESTS + 4` in `db/session.py` (`Pitfall #1`).
  2. **Silent Mock Predictions or Outage Masking in Production (`C2`):** Eliminated by defaulting `APP_ENV=production` fail-safe (raising startup `ValueError` if `ML_PROVIDER_MODE=mock`) where `MockMLAdapter` is strictly disabled (`IMPL-008`, `IMPL-018`) and `worker` shares health state via Redis `ml:provider_status`.
  3. **Redis Outage / Quota Drift / Spoofed IP Headers (`C3`, `D7`):** Fail closed (`503`) on API outage (`REDIS_FAIL_CLOSED=true`), hydrate guest quarters atomically from `guest_sessions FOR UPDATE`, use interpolated two-bucket Lua throttles + Step 2 `403`/Steps 3–5 rollback via clamped `EXISTS`-guarded `DECRBY >= 0` / `DEL`, commit PG refunds unconditionally in worker, and gate `X-Forwarded-For` behind `TRUSTED_PROXY_CIDRS` (`IMPL-001`).
  4. **`last_good_replay` Chain Loops or Selection Pollution (`C1`):** Prevented by `req_src.received_at IS NOT NULL` non-chaining filter and self-contained `analysis_results` copy (`IMPL-017`).
  5. **Refresh Token Reuse Rollback & `claim-guest` Cascade Wipe (`D4`):** Family revocation commits independently before raising `401` (`Pitfall #2`), and `claim-guest` transfers `farms` ownership before deleting `guest_sessions` (`IMPL-021`).

---

## 5. Coverage Matrix for All 16 Known Implementation Pitfalls (Master Prompt `§7`)

| # | Pitfall | Handling Design | Enforcing Milestone & Module |
| :-: | :--- | :--- | :--- |
| 1 | Session-level advisory locks (`1001..1008`) & pools | Acquire/hold/unlock on single dedicated pinned async connection in `try/finally`; never transaction-pooled | `M8` (`worker/runner.py`) |
| 2 | Refresh reuse revocation rollback | Commit family revocation in independent transaction before raising `401`; atomic `UPDATE ... WHERE used_at IS NULL AND revoked_at IS NULL RETURNING` | `M3` (`services/auth.py`) |
| 3 | FastAPI default `422` validation errors | Override `RequestValidationError` handler to `400 INVALID_INPUT` with `{error:{code,message,details,request_id}}` | `M2` (`core/errors.py`) |
| 4 | PostGIS `(lon, lat)` axis order | Strictly `ST_SetSRID(ST_MakePoint(lon, lat), 4326)` and `[lon, lat]` GeoJSON; verified with Guelma vs Setif | `M1, M4, M5` (`services/geo.py`) |
| 5 | `SKIP LOCKED` atomic claim + lease/heartbeat | Single atomic `UPDATE ... FROM (SELECT ... FOR UPDATE SKIP LOCKED)` setting `running`, `lease_until`, `attempts+1` + `2s` heartbeat + reclaim | `M8` (`worker/runner.py`) |
| 6 | Cooperative mid-flight & pre-dispatch cancel | Poll `cancelled_at` / farm existence every `2s` -> `task.cancel()` (aborting both HTTP + backoff sleep) + unlock slot; `/cancel` on `pending` refunds immediately, pre-dispatch & final cascade guards check `status == 'running' AND cancelled_at IS NULL` | `M7, M8` (`worker/runner.py`, `services/analysis.py`) |
| 7 | Breaker row locking & failure scoping | `SELECT ... FOR UPDATE` on `ml_breaker_state (id=1)`; single-flight `half_open` probe via `half_open_probe_at`; `4xx` on `half_open` transitions `-> closed`; failed probe resets to `open`; only 5xx/timeout/`ML_DATASET_ERROR` increment | `M10` (`worker/breaker.py`) |
| 8 | Exact bytes `input_snapshot_gz` & outgoing validation | Serialize & validate `FarmAnalysisInput` (`additionalProperties: false`), store gzip of exact wire bytes, reuse in `SEM-04` | `M7, M8, M9` (`services/analysis.py`) |
| 9 | Cross-file OpenAPI <-> JSON Schema `$ref` resolution | `referencing.Registry` resolving local `backend/contracts/schema-v5.0.json`; unknown `5.x` property tree walker logs & counts, `6.0` fails | `M0, M6, M9` (`services/verification.py`) |
| 10 | History decoupled from `crop_catalog` | Zero FK from `field_crop_history` to `crop_catalog`; preserve `catalog_version` & `crop_name_raw` | `M1, M5, M6` (`models/field.py`) |
| 11 | Deterministic canonical JSON hashing | Sorted keys, `(",", ":")`, normalized floats (`6` decimals), fields sorted by `field_id`, SHA-256 hex | `M7` (`services/canonical_hash.py`) |
| 12 | Timestamps UTC `timestamptz` | `datetime.now(timezone.utc)` everywhere; zero naive datetimes (`mypy` + `ruff DTZ`) | `M0–M13` (`core/`, all models) |
| 13 | Single-tx `DELETE /auth/me`, safe `export` & `claim-guest` | Atomic cascade wipe incl. `input_snapshot_gz`; `export` maps strict JSON omitting `bytea`/hashes; `claim-guest` locks guest row & reassigns farms before delete | `M3` (`services/auth.py`) |
| 14 | Concurrency-safe public IDs & ID hiding | `farm_<bigserial.id>` generated by DB sequence; `(farm_id, external_field_id)` protected by UNIQUE -> `409`; no internal bigints returned | `M5` (`services/farm.py`) |
| 15 | Rare `analysis_<12hex>` collision | Rely on DB `UNIQUE (analysis_id)` constraint with bounded retry on insert conflict | `M9` (`repositories/analysis.py`) |
| 16 | Zero secrets / PII in logs | Dedicated `structlog` processor stripping `password`, `token`, `api_key`, `guest_token`, emails at `INFO`, and raw farm bodies | `M0–M13` (`core/logging.py`) |

---

## 6. Test Strategy (8 Verification Layers — Master Prompt `§8`)

Every test suite runs against real Docker services (`postgis/postgis:16-3.4` + `redis:7-alpine`):
1. **Unit (`tests/unit/`):** `INPUT-01..03` (incl. every Hemisphere × Season × Month cell), `SEM-01..07` positive/negative, canonical hashing golden vectors, quarter quota math, interpolated two-bucket sliding-window Lua atomicity & clamped `EXISTS`-guarded `DECRBY`/`DEL`, `TRUSTED_PROXY_CIDRS` extraction, `APP_ENV=production` + `ML_PROVIDER_MODE=mock` `ValueError` fail-fast, `FieldPatchRequest` nested validation, JWT dual-key/alg rejection, ML error mapping table.
2. **Migration (`tests/migration/`):** `upgrade head` -> `downgrade base` -> `upgrade head`; DDL constraint/index introspection; empty initial `crop_catalog` check; `ml_reader` `SELECT` allowed on `dataset.*` (including simulated `ML_DATASET_OWNER_ROLE` tables) and `InsufficientPrivilege` on `public.*` / `CREATE`.
3. **Contract (`tests/contract/`):** All 34 routes validated against Option-A `openapi.yaml` via `openapi-core` / `schemathesis` (incl. normative `429`/`500`/`503` responses); all 19 ErrorCodes reachable & envelope-compliant; unknown-field `5.1` pass vs `6.0` fail (`25 $refs` targeting `14` `$defs`).
4. **Fixtures (`tests/contract/` + `tests/integration/`):** Verified Fixtures `9.1–9.4` + named tests for every `Visual I/O §10` case (`1`–`8`) + Redis `429` (`6` buckets incl. `120 req/min` poll bucket, non-burning Step 2 `403`, Redis outage `503`, PG->Redis hydration) vs `403` + `MLProviderManager` switchover + `mock-ml` container wire HTTP tests.
5. **Integration (`tests/integration/`):** Full `W1`–`W4` flows end-to-end (guest -> farm -> field -> analysis -> mock ML -> poll -> selection switch -> fetch; outside-Guelma registered flow; populated `claim-guest` ordering; `DELETE /auth/me`; `GET /auth/me/export` bytea/secret exclusion; `GET /catalog` `502` cold-start; `POST /analysis?wait=true` error translation).
6. **Mock ML Modes (`app/ml_client/mock_adapter.py`):** Deterministic fixture responses + switchable failure injection (`500`, `503`, `429`, `413`, `400`, `401`, `409`, `422`, `ML_DATASET_ERROR`, corrupt JSON, wrong `dataset_version_used`, extra fields, `6.0`).
7. **Concurrency & Fault Injection (`tests/concurrency/`):** Multi-worker `SKIP LOCKED` race, 8-slot advisory bulkhead cap & DB pool headroom, refresh-token race, idempotency savepoint race, guest farm/field row-lock race, 0-row parent `analysis_results FOR UPDATE` selection switch race, breaker 5-failure open -> 30s single-flight `half_open` probe (`4xx -> closed` & `5xx -> open`) -> recovery & non-chaining `last_good_replay` survival across `/analysis/{id}`, killed worker reclaim, `pending` cancel immediate refund, mid-flight backoff-sleep cancel & final `cancelled_at IS NULL` cascade guard race.
8. **Security (`tests/integration/test_security.py`) & Golden (`tests/golden/`):** Foreign `404`, Guelma guest `422`, forged/`alg=none` JWT, PII-free `FarmAnalysisInput` assertion, SQLi & body-limit hardening, and `backend/tests/golden/` runner skeleton (`# TODO(OQ-6)`).

---

## 7. Definition of Done (Master Prompt `§9`)

- **Development Milestones (`M6`–`M10` Fast Loop):** To accelerate iteration across WSL2/Docker, keep only the infrastructure containers running in WSL (`wsl -d Ubuntu -- docker compose up -d db redis`), **without** rebuilding `api`/`worker`/`migrate`/`mock-ml` Docker images or launching the full Compose application stack at every milestone gate. Each milestone closes with verified terminal output from `.venv` directly against live `db` (`postgis/postgis:16-3.4`) and `redis` (`redis:7-alpine`) showing: `ruff` + `mypy` + `verify_contracts.py` clean, `alembic` migrations valid, 0 failing tests (`>= 90%` coverage on `auth`, `validators/SEM`, `worker`, `breaker`, `ml_client`, `rate_limit`), updated `TRACEABILITY.md` / `DECISIONS.md` / `DESIGN_ISSUES.md`, and an approved `M<n>` commit on branch `backend-system`.
- **Integrated Container Bring-up & Compose E2E Gate (`M11` / `M13`):** Full image rebuild and orchestrated startup of all project containers (`migrate`, `api`, `worker`, and `mock-ml` alongside `db` and `redis`), Compose/`.env` config validation, container `healthcheck` verification (`/health` `curl` + `python -m app.worker.healthcheck`), and full E2E stack boot from **fresh Docker volumes** (`docker compose down -v`) are reserved as a dedicated integrated verification gate within `M11`/`M13`.
- **Overall Release Gate:** `verify_contracts.py` reports **`34/34` routes, `13/13` tables, `19/19` error codes, `40/40` normative env vars (+ `7` Companion Settings), `3/3` `INPUT` rules, `7/7` `SEM` rules**, fresh-volume Compose E2E passes cleanly, and every testable KPI from `Blueprint §1.1` passes.
