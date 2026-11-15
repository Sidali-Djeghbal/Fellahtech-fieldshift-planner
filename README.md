# Field Shift — Guelma Wilaya Crop Rotation Decision-Support System (`FieldShift-PhaseFJ-1.1.0`)

Data-driven geospatial & agronomic crop rotation decision-support system for **Guelma Wilaya, Algeria** (`3683.2311 km²`, `34` communes, `EPSG:32632`), originally initiated for **NASA Space Apps Challenge 2026** and extended through Phases A–O into a validated FastAPI + SQLite + Web UI application.

---

## 1. Quick Start & Installation

**Prerequisites:** Python `3.14` (tested on `Python 3.14.7`).

1. **Create and activate a virtual environment** (skip if using the existing `./venv/`):
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

2. **Install dependencies from `requirements.txt`:**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

---

## 2. Running the API Server & Farmer Web UI

Start the FastAPI backend from the repository root (`/home/lokman/Desktop/FeildShit-SI-Model`):

```bash
./venv/bin/uvicorn src.api.app:app --reload --host 127.0.0.1 --port 8000
```

Once running:
- **Farmer Web Interface:** `http://127.0.0.1:8000/` (`frontend/index.html`)
- **Interactive OpenAPI / Swagger Docs:** `http://127.0.0.1:8000/docs`
- **Health Check:** `http://127.0.0.1:8000/api/v1/health`

**Persistence:** Analyses are persisted locally by default in SQLite at `data/app_state/fieldshift_analyses.db`. You can override the SQLite location via:
```bash
FIELDSHIFT_SQLITE_PATH=/tmp/fieldshift_test.db ./venv/bin/uvicorn src.api.app:app --port 8000
```

---

## 3. API Endpoints & Quick Test Requests

### Core Endpoints
- `GET /api/v1/health` — Service health, knowledge base counts (`13` crops, `15` crop rules, `10` sequence rules), core geospatial archive checks, and database status.
- `GET /api/v1/reference/crops` — Canonical crop catalog (`DURUM_WHEAT`, `SOFT_WHEAT`, `BARLEY`, `FABA_BEAN`, `CHICKPEA_WINTER`, `CHICKPEA_SPRING`, `LENTIL`, `VETCH_OAT`, `TOMATO_IND`, `POTATO`, `SUNFLOWER`, `OLIVE`, `BARE_FALLOW`).
- `GET /api/v1/reference/guelma-boundary` — Guelma Wilaya boundary GeoJSON.
- `POST /api/v1/fields/validate` — Validates farmer inputs, target/excluded crop conflicts, chronological `crop_history`, and Guelma polygon overlap (fast check, no raster extraction).
- `POST /api/v1/fields/analyze` — Runs the full Phases F -> G -> H -> I -> J pipeline (geospatial extraction, constraints, candidate generation, multi-objective scoring, Draft 2020-12 output validation) and persists/caches results in SQLite.
- `GET /api/v1/analyses/{analysis_id}` — Retrieves a persisted analysis by ID.

### Smoke-Test Requests (`curl`)
```bash
# 1. Health & supported crop IDs
curl -s http://127.0.0.1:8000/api/v1/health | python3 -m json.tool
curl -s http://127.0.0.1:8000/api/v1/reference/crops | python3 -m json.tool

# 2. Validate Belkheir reference polygon
curl -i -X POST http://127.0.0.1:8000/api/v1/fields/validate \
  -H "Content-Type: application/json" \
  -d '{
    "field": {
      "field_id": "FLD_GUELMA_PILOT_01",
      "field_name": "Belkheir Valley",
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[7.48, 36.47], [7.486, 36.47], [7.486, 36.474], [7.48, 36.474], [7.48, 36.47]]]
      },
      "geometry_crs": "EPSG:4326"
    },
    "water": { "availability": "limited", "source": "rainfed", "irrigation_system": "none" },
    "crop_history": null,
    "planning": { "start_season": "Autumn", "start_year": 2026, "horizon_seasons": 3, "planning_mode": "CURRENT_PLANNING" },
    "preferences": { "target_crop_ids": [], "excluded_crop_ids": [], "equipment_constraints": null, "forage_value_weight": null }
  }'

# 3. Run full analysis & fetch stored result
curl -s -X POST http://127.0.0.1:8000/api/v1/fields/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "field": {
      "field_id": "FLD_GUELMA_PILOT_01",
      "field_name": "Belkheir Valley",
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[7.48, 36.47], [7.486, 36.47], [7.486, 36.474], [7.48, 36.474], [7.48, 36.47]]]
      },
      "geometry_crs": "EPSG:4326"
    },
    "water": { "availability": "limited", "source": "rainfed", "irrigation_system": "none" },
    "crop_history": null,
    "planning": { "start_season": "Autumn", "start_year": 2026, "horizon_seasons": 3, "planning_mode": "CURRENT_PLANNING" },
    "preferences": { "target_crop_ids": [], "excluded_crop_ids": [], "equipment_constraints": null, "forage_value_weight": null },
    "language": "en"
  }' | python3 -m json.tool

curl -s http://127.0.0.1:8000/api/v1/analyses/ANAL_241B50895CE3FED6 | python3 -m json.tool
```

All `422` validation errors (`/validate` and `/analyze`) return a uniform top-level envelope: `{"error_code": "...", "message": "...", "details": [...]}`.

---

## 4. Running Automated Tests & Data Pipelines

- **Run the complete regression suite (`91` tests across Phases D–O):**
  ```bash
  ./venv/bin/python -m unittest discover -s tests -v
  ```
- **Run a single phase test module (example: Phase O sensitivity & API contract tests):**
  ```bash
  ./venv/bin/python -m unittest tests.test_phaseO_input_sensitivity -v
  ```
- **Run the reproducible Phase D cross-dataset integration pipeline (zero GEE calls):**
  ```bash
  ./venv/bin/python run_phaseD_integration.py
  ```

---

## 5. Project Pipeline Foundation & Guardrails

1. **NASA POWER Regional Climate (`2016–2025`):** Daily, monthly, seasonal, and annual area-weighted climate variables (`AG` `0.5°×0.625°` MERRA-2 + `RE` `1.0°×1.0°` CERES SYN1deg) -> `data/NASA_POWER_REGIONAL/processed/` (`run_nasa_power_pipeline.py`).
2. **Sentinel-2 Vegetation Indices (`2017–2025`, GEE Project `spry-framework-514800-j2`):** `108` monthly statistical summaries (`10 m` NDVI/EVI with `denom>0.1` + `SR>=0`; `20 m` NDMI/NDRE) + `3,593` scene metadata rows MD5-verified (`16 PASS, 1 CHECK, 0 FAIL`); deferred multi-year GeoTIFFs & pixel-median seasonal/annual tasks queued cleanly on noncommercial `restricted mode` -> `data/SENTINEL2/` (`sentinel2_pipeline/phaseC_runner.py`).
3. **Phase D Cross-Dataset Integration & Feature Engineering Foundation:** Canonical normalization (`NASA POWER`, `GPM IMERG`, `SMAP L4`, `MODIS MOD13Q1`, `SoilGrids 2.0 V6`, `ESA Crop Frequency`, `Sentinel-2`, `GADM 4.1`), raster alignment (`Crop Frequency 10 m -> Sentinel-2 10 m`), downward-only `250 m` & `34`-Commune aggregations, causal lagged feature tables, and `11 PASS / 1 CHECK / 0 FAIL` automated validation -> `data/INTEGRATED/`.
   - Specifications & reports: `data/INTEGRATED/metadata/`, `data/INTEGRATED/docs/`, `data/INTEGRATED/quality/phaseD_validation_report.csv`, `data/INTEGRATED/features/`.
4. **Phases F–O Decision-Support Architecture:** Field profile assembly (`field_profile_builder.py`), agronomic constraints & chronology (`src/agronomic/`), candidate rotation generation (`src/rotation/`), multi-objective scoring & Pareto ranking (`src/optimization/`), Draft 2020-12 recommendation assembly (`src/output/`), FastAPI + SQLite application (`src/api/`, `frontend/`), pilot protocols (`docs/phaseM/`, `src/pilot/`), scientific hardening (`docs/phaseN/`), and farmer input sensitivity & fixes (`docs/phaseO/input_sensitivity/`).

### Scientific Guardrails
- Coarse regional datasets (`NASA POWER ~55–111 km`, `SMAP 11 km`, `GPM 9.6 km`) are **never** upsampled to `10 m` field pixels.
- Monthly `GPM`/`SMAP` files do not exist on disk and are not fabricated; `2017-01` (`1.4173%` coverage) and `Winter 2017` are explicitly flagged ineligible.
- `Crop Frequency (2021–2025)` is blocked from predicting `2017–2020`, and `SoilGrids Nitrogen` is retained strictly for traceability (`UNVALIDATED_EXCLUDED`).
- Technical soil/climate/RS inputs are blocked on farmer-facing requests (`extra="forbid"`), and missing operational fields preserve distinct `null` (`NOT_PROVIDED`) vs `[]` (`EXPLICITLY_CONFIRMED_EMPTY`) semantics.
