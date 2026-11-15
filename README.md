# fieldshift-planner

A farmer-friendly decision-support web app combining curated local environmental & agronomic datasets, farm soil and water records, and crop characteristics to explore and compare climate-resilient crop-rotation strategies.

---

## System Design

1. [System Design Master Index](SYSTEM%20DESGIN/SYSTEM%20DESGIN.md)
2. [Architecture Decision Records (ADR)](SYSTEM%20DESGIN/SYSTEM%20DESGIN/Architecture%20Decision%20Records%20%28ADR%29.md)
3. [System Architecture Blueprint](SYSTEM%20DESGIN/SYSTEM%20DESGIN/System%20Architecture%20Blueprint.md)
4. [ENDPOINTS API & Database Specification](SYSTEM%20DESGIN/SYSTEM%20DESGIN/System%20Architecture%20Blueprint/FieldShift%20Planner%20%E2%80%94%20ENDPOINTS%20api%20%26%20Database%20Specification.md)
5. [Visual Input / Output Specification (API + Database Test)](SYSTEM%20DESGIN/SYSTEM%20DESGIN/System%20Architecture%20Blueprint/Visual%20Input%20%20Output%20Specification.md)
6. [OpenAPI 3.1.0 Specification (`openapi.yaml`)](SYSTEM%20DESGIN/SYSTEM%20DESGIN/System%20Architecture%20Blueprint/openapi.yaml)
7. [ML Wire JSON Schema (`schema-v5.0.json`)](SYSTEM%20DESGIN/SYSTEM%20DESGIN/System%20Architecture%20Blueprint/schema-v5.0.json)

## Implementation & Operations Docs

- [`docs/impl/00-spec-digest.md`](docs/impl/00-spec-digest.md) — Normative specification digest (`34` routes, `13` tables + `Schema: dataset`, `19` errors, `40+7` settings)
- [`docs/impl/01-audit-and-gaps.md`](docs/impl/01-audit-and-gaps.md) — Cross-spec audit and gap reconciliation
- [`docs/impl/02-implementation-plan.md`](docs/impl/02-implementation-plan.md) — Milestone plan (`M0`–`M13`), 16 pitfall mitigations, and 8-layer test strategy
- [`docs/impl/DECISIONS.md`](docs/impl/DECISIONS.md) — Architecture/implementation decisions (`IMPL-001`..`IMPL-023`)
- [`docs/impl/DESIGN_ISSUES.md`](docs/impl/DESIGN_ISSUES.md) — Spec discrepancies & resolutions (`DI-01`..`DI-17`)
- [`docs/impl/TRACEABILITY.md`](docs/impl/TRACEABILITY.md) — Full requirement-to-code-to-test traceability matrix
- [`docs/impl/RUNBOOK.md`](docs/impl/RUNBOOK.md) — Deployment, secret rotation, Redis inspection, breaker, and backup/restore runbook
- [`docs/impl/BACKLOG.md`](docs/impl/BACKLOG.md) — Open Questions (`OQ-1`..`OQ-11`, `OQ-D1`..`OQ-D8`) and `# TODO(OQ-*)` index

---

## Quickstart (Windows PowerShell + WSL2 Docker Compose)

### 1. Environment Configuration

Copy [`.env.example`](.env.example) to `.env` in the repository root and set strong secrets (`DB_PASSWORD`, `ML_READER_PASSWORD`, `JWT_SECRET_KEY`, `ML_SERVICE_API_KEY`):

```powershell
Copy-Item .env.example .env
```

For local multi-container HTTP wire testing against the built-in `mock-ml` service (`--profile dev`), set these overrides in `.env`:

```env
APP_ENV=development
ML_PROVIDER_MODE=auto
ML_SERVICE_URL=http://mock-ml:8090
```

> **Production Safety (`IMPL-018`):** `.env.example` keeps fail-safe defaults (`APP_ENV=production`, `ML_PROVIDER_MODE=auto`, `REDIS_FAIL_CLOSED=true`). With `APP_ENV=production`, `ML_PROVIDER_MODE=mock` and non-`https://` `ML_SERVICE_URL` values are rejected at startup.

### 2. Full Stack Bring-Up (`db`, `redis`, `migrate`, `api`, `worker`, `mock-ml`)

```powershell
# Validate Compose YAML and environment interpolation
wsl -d Ubuntu -- bash -lc "cd /mnt/c/Users/SURFUCE/Pictures/fieldshift-planner && docker compose --profile dev config"

# Clean fresh-volume boot (rebuilds images, runs Alembic migrations, starts healthy services)
wsl -d Ubuntu -- bash -lc "cd /mnt/c/Users/SURFUCE/Pictures/fieldshift-planner && docker compose --profile dev down -v && docker compose --profile dev up -d --build --wait"
wsl -d Ubuntu -- bash -lc "cd /mnt/c/Users/SURFUCE/Pictures/fieldshift-planner && docker compose --profile dev ps -a"
```

Verify live container healthchecks:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/api/v1/health?check=ready"
Invoke-WebRequest "http://127.0.0.1:8000/api/v1/metrics" | Select-Object -ExpandProperty StatusCode
wsl -d Ubuntu -- bash -lc "cd /mnt/c/Users/SURFUCE/Pictures/fieldshift-planner && docker compose exec -T worker python -m app.worker.healthcheck"
```

---

## Local Development, Linting, Contracts & Test Suite

Start only PostgreSQL/PostGIS and Redis containers in WSL, then run migrations, contract checks, static analysis, and tests from `backend/.venv`:

```powershell
wsl -d Ubuntu -- bash -lc "cd /mnt/c/Users/SURFUCE/Pictures/fieldshift-planner && docker compose up -d --wait db redis"

cd backend
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\alembic.exe check
.\.venv\Scripts\python.exe tools/verify_contracts.py
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\mypy.exe --strict app
.\.venv\Scripts\pytest.exe -q --cov=app --cov-report=term-missing
```

---

## Operations Quick Reference

See [`docs/impl/RUNBOOK.md`](docs/impl/RUNBOOK.md) for full procedures:

- **Database Migrations:** `alembic upgrade head` (`001_initial_schema.py` creates 13 `public` tables, isolated `Schema: dataset`, and read-only `ml_reader`; `002_seed_initial_data.py` seeds Wilaya of Guelma placeholder boundary, initial dataset registry, and singleton `ml_breaker_state`).
- **Zero-Downtime Key Rotation:**
  - **JWT (`HS256`):** Copy old secret to `JWT_PREVIOUS_SECRET_KEY`, set new `JWT_SECRET_KEY`, restart `api`, then remove `JWT_PREVIOUS_SECRET_KEY` after `JWT_ACCESS_EXPIRES_SECONDS` (`3600` s).
  - **ML API Key (`X-ML-API-Key`):** Set previous key in `ML_SERVICE_PREVIOUS_API_KEY`, set new primary key in `ML_SERVICE_API_KEY`, restart `api` and `worker` (`RealMLAdapter` retries `401`/`403` once using the previous key), then clear `ML_SERVICE_PREVIOUS_API_KEY` after cutover.
- **Redis Inspection:**
  ```powershell
  wsl -d Ubuntu -- bash -lc "cd /mnt/c/Users/SURFUCE/Pictures/fieldshift-planner && docker compose exec -T redis redis-cli GET ml:provider_status"
  wsl -d Ubuntu -- bash -lc "cd /mnt/c/Users/SURFUCE/Pictures/fieldshift-planner && docker compose exec -T redis redis-cli --scan --pattern 'worker:heartbeat:*'"
  wsl -d Ubuntu -- bash -lc "cd /mnt/c/Users/SURFUCE/Pictures/fieldshift-planner && docker compose exec -T redis redis-cli --scan --pattern 'rl:*'"
  ```
- **Logical Backups:**
  ```powershell
  wsl -d Ubuntu -- bash -lc "cd /mnt/c/Users/SURFUCE/Pictures/fieldshift-planner && docker compose exec -T db pg_dump -U fieldshift -d fieldshift -Fc > backup_fieldshift.dump"
  ```
