# Phase L — Integration Architecture Audit

> **Project:** Field Shift — Guelma Wilaya Crop Rotation Decision-Support System  
> **Audit Principle:** Findings below are verified directly against existing source files, schemas, test suites, and runtime environment checks on `2026-11-15`—not inferred solely from Phase D–K documentation.

---

## 1. Existing Module & Asset Inventory

| Layer / Phase | Authoritative Paths Inspected | Responsibility | Status Before Phase L |
|---|---|---|---|
| **Phase D (Data Harm.)** | [`fieldshift_integration/config.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/fieldshift_integration/config.py), `canonical_layers.py`, `spatial_harmonization.py` | UTM 32N (`EPSG:32632`) harmonized rasters, seasonal CSV panels, NASA POWER cells, GPKG boundaries | Complete & verified (`5` tests) |
| **Phase E (Problem & Constraints)** | [`docs/phaseE/`](file:///home/lokman/Desktop/FeildShit-SI-Model/docs/phaseE/phaseE_research_report.md) (`crop_system_inventory.csv`, `agronomic_constraints_framework.csv`, `validation_strategy.md`) | Crop inventory, 14 constraints, 7-pillar pre-deployment validation gates | Complete (reference specs & lookups) |
| **Phase F (Input & Geospatial)** | [`field_input_schema.json`](file:///home/lokman/Desktop/FeildShit-SI-Model/field_input_schema.json), [`field_geospatial_processor.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/field_geospatial_processor.py), [`field_profile_builder.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/field_profile_builder.py) | Minimal farmer validation + automatic extraction (`SoilGrids V6`, `ESA CropFreq`, `S2 2024-03`, `MODIS`, `GPM`, `SMAP`, `NASA POWER`, `DEM` placeholder) -> 4-part `FieldProfile` | Complete & audited (`15` tests across `test_field_profile` + `test_phaseF_audit`) |
| **Phase G (Agronomic KB & Rules)** | [`agronomic_knowledge/`](file:///home/lokman/Desktop/FeildShit-SI-Model/agronomic_knowledge/crop_profiles.json) (`13` crops, `15` rules, `10` sequence rules), [`src/agronomic/constraint_engine.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/src/agronomic/constraint_engine.py) | Single-crop & multi-year sequence evaluation preserving `PASS`, `WARNING`, `FAIL`, `UNKNOWN` | Complete (`11` tests) |
| **Phase H (Candidate Generator)** | [`src/rotation/candidate_generator.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/src/rotation/candidate_generator.py) | Deterministic generation of `<= 8` diverse `2–4` season strategies + baseline counterfactuals | Complete (`10` tests) |
| **Phase I (Scoring & Pareto)** | [`src/optimization/scoring_engine.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/src/optimization/scoring_engine.py), `pareto.py`, `sensitivity.py` | 8-objective scoring, Pareto dominance, normalized active weights, OAT/climate sensitivity | Complete (`10` tests) |
| **Phase J (Final Output Contract)** | [`schemas/final_recommendation_output.schema.json`](file:///home/lokman/Desktop/FeildShit-SI-Model/schemas/final_recommendation_output.schema.json), [`src/output/recommendation_builder.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/src/output/recommendation_builder.py), [`src/output/output_validator.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/src/output/output_validator.py) | Assembles normalized Draft 2020-12 JSON response + standalone schema/semantic validator | Complete (`8` tests) |
| **Phase K (Scientific Validation)** | [`docs/phaseK/`](file:///home/lokman/Desktop/FeildShit-SI-Model/docs/phaseK/scientific_validation_report.md), [`tests/test_phaseK_validation.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/tests/test_phaseK_validation.py) | 17-scenario stress matrix, causal backtest, scorecard (`CONDITIONAL` readiness) | Complete (`5` tests; total `64` passing tests) |

---

## 2. Actual Public Interfaces & Data Exchange Signatures

Verified directly from module exports (`__init__.py` and root modules):

1. **Farmer Input & Polygon Validation (Root Modules):**
   - `validate_farmer_input(payload: Dict[str, Any]) -> Dict[str, Any]` (`field_profile_builder.py`)  
     Raises `FarmerInputValidationError(ValueError)`. Normalizes `crop_aliases`, enforces `required = {"field", "water", "planning"}`, blocks `FORBIDDEN_TECHNICAL_KEYS` recursively, preserves `null` (`"NOT_PROVIDED"`) vs `[]` (`"EXPLICITLY_CONFIRMED_EMPTY"`).
   - `validate_and_project_polygon(geometry: Dict[str, Any], geometry_crs: str = "EPSG:4326") -> Dict[str, Any]` (`field_geospatial_processor.py`)  
     Raises `ValueError`. Enforces GeoJSON `"Polygon"` (`shape(geometry)` valid, finite coords, non-empty, `wilaya_overlap_pct > 0.0` in `EPSG:32632`), calculates `area_m2`, `area_ha`, `commune_overlaps`, `validation_warnings`.
   - `extract_field_geospatial_context(geometry: Dict[str, Any], geometry_crs: str = "EPSG:4326") -> Dict[str, Any]` (`field_geospatial_processor.py`)  
     Returns `{"spatial_validation": {...}, "extracted_datasets": {...}}`.
   - `build_field_profile(farmer_payload: Dict[str, Any]) -> Dict[str, Any]` (`field_profile_builder.py`)  
     Orchestrates input validation + geospatial extraction + Phase E diagnostics + quality/uncertainty follow-ups -> 4-section dict (`section_a_farmer_provided`, `section_b_extracted_geospatial`, `section_c_agronomic_knowledge_base`, `section_d_quality_and_uncertainty`).
2. **Agronomic Knowledge & Constraints (`src.agronomic`):**
   - `load_knowledge_base() -> AgronomicKnowledgeBase` (`@lru_cache(maxsize=1)`)
   - `evaluate_crop_for_field(crop_id: str, field_profile: Dict[str, Any], planting_season: Optional[str] = None, kb: Optional[AgronomicKnowledgeBase] = None) -> Dict[str, Any]`
   - `evaluate_all_crops_for_field(...) -> Dict[str, Dict[str, Any]]`
   - `evaluate_crop_sequence(sequence_slots: Sequence[Dict[str, Any]], field_profile: Dict[str, Any], crop_history: Optional[Sequence[Dict[str, Any]]] = None, kb: Optional[AgronomicKnowledgeBase] = None) -> Dict[str, Any]`
3. **Candidate Generation (`src.rotation`):**
   - `generate_rotation_candidates(field_profile: Dict[str, Any], config: Optional[GenerationConfig] = None, kb: Optional[AgronomicKnowledgeBase] = None) -> Dict[str, Any]`
4. **Multi-Objective Optimization (`src.optimization`):**
   - `rank_rotation_candidates(candidate_output: Dict[str, Any], field_profile: Optional[Dict[str, Any]] = None, weights: Optional[Dict[str, Optional[float]]] = None, economic_data: Optional[Dict[str, Any]] = None, kb: Optional[AgronomicKnowledgeBase] = None) -> Dict[str, Any]`
5. **Final Output Assembly & Validation (`src.output`):**
   - `build_final_recommendation(field_profile: Dict[str, Any], candidate_output: Dict[str, Any], ranking_output: Dict[str, Any], language: str = "en", generated_at: Optional[str] = None, request_id: Optional[str] = None, kb: Optional[AgronomicKnowledgeBase] = None) -> Dict[str, Any]`
   - `validate_final_recommendation(payload: Dict[str, Any], schema_path: Optional[Path] = None) -> Dict[str, Any]` -> returns `{"valid": bool, "errors": List[str], "schema_version": ...}` (does **not** raise automatically unless caller raises `OutputValidationError`).

### Pipeline Data Flow
```
Minimal Farmer JSON
  └─▶ field_profile_builder.build_field_profile()          [4-section FieldProfile]
        └─▶ src.rotation.generate_rotation_candidates()     [<=8 sequences, Phase G rules]
              └─▶ src.optimization.rank_rotation_candidates() [8 objectives, Pareto, OAT/Climate]
                    └─▶ src.output.build_final_recommendation(..., request_id=...)
                          └─▶ src.output.validate_final_recommendation()  [Draft 2020-12 gate]
```

---

## 3. Infrastructure & Dependency Reality Check

| Dependency Area | Observed Local State | Architecture Implication |
|---|---|---|
| **Python Scientific Stack (`venv`)** | Python 3.14; `geopandas 1.2.0`, `rasterio 1.5.2`, `shapely 2.2.0`, `pyproj 3.8.0`, `pandas 3.1.1`, `numpy 2.5.4`, `scipy 1.18.1` | Fully ready for geospatial pipeline execution. |
| **Web / API Libraries** | `fastapi`, `uvicorn`, `pydantic`, `httpx` NOT initially installed in `venv`; PyPI (`fastapi 0.163.0`) accessible | Install `fastapi`, `uvicorn`, `httpx` in `venv` cleanly without altering Phases A–K dependencies. |
| **`jsonschema` Package** | Not installed in `venv` | Both Phase F (`validate_farmer_input`) & Phase J (`output_validator.py`) implement dependency-free structural/semantic validators cleanly. |
| **PostgreSQL / PostGIS** | `psql (PostgreSQL) 18.6` active on `/var/run/postgresql:5432`, **NO PostGIS extension files on host** (`/usr/share/postgresql/*/extension/postgis*` missing); no `psycopg` in `venv` | Author authoritative **PostGIS SQL DDL** (`db/schema_postgis.sql`) + repository interface, and execute live local persistence via Python stdlib **`sqlite3 3.51.2`** (zero external privilege barrier) while flagging PostGIS runtime connection as **DISCONNECTED** until host PostGIS package & DSN are provisioned. |
| **Reference Spatial Boundary** | [`guelma_wilaya_boundary.geojson`](file:///home/lokman/Desktop/FeildShit-SI-Model/guelma_wilaya_boundary.geojson) (`25 KB`) present at repo root | Can be served directly via API for offline-capable map rendering in field pilots. |

---

## 4. Documented vs. Actual Implementation Gaps & Integration Risks

1. **CRITICAL Integration Bug Prevented — Upstream `request_id` Ignores Polygon Geometry & Water:**  
   In [`src/output/recommendation_builder.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/src/output/recommendation_builder.py#L33-L44), `_deterministic_request_id(field_id, cand_out)` hashes ONLY `field_id`, `generation_config`, `history`, and `preferences`. Resubmitting the same `field_id` with a edited polygon or changed irrigation system yields an identical Phase J `request_id`!  
   **Fix in Phase L:** Compute a cryptographic full-request SHA-256 hash (`analysis_id`) over the normalized payload (`field.geometry`, `water`, `crop_history`, `planning`, `preferences`) and pass it explicitly into `build_final_recommendation(..., request_id=...)` OR store both `analysis_id` (PK) and `engine_request_id` cleanly.

2. **Output Schema Validation Not Automatic in `build_final_recommendation`:**  
   `build_final_recommendation()` returns an unvalidated dict; callers must explicitly invoke `validate_final_recommendation(payload)` and reject/500 on `not res["valid"]`.

3. **GeoJSON Input Strictness vs. Interactive Map Libraries (`Leaflet` / `GeoJSON Features`):**  
   `validate_and_project_polygon()` strictly requires bare GeoJSON `{"type": "Polygon", "coordinates": ...}`. Interactive map drawing tools often produce GeoJSON `Feature` objects; the frontend/API schema must explicitly accept raw `Polygon` (and unwrap/validate strictly without permitting `MultiPolygon`).

4. **Mixed Exception Types Across Pipeline Seams:**  
   `validate_farmer_input()` raises `FarmerInputValidationError`, `validate_and_project_polygon()` raises `ValueError`, and `output_validator` uses `OutputValidationError`. The FastAPI layer needs centralized exception mapping (`422` for farmer/geometry/forbidden-field rejections with structured details; `500` without leaking internal tracebacks for output validation or missing raster infrastructure).

5. **Cold-Start Table Loading & Sync Threadpool Offloading:**  
   `@lru_cache(maxsize=1)` in `field_geospatial_processor.py` loads `GPKG`, `NASA POWER daily CSV`, `GPM`, `SMAP`, and `Wilaya Monthly` tables lazily on the first call (~2–4 s warm-up), and `rasterio`/`shapely` calls are CPU/IO synchronous. FastAPI route handlers touching the pipeline MUST be defined as regular sync `def` endpoints (so Starlette runs them in a worker threadpool) and `/api/v1/health` should inspect dataset presence/warm status cleanly.

6. **Localization Metadata (`en`/`fr`/`ar`) vs. English Explanation Strings:**  
   `final_recommendation_output.schema.json` allows `language` in `["en", "fr", "ar"]`, yet `recommendation_builder.py` emits English explanations/reasons regardless of `language`. Frontend UI should support i18n chrome/labels cleanly while disclosing when engine rule prose is `en`.

7. **No Farmer Authentication / Access Control in Phases A–K:**  
   Phases A–K accept stateless anonymous payloads with no user/farmer table. Phase L database design includes `farmers_users` + ownership FKs, while noting local anonymous advisory-session mode vs production OAuth2/JWT auth (`DISCONNECTED` until deployment identity provider is wired).
