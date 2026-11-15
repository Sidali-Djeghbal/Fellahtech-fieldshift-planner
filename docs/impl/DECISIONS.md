# Architectural & Implementation Decisions Log (`DECISIONS.md`)

Engineering decisions made for ambiguities, gaps (`G1`–`G21`), and contract nuances discovered during Phases 1–3, in ADR format (`IMPL-001` through `IMPL-021`).

---

## `IMPL-001` — Centralized Redis Rate Limiting (`429`) + Durable PostgreSQL Guest Quotas (`403`)
- **Status:** Accepted (User Approved via `/grill-me`, `G1` & `G1b`; Revised per First Audit `C3`, `D7`)
- **Context:** Time-window rate limits (`GUEST_CREATE_PER_IP_HOUR=5`, `GUEST_BURST_PER_MIN=30`, `RATE_LIMIT_CRUD_PER_MIN=60`, `120 req/min` poll bucket, `RATE_LIMIT_ANALYSIS_PER_HOUR=10`, `ANALYSIS_PER_IP_HOUR=15`) need to work accurately across horizontally scaled `api` replicas without adding tables to the 13-table `public` PostgreSQL schema. Meanwhile, guest session business limits (`GUEST_MAX_ANALYSES=10` = `40` canonical quarters, `GUEST_MAX_FARMS=3`, `GUEST_MAX_FIELDS_PER_FARM=5`) are durable 7-day session limits (`403 GUEST_LIMIT_REACHED`).
- **Decision:**
  1. **Backend-Only Redis Service:** Add `redis:7-alpine` (`REDIS_URL=redis://redis:6379/0`, `40`th `.env` variable) behind the backend network (never accessible from Frontend). Both `api` and `worker` services declare `depends_on: redis: condition: service_healthy`.
  2. **Atomic Two-Bucket Sliding-Window Rate Limiting & PII-Safe Keys (`429` + `Retry-After`):** Implement an atomic Lua **interpolated integer two-bucket sliding-window** counter script (using `current` + `prev` bucket keys, returning the exact incremented `bucket_key` to callers for rollback) across all 6 rate-limited buckets, including the dedicated **`120 req/min` poll bucket** (`GET /analysis/requests/{request_id}` per `openapi.yaml` L829, exempt from `GUEST_BURST_PER_MIN=30` and `RATE_LIMIT_CRUD_PER_MIN=60`). Key format uses hashed IP/token digests rather than raw IPs/guest tokens (`rl:crud:u:{uid}:{b}`, `rl:crud:g:{tok_hash16}:{b}`, `rl:poll:{actor_key}:{b}`, `rl:guest_create:ip:{ip_sha256}:{b}`, `rl:analysis:ip:{ip_sha256}:{b}`, `rl:analysis:u:{uid}:{b}`). Client IP extraction trusts `X-Forwarded-For` **only** when the peer IP belongs to `TRUSTED_PROXY_CIDRS` (`""` default = direct peer IP only).
  3. **Durable PostgreSQL Quotas + Atomic Cache-Miss Hydration:** PostgreSQL (`guest_sessions`, `farms`, `fields`, `analysis_requests`) remains the authoritative durable source for 7-day guest quotas (`403 GUEST_LIMIT_REACHED`), mirrored in Redis key `guest_quota:{token_hash}:quarters` with TTL matching remaining `guest_sessions.expires_at`. On any Redis cache miss (`GET == nil`, e.g., Redis restart/eviction), the backend locks `guest_sessions` (`FOR UPDATE`), computes `SELECT COALESCE(SUM(ar.quota_units), 0) FROM analysis_requests ar JOIN farms f ON f.id = ar.farm_id WHERE f.guest_session_token = :tok`, and atomically populates Redis via Lua `SET key val EX ttl NX`.
  4. **Non-Burning W1 Step 2 Pre-Check & Step 5 Commit / Compensation (`POST /analysis`):** In `POST /analysis`, Step 2 (`429`/`403`) performs the atomic rate-limit check/increment and then wraps **both** the locked PG `guest_sessions FOR UPDATE` quota check (`403 GUEST_LIMIT_REACHED`) and Steps 3–5 (`422`, `400`, `409`, `503`) inside a single `try ... except:` block that executes a compensating Lua `DECRBY` on the exact returned rate-limit `bucket_key`s — so `403`, `400`, `422`, `409`, and `503` errors never burn hourly user or IP quarters. Redis guest quarter updates occur **only after** Steps 3–4 pass and the DB `INSERT` succeeds; any guest quota rollback/refund executes a Lua `if redis.call('EXISTS', key) == 1` clamped `DECRBY >= 0` (preserving TTL) or `DEL` (never leaving negative `TTL = -1` keys).
  5. **Redis Failure Contract (`503`):**
     - `GET /health?check=ready|dependencies` returns **`503 SERVICE_UNAVAILABLE`** when Redis is unreachable.
     - Request-path rate limiting fails closed (`503 SERVICE_UNAVAILABLE` with `Retry-After: 5`, structured `CRITICAL` log, `redis_errors_total` metric) when `REDIS_FAIL_CLOSED=true` (default) so abuse/IP ceilings cannot be bypassed during outages.
     - Worker ML refunds (`IMPL-011`) commit PostgreSQL `quota_units = 0` unconditionally even if Redis is briefly offline, logging `WARNING` (`redis_quota_sync_failed`) and letting cache-miss hydration / `DEL` key invalidation re-sync Redis cleanly.
- **Consequences:** Preserves the exact `13`-table `public` schema, eliminates TOCTOU and validation-burn bugs, recovers transparently from Redis restarts, and keeps Frontend completely isolated from Redis.

## `IMPL-002` — 24-Hour `Idempotency-Key` Window vs `uq_analysis_idempotency`
- **Status:** Accepted (User Approved, `G2`; Hardened per First Audit `D6`)
- **Decision:** On `POST /api/v1/analysis` with `Idempotency-Key`:
  - Query `public.analysis_requests WHERE farm_id = :farm_id AND idempotency_key = :key`.
  - If found and `created_at >= now() - interval '24 hours'`: return the existing queued/completed job (`202`, or `200` / error if `?wait=true` & `ALLOW_SYNC_WAIT=true`, `0` extra quota/rate burn) if `full_input_hash` matches; raise `409 CONFLICT` if `full_input_hash` differs.
  - If found and `created_at < now() - interval '24 hours'`: `UPDATE public.analysis_requests SET idempotency_key = NULL WHERE request_id = :old_id` inside the admission transaction before inserting the new request. Reaper also clears keys older than `24h`.
  - **Concurrency Race Guard:** On simultaneous identical submissions with the same `(farm_id, idempotency_key)`, execute the `INSERT` inside a savepoint / catch `UniqueViolation` (`uq_analysis_idempotency`), roll back any Step 2 rate-limit increment via Lua `DECRBY`, re-select the winning row cleanly, and return `202` (matching hash) or `409 CONFLICT` (differing hash).
- **Consequences:** Honors both `24h` deduplication semantics (`ENDPOINTS B.7`) and `uq_analysis_idempotency` cleanly under high concurrency.

## `IMPL-003` — Canonical JSON Hashing (`input_hash` / `full_input_hash`) & 24h What-If Window
- **Status:** Accepted (User Approved, `G3`)
- **Decision:**
  - Normalize `FarmAnalysisInput` dict: sort `fields[]` by `field_id`, sort each field's `crop_history[]` by `(year, season, planting_month or 0, crop_id or "")`, normalize floats with `round(float(x), 6)` while keeping integers as ints, exclude `request_id`.
  - Serialize via `json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")`.
  - `full_input_hash = sha256(canonical(payload_without_request_id))`.
  - `input_hash = sha256(canonical(payload_without_request_id_and_weights_and_scenario_overrides))`.
  - Recent What-If window = `24` hours on the same `farm_id` (sets `quota_units = 1` and populates `parent_request_id` to the most recent matching `request_id`).
- **Consequences:** `last_good_replay` and What-If quarter accounting are bit-for-bit deterministic across restarts and replicas.

## `IMPL-004` — Acceptance of `ADR-7`, `ADR-8`, and `ADR-9`
- **Status:** Accepted (User Approved, `G4`)
- **Decision:** Updated `ADR.md` and `SYSTEM DESGIN.md` so `ADR-7`, `ADR-8`, and `ADR-9` carry `Status: Accepted` (`2026-11-15`).

## `IMPL-005` — Safe Idempotent `ml_reader` Migration & `ALTER DEFAULT PRIVILEGES FOR ROLE`
- **Status:** Accepted (User Approved, `G5`; Revised per First Audit `D3`)
- **Decision:** Alembic migration reads `ML_READER_PASSWORD`, `ML_DB_CONNECTION_LIMIT`, and `ML_DB_STATEMENT_TIMEOUT_MS` at runtime without echoing password SQL in Alembic or app logs; checks `pg_roles` for idempotent `CREATE ROLE` / `ALTER ROLE`; sets `REVOKE ALL ON SCHEMA public`, `REVOKE ALL ON ALL TABLES IN SCHEMA public`, `GRANT USAGE/SELECT ON SCHEMA dataset`, `REVOKE CREATE ON SCHEMA dataset`; and executes **`ALTER DEFAULT PRIVILEGES IN SCHEMA dataset GRANT SELECT ON TABLES TO ml_reader`** plus optional `FOR ROLE <dataset_loader_role>` (configurable via `ML_DATASET_OWNER_ROLE` companion setting if the external ML team's pipeline loads `Schema: dataset` tables under a distinct role, documented in `RUNBOOK.md` and checked in `M1` isolation tests). Handles non-superuser CI/managed Postgres permissions explicitly via pre-flight role capability check.

## `IMPL-006` — Worker Cooperative Cancellation & Pinned Connection Advisory Locks
- **Status:** Accepted (User Approved, `G6`; Revised per First Audit `C5`, `D6`)
- **Decision:**
  - Each worker concurrency slot holds one dedicated SQLAlchemy/asyncpg connection for `pg_try_advisory_lock(slot)` (`slot` in `1001..1008`) across the entire ML invocation, runs `MLProviderManager.analyze()` (including any bounded backoff sleep `2s + jitter` / `Retry-After <= 5s`) inside a cancellable `asyncio.Task`, polls `cancelled_at IS NOT NULL` (and farm existence) every `2s`, calls `task.cancel()` on cancellation (aborting active `httpx` streams and backoff sleeps immediately), and releases `pg_advisory_unlock(slot)` inside `finally:` on the same connection (with connection close as defense-in-depth).
  - **Pre-Dispatch & Final Cascade Cancellation Checks:** Right before acquiring the ML call / setting `sent_at = now()`, worker locks the row `FOR UPDATE` and verifies `cancelled_at IS NULL AND status = 'running'`; if already cancelled before `sent_at` was set, transitions cleanly to `status = 'cancelled', quota_units = 0` and updates Redis via Lua `EXISTS`-guarded clamped `DECRBY`/`DEL` without calling ML. Similarly, the final `analysis_results` persistence transaction verifies **both `row.status == 'running' AND row.cancelled_at IS NULL`**; if `cancelled_at IS NOT NULL`, transitions to `status = 'cancelled'` without inserting `analysis_results` (even if ML returned within the `2s` poll window).

## `IMPL-007` — Exact `analysis_results.status` <-> `analysis_requests.status` Mapping
- **Status:** Accepted (User Approved, `G7`)
- **Decision:**
  - Valid ML `ok` -> `analysis_results(status='ok', validation_passed=true)` + `analysis_requests(status='ok', error_code=NULL)`.
  - Valid ML `partial` -> `analysis_results(status='partial', validation_passed=true)` + `analysis_requests(status='partial', error_code=NULL)`.
  - Stage 1 or `SEM-01..06` failure -> `analysis_results(status='invalid', validation_passed=false)` + `analysis_requests(status='failed', error_code='ML_INVALID_RESPONSE')`.
  - `SEM-07` mismatch -> `analysis_results(status='invalid', validation_passed=false)` + `analysis_requests(status='failed', error_code='DATASET_VERSION_UNAVAILABLE')`.

## `IMPL-008` — Mandatory ML Adapter Pattern (`app/ml_client/`) & Production Fail-Safe Config
- **Status:** Accepted (User Approved, `G8`; Revised per First Audit `C2`)
- **Decision:** Define `MLAdapter` ABC (`analyze`, `get_catalog`, `get_health`, `provider_name`) in `app/ml_client/base.py` with:
  - `RealMLAdapter`: HTTP `/v1/*` client via `httpx.AsyncClient` (`X-ML-API-Key` + `ML_SERVICE_PREVIOUS_API_KEY` 1x retry + gzip + timeouts).
  - `MockMLAdapter`: deterministic local provider backed by verified Fixtures `9.3` & `9.4` (dynamically preserving `request_id`, `dataset_version`, requested `field_id`s, `horizon_seasons`, `target_crop_ids`, and excluded crops) + switchable fault-injection test modes.
  - `MLProviderManager`: controlled explicitly via Companion App Settings (`APP_ENV=production|development|test` defaulting fail-safe to **`production`**, `ML_PROVIDER_MODE=auto|real|mock` defaulting to **`auto`**, and `ML_HEALTH_CHECK_INTERVAL_SECONDS=30` — outside the normative 40 `.env` vars):
    1. **Strict Production Isolation ("Zero Pretend Precision"):** When `APP_ENV == 'production'`, configuring `ML_PROVIDER_MODE == 'mock'` raises a startup **`ValueError`** (fail-fast in `config.py`). When `APP_ENV == 'production'` OR `ML_PROVIDER_MODE == 'real'`, **`MockMLAdapter` is NEVER selected or fallen back to** — real `ML_SERVICE_URL` (`https://` enforced outside local dev) and `ML_SERVICE_API_KEY` fail fast at startup, and outages feed `public.ml_breaker_state` + `last_good_replay` / `502 ML_UNAVAILABLE`.
    2. **Dev/Test Auto-Selection:** Only when `APP_ENV in ('development', 'test')` and `ML_PROVIDER_MODE == 'auto'`, if `RealMLAdapter` is unconfigured or `/v1/health` is unreachable during periodic readiness probe, `MLProviderManager` selects `MockMLAdapter` for local DX and periodically checks `/v1/health` to auto-promote back to `RealMLAdapter`. When `ML_PROVIDER_MODE == 'mock'`, always uses `MockMLAdapter`.
    3. **Never Mask In-Flight Failures or 4xx Errors:** Regardless of mode, `MLProviderManager` **never** silently falls back mid-request on an ML HTTP error (`400`, `401`, `409`, `413`, `422`, `429`, `500`, `502`, `503`, timeout, or Stage 1/2 failure). Every analysis logs `ml_provider` (`real_ml` | `mock_ml`) and increments Prometheus series `ml_active_provider`.
    4. **Consistent Cross-Container Provider Reporting (`api` vs `worker`):** `worker`'s health-probe loop writes the active provider snapshot (`ml:provider_status` key with `2 * ML_HEALTH_CHECK_INTERVAL_SECONDS` TTL) in Redis so `GET /health` in `api` reports consistent `ml_service` status across containers without in-memory split-brain.

## `IMPL-009` — Dev/Test Seeds, Cold-Start Catalog Safety & Container Tooling
- **Status:** Accepted (User Approved, `G8` & `G9`; Revised per First Audit `D2`, `E2` & `IMPL-023`)
- **Decision:**
  1. Alembic `002_seed_reference_data.py` idempotently seeds **only**: `demo_locations` (`id=1, code='guelma'`, 10-vertex non-authoritative `MultiPolygon` `# TODO(OQ-D7)`, without any backend default parcel per `IMPL-023`), `dataset_registry` (`2026.11-guelma-v1`, `is_active=true`), and `ml_breaker_state` (`id=1`).
  2. Do **NOT** unconditionally seed `public.crop_catalog` in Alembic migration `002`, so `GET /api/v1/catalog` preserves authentic empty-catalog bootstrap (`502 ML_UNAVAILABLE` if upstream `/v1/catalog` is unreachable — `ENDPOINTS B.8`). During `api`/`worker` lifespan startup (or first `GET /catalog` miss), `MLProviderManager.get_catalog()` populates `crop_catalog` (using `MockMLAdapter` returning Fixture `9.4` only when `APP_ENV in ('development','test')` and mode permits).
  3. Include `curl` in `Dockerfile`, implement `python -m app.worker.healthcheck`, and provide both fast in-process `MockMLAdapter` AND an optional `mock-ml` ASGI container under Compose `profiles: ["dev", "test"]` (specifically to test `RealMLAdapter`'s HTTP/gzip/`X-ML-API-Key`/timeout wire transport end-to-end).

## `IMPL-010` — Leader-Elected Periodic Catalog Sync & Reaper in Worker
- **Status:** Accepted (User Approved, `G10`)
- **Decision:** Worker runs periodic `catalog_sync` (`ML_CATALOG_SYNC_HOURS=6`, retaining `N` and `N-1` versions) and `reaper` (every `15s` for expired leases where `lease_until < now()` + every `1h`/`6h` for expired `guest_sessions` & `>24h` `idempotency_key` cleanup), guarded by `pg_try_advisory_lock(hashtext('catalog_sync'))` and `pg_try_advisory_lock(hashtext('reaper'))`.

## `IMPL-011` — Guest ML Refund Counter & Redis Cache Sync
- **Status:** Accepted (User Approved, `G11`; Hardened per First Audit `C3`, `C5`)
- **Decision:** Count ML-error refunds in SQL across the guest session's farms as `COUNT(*) FROM analysis_requests ar JOIN farms f ON f.id = ar.farm_id WHERE f.guest_session_token = :tok AND ar.status = 'failed' AND ar.sent_at IS NOT NULL AND ar.quota_units = 0`. Only `502`/`504` external ML failures (`ML_UNAVAILABLE`, `ML_TIMEOUT`, `ML_INVALID_RESPONSE`, `ML_CONTRACT_ERROR`, `DATASET_VERSION_UNAVAILABLE`, `ML_DATASET_ERROR`, `INTERNAL_ERROR` on exhausted `413`) refund `quota_units = 0` up to `GUEST_MAX_ML_REFUNDS=3` and update Redis `guest_quota:{token_hash}:quarters` using a Lua `EXISTS`-guarded clamped `DECRBY >= 0` (preserving TTL) or `DEL` (never creating negative `TTL = -1` keys on missing cache entries, logging non-fatal warning on transient Redis error so PG commit always succeeds). Pre-dispatch cancellations (`sent_at IS NULL`) always refund `0` quarters (`quota_units = 0`) cleanly without consuming one of the 3 ML failure refunds (`IMPL-020`).

## `IMPL-012` — SHA-256 Digest in `guest_sessions.guest_token`
- **Status:** Accepted (User Approved, `G12`)
- **Decision:** Always store `sha256_hex(raw_guest_token)` (`64` hex chars) in `guest_sessions.guest_token` and `farms.guest_session_token`. Return raw `guest_token` (`gst_<24hex>`) once from `POST /auth/guest`; never log or persist raw tokens.

## `IMPL-013` — Synchronous Assembly & Compression of `input_snapshot_gz` at Admission
- **Status:** Accepted (User Approved, `G13`)
- **Decision:** `POST /analysis` assembles the strict allowlisted `FarmAnalysisInput` JSON, validates it against `schema-v5.0.json#/$defs/FarmAnalysisInput`, gzip-compresses the exact wire bytes, and persists `input_snapshot_gz` into `public.analysis_requests` in the initial `INSERT`. Worker decompresses and forwards those exact bytes (only re-serializing to trim older `crop_history` items on `413 PAYLOAD_TOO_LARGE` or exceeding `ML_MAX_PAYLOAD_BYTES`).

## `IMPL-014` — JWT `fid` (`family_id`) Claim for Empty-Body `POST /auth/logout`
- **Status:** Accepted (Implementation Clarifying Decision)
- **Decision:** Embed `"fid": str(family_id)` in every issued HS256 access JWT payload. `POST /auth/logout` revokes `family_id` matching body `refresh_token` if provided, or `fid` from the verified access JWT otherwise.

## `IMPL-015` — Pre-Designated Demo Parcel Preview Lifecycle (`POST /auth/guest`)
- **Status:** Superseded by `IMPL-023` (User Requested Frontend-Only Demo Parcels)
- **Original Decision:** `POST /auth/guest` read `default_parcel_*` from `public.demo_locations` to return `demo_parcel`. Removed in `IMPL-023` so frontend supplies all demo farms/parcels freely inside `demo_locations.boundary`.

## `IMPL-016` — `?lang` Display Projection on `GET /catalog`
- **Status:** Accepted (Implementation Clarifying Decision)
- **Decision:** Always return full `names: {en, fr, ar}`, and populate `display_name = names.get(lang or "en", names["en"])` on `GET /api/v1/catalog` so both `schema-v5.0.json#/$defs/CropItem` and `?lang` localization pass cleanly.

## `IMPL-017` — 13-Table Persistence & Read Reconstruction for `last_good_replay` (`C1`, `M10`)
- **Status:** Accepted (First Audit Resolution `G17`)
- **Context:** Neither `public.analysis_requests` nor `public.analysis_results` has a `degraded_mode` column, and adding columns/tables violates the strict `13`-table database invariant. Yet `GET /analysis/requests/{request_id}`, `GET /analysis/{analysis_id}`, `POST /analysis?wait=true`, and `PATCH /analysis/{analysis_id}/selection` all require deterministic `degraded_mode` persistence (`{kind: "last_good_replay", stale: true, source_analysis_id, created_at, dataset_version, age_seconds}`) and isolated per-analysis selection storage (`ADR-8`, `openapi.yaml`).
- **Decision:**
  1. **Replay Criteria on Source Candidate (`res_src`):** Query latest row with `req_src.farm_id = req_new.farm_id`, `req_src.full_input_hash = req_new.full_input_hash`, `req_src.received_at IS NOT NULL` (live ML result — prevents chain-replaying an already degraded replay), `res_src.validation_passed = true`, `res_src.status IN ('ok', 'partial')`, and `res_src.created_at >= now() - make_interval(hours => DEGRADED_MODE_MAX_AGE_HOURS)`.
  2. **Deterministic Persistence Using Exact Existing Columns:**
     - Insert a self-contained row `res_new` into `public.analysis_results`: fresh Backend-minted `analysis_id` (`^analysis_[0-9a-f]{12}$`), `request_id = req_new.request_id`, `status = res_src.status`, `dataset_version_used = res_src.dataset_version_used`, `ml_engine_version = res_src.ml_engine_version`, `result_json = res_src.result_json` (write-once copy), `validation_passed = true`, `validation_errors = NULL`.
     - Update `req_new` in `public.analysis_requests`: `status = res_src.status`, **`received_at = NULL`** (since no live ML HTTP payload was received), **`error_code = f"last_good_replay:{res_src.analysis_id}"`** (zero DB CHECK constraint on `error_code`; internal marker only — never emitted into API `PollErrorObject` when `status IN ('ok','partial')`).
  3. **Read-Time Reconstruction:** On `GET /analysis/requests/{id}`, `GET /analysis/{analysis_id}`, and `POST /analysis?wait=true`: whenever `req.status IN ('ok', 'partial')` and `req.error_code` starts with `"last_good_replay:"` (or `req.received_at IS NULL`), extract `source_analysis_id`, look up `res_src` (via `source_analysis_id`) to get `source_created_at` and `dataset_version`, and assemble `degraded_mode = DegradedModeMetadata(kind="last_good_replay", stale=True, source_analysis_id=..., created_at=source_created_at, dataset_version=..., age_seconds=max(0, int((now_utc - source_created_at).total_seconds())))`.
  4. **Breaker Half-Open Probe Rules (`D5` & Second Audit #5):** Inside `SELECT ... FOR UPDATE` on `ml_breaker_state (id=1)`: if the single-flight `half_open` probe fails (`5xx`/timeout/`ML_DATASET_ERROR`), immediately reset `state = 'open'`, `opened_at = now()`, `half_open_probe_at = NULL` (full cooldown `30s`); if the probe reaches ML and returns a valid non-breaker `4xx` response (e.g., `422 INSUFFICIENT_DATA`, `400`, `409`), transition **`half_open -> closed`** (`consecutive_failures = 0`, `half_open_probe_at = NULL`) so valid client/domain rejections never leave the breaker wedged in `half_open`.
- **Consequences:** Zero schema drift (`13` tables, identical DDL), completely isolated `analysis_selections` per `analysis_id`, clean `GET /farms/{id}/analyses` joins, and guaranteed `degraded_mode.stale = true` on both polling and permalink fetches.

## `IMPL-018` — Explicit Scope of 40 Normative `.env` Vars vs Companion App Settings (`E1`)
- **Status:** Accepted (First Audit Resolution `G18`)
- **Decision:** Keep `.env.example` and `verify_contracts.py` validating **all `40` normative spec variables** from `ENDPOINTS Section C`. Declare any additional implementation/safety tuning knobs (`APP_ENV`, `ML_PROVIDER_MODE`, `ML_HEALTH_CHECK_INTERVAL_SECONDS`, `SEM04_NUMERIC_TOLERANCE`, `TRUSTED_PROXY_CIDRS`, `REDIS_FAIL_CLOSED`, `ML_DATASET_OWNER_ROLE`) in a clearly documented **Companion Settings** group in `app/core/config.py` and `.env.example` with fail-safe defaults (`APP_ENV=production`, `ML_PROVIDER_MODE=auto`, `REDIS_FAIL_CLOSED=true`).

## `IMPL-019` — Guest Farm/Field Row-Locking & `FieldPatchRequest` Deep Validation (`C3`, `C4`, `D8`)
- **Status:** Accepted (First Audit Resolution `G19`)
- **Decision:**
  1. `POST /farms` (guest) acquires `SELECT ... FROM public.guest_sessions WHERE guest_token = :tok AND expires_at > now() FOR UPDATE` before verifying `count < GUEST_MAX_FARMS (3)`.
  2. `POST /farms/{farm_id}/fields` locks parent `public.farms WHERE id = :fid FOR UPDATE` (plus validates non-expired `guest_sessions` when guest) before verifying `count < GUEST_MAX_FIELDS_PER_FARM (5)` and inserting; duplicate `(farm_id, external_field_id)` returns `409 CONFLICT` cleanly.
  3. Although `openapi.yaml` types `FieldPatchRequest.location`, `.soil`, `.water` as `type: object`, Pydantic schemas (`FieldLocationPatch`, `FieldSoilPatch`, `FieldWaterPatch` with `extra="forbid"`) strictly validate every enum/range constraint matching `public.fields` DDL (`400 INVALID_INPUT` on bad subfields), deep-merge subfields onto existing values, recalculate `soil_source` (`'farmer'` if `soil_type != 'unknown'` or any lab metric present, else `'unknown'`), clear `water_source_other` if `water.source != 'other'`, and atomically replace `field_crop_history` when supplied (rejecting duplicate `(year, season)` entries with `400`/`409`).

## `IMPL-020` — `POST /cancel` Pending Refund, `PATCH /selection` Switch & `?wait=true` Error Translation (`C5`, `D6`)
- **Status:** Accepted (First Audit Resolution `G20`)
- **Decision:**
  1. **`POST /analysis/requests/{request_id}/cancel` (`pending` vs `running`):** Lock row `FOR UPDATE`. If `status == 'pending'`, immediately set `status = 'cancelled', cancelled_at = now(), quota_units = 0` inside `/cancel` and update Redis guest quarters via Lua `EXISTS`-guarded clamped `DECRBY >= 0` / `DEL` (`409` on terminal statuses). If `status == 'running'`, set `cancelled_at = now()`; worker aborts pre-dispatch (refunding if `sent_at IS NULL`), mid-flight, or in its final `cancelled_at IS NULL` cascade guard without inserting results (`sent_at IS NOT NULL`).
  2. **`PATCH /analysis/{analysis_id}/selection`:** Lock parent **`public.analysis_results WHERE analysis_id = :aid FOR UPDATE`** (always exists, preventing `0`-row phantom lock races on `analysis_selections`); when setting `'selected'` on `strategy_id`, first `DELETE FROM analysis_selections WHERE analysis_id = :aid AND field_id = :fid AND strategy_id <> :sid AND selection_status = 'selected'` inside the same transaction before `INSERT ... ON CONFLICT (analysis_id, field_id, strategy_id) DO UPDATE`, eliminating `idx_one_selected_strategy_per_field` `UniqueViolation` even on concurrent initial selections.
  3. **`POST /analysis?wait=true` Error Translation:** When `ALLOW_SYNC_WAIT=true` and polled row terminates with `status == 'failed'`, translate `error_code` back to its documented `PollErrorObject.http_equivalent` (`INSUFFICIENT_DATA -> 422`, `ML_TIMEOUT -> 504`, `INTERNAL_ERROR -> 500`, `ML_*`/`DATASET_VERSION_UNAVAILABLE -> 502`, timeout waiting -> `504 JOB_TIMEOUT`).

## `IMPL-021` — `GET /auth/me/export` Serialization & `POST /auth/claim-guest` Cascade Safety (`D1`, `D4`)
- **Status:** Accepted (First Audit Resolution `G21`)
- **Decision:**
  1. **`GET /auth/me/export`:** Never raw-serialize ORM models. Map explicitly to `UserDataExport` (`UserProfile`, `FarmPublic`, `FieldDetailPublic` including `warnings[]` & `crop_history[]`, safe `analysis_requests` dicts explicitly **omitting `input_snapshot_gz`**, `analysis_results`, `analysis_selections`). Zero `password_hash`, `token_hash`, or raw bytes.
  2. **`POST /auth/claim-guest`:** Lock `guest_sessions` (`FOR UPDATE`, verify `expires_at > now()`), execute `UPDATE public.farms SET user_id = :uid, guest_session_token = NULL WHERE guest_session_token = :tok` **before** `DELETE FROM public.guest_sessions WHERE guest_token = :tok` (avoiding `ON DELETE CASCADE` farm wipe), and delete Redis `guest_quota:{token_hash}:quarters`.

## `IMPL-022` — Optional & Nullable `priorities.equipment_constraints` (Fertilizer & Equipment Constraints)
- **Status:** Accepted
- **Context:** Farmers need to specify optional constraints for both **fertilizer availability** and **agricultural equipment/machinery** limits inside `priorities.equipment_constraints`, and callers may either supply constraint strings, pass `[]`, pass `null`, or omit the field entirely.
- **Decision:**
  1. Remove `equipment_constraints` from `required` in `AnalysisSubmitRequest.priorities` (`openapi.yaml`) and `FarmAnalysisInput.priorities` (`schema-v5.0.json`, kept byte-identical with `SYSTEM DESGIN/.../System Architecture Blueprint/`).
  2. Type `equipment_constraints` as `["array", "null"]` with `default: []`, keeping `maxItems: 20` and `items: {type: "string", minLength: 1, maxLength: 160}`, and document that it covers both fertilizer availability and equipment constraints.
  3. When assembling `FarmAnalysisInput` on `POST /analysis` (`M7`), normalize omitted or `null` values to `[]` while keeping `schema-v5.0.json` permissive for optional/nullable inputs.

## `IMPL-023` — Frontend-Defined Demo Parcels (`demo_locations.boundary` Retained, `default_parcel_*` / `demo_parcel` Removed)
- **Status:** Accepted (User Requested; Supersedes `IMPL-015`)
- **Context:** Keeping a backend-stored `default_parcel_*` (`F1` at `36.52° N, 7.52° E`) and returning `demo_parcel` (`DemoParcelPreview`) from `POST /auth/guest` and `GET /demo/session` tied demo workflows to a static server-side parcel stub.
- **Decision:**
  1. Remove `default_parcel_id`, `default_parcel_name`, `default_parcel_lat`, `default_parcel_lon`, and `default_parcel_area_ha` from `public.demo_locations`, ORM model `DemoLocation`, and `seed.py`, while **keeping** `demo_locations.boundary` (`MultiPolygon`, `SRID 4326`, Wilaya of Guelma) for `GET /demo/locations/{id}/boundary` and PostGIS `ST_Covers` (`422 OUTSIDE_DEMO_BOUNDARY`) enforcement.
  2. Remove `DemoParcelPreview` and `demo_parcel` from `GuestSessionStartResponse` (`POST /auth/guest`) and `GuestSessionInfo` (`GET /demo/session`) in `openapi.yaml` and backend DTOs/services. Frontend sends all demo farm/field payloads freely via `POST /farms`, `POST /farms/{farm_id}/fields`, and `POST /analysis`.
  3. Keep optional `FieldWriteRequest.is_unverified_demo_parcel` (`default: false`) and warning `DEMO_PARCEL_UNVERIFIED` so the frontend can still explicitly flag an unverified demo parcel on a field when desired without breaking `schema-v5.0.json` or ML fixtures.
