# Phase 2 — Cross-File Consistency Audit & Gaps (`01-audit-and-gaps.md`)

> **Audit Scope:** Mechanical and semantic cross-verification across all documents in `SYSTEM DESGIN/` (`SYSTEM DESGIN.md` Index v3.2 · `Blueprint.md` · `ADR.md` · `ENDPOINTS api & Database Specification.md` · `Visual Input  Output Specification.md` · `openapi.yaml` · `schema-v5.0.json`) and Phase 1–3 implementation plans (`First & Second Independent Audits`).

---

## 1. Mechanical Consistency Verification Results

Verified by Python execution against the raw files in `SYSTEM DESGIN/` (to be institutionalized as CI checks in `backend/tools/verify_contracts.py`):

| Check | Scope | Expected | Observed Result | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Duplicate Contracts** | Recursive search for `openapi.yaml` & `schema-v5.0.json` | Canonical single copy or byte-identical copies | `1` copy of `openapi.yaml` (`63,659` bytes, `SHA256_16: 034dce2ee08fc521`); `1` copy of `schema-v5.0.json` (`34,115` bytes, `SHA256_16: 9945a473276e28b8`) | **PASS** |
| **Routes Parity** | `openapi.yaml` paths vs `ENDPOINTS B.2–B.9` vs `Blueprint §7` | `34` Backend `/api/v1` operations + `3` ML `/v1` routes | `34` operations across `24` path templates (`Auth: 9`, `Demo: 4`, `Farms: 6`, `Fields: 6`, `Analysis: 6`, `Catalog: 1`, `System: 2`) match `ENDPOINTS` & `Blueprint` 1:1; `3` ML routes (`B.10`) | **PASS** |
| **OpenAPI Response Codes vs Runtime Policy** | `openapi.yaml` operation `responses` vs `ENDPOINTS B.1, B.10.4` & `IMPL-001` | Consistent `429`, `500`, `503` coverage | Option A reconciled `openapi.yaml`: `"429"` & `"503"` defined consistently on all `27` throttled session/CRUD/catalog/analysis routes (incl. **`120 req/min` poll bucket** `L829`), `"500"` (`InternalError`) on `POST /analysis`, `ServiceOrDatasetUnavailable` (`L1229`) covers DB & fail-closed Redis (`FieldPatchRequest` strict Pydantic enforcement `IMPL-019`) | **PASS** |
| **Error Codes & Notices** | `openapi.yaml#/components/schemas/ErrorCode` vs `ENDPOINTS B.1` | `19` ErrorCodes + `2` WarningNotices | Exact `19` `ErrorCode` enum values match `ENDPOINTS B.1`; exact `2` notices (`MVP_OUTSIDE_COVERAGE`, `DEMO_PARCEL_UNVERIFIED`) | **PASS** |
| **OpenAPI ⟶ JSON Schema `$ref`** | Every `./schema-v5.0.json#/$defs/...` in `openapi.yaml` | `100%` resolution inside `schema-v5.0.json` (`39` `$defs`) | `25` `$ref` occurrences targeting `14` unique `$defs` in `schema-v5.0.json` resolve with `0` missing | **PASS** |
| **Fixtures & Mutation Checks** | `Visual I/O §9.1–§9.4` + `§10 #8` vs `schema-v5.0.json` Draft 2020-12 | `0` validation errors on fixtures + `5.1` extra passes / `6.0` fails | `9.1` & `9.2` (`FarmAnalysisInput`), `9.3` (`AnalysisResult`), `9.4` (`CropCatalog`) all pass (`0` errors); `5.1` + extra field passes (`0` errors); `6.0` fails (`2` errors) | **PASS** |
| **DDL vs ERD vs Env Vars** | `ENDPOINTS A.1` ERD vs `ENDPOINTS A.4` DDL; `ENDPOINTS C` vs `Blueprint §8` | `13` `public` tables + `Schema: dataset`; `40` `.env` vars | All `13` tables match ERD columns/constraints; all `40` `.env` variables synchronized (`39` original + `REDIS_URL` per `G1b`); `7` optional Companion Settings isolated (`IMPL-018`) | **PASS** *(DDL live-run in PostGIS `16-3.4` scheduled in M1 gate)* |

---

## 2. Detailed Gap & Ambiguity Audit (`G1`–`G21`)

All gaps resolved via `/grill-me` (`G1`–`G13`), cross-spec inspection (`G14`–`G16`), the First & Second Independent Principal Architect Audits (`G17`–`G21`, Option A `SYSTEM DESGIN/` + `openapi.yaml` alignment, and 5 Phase-4 hardening rules). **Zero technical gaps remain; uncommitted `SYSTEM DESGIN/` updates (`DI-17`) await user review prior to `M0`.**

### `G1` & `G1b` — Redis Rate Limiting (`429`) vs 13-Table Durable Quotas (`403`) (`ENDPOINTS B.1, C`, `ADR-8`, `IMPL-001`)
- **Evidence:** Spec defines 6 time-window rate limits (`5/h` IP guest create, `30/min` guest burst, `60/min` user CRUD, **`120/min` poll bucket (`openapi.yaml` line 829)**, `10/h` user analysis = `40` quarters/h, `15/h` IP analysis = `60` quarters/h) and durable 7-day guest business quotas (`3` farms, `5` fields/farm, `10` analyses = `40` quarters -> `403`).
- **Resolution (`IMPL-001` Revised):** `redis:7-alpine` (`REDIS_URL`, backend-only) enforces atomic **interpolated integer two-bucket sliding-window** Lua throttles (`429` + `Retry-After`) with hashed keys & `TRUSTED_PROXY_CIDRS`-safe IP extraction. PG remains authoritative for 7-day guest quotas, locked with `SELECT ... FROM guest_sessions FOR UPDATE`, hydrated atomically from PG on Redis cache miss (`SET NX EX`), and never burned on `403`/`400`/`422`/`409`/`503` failures (Step 2 wraps both PG `403` and Steps 3–5 inside `try...except:` Lua `DECRBY` compensation on returned bucket keys; guest quota updates/refunds use Lua `EXISTS`-guarded clamped `DECRBY >= 0` / `DEL`). Both `api` and `worker` declare `depends_on: redis: service_healthy` in `Blueprint §6.1` & `docker-compose.yml`. On Redis outage: `/health` returns `503`; API fails closed `503`; worker commits PG refunds cleanly and warns on Redis sync miss. **Status: Resolved.**

### `G2` — `Idempotency-Key` 24h Window, Unique Index & Concurrency Race (`ENDPOINTS A.4, B.7`, `IMPL-002`)
- **Resolution (`IMPL-002` Revised):** Reuse `> 24h` clears old row's `idempotency_key = NULL`; concurrent identical double-submits handle `uq_analysis_idempotency` `UniqueViolation` cleanly inside savepoint, roll back Step 2 rate increment, and replay (`202`) or reject (`409`). **Status: Resolved.**

### `G3` — Canonical JSON Hashing & 24h What-If Window (`ENDPOINTS A.1, B.1`, `ADR-8`, `IMPL-003`)
- **Resolution (`IMPL-003`):** Deterministic sorted-key compact JSON with 6-decimal float normalization and sorted `fields[]`/`crop_history[]`, excluding `request_id` (`full_input_hash`) and weights/`scenario_overrides` (`input_hash`); `24h` per-farm window for `quota_units = 1`. **Status: Resolved.**

### `G4` — `ADR-7`, `ADR-8`, `ADR-9` Accepted Status (`ADR.md`, `ENDPOINTS B.1`, `IMPL-004`, `DI-03`)
- **Resolution (`IMPL-004`, Option A):** Promoted in `ADR.md` (`2026-11-15`) and stale `"ADR-7 (Proposed)"` on `ENDPOINTS B.1` line 493 reconciled to `"ADR-7 (Accepted)"`. **Status: Resolved.**

### `G5` — `ml_reader` Role Password, Non-Superuser Safety & `ALTER DEFAULT PRIVILEGES FOR ROLE` (`ENDPOINTS A.5`, `IMPL-005`)
- **Resolution (`IMPL-005` Revised):** Runtime reading of `ML_READER_PASSWORD`, secret-redacted Alembic logs, pre-flight role/extension capability checks, and `ALTER DEFAULT PRIVILEGES ... GRANT SELECT` (plus optional `FOR ROLE` via `ML_DATASET_OWNER_ROLE` if an external ML DB loader creates dataset tables). **Status: Resolved.**

### `G6` — Worker Cooperative Cancel, Retry-Sleep Abort, Final Guard & Advisory-Lock Release (`ENDPOINTS A.3`, `IMPL-006`)
- **Resolution (`IMPL-006` Revised):** Cancellable `asyncio.Task` wraps both HTTP requests and retry backoff sleeps (`2s + jitter`, `Retry-After`); pre-dispatch `FOR UPDATE` check inspects `cancelled_at IS NULL` before setting `sent_at = now()`; final `analysis_results` tx verifies **both `status == 'running' AND cancelled_at IS NULL`**; `pg_advisory_unlock(1001..1008)` runs unconditionally in `finally:` on pinned connection. **Status: Resolved.**

### `G7` — `analysis_results.status` vs `analysis_requests.status` Mapping (`ENDPOINTS A.4, B.10.4`, `IMPL-007`)
- **Resolution (`IMPL-007`):** Exact 4-row truth table (`ok->ok`, `partial->partial`, `Stage1/SEM1..6->invalid/failed/ML_INVALID_RESPONSE`, `SEM-07->invalid/failed/DATASET_VERSION_UNAVAILABLE`). **Status: Resolved.**

### `G8` & `G9` — Seed Data, Empty-Catalog `502`, & Production-Safe ML Adapter (`Blueprint §5.1, §6.1`, `ENDPOINTS B.8`, `IMPL-008`, `IMPL-009`)
- **Evidence:** `ENDPOINTS C` (`40` vars) omitted `APP_ENV` / `ML_PROVIDER_MODE`; unconditional `crop_catalog` seeding masked `GET /catalog -> 502`; unguarded in-memory `MLProviderManager` risked production fake results and `api`/`worker` split-brain.
- **Resolution (`IMPL-008` & `IMPL-009` Revised):**
  1. Alembic `002` seeds `demo_locations`, `dataset_registry`, and `ml_breaker_state` (`id=1`), leaving `crop_catalog` empty for live/adapter bootstrap (`GET /catalog -> 502` when real ML offline).
  2. Companion settings `APP_ENV` (fail-safe default `production`) and `ML_PROVIDER_MODE` (`auto` | `real` | `mock`) strictly forbid `MockMLAdapter` fallback in `production` or `real` mode and never mask in-flight ML errors or `ml_breaker_state` fault tests.
  3. `worker` publishes `ml:provider_status` in Redis so `api` `/health` agrees across replicas; optional Compose `mock-ml` profile verifies HTTP/gzip transport cleanly. **Status: Resolved.**

### `G10` — Leader-Elected Reaper & Periodic Catalog Sync (`Blueprint §3.4`, `IMPL-010`)
- **Resolution (`IMPL-010`):** Periodic `worker` background loops coordinated across replicas via `pg_try_advisory_lock(hashtext('catalog_sync' | 'reaper'))`. **Status: Resolved.**

### `G11` — Guest Quota Refunds (`GUEST_MAX_ML_REFUNDS=3`) & Pre-Dispatch Cancel (`ENDPOINTS B.1, B.7`, `IMPL-011`, `IMPL-020`)
- **Resolution (`IMPL-001`, `IMPL-011`, `IMPL-020`):** SQL count (`status='failed' AND sent_at IS NOT NULL AND quota_units=0`) enforces max 3 ML error refunds; `POST /cancel` on `pending` refunds `quota_units = 0` & decrements Redis **immediately inside the cancel endpoint transaction** (never stranded in worker). Redis `guest_quota` rollback/refund uses a Lua `if EXISTS == 1` clamped `DECRBY >= 0` (preserving TTL) or `DEL` helper so no persistent negative `TTL = -1` keys are created, and Step 2 `403 GUEST_LIMIT_REACHED` is wrapped in the W1 `DECRBY` rollback handler so `403` never burns hourly IP quotas. Redis failures during worker refunds log warnings without rolling back PG. **Status: Resolved.**

### `G12` — SHA-256 Digest in `guest_sessions.guest_token` (`ENDPOINTS A.4, B.1`, `IMPL-012`)
- **Resolution (`IMPL-012`):** Raw `gst_<24hex>` returned once; only 64-char SHA-256 hex stored. **Status: Resolved.**

### `G13` — Synchronous Payload Assembly in `input_snapshot_gz` (`ENDPOINTS A.4`, `Blueprint §4 W1/W3`, `IMPL-013`, `DI-05`)
- **Resolution (`IMPL-013`):** `POST /analysis` assembles, schema-validates, and gzips `FarmAnalysisInput` into `input_snapshot_gz`; worker forwards exact bytes (trimming history only on `413`). **Status: Resolved.**

### `G14`–`G16` — `fid` JWT Logout Claim, Demo Parcel Preview, `?lang` Catalog Projection (`IMPL-014..016`)
- **Resolution (`IMPL-014..016`):** Access JWT includes `"fid"` (`family_id`); `POST /auth/guest` previews `F1` without consuming farm quota; `GET /catalog` returns full `names` + localized `display_name`. **Status: Resolved.**

### `G17` — `last_good_replay` / `degraded_mode` Persistence Under 13 Tables & Breaker Probe Rules (`C1`, `D5`, `IMPL-017`)
- **Resolution (`IMPL-017`):** Replay inserts self-contained `analysis_results` copy (`validation_passed=true, validation_errors=NULL`) + marks `analysis_requests` (`status=res_src.status, received_at=NULL, error_code='last_good_replay:' || source_analysis_id`); read paths reconstruct `DegradedModeMetadata` deterministically with `stale=true` and `source_analysis_id`; prevents chain replays (`req_src.received_at IS NOT NULL`); `half_open` probe failure immediately resets breaker to `'open'` with fresh cooldown, while a valid ML `4xx` probe transitions **`half_open -> closed`** (`consecutive_failures=0, half_open_probe_at=NULL`). **Status: Resolved.**

### `G18` — Normative `40` Env Vars vs Companion Settings (`C2`, `E1`, `IMPL-018`)
- **Resolution (`IMPL-018`):** `40` normative `ENDPOINTS C` variables verified 1:1 by `verify_contracts.py`; `7` additional safety/tuning knobs (`APP_ENV`, `ML_PROVIDER_MODE`, `ML_HEALTH_CHECK_INTERVAL_SECONDS`, `SEM04_NUMERIC_TOLERANCE`, `TRUSTED_PROXY_CIDRS`, `REDIS_FAIL_CLOSED`, `ML_DATASET_OWNER_ROLE`) cleanly grouped as Companion Settings with fail-safe defaults (`APP_ENV=production` + `ML_PROVIDER_MODE=mock` raises startup `ValueError`). **Status: Resolved.**

### `G19` — Guest Farm/Field Row-Locking, `FieldPatchRequest` Validation & Multi-Field Warnings (`C3`, `C4`, `D8`, `IMPL-019`)
- **Resolution (`IMPL-019`):** `FOR UPDATE` serialization on `guest_sessions` (`POST /farms`) and parent `farms` (`POST /farms/{id}/fields`); strict nested Pydantic patch models (`FieldLocationPatch`, `FieldSoilPatch`, `FieldWaterPatch`) recomputing `soil_source` & `water_source_other` and validating crop-history duplicates (`ENDPOINTS B.6` L932 aligned to `FieldDetailPublic`); aggregated `WarningNotice.fields[]` on `POST /analysis`. **Status: Resolved.**

### `G20` — `120 req/min` Poll Bucket, OpenAPI `429`/`500`/`503` Reconciliation, `PATCH /selection` Lock, `?wait=true` (`C4`, `C5`, `D6`, `IMPL-020`, `DI-13`)
- **Resolution (`IMPL-020`, Option A):** Dedicated `120 req/min` Redis bucket on `GET /analysis/requests/{request_id}`; `openapi.yaml` reconciled with `"429"` & `"503"` on all `27` throttled routes plus `InternalError` (`500`) on `POST /analysis` and `ServiceOrDatasetUnavailable` DB/Redis wording; `PATCH /selection` locks **parent `public.analysis_results FOR UPDATE`** (eliminating 0-row phantom races) and deletes prior `'selected'` row before upsert; `?wait=true` translates terminal worker `error_code` to exact `http_equivalent` (`422`/`500`/`502`/`504`). **Status: Resolved.**

### `G21` — `GET /auth/me/export` `bytea` Safety, `claim-guest` Cascade Order & Uncommitted Spec Diffs (`C6`, `D1`, `D4`, `IMPL-021`, `DI-17`)
- **Resolution (`IMPL-021`):** Explicit `UserDataExport` mapper excludes `input_snapshot_gz` (`bytea`), `password_hash`, and `token_hash`, while formatting `fields[]` via `FieldDetailPublic`. `POST /auth/claim-guest` locks `guest_sessions`, updates `farms` ownership **before** deleting `guest_sessions` (`ON DELETE CASCADE`), and deletes the Redis quota key. **`DI-17` uncommitted `SYSTEM DESGIN/` updates remain on `backend-system` for user review prior to `M0`.**
