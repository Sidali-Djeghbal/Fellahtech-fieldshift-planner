# Phase O — Minimal Targeted Fixes Changelog

**Principle:** Implement the smallest justified corrections across Tasks 7–8 without inventing agronomic coefficients, weakening hard constraints, or altering baseline geospatial semantics.

---

## Summary of Implemented Fixes (Fixes 1–6)

### FIX 1 — Support `water.source = "unknown"` Conservatively
- **`field_input_schema.json`, `src/api/schemas.py`, `field_profile_builder.py`, `db/schema_postgis.sql`, `frontend/index.html`:**
  - Added `"unknown"` to `water.source` allowed enum/CHECK/UI selector while keeping `"other"` distinct.
  - Updated `_build_quality_and_clarifications()` in `field_profile_builder.py` to emit `Q_WATER_MATERIAL` whenever `water.source == "unknown"`.
- **`src/agronomic/constraint_engine.py`, `src/rotation/candidate_generator.py`, `src/optimization/scoring_engine.py`:**
  - `_eval_water_irrigation_gate()`: Treats `src == "unknown"` identically to `avail == "unknown"` for `STRICTLY_IRRIGATED` (`UNKNOWN`) and conservatively rainfed for `RAINFED_OR_SUPPLEMENTAL` (`PASS`).
  - `_eval_precipitation_regime()`, `_eval_soil_moisture()`, `evaluate_crop_sequence()`, and `generate_rotation_candidates()` (`irrig_eligible`): Require non-rainfed and non-unknown `source` and `irrigation_system` so `"unknown"` never activates irrigation assumptions.
  - `_eval_salinity_unmeasured()`: Treats `src == "unknown"` (unless `sys == "none"`) as `UNKNOWN` rather than falsely returning `"Rainfed parcel" PASS`.
  - `_eval_water_efficiency()` (`scoring_engine.py`): Marks `STRICTLY_IRRIGATED` as `UNKNOWN` (`score=None`) and rainfed evaluations as `PARTIAL` when water source/system/availability is `"unknown"`.

### FIX 2 — Reconcile `equipment_constraints` Between UI, API & Knowledge Base
- **`frontend/index.html`:** Replaced unmodeled `no_sprayer` and `no_harvester` select options with the 6 tags actually defined in `agronomic_knowledge/crop_profiles.json` (`no_hay_baler`, `no_mower`, `no_drip_irrigation`, `no_precision_planter`, `no_potato_harvester`, `no_sunflower_header`).
- **`src/agronomic/constraint_engine.py`:** Updated `_eval_equipment_constraints()` to compute `known_kb_tags` from `kb.crops` and track `unmodeled = sorted(set(eq_list) - known_kb_tags)`. Supported tag conflicts continue to return `WARNING`, while unmodeled API tags return `UNKNOWN` (with `unsupported_equipment_tags` in `observed_inputs`) rather than falsely coercing to `PASS`. No tags were mapped across distinct machinery types.
- **`src/optimization/scoring_engine.py`, `src/output/recommendation_builder.py`:** `_eval_farmer_priority_fit()` marks strategies with `unsupported_equipment_tags` as `PARTIAL` (`0.75` slot readiness, uniform across all strategies), and `data_quality` surfaces explicit `[UNSUPPORTED_EQUIPMENT_TAG]` notices in `warnings` and `missing_data`.

### FIX 3 — Preserve Default Core Weights When `forage_value_weight` Is Supplied Alone
- **`src/optimization/scoring_engine.py`:** Extracted `_resolve_farmer_weights_from_mapping()` in `_resolve_weights()`. When all 4 core weights (`water_saving_weight`, `soil_improvement_weight`, `income_weight`, `risk_reduction_weight`) are omitted (`None`), they preserve `DEFAULT_FARMER_WEIGHTS` (`0.25, 0.30, 0.20, 0.25`) instead of collapsing to `0.0`. Both `forage_value_weight = 0.0` (`NOT_APPLICABLE`) and positive `forage_value_weight` work cleanly alongside default core weights; explicit custom core weights totaling `0.0` still raise `ValueError` -> `422 INVALID_PRIORITY_WEIGHTS`. Also fixed `rank_rotation_candidates()` `forage_flag` handling when `priority_weights` overrides `field_profile`.
- **`field_profile_builder.py`:** Added zero-total guard in `validate_farmer_input()` when custom core weights are supplied without positive weights (`INVALID_PRIORITY_WEIGHTS`).
- **`frontend/app.js`:** Removed hardcoded non-default weight overrides (`0.15/0.20/0.05/0.15` and `0.25/0.30/0.20/0.25`) so the UI serializes only `forage_value_weight`, achieving exact Frontend/API parity.

### FIX 4 — Canonical Chronological `crop_history` Predecessor Semantics
- **`src/agronomic/temporal_planning.py`:** Added `SEASON_RANK`, `season_sort_key()`, `season_ordinal()`, and `assess_crop_history_completeness()`. Enforced strict pre-start validation (`h_ord >= start_ord`) across planning modes (`CROP_HISTORY_AFTER_PLANNING_START`), rejecting both future and concurrent history records.
- **`field_profile_builder.py`, `src/agronomic/constraint_engine.py`, `src/rotation/candidate_generator.py`:** Unified all three modules around `assess_crop_history_completeness()`. Emits distinct `NOT_PROVIDED`, `EXPLICITLY_CONFIRMED_EMPTY`, `PROVIDED_PARTIAL`, and `PROVIDED_COMPLETE` states without inventing missing years or skipping recent unresolved records. Updated `Q_LAST_CROP_MATERIAL` follow-up logic and `SEQ_10` predecessor lookup to recognize intra-year campaigns (`Winter`, `Spring`, `Summer 2026` prior to `Autumn 2026`).
- **`src/output/recommendation_builder.py`, `db/schema_postgis.sql`:** Updated completeness checks and SQL `CHECK` constraint on `crop_history_flag` to include `PROVIDED_PARTIAL` and `PROVIDED_COMPLETE`.

### FIX 5 — Explicit Validation for `target_crop_ids ∩ excluded_crop_ids` Conflicts
- **`field_profile_builder.py`, `src/api/pipeline_service.py`:** Added `validate_target_excluded_conflict()` and enforced it in both `validate_farmer_submission()` and `run_field_analysis_pipeline()`. Conflicting crop IDs now trigger `FarmerInputValidationError(..., error_code="TARGET_EXCLUDED_CROP_CONFLICT", details={"conflicting_crop_ids": overlap})` -> HTTP `422`.

### FIX 6 — Unified HTTP 422 JSON Contract Across All Validation Handlers
- **`src/api/app.py`, `frontend/app.js`, `tests/test_phaseL_api.py`:** Replaced duplicated `HTTPException(status_code=422, detail=...)` blocks in `/api/v1/fields/validate` and `/api/v1/fields/analyze` with shared `_value_error_422_response(exc)`, returning top-level `{"error_code", "message", "details"}` consistently across all `422` errors. Updated UI error extraction and aligned `tests/test_phaseL_api.py` assertions (`detail` wrapper removal + explicit all-zero provided weights).
