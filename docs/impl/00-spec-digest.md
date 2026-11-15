# Phase 1 — FieldShift Planner Specification Digest (`00-spec-digest.md`)

> **Document Status:** Authoritative Engineering Digest (`v3.2` — Local-Dataset Edition)
> **Source Pack:** `SYSTEM DESGIN/` ([Index](../../SYSTEM%20DESGIN/SYSTEM%20DESGIN.md) · [Blueprint](../../SYSTEM%20DESGIN/SYSTEM%20DESGIN/System%20Architecture%20Blueprint.md) · [ADR](../../SYSTEM%20DESGIN/SYSTEM%20DESGIN/Architecture%20Decision%20Records%20%28ADR%29.md) · [ENDPOINTS & DB](../../SYSTEM%20DESGIN/SYSTEM%20DESGIN/System%20Architecture%20Blueprint/FieldShift%20Planner%20—%20ENDPOINTS%20api%20%26%20Database%20Specification.md) · [Visual I/O](../../SYSTEM%20DESGIN/SYSTEM%20DESGIN/System%20Architecture%20Blueprint/Visual%20Input%20%20Output%20Specification.md) · [openapi.yaml](../../SYSTEM%20DESGIN/SYSTEM%20DESGIN/System%20Architecture%20Blueprint/openapi.yaml) · [schema-v5.0.json](../../SYSTEM%20DESGIN/SYSTEM%20DESGIN/System%20Architecture%20Blueprint/schema-v5.0.json))
> **Self-Check Totals (Verified):** **`34` Backend `/api/v1` routes** across `24` path templates · **`3` External ML routes** · **`13` `public` tables + isolated `Schema: dataset`** · **`19` error codes + `2` non-blocking notices** · **`40` normative `.env` variables** (`39` original + `REDIS_URL`) + **`7` Companion Settings** (`IMPL-018`) · **`6` Redis rate-limit buckets** (incl. `120 req/min` poll bucket per `openapi.yaml` L829) · **`25` `$ref` occurrences targeting `14` unique `$defs` in `schema-v5.0.json`** (`39` total `$defs`, `0` missing) · **`7` `SEM` rules (`SEM-01..07`)** · **`3` `INPUT` rules (`INPUT-01..03`)** · **`19` Open Questions (`OQ-1..11` + `OQ-D1..D8`)**. *(ID masking note: `/farms`, `/fields`, `/analysis` mask internal bigints; `/auth/me` & `/demo/locations` return schema-typed integer `id`s per `DI-16`.)*

---

## 3.1 Architecture Summary & Responsibility Matrix (`Blueprint §1–§3`, `ADR-1..9`, `ENDPOINTS A.5`)

FieldShift Planner is a crop-rotation planning backend and spatial API platform centered on the **Wilaya of Guelma, Algeria** (regional reference `~36.46° N, 7.43° E`; pre-designated unstudied demo parcel centroid `36.52° N, 7.52° E` — `Blueprint §1.1`, `OQ-9`). Under the **Local-Dataset Edition (`ADR-1`, `ADR-9`)**, the Backend makes **zero external HTTP calls** to NASA POWER, ORNL MODIS, ISRIC SoilGrids, SRTM, or external geocoders.

| Component | Owns (`Blueprint §2`, `§3`, `ADR-1..9`) | Explicitly Does NOT Own |
| :--- | :--- | :--- |
| **Web / Mobile Client** | Spatial polygon/point UI, JWT & `X-Guest-Token` storage, polling `GET /api/v1/analysis/requests/{request_id}`, submitting strategy selections (`PATCH /analysis/{analysis_id}/selection`), displaying `warnings[]` & `degraded_mode` badges | Never connects to PostgreSQL, Redis, or External ML directly (`Blueprint §2.1`, `ADR-8`) |
| **Backend API (`api`)** | All `34` REST endpoints (`/api/v1/*`), Auth (Argon2id, HS256 dual-key JWT, `refresh_tokens` family rotation, `X-Guest-Token` SHA-256), **Redis** centralized atomic rate limiting (`429 RATE_LIMIT_EXCEEDED`), **PostgreSQL** durable guest quotas (`403 GUEST_LIMIT_REACHED`), PostGIS `ST_Covers` boundary gate (`422 OUTSIDE_DEMO_BOUNDARY`), synchronous `INPUT-01..03`, assembling & gzipping allowlisted `FarmAnalysisInput` (`input_snapshot_gz`), enqueueing `analysis_requests` (`status='pending'`, `202 Accepted`), merging `analysis_selections` at read time | Never runs ML inference synchronously (except test-only `?wait=true` polling DB when `ALLOW_SYNC_WAIT=true`); never queries `Schema: dataset` (`Blueprint §2`, `ADR-1`) |
| **Backend Worker (`worker`)** | Durable job leasing via `FOR UPDATE SKIP LOCKED` (`WORKER_CONCURRENCY=4`, `JOB_LEASE_SECONDS=90`, `MAX_JOB_ATTEMPTS=2`), heartbeats, cascade guard, 8-slot advisory-lock bulkhead (`pg_try_advisory_lock(1001..1008)`), shared `public.ml_breaker_state` (`half_open -> open` probe reset `IMPL-017`), Redis `ml:provider_status` publishing & guest refund sync (`depends_on: redis: service_healthy`), `last_good_replay` persistence (`IMPL-017`), cooperative mid-flight cancel (`asyncio.Task.cancel()` + stream & backoff abort + pre-dispatch `sent_at` guard), dispatching via `MLProviderManager`, Stage 1 (`schema-v5.0.json`) + Stage 2 (`SEM-01..07`), minting `analysis_<12hex>`, write-once `analysis_results`, leader-elected periodic `/v1/catalog` sync (`ML_CATALOG_SYNC_HOURS=6`) & expired session / stale lease reaper (`Blueprint §2–§4`, `ENDPOINTS A.3`) | Never mutates raw `result_json` after insert; never exposes public HTTP traffic; never queries `Schema: dataset` features (`Blueprint §2`) |
| **ML Adapter Layer (`app/ml_client/`)** | Unified `MLAdapter` ABC (`analyze`, `get_catalog`, `get_health`), `RealMLAdapter` (HTTP `/v1/*` with `X-ML-API-Key`, dual-key rotation, gzip, timeouts), `MockMLAdapter` (deterministic dev/test Fixtures `9.3` & `9.4` + fault modes), `MLProviderManager` (strictly fail-safe in `APP_ENV=production` / `ML_PROVIDER_MODE=real`: zero mock fallback; auto-selects mock only when `APP_ENV in ('development','test')` and `ML_PROVIDER_MODE='auto'|'mock'`, periodic `/v1/health` probe synced to Redis, logs `ml_provider`, never masks in-flight 4xx/5xx/business errors) (`Blueprint §1, §3`, `ADR-4`, `IMPL-008`) | Never bypasses Stage 1 / Stage 2 verification, never silently falls back in production, or alters API/DB contracts |
| **Redis 7 (`redis`)** | Backend-only store (`REDIS_URL`) for atomic Lua / `INCR`+`EXPIRE` time-window rate-limit counters across `api` replicas (`429`) and cached guest quarter quota mirror (`Blueprint §1, §3.5`, `ADR-8`) | Never accessed by Frontend; never holds durable queues, circuit breaker state, or business entities |
| **PostgreSQL 16 + PostGIS 3.4 (`db`)** | `Schema: public` (**13** OLTP/resilience tables + `pg_try_advisory_lock` bulkhead) + isolated `Schema: dataset` (environmental layers read `SELECT`-only by `ml_reader`, `REVOKE ALL ON SCHEMA public`) (`ENDPOINTS A.1–A.5`, `ADR-9`) | `app_user` does not query `dataset.*` feature tables; `ml_reader` cannot read or write `public.*` feature/PII tables (`ENDPOINTS A.5`) |
| **External ML Service (`{ML_SERVICE_URL}`)** | `POST /v1/analyze`, `GET /v1/catalog`, `GET /v1/health`; reading `Schema: dataset` via `ML_DATASET_DB_URL` (`ml_reader`); scoring strategies and returning `AnalysisResult` + `dataset_version_used` (NO `analysis_id`) (`Blueprint §2`, `ENDPOINTS B.10`, `ADR-4`) | Cannot access `public.*` tables; does not mint `analysis_id`; does not enforce user quotas or Guelma PostGIS boundaries |

---

## 3.2 Tech Stack Fixed by the Design (`Blueprint §1`, `§3`, `§6.1`)

- **Runtime & Web:** Python `3.11+` (`3.12` target), FastAPI (async), Pydantic v2, Uvicorn.
- **Database & Spatial:** PostgreSQL `16` + PostGIS `3.4` (`postgis/postgis:16-3.4`), `asyncpg`, SQLAlchemy `2.x` async, GeoAlchemy2 / PostGIS SQL, Alembic via dedicated one-shot `migrate` service (`alembic upgrade head`).
- **Rate-Limit Store:** Redis `7` (`redis:7-alpine`), `redis.asyncio`, backend-only (`REDIS_URL`).
- **Async Job Queue, Breaker & Bulkhead:** PostgreSQL `FOR UPDATE SKIP LOCKED` workers (`worker` service), `public.ml_breaker_state` (`id = 1`), PostgreSQL session advisory locks `pg_try_advisory_lock(1001..1008)`.
- **Security & Validation:** `argon2-cffi` (Argon2id), `PyJWT` (`HS256`, dual-key verification with `JWT_SECRET_KEY` + `JWT_PREVIOUS_SECRET_KEY`), `hashlib.sha256`, `jsonschema` (`Draft202012Validator` + `referencing`), `httpx` async, `prometheus-client`, `structlog` (JSON logs).
- **Contracts & Compose:** OpenAPI `3.1.0` (`openapi.yaml`), JSON Schema Draft `2020-12` (`schema-v5.0.json`), Docker Compose (`db`, `redis`, `migrate`, `api`, `worker` + dev/test `mock-ml` or `MLAdapter` integration).

---

## 3.3 Database Inventory (`ENDPOINTS A.1–A.5`)

### A. All 13 `public` Schema Tables (`ENDPOINTS A.4`)

| # | Table | Columns (`name: type [NULL/NOT NULL]`) | PK & Unique Constraints | CHECK Constraints | Foreign Keys (`ON DELETE`) | Indexes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **1** | `public.users` | `id: bigserial NOT NULL`, `email: text NOT NULL`, `password_hash: text NOT NULL`, `full_name: text NOT NULL`, `preferred_lang: text NOT NULL DEFAULT 'en'`, `created_at: timestamptz NOT NULL DEFAULT now()` | `PK (id)`, `uq_users_email_lower UNIQUE (LOWER(email))` | `preferred_lang IN ('en','fr','ar')` | None | `uq_users_email_lower UNIQUE (LOWER(email))` |
| **2** | `public.refresh_tokens` | `id: bigserial NOT NULL`, `user_id: bigint NOT NULL`, `family_id: uuid NOT NULL`, `token_hash: text NOT NULL`, `used_at: timestamptz NULL`, `revoked_at: timestamptz NULL`, `expires_at: timestamptz NOT NULL`, `created_at: timestamptz NOT NULL DEFAULT now()` | `PK (id)`, `UNIQUE (token_hash)` | `char_length(token_hash) = 64` | `user_id -> public.users(id) ON DELETE CASCADE` | `idx_refresh_tokens_user_family (user_id, family_id)` |
| **3** | `public.demo_locations` | `id: bigserial NOT NULL`, `code: text NOT NULL`, `name: text NOT NULL`, `country: text NOT NULL`, `region: text NOT NULL`, `boundary: geometry(MultiPolygon, 4326) NOT NULL`, `is_active: boolean NOT NULL DEFAULT true`, `created_at: timestamptz NOT NULL DEFAULT now()` | `PK (id)`, `UNIQUE (code)` | None | None | `idx_demo_locations_boundary USING GIST (boundary)` |
| **4** | `public.guest_sessions` | `guest_token: text NOT NULL`, `demo_location_id: bigint NOT NULL`, `created_at: timestamptz NOT NULL DEFAULT now()`, `expires_at: timestamptz NOT NULL` | `PK (guest_token)` | `char_length(guest_token) = 64` | `demo_location_id -> public.demo_locations(id) ON DELETE RESTRICT` | PK index (`guest_token`) |
| **5** | `public.farms` | `id: bigserial NOT NULL`, `user_id: bigint NULL`, `guest_session_token: text NULL`, `farm_name: text NOT NULL`, `country: text NOT NULL`, `region: text NOT NULL`, `commune: text NULL`, `created_at: timestamptz NOT NULL DEFAULT now()` | `PK (id)` | `char_length(farm_name) BETWEEN 1 AND 120`, `char_length(country) BETWEEN 1 AND 80`, `char_length(region) BETWEEN 1 AND 80`, `commune IS NULL OR char_length(commune) <= 120`, `chk_farms_single_owner: (user_id IS NOT NULL) <> (guest_session_token IS NOT NULL)` | `user_id -> public.users(id) ON DELETE CASCADE`, `guest_session_token -> public.guest_sessions(guest_token) ON DELETE CASCADE` | PK index (`id`) |
| **6** | `public.fields` | `id: bigserial NOT NULL`, `farm_id: bigint NOT NULL`, `external_field_id: text NOT NULL`, `field_name: text NOT NULL`, `is_unverified_demo_parcel: boolean NOT NULL DEFAULT false`, `geom_point: geometry(Point, 4326) NOT NULL`, `geom_polygon: geometry(Polygon, 4326) NULL`, `area_hectares: numeric(10,4) NOT NULL`, `soil_type: text NOT NULL`, `soil_source: text NOT NULL DEFAULT 'unknown'`, `soil_ph: numeric(4,2) NULL`, `organic_matter_percent: numeric(5,2) NULL`, `soil_test_date: date NULL`, `water_availability: text NOT NULL`, `water_source: text NOT NULL`, `water_source_other: text NULL`, `irrigation_system: text NOT NULL`, `elevation_m: numeric(7,2) NULL`, `created_at: timestamptz NOT NULL DEFAULT now()`, `updated_at: timestamptz NOT NULL DEFAULT now()` | `PK (id)`, `UNIQUE (farm_id, external_field_id)` | `char_length(external_field_id) BETWEEN 1 AND 64`, `char_length(field_name) BETWEEN 1 AND 120`, `area_hectares > 0 AND area_hectares <= 10000`, `soil_type IN ('sandy','clay','loamy','silty','unknown')`, `soil_source IN ('farmer','unknown')`, `soil_ph IS NULL OR (soil_ph BETWEEN 3.0 AND 11.0)`, `organic_matter_percent IS NULL OR (organic_matter_percent BETWEEN 0 AND 100)`, `water_availability IN ('abundant','moderate','limited','very_limited','rainfed_only')`, `water_source IN ('rainwater','groundwater','well','dam_reservoir','irrigation_network','other','unknown')`, `water_source_other IS NULL OR char_length(water_source_other) <= 200`, `irrigation_system IN ('rainfed','drip','sprinkler','flood','other','unknown')`, `elevation_m IS NULL OR (elevation_m BETWEEN -500 AND 9000)` | `farm_id -> public.farms(id) ON DELETE CASCADE` | `idx_fields_geom_point USING GIST (geom_point)`, `idx_fields_geom_polygon USING GIST (geom_polygon)` |
| **7** | `public.field_crop_history` | `id: bigserial NOT NULL`, `field_id: bigint NOT NULL`, `season: text NOT NULL`, `year: integer NOT NULL`, `planting_month: smallint NULL`, `catalog_version: text NULL`, `crop_id: text NULL`, `crop_name_raw: text NULL`, `yield_tons_per_hectare: numeric(8,3) NULL`, `notes: text NULL` | `PK (id)`, `UNIQUE (field_id, year, season)` | `season IN ('spring','summer','autumn','winter')`, `year BETWEEN 1980 AND 2100`, `planting_month IS NULL OR (planting_month BETWEEN 1 AND 12)`, `crop_id IS NULL OR char_length(crop_id) BETWEEN 1 AND 64`, `crop_name_raw IS NULL OR char_length(crop_name_raw) BETWEEN 1 AND 120`, `yield_tons_per_hectare IS NULL OR yield_tons_per_hectare >= 0`, `notes IS NULL OR char_length(notes) <= 500`, `chk_history_crop_identifier: crop_id IS NOT NULL OR crop_name_raw IS NOT NULL` | `field_id -> public.fields(id) ON DELETE CASCADE` *(deliberately NO FK to `crop_catalog`)* | PK + `UNIQUE (field_id, year, season)` |
| **8** | `public.crop_catalog` | `catalog_version: text NOT NULL`, `crop_id: text NOT NULL`, `names: jsonb NOT NULL`, `category: text NOT NULL`, `roles: text[] NOT NULL`, `family: text NOT NULL`, `synced_at: timestamptz NOT NULL DEFAULT now()` | `PK (catalog_version, crop_id)` | `category IN ('cereals','legumes','oilseeds','vegetables','forage','cover_crops','fallow')` | None | PK `(catalog_version, crop_id)` |
| **9** | `public.dataset_registry` | `dataset_version: text NOT NULL`, `source_description: text NOT NULL`, `coverage_notes: text NOT NULL`, `is_active: boolean NOT NULL DEFAULT false`, `loaded_at: timestamptz NOT NULL DEFAULT now()`, `notes: text NULL` | `PK (dataset_version)`, `uq_dataset_registry_single_active UNIQUE (is_active) WHERE is_active = true` | `char_length(dataset_version) BETWEEN 1 AND 64` | None | `uq_dataset_registry_single_active UNIQUE (is_active) WHERE is_active = true` |
| **10** | `public.analysis_requests` | `request_id: text NOT NULL`, `farm_id: bigint NOT NULL`, `idempotency_key: text NULL`, `parent_request_id: text NULL`, `schema_version: text NOT NULL`, `catalog_version: text NOT NULL`, `dataset_version: text NOT NULL`, `language: text NOT NULL`, `quota_units: smallint NOT NULL DEFAULT 4`, `input_hash: text NOT NULL`, `full_input_hash: text NOT NULL`, `input_snapshot_gz: bytea NULL`, `warnings: jsonb NOT NULL DEFAULT '[]'::jsonb`, `status: text NOT NULL`, `error_code: text NULL`, `lease_until: timestamptz NULL`, `heartbeat_at: timestamptz NULL`, `attempts: smallint NOT NULL DEFAULT 0`, `cancelled_at: timestamptz NULL`, `sent_at: timestamptz NULL`, `received_at: timestamptz NULL`, `duration_ms: integer NULL`, `created_at: timestamptz NOT NULL DEFAULT now()` | `PK (request_id)`, `uq_analysis_idempotency UNIQUE (farm_id, idempotency_key) WHERE idempotency_key IS NOT NULL` | `language IN ('en','fr','ar')`, `quota_units IN (0,1,4)`, `char_length(input_hash) = 64`, `char_length(full_input_hash) = 64`, `status IN ('pending','running','ok','partial','failed','cancelled')`, `attempts >= 0`, `duration_ms IS NULL OR duration_ms >= 0` | `farm_id -> public.farms(id) ON DELETE CASCADE`, `parent_request_id -> public.analysis_requests(request_id) ON DELETE SET NULL`, `dataset_version -> public.dataset_registry(dataset_version) ON DELETE RESTRICT` | `uq_analysis_idempotency`, `idx_analysis_queue (status, lease_until, created_at)` |
| **11** | `public.analysis_results` | `id: bigserial NOT NULL`, `analysis_id: text NOT NULL DEFAULT ('analysis_' \|\| substr(replace(gen_random_uuid()::text, '-', ''), 1, 12))`, `request_id: text NOT NULL`, `status: text NOT NULL`, `dataset_version_used: text NOT NULL`, `ml_engine_version: text NOT NULL`, `result_json: jsonb NOT NULL`, `validation_passed: boolean NOT NULL`, `validation_errors: jsonb NULL`, `created_at: timestamptz NOT NULL DEFAULT now()` | `PK (id)`, `UNIQUE (analysis_id)`, `UNIQUE (request_id)` | `analysis_id ~ '^analysis_[0-9a-f]{12}$'`, `status IN ('ok','partial','invalid')` | `request_id -> public.analysis_requests(request_id) ON DELETE CASCADE` | PK + Unique indexes on `analysis_id`, `request_id` |
| **12** | `public.analysis_selections` | `analysis_id: text NOT NULL`, `field_id: text NOT NULL`, `strategy_id: text NOT NULL`, `selection_status: text NOT NULL`, `updated_at: timestamptz NOT NULL DEFAULT now()` | `PK (analysis_id, field_id, strategy_id)`, `idx_one_selected_strategy_per_field UNIQUE (analysis_id, field_id) WHERE selection_status = 'selected'` | `selection_status IN ('selected','rejected')` | `analysis_id -> public.analysis_results(analysis_id) ON DELETE CASCADE` | `idx_one_selected_strategy_per_field` |
| **13** | `public.ml_breaker_state` | `id: smallint NOT NULL DEFAULT 1`, `state: text NOT NULL DEFAULT 'closed'`, `consecutive_failures: integer NOT NULL DEFAULT 0`, `opened_at: timestamptz NULL`, `half_open_probe_at: timestamptz NULL`, `updated_at: timestamptz NOT NULL DEFAULT now()` | `PK (id)` | `id = 1`, `state IN ('closed','open','half_open')`, `consecutive_failures >= 0` | None | Singleton row `id = 1` |

### B. `Schema: dataset` & Read-Only Role `ml_reader` (`ENDPOINTS A.5`, `ADR-9`)
- Isolated PostgreSQL schema: `CREATE SCHEMA IF NOT EXISTS dataset;`
- Exact tables/columns inside `dataset` are **`TBD` by the ML Team (`OQ-D1`)**.
- Role `ml_reader` created with password from `ML_READER_PASSWORD`, `CONNECTION LIMIT` (`ML_DB_CONNECTION_LIMIT=10` — `OQ-D4`), and `ALTER ROLE ml_reader SET statement_timeout = '<ML_DB_STATEMENT_TIMEOUT_MS>ms'` (`5000ms` — `OQ-D4`).
- Privileges: `REVOKE ALL ON SCHEMA public FROM ml_reader; REVOKE ALL ON ALL TABLES IN SCHEMA public FROM ml_reader; GRANT USAGE ON SCHEMA dataset TO ml_reader; GRANT SELECT ON ALL TABLES IN SCHEMA dataset TO ml_reader; ALTER DEFAULT PRIVILEGES IN SCHEMA dataset GRANT SELECT ON TABLES TO ml_reader; REVOKE CREATE ON SCHEMA dataset FROM ml_reader;`.

---

## 3.4 Route Inventory (`ENDPOINTS B.2–B.10`, `openapi.yaml`)

### A. All 34 Backend Routes (`/api/v1` prefix, `24` path templates)

| # | Method | Path | `operationId` (`openapi.yaml`) | Auth Type | Request / Query Schema | Success Status & Response Schema | Documented Error Codes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **1** | `POST` | `/auth/guest` | `startGuestSession` | Public | `{ demo_location_id: int >= 1 }` | `201` — `GuestSessionStartResponse` | `400 INVALID_INPUT`, `404 NOT_FOUND`, `429 RATE_LIMIT_EXCEEDED` |
| **2** | `POST` | `/auth/register` | `registerUser` | Public | `{ email, password (8..128), full_name (1..120), preferred_lang? }` | `201` — `RegisterResponse` | `400 INVALID_INPUT`, `409 CONFLICT` |
| **3** | `POST` | `/auth/login` | `loginUser` | Public | `{ email, password }` | `200` — `TokenPairResponse` | `400 INVALID_INPUT`, `401 UNAUTHORIZED` |
| **4** | `POST` | `/auth/refresh` | `refreshToken` | Public (refresh token) | `{ refresh_token }` | `200` — `TokenPairResponse` | `400 INVALID_INPUT`, `401 UNAUTHORIZED` |
| **5** | `POST` | `/auth/logout` | `logoutUser` | `BearerAuth` | Optional `{ refresh_token? }` | `204` — Empty | `401 UNAUTHORIZED` |
| **6** | `GET` | `/auth/me` | `getMe` | `BearerAuth` | None | `200` — `UserProfile` | `401 UNAUTHORIZED` |
| **7** | `DELETE` | `/auth/me` | `deleteMe` | `BearerAuth` | None | `204` — Empty | `401 UNAUTHORIZED` |
| **8** | `GET` | `/auth/me/export` | `exportMeData` | `BearerAuth` | None | `200` — `UserDataExport` | `401 UNAUTHORIZED` |
| **9** | `POST` | `/auth/claim-guest` | `claimGuestSession` | `BearerAuth` + `GuestTokenAuth` | Both auth headers | `200` — `{ claimed_farms_count }` | `401 UNAUTHORIZED` |
| **10** | `GET` | `/demo/locations` | `listDemoLocations` | Public | Query: `limit? (1..100, default 20)`, `cursor?` | `200` — `DemoLocationPage` | `400 INVALID_INPUT` |
| **11** | `GET` | `/demo/locations/{id}/boundary` | `getDemoLocationBoundary` | Public | Path: `id: int >= 1` | `200` — `BoundaryFeature` | `404 NOT_FOUND` |
| **12** | `GET` | `/demo/session` | `getDemoSession` | `GuestTokenAuth` | Header `X-Guest-Token` | `200` — `GuestSessionInfo` | `401 UNAUTHORIZED` |
| **13** | `DELETE` | `/demo/session` | `deleteDemoSession` | `GuestTokenAuth` | Header `X-Guest-Token` | `204` — Empty | `401 UNAUTHORIZED` |
| **14** | `GET` | `/farms` | `listFarms` | `BearerAuth` or `GuestTokenAuth` | Query: `limit?`, `cursor?`, `country?`, `region?`, `search?` | `200` — `FarmPage` | `400 INVALID_INPUT`, `401 UNAUTHORIZED` |
| **15** | `POST` | `/farms` | `createFarm` | `BearerAuth` or `GuestTokenAuth` | `FarmWriteRequest` (`farm_name`, `country`, `region`, `commune?`) | `201` — `FarmPublic` | `400 INVALID_INPUT`, `401 UNAUTHORIZED`, `403 GUEST_LIMIT_REACHED`, `429 RATE_LIMIT_EXCEEDED` |
| **16** | `GET` | `/farms/{farm_id}` | `getFarm` | `BearerAuth` or `GuestTokenAuth` | Path: `farm_id` (`^farm_[0-9]+$`) | `200` — `FarmPublic` | `401 UNAUTHORIZED`, `404 NOT_FOUND` |
| **17** | `PUT` | `/farms/{farm_id}` | `replaceFarm` | `BearerAuth` or `GuestTokenAuth` | Path: `farm_id`; Body: `FarmWriteRequest` | `200` — `FarmPublic` | `400 INVALID_INPUT`, `401 UNAUTHORIZED`, `404 NOT_FOUND` |
| **18** | `PATCH` | `/farms/{farm_id}` | `patchFarm` | `BearerAuth` or `GuestTokenAuth` | Path: `farm_id`; Body: `FarmPatchRequest` | `200` — `FarmPublic` | `400 INVALID_INPUT`, `401 UNAUTHORIZED`, `404 NOT_FOUND` |
| **19** | `DELETE` | `/farms/{farm_id}` | `deleteFarm` | `BearerAuth` or `GuestTokenAuth` | Path: `farm_id` | `204` — Empty | `401 UNAUTHORIZED`, `404 NOT_FOUND` |
| **20** | `GET` | `/farms/{farm_id}/fields` | `listFields` | `BearerAuth` or `GuestTokenAuth` | Path: `farm_id`; Query: `limit?`, `cursor?`, `soil_type?`, `water_availability?` | `200` — `FieldPage` | `401 UNAUTHORIZED`, `404 NOT_FOUND` |
| **21** | `POST` | `/farms/{farm_id}/fields` | `createField` | `BearerAuth` or `GuestTokenAuth` | Path: `farm_id`; Body: `FieldWriteRequest` | `201` — `FieldPublic` | `400 INVALID_INPUT`, `401 UNAUTHORIZED`, `403 GUEST_LIMIT_REACHED`, `404 NOT_FOUND`, `409 CONFLICT`, `422 OUTSIDE_DEMO_BOUNDARY` |
| **22** | `GET` | `/farms/{farm_id}/fields/{field_id}` | `getField` | `BearerAuth` or `GuestTokenAuth` | Path: `farm_id`, `field_id` | `200` — `FieldDetailPublic` | `401 UNAUTHORIZED`, `404 NOT_FOUND` |
| **23** | `PUT` | `/farms/{farm_id}/fields/{field_id}` | `replaceField` | `BearerAuth` or `GuestTokenAuth` | Path: `farm_id`, `field_id`; Body: `FieldWriteRequest` | `200` — `FieldDetailPublic` | `400 INVALID_INPUT`, `401 UNAUTHORIZED`, `404 NOT_FOUND`, `409 CONFLICT`, `422 OUTSIDE_DEMO_BOUNDARY` |
| **24** | `PATCH` | `/farms/{farm_id}/fields/{field_id}` | `patchField` | `BearerAuth` or `GuestTokenAuth` | Path: `farm_id`, `field_id`; Body: `FieldPatchRequest` | `200` — `FieldDetailPublic` | `400 INVALID_INPUT`, `401 UNAUTHORIZED`, `404 NOT_FOUND`, `409 CONFLICT`, `422 OUTSIDE_DEMO_BOUNDARY` |
| **25** | `DELETE` | `/farms/{farm_id}/fields/{field_id}` | `deleteField` | `BearerAuth` or `GuestTokenAuth` | Path: `farm_id`, `field_id` | `204` — Empty | `401 UNAUTHORIZED`, `404 NOT_FOUND` |
| **26** | `POST` | `/analysis` | `submitAnalysis` | `BearerAuth` or `GuestTokenAuth` | Query: `wait?`; Header: `Idempotency-Key?`; Body: `AnalysisSubmitRequest` | `202` — `AnalysisQueuedResponse` (or `200` `AnalysisEnvelope` if `wait=true` & `ALLOW_SYNC_WAIT=true`) | `400 INVALID_INPUT`, `401 UNAUTHORIZED`, `403 GUEST_LIMIT_REACHED`, `404 NOT_FOUND`, `409 CONFLICT`/`CATALOG_VERSION_MISMATCH`, `422 OUTSIDE_DEMO_BOUNDARY`/`INSUFFICIENT_DATA`, `429 RATE_LIMIT_EXCEEDED`, `500 INTERNAL_ERROR` (`?wait=true` + exhausted `413`), `502` ML errors, `503 SERVICE_UNAVAILABLE`/`DATASET_UNAVAILABLE`, `504 ML_TIMEOUT`/`JOB_TIMEOUT` |
| **27** | `GET` | `/analysis/requests/{request_id}` | `pollAnalysisRequest` | `BearerAuth` or `GuestTokenAuth` | Path: `request_id: uuid` | `200` — `AnalysisPollEnvelope` (+ `Retry-After: 2` while `pending`/`running`; read-time `degraded_mode` reconstruction) | `401 UNAUTHORIZED`, `404 NOT_FOUND`, `429 RATE_LIMIT_EXCEEDED` (`120 req/min` poll bucket per `openapi.yaml`), `503 SERVICE_UNAVAILABLE` |
| **28** | `POST` | `/analysis/requests/{request_id}/cancel` | `cancelAnalysisRequest` | `BearerAuth` or `GuestTokenAuth` | Path: `request_id: uuid` | `200` — `{ request_id, status: "cancelled" }` (`pending` cancels + refunds immediately `IMPL-020`) | `401 UNAUTHORIZED`, `404 NOT_FOUND`, `409 CONFLICT`, `429 RATE_LIMIT_EXCEEDED`, `503 SERVICE_UNAVAILABLE` |
| **29** | `GET` | `/analysis/{analysis_id}` | `getAnalysisResult` | `BearerAuth` or `GuestTokenAuth` | Path: `analysis_id` (`^analysis_[0-9a-f]{12}$`) | `200` — `AnalysisEnvelope` (with read-time `degraded_mode` reconstruction `IMPL-017`) | `401 UNAUTHORIZED`, `404 NOT_FOUND`, `429 RATE_LIMIT_EXCEEDED`, `503 SERVICE_UNAVAILABLE` |
| **30** | `PATCH` | `/analysis/{analysis_id}/selection` | `updateAnalysisSelection` | `BearerAuth` or `GuestTokenAuth` | Path: `analysis_id`; Body: `{ field_id, strategy_id, selection_status: 'selected' \| 'rejected' }` | `200` — `{ analysis_id, field_id, strategy_id, selection_status }` (locks parent `analysis_results FOR UPDATE` + atomic prior-`'selected'` clear `IMPL-020`) | `400 INVALID_INPUT`, `401 UNAUTHORIZED`, `404 NOT_FOUND`, `429 RATE_LIMIT_EXCEEDED`, `503 SERVICE_UNAVAILABLE` |
| **31** | `GET` | `/farms/{farm_id}/analyses` | `listFarmAnalyses` | `BearerAuth` or `GuestTokenAuth` | Path: `farm_id`; Query: `limit?`, `cursor?`, `status?` | `200` — `FarmAnalysesPage` | `401 UNAUTHORIZED`, `404 NOT_FOUND`, `429 RATE_LIMIT_EXCEEDED`, `503 SERVICE_UNAVAILABLE` |
| **32** | `GET` | `/catalog` | `getCatalog` | `BearerAuth` or `GuestTokenAuth` | Query: `limit?`, `cursor?`, `category?`, `role?`, `lang?`, `version?` | `200` — `CatalogPage` | `401 UNAUTHORIZED`, `404 NOT_FOUND`, `429 RATE_LIMIT_EXCEEDED`, `502 ML_UNAVAILABLE` (on empty-catalog bootstrap failure `IMPL-009`), `503 SERVICE_UNAVAILABLE` |
| **33** | `GET` | `/health` | `getHealth` | Public | Query: `check? ('live' \| 'ready' \| 'dependencies', default 'dependencies')` | `200` — `HealthResponse` (`ok` or `degraded`) | `503 SERVICE_UNAVAILABLE` / `DATASET_UNAVAILABLE` |
| **34** | `GET` | `/metrics` | `getMetrics` | Internal ACL (`x-internal-only: true`) | None | `200` — `text/plain` Prometheus metrics | Blocked externally by reverse proxy ACL |

### B. All 3 External ML Service Sub-Contract Routes (`ENDPOINTS B.10`, `ADR-4`)

| # | Method | Path (`{ML_SERVICE_URL}`) | Headers | Timeout & Sync Interval | Wire Contract (`schema-v5.0.json`) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **ML-1** | `POST` | `/v1/analyze` | `X-ML-API-Key`, `Idempotency-Key: <request_id>`, optional `Content-Encoding: gzip` | `ML_TIMEOUT_SECONDS=60` | Req: `#/$defs/FarmAnalysisInput` / Res: `#/$defs/AnalysisResult` (`dataset_version_used`, NO `analysis_id`) |
| **ML-2** | `GET` | `/v1/catalog` | `X-ML-API-Key` | `ML_CATALOG_TIMEOUT_SECONDS=5`; synced every `ML_CATALOG_SYNC_HOURS=6` | Res: `#/$defs/CropCatalog` |
| **ML-3** | `GET` | `/v1/health` | `X-ML-API-Key` | `ML_HEALTH_TIMEOUT_SECONDS=3` | `{ status, ml_engine_version, dataset_versions_supported, ... }` |

### C. Complete ML Error -> Backend Error Mapping Table (`ENDPOINTS B.10.4`)

| ML HTTP & Code | Retry Policy | Circuit Breaker (`ml_breaker_state`) | Backend Mapped `error_code` (`status='failed'`) & Degraded Replay |
| :--- | :--- | :---: | :--- |
| `400 INVALID_INPUT` | 0 retries; critical ops alert | No | `ML_CONTRACT_ERROR` (`502`) |
| `401` / `403 AUTH_FAILED` | Retry `1`x with `ML_SERVICE_PREVIOUS_API_KEY` if set during rotation; else critical alert | No | `ML_UNAVAILABLE` (`502`) |
| `409 CATALOG_VERSION_MISMATCH` | Acquire `pg_try_advisory_lock(hashtext('catalog_sync'))`, sync `/v1/catalog`, retry `1`x if crops remain valid | No | `CATALOG_VERSION_MISMATCH` (`409`) |
| `409` / `422 DATASET_VERSION_UNAVAILABLE` | 0 retries; alert data/ops | No | `DATASET_VERSION_UNAVAILABLE` (`502`) |
| `413 PAYLOAD_TOO_LARGE` | Trim older `crop_history` annotations beyond recent window & retry `1`x inside lease; else fail | No | `INTERNAL_ERROR` (`500`) |
| `422 INSUFFICIENT_DATA` | 0 retries | No | `INSUFFICIENT_DATA` (`422`) *(no guest quota refund — domain gap)* |
| `429 RATE_LIMITED` | Respect `Retry-After <= 5s` inside remaining lease (`1` retry); else fail | No | `ML_UNAVAILABLE` (`502`) |
| `500 INTERNAL_ERROR` (non-dataset) / `503 OVERLOADED` | Retry `ML_MAX_RETRIES=1` (2s + jitter or `Retry-After <= 5s`) with same `Idempotency-Key` | **Yes (`+1`)** | `ML_UNAVAILABLE` (`502`) or `last_good_replay` if eligible |
| `500` / `502 ML_DATASET_ERROR` | 0 retries; DB dataset query failure on `Schema: dataset` | **Yes (`+1`)** | `ML_DATASET_ERROR` (`502`) |
| Network timeout (`> ML_TIMEOUT_SECONDS=60`) | Retry `ML_MAX_RETRIES=1` with same `Idempotency-Key` | **Yes (`+1`)** | `ML_TIMEOUT` (`504`) or `last_good_replay` if eligible |
| `200 OK` failing Stage 1 (`schema-v5.0.json`) or Stage 2 (`SEM-01..06`) | Write raw JSON to `analysis_results(status='invalid', validation_passed=false)` with Backend `analysis_<12hex>`; 0 retries | No | `ML_INVALID_RESPONSE` (`502`) |
| `200 OK` failing `SEM-07` (`dataset_version_used != dataset_version`) | Write raw JSON to `analysis_results(status='invalid', validation_passed=false)`; alert ops; 0 retries | No | `DATASET_VERSION_UNAVAILABLE` (`502`) |

---

## 3.5 Error Model, Warning Notices & Enums (`ENDPOINTS B.1`, `openapi.yaml`)

### A. All 19 Canonical Error Codes (`openapi.yaml#/components/schemas/ErrorCode`)

| # | Code | HTTP | Meaning |
| :--- | :--- | :---: | :--- |
| **1** | `INVALID_INPUT` | `400` | Schema/syntax failure (including FastAPI request validation handler) or `INPUT-01..03` failure |
| **2** | `UNAUTHORIZED` | `401` | Missing, invalid, expired, revoked, or reused token/session |
| **3** | `GUEST_LIMIT_REACHED` | `403` | Guest exceeded `GUEST_MAX_FARMS` (`3`), `GUEST_MAX_FIELDS_PER_FARM` (`5`), or `GUEST_MAX_ANALYSES` (`10` = `40` quarters) |
| **4** | `NOT_FOUND` | `404` | Resource missing or owned by another user/guest (anti-enumeration rule) |
| **5** | `CONFLICT` | `409` | Duplicate email, duplicate `(farm_id, field_id)`, duplicate `(field_id, year, season)`, non-cancellable terminal job, or idempotency payload mismatch |
| **6** | `CATALOG_VERSION_MISMATCH` | `409` | Requested crop/version missing after ML catalog sync |
| **7** | `OUTSIDE_DEMO_BOUNDARY` | `422` | Guest field coordinate falls outside Guelma PostGIS `boundary` |
| **8** | `INSUFFICIENT_DATA` | `422` | External ML cannot generate plans from submitted history/dataset coverage |
| **9** | `RATE_LIMIT_EXCEEDED` | `429` | Per-minute CRUD or per-hour analysis/IP Redis rate limit exceeded (`Retry-After` header set) |
| **10** | `INTERNAL_ERROR` | `500` | Unhandled backend failure or exhausted `413` retry |
| **11** | `ML_UNAVAILABLE` | `502` | Circuit breaker open, bulkhead saturated, ML `500`/`503`/`429`, or auth mismatch |
| **12** | `ML_INVALID_RESPONSE` | `502` | External ML output failed Stage 1 schema or Stage 2 `SEM-01..06` checks |
| **13** | `ML_CONTRACT_ERROR` | `502` | External ML returned `400 INVALID_INPUT` rejecting Backend's schema-valid request |
| **14** | `DATASET_VERSION_UNAVAILABLE` | `502` | External ML rejected `dataset_version` or returned `dataset_version_used != dataset_version` (`SEM-07`) |
| **15** | `ML_DATASET_ERROR` | `502` | External ML failed querying `Schema: dataset` via `ml_reader` |
| **16** | `SERVICE_UNAVAILABLE` | `503` | PostgreSQL/PostGIS unreachable (`GET /health`) or readiness failure |
| **17** | `DATASET_UNAVAILABLE` | `503` | No row with `is_active = true` in `public.dataset_registry` |
| **18** | `ML_TIMEOUT` | `504` | External ML exceeded `ML_TIMEOUT_SECONDS=60` |
| **19** | `JOB_TIMEOUT` | `504` | Sync test wait (`?wait=true`) exceeded `SYNC_WAIT_TIMEOUT_SECONDS=58` (job continues asynchronously) |

### B. Error Envelope, 2 Non-Blocking Notices & Enums
- **Error Envelope:** `{ "error": { "code": ErrorCode, "message": str, "details": [...], "request_id": str | null } }` (`openapi.yaml#/components/schemas/ErrorEnvelope`).
- **2 Warning Notices:**
  1. `DEMO_PARCEL_UNVERIFIED`: Optional `is_unverified_demo_parcel: true` flag submitted on a field when demo parcel measurements have not yet been studied (`OQ-D8`).
  2. `MVP_OUTSIDE_COVERAGE`: Registered user saves/updates a field outside Wilaya of Guelma `boundary` (allowed `201`/`200` with notice).
- **Canonical Enums (`schema-v5.0.json`, `ENDPOINTS B.1.4`):**
  - `Language`: `'en' | 'fr' | 'ar'`
  - `Season`: `'spring' | 'summer' | 'autumn' | 'winter'`
  - `CycleMode`: `'annual_rotation' | 'consecutive_seasons'`
  - `SoilType`: `'sandy' | 'clay' | 'loamy' | 'silty' | 'unknown'`
  - `SoilSource`: `'farmer' | 'unknown'`
  - `MarketPreference`: `'local_market' | 'export' | 'subsistence' | 'mixed'`
  - `WaterAvailability`: `'abundant' | 'moderate' | 'limited' | 'very_limited' | 'rainfed_only'`
  - `WaterSource`: `'rainwater' | 'groundwater' | 'well' | 'dam_reservoir' | 'irrigation_network' | 'other' | 'unknown'`
  - `IrrigationSystem`: `'rainfed' | 'drip' | 'sprinkler' | 'flood' | 'other' | 'unknown'`
  - `CropCategory`: `'cereals' | 'legumes' | 'oilseeds' | 'vegetables' | 'forage' | 'cover_crops' | 'fallow'`
  - `CropRole`: `'cash_crop' | 'nitrogen_fixer' | 'forage' | 'cover_crop' | 'break_crop' | 'main_crop' | 'fallow'`
  - `SelectionStatus`: `'suggested' | 'selected' | 'rejected'`
  - `SeverityLevel`: `'low' | 'medium' | 'high'`
  - `DataSource`: `'farmer_input' | 'dataset'`

---

## 3.6 Deterministic Workflows (`Blueprint §4–§5`, `ENDPOINTS A.3, B.3–B.10`)

1. **`W1` — Analysis Request End-to-End (`POST /api/v1/analysis` -> Worker -> Poll):**
   - **Exact Synchronous Admission Check Order (`Blueprint §4 W1`, `IMPL-001`, `IMPL-002`, `IMPL-020`):**
     1. **Auth & Ownership (`401` / `404`):** Validate `Bearer` JWT or `X-Guest-Token`; verify caller owns `farm_id` and every requested `field_id` (`404 NOT_FOUND` if missing/foreign).
     2. **Idempotency (`409` / `202`), Redis Sliding-Window Rate Limits (`429`), & Guest Quarter Quotas (`403`):** Check `Idempotency-Key` (`24h` per farm; `202` replay if `full_input_hash` matches, `409 CONFLICT` if different; concurrent `UniqueViolation` handled cleanly via savepoint `IMPL-002`); compute what-if quarter cost (`quota_units = 1` if matching recent `input_hash` within `24h` on `farm_id`, else `4`); enforce Redis atomic **interpolated integer two-bucket sliding-window** counters (`RATE_LIMIT_ANALYSIS_PER_HOUR`, `ANALYSIS_PER_IP_HOUR` -> `429` + `Retry-After`, returning the incremented `bucket_key`; fail-closed `503` if Redis down `IMPL-001`), then wrap **both** the locked PG `guest_sessions FOR UPDATE` quota check (`GUEST_MAX_ANALYSES = 10` = `40` quarters -> `403 GUEST_LIMIT_REACHED`, hydrating Redis on miss) and Steps 3–5 inside `try ... except:` so `403`, `400`, `422`, `409`, and `503` errors roll back Redis rate-limit increments (`DECRBY` on returned `bucket_key`) and never burn hourly or guest quotas. Redis guest quarter updates occur **only after** Steps 3–4 pass and DB `INSERT` succeeds (rollback/refund uses Lua `EXISTS`-guarded clamped `DECRBY >= 0` or `DEL`).
     3. **PostGIS Boundary & `INPUT-01..03` (`422` / `400`):** For guests, verify `ST_Covers(demo_locations.boundary, geom_point)` (`422 OUTSIDE_DEMO_BOUNDARY`); run `INPUT-01..03` (`400 INVALID_INPUT`). Aggregate parcel `WarningNotice.fields[]` across requested fields (`IMPL-019`).
     4. **Catalog & Active Dataset Ready (`409` / `503`):** Verify `crop_id`s exist in active `public.crop_catalog` (sync once on miss under `pg_try_advisory_lock(hashtext('catalog_sync'))` before `409 CATALOG_VERSION_MISMATCH`); fetch unique `dataset_registry WHERE is_active = true` (`503 DATASET_UNAVAILABLE` if missing).
     5. **Snapshot & Enqueue (`202 Accepted`):** Assemble strict allowlisted `FarmAnalysisInput` JSON (`schema-v5.0.json#/$defs/FarmAnalysisInput`), gzip into `input_snapshot_gz` (`IMPL-013`; note `Blueprint`/`Visual I/O` Mermaid text describing worker-side assembly is superseded per `DI-05`), insert `analysis_requests(status='pending')`, commit, update Redis guest quarter mirror, return `202` with `{request_id, status: "pending", poll_url, poll_interval_ms: 2000, warnings}` + `Location` header (or poll until `SYNC_WAIT_TIMEOUT_SECONDS=58` if `?wait=true` and `ALLOW_SYNC_WAIT=true`, translating terminal errors per `PollErrorObject.http_equivalent` `IMPL-020`).
2. **`W2` — Worker Execution, Bulkhead, Breaker & Cooperative Cancel (`Blueprint §4 W2`, `ADR-6`, `ADR-8`, `IMPL-006`, `IMPL-017`):**
   - Worker claims oldest eligible `pending` row (or expired lease with `attempts < MAX_JOB_ATTEMPTS=2`) atomically via `FOR UPDATE SKIP LOCKED`, setting `status='running'`, `lease_until = now() + 90s`, `heartbeat_at = now()`, `attempts = attempts + 1`.
   - Heartbeat task renews `lease_until` and polls `cancelled_at IS NOT NULL` / farm deletion every `2s`.
   - Before dispatch / setting `sent_at = now()`, lock row `FOR UPDATE` and verify `cancelled_at IS NULL AND status = 'running'` (pre-dispatch cancel transitions cleanly to `cancelled`, `quota_units = 0` without calling ML or consuming `GUEST_MAX_ML_REFUNDS`).
   - If `ml_breaker_state` is `'open'` within `30s` cooldown: check `last_good_replay` (`full_input_hash` match, `req_src.received_at IS NOT NULL`, `validation_passed = true` within `DEGRADED_MODE_MAX_AGE_HOURS=72`, copying validated `result_json` to fresh `analysis_results` row + `req.received_at=NULL, req.error_code='last_good_replay:' || source_analysis_id` `IMPL-017`), else fail `ML_UNAVAILABLE` (`502`). On `'half_open'` single-flight probe: failed `5xx`/timeout/`ML_DATASET_ERROR` resets immediately to `'open'` with fresh cooldown; valid ML `4xx` transitions **`half_open -> closed`** (`consecutive_failures=0, half_open_probe_at=NULL` `IMPL-017`).
   - Acquire session advisory lock `pg_try_advisory_lock(1001..1008)` on a dedicated pinned DB session; decompress `input_snapshot_gz` (`sent_at = now()`); run `MLProviderManager.analyze()` (including retry backoff sleeps) inside cancellable `asyncio.Task`. Always call `pg_advisory_unlock(slot)` in `finally:`.
   - Before writing `analysis_results`, re-verify in transaction that `analysis_requests` still exists with **both `status = 'running' AND cancelled_at IS NULL`** (cascade & late-cancel guard; if `cancelled_at IS NOT NULL`, transition to `status = 'cancelled'` without inserting `analysis_results`).
3. **`W3` — `FarmAnalysisInput` Data Minimization (`Blueprint §4 W3, §12.1`):**
   - Strictly allowlists `schema_version`, `dataset_version`, `request_id`, `catalog_version`, `language`, `farm.{farm_id, farm_name, country, region, commune}`, `planning`, `priorities`, `fields[].{field_id, field_name, is_unverified_demo_parcel, location, area_hectares, elevation_m, soil, water, crop_history[]}`.
   - Strictly strips `email`, `full_name`, `user_id`, `guest_token`, IP, `field_crop_history.notes`, backend `warnings[]`.
4. **`W4` — Validation Pipeline & What-If Scenario Replay (`Blueprint §4 W4, §4.5`, `Visual I/O §8, §10`, `IMPL-017`):**
   - Stage 1 validates `#/$defs/AnalysisResult` with `additionalProperties: true` (`5.x` extra fields logged at `WARNING` + `ml_unknown_fields_observed_total` metric; `6.0` fails); Stage 2 checks `SEM-01..07`; `last_good_replay` is reconstructed on `GET /analysis/requests/{id}`, `GET /analysis/{analysis_id}`, and `POST /analysis?wait=true` as `degraded_mode: {kind: "last_good_replay", stale: true, source_analysis_id, created_at, dataset_version, age_seconds}`.

---

## 3.7 Validation Rules (`Blueprint §4 W4`, `ENDPOINTS B.10.4`)

- **Pre-Queue (`INPUT-01..03` -> `400 INVALID_INPUT`):**
  - **`INPUT-01`:** `sum(priorities.weights.*) == 100` (`water_saving + soil_improvement + income + risk_reduction + forage_value == 100`, integer `0..100` each).
  - **`INPUT-02`:** `set(priorities.target_crop_ids) & set(priorities.excluded_crop_ids) == set()`.
  - **`INPUT-03`:** When `planning.planting_month` is non-null: Northern (`latitude >= 0`) `winter` -> `{12,1,2}`, `spring` -> `{3,4,5}`, `summer` -> `{6,7,8}`, `autumn` -> `{9,10,11}`; Southern (`latitude < 0`) `winter` -> `{6,7,8}`, `spring` -> `{9,10,11}`, `summer` -> `{12,1,2}`, `autumn` -> `{3,4,5}` (`OQ-10`).
- **Stage 1 (`schema-v5.0.json#/$defs/AnalysisResult`):** `^5\.[0-9]+$`, conditional `status == 'ok'` (every `field_plans[]` has `status='ok'`, `suggested_strategy_id` non-null, `3..5` strategies, **exactly 1** `is_existing_rotation: true`) vs `status == 'partial'` (`partial_reason` required). Tolerant reader (`additionalProperties: true`).
- **Stage 2 (`SEM-01..07`):**
  - **`SEM-01`:** Strategies sorted / non-empty per `ok` field, unique `strategy_id` per field, `is_existing_rotation: true` baseline count == 1 (`status='ok'`).
  - **`SEM-02`:** Exact 1:1 `field_id` alignment between `FarmAnalysisInput.fields` and `AnalysisResult.field_plans`, and `len(strategy.seasons) == planning.horizon_seasons`.
  - **`SEM-03`:** Every `crop_id` in `seasons[]` matches `(catalog_version, crop_id)` in `public.crop_catalog` with matching `category` and subset/valid `role` in `roles`.
  - **`SEM-04`:** Evidence provenance: `data_source` in `{'farmer_input', 'dataset'}`; raw `'farmer_input'` values match `input_snapshot_gz` within `±TBD` (`OQ-3`, default exact/1e-3); computed aggregates set `derived: true`; `'dataset'` items include audit metadata (`OQ-D5`).
  - **`SEM-05`:** When non-null, `suggested_strategy_id` exists in `field_plan.strategies[].strategy_id`.
  - **`SEM-06`:** Every `crop_id` in `priorities.target_crop_ids` appears in `requested_crop_results[]` with non-empty `explanation`.
  - **`SEM-07`:** `AnalysisResult.dataset_version_used == analysis_requests.dataset_version` (mismatch -> `502 DATASET_VERSION_UNAVAILABLE` + raw JSON stored `validation_passed=false`).

---

## 3.8 Security & Privacy Rules (`Blueprint §12.1`, `ENDPOINTS A.3, A.5, B.1–B.3`, `ADR-5, ADR-6`)

1. **Passwords & Tokens:** Argon2id; JWT HS256 (`JWT_SECRET_KEY` primary, `JWT_PREVIOUS_SECRET_KEY` fallback; reject `alg=none` and other algs); access JWT carries `sub`, `fid` (`family_id`), `exp`, `jti`; refresh tokens & guest tokens stored strictly as 64-char SHA-256 hex digests; never logged.
2. **Refresh Rotation Reuse Detection:** Atomic `UPDATE ... WHERE used_at IS NULL AND revoked_at IS NULL RETURNING ...`. On replay (`used_at IS NOT NULL` or `revoked_at IS NOT NULL`), commit `UPDATE public.refresh_tokens SET revoked_at = now() WHERE family_id = :fid` in its own committed transaction **before** raising `401 UNAUTHORIZED`.
3. **Anti-Enumeration & ID Masking (`DI-16`):** Foreign-owned resource -> `404 NOT_FOUND`; `403 FORBIDDEN` reserved exclusively for `GUEST_LIMIT_REACHED`. Internal DB bigints are strictly masked on `/farms`, `/fields`, `/analysis` (`farm_<n>`, `F1`, `analysis_<12hex>`), while `/auth/me` (`UserProfile.id`) and `/demo/locations` (`DemoLocationSummary.id`) return schema-typed integer IDs per `openapi.yaml`.
4. **`ml_reader` & Key Rotation:** `ml_reader` has `SELECT` on `Schema: dataset` only (`REVOKE ALL ON SCHEMA public`); Backend retries `401/403` ML calls once with `ML_SERVICE_PREVIOUS_API_KEY` if set.
5. **Privacy Deletion, Export & Claim-Guest (`IMPL-021`):** `DELETE /auth/me` performs single-transaction cascade wipe across `users`, `refresh_tokens`, `farms`, `fields`, `field_crop_history`, `analysis_requests` (incl. `input_snapshot_gz`), `analysis_results`, `analysis_selections`; `GET /auth/me/export` maps strictly to `UserDataExport` (explicitly excluding `input_snapshot_gz` `bytea`, `password_hash`, and `token_hash`, formatting `FieldDetailPublic`); `POST /auth/claim-guest` locks `guest_sessions FOR UPDATE` and updates `farms` ownership **before** deleting `guest_sessions` (`ON DELETE CASCADE`), then deletes Redis `guest_quota:{token_hash}:quarters`.

---

## 3.9 Configuration — All 40 `.env` Variables (`ENDPOINTS Section C`)

| # | Variable | Default / Example | Purpose | Reader |
| :--- | :--- | :--- | :--- | :--- |
| 1 | `DATABASE_URL` | `postgresql+asyncpg://fieldshift:***@db:5432/fieldshift` | Async PostGIS URI (`public` schema) | `api`, `worker`, `migrate` |
| 2 | `DB_PASSWORD` | `<strong random secret>` | PostgreSQL password for `db` service | `db` |
| 3 | `REDIS_URL` | `redis://redis:6379/0` | Backend-only Redis URL for rate limits & guest quota cache | `api`, `worker` |
| 4 | `ML_DATASET_DB_URL` | `postgresql://ml_reader:***@db:5432/fieldshift` | Read-only URI for External ML querying `Schema: dataset` | `ml-service` |
| 5 | `ML_READER_PASSWORD` | `<strong random secret>` | Password for PostgreSQL role `ml_reader` | `migrate`, `ml-service` |
| 6 | `ML_DB_STATEMENT_TIMEOUT_MS` | `5000` *(TBD — `OQ-D4`)* | `ml_reader` SQL `statement_timeout` | `migrate` |
| 7 | `ML_DB_CONNECTION_LIMIT` | `10` *(TBD — `OQ-D4`)* | `ml_reader` `CONNECTION LIMIT` | `migrate` |
| 8 | `JWT_SECRET_KEY` | `<256-bit random secret>` | Primary HS256 signing key | `api` |
| 9 | `JWT_PREVIOUS_SECRET_KEY` | `""` | Secondary HS256 verification key for zero-downtime rollover | `api` |
| 10 | `JWT_ACCESS_EXPIRES_SECONDS` | `3600` | Access JWT lifetime (1 h) | `api` |
| 11 | `JWT_REFRESH_EXPIRES_SECONDS` | `2592000` | Rotating `refresh_tokens` TTL (30 d) | `api` |
| 12 | `GUEST_SESSION_DAYS` | `7` | Guest session lifetime in days | `api`, `worker` |
| 13 | `GUEST_MAX_FARMS` | `3` | Max farms per guest session (`403`) | `api` |
| 14 | `GUEST_MAX_FIELDS_PER_FARM` | `5` | Max fields per guest farm (`403`) | `api` |
| 15 | `GUEST_MAX_ANALYSES` | `10` | Equivalent max full analyses (`40` quarters, `403`) | `api`, `worker` |
| 16 | `GUEST_MAX_ML_REFUNDS` | `3` | Max refunded ML failures (`502`/`504`) per guest | `worker` |
| 17 | `GUEST_BURST_PER_MIN` | `30` | Guest CRUD requests/min Redis rate limit (`429`) | `api` |
| 18 | `GUEST_CREATE_PER_IP_HOUR` | `5` | `POST /auth/guest` calls/h/IP Redis limit (`429`) | `api` |
| 19 | `RATE_LIMIT_CRUD_PER_MIN` | `60` | Registered user CRUD requests/min Redis limit (`429`) | `api` |
| 20 | `RATE_LIMIT_ANALYSIS_PER_HOUR` | `10` | User hourly analysis Redis limit (`40` quarters/h, `429`) | `api` |
| 21 | `ANALYSIS_PER_IP_HOUR` | `15` | IP hourly analysis Redis limit (`60` quarters/h, `429`) | `api` |
| 22 | `ML_SERVICE_URL` | `https://ml.fieldshift.internal` | Base URL for `RealMLAdapter` (dev/test mock only if `APP_ENV != 'production'` and `ML_PROVIDER_MODE = 'auto'`) | `api`, `worker` |
| 23 | `ML_SERVICE_API_KEY` | `<shared service secret>` | Active `X-ML-API-Key` secret | `api`, `worker` |
| 24 | `ML_SERVICE_PREVIOUS_API_KEY` | `""` | Secondary key tried once on `401`/`403` | `api`, `worker` |
| 25 | `ML_TIMEOUT_SECONDS` | `60` | Hard HTTP read timeout on `POST /v1/analyze` | `worker` |
| 26 | `ML_MAX_RETRIES` | `1` | Max 5xx/timeout retries per job using same `Idempotency-Key` | `worker` |
| 27 | `ML_MAX_PAYLOAD_BYTES` | `524288` *(TBD — `OQ-4`)* | Max uncompressed `FarmAnalysisInput` bytes before trim | `worker` |
| 28 | `ML_CATALOG_TIMEOUT_SECONDS` | `5` | Timeout on `GET /v1/catalog` | `api`, `worker` |
| 29 | `ML_HEALTH_TIMEOUT_SECONDS` | `3` | Timeout on `GET /v1/health` | `api`, `worker` |
| 30 | `ML_CATALOG_SYNC_HOURS` | `6` | Periodic catalog sync interval in hours | `worker` |
| 31 | `ML_CIRCUIT_BREAKER_THRESHOLD` | `5` | Consecutive failures to open `ml_breaker_state` | `worker` |
| 32 | `ML_BREAKER_COOLDOWN_SECONDS` | `30` | Cooldown before half-open probe | `worker` |
| 33 | `ML_MAX_CONCURRENT_REQUESTS` | `8` | Cluster-wide advisory lock bulkhead slots (`1001..1008`) | `worker` |
| 34 | `DEGRADED_MODE_MAX_AGE_HOURS` | `72` *(TBD — `OQ-8`)* | Max age for `last_good_replay` | `api`, `worker` |
| 35 | `ALLOW_SYNC_WAIT` | `false` | Enables test-only `POST /analysis?wait=true` | `api` |
| 36 | `SYNC_WAIT_TIMEOUT_SECONDS` | `58` | Sync wait timeout before `504 JOB_TIMEOUT` | `api` |
| 37 | `WORKER_CONCURRENCY` | `4` | Concurrent `SKIP LOCKED` tasks per worker container | `worker` |
| 38 | `JOB_LEASE_SECONDS` | `90` | Worker lease TTL before stale reclaim | `worker` |
| 39 | `MAX_JOB_ATTEMPTS` | `2` | Max attempts per request after lease expiry | `worker` |
| 40 | `CORS_ALLOWED_ORIGINS` | `http://localhost:5173` | Comma-separated allowed CORS origins | `api` |

### 3.9b Companion Runtime Settings (`7` Non-Spec Safety & Tuning Knobs — `IMPL-018`)

These `7` knobs live explicitly in a separate **Companion Settings** section of `app/core/config.py` and `.env.example` so `verify_contracts.py` preserves strict `40/40` parity on `ENDPOINTS Section C`:

| # | Setting | Safe Default | Purpose | Reader |
| :--- | :--- | :--- | :--- | :--- |
| C1 | `APP_ENV` | `production` | Fail-safe environment mode (`production` \| `development` \| `test`); **forbids** `MockMLAdapter` when `production` (`IMPL-008`) | `api`, `worker` |
| C2 | `ML_PROVIDER_MODE` | `auto` | Explicit ML adapter mode (`auto` \| `real` \| `mock`; setting `mock` when `APP_ENV=production` raises startup `ValueError` in `config.py` `IMPL-008`) | `api`, `worker` |
| C3 | `ML_HEALTH_CHECK_INTERVAL_SECONDS` | `30` | Interval for `worker` `/v1/health` probe publishing `ml:provider_status` to Redis | `worker` |
| C4 | `SEM04_NUMERIC_TOLERANCE` | `0.001` (`1e-3`) | Tolerance for `SEM-04` `'farmer_input'` numerical cross-checks (`# TODO(OQ-3)`) | `worker` |
| C5 | `TRUSTED_PROXY_CIDRS` | `""` | Comma-separated CIDRs permitted to supply `X-Forwarded-For` (`""` = peer IP only, `IMPL-001`) | `api` |
| C6 | `REDIS_FAIL_CLOSED` | `true` | Enforce `503 SERVICE_UNAVAILABLE` on request-path Redis outage (`IMPL-001`) | `api` |
| C7 | `ML_DATASET_OWNER_ROLE` | `""` | Optional external ML loader role for `ALTER DEFAULT PRIVILEGES FOR ROLE` on `Schema: dataset` (`IMPL-005`) | `migrate` |

---

## 3.10 Open Questions Registry (`Blueprint §13` — 11+8 = 19 Items)

| ID | Topic | How Handled in Code (`# TODO(OQ-*)`) |
| :--- | :--- | :--- |
| `OQ-1` | ML `p95`/`p99` & Stage 1/2 budget | `ML_TIMEOUT_SECONDS=60` default; timing instrumented in Prometheus + structlog; KPI latency target marked pending SLA |
| `OQ-2` | Free-text prompt-injection risk on `farm_name` / `crop_name_raw` | Enforces `maxLength` + control-char stripping helper `# TODO(OQ-2)` |
| `OQ-3` | `SEM-04` numeric comparison tolerance | Configurable `SEM04_NUMERIC_TOLERANCE` setting (default `1e-3`, `# TODO(OQ-3)`) |
| `OQ-4` | `ML_MAX_PAYLOAD_BYTES` exact ceiling | Configurable `ML_MAX_PAYLOAD_BYTES=524288` with history annotation trimmer (`# TODO(OQ-4)`) |
| `OQ-5` | Legacy `ADR-0` doc date/location | Documentation metadata only; zero code impact |
| `OQ-6` | 15 Golden scenarios & Agronomy Owner pass threshold | Build runnable `backend/tests/golden/` harness + sample fixture clearly marked `# TODO(OQ-6)` without inventing agronomic truth |
| `OQ-7` | Backups, RPO/RTO & `input_snapshot_gz` archival TTL | Configurable optional pruning TTL (`# TODO(OQ-7)`); documented in `RUNBOOK.md` |
| `OQ-8` | `DEGRADED_MODE_MAX_AGE_HOURS` & `ADR-7` `Deprecation`/`Sunset` window | `DEGRADED_MODE_MAX_AGE_HOURS=72` configurable; deprecation headers middleware hook `# TODO(OQ-8)` |
| `OQ-9` | Guelma regional boundary polygon coordinates | Stored in `public.demo_locations.boundary` seed; editable cleanly (`# TODO(OQ-9)`) |
| `OQ-10` | Protected/greenhouse `INPUT-03` override | Strict `INPUT-03` table by default + documented greenhouse config hook (`# TODO(OQ-10)`) |
| `OQ-11` | Strategy tie-breaking & `priority_fit` spread | Owned by External ML; `SEM-01` validates non-empty ordering only |
| `OQ-D1` | `Schema: dataset` tables/units | Schema created by Alembic (`# TODO(OQ-D1)`); `ml_reader` granted `USAGE` + `SELECT` + `ALTER DEFAULT PRIVILEGES` |
| `OQ-D2` | Spatial/temporal coverage of initial dataset | Metadata stored in `public.dataset_registry` (`# TODO(OQ-D2)`) |
| `OQ-D3` | Dataset rollout / zero-downtime swap vs drain | `uq_dataset_registry_single_active` + pinning per `analysis_requests.dataset_version` (`# TODO(OQ-D3)`) |
| `OQ-D4` | `ml_reader` statement timeout & connection limit | Configurable `ML_DB_STATEMENT_TIMEOUT_MS=5000`, `ML_DB_CONNECTION_LIMIT=10` in Alembic (`# TODO(OQ-D4)`) |
| `OQ-D5` | Cross-verifying `"data_source": "dataset"` evidence | `SEM-04` validates `data_source` enum & `derived` rules without hardcoding internal `dataset` queries (`# TODO(OQ-D5)`) |
| `OQ-D6` | Minimum parcel history richness for `422 INSUFFICIENT_DATA` | Propagated cleanly from ML `422` response (Backend enforces `crop_history.minItems = 1`) |
| `OQ-D7` | Authoritative Guelma shapefile source | Placeholder 10-vertex Polygon in `ENDPOINTS B.4` flagged non-authoritative `# TODO(OQ-D7)` |
| `OQ-D8` | Unstudied demo parcel field measurements | Optional frontend-supplied `is_unverified_demo_parcel=true` -> `DEMO_PARCEL_UNVERIFIED` (`default_parcel_*` removed per `IMPL-023`) |

---

## 3.11 Fixtures & Edge-Case Test Catalogue (`Visual I/O §9–§10`)

- **Fixtures (`Visual I/O §9.1–§9.4`):**
  1. `9.1 input.json` (`FarmAnalysisInput`, Guest, Guelma pre-designated unstudied parcel `F1`, `36.52° N, 7.52° E`, `soil.source: "unknown"`).
  2. `9.2 input_setif.json` (`FarmAnalysisInput`, Registered user, Sétif `36.19° N, 5.41° E`, `elevation_m: 980.0`, `crop_name_raw: "Ble dur local"`).
  3. `9.3 output.json` (`AnalysisResult`, NO `analysis_id`, 3 strategies including 1 baseline, `dataset_version_used: "2026.11-guelma-v1"`).
  4. `9.4 catalog.json` (`CropCatalog`, `catalog_version: "2026.11"`, 6 canonical crops: `durum_wheat`, `barley`, `chickpea`, `vetch_forage`, `sunflower`, `fallow`).
- **Edge-Case Test Matrix (`Visual I/O §10` items 1–8 + `IMPL-001` / `IMPL-008`):**
  1. `sum(priorities.weights.*) != 100` on `POST /analysis` -> `400 INVALID_INPUT` (`INPUT-01`) before DB enqueue.
  2. `planting_month: 8` with `start_season: "winter"` at `latitude: 36.52` or overlapping `target`/`excluded` crops -> `400 INVALID_INPUT` (`INPUT-02`, `INPUT-03`).
  3. Guest creates 4th farm or exceeds 40 analysis quarters -> `403 GUEST_LIMIT_REACHED`; exceeding `GUEST_BURST_PER_MIN` (`30`) or `RATE_LIMIT_CRUD_PER_MIN` (`60`) -> `429 RATE_LIMIT_EXCEEDED` + `Retry-After` via Redis.
  4. Corrupt JSON or Stage 1 / Stage 2 (`SEM-01..06`) failure -> mint `analysis_<12hex>`, store `analysis_results(status='invalid', validation_passed=false)`, mark request `'failed'` with `ML_INVALID_RESPONSE`.
  5. `POST /analysis/requests/{id}/cancel` -> `200 {status: "cancelled"}` (`pending` refunds `quota_units=0` + decrements Redis immediately inside `/cancel`; `running` pre-dispatch refunds without consuming `GUEST_MAX_ML_REFUNDS=3`, mid-flight aborts HTTP + backoff sleeps and unlocks slot); `409 CONFLICT` if terminal.
  6. Foreign owner `GET /farms/farm_99` -> `404 NOT_FOUND`; Guest Setif field (`36.19° N, 5.41° E`) -> `422 OUTSIDE_DEMO_BOUNDARY`; Registered Setif field -> `201 Created` + `MVP_OUTSIDE_COVERAGE`.
  7. `dataset_version_used != dataset_version` (`SEM-07`) -> `502 DATASET_VERSION_UNAVAILABLE` (`validation_passed=false`); absent active dataset -> `503 DATASET_UNAVAILABLE`.
  8. `schema_version: "5.1"` + extra unknown property -> **PASSES** (logged `WARNING` + `ml_unknown_fields_observed_total`); `schema_version: "6.0"` -> **FAILS**; outage replay -> `degraded_mode: {kind: "last_good_replay", stale: true, source_analysis_id, ...}`.
  9. `MLProviderManager` switches between `MockMLAdapter` and `RealMLAdapter` **only** in `APP_ENV in ('development','test')` when `ML_PROVIDER_MODE='auto'`, never selects mock in `production` or `ML_PROVIDER_MODE='real'`, and never silently falls back on in-flight errors (`IMPL-008`).
