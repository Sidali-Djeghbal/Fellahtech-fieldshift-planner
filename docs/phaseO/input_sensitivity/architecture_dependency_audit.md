# Phase O — Architecture & Farmer Input Dependency Audit

**System:** Field Shift — Guelma Crop Rotation Decision Support System (DSS)  
**Decision Engine Version:** `FieldShift-PhaseFJ-1.1.0`  
**Audit Reference Polygon:** `FLD_GUELMA_PILOT_01` (Belkheir Valley, Guelma, `23.8605 ha`)  

---

## 1. End-to-End Request & Pipeline Architecture

Every recommendation flows sequentially from farmer-facing inputs through validated contracts without mutating geospatial rasters or fabricating missing agronomic measurements:

1. **Web Frontend (`frontend/index.html`, `frontend/app.js`)**
   - `buildApiPayload()` constructs the JSON body for `/api/v1/fields/validate` and `/api/v1/fields/analyze`.
   - Water source selector (`#waterSource`) includes `rainfed`, `reservoir`, `river`, `well`, `groundwater`, `other`, and `unknown`.
   - Equipment selector (`#equipmentMode`) exposes the 6 KB-supported constraints (`no_hay_baler`, `no_mower`, `no_drip_irrigation`, `no_precision_planter`, `no_potato_harvester`, `no_sunflower_header`) alongside `null` and `[]`.
   - Forage priority (`#forageMode`) sends only `forage_value_weight` (`null`, `0.0`, `0.30`, `0.60`), achieving strict parity with raw API payloads.

2. **Schema & API Validation (`field_input_schema.json`, `src/api/schemas.py`, `src/api/app.py`, `src/api/pipeline_service.py`)**
   - `StrictModel` rejects forbidden technical inputs (e.g. `soil_ph`, `ndvi`, `rainfall_mm`) and enforces exact field enums (`WaterInputContract.source` accepts `"unknown"` separately from `"other"`).
   - `validate_target_excluded_conflict()` rejects overlapping `target_crop_ids` and `excluded_crop_ids` on both `/api/v1/fields/validate` and `/api/v1/fields/analyze` with HTTP `422` (`TARGET_EXCLUDED_CROP_CONFLICT`).
   - All `422` handlers (`RequestValidationError`, `FarmerInputValidationError`, and endpoint `ValueError` via `_value_error_422_response`) return a uniform top-level JSON structure: `{"error_code": str, "message": str, "details": list}`.
   - Full-request content addressing (`compute_payload_sha256` + `derive_analysis_id`) keys SQLite caching strictly on `(decision_engine_version, language, scientific_payload)` so distinct operational inputs never collide in cache (`src/api/repository.py`).

3. **Phase F — Field Profile & Temporal Calendar (`field_profile_builder.py`, `src/agronomic/temporal_planning.py`)**
   - Validates geometry inside Guelma Wilaya and extracts spatial layers independently of operational parameters (`field_geospatial_processor.py`).
   - `validate_and_build_planning_timeline()` uses `SEASON_ORDER = ("Winter", "Spring", "Summer", "Autumn")` and rejects any `crop_history` entry concurrent with or chronologically after planning start (`CROP_HISTORY_AFTER_PLANNING_START`).
   - `assess_crop_history_completeness()` classifies `crop_history` strictly into `NOT_PROVIDED`, `EXPLICITLY_CONFIRMED_EMPTY`, `PROVIDED_PARTIAL`, or `PROVIDED_COMPLETE`, keeping `null` vs `[]` distinct and triggering `Q_LAST_CROP_MATERIAL` only when history is incomplete or lacks a verified multi-campaign baseline.

4. **Phase G — Agronomic Knowledge & Constraints (`src/agronomic/constraint_engine.py`, `agronomic_knowledge/*.json`)**
   - Evaluates 13 crop profiles, 15 crop rules, and 10 sequence compatibility rules (`RuleEvaluation`).
   - Water gates keep `"unknown"` conservative (`RULE_WATER_IRRIGATION_GATE = UNKNOWN` and `RULE_SALINITY_UNMEASURED_IRRIGATION = UNKNOWN` for strictly irrigated systems; `RAINFED_OR_SUPPLEMENTAL` remains evaluated under rainfed tolerance without inferring supplemental water supply).
   - `_eval_equipment_constraints()` evaluates `equipment_tags_sensitive` from `crop_profiles.json`; tags outside the KB (`no_sprayer`, `no_harvester`, etc.) yield `UNKNOWN` (never coerced to `PASS`) with `unsupported_equipment_tags` recorded explicitly.
   - `evaluate_crop_sequence()` resolves `T-1` and `T-2` via canonical `assess_crop_history_completeness()` chronology (`Winter < Spring < Summer < Autumn`) rather than `start_year - 1` alone.

5. **Phase H — Candidate Generation (`src/rotation/candidate_generator.py`)**
   - Consumes a non-mutated `FieldProfile` and calls `_assess_crop_history()` (delegated to `assess_crop_history_completeness()`).
   - Generates `EXISTING_ROTATION_BASELINE` only when `sufficient_for_existing_baseline` is true (`>= 2` resolved prior seasons with a resolved immediate predecessor within `1..4` seasons).
   - `irrig_eligible` explicitly requires non-rainfed and non-unknown `source` and `irrigation_system` so `"unknown"` water never injects irrigated cash strategies unless explicitly requested via `target_crop_ids` (which then become `SELECTED_INFEASIBLE_COUNTERFACTUAL`).

6. **Phase I — Multi-Objective Scoring & Ranking (`src/optimization/scoring_engine.py`)**
   - Evaluates 8 objectives (`water_efficiency`, `soil_improvement`, `nitrogen_contribution`, `pest_disease_disruption`, `erosion_protection`, `income_potential`, `forage_value`, `farmer_priority_fit`).
   - `_resolve_weights()` preserves `DEFAULT_FARMER_WEIGHTS` (`0.25, 0.30, 0.20, 0.25`) whenever all 4 core weights are omitted even if `forage_value_weight` (`0.0` or `> 0`) is supplied alone. Explicit custom core weights totaling `0.0` raise `ValueError` -> `422 INVALID_PRIORITY_WEIGHTS`.
   - Active weight normalization runs once over scorable objectives with positive weight (`income_potential` remains `UNKNOWN` without local yield/price budgets, shifting core weights smoothly over active objectives).
   - `_eval_farmer_priority_fit()` marks unmodeled equipment tags as `PARTIAL` (matching `UNKNOWN` slot readiness `0.75`) so unsupported API tags do not inflate scores or alter relative ranking.

7. **Phase J — Final Recommendation Assembly & Validation (`src/output/recommendation_builder.py`, `src/output/output_validator.py`)**
   - Preserves `PROVIDED_PARTIAL` and `PROVIDED_COMPLETE` alongside `NOT_PROVIDED` and `EXPLICITLY_CONFIRMED_EMPTY` in `data_quality.input_completeness_flags` and `completeness_score` (`db/schema_postgis.sql` CHECK constraint aligned).
   - Surfaces any unmodeled equipment tags in both `data_quality.warnings` (`[UNSUPPORTED_EQUIPMENT_TAG]`) and `data_quality.missing_data`.
   - Validates 100% of responses against Draft 2020-12 JSON Schema & safety invariants (`validate_final_recommendation`).

---

## 2. Input-to-Component Dependency Matrix

| Farmer Input Field | Schema / Validation | Phase F (`field_profile`) | Phase G (`constraint_engine`) | Phase H (`candidate_generator`) | Phase I (`scoring_engine`) | Phase J / Persistence |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `water.*` (`availability`, `source`, `irrigation_system`) | Enum check (`"unknown"` allowed, `"other"` distinct) | `section_a.water`, `Q_WATER_MATERIAL`, `Q_IRRIGATION_SALINITY_SIGN` | `RULE_WATER_IRRIGATION_GATE`, `RULE_PRECIPITATION_REGIME`, `RULE_SALINITY_UNMEASURED_IRRIGATION`, `RULE_ROOTZONE_SOIL_MOISTURE_CONTEXT`, `SEQ_09` | `irrig_eligible` gating of `IRRIGATED_CASH_BREAK` | `water_efficiency` (`SCORED` / `PARTIAL` / `UNKNOWN`), `farmer_priority_fit` | `critical_missing` ECe check, DB `analysis_requests` |
| `crop_history` (`null`, `[]`, entries) | `SEASON_ORDER` + strict pre-start check (`>= start` -> 422) | `NOT_PROVIDED` / `EXPLICITLY_CONFIRMED_EMPTY` / `PROVIDED_PARTIAL` / `PROVIDED_COMPLETE`, `Q_LAST_CROP_MATERIAL` | `SEQ_10_UNKNOWN_PREDECESSOR_GUARD`, chronological `T-2`/`T-1` carryover (`SEQ_02..SEQ_07`) | `_assess_crop_history`, `EXISTING_ROTATION_BASELINE` eligibility, cereal-start avoidance | `pest_disease_disruption` (`PARTIAL` vs `SCORED`) | `completeness_score`, `crop_history_records`, `critical_data_adequacy` |
| `preferences.forage_value_weight` (`null`, `0.0`, `>0`) + core weights | `[0.0, 1.0]` check, custom all-zero core rejection (422) | `forage_value_weight` completeness flag (`NOT_PROVIDED` vs `PROVIDED`) | `RULE_FORAGE_PRIORITY_ALIGNMENT` | `SELECTION` prioritization of `VETCH_OAT` candidate when active | `_resolve_weights` (preserves `DEFAULT_FARMER_WEIGHTS` if core omitted), `forage_value` (`NOT_APPLICABLE` vs `SCORED`), single normalization | `ranking_methodology`, `data_quality` completeness |
| `preferences.equipment_constraints` (`null`, `[]`, KB tags, unmodeled tags) | String list or `null` | `equipment_constraints` completeness flag | `_eval_equipment_constraints`: KB hits -> `WARNING`, `[]` -> `PASS`, `null` -> `UNKNOWN`, unmodeled -> `UNKNOWN` | Evaluated per strategy slot & recorded in observed inputs | `farmer_priority_fit` (`0.75` for `UNKNOWN`, `PARTIAL` for null or unmodeled tags) | `[UNSUPPORTED_EQUIPMENT_TAG]` warning & `missing_data` notice |
| `preferences.target_crop_ids` & `excluded_crop_ids` | Intersection rejected (`422 TARGET_EXCLUDED_CROP_CONFLICT`) | Normalized lists & flags | `excluded` & target eligibility evaluated per slot | Blueprint inclusion, counterfactuals for infeasible targets, exclusion filtering | `farmer_priority_fit` target hit ratio & `0.0` score if excluded | `requested_crop_results` (`selected`, `excluded`, `unavailable_due_to_insufficient_evidence`) |

---

## 3. Immutable Baseline Invariants

Across every operational input permutation (`water`, `crop_history`, `forage_value_weight`, `equipment_constraints`, `target_crop_ids`, `excluded_crop_ids`), the following extracted layers remain **100% invariant**:
- Parcel geometry, `area_ha` (`23.8605`), commune (`Belkheir`), and Wilaya overlap (`100.0%`).
- `SoilGrids V6 (250 m)` physical/chemical extractions and quarantined `nitrogen_0_30cm` status.
- `ESA WorldCereal Crop Frequency (2021–2025)` (`0.9253`).
- `GPM (~11 km)` & `NASA POWER (~55 km)` climate averages and spring SMAP root-zone moisture.
- `Sentinel-2 (10 m)` NDVI (`0.5386`) and unavailable local DEM flag (`UNAVAILABLE_NOT_INTEGRATED`).
