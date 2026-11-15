# Phase L — Backend REST API Contract (`v1`)

> **Framework:** FastAPI (`0.163.0`) + Pydantic v2 (`2.14.3`)  
> **Application Entry:** [`src/api/app.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/src/api/app.py) (`create_app()`)  
> **Input Schema Basis:** [`field_input_schema.json`](file:///home/lokman/Desktop/FeildShit-SI-Model/field_input_schema.json) | **Output Schema Basis:** [`schemas/final_recommendation_output.schema.json`](file:///home/lokman/Desktop/FeildShit-SI-Model/schemas/final_recommendation_output.schema.json)

---

## 1. Endpoint Summary

| Method & Path | Purpose | Request Schema | Response Codes |
|---|---|---|---|
| `GET /api/v1/health` | Inspect KB loaded counts, local geospatial dataset readiness, active DB backend, and disclaimers | None | `200 OK` |
| `POST /api/v1/fields/validate` | Validate GeoJSON `Polygon` (`EPSG:4326` -> `EPSG:32632`), Wilaya overlap, and minimal farmer input rules (`null` vs `[]`, forbidden technical fields) without full scoring | `FieldValidationRequest` | `200 OK`, `422 Unprocessable Entity` |
| `POST /api/v1/fields/analyze` | Execute Phases F -> G -> H -> I -> J, validate Draft 2020-12 output, persist 8 DB entities, and return reproducible recommendation | `FieldAnalyzeRequest` | `200 OK`, `422`, `500` |
| `GET /api/v1/analyses/{analysis_id}` | Retrieve persisted original farmer input, Field Profile summary, and validated Phase J recommendation | Path param `analysis_id` | `200 OK`, `404 Not Found` |
| `GET /api/v1/reference/guelma-boundary` | Serve [`guelma_wilaya_boundary.geojson`](file:///home/lokman/Desktop/FeildShit-SI-Model/guelma_wilaya_boundary.geojson) for offline interactive map display | None | `200 OK`, `404` |
| `GET /api/v1/reference/crops` | Return non-technical crop inventory list (`crop_id`, `canonical_name`, `crop_category`, scope & evidence status) | None | `200 OK` |
| `GET /` & `/static/*` | Serve mobile-friendly Farmer Interface ([`frontend/index.html`](file:///home/lokman/Desktop/FeildShit-SI-Model/frontend/index.html)) | None | `200 OK` |

---

## 2. Core Request Contracts

### 2.1 `POST /api/v1/fields/validate` & `POST /api/v1/fields/analyze`

Required minimal fields:
- `field`: `{field_id, field_name?, geometry: {type: "Polygon", coordinates: [...]}, geometry_crs?: "EPSG:4326"}`
- `water`: `{availability: "limited|moderate|abundant|unknown", source: "groundwater|well|reservoir|river|rainfed|other", irrigation_system: "drip|sprinkler|surface|none|unknown"}`
- `planning`: `{start_season: "Winter|Spring|Summer|Autumn", start_year: 2024..2035, horizon_seasons: 2..4, planting_month?: 1..12}`

Optional fields (strictly preserving omitted/`null` vs `[]` vs `0.0`):
- `crop_history`: `null` (omitted/`NOT_PROVIDED`) | `[]` (`EXPLICITLY_CONFIRMED_EMPTY`) | `[{season, year, crop_name_raw, planting_month?, crop_id?, yield_tons_per_hectare?, notes?}]`
- `preferences`: `null` | `{target_crop_ids?, excluded_crop_ids?, equipment_constraints?, water_saving_weight?, soil_improvement_weight?, income_weight?, risk_reduction_weight?, forage_value_weight?}`
- *(Analyze only)* `language`: `"en"` | `"fr"` | `"ar"` (default `"en"`), `farmer_account`: optional `{user_id?, role?, display_name?, commune_name?}`

**Strict Input Rejection (`422`):**
- Supplying any technical variable (`soil_ph`, `clay_pct`, `soc`, `cec`, `nitrogen`, `ndvi`, `rainfall_mm`, `temperature_c`, `elevation_m`, `quality_status`) anywhere in JSON is rejected cleanly (`INVALID_FARMER_INPUT`).
- Supplying `MultiPolygon`, unclosed rings, self-intersections (bowtie), or polygons outside Guelma Wilaya (`wilaya_overlap_pct == 0%`) is rejected cleanly (`INVALID_FIELD_POLYGON`).

---

## 3. Core Response Contracts

### 3.1 `POST /api/v1/fields/analyze` (`200 OK`)
```json
{
  "analysis_id": "ANAL_9D42C1...",
  "payload_sha256": "9d42c1...",
  "reused_existing": false,
  "persistence_backend": "sqlite_local",
  "field_profile_summary": {
    "field_id": "FLD_GUELMA_PILOT_01",
    "spatial_validation": { "area_ha": 24.86, "wilaya_overlap_pct": 100.0, "primary_commune": {"name_2": "Belkheir"} },
    "extracted_summary": { "clay_0_30cm_pct": {"value": 33.76, "quality_status": "MODELED_SPATIAL_ESTIMATE"}, "dem_elevation_m": {"value": null, "quality_status": "UNAVAILABLE_NOT_INTEGRATED"} },
    "descriptive_field_diagnostics": [],
    "conditional_follow_up_questions": [],
    "input_completeness_flags": { "crop_history": "PROVIDED", "equipment_constraints": "NOT_PROVIDED", "forage_value_weight": "NOT_PROVIDED" }
  },
  "recommendation": { "...": "Complete validated Draft 2020-12 Phase J payload (field_plans[0], strategies[], data_quality, requested_crop_results[])" }
}
```

### 3.2 Error Envelope (`422` / `404` / `500`)
- Validation errors from Pydantic / Phase F return `422` with `error_code` (`INVALID_FARMER_INPUT`, `FARMER_INPUT_POLICY_ERROR`, or `INVALID_FIELD_POLYGON`), human-readable `message`, and structured `details`. Internal stack traces and filesystem paths are never returned to clients.
