# Phase O — Regression Test & Final Verification Report

## 1. Test Execution Summary

After completing all Phase O source, schema, database DDL, frontend, and test updates, the complete repository regression suite was executed in `/home/lokman/Desktop/FeildShit-SI-Model`:

- **Command:** `/home/lokman/Desktop/FeildShit-SI-Model/venv/bin/python -m unittest discover -s tests -v`
- **Result:** `Ran 91 tests in 332.639s` — **`OK`** (`Command exited with code 0`)
- **Failures / Errors / Skips:** `0` failures, `0` errors, `0` skipped tests.
- **Warning Observed (non-failing dependency deprecation):** `StarletteDeprecationWarning` from `fastapi/testclient.py` (`Using httpx with starlette.testclient is deprecated; install httpx2 instead.`).

## 2. Suite Breakdown by Test Module (91 Total Tests)

| Test Module | Test Class | Count | Status |
| :--- | :--- | :---: | :--- |
| `tests/test_field_profile.py` | `TestFieldInputAndProfile` | 5 | Pass (`ok`) |
| `tests/test_phaseD_integration.py` | `TestPhaseDIntegration` | 5 | Pass (`ok`) |
| `tests/test_phaseF_audit.py` | `TestPhaseFAudit` | 10 | Pass (`ok`) |
| `tests/test_phaseG_knowledge.py` | `TestPhaseGKnowledgeAndConstraints` | 11 | Pass (`ok`) |
| `tests/test_phaseH_candidate_generator.py` | `TestPhaseHCandidateGenerator` | 10 | Pass (`ok`) |
| `tests/test_phaseI_scoring.py` | `TestPhaseIMultiObjectiveScoring` | 10 | Pass (`ok`) |
| `tests/test_phaseJ_output.py` | `TestPhaseJOutputEngine` | 8 | Pass (`ok`) |
| `tests/test_phaseK_validation.py` | `TestPhaseKScientificValidation` | 5 | Pass (`ok`) |
| `tests/test_phaseL_api.py` | `TestPhaseLApplicationIntegration` | 7 | Pass (`ok`) |
| `tests/test_phaseM_pilot.py` | `PhaseMPilotContractTests` | 7 | Pass (`ok`) |
| `tests/test_phaseN_hardening.py` | `TestPhaseNHardening` | 7 | Pass (`ok`) |
| `tests/test_phaseO_input_sensitivity.py` | `TestPhaseOAPIFixesAndInvariance`, `TestPhaseOUnitFixes` | 6 | Pass (`ok`) |
| **Total** | | **91** | **All Pass (`OK`)** |

## 3. Phase O Regression Tests (`tests/test_phaseO_input_sensitivity.py`)

The 6 new Phase O tests in `tests/test_phaseO_input_sensitivity.py` verify both unit-level scientific invariants and end-to-end FastAPI `/validate` + `/analyze` behavior using isolated in-memory SQLite state:

1. `TestPhaseOUnitFixes.test_01_water_source_unknown_accepted_distinct_and_conservative`
   - Verifies Fix 1: `water.source = "unknown"` is accepted by schema/profile building, kept distinct from `"other"` and `"rainfed_only"`, never implies irrigation supply, and preserves conservative gating/scores.
2. `TestPhaseOUnitFixes.test_02_equipment_constraints_kb_alignment_and_unsupported_tags`
   - Verifies Fix 2: KB equipment tags (`no_hay_baler`, `no_mower`, `no_drip_irrigation`, `no_precision_planter`, `no_potato_harvester`, `no_sunflower_header`) drive modeled suitability/fit, while unmodeled tags (e.g., `no_sprayer`, `no_harvester`) evaluate to `UNKNOWN` (never coerced to `PASS`) with `PARTIAL` priority fit and explicit warning/missing-data disclosure.
3. `TestPhaseOUnitFixes.test_03_forage_weight_and_core_weight_preservation`
   - Verifies Fix 3: Omitting core objective weights while supplying `forage_value_weight` (`0.0` or `> 0`) preserves `DEFAULT_FARMER_WEIGHTS` without zeroing omitted core objectives, treats `forage_value_weight = 0.0` as inactive (`NOT_APPLICABLE`) vs `null` (`NOT_PROVIDED`), normalizes once in Phase I, and rejects explicit all-zero custom weights (`INVALID_PRIORITY_WEIGHTS`).
4. `TestPhaseOUnitFixes.test_04_crop_history_chronological_order_and_completeness_states`
   - Verifies Fix 4: `crop_history` uses canonical `SEASON_ORDER` chronology (`Winter < Spring < Summer < Autumn`) via `season_ordinal`/`assess_crop_history_completeness`, classifies `NOT_PROVIDED` / `EXPLICITLY_CONFIRMED_EMPTY` / `PROVIDED_PARTIAL` / `PROVIDED_COMPLETE`, avoids fabricating missing periods, and rejects concurrent/future entries relative to planning start (`CROP_HISTORY_AFTER_PLANNING_START`).
5. `TestPhaseOAPIFixesAndInvariance.test_01_standardized_422_conflicts_and_temporal_errors`
   - Verifies Fixes 3, 4, 5, and 6 on HTTP `422` responses: overlapping `target_crop_ids` and `excluded_crop_ids` (`TARGET_EXCLUDED_CROP_CONFLICT`), future/concurrent `crop_history` (`CROP_HISTORY_AFTER_PLANNING_START`), explicit all-zero custom priority weights (`INVALID_PRIORITY_WEIGHTS`), and uniform top-level `{"error_code", "message", "details"}` error envelopes without nested `"detail"` wrappers.
6. `TestPhaseOAPIFixesAndInvariance.test_02_api_water_unknown_equipment_forage_history_determinism_and_invariance`
   - Verifies Fixes 1–4 end-to-end through `/analyze` plus geospatial invariance (`field_profile` immutability across farmer-input variations) and deterministic reproducibility.

## 4. Compatibility Update in Existing API Tests (`tests/test_phaseL_api.py`)

`tests/test_phaseL_api.py` (lines 179 and 230–239) received minimal updates to match the unified HTTP `422` contract (`error_code` at top level without `"detail"` wrapper) and explicit all-zero custom weight validation, without relaxing scientific assertions. All 7 tests in `TestPhaseLApplicationIntegration` pass under the final run. All 10 tests in `TestPhaseHCandidateGenerator` (including `test_excluded_and_target_crop_handling_and_precedence`) also remain intact and passing.

## 5. Post-Fix 50-Scenario Re-Audit Summary

Running the isolated FastAPI TestClient re-audit across all 50 scenarios (39 unique scenario payloads including Baseline + water, history, forage/weight, equipment, target/excluded conflict, and determinism scenarios):

- **Total scenarios executed:** `50` (`47` HTTP `200`, `3` HTTP `422`)
- **Unified 422 failures (`non_unified_422`):** `[]` (0 failures)
  - `B2g_hist_concurrent_2026_422` -> `CROP_HISTORY_AFTER_PLANNING_START`
  - `C4_all_zero_core_weights_422` -> `INVALID_PRIORITY_WEIGHTS`
  - `E4_target_and_exclude_faba` -> `TARGET_EXCLUDED_CROP_CONFLICT` (`conflicting_crop_ids=['FABA_BEAN']`)
- **Geospatial invariance failures (`invariance_failures`):** `[]` across all 47 HTTP `200` runs
- **Output schema validation failures (`schema_failures`):** `[]`
- **Pipeline mutation of extracted `field_profile` (`field_profile_mutated_by_pipeline`):** `False`
- **Baseline (`BASE`) verified metrics:**
  - `analysis_id`: `ANAL_241B50895CE3FED6`
  - Top strategy: `STRAT_SOIL_IMPROVEMENT` (`top_score = 0.879238`, `ranking_margin = 0.04176`, `stability_index = 1.0`)
  - `completeness_score = 0.8846`, `critical_data_adequacy = PARTIAL`, `decision_gate = REQUIRES_LOCAL_VERIFICATION`
