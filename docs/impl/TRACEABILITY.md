# FieldShift Planner Backend — Requirements Traceability Matrix (`TRACEABILITY.md`)

> **Legend:** Status remains **`Pending`** until implemented, verified by automated tests, and closed at its milestone gate.
> **Totals Tracked:** `34` Backend Routes (Option-A `429`/`500`/`503` normative in `openapi.yaml`) + `3` ML Routes · `13` `public` Tables + `Schema: dataset` (`ml_reader`) · `19` Error Codes + `2` Notices · `40` Normative `.env` Vars + `7` Companion Settings · `6` Redis Rate-Limit Buckets (incl. `120 req/min` poll bucket) · `3` `INPUT` Rules + `7` `SEM` Rules · `4` Workflows (`W1–W4`) · `6` KPIs · `10` ADRs + `21` `IMPL` Decisions (`#1–#5` Second-Audit Hardening) · `19` Open Questions (`OQ-*`).

---

## 1. Backend REST Routes (`34 / 34` — `openapi.yaml` & `ENDPOINTS B.2–B.9`)

| ID | Route & Method | `operationId` | Spec Source | Target Module(s) | Target Test(s) | Milestone | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :---: | :--- |
| `RT-01` | `POST /api/v1/auth/guest` | `startGuestSession` | `ENDPOINTS B.3`, `openapi.yaml` | `api/v1/auth.py`, `services/auth.py` | `tests/integration/test_auth.py`, `tests/contract/` | `M3` | `M3 Verified (live PostGIS + Redis integration)` |
| `RT-02` | `POST /api/v1/auth/register` | `registerUser` | `ENDPOINTS B.3`, `openapi.yaml` | `api/v1/auth.py`, `services/auth.py` | `tests/integration/test_auth.py`, `tests/concurrency/` | `M3` | `M3 Verified (integration + 5x concurrency race)` |
| `RT-03` | `POST /api/v1/auth/login` | `loginUser` | `ENDPOINTS B.3`, `openapi.yaml` | `api/v1/auth.py`, `services/auth.py` | `tests/integration/test_auth.py`, `tests/contract/` | `M3` | `M3 Verified (integration)` |
| `RT-04` | `POST /api/v1/auth/refresh` | `refreshToken` | `ENDPOINTS B.3`, `openapi.yaml` | `api/v1/auth.py`, `services/auth.py` | `tests/integration/test_auth.py`, `tests/concurrency/` | `M3` | `M3 Verified (integration + 8x replay concurrency race)` |
| `RT-05` | `POST /api/v1/auth/logout` | `logoutUser` | `ENDPOINTS B.3`, `openapi.yaml` | `api/v1/auth.py`, `services/auth.py` | `tests/integration/test_auth.py`, `tests/contract/` | `M3` | `M3 Verified (integration)` |
| `RT-06` | `GET /api/v1/auth/me` | `getMe` | `ENDPOINTS B.3`, `openapi.yaml` | `api/v1/auth.py`, `services/auth.py` | `tests/integration/test_auth.py`, `tests/contract/` | `M3` | `M3 Verified (integration + live Redis 429/503)` |
| `RT-07` | `DELETE /api/v1/auth/me` | `deleteMe` | `ENDPOINTS B.3`, `openapi.yaml` | `api/v1/auth.py`, `services/auth.py` | `tests/integration/test_auth.py`, `tests/contract/` | `M3` | `M3 Verified (integration cascade purge)` |
| `RT-08` | `GET /api/v1/auth/me/export` | `exportMeData` | `ENDPOINTS B.3`, `openapi.yaml` | `api/v1/auth.py`, `services/auth.py`, `schemas/auth.py` | `tests/integration/test_auth.py`, `tests/integration/test_farms_and_fields.py` | `M3` *(re-verified `M5/M7`)* | `M3+M5 Verified (HTTP M5 farms/fields/crop_history export; M7 analysis blobs pending)` |
| `RT-09` | `POST /api/v1/auth/claim-guest` | `claimGuestSession` | `ENDPOINTS B.3`, `openapi.yaml` | `api/v1/auth.py`, `services/auth.py`, `core/rate_limit.py` | `tests/integration/test_auth.py`, `tests/concurrency/test_auth_concurrency.py`, `tests/integration/test_farms_and_fields.py` | `M3` *(re-verified `M5/M7`)* | `M3+M5 Verified (integration, 5x race & HTTP M5 farms/fields transfer; M7 analysis claim pending)` |
| `RT-10` | `GET /api/v1/demo/locations` | `listDemoLocations` | `ENDPOINTS B.4`, `openapi.yaml` | `api/v1/demo.py`, `services/demo.py` | `tests/integration/test_demo.py` | `M4` | `M4 Verified (live PostGIS + OpenAPI)` |
| `RT-11` | `GET /api/v1/demo/locations/{id}/boundary` | `getDemoLocationBoundary` | `ENDPOINTS B.4`, `openapi.yaml` | `api/v1/demo.py`, `services/demo.py` | `tests/integration/test_demo.py` | `M4` | `M4 Verified (live PostGIS GeoJSON + bbox + OpenAPI)` |
| `RT-12` | `GET /api/v1/demo/session` | `getDemoSession` | `ENDPOINTS B.4`, `openapi.yaml` | `api/v1/demo.py`, `services/demo.py` | `tests/integration/test_demo.py` | `M4` | `M4 Verified (live PostGIS + Redis 429/503 + OpenAPI)` |
| `RT-13` | `DELETE /api/v1/demo/session` | `deleteDemoSession` | `ENDPOINTS B.4`, `openapi.yaml` | `api/v1/demo.py`, `services/demo.py` | `tests/integration/test_demo.py` | `M4` | `M4 Verified (cascade purge + Redis cleanup)` |
| `RT-14` | `GET /api/v1/farms` | `listFarms` | `ENDPOINTS B.5`, `openapi.yaml` | `api/v1/farms.py`, `services/farms.py`, `repositories/farm.py` | `tests/integration/test_farms_and_fields.py` | `M5` | `M5 Verified (live PostGIS + Redis + LIKE escape + OpenAPI)` |
| `RT-15` | `POST /api/v1/farms` | `createFarm` | `ENDPOINTS B.5`, `openapi.yaml` | `api/v1/farms.py`, `services/farms.py`, `repositories/farm.py` | `tests/integration/test_farms_and_fields.py`, `tests/concurrency/test_quota_concurrency.py` | `M5` | `M5 Verified (live PostGIS + 8x guest concurrency race + OpenAPI)` |
| `RT-16` | `GET /api/v1/farms/{farm_id}` | `getFarm` | `ENDPOINTS B.5`, `openapi.yaml` | `api/v1/farms.py`, `services/farms.py` | `tests/integration/test_farms_and_fields.py` | `M5` | `M5 Verified (owner-scoped 404 + Pitfall #14 + OpenAPI)` |
| `RT-17` | `PUT /api/v1/farms/{farm_id}` | `replaceFarm` | `ENDPOINTS B.5`, `openapi.yaml` | `api/v1/farms.py`, `services/farms.py` | `tests/integration/test_farms_and_fields.py` | `M5` | `M5 Verified (integration + OpenAPI)` |
| `RT-18` | `PATCH /api/v1/farms/{farm_id}` | `patchFarm` | `ENDPOINTS B.5`, `openapi.yaml` | `api/v1/farms.py`, `services/farms.py` | `tests/integration/test_farms_and_fields.py` | `M5` | `M5 Verified (nullable vs non-null rules + OpenAPI)` |
| `RT-19` | `DELETE /api/v1/farms/{farm_id}` | `deleteFarm` | `ENDPOINTS B.5`, `openapi.yaml` | `api/v1/farms.py`, `services/farms.py` | `tests/integration/test_farms_and_fields.py` | `M5` | `M5 Verified (cascade delete + 404 isolation)` |
| `RT-20` | `GET /api/v1/farms/{farm_id}/fields` | `listFields` | `ENDPOINTS B.6`, `openapi.yaml` | `api/v1/fields.py`, `services/fields.py`, `repositories/field.py` | `tests/integration/test_farms_and_fields.py` | `M5` | `M5 Verified (PostGIS + soil/water filters + pagination + OpenAPI)` |
| `RT-21` | `POST /api/v1/farms/{farm_id}/fields` | `createField` | `ENDPOINTS B.6`, `openapi.yaml` | `api/v1/fields.py`, `services/fields.py`, `services/geo.py` | `tests/integration/test_farms_and_fields.py`, `tests/concurrency/test_quota_concurrency.py` | `M5` | `M5 Verified (PostGIS ST_Covers + 10x quota race + 6x dup race + OpenAPI)` |
| `RT-22` | `GET /api/v1/farms/{farm_id}/fields/{field_id}` | `getField` | `ENDPOINTS B.6`, `openapi.yaml` | `api/v1/fields.py`, `services/fields.py` | `tests/integration/test_farms_and_fields.py` | `M5` | `M5 Verified (FieldDetailPublic + ordered crop_history + warnings)` |
| `RT-23` | `PUT /api/v1/farms/{farm_id}/fields/{field_id}` | `replaceField` | `ENDPOINTS B.6`, `openapi.yaml` | `api/v1/fields.py`, `services/fields.py` | `tests/integration/test_farms_and_fields.py` | `M5` | `M5 Verified (atomic crop_history + PostGIS boundary + OpenAPI)` |
| `RT-24` | `PATCH /api/v1/farms/{farm_id}/fields/{field_id}` | `patchField` | `ENDPOINTS B.6`, `openapi.yaml` | `api/v1/fields.py`, `services/fields.py`, `schemas/field.py` | `tests/integration/test_farms_and_fields.py` | `M5` | `M5 Verified (strict sub-models, soil_source/water clear, GeoJSON + OpenAPI)` |
| `RT-25` | `DELETE /api/v1/farms/{farm_id}/fields/{field_id}` | `deleteField` | `ENDPOINTS B.6`, `openapi.yaml` | `api/v1/fields.py`, `services/fields.py` | `tests/integration/test_farms_and_fields.py` | `M5` | `M5 Verified (cascade delete + farm field_count consistency)` |
| `RT-26` | `POST /api/v1/analysis` | `submitAnalysis` | `ENDPOINTS B.7`, `openapi.yaml` | `api/v1/analysis.py`, `services/analysis.py`, `core/rate_limit.py` | `tests/integration/test_analysis.py`, `tests/concurrency/` | `M7` *(re-verified `M8–M10`)* | `Pending` |
| `RT-27` | `GET /api/v1/analysis/requests/{request_id}` | `pollAnalysisRequest` | `ENDPOINTS B.7`, `openapi.yaml` (`120/min` L829) | `api/v1/analysis.py`, `services/analysis.py`, `core/rate_limit.py` | `tests/integration/test_analysis.py`, `tests/integration/test_rate_limit.py` | `M7` | `Pending` |
| `RT-28` | `POST /api/v1/analysis/requests/{request_id}/cancel` | `cancelAnalysisRequest` | `ENDPOINTS B.7`, `openapi.yaml` | `api/v1/analysis.py`, `services/analysis.py`, `core/rate_limit.py` | `tests/integration/test_analysis.py`, `tests/concurrency/` | `M7, M8` | `Pending` |
| `RT-29` | `GET /api/v1/analysis/{analysis_id}` | `getAnalysisResult` | `ENDPOINTS B.7`, `openapi.yaml` | `api/v1/analysis.py`, `services/analysis.py` | `tests/integration/test_analysis.py`, `tests/integration/test_breaker.py` | `M7, M10` | `Pending` |
| `RT-30` | `PATCH /api/v1/analysis/{analysis_id}/selection` | `updateAnalysisSelection` | `ENDPOINTS B.7`, `openapi.yaml` | `api/v1/analysis.py`, `services/analysis.py` (`analysis_results FOR UPDATE`) | `tests/integration/test_analysis.py`, `tests/concurrency/` | `M7` | `Pending` |
| `RT-31` | `GET /api/v1/farms/{farm_id}/analyses` | `listFarmAnalyses` | `ENDPOINTS B.7`, `openapi.yaml` | `api/v1/analysis.py`, `services/analysis.py` | `tests/integration/test_analysis.py`, `tests/contract/` | `M7` | `Pending` |
| `RT-32` | `GET /api/v1/catalog` | `getCatalog` | `ENDPOINTS B.8`, `openapi.yaml` | `api/v1/catalog.py`, `services/catalog.py` | `tests/integration/test_catalog.py`, `tests/contract/` | `M6` | `M6 Verified (cold-start, filters, ?lang, keyset, N/N-1)` |
| `RT-33` | `GET /api/v1/health` | `getHealth` | `ENDPOINTS B.9`, `openapi.yaml` | `api/v1/system.py`, `services/health.py` | `tests/integration/test_system.py`, `tests/contract/` | `M11` | `Pending` |
| `RT-34` | `GET /api/v1/metrics` | `getMetrics` | `ENDPOINTS B.9`, `openapi.yaml` | `api/v1/system.py`, `core/metrics.py` | `tests/integration/test_system.py`, `tests/contract/` | `M11` | `Pending` |

## 2. External ML Sub-Contract Routes (`3 / 3` — `ENDPOINTS B.10`)

| ID | External ML Route | Adapter Interface | Target Module(s) | Target Test(s) | Milestone | Status |
| :--- | :--- | :--- | :--- | :--- | :---: | :--- |
| `ML-01` | `POST {ML_SERVICE_URL}/v1/analyze` | `MLAdapter.analyze()` | `ml_client/{base,real_adapter,mock_adapter,mock_server,manager}.py` | `tests/unit/test_ml_client.py`, `tests/integration/test_worker.py` | `M6, M8` | `M6 Verified (RealMLAdapter gzip/key-rotation/TCP + MockMLAdapter/mock_server + manager); M8 worker pending` |
| `ML-02` | `GET {ML_SERVICE_URL}/v1/catalog` | `MLAdapter.get_catalog()` | `ml_client/`, `services/catalog.py`, `worker/jobs.py` | `tests/unit/test_ml_client.py`, `tests/integration/test_catalog.py` | `M6, M11` | `M6 Verified (RealMLAdapter multi-page + CropCatalog schema + MockMLAdapter + cold-start); M11 cron pending` |
| `ML-03` | `GET {ML_SERVICE_URL}/v1/health` | `MLAdapter.get_health()` | `ml_client/`, `services/health.py` | `tests/unit/test_ml_provider_manager.py`, `tests/integration/test_system.py` | `M6, M11` | `M6 Verified (RealMLAdapter + MockMLAdapter + MLProviderManager + Redis ml:provider_status); M11 /health pending` |

## 3. Database Objects (`13 / 13` `public` Tables + `Schema: dataset` / `ml_reader`)

| ID | DB Object | Spec Source | Target Module(s) | Target Test(s) | Milestone | Status |
| :--- | :--- | :--- | :--- | :--- | :---: | :--- |
| `DB-01` | `public.users` | `ENDPOINTS A.4` | `db/migrations/`, `models/user.py`, `repositories/user.py` | `tests/migration/test_schema_and_ml_reader.py`, `tests/integration/test_auth.py` | `M1, M3` | `M1+M3 Verified` |
| `DB-02` | `public.refresh_tokens` | `ENDPOINTS A.4` | `db/migrations/`, `models/user.py`, `repositories/user.py` | `tests/migration/test_schema_and_ml_reader.py`, `tests/concurrency/` | `M1, M3` | `M1+M3 Verified` |
| `DB-03` | `public.demo_locations` | `ENDPOINTS A.4` | `db/migrations/`, `models/demo.py`, `db/seed.py`, `repositories/demo.py` | `tests/migration/test_schema_and_ml_reader.py`, `tests/integration/test_demo.py` | `M1, M4` | `M1+M4 Verified (PostGIS ST_Covers + boundary + pagination)` |
| `DB-04` | `public.guest_sessions` | `ENDPOINTS A.4` | `db/migrations/`, `models/demo.py`, `repositories/user.py` | `tests/migration/test_schema_and_ml_reader.py`, `tests/integration/test_auth.py` | `M1, M3` | `M1+M3 Verified` |
| `DB-05` | `public.farms` | `ENDPOINTS A.4` | `db/migrations/`, `models/farm.py`, `repositories/farm.py` | `tests/migration/test_schema_and_ml_reader.py`, `tests/integration/test_farms_and_fields.py` | `M1, M5` | `M1+M5 Verified (DDL + ORM + live CRUD & race tests)` |
| `DB-06` | `public.fields` | `ENDPOINTS A.4` | `db/migrations/`, `models/field.py`, `repositories/field.py` | `tests/migration/test_schema_and_ml_reader.py`, `tests/integration/test_farms_and_fields.py` | `M1, M5` | `M1+M5 Verified (DDL + ORM + live PostGIS POINT/POLYGON & race tests)` |
| `DB-07` | `public.field_crop_history` | `ENDPOINTS A.4` | `db/migrations/`, `models/field.py`, `repositories/field.py` | `tests/migration/test_schema_and_ml_reader.py`, `tests/integration/test_farms_and_fields.py` | `M1, M5` | `M1+M5 Verified (DDL + ORM + atomic replace & 409 unique year/season)` |
| `DB-08` | `public.crop_catalog` | `ENDPOINTS A.4` | `db/migrations/`, `models/catalog.py`, `repositories/catalog.py`, `services/catalog.py` | `tests/migration/test_schema_and_ml_reader.py`, `tests/integration/test_catalog.py` | `M1, M6` | `M1+M6 Verified (DDL, ORM, upsert, N/N-1 retention, advisory lock)` |
| `DB-09` | `public.dataset_registry` | `ENDPOINTS A.4` | `db/migrations/`, `models/catalog.py`, `repositories/dataset.py`, `db/seed.py` | `tests/migration/test_schema_and_ml_reader.py`, `tests/integration/test_catalog.py`, `tests/integration/test_analysis.py` | `M1, M6` | `M1+M6 Verified (DDL, ORM, seed, active lookup -> 503); M7/M8 analysis pinning pending` |
| `DB-10` | `public.analysis_requests` | `ENDPOINTS A.4` | `db/migrations/`, `models/analysis.py`, `repositories/analysis.py` | `tests/migration/test_schema_and_ml_reader.py`, `tests/integration/test_worker.py` | `M1, M7, M8` | `M1 Verified (DDL + ORM; M7–M8 pending)` |
| `DB-11` | `public.analysis_results` | `ENDPOINTS A.4` | `db/migrations/`, `models/analysis.py`, `repositories/analysis.py` | `tests/migration/test_schema_and_ml_reader.py`, `tests/integration/test_verification.py` | `M1, M9` | `M1 Verified (DDL + ORM; M9 pending)` |
| `DB-12` | `public.analysis_selections` | `ENDPOINTS A.4` | `db/migrations/`, `models/analysis.py`, `repositories/analysis.py` | `tests/migration/test_schema_and_ml_reader.py`, `tests/integration/test_analysis.py` | `M1, M7` | `M1 Verified (DDL + ORM; M7 pending)` |
| `DB-13` | `public.ml_breaker_state` | `ENDPOINTS A.4` | `db/migrations/`, `models/breaker.py`, `worker/breaker.py`, `db/seed.py` | `tests/migration/test_schema_and_ml_reader.py`, `tests/integration/test_breaker.py` | `M1, M10` | `M1 Verified (DDL + ORM; M10 pending)` |
| `DB-14` | `Schema: dataset` & Role `ml_reader` | `ENDPOINTS A.5`, `ADR-9` | `db/migrations/versions/001_initial_schema.py` | `tests/migration/test_schema_and_ml_reader.py` | `M1` | `M1 Verified (Docker postgis/postgis:16-3.4 roundtrip + alembic check + ml_reader)` |

## 4. Error Codes (`19 / 19`) & Warning Notices (`2 / 2`)

| ID | Symbol & HTTP Status | Target Module(s) | Target Test(s) | Milestone | Status |
| :--- | :--- | :--- | :--- | :---: | :--- |
| `ERR-01` | `INVALID_INPUT` (`400`) | `core/errors.py`, `services/validation.py` | `tests/contract/test_errors.py`, `tests/unit/test_input_rules.py` | `M2, M7` | `M2 Verified (400 + 422 override); M7 INPUT-01..03 pending` |
| `ERR-02` | `UNAUTHORIZED` (`401`) | `core/errors.py`, `api/deps.py`, `services/auth.py` | `tests/contract/test_errors.py`, `tests/integration/test_auth.py` | `M2, M3` | `M2+M3 Verified (JWT/refresh/guest 401)` |
| `ERR-03` | `GUEST_LIMIT_REACHED` (`403`) | `core/errors.py`, `services/farms.py`, `services/fields.py`, `services/analysis.py` | `tests/contract/test_errors.py`, `tests/integration/test_farms_and_fields.py`, `tests/concurrency/test_quota_concurrency.py` | `M2, M5, M7` | `M2+M5 Verified (row-locked 3 farms / 5 fields + 8x/10x race); M7 analyses pending` |
| `ERR-04` | `NOT_FOUND` (`404`) | `core/errors.py`, all owner-scoped repos/services | `tests/contract/test_errors.py`, `tests/integration/test_demo.py`, `tests/integration/test_farms_and_fields.py` | `M2, M4, M5` | `M2+M4+M5 Verified (demo boundary + owner-scoped farm/field 404)` |
| `ERR-05` | `CONFLICT` (`409`) | `core/errors.py`, `services/auth.py`, `services/fields.py`, `services/analysis.py` | `tests/contract/test_errors.py`, `tests/integration/test_auth.py`, `tests/integration/test_farms_and_fields.py`, `tests/concurrency/` | `M2, M3, M5, M7` | `M2+M3+M5 Verified (dup email/field_id/crop_history 409 + races); M7 idempotency pending` |
| `ERR-06` | `CATALOG_VERSION_MISMATCH` (`409`) | `core/errors.py`, `ml_client/base.py`, `services/catalog.py`, `worker/runner.py` | `tests/unit/test_ml_client.py`, `tests/integration/test_worker.py` | `M2, M6, M8` | `M2+M6 Verified (ErrorCode + Envelope + MLCatalogVersionMismatchError classification); M8 worker retry pending` |
| `ERR-07` | `OUTSIDE_DEMO_BOUNDARY` (`422`) | `core/errors.py`, `services/geo.py`, `services/fields.py` | `tests/integration/test_demo.py`, `tests/integration/test_farms_and_fields.py` | `M2, M4, M5` | `M2+M4+M5 Verified (PostGIS ST_Covers 422 on guest field POST/PATCH/PUT)` |
| `ERR-08` | `INSUFFICIENT_DATA` (`422`) | `core/errors.py`, `worker/runner.py` | `tests/contract/test_errors.py`, `tests/unit/test_ml_error_map.py` | `M2, M8` | `M2 Verified (ErrorCode + Envelope); M8 pending` |
| `ERR-09` | `RATE_LIMIT_EXCEEDED` (`429` + `Retry-After`) | `core/errors.py`, `core/rate_limit.py` | `tests/contract/test_errors.py`, `tests/integration/test_rate_limit.py`, `tests/integration/test_auth.py` | `M2, M3, M7` | `M2+M3 Verified (live Redis 429 on /auth/guest & /auth/me); M7 pending` |
| `ERR-10` | `INTERNAL_ERROR` (`500`) | `core/errors.py`, `main.py`, `worker/runner.py` | `tests/contract/test_errors.py`, `tests/unit/test_ml_error_map.py` | `M2, M8` | `M2 Verified (500 masking + X-Request-Id); M8 pending` |
| `ERR-11` | `ML_UNAVAILABLE` (`502`) | `core/errors.py`, `worker/{breaker,runner}.py` | `tests/contract/test_errors.py`, `tests/integration/test_breaker.py` | `M2, M8, M10` | `M2 Verified (ErrorCode + Envelope); M8, M10 pending` |
| `ERR-12` | `ML_INVALID_RESPONSE` (`502`) | `core/errors.py`, `services/verification.py` | `tests/contract/test_errors.py`, `tests/unit/test_sem_rules.py` | `M2, M9` | `M2 Verified (ErrorCode + Envelope); M9 pending` |
| `ERR-13` | `ML_CONTRACT_ERROR` (`502`) | `core/errors.py`, `worker/runner.py` | `tests/contract/test_errors.py`, `tests/unit/test_ml_error_map.py` | `M2, M8` | `M2 Verified (ErrorCode + Envelope); M8 pending` |
| `ERR-14` | `DATASET_VERSION_UNAVAILABLE` (`502`) | `core/errors.py`, `services/verification.py`, `worker/runner.py` | `tests/contract/test_errors.py`, `tests/unit/test_sem_rules.py` | `M2, M8, M9` | `M2 Verified (ErrorCode + Envelope); M8, M9 pending` |
| `ERR-15` | `ML_DATASET_ERROR` (`502`) | `core/errors.py`, `worker/runner.py` | `tests/contract/test_errors.py`, `tests/unit/test_ml_error_map.py` | `M2, M8` | `M2 Verified (ErrorCode + Envelope); M8 pending` |
| `ERR-16` | `SERVICE_UNAVAILABLE` (`503`) | `core/errors.py`, `services/health.py` | `tests/contract/test_errors.py`, `tests/integration/test_system.py` | `M2, M11` | `M2 Verified (503 fail-closed Redis outage); M11 /health pending` |
| `ERR-17` | `DATASET_UNAVAILABLE` (`503`) | `core/errors.py`, `repositories/dataset.py`, `services/health.py` | `tests/integration/test_catalog.py`, `tests/integration/test_analysis.py` | `M2, M6, M7, M11` | `M2+M6 Verified (ErrorCode + Envelope + require_active_dataset 503); M7, M11 pending` |
| `ERR-18` | `ML_TIMEOUT` (`504`) | `core/errors.py`, `ml_client/`, `worker/runner.py` | `tests/contract/test_errors.py`, `tests/integration/test_worker.py` | `M2, M8` | `M2 Verified (ErrorCode + Envelope); M8 pending` |
| `ERR-19` | `JOB_TIMEOUT` (`504`) | `core/errors.py`, `api/v1/analysis.py` | `tests/contract/test_errors.py`, `tests/integration/test_analysis.py` | `M2, M7` | `M2 Verified (ErrorCode + Envelope); M7 pending` |
| `NTC-01` | `DEMO_PARCEL_UNVERIFIED` | `services/{fields,analysis,auth}.py` | `tests/integration/test_auth.py`, `tests/integration/test_farms_and_fields.py` | `M3, M5, M7` | `M3+M5 Verified (/auth/me/export & /farms/*/fields*); M7 /analysis pending` |
| `NTC-02` | `MVP_OUTSIDE_COVERAGE` | `services/geo.py`, `services/{fields,analysis}.py` | `tests/integration/test_demo.py`, `tests/integration/test_farms_and_fields.py` | `M4, M5, M7` | `M4+M5 Verified (PostGIS ST_Covers notice on registered fields); M7 /analysis pending` |

## 5. Validation Rules (`INPUT-01..03`, Stage 1, `SEM-01..07`)

| ID | Rule | Spec Source | Target Module(s) | Target Test(s) | Milestone | Status |
| :--- | :--- | :--- | :--- | :--- | :---: | :--- |
| `VAL-IN1` | `INPUT-01`: `sum(priorities.weights.*) == 100` | `Blueprint §4 W4` | `services/validation.py` | `tests/unit/test_input_rules.py` | `M7` | `Pending` |
| `VAL-IN2` | `INPUT-02`: `target_crop_ids ∩ excluded_crop_ids == ∅` | `Blueprint §4 W4` | `services/validation.py` | `tests/unit/test_input_rules.py` | `M7` | `Pending` |
| `VAL-IN3` | `INPUT-03`: Hemisphere × `start_season` × `planting_month` | `Blueprint §4 W4` | `services/validation.py` | `tests/unit/test_input_rules.py` | `M7` | `Pending` |
| `VAL-ST1` | Stage 1 JSON Schema + Unknown Field Policy (`5.x` warn / `6.0` fail) | `ADR-6`, `schema-v5.0.json` | `services/verification.py` | `tests/contract/test_schema_policy.py` | `M9` | `Pending` |
| `VAL-SM1` | `SEM-01`: Field strategies ordering, baseline count (`1` when `ok`), unique `strategy_id` | `Blueprint §4 W4` | `services/verification.py` | `tests/unit/test_sem_rules.py` | `M9` | `Pending` |
| `VAL-SM2` | `SEM-02`: 1:1 `field_id` alignment & `len(seasons) == horizon_seasons` | `Blueprint §4 W4` | `services/verification.py` | `tests/unit/test_sem_rules.py` | `M9` | `Pending` |
| `VAL-SM3` | `SEM-03`: Every `crop_id` matches `(catalog_version, crop_id)` category/roles | `Blueprint §4 W4` | `services/verification.py` | `tests/unit/test_sem_rules.py` | `M9` | `Pending` |
| `VAL-SM4` | `SEM-04`: `data_source` provenance + farmer input match (`OQ-3`) + `derived: true` | `Blueprint §4 W4`, `Visual I/O §8` | `services/verification.py` | `tests/unit/test_sem_rules.py` | `M9` | `Pending` |
| `VAL-SM5` | `SEM-05`: `suggested_strategy_id` present in `strategies[]` | `Blueprint §4 W4` | `services/verification.py` | `tests/unit/test_sem_rules.py` | `M9` | `Pending` |
| `VAL-SM6` | `SEM-06`: Every `target_crop_id` evaluated in `requested_crop_results[]` | `Blueprint §4 W4` | `services/verification.py` | `tests/unit/test_sem_rules.py` | `M9` | `Pending` |
| `VAL-SM7` | `SEM-07`: `dataset_version_used == analysis_requests.dataset_version` | `Blueprint §4 W4`, `ADR-9` | `services/verification.py` | `tests/unit/test_sem_rules.py` | `M9` | `Pending` |

## 6. Workflows (`W1–W4`), KPIs (`1–6`), ADRs (`ADR-1..9`) & Decisions (`IMPL-001..021`)

| ID | Item | Spec Source | Target Module(s) | Target Test(s) | Milestone | Status |
| :--- | :--- | :--- | :--- | :--- | :---: | :--- |
| `WF-01` | Workflow `W1`: Admission check order -> `202` enqueue | `Blueprint §4 W1` | `services/analysis.py`, `api/v1/analysis.py` | `tests/integration/test_analysis.py` | `M7` | `Pending` |
| `WF-02` | Workflow `W2`: Dataset pin, `SKIP LOCKED`, breaker, bulkhead `8`, cancel | `Blueprint §4 W2` | `worker/{runner,breaker}.py` | `tests/integration/test_worker.py`, `tests/concurrency/` | `M8, M10` | `Pending` |
| `WF-03` | Workflow `W3`: Strict allowlist `FarmAnalysisInput` + `input_snapshot_gz` | `Blueprint §4 W3` | `services/analysis.py` | `tests/integration/test_security.py` | `M7` | `Pending` |
| `WF-04` | Workflow `W4`: 2-stage validation + What-If `1`-quarter replay | `Blueprint §4 W4, §4.5` | `services/{verification,analysis}.py` | `tests/integration/test_e2e_workflows.py` | `M7, M9` | `Pending` |
| `KPI-01` | `POST /analysis` `202 Accepted` `< 300ms` p95 (`OQ-1` ML SLA TBD) | `Blueprint §1.1` | `api/v1/analysis.py`, `core/metrics.py` | `tests/integration/test_analysis.py` | `M7, M12` | `Pending` |
| `KPI-02` | `100%` stored valid responses pass Stage 1 + `SEM-01..07` | `Blueprint §1.1` | `services/verification.py` | `tests/integration/test_verification.py` | `M9, M12` | `Pending` |
| `KPI-03` | `0%` fabricated sources; `SEM-04` farmer provenance & `derived: true` | `Blueprint §1.1` | `services/verification.py`, `services/fields.py` | `tests/unit/test_sem_rules.py`, `tests/integration/test_farms_and_fields.py` | `M5, M9` | `M5 Verified (soil.source farmer/unknown recomputation on POST/PUT/PATCH); M9 SEM-04 pending` |
| `KPI-04` | `100%` guest outside Guelma -> `422`; unverified parcel flag -> `DEMO_PARCEL_UNVERIFIED` | `Blueprint §1.1` | `services/geo.py`, `services/fields.py` | `tests/integration/test_demo.py`, `tests/integration/test_farms_and_fields.py` | `M4, M5` | `M4+M5 Verified (100% guest outside Guelma -> 422 & DEMO_PARCEL_UNVERIFIED on fields)` |
| `KPI-05` | ML outages trip `ml_breaker_state`, cap 8 bulkhead, label `last_good_replay` | `Blueprint §1.1` | `worker/{breaker,runner}.py` | `tests/concurrency/test_fault_injection.py` | `M8, M10, M12` | `Pending` |
| `KPI-06` | Golden 15-scenario harness (`>= TBD%` `OQ-6` pending Agronomy Owner) | `Blueprint §1.1, §4.5` | `tests/golden/` | `tests/golden/test_golden_harness.py` | `M12` | `Pending` |
| `ADR-1..9` | All Active Architecture Decisions (`ADR-0` superseded) | `ADR.md` | System-wide | Full suite + `verify_contracts.py` | `M0–M13` | `Pending` |
| `IMPL-001` | Interpolated two-bucket Redis sliding-window Lua throttles (`6` buckets incl. `120/min` poll), clamped `EXISTS`-guarded `DECRBY >= 0`/`DEL` refunds, hashed keys, `TRUSTED_PROXY_CIDRS`, PG->Redis hydration, non-burning W1 admission (incl. Step 2 `403`), `worker -> redis` dep, `503` fail-closed | `DECISIONS.md` | `core/rate_limit.py`, `services/analysis.py`, `docker-compose.yml` | `tests/integration/test_rate_limit.py`, `tests/integration/test_auth.py`, `tests/integration/test_quotas.py` | `M0, M2, M3, M7, M8` | `M2+M3 Verified (live Redis 7-alpine + PostGIS 16-3.4 + M3 auth/guest cleanup); M7/M8 pending` |
| `IMPL-002..007, 010..014` | Remaining resolved design & resilience decisions (24h idempotency savepoint, canonical hashes, `ml_reader` `FOR ROLE`, cooperative backoff/stream + `cancelled_at IS NULL` final cascade guard, reaper, refunds, SHA-256 tokens, `input_snapshot_gz`, JWT `fid`; `IMPL-015` superseded by `IMPL-023`) | `DECISIONS.md` | Corresponding `core/`, `services/`, `worker/`, `db/` modules | `tests/unit/`, `tests/migration/`, `tests/integration/`, `tests/concurrency/` | `M1–M11` | `Partially Verified (M1–M5 active modules; M7–M11 pending)` |
| `IMPL-008` | `MLAdapter` (`RealMLAdapter`/`MockMLAdapter`), `mock_server.py`, `MLProviderManager` (no-mock production guard, zero in-flight silent fallback), Redis `ml:provider_status`, `app/ml_client/fixtures/` | `DECISIONS.md` | `ml_client/{base,real_adapter,mock_adapter,mock_server,manager}.py`, `main.py` | `tests/unit/test_ml_client.py`, `tests/unit/test_ml_provider_manager.py`, `tests/integration/test_catalog.py` | `M6` | `M6 Verified` |
| `IMPL-009` | Empty `crop_catalog` cold-start (`502 ML_UNAVAILABLE` in production vs lazy mock sync in dev/test), `pg_advisory_xact_lock(hashtext('catalog_sync'))`, `N`/`N-1` retention & clock-tie guard | `DECISIONS.md` | `repositories/catalog.py`, `services/catalog.py`, `api/v1/catalog.py` | `tests/integration/test_catalog.py` | `M6` | `M6 Verified` |
| `IMPL-016` | Localized `display_name` projection from `?lang` (`en`/`fr`/`ar`) while preserving full `names` dictionary in `CropCatalog` / `GET /catalog` | `DECISIONS.md` | `schemas/catalog.py`, `services/catalog.py`, `api/v1/catalog.py` | `tests/integration/test_catalog.py` | `M6` | `M6 Verified` |
| `IMPL-017` | 13-table `last_good_replay` persistence (`res_new` copy + `req.received_at=NULL` + `error_code='last_good_replay:' \|\| id`), non-chaining filter, read-time reconstruction, `half_open -> open` failure reset & `half_open -> closed` valid-`4xx` transition | `DECISIONS.md` | `worker/breaker.py`, `services/analysis.py`, `repositories/analysis.py` | `tests/integration/test_breaker.py`, `tests/concurrency/test_fault_injection.py` | `M7, M10` | `Pending` |
| `IMPL-018` | Strict separation of `40` normative `.env` vars vs `7` fail-safe Companion Settings (`APP_ENV=production` default, `ValueError` on `production` + `ML_PROVIDER_MODE=mock`) | `DECISIONS.md` | `core/config.py`, `.env.example`, `tools/verify_contracts.py` | `tests/unit/test_config.py`, `verify_contracts.py` | `M0` | `M0 Verified` |
| `IMPL-019` | Row-locked guest farm/field quotas (`FOR UPDATE`), strict `FieldPatchRequest` nested sub-models (`soil_source`, `water_source_other`, crop history), `WarningNotice.fields[]` aggregation | `DECISIONS.md` | `services/farms.py`, `services/fields.py`, `schemas/field.py`, `services/analysis.py` | `tests/integration/test_farms_and_fields.py`, `tests/concurrency/test_quota_concurrency.py` | `M5, M7` | `M5 Verified (FOR UPDATE quotas, strict FieldPatchRequest, crop_history); M7 WarningNotice.fields pending` |
| `IMPL-020` | `POST /cancel` immediate `pending` refund (`EXISTS`-guarded Lua), `PATCH /selection` parent `analysis_results FOR UPDATE` lock + prior-`'selected'` `DELETE`, `?wait=true` `http_equivalent` error translation | `DECISIONS.md` | `api/v1/analysis.py`, `services/analysis.py`, `repositories/analysis.py` | `tests/integration/test_analysis.py`, `tests/concurrency/` | `M7, M8, M10` | `Pending` |
| `IMPL-021` | `GET /auth/me/export` `UserDataExport` exclusion of `bytea`/hashes & `FieldDetailPublic` format; `POST /auth/claim-guest` farm reassignment before guest delete + Redis cleanup | `DECISIONS.md` | `services/auth.py`, `schemas/auth.py`, `core/rate_limit.py` | `tests/integration/test_auth.py`, `tests/concurrency/test_auth_concurrency.py`, `tests/integration/test_farms_and_fields.py` | `M3, M5, M7` | `M3+M5 Verified (export serialization, claim-guest, races & HTTP M5 farms/fields; M7 analyses pending)` |
| `IMPL-023` | Remove `default_parcel_*` / `DemoParcelPreview` from backend/DB while retaining Guelma `demo_locations.boundary` & PostGIS `ST_Covers`; frontend supplies demo parcels freely | `DECISIONS.md` | `contracts/openapi.yaml`, `models/demo.py`, `db/seed.py`, `services/{auth,demo,geo}.py`, `schemas/{auth,demo}.py` | `tests/migration/test_schema_and_ml_reader.py`, `tests/integration/test_auth.py`, `tests/integration/test_demo.py`, `verify_contracts.py` | `M1, M3, M4` | `M1+M3+M4 Verified (schema, /auth/guest, /demo/* & ST_Covers)` |

## 7. Environment Variables (`40 / 40` — `ENDPOINTS Section C`)

| ID | Variable | Default / Example | Consuming Module(s) | Test Verifying Presence & Parsing | Milestone | Status |
| :--- | :--- | :--- | :--- | :--- | :---: | :--- |
| `ENV-01` | `DATABASE_URL` | `postgresql+asyncpg://...` | `core/config.py`, `db/session.py` | `tests/unit/test_config.py`, `tests/migration/test_schema_and_ml_reader.py` | `M0, M1` | `M1 Verified` |
| `ENV-02` | `DB_PASSWORD` | required in `.env` | `docker-compose.yml`, `.env.example` | `tools/verify_contracts.py` | `M0` | `M0 Verified` |
| `ENV-03` | `REDIS_URL` | `redis://redis:6379/0` | `core/config.py`, `core/rate_limit.py` | `tests/unit/test_config.py`, `tests/integration/test_rate_limit.py` | `M0, M2` | `M2 Verified (live Redis 7-alpine lifespan + integration)` |
| `ENV-04` | `ML_DATASET_DB_URL` | `postgresql://ml_reader:...` | `core/config.py`, `.env.example` | `tools/verify_contracts.py` | `M0` | `M0 Verified` |
| `ENV-05` | `ML_READER_PASSWORD` | required secret | `core/config.py`, `db/migrations/versions/001_initial_schema.py` | `tests/migration/test_schema_and_ml_reader.py` | `M0, M1` | `M1 Verified` |
| `ENV-06` | `ML_DB_STATEMENT_TIMEOUT_MS` | `5000` (`# TODO(OQ-D4)`) | `core/config.py`, `db/migrations/versions/001_initial_schema.py` | `tests/migration/test_schema_and_ml_reader.py` | `M0, M1` | `M1 Verified` |
| `ENV-07` | `ML_DB_CONNECTION_LIMIT` | `10` (`# TODO(OQ-D4)`) | `core/config.py`, `db/migrations/versions/001_initial_schema.py` | `tests/migration/test_schema_and_ml_reader.py` | `M0, M1` | `M1 Verified` |
| `ENV-08` | `JWT_SECRET_KEY` | required secret | `core/config.py`, `core/security.py` | `tests/unit/test_security.py`, `tests/integration/test_auth.py` | `M0, M3` | `M3 Verified` |
| `ENV-09` | `JWT_PREVIOUS_SECRET_KEY` | optional string | `core/config.py`, `core/security.py` | `tests/unit/test_security.py` | `M0, M3` | `M3 Verified` |
| `ENV-10` | `JWT_ACCESS_EXPIRES_SECONDS` | `3600` | `core/config.py`, `services/auth.py` | `tests/integration/test_auth.py` | `M0, M3` | `M3 Verified` |
| `ENV-11` | `JWT_REFRESH_EXPIRES_SECONDS` | `2592000` | `core/config.py`, `services/auth.py` | `tests/integration/test_auth.py` | `M0, M3` | `M3 Verified` |
| `ENV-12` | `GUEST_SESSION_DAYS` | `7` | `core/config.py`, `services/auth.py` | `tests/integration/test_auth.py` | `M0, M3` | `M3 Verified` |
| `ENV-13` | `GUEST_MAX_FARMS` | `3` | `core/config.py`, `services/farms.py` | `tests/integration/test_farms_and_fields.py`, `tests/concurrency/test_quota_concurrency.py` | `M0, M5` | `M0+M5 Verified (sequential + 8x concurrency race)` |
| `ENV-14` | `GUEST_MAX_FIELDS_PER_FARM` | `5` | `core/config.py`, `services/fields.py` | `tests/integration/test_farms_and_fields.py`, `tests/concurrency/test_quota_concurrency.py` | `M0, M5` | `M0+M5 Verified (sequential + 10x concurrency race)` |
| `ENV-15` | `GUEST_MAX_ANALYSES` | `10` (`40` quarters) | `core/config.py`, `services/analysis.py` | `tests/integration/test_quotas.py` | `M0, M7` | `Pending` |
| `ENV-16` | `GUEST_MAX_ML_REFUNDS` | `3` | `core/config.py`, `worker/runner.py` | `tests/integration/test_quotas.py` | `M0, M8` | `Pending` |
| `ENV-17` | `GUEST_BURST_PER_MIN` | `30` | `core/config.py`, `core/rate_limit.py` | `tests/integration/test_rate_limit.py` | `M0, M2` | `M2 Verified (live Redis 7-alpine rate limit test)` |
| `ENV-18` | `GUEST_CREATE_PER_IP_HOUR` | `5` | `core/config.py`, `core/rate_limit.py` | `tests/integration/test_auth.py`, `tests/integration/test_rate_limit.py` | `M0, M3` | `M3 Verified (live Redis 429 on POST /auth/guest)` |
| `ENV-19` | `RATE_LIMIT_CRUD_PER_MIN` | `60` | `core/config.py`, `core/rate_limit.py` | `tests/integration/test_rate_limit.py` | `M0, M2` | `M2 Verified (live Redis 7-alpine rate limit test)` |
| `ENV-20` | `RATE_LIMIT_ANALYSIS_PER_HOUR` | `10` (`40` quarters/h) | `core/config.py`, `core/rate_limit.py` | `tests/integration/test_rate_limit.py` | `M0, M7` | `Pending` |
| `ENV-21` | `ANALYSIS_PER_IP_HOUR` | `15` (`60` quarters/h) | `core/config.py`, `core/rate_limit.py` | `tests/integration/test_rate_limit.py` | `M0, M7` | `Pending` |
| `ENV-22` | `ML_SERVICE_URL` | `https://ml.fieldshift.internal` | `core/config.py`, `ml_client/{real_adapter,manager}.py` | `tests/unit/test_ml_provider_manager.py`, `tests/unit/test_ml_client.py`, `tests/integration/test_catalog.py` | `M0, M6` | `M0+M6 Verified` |
| `ENV-23` | `ML_SERVICE_API_KEY` | required secret | `core/config.py`, `ml_client/real_adapter.py`, `ml_client/mock_server.py` | `tests/unit/test_ml_client.py`, `tests/integration/test_catalog.py` | `M0, M6` | `M0+M6 Verified` |
| `ENV-24` | `ML_SERVICE_PREVIOUS_API_KEY` | optional string | `core/config.py`, `ml_client/real_adapter.py`, `ml_client/mock_server.py` | `tests/unit/test_ml_client.py` | `M0, M6, M8` | `M0+M6 Verified (1x rotation retry + fail); M8 worker E2E pending` |
| `ENV-25` | `ML_TIMEOUT_SECONDS` | `60` | `core/config.py`, `ml_client/real_adapter.py` | `tests/integration/test_worker.py` | `M0, M8` | `Pending` |
| `ENV-26` | `ML_MAX_RETRIES` | `1` | `core/config.py`, `worker/runner.py` | `tests/unit/test_ml_error_map.py` | `M0, M8` | `Pending` |
| `ENV-27` | `ML_MAX_PAYLOAD_BYTES` | `524288` (`# TODO(OQ-4)`) | `core/config.py`, `worker/runner.py` | `tests/integration/test_worker.py` | `M0, M8` | `Pending` |
| `ENV-28` | `ML_CATALOG_TIMEOUT_SECONDS` | `5` | `core/config.py`, `ml_client/real_adapter.py` | `tests/unit/test_ml_client.py` | `M0, M6` | `M0+M6 Verified` |
| `ENV-29` | `ML_HEALTH_TIMEOUT_SECONDS` | `3` | `core/config.py`, `ml_client/real_adapter.py` | `tests/unit/test_ml_client.py` | `M0, M6` | `M0+M6 Verified` |
| `ENV-30` | `ML_CATALOG_SYNC_HOURS` | `6` | `core/config.py`, `worker/jobs.py` | `tests/integration/test_catalog.py` | `M0, M11` | `Pending` |
| `ENV-31` | `ML_CIRCUIT_BREAKER_THRESHOLD` | `5` | `core/config.py`, `worker/breaker.py` | `tests/integration/test_breaker.py` | `M0, M10` | `Pending` |
| `ENV-32` | `ML_BREAKER_COOLDOWN_SECONDS` | `30` | `core/config.py`, `worker/breaker.py` | `tests/integration/test_breaker.py` | `M0, M10` | `Pending` |
| `ENV-33` | `ML_MAX_CONCURRENT_REQUESTS` | `8` | `core/config.py`, `worker/runner.py` | `tests/concurrency/test_bulkhead.py` | `M0, M8` | `Pending` |
| `ENV-34` | `DEGRADED_MODE_MAX_AGE_HOURS` | `72` (`# TODO(OQ-8)`) | `core/config.py`, `worker/runner.py` | `tests/integration/test_breaker.py` | `M0, M10` | `Pending` |
| `ENV-35` | `ALLOW_SYNC_WAIT` | `false` | `core/config.py`, `api/v1/analysis.py` | `tests/integration/test_analysis.py` | `M0, M7` | `Pending` |
| `ENV-36` | `SYNC_WAIT_TIMEOUT_SECONDS` | `58` | `core/config.py`, `api/v1/analysis.py` | `tests/integration/test_analysis.py` | `M0, M7` | `Pending` |
| `ENV-37` | `WORKER_CONCURRENCY` | `4` | `core/config.py`, `worker/runner.py` | `tests/concurrency/test_worker_race.py` | `M0, M8` | `Pending` |
| `ENV-38` | `JOB_LEASE_SECONDS` | `90` | `core/config.py`, `worker/runner.py` | `tests/integration/test_worker.py` | `M0, M8` | `Pending` |
| `ENV-39` | `MAX_JOB_ATTEMPTS` | `2` | `core/config.py`, `worker/runner.py` | `tests/integration/test_worker.py` | `M0, M8` | `Pending` |
| `ENV-40` | `CORS_ALLOWED_ORIGINS` | `http://localhost:5173` | `core/config.py`, `main.py` | `tests/contract/test_cors.py` | `M0, M2` | `M2 CORS Middleware Verified` |

### 7b. Companion Runtime Settings (`7 / 7` Non-Spec Safety & Tuning Knobs — `IMPL-018`)

| ID | Variable | Fail-Safe Default | Consuming Module(s) | Test Verifying Presence & Parsing | Milestone | Status |
| :--- | :--- | :--- | :--- | :--- | :---: | :--- |
| `CMP-01` | `APP_ENV` | `production` (startup `ValueError` if `ML_PROVIDER_MODE=mock`) | `core/config.py`, `ml_client/manager.py` | `tests/unit/test_config.py`, `tests/unit/test_ml_provider_manager.py`, `tests/integration/test_catalog.py` | `M0, M6` | `M0+M6 Verified` |
| `CMP-02` | `ML_PROVIDER_MODE` | `auto` (forbidden=`mock` when `APP_ENV=production`) | `core/config.py`, `ml_client/manager.py` | `tests/unit/test_config.py`, `tests/unit/test_ml_provider_manager.py`, `tests/integration/test_catalog.py` | `M0, M6` | `M0+M6 Verified` |
| `CMP-03` | `ML_HEALTH_CHECK_INTERVAL_SECONDS` | `30` | `core/config.py`, `ml_client/manager.py`, `worker/runner.py` | `tests/unit/test_ml_provider_manager.py`, `tests/integration/test_catalog.py`, `tests/integration/test_system.py` | `M0, M6, M11` | `M0+M6 Verified (probe staleness + 2xTTL Redis snapshot); M11 /health & worker loop pending` |
| `CMP-04` | `SEM04_NUMERIC_TOLERANCE` | `0.001` (`1e-3`) | `core/config.py`, `services/verification.py` | `tests/unit/test_sem_rules.py` | `M0, M9` | `Pending` |
| `CMP-05` | `TRUSTED_PROXY_CIDRS` | `""` | `core/config.py`, `core/rate_limit.py` | `tests/unit/test_rate_limit.py`, `tests/integration/test_security.py` | `M0, M2, M12` | `M2 Unit Verified; M12 security integration pending` |
| `CMP-06` | `REDIS_FAIL_CLOSED` | `true` | `core/config.py`, `core/rate_limit.py`, `api/deps.py` | `tests/integration/test_rate_limit.py` | `M0, M2` | `M2 Verified (unit 503 fail-closed + live Redis 7-alpine lifespan)` |
| `CMP-07` | `ML_DATASET_OWNER_ROLE` | `""` | `core/config.py`, `db/migrations/versions/001_initial_schema.py` | `tests/migration/test_schema_and_ml_reader.py` | `M0, M1` | `M1 Verified` |

## 8. Open Questions (`19 / 19` — `Blueprint §13`)

| ID | Topic | Configurable / Placeholder Target Module | Milestone | Status |
| :--- | :--- | :--- | :---: | :--- |
| `OQ-1` | External ML latency SLA (`X` s) & Stage budget | `core/config.py`, `services/health.py`, `metrics.py` | `M0, M11` | `Pending` |
| `OQ-2` | Free-text prompt-injection risk (`farm_name`, `crop_name_raw`) | `schemas/common.py` `sanitize_free_text` helper `# TODO(OQ-2)` | `M5` | `M5 Mitigated (# TODO(OQ-2) control-char strip helper + integration test)` |
| `OQ-3` | `SEM-04` numeric tolerance (`±TBD`) | `core/config.py` (`SEM04_NUMERIC_TOLERANCE`) + `services/verification.py` | `M9` | `Pending` |
| `OQ-4` | `ML_MAX_PAYLOAD_BYTES` exact ceiling | `core/config.py` + `worker/runner.py` history trimmer | `M8` | `Pending` |
| `OQ-5` | Legacy `ADR-0` doc location/date | Docs only (`DESIGN_ISSUES.md`) | `M13` | `Pending` |
| `OQ-6` | 15 Golden scenarios & Agronomy pass gate | `backend/tests/golden/` harness + `# TODO(OQ-6)` marker | `M12` | `Pending` |
| `OQ-7` | Backups, RPO/RTO & `input_snapshot_gz` archival TTL | `docs/impl/RUNBOOK.md` + optional reaper hook `# TODO(OQ-7)` | `M11, M13` | `Pending` |
| `OQ-8` | `DEGRADED_MODE_MAX_AGE_HOURS` & `Deprecation`/`Sunset` duration | `core/config.py` + middleware hook `# TODO(OQ-8)` | `M2, M10` | `M2 Middleware Hook Verified; M10 replay pending` |
| `OQ-9` | Exact Guelma regional & demo parcel coords | `db/seed.py` `# TODO(OQ-9)` | `M1` | `M1 Placeholder Added` |
| `OQ-10` | Protected/greenhouse `INPUT-03` override | `services/validation.py` `# TODO(OQ-10)` | `M7` | `Pending` |
| `OQ-11` | Strategy tie-breaking & `priority_fit` spread | Delegated to External ML; `SEM-01` checks structural order | `M9` | `Pending` |
| `OQ-D1` | `Schema: dataset` tables/columns/units | `db/migrations/versions/001_initial_schema.py` empty `dataset` schema + `ALTER DEFAULT PRIVILEGES` | `M1` | `M1 Schema Isolated` |
| `OQ-D2` | Spatial & temporal dataset coverage bounds | `public.dataset_registry` metadata (`db/seed.py`) | `M1` | `M1 Registry Seeded` |
| `OQ-D3` | Dataset rollout / zero-downtime swap | `uq_dataset_registry_single_active` + `repositories/dataset.py` + per-request pinning | `M6, M7` | `M6 Verified (require_active_dataset + get_dataset_by_version + 503); M7 POST /analysis pinning pending` |
| `OQ-D4` | `ml_reader` statement timeout & conn limit | `ML_DB_STATEMENT_TIMEOUT_MS`, `ML_DB_CONNECTION_LIMIT` in Alembic | `M1` | `M1 Configurable` |
| `OQ-D5` | Cross-verifying `"data_source": "dataset"` evidence | `services/verification.py` (`SEM-04` structural + period check) | `M9` | `Pending` |
| `OQ-D6` | Minimum parcel history richness for `422 INSUFFICIENT_DATA` | ML error pass-through (`worker/runner.py`) + minItems=1 | `M5, M8` | `M5 Verified (minItems=1 schema); M8 ML 422 pass-through pending` |
| `OQ-D7` | Authoritative Guelma administrative shapefile | Placeholder 10-vertex Polygon in `db/seed.py` (`# TODO(OQ-D7)`) | `M1` | `M1 Placeholder Added` |
| `OQ-D8` | Unstudied demo parcel field measurements | Optional frontend `is_unverified_demo_parcel=true` -> `DEMO_PARCEL_UNVERIFIED` (`default_parcel_*` removed per `IMPL-023`) | `M1, M3, M5` | `M1+M3+M5 Verified (IMPL-023 + field DEMO_PARCEL_UNVERIFIED notice)` |
