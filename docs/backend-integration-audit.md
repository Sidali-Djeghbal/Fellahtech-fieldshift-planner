# FieldShift Planner — Backend Integration & Contract Audit

**Inspection Date:** 2026-11-15  
**Backend Repository:** `git@github.com:Sidali-Djeghbal/fieldshift-planner.git` (`https://github.com/Sidali-Djeghbal/fieldshift-planner.git`)  
**Backend Branch & Commit:** `backend-system` @ `4f17c19715a638aef2c0da2c450dde1805b220e6` (`4f17c19`)  
**Local Backend Reference Path:** `/home/void/Project/fieldshift-backend-reference` (read-only clone)  
**Android Repository:** `/home/void/Project/hackthon` (`feat/analysis-workflow` @ `881410c`)

---

## 1. Backend Architecture & Relevant Modules

The backend is a FastAPI + SQLAlchemy (async PostgreSQL/PostGIS) + Redis + Pydantic v2 service rooted at `/api/v1` (`backend/app/api/v1/__init__.py`):

- **Application Factory & Middleware:** `backend/app/main.py` (`create_app`, `RequestIdMiddleware`, `DeprecationHeadersMiddleware`).
- **Auth & Rate Limiting Dependencies:** `backend/app/api/deps.py` (`Principal`, `authenticate_bearer_user`, `authenticate_guest_session`, `require_actor_no_rate_limit`, `enforce_crud_rate_limit`, `enforce_poll_rate_limit`).
- **Routers (`backend/app/api/v1/`):** `auth.py`, `demo.py`, `farms.py`, `fields.py`, `analysis.py`, `catalog.py`, `system.py`.
- **Schemas (`backend/app/schemas/`):** `common.py`, `auth.py`, `demo.py`, `farm.py`, `field.py`, `analysis.py`, `catalog.py`, `system.py`.
- **Services & Repositories:** `backend/app/services/analysis.py`, `backend/app/repositories/analysis.py`, `backend/app/core/errors.py`, `backend/app/core/pagination.py`.
- **ML Fixtures & Integration Tests:** `backend/app/ml_client/fixtures/fixture_9_3_output.json`, `backend/tests/integration/test_analysis.py`.

---

## 2. Actual Endpoint Inventory (`/api/v1`)

| Method & Path | Handler (`backend/app/api/v1/`) | Auth Dependency | Rate Limit | Android Status |
|---|---|---|---|---|
| `POST /api/v1/auth/guest` | `auth.py:start_guest_session` | Public | IP guest-create | Implemented |
| `POST /api/v1/auth/register` | `auth.py:register_user` | Public | None | Implemented |
| `POST /api/v1/auth/login` | `auth.py:login_user` | Public | None | Implemented |
| `POST /api/v1/auth/refresh` | `auth.py:refresh_token` | Public (refresh token body) | None | Implemented |
| `POST /api/v1/auth/logout` | `auth.py:logout_user` | `BearerPrincipalDep` | CRUD | Implemented |
| `GET /api/v1/auth/me` | `auth.py:get_me` | `BearerPrincipalDep` | CRUD | Implemented |
| `DELETE /api/v1/auth/me` | `auth.py:delete_me` | `BearerPrincipalDep` | CRUD | Not in Android |
| `GET /api/v1/auth/me/export` | `auth.py:export_me_data` | `BearerPrincipalDep` | CRUD | Not in Android |
| `POST /api/v1/auth/claim-guest` | `auth.py:claim_guest_session` | `Bearer` + `X-Guest-Token` | CRUD | Not in Android |
| `GET /api/v1/demo/locations` | `demo.py:list_demo_locations` | Public | None | Implemented |
| `GET /api/v1/demo/locations/{id}/boundary` | `demo.py:get_demo_location_boundary` | Public | None | Not in Android |
| `GET /api/v1/demo/session` | `demo.py:get_demo_session` | `GuestPrincipalDep` | CRUD | Implemented |
| `DELETE /api/v1/demo/session` | `demo.py:delete_guest_session` | `GuestPrincipalDep` | CRUD | Implemented |
| `GET/POST /api/v1/farms` | `farms.py:list_farms`, `create_farm` | `ActorPrincipalDep` | CRUD | Implemented |
| `GET/PUT/PATCH/DELETE /api/v1/farms/{farm_id}` | `farms.py:get_farm`, `replace_farm`, `patch_farm`, `delete_farm` | `ActorPrincipalDep` | CRUD | Implemented |
| `GET/POST /api/v1/farms/{farm_id}/fields` | `fields.py:list_fields`, `create_field` | `ActorPrincipalDep` | CRUD | Implemented |
| `GET/PUT/PATCH/DELETE /api/v1/farms/{farm_id}/fields/{field_id}` | `fields.py:get_field`, `replace_field`, `patch_field`, `delete_field` | `ActorPrincipalDep` | CRUD | Implemented |
| `POST /api/v1/analysis` | `analysis.py:submit_analysis` | `ActorNoRateLimitDep` | Service quota/RL | Implemented |
| `GET /api/v1/analysis/requests/{request_id}` | `analysis.py:poll_analysis_request` | `ActorNoRateLimitDep` | Dedicated 120/min | Implemented |
| `POST /api/v1/analysis/requests/{request_id}/cancel` | `analysis.py:cancel_analysis_request` | `ActorPrincipalDep` | CRUD | Implemented |
| `GET /api/v1/analysis/{analysis_id}` | `analysis.py:get_analysis_result` | `ActorPrincipalDep` | CRUD | Implemented |
| `PATCH /api/v1/analysis/{analysis_id}/selection` | `analysis.py:update_analysis_selection` | `ActorPrincipalDep` | CRUD | Task A Done |
| `GET /api/v1/farms/{farm_id}/analyses` | `analysis.py:list_farm_analyses` | `ActorPrincipalDep` | CRUD | Repo Done; UI Phase 6 |
| `GET /api/v1/catalog` | `catalog.py:get_catalog` | `ActorPrincipalDep` | CRUD | Implemented |
| `GET /api/v1/health`, `/metrics` | `system.py:get_health`, `get_metrics` | Public / Internal ACL | None | Not in Android |

---

## 3. Authentication & Error Contract

- **Actor Resolution (`backend/app/api/deps.py:219-229`, `require_actor_no_rate_limit`):**
  - If `Authorization` header is present, validates `Bearer <jwt>` via `authenticate_bearer_user()` and ignores `X-Guest-Token`.
  - Otherwise validates `X-Guest-Token` via `authenticate_guest_session()` against SHA-256 hashed active `public.guest_sessions`.
  - Matches Android `AuthInterceptor` (`app/src/main/java/com/example/myapplication/core/network/AuthInterceptor.kt:54-65`).
- **Error Envelope (`backend/app/core/errors.py:17-61, 102-142`):**
  - Returns `{"error": {"code": "<ErrorCode>", "message": "...", "details": [...], "request_id": "..."}}` with `X-Request-Id` header.
  - Matches Android `ApiErrorParser`.

---

## 4. Actual Request/Response Examples Verified in Backend Code & Tests

### A. Strategy Selection (`PATCH /api/v1/analysis/{analysis_id}/selection`)
From `backend/tests/integration/test_analysis.py:850-860`:
```json
// Request
{
  "field_id": "F1",
  "strategy_id": "S2_water_resilient",
  "selection_status": "selected"
}

// 200 Response (SelectionResponse in backend/app/schemas/analysis.py:246-254)
{
  "analysis_id": "analysis_aaa111bbb222",
  "field_id": "F1",
  "strategy_id": "S2_water_resilient",
  "selection_status": "selected"
}
```
Invalid `field_id` or `strategy_id` raises `400 INVALID_INPUT` (`_assert_strategy_in_result` in `backend/app/services/analysis.py:1051-1084`). Unknown/unowned `analysis_id` raises `404 NOT_FOUND` (`backend/app/services/analysis.py:1104-1108`).

### B. `GET /api/v1/analysis/{analysis_id}` After Selection Merge
From `backend/app/ml_client/fixtures/fixture_9_3_output.json:36-46` + `backend/tests/integration/test_analysis.py:886-899`:
- `S2_water_resilient` (superseded by `S3_income_diversified`): every item in `S2_water_resilient.seasons[]` has `"selection_status": "suggested"`.
- `S3_income_diversified` (selected): every item in `S3_income_diversified.seasons[]` has `"selection_status": "selected"`.
- Neither `S2_water_resilient` nor `S3_income_diversified` has a top-level `strategy.selection_status` key.

### C. Farm History (`GET /api/v1/farms/{farm_id}/analyses`)
From `backend/app/schemas/analysis.py:257-275`, `backend/app/core/pagination.py:16-34`, and `backend/tests/integration/test_analysis.py:926-935`:
- Query params: `limit` (`1..100`, default `20`), `cursor` (URL-safe Base64 keyset over `(created_at, request_id)`), `status` (`pending|running|ok|partial|failed|cancelled`).
- Returns `FarmAnalysesPage` (`items`, `next_cursor`, `has_more`).

---

## 5. Android / Backend Compatibility Table

| Area | Status | Evidence |
|---|---|---|
| Base path `/api/v1` & `X-Request-Id` | **Compatible** | `backend/app/api/v1/__init__.py:15`, `main.py:67-104` |
| Auth (`Bearer` / `X-Guest-Token`) & Refresh | **Compatible** | `backend/app/api/deps.py:91-229` vs Android `AuthInterceptor` |
| Error Envelope & 19 `ErrorCode`s | **Compatible** | `backend/app/core/errors.py:17-142` vs Android `ApiErrorParser` |
| Farms CRUD & Pagination | **Compatible** | `backend/app/api/v1/farms.py`, `schemas/farm.py` |
| Fields CRUD, GeoJSON & `crop_history` | **Compatible** | `backend/app/api/v1/fields.py`, `schemas/field.py` |
| Analysis Submit (`Idempotency-Key`, `priorities`) | **Compatible** | `schemas/analysis.py:123-159`; Android `@EncodeDefault` ensures required `target_crop_ids`/`excluded_crop_ids`/`equipment_constraints` |
| Analysis Polling (`Retry-After`, `429`, `degraded_mode`) | **Compatible** | `analysis.py:103-128`, `schemas/analysis.py:174-224` |
| Analysis Cancellation (`200`, `409`) | **Compatible** | `analysis.py:130-149`, `test_analysis.py:772-785` |
| `PATCH /analysis/{analysis_id}/selection` | **Compatible** | `analysis.py:170-189`, `schemas/analysis.py:236-255` vs Task A `881410c` |
| `GET /analysis/{analysis_id}` Selection Read Merge | **Mismatch / Gap in Android UI Model** | Backend merges `selection_status` **only** into `strategy.seasons[*].selection_status` (`services/analysis.py:141-172`), whereas Android `Strategy` (`AnalysisModels.kt:195-204`) and `AnalysisResultScreen` do not yet surface strategy selection state |
| `GET /farms/{farm_id}/analyses` History | **Partial (Backend/Repo Ready, UI Missing)** | `AnalysisApiService.listFarmAnalyses` & DTOs match `FarmAnalysesPage`; UI/ViewModel scheduled for Phase 6 |
| `GET /catalog` Pagination & `?lang` | **Compatible** | `backend/app/api/v1/catalog.py`, `schemas/catalog.py` |

---

## 6. Discrepancies Between Implementation, OpenAPI, and ML Schema

1. **`equipment_constraints` nullability:** `docs/openapi-v3.2.yaml:1725` marks `equipment_constraints` as required non-null array, whereas `backend/app/schemas/analysis.py:136-144` allows `None` and normalizes it to `[]` (`IMPL-022`). Android always sends `[]`, which satisfies both.
2. **Read-time selection merge target:** `docs/openapi-v3.2.yaml:813` states *"read-time merged user selections"* without specifying the JSON path; `docs/ml-contract-v5.0.json` defines `selection_status` on `SeasonPlan` (`#/$defs/SeasonPlan`) and not on `Strategy`. Backend implementation (`backend/app/services/analysis.py:141-172`) confirms the merge writes **only** to `field_plans[].strategies[].seasons[].selection_status`.
3. **Unimplemented backend endpoints in Android:** `POST /auth/claim-guest`, `GET /auth/me/export`, `DELETE /auth/me`, `GET /demo/locations/{id}/boundary` exist in backend and OpenAPI, but are outside Phases 1–6 Android scope.

---

## 7. Definitive Findings About Strategy Selection

Verified directly from `backend/app/services/analysis.py:141-172, 1051-1130`, `backend/app/repositories/analysis.py:316-365`, and `backend/tests/integration/test_analysis.py:849-917`:

1. **Where `selection_status` appears on `GET`:**
   - `merge_selections_into_result()` writes `season["selection_status"] = override` on every `season` inside `field_plans[].strategies[].seasons[]`.
   - It does **not** add `selection_status` to `Strategy` (`field_plans[].strategies[]`).
2. **Whether all strategies receive a status:**
   - Every `SeasonPlan` in `result_json` already has `"selection_status"` (initially `"suggested"` in `fixture_9_3_output.json`). Strategies without a row in `analysis_selections` retain their original `"suggested"` status on all seasons.
3. **Switching `selected` to another strategy on the same field:**
   - `upsert_analysis_selection()` (`repositories/analysis.py:336-344`) **deletes** any existing `AnalysisSelection` row for `(analysis_id, field_id)` with `selection_status == "selected"` and `strategy_id != payload.strategy_id` before upserting the new `"selected"` row.
   - Consequently, the previously selected strategy automatically reverts to `"suggested"` on the next `GET` (verified in `test_analysis.py:862-899`).
4. **Rejected strategies:**
   - `merge_selections_into_result()` never removes strategies; rejected strategies remain in `field_plans[].strategies[]` with `seasons[].selection_status == "rejected"`.
5. **Immediate consistency:**
   - `update_analysis_selection()` acquires a `FOR UPDATE` row lock on `AnalysisResult`, upserts `analysis_selections`, and calls `await db.commit()` before returning `200`. Subsequent `GET /analysis/{analysis_id}` reads PostgreSQL directly and reflects the change immediately.
6. **`result_json` immutability:**
   - `merge_selections_into_result()` operates on `copy.deepcopy(dict(result_json))`; `analysis_results.result_json` in PostgreSQL is never mutated.

---

## 8. Recommended Android Changes (for Phase 6 Task B & C)

1. **Task B (Strategy Selection UI & ViewModel):**
   - Derive each strategy's effective display selection state in `AnalysisResultViewModel` / UI from `strategy.seasons`:
     - If `strategy.seasons.any { it.selectionStatus == "selected" }` -> `SELECTED`
     - Else if `strategy.seasons.any { it.selectionStatus == "rejected" }` -> `REJECTED`
     - Else -> `SUGGESTED`
   - Keep `SeasonPlan.selectionStatus: String` intact (do not lose season-level data).
   - On `PATCH /analysis/{analysis_id}/selection` `200` success, update UI state immediately (updating that strategy's seasons' `selectionStatus` to `"selected"` or `"rejected"`, and if `"selected"`, resetting any previously `"selected"` strategy on the same `field_id` back to `"suggested"`), or re-fetch `GET /analysis/{analysis_id}` to match the exact backend read-time merge.
   - Guard concurrent mutations per field (`mutatingFieldIds`) and surface `400`/`404`/network errors without discarding valid results.
2. **Task C (Analysis History):**
   - Wire `AnalysisHistoryViewModel` + `AnalysisHistoryScreen` to `AnalysisRepository.listFarmAnalyses(farmId, limit = 20, cursor, status)` using `next_cursor` and `has_more`, opening completed analyses (`analysisId != null`) in `AnalysisResultScreen` and active jobs (`pending`/`running`) in `AnalysisProgressScreen`.

---

## 9. Remaining Questions for Backend Developer
- None blocking Phase 6 Task B or Task C. All strategy selection and history pagination behaviors are verified in backend code and integration tests.
