# FieldShift Planner Backend — Open Questions & Future Backlog (`BACKLOG.md`)

Tracks all **`19` Open Questions (`OQ-1..11` & `OQ-D1..D8`)** from [`System Architecture Blueprint §13`](../../SYSTEM%20DESGIN/SYSTEM%20DESGIN/System%20Architecture%20Blueprint.md), all in-code `# TODO(OQ-*)` markers, and deferred operational/external-team cutover items. Zero domain thresholds or unverified spatial/ML values were fabricated; every unresolved threshold is configurable via environment variables or guarded by an explicit marker.

---

## 1. Consolidated Open Questions & Cutover Backlog (`19 / 19`)

| ID | Topic | Owner (`Blueprint §13`) | Current Backend State & Default | Cutover / Future Action Required |
| :--- | :--- | :--- | :--- | :--- |
| **`OQ-1`** | External ML latency SLA (`X` s) & Stage 1/2 budget | External ML Lead | Hard HTTP timeout `ML_TIMEOUT_SECONDS=60`; `GET /api/v1/metrics` exports `ml_request_duration_seconds`; `services/health.py` marks `# TODO(OQ-1)`. | Set committed `p95`/`p99` budget once ML benchmarks complete and enforce probe/Stage 1-2 SLA alert thresholds. |
| **`OQ-2`** | Free-text prompt-injection risk (`farm_name`, `crop_name_raw`) | External ML Lead | `schemas/common.py` `sanitize_free_text` strips ASCII control chars and trims inputs; tested in `tests/integration/test_security_hardening.py`. | Review whether External ML interpolates free-text fields into an LLM prompt; add stricter escaping/redaction if needed. |
| **`OQ-3`** | `SEM-04` numeric tolerance (`±TBD`) | Backend + ML Leads | `SEM04_NUMERIC_TOLERANCE=0.001` (`Settings` + `services/verification.py` line 594). | Confirm per-metric rounding/measurement tolerance with Agronomy & ML teams (e.g., pH vs yield vs organic matter). |
| **`OQ-4`** | Exact uncompressed ML payload ceiling | Backend + ML Leads | `ML_MAX_PAYLOAD_BYTES=524288` (512 KiB); `worker/runner.py` performs pre-dispatch & `413` oldest-first crop-history trim while keeping `input_snapshot_gz` immutable. | Confirm exact production byte limit with External ML server ingress configuration. |
| **`OQ-5`** | Legacy `ADR-0` document location & original date | Architecture Author | Superseded by `ADR-4`; `ADR.md` notes `"Date: TBD"`. Zero runtime impact. | Fill historical location/date if original v1 document is archived into git. |
| **`OQ-6`** | 15 Golden scenarios & Agronomy acceptance threshold | Agronomy Lead | All 15 structural/semantic scenarios (`G01`–`G15`) pass live `POST /analysis` + `WorkerRunner` in `tests/golden/test_golden_harness.py`. | Agronomy Lead to sign off qualitative agronomic expectations & set concrete `GOLDEN_OQ6_PASS_THRESHOLD_PERCENT`. |
| **`OQ-7`** | Backups, RPO/RTO & `input_snapshot_gz` archival TTL | Infra / Security Lead | Immediate hard delete on `DELETE /auth/me` & `DELETE /demo/session`; worker reaper runs periodically with `# TODO(OQ-7)` archival hook (`worker/runner.py:1115`). | Configure automated `pg_dump` + WAL archiving/PITR schedules per `RUNBOOK.md` and wire configurable archival/pruning TTL for aged `input_snapshot_gz` blobs. |
| **`OQ-8`** | `DEGRADED_MODE_MAX_AGE_HOURS` & `ADR-7` `Deprecation`/`Sunset` window | Backend Lead / Product Owner | `DEGRADED_MODE_MAX_AGE_HOURS=72` verified in worker/API replay; `DeprecationHeadersMiddleware` ASGI hook wired in `app/main.py:29-40`. | Confirm final `last_good_replay` max age and populate `route_headers` once `v1` deprecation dates are scheduled. |
| **`OQ-9`** | Exact Wilaya of Guelma boundary & surveyed demo coordinates | Geospatial / Agronomy Team | `demo_locations` seeds placeholder 10-vertex Guelma `MultiPolygon` (`db/seed.py`). `default_parcel_*` removed per `IMPL-023`. | Replace placeholder polygon with official surveyed Guelma boundary coordinates (`OQ-D7`). |
| **`OQ-10`** | Protected / greenhouse `INPUT-03` override | Agronomy Lead | Strict `INPUT-03` hemisphere × `start_season` × `planting_month` matrix enforced in `services/analysis_input.py:178`; marker `# TODO(OQ-10)` placed at check site. | Define greenhouse/protected cultivation flag & override rules if irrigated greenhouses bypass seasonal planting windows. |
| **`OQ-11`** | Strategy tie-breaking, `priority_fit` spread & crop taxonomy sync | ML + Agronomy Leads | Delegated to External ML; `SEM-01` checks structural ranking/ordering; `services/verification.py` marks enum/reason-code coordination (`lines 488, 733`). | Finalize deterministic tie-breaking, minimum fit score delta, and cross-team crop-role/reason-code translation sync. |
| **`OQ-D1`** | `Schema: dataset` tables, columns, units & cadence | ML Team | Alembic `001` creates isolated `Schema: dataset` + `ALTER DEFAULT PRIVILEGES ... SELECT` to `ml_reader` (and optional `ML_DATASET_OWNER_ROLE`). | ML/Data team populates `dataset.*` tables via `ML_DATASET_OWNER_ROLE` without sharing `public` credentials. |
| **`OQ-D2`** | Spatial & temporal dataset coverage bounds | ML + Data Owners | Initial `public.dataset_registry` active row seeded (`2025.01` -> upgraded/pinned in queries) in `db/seed.py`. | Update `dataset_registry.metadata` bbox/temporal coverage when production EO/climate layers are loaded. |
| **`OQ-D3`** | Dataset versioning & zero-downtime rollout | ML + Backend Leads | `uq_dataset_registry_single_active`, `POST /analysis` version pinning, `GET /catalog` N/N-1 retention, and `503 DATASET_UNAVAILABLE` fail-closed checks implemented. | Document/automate promotion script inserting new `dataset_registry` row and flipping `is_active` inside one transaction. |
| **`OQ-D4`** | Production `ml_reader` SQL timeout & connection cap | Backend / DBA Lead | Configured via `ML_DB_STATEMENT_TIMEOUT_MS=5000` and `ML_DB_CONNECTION_LIMIT=10` in Alembic `001` (`line 406`) and `Settings` (`config.py:83`). | Tune based on production `dataset.*` spatial join latency and Postgres `max_connections`. |
| **`OQ-D5`** | Cross-verifying `"data_source": "dataset"` evidence | Backend + ML Leads | `SEM-04` verifies structural presence, `"derived": true` provenance, and non-fabrication (`services/verification.py:595`). | Agree on `dataset` `period` interval format and optional backend lookup/attestation against `Schema: dataset`. |
| **`OQ-D6`** | Minimum parcel history richness for `422 INSUFFICIENT_DATA` | ML + Agronomy Leads | `minItems=1` on API `crop_history`; worker handles `422 INSUFFICIENT_DATA` as non-retryable and non-refundable for guest quarters. | Align UI guidance with ML team's minimum seasonal history requirement. |
| **`OQ-D7`** | Official Guelma administrative shapefile | Geospatial Owner | `db/seed.py` loads placeholder MultiPolygon bbox `[7.00, 36.05, 7.90, 36.65]`. | Supply GeoJSON/shapefile extraction migration updating `public.demo_locations.boundary` for `"guelma"`. |
| **`OQ-D8`** | Unstudied demo parcel soil/history handling | Project / Agronomy Team | `IMPL-023` removed backend `default_parcel_*`; frontend may pass `is_unverified_demo_parcel=true` to attach `DEMO_PARCEL_UNVERIFIED` notice. | Confirm UX disclaimer text in frontend and survey real soil samples for official presets. |

---

## 2. Verified `# TODO(OQ-*)` Code & Config Marker Index

Every `# TODO(OQ-*)` marker present in the repository at M13 completion:

| Marker | File & Line | Purpose |
| :--- | :--- | :--- |
| `# TODO(OQ-1)` | [`backend/app/api/v1/system.py:44`](../../backend/app/api/v1/system.py#L44) | Prometheus `/metrics` SLA budget tracking |
| `# TODO(OQ-1)` | [`backend/app/services/health.py:94`](../../backend/app/services/health.py#L94) | ML health probe SLA budget enforcement |
| `# TODO(OQ-2)` | [`backend/app/schemas/common.py:19`](../../backend/app/schemas/common.py#L19), [`:24`](../../backend/app/schemas/common.py#L24), [`backend/tests/integration/test_security_hardening.py:545`](../../backend/tests/integration/test_security_hardening.py#L545) | Free-text sanitization review beyond control-char stripping & trimming |
| `# TODO(OQ-3)` | [`backend/app/core/config.py:136`](../../backend/app/core/config.py#L136), [`backend/app/services/verification.py:594`](../../backend/app/services/verification.py#L594), [`.env.example:69`](../../.env.example#L69) | Numeric tolerance (`SEM04_NUMERIC_TOLERANCE`) for `SEM-04` farmer input comparison |
| `# TODO(OQ-4)` | [`backend/app/core/config.py:111`](../../backend/app/core/config.py#L111), [`.env.example:41`](../../.env.example#L41) | Uncompressed payload size ceiling (`ML_MAX_PAYLOAD_BYTES`) |
| `# TODO(OQ-6)` | [`backend/tests/golden/test_golden_harness.py:1`](../../backend/tests/golden/test_golden_harness.py#L1), [`:19`](../../backend/tests/golden/test_golden_harness.py#L19), [`:186`](../../backend/tests/golden/test_golden_harness.py#L186) | Concrete Agronomy pass-rate threshold (`GOLDEN_OQ6_PASS_THRESHOLD_PERCENT`) & scenario sign-off |
| `# TODO(OQ-7)` | [`backend/app/worker/runner.py:1115`](../../backend/app/worker/runner.py#L1115) | Configurable `input_snapshot_gz` archival TTL per RPO policy |
| `# TODO(OQ-8)` | [`backend/app/core/config.py:121`](../../backend/app/core/config.py#L121), [`backend/app/main.py:30`](../../backend/app/main.py#L30), [`:39`](../../backend/app/main.py#L39), [`.env.example:51`](../../.env.example#L51) | Degraded replay max age & `ADR-7` route deprecation/sunset schedule |
| `# TODO(OQ-9)` | [`backend/app/db/seed.py:11`](../../backend/app/db/seed.py#L11) | Official surveyed Wilaya of Guelma coordinates |
| `# TODO(OQ-10)` | [`backend/app/services/analysis_input.py:178`](../../backend/app/services/analysis_input.py#L178) | Protected / greenhouse cultivation override for `INPUT-03` |
| `# TODO(OQ-11)` | [`backend/app/services/verification.py:488`](../../backend/app/services/verification.py#L488), [`:733`](../../backend/app/services/verification.py#L733) | Shared crop-role enum & reason-code coordination with ML/Frontend |
| `# TODO(OQ-D1)` | [`backend/app/db/migrations/versions/001_initial_schema.py:376`](../../backend/app/db/migrations/versions/001_initial_schema.py#L376), [`backend/app/db/seed.py:37`](../../backend/app/db/seed.py#L37) | ML team schema definition & ETL population of `Schema: dataset` |
| `# TODO(OQ-D4)` | [`backend/app/core/config.py:83`](../../backend/app/core/config.py#L83), [`backend/app/db/migrations/versions/001_initial_schema.py:406`](../../backend/app/db/migrations/versions/001_initial_schema.py#L406), [`.env.example:13`](../../.env.example#L13) | Production `ml_reader` statement timeout & connection limit tuning |
| `# TODO(OQ-D5)` | [`backend/app/services/verification.py:595`](../../backend/app/services/verification.py#L595) | `dataset` evidence `period` interval alignment with ML |
| `# TODO(OQ-D7)` | [`backend/app/db/seed.py:9`](../../backend/app/db/seed.py#L9) | Official shapefile replacement for placeholder Guelma MultiPolygon |

---

## 3. Deferred Post-MVP Enhancements & Documentation Hygiene

- **Spec Diagram Alignment (`DI-05`):** Frozen specification documents (`Blueprint §4 W1/W3`, `Visual I/O §1/§7`) contain Mermaid notes predating `IMPL-013` that describe worker-side `FarmAnalysisInput` gzip construction; implementation intentionally assembles and stores `input_snapshot_gz` synchronously at `POST /api/v1/analysis` admission because `analysis_requests` has no columns for ephemeral planning/priority inputs.
- **Standalone Production Infrastructure:** Adding a TLS-terminating reverse proxy (`Caddy`/`Nginx`/`Traefik`) with `TRUSTED_PROXY_CIDRS` configured, ACL restriction on `GET /api/v1/metrics` (`x-internal-only: true`), and external Prometheus/Alertmanager scraping rules (`ml_breaker_state == 1`, `redis_errors_total > 0`, `worker_active_leases`).
- **Automated Archival & Backups (`OQ-7`):** Automated off-host `pg_dump` / WAL-G / pgBackRest cron/object-storage shipping and optional S3 cold archival for aged `analysis_requests.input_snapshot_gz` bytea blobs.
