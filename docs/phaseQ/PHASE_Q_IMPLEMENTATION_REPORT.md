# Field Shift — Phase Q Implementation & Verification Report

## 1. Executive Summary

Phase Q remediated all verified software, schema, validation, and decision-gating defects identified during the Phase P audit (`CRITICAL-01`, `CRITICAL-02`, `HIGH-01`, `MEDIUM-01`, and the `MEDIUM-02` coordinate-order and readiness-gating defect) without redesigning the agronomic scoring model, altering `DEFAULT_FARMER_WEIGHTS`, weakening agronomic rules, introducing ML, fabricating field measurements, or modifying `docs/phaseP/`.

**Verification Summary (Post-Final-Edit):**
- **Complete Repository Test Suite (`./venv/bin/python -m unittest discover -s tests -v`):** **114 passed, 0 failed, 0 skipped** (`91` existing tests + `23` new Phase Q regression tests in `tests/test_phaseQ_remediation.py`, executed in `839.702s`).
- **63-Scenario Controlled Comparison (`PHASE_Q_BEFORE_AFTER_COMPARISON.csv`):** All **9** targeted defect/gap scenarios transitioned cleanly to expected remediated behavior; all **54** invariant reference, perturbation, and real-parcel scenarios remained **100% preserved** (`PRESERVED_INVARIANT`).
- **`docs/phaseP/` Preservation:** Confirmed untouched (`git status --short`).

---

## 2. Remediated Defects & Implementation Details

### Task 1 — `CRITICAL-01`: Soil pH Output Schema & API Exception Handling Failure

**Root Cause (Phase P):**
1. Soft agronomic rule `RULE_SOIL_PH_SUITABILITY` failing a slot caused Phase G/H to assign strategy status `"INFEASIBLE_CONSTRAINT"` (keeping `HARD_CONSTRAINT` distinct as `"INFEASIBLE_HARD_CONSTRAINT"`), but `schemas/final_recommendation_output.schema.json` and `src/output/output_validator.py` omitted `"INFEASIBLE_CONSTRAINT"`, triggering `OutputValidationError`.
2. In `src/api/app.py`, `OutputValidationError` and `TemporalPlanningError` (subclasses of `ValueError`) were intercepted by a broad `except ValueError` block before reaching dedicated exception handlers, turning internal output validation failures into misleading HTTP `422` errors.

**Implemented Remediation:**
- [src/agronomic/constraint_engine.py](file:///home/lokman/Desktop/FeildShit-SI-Model/src/agronomic/constraint_engine.py#L691-L719) & [L1065-L1102](file:///home/lokman/Desktop/FeildShit-SI-Model/src/agronomic/constraint_engine.py#L1065-L1102): Exposed explicit `soft_fail_rules` and `soft_fail_reasons` while preserving the hard vs. soft distinction (`"INFEASIBLE_HARD_CONSTRAINT"` vs. `"INFEASIBLE_CONSTRAINT"`).
- [src/rotation/candidate_generator.py](file:///home/lokman/Desktop/FeildShit-SI-Model/src/rotation/candidate_generator.py#L669-L676): Propagated `soft_fail_reasons` into candidate evaluation objects alongside SoilGrids topsoil adequacy fields (`clay_0_30cm_coverage_pct`, `clay_0_30cm_quality_status`).
- [schemas/final_recommendation_output.schema.json](file:///home/lokman/Desktop/FeildShit-SI-Model/schemas/final_recommendation_output.schema.json#L182-L191): Added `"INFEASIBLE_CONSTRAINT"` to `StrategyItem.feasibility_status.enum`.
- [src/output/output_validator.py](file:///home/lokman/Desktop/FeildShit-SI-Model/src/output/output_validator.py#L12): Added `"INFEASIBLE_CONSTRAINT"` to `INFEASIBLE_STATUSES`.
- [src/optimization/scoring_engine.py](file:///home/lokman/Desktop/FeildShit-SI-Model/src/optimization/scoring_engine.py#L1339-L1352) & [src/output/recommendation_builder.py](file:///home/lokman/Desktop/FeildShit-SI-Model/src/output/recommendation_builder.py#L310-L570): Rendered `soft_fail_reasons` in excluded strategy explanations and target-crop infeasibility diagnostics.
- [src/api/app.py](file:///home/lokman/Desktop/FeildShit-SI-Model/src/api/app.py#L114-L138) & [L181-L219](file:///home/lokman/Desktop/FeildShit-SI-Model/src/api/app.py#L181-L219): Re-raised `OutputValidationError` and `TemporalPlanningError` before `except ValueError` so `OutputValidationError` maps to HTTP `500` (`INTERNAL_OUTPUT_VALIDATION_ERROR`) and `TemporalPlanningError` maps to HTTP `422` (`PAST_PLANNING_SEASON`).
- [frontend/app.js](file:///home/lokman/Desktop/FeildShit-SI-Model/frontend/app.js#L267-L304): Added UI badge handling for `"INFEASIBLE_CONSTRAINT"`.

**Verified Regression Scenarios:**
- `SG-PH-8.6`, `SG-PH-9.1`: `HTTP 500 -> HTTP 200` (schema-valid `decision_status = "INFEASIBLE"`, `eligible = 0`, `infeasible = 4` all with `INFEASIBLE_CONSTRAINT`).
- `SG-PH-7.8-DRIP-TOMATO`: `HTTP 500 -> HTTP 200` (schema-valid `decision_status = "REQUIRES_LOCAL_VERIFICATION"`, `STRAT_IRRIGATED_CASH` excluded cleanly as `INFEASIBLE_CONSTRAINT`, `4` eligible strategies ranked, `STRAT_SOIL_IMPROVEMENT` endorsed at `0.845644`).
- `test_05` & `test_06`: Actual hard constraint failure (`TOMATO_IND` under rainfed) preserves `"INFEASIBLE_HARD_CONSTRAINT"`, and API `OutputValidationError` returns HTTP `500`.

---

### Task 2 — `CRITICAL-02`: Single-Source Critical Data Adequacy Enforcement

**Root Cause (Phase P):**
1. Decision-gating adequacy checks were duplicated between Phase I scoring and Phase J recommendation output building, creating drift risk.
2. When `SoilGrids` failed (`coverage = 0%` / `clay_0_30cm is None`) on polygons with `wilaya_overlap = 95%` or `crop_frequency = 0.20`, `critical_data_adequacy.adequacy_status` became `"INSUFFICIENT"` while `decision_status` stayed `"REQUIRES_LOCAL_VERIFICATION"` and still endorsed a winner.

**Implemented Remediation:**
- [src/agronomic/data_adequacy.py](file:///home/lokman/Desktop/FeildShit-SI-Model/src/agronomic/data_adequacy.py#L23-L247) & [src/agronomic/__init__.py](file:///home/lokman/Desktop/FeildShit-SI-Model/src/agronomic/__init__.py): Extracted one shared source of truth defining `BLOCKING_ADEQUACY_STATUSES = ("INSUFFICIENT", "NOT_ASSESSABLE")`, `compute_data_completeness_score()`, and `assess_critical_data_adequacy()`. Any blocking status (`clay_0_30cm is None`, SoilGrids masked/unavailable, `polygon_coverage_pct < 25%`, or missing both GPM+POWER precipitation) is detected uniformly.
- [src/optimization/scoring_engine.py](file:///home/lokman/Desktop/FeildShit-SI-Model/src/optimization/scoring_engine.py#L1205-L1291) & [L1382](file:///home/lokman/Desktop/FeildShit-SI-Model/src/optimization/scoring_engine.py#L1382): Invokes `assess_critical_data_adequacy()` and, when `adequacy_status in BLOCKING_ADEQUACY_STATUSES`, forces `decision_status = "EXPLORATORY_ONLY"`, `recommendation_status = "EXPLORATORY_ONLY"`, `endorsed_recommendation_id = None`, `provisional_only = True`, and `provisional = True` on all strategies while preserving candidate diagnostic scores and `exploratory_candidate_id`.
- [src/output/recommendation_builder.py](file:///home/lokman/Desktop/FeildShit-SI-Model/src/output/recommendation_builder.py#L310-L570): Delegates strictly to `assess_critical_data_adequacy()` and `compute_data_completeness_score()`, eliminating duplicate adequacy logic.
- [src/output/output_validator.py](file:///home/lokman/Desktop/FeildShit-SI-Model/src/output/output_validator.py#L205-L219): Added semantic invariant rejecting any payload where `critical_data_adequacy.adequacy_status in BLOCKING_ADEQUACY_STATUSES` yet `endorsed_recommendation_id is not None` or `decision_status not in ("EXPLORATORY_ONLY", "INFEASIBLE", "NO_RECOMMENDATION")`.

**Verified Regression Scenarios:**
- `SG-GAP-PARTIAL-WILAYA` (`SoilGrids cov=0%`, `Wilaya overlap=95%`) & `SG-GAP-LOW-CF` (`SoilGrids cov=0%`, `cf=0.20`): `decision_status` transitioned `REQUIRES_LOCAL_VERIFICATION -> EXPLORATORY_ONLY`, `endorsed_strategy_id` transitioned `STRAT_SOIL_IMPROVEMENT -> NONE`, while exploratory top candidate `STRAT_SOIL_IMPROVEMENT (0.879238)` was preserved diagnostically.
- `LU-CF-015` / Belkheir `PARTIAL`: Verified distinct from `INSUFFICIENT`, preserving `REQUIRES_LOCAL_VERIFICATION`.
- `test_10` & `test_11`: `NOT_ASSESSABLE` missing climate gates to `EXPLORATORY_ONLY` (`endorsed_recommendation_id = None`), and validator rejects desynchronized payloads.

---

### Task 3 — `HIGH-01`: Unsupported `income_weight` Without Economic Data

**Root Cause (Phase P):**
1. When a farmer submitted `preferences = {"income_weight": 0.8}` with core weights omitted, omitted core weights were zeroed out because a custom preference key was present; since `income_potential = UNKNOWN` without farmgate `economic_data`, `active_weight_sum` collapsed to `0.0` and returned `NO_RECOMMENDATION`.
2. When `income_weight` was combined with core weights (e.g., `0.70` income + `0.10` each core), it was silently normalized to `0.0` weight without explicit warning.

**Implemented Remediation:**
- [src/optimization/scoring_engine.py](file:///home/lokman/Desktop/FeildShit-SI-Model/src/optimization/scoring_engine.py#L259) (`_resolve_weights`) & [L1059-L1132](file:///home/lokman/Desktop/FeildShit-SI-Model/src/optimization/scoring_engine.py#L1059-L1132): Added two-pass `income_scorable` check before resolving weights:
  - When `income_scorable=False` and core weights were omitted (`{"income_weight": 0.8}`), default scorable core weights (`water=0.25, soil=0.30, risk=0.25`) are preserved (`income_weight_status = "IGNORED_UNAVAILABLE_ECONOMIC_DATA_DEFAULT_CORE_PRESERVED"`).
  - When `income_scorable=False` and core weights were supplied alongside `income_weight > 0`, core weights renormalize (`"IGNORED_UNAVAILABLE_ECONOMIC_DATA_RENORMALIZED"`).
  - Explicit warnings are emitted into `ranking_methodology.weight_warnings` and `inactive_objectives_audit.income_potential.reason = "INCOME_POTENTIAL_UNAVAILABLE_WITHOUT_ECONOMIC_DATA"`.
- [src/output/recommendation_builder.py](file:///home/lokman/Desktop/FeildShit-SI-Model/src/output/recommendation_builder.py#L310-L570): Surfaces `[INCOME_WEIGHT_IGNORED_UNAVAILABLE_ECONOMIC_DATA]` warnings in `data_quality.warnings`.
- [frontend/index.html](file:///home/lokman/Desktop/FeildShit-SI-Model/frontend/index.html#L131-L137) & [frontend/app.js](file:///home/lokman/Desktop/FeildShit-SI-Model/frontend/app.js#L267-L304): Added UI disclosure noting `income_weight` requires verified farmgate economic data and renders returned `weight_warnings` prominently.

**Verified Regression Scenarios:**
- `FRM-WT-INCOME-ALONE` (`income_weight = 0.80`, core omitted): Transitioned `NO_RECOMMENDATION -> REQUIRES_LOCAL_VERIFICATION`, endorsed `STRAT_SOIL_IMPROVEMENT (0.879238)`, emitted `income_weight_status = "IGNORED_UNAVAILABLE_ECONOMIC_DATA_DEFAULT_CORE_PRESERVED"`, `weight_warnings_count = 1`.
- `FRM-WT-INCOME-MIXED` (`water=0.1, soil=0.1, risk=0.1, income=0.7`): Emits `"IGNORED_UNAVAILABLE_ECONOMIC_DATA_RENORMALIZED"` and explicit warning (`STRAT_SOIL_IMPROVEMENT = 0.883925`).
- `test_14`–`test_16`: Confirmed real `economic_data` activates `income_potential`, solo `forage_value_weight` emits no income warning, and all-zero custom weights still return HTTP `422` (`INVALID_PRIORITY_WEIGHTS`).

---

### Task 4 — `MEDIUM-01`: Equipment Constraint Warning Scoring Paradox

**Root Cause (Phase P):**
In `_eval_farmer_priority_fit`, `UNKNOWN` equipment slots scored `0.75` (`0.375` weighted by `0.5`), while declaring an equipment limitation (`["no_hay_baler"]`) upgraded unaffected cereal/pulse slots from `UNKNOWN (0.75)` to `PASS (1.00)` and averaged the `WARNING (0.45)` slot against them—raising `farmer_priority_fit` (`0.825 -> 0.8583`) and total score above the `UNKNOWN` baseline.

**Implemented Remediation:**
- [src/optimization/scoring_engine.py](file:///home/lokman/Desktop/FeildShit-SI-Model/src/optimization/scoring_engine.py#L809-L917) (`_eval_farmer_priority_fit` & `_ops_slot_score`):
  - Separated `(w_st, e_st)` state scoring (`PASS/PASS=1.0`, `PASS/UNKNOWN=0.75`, `PASS/WARNING=0.35`, `FAIL=0.0`).
  - Applied an asymmetric bottleneck penalty across `warn_indices`:
    `ops_factor = max(0.0, min(0.50 * mean_slot + 0.50 * min_warn_slot, mean_unk_baseline - 0.05 * len(warn_indices)))`,
    ensuring explicit modeled machinery warnings always score strictly below the corresponding `UNKNOWN` (`null`) baseline.

**Verified Regression Scenarios:**
- `FRM-EQ-NO-HAY-BALER`: `top_pref_fit` dropped `0.8583 -> 0.7333` (strictly below `0.825` `UNKNOWN` baseline) and top composite score dropped `0.88288 -> 0.869208`.
- `FRM-EQ-NO-DRIP-POTATO`: Unaffected forage strategy (`VETCH_OAT`) improved cleanly (`0.95` vs `0.825`) while the affected `STRAT_IRRIGATED_CASH` strategy dropped strictly below its `UNKNOWN` baseline (`test_18`).
- `FRM-EQ-UNMODELED` (`['no_sprayer', 'manual_only']`): Preserves `UNKNOWN` (`0.825`) with explicit unsupported-tag disclosure (`test_19`).

---

### Task 5 — `MEDIUM-02`: Water Balance Coordinate-Order & Strict Gating Fix

**Root Cause (Phase P):**
`FieldGeospatialProcessor` emits `spatial_validation.centroid_lon_lat` in `[lon, lat]` order, whereas `water_balance.py` looked for `"centroid_lat_lon"` (producing `latitude_deg = None` in every real parcel run), and checked `bool(kc_coverage)` rather than verifying `COMPLETE_KC_AND_STAGE_LENGTHS`.

**Implemented Remediation:**
- [src/optimization/water_balance.py](file:///home/lokman/Desktop/FeildShit-SI-Model/src/optimization/water_balance.py#L156-L188) (`_extract_centroid_latitude_deg`): Resolves explicit `hydro_override` first, then GeoJSON-ordered `centroid_lon_lat[1]`, then legacy `centroid_lat_lon`, enforcing `math.isfinite(val)` and `-90.0 <= val <= 90.0`.
- [src/optimization/water_balance.py](file:///home/lokman/Desktop/FeildShit-SI-Model/src/optimization/water_balance.py#L285-L299) (`assess_water_balance_readiness`): Enforces `has_complete_kc = any(v == "COMPLETE_KC_AND_STAGE_LENGTHS" for v in kc_coverage.values())` alongside `not missing_stage_crops`, `et0_mm_day`, `eff_precip_mm`, `PROVIDED_LOCAL_FC_PWP`, and irrigation `Ea` for `COMPUTED_FULL`.

**Verified Regression Scenarios:**
- All real parcel runs now report exact parcel latitudes in `wb_latitude_deg`: `36.472` (Belkheir North), `36.445` (Peri-Urban), `36.4645` (Bouchecouf), and `36.13` (Tamlouka).
- `test_20`–`test_22`: Verified `[lon, lat]` extraction, legacy fallback & invalid latitude bounds (`lat > 90` / `NaN`), and strict `COMPUTED_FULL` gating.

---

## 3. Complete Verification Matrix (Post-Final-Edit)

### Test Suite Results (`./venv/bin/python -m unittest discover -s tests -v`)
- **Total Executed:** **114 tests** in **839.702s**
- **Result:** **OK** (`114` passed, `0` failures, `0` errors, `0` skipped)
  - Existing Phases (A–O): **91 tests passed** (`test_field_profile`: 5, `test_phaseD_integration`: 5, `test_phaseF_audit`: 10, `test_phaseG_knowledge`: 11, `test_phaseH_candidate_generator`: 10, `test_phaseI_scoring`: 10, `test_phaseJ_output`: 8, `test_phaseK_validation`: 5, `test_phaseL_api`: 7, `test_phaseM_pilot`: 7, `test_phaseN_hardening`: 7, `test_phaseO_input_sensitivity`: 6).
  - Phase Q Remediation Suite ([tests/test_phaseQ_remediation.py](file:///home/lokman/Desktop/FeildShit-SI-Model/tests/test_phaseQ_remediation.py)): **23 tests passed** (`test_01`..`test_23`).

### 63-Scenario Controlled Comparison Summary
See full tables in [PHASE_Q_REGRESSION_RESULTS.csv](file:///home/lokman/Desktop/FeildShit-SI-Model/docs/phaseQ/PHASE_Q_REGRESSION_RESULTS.csv) and [PHASE_Q_BEFORE_AFTER_COMPARISON.csv](file:///home/lokman/Desktop/FeildShit-SI-Model/docs/phaseQ/PHASE_Q_BEFORE_AFTER_COMPARISON.csv):
- **9/9 target scenarios remediated:** `SG-GAP-PARTIAL-WILAYA`, `SG-GAP-LOW-CF`, `SG-PH-8.6`, `SG-PH-9.1`, `SG-PH-7.8-DRIP-TOMATO`, `FRM-WT-INCOME-ALONE`, `FRM-WT-INCOME-MIXED`, `FRM-EQ-NO-HAY-BALER`, `FRM-EQ-NO-DRIP-POTATO`.
- **54/54 invariant scenarios preserved:** Zero unintended score, rank, feasibility, or gate drift (`PRESERVED_INVARIANT`).
