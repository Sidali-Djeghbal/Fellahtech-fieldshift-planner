er # Field Shift (`SI Model V4`) — Docker Build & Share Guide

Containerized setup for **Field Shift (Guelma Wilaya Crop Rotation DSS)** containing Python `3.14`, FastAPI + Uvicorn backend, interactive Farmer Web UI, agronomic knowledge base, schemas, and required Guelma geospatial datasets.

---

## Option 1 — Send a Single Self-Contained Image File (Easiest for Your Friend)

Your friend only needs **Docker** installed (no source code, Python, or manual data setup needed).

### 1. Export the built image (`fieldshift-si-model:v4`) to a compressed archive
Run on your machine:
```bash
docker save fieldshift-si-model:v4 | gzip > fieldshift-si-model-v4.tar.gz
```
Send `fieldshift-si-model-v4.tar.gz` to your friend.

### 2. Your friend loads and starts the container
```bash
docker load -i fieldshift-si-model-v4.tar.gz
docker run -d --name fieldshift-dss -p 8000:8000 -v fieldshift_state:/app/state fieldshift-si-model:v4
```

Then open in browser:
- **Farmer Web Interface:** http://127.0.0.1:8000/
- **API Swagger Docs:** http://127.0.0.1:8000/docs
- **Health Check:** http://127.0.0.1:8000/api/v1/health

Useful lifecycle commands for your friend:
```bash
docker logs -f fieldshift-dss     # View server logs
docker stop fieldshift-dss        # Stop container
docker start fieldshift-dss       # Restart later (analyses persist in volume fieldshift_state)
```

---

## Option 2 — Send Project Folder & Run with Docker Compose

If your friend prefers building from the project folder directly:
```bash
docker compose up -d --build
```
Stop cleanly:
```bash
docker compose down
```
*(Stored SQLite analyses persist in Docker volume `fieldshift_state` mounted at `/app/state/fieldshift_analyses.db`.)*
