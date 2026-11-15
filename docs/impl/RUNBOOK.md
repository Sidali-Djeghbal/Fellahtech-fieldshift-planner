# FieldShift Planner Backend — Operations & Deployment Runbook (`RUNBOOK.md`)

Operational procedures for running, verifying, rotating secrets on, monitoring, and backing up the FieldShift Planner backend stack (`PostGIS`, `Redis`, `migrate`, `api`, `worker`, and optional `--profile dev` `mock-ml`).

---

## 1. Service Topology & Profiles

Defined in [`docker-compose.yml`](../../docker-compose.yml) and [`backend/Dockerfile`](../../backend/Dockerfile):

| Service | Image / Build | Port (Localhost) | Role & Healthcheck |
| :--- | :--- | :--- | :--- |
| **`db`** | `postgis/postgis:16-3.4` | `127.0.0.1:5432` | Primary PostgreSQL 16 + PostGIS 3.4 database (`pgdata` volume); healthcheck `pg_isready -U fieldshift -d fieldshift` |
| **`redis`** | `redis:7-alpine` | `127.0.0.1:6379` | Sliding-window Lua rate limiter, guest quarter cache mirror, `ml:provider_status`, `worker:heartbeat:*`; healthcheck `redis-cli ping` |
| **`migrate`** | `./backend` | — | One-shot Alembic runner (`alembic upgrade head`), exits `0` before `api` and `worker` start |
| **`api`** | `./backend` | `127.0.0.1:8000` | FastAPI + Uvicorn (`app.main:app`); depends on `migrate` (`service_completed_successfully`) and `redis` (`service_healthy`); healthcheck `curl -fsS http://localhost:8000/api/v1/health?check=ready` |
| **`worker`** | `./backend` | — | Asyncio job runner (`python -m app.worker.runner`); `SKIP LOCKED` claims, advisory bulkhead `1001..1008`, breaker & catalog sync; healthcheck `python -m app.worker.healthcheck` |
| **`mock-ml`** | `./backend` *(profile `dev`/`test`)* | `127.0.0.1:8090` | Standalone ASGI mock External ML server (`app.ml_client.mock_server:app`); healthcheck `curl -fsS -H "X-ML-API-Key: $${ML_SERVICE_API_KEY:-}" http://localhost:8090/v1/health \|\| exit 1` |

---

## 2. Environment Setup & Production Guardrails

1. Copy [`.env.example`](../../.env.example) to `.env` (gitignored) and replace every secret (`DB_PASSWORD`, `ML_READER_PASSWORD`, `JWT_SECRET_KEY`, `ML_SERVICE_API_KEY`). Ensure `DATABASE_URL` and `ML_DATASET_DB_URL` match `DB_PASSWORD` / `ML_READER_PASSWORD`.
2. **Production Defaults (`IMPL-018`):** `.env.example` defaults to `APP_ENV=production`, `ML_PROVIDER_MODE=auto`, and `REDIS_FAIL_CLOSED=true`. Starting the backend with `APP_ENV=production` fails fast with `ValueError` if `ML_PROVIDER_MODE=mock` or if `ML_SERVICE_URL` does not use `https://`.
3. **Local Wire Testing (`--profile dev`):** Set `APP_ENV=development` and `ML_SERVICE_URL=http://mock-ml:8090` in local `.env` so `api` and `worker` communicate with the `mock-ml` container over the Compose network.
4. **Reverse Proxy & Network ACLs:**
   - Terminate TLS (`https://`) at a reverse proxy (`Caddy` / `Nginx` / `Traefik`).
   - Set `TRUSTED_PROXY_CIDRS` to your proxy CIDR(s) so `extract_client_ip` safely unwraps rightmost proxy hops from `X-Forwarded-For` without honoring spoofed client headers.
   - Restrict `GET /api/v1/metrics` (`x-internal-only: true`) to internal Prometheus scrapers at the ingress/proxy layer.
   - Configure `CORS_ALLOWED_ORIGINS` (comma-separated frontend origins, default `http://localhost:5173`).

---

## 3. Clean Bring-Up & Migrations (Windows + WSL2 Docker)

### Full Orchestrated Stack (with `mock-ml` dev profile)

```powershell
# From repo root in PowerShell
wsl -d Ubuntu -- bash -lc "cd /mnt/c/Users/SURFUCE/Pictures/fieldshift-planner && docker compose --profile dev config"
wsl -d Ubuntu -- bash -lc "cd /mnt/c/Users/SURFUCE/Pictures/fieldshift-planner && docker compose --profile dev down -v"
wsl -d Ubuntu -- bash -lc "cd /mnt/c/Users/SURFUCE/Pictures/fieldshift-planner && docker compose --profile dev up -d --build"
wsl -d Ubuntu -- bash -lc "cd /mnt/c/Users/SURFUCE/Pictures/fieldshift-planner && docker compose --profile dev ps"
```

Verify container health directly:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/api/v1/health?check=ready"
wsl -d Ubuntu -- bash -lc "cd /mnt/c/Users/SURFUCE/Pictures/fieldshift-planner && docker compose exec -T worker python -m app.worker.healthcheck"
```

### Infrastructure-Only Loop (`db` + `redis` for Local `.venv` Tests)

```powershell
wsl -d Ubuntu -- bash -lc "cd /mnt/c/Users/SURFUCE/Pictures/fieldshift-planner && docker compose up -d db redis"
cd backend
.\.venv\Scripts\alembic.exe current
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\alembic.exe check
```

### Dataset Schema & `ml_reader` Verification (`Schema: dataset` / `OQ-D1`..`D4`)

Alembic `001_initial_schema.py` creates isolated `Schema: dataset`, role `ml_reader` (using `ML_READER_PASSWORD`, timeout `ML_DB_STATEMENT_TIMEOUT_MS`, cap `ML_DB_CONNECTION_LIMIT`), grants read-only `SELECT` on `dataset.*`, and optionally configures `ALTER DEFAULT PRIVILEGES FOR ROLE <ML_DATASET_OWNER_ROLE>` when `ML_DATASET_OWNER_ROLE` is non-empty. `ml_reader` has zero privileges on `public.*` user/analysis tables.

To check active datasets (`public.dataset_registry`):

```powershell
wsl -d Ubuntu -- bash -lc "cd /mnt/c/Users/SURFUCE/Pictures/fieldshift-planner && docker compose exec -T db psql -U fieldshift -d fieldshift -c 'SELECT id, version, is_active, created_at FROM public.dataset_registry ORDER BY id DESC;'"
```

*(Production note: keep at most one `is_active = true` row (`uq_dataset_registry_single_active`); promote new dataset versions inside one transaction before updating or syncing ML catalog metadata.)*

---

## 4. Zero-Downtime Secret & Key Rotation

### A. JWT Access Signing Key (`JWT_SECRET_KEY` / `JWT_PREVIOUS_SECRET_KEY`)

`app/core/security.py` (`decode_access_token`) pins `alg=HS256`, verifies against `JWT_SECRET_KEY` first, and falls back to `JWT_PREVIOUS_SECRET_KEY` if non-empty and distinct:

1. Move the existing `JWT_SECRET_KEY` value into `JWT_PREVIOUS_SECRET_KEY` in `.env` / secrets manager.
2. Generate a new 32+ byte random string for `JWT_SECRET_KEY`.
3. Recreate `api`: `docker compose up -d api`. Existing access tokens signed by the previous key remain valid until `JWT_ACCESS_EXPIRES_SECONDS` (default `3600` s).
4. Once `JWT_ACCESS_EXPIRES_SECONDS` has elapsed, clear `JWT_PREVIOUS_SECRET_KEY=` and recreate `api`.

*(Refresh tokens are opaque random secrets stored strictly as SHA-256 hashes in `public.refresh_tokens`, so JWT key rotation never invalidates valid refresh token families.)*

### B. External ML API Key (`ML_SERVICE_API_KEY` / `ML_SERVICE_PREVIOUS_API_KEY`)

`RealMLAdapter._request_with_key_rotation` sends `X-ML-API-Key: <ML_SERVICE_API_KEY>` and on HTTP `401` or `403` retries once with `ML_SERVICE_PREVIOUS_API_KEY` (logging `ml_api_key_rotation_retry`):

1. Configure the External ML service (or `mock-ml`, which reads both env vars) to accept the new key alongside the current key.
2. Put the previous key in `ML_SERVICE_PREVIOUS_API_KEY` and the new key in `ML_SERVICE_API_KEY`.
3. Recreate `api` and `worker`: `docker compose up -d api worker`.
4. After verifying `200` on `/v1/health` and `/v1/analyze` without rotation warnings, retire the old key on the External ML service and clear `ML_SERVICE_PREVIOUS_API_KEY=`.

---

## 5. Redis Inspection & Operational Keys

Inspect live Redis state without exposing PII (IPs and tokens are stored only as SHA-256 hex digests or 16-char hash prefixes):

```powershell
wsl -d Ubuntu -- bash -lc "cd /mnt/c/Users/SURFUCE/Pictures/fieldshift-planner && docker compose exec -T redis redis-cli INFO keyspace"
wsl -d Ubuntu -- bash -lc "cd /mnt/c/Users/SURFUCE/Pictures/fieldshift-planner && docker compose exec -T redis redis-cli GET ml:provider_status"
wsl -d Ubuntu -- bash -lc "cd /mnt/c/Users/SURFUCE/Pictures/fieldshift-planner && docker compose exec -T redis redis-cli --scan --pattern 'worker:heartbeat:*'"
wsl -d Ubuntu -- bash -lc "cd /mnt/c/Users/SURFUCE/Pictures/fieldshift-planner && docker compose exec -T redis redis-cli --scan --pattern 'rl:*'"
```

| Key Pattern | TTL / Behavior | Purpose |
| :--- | :--- | :--- |
| `ml:provider_status` | `2 * ML_HEALTH_CHECK_INTERVAL_SECONDS` | Cross-container ML provider snapshot (`real_ml` / `mock_ml`, `reachable`, `ml_engine_version`) |
| `worker:heartbeat:<worker_id>` | Expiring heartbeat TTL | Live `WorkerRunner` presence scanned non-blockingly by `GET /api/v1/health` |
| `guest_quota:<sha256_hex>:quarters` | `GUEST_SESSION_DAYS` (`7d`) | Cached guest quarter counter hydrated from `guest_sessions FOR UPDATE` |
| `rl:guest_create:ip:<sha256>:<ts>` | Interpolated 2-bucket (`3600s`) | `POST /auth/guest` per-IP throttle (`GUEST_CREATE_PER_IP_HOUR`) |
| `rl:crud:{u:<id>\|g:<hash16>}:<ts>` | Interpolated 2-bucket (`60s`) | Authenticated (`RATE_LIMIT_CRUD_PER_MIN`) / guest (`GUEST_BURST_PER_MIN`) CRUD burst |
| `rl:poll:{u:<id>\|g:<hash16>}:<ts>` | Interpolated 2-bucket (`60s`) | Dedicated `120 req/min` bucket for `GET /analysis/requests/{id}` |
| `rl:analysis:{u:<id>\|ip:<sha256>}:<ts>` | Interpolated 2-bucket (`3600s`) | Quarter-weighted hourly analysis buckets (`4` full / `1` What-If) |

*(If Redis goes down with `REDIS_FAIL_CLOSED=true`, protected API routes return `503 SERVICE_UNAVAILABLE` and `redis_errors_total` increments; `GET /api/v1/health` reports `503 SERVICE_UNAVAILABLE`.)*

---

## 6. Circuit Breaker, Worker & Health Monitoring

- **Health Endpoints:**
  - `GET /api/v1/health?check=live` — fast liveness response
  - `GET /api/v1/health?check=ready` — verifies Postgres + Redis (`503 SERVICE_UNAVAILABLE` on failure), active dataset (`503 DATASET_UNAVAILABLE` if missing), active workers, and External ML (`200 {status: "degraded"}` if ML is down while DB/Redis/dataset are healthy)
  - `GET /api/v1/health?check=dependencies` — full dependency diagnostics
- **Prometheus Scrape Target (`GET /api/v1/metrics`):**
  - `analysis_requests_total{status,error_code}`
  - `ml_request_duration_seconds{provider,outcome}`
  - `worker_active_leases`
  - `worker_bulkhead_inflight`
  - `ml_breaker_state` (`0=closed`, `1=open`, `2=half_open`)
  - `ml_active_provider{provider}`
  - `redis_errors_total{operation}`
  - `ml_unknown_fields_observed_total`
- **Circuit Breaker & `last_good_replay` Inspection (`public.ml_breaker_state`):**

```powershell
wsl -d Ubuntu -- bash -lc "cd /mnt/c/Users/SURFUCE/Pictures/fieldshift-planner && docker compose exec -T db psql -U fieldshift -d fieldshift -c 'SELECT state, failure_count, opened_at, next_retry_at, last_error_code, half_open_probe_at FROM public.ml_breaker_state WHERE id = 1;'"
```

When `ml_breaker_state.state = 'open'`, new non-`1Q` jobs with a prior verified canonical match within `DEGRADED_MODE_MAX_AGE_HOURS` (`72`h) resolve cleanly as `last_good_replay` (`status = 'ok'`, `degraded_mode.stale = true`) without calling ML. After `ML_BREAKER_COOLDOWN_SECONDS` (`30`s), one worker acquires a single-flight `half_open` probe via `SELECT ... FOR UPDATE`.

---

## 7. Backup, Recovery & Retention (`# TODO(OQ-7)`)

> **Pending Governance (`OQ-7`):** Automated off-host backup cron frequency, RPO/RTO SLA targets, audit log retention, and archival TTL pruning for `analysis_requests.input_snapshot_gz` (`app/worker/runner.py:1115`) remain queued in [`BACKLOG.md`](BACKLOG.md).

### Manual `pg_dump` / `pg_restore` Procedures

```powershell
# Logical custom-format backup (preserves PostGIS geometries + binary bytea snapshots)
wsl -d Ubuntu -- bash -lc "cd /mnt/c/Users/SURFUCE/Pictures/fieldshift-planner && docker compose exec -T db pg_dump -U fieldshift -d fieldshift -Fc > backup_fieldshift_$(date +%Y%m%d_%H%M%S).dump"

# Restore into a fresh PostgreSQL + PostGIS database (stop api/worker first)
wsl -d Ubuntu -- bash -lc "cd /mnt/c/Users/SURFUCE/Pictures/fieldshift-planner && docker compose stop api worker && docker compose exec -T db pg_restore -U fieldshift -d fieldshift --clean --if-exists < backup_file.dump && docker compose start api worker"
```

Verify post-restore health and data counts: `GET /api/v1/health?check=ready` -> `200`, then `docker compose exec -T worker python -m app.worker.healthcheck`.
