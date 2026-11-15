# Phase L — Integration & Regression Test Report

> **Test Runner:** `PYTHONPATH=. /home/lokman/Desktop/FeildShit-SI-Model/venv/bin/python -m unittest discover -s tests -v`  
> **Result Observed:** **`Ran 71 tests in 223.656s — OK`** (`0` failures, `0` errors, `0` skipped tests)

---

## 1. Test Execution Breakdown

| Test Suite File | Phase Scope | Tests Executed | Outcome |
|---|---|---:|---|
| [`tests/test_phaseD_integration.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/tests/test_phaseD_integration.py) | Phase D Spatial Alignment & Leakage Guards | `5` | `OK` |
| [`tests/test_field_profile.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/tests/test_field_profile.py) | Farmer Input Contract & Field Profile Builder | `5` | `OK` |
| [`tests/test_phaseF_audit.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/tests/test_phaseF_audit.py) | Phase F Scientific & Geospatial Audit | `10` | `OK` |
| [`tests/test_phaseG_knowledge.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/tests/test_phaseG_knowledge.py) | Phase G Knowledge Base & Constraint Engine | `11` | `OK` |
| [`tests/test_phaseH_candidate_generator.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/tests/test_phaseH_candidate_generator.py) | Phase H Candidate Generator | `10` | `OK` |
| [`tests/test_phaseI_scoring.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/tests/test_phaseI_scoring.py) | Phase I Multi-Objective Scoring & Pareto | `10` | `OK` |
| [`tests/test_phaseJ_output.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/tests/test_phaseJ_output.py) | Phase J Output Contract & Validator | `8` | `OK` |
| [`tests/test_phaseK_validation.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/tests/test_phaseK_validation.py) | Phase K Backtest, Stress & Scorecard Validation | `5` | `OK` |
| [`tests/test_phaseL_api.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/tests/test_phaseL_api.py) | Phase L FastAPI Endpoints, Persistence & UI Integration | `7` | `OK` |
| **Total** | **Full End-to-End Regression Suite** | **`71`** | **`OK`** |

---

## 2. Section 8 Scenario Coverage Checklist (`test_phaseL_api.py`)

| # | Required Integration Scenario | Verified API / DB Behavior Observed | Test Method |
|---:|---|---|---|
| 1 | **Valid field submission & retrieval** | `POST /api/v1/fields/validate` -> `200`; `POST /api/v1/fields/analyze` -> `200`; `GET /api/v1/analyses/{id}` replays exact stored JSON; all `8` SQLite entities receive rows (`>= 1`) | `test_02_valid_field_submission_persistence_retrieval_and_schema` |
| 2 | **Invalid Polygon rejection** | Bowtie self-intersection, out-of-Wilaya polygon, `MultiPolygon`, and forbidden technical keys (`soil_ph`) all rejected with HTTP `422` | `test_03_invalid_polygons_and_forbidden_technical_fields_rejected` |
| 3 | **Missing optional inputs** | Omitting `crop_history` and `preferences` succeeds (`200`) with `NOT_PROVIDED` completeness flags | `test_04_missing_optional_inputs_and_null_vs_empty_list_distinction` |
| 4 | **`null` versus `[]` behavior** | Preserves `"crop_history": null` / `"equipment_constraints": null` as `NOT_PROVIDED` vs `[]` as `EXPLICITLY_CONFIRMED_EMPTY` and `forage_value_weight: 0.0` as `PROVIDED`; rejects all-zero priority weights cleanly (`422 INVALID_PRIORITY_WEIGHTS`) | `test_04_missing_optional_inputs_and_null_vs_empty_list_distinction` |
| 5 | **Unknown water availability** | Requesting `TOMATO_IND` under `water=unknown` sets `outcome = "unavailable_due_to_insufficient_evidence"` rather than auto-passing | `test_05_unknown_water_infeasible_targets_and_no_eligible_recommendation` |
| 6 | **Infeasible rotation handling** | Requesting perennial `OLIVE` sets `outcome = "excluded"` via `RULE_PERENNIAL_EXCLUSION`; excluded sequences keep `rank = null` | `test_05_unknown_water_infeasible_targets_and_no_eligible_recommendation` |
| 7 | **No eligible recommendation** | Excluding all 12 annual crops sets `suggested_strategy_id = null`, `status = "NO_ELIGIBLE_STRATEGY"`, and `recommendation_status = "NO_STRATEGY_RECOMMENDED_ALL_INFEASIBLE"` | `test_05_unknown_water_infeasible_targets_and_no_eligible_recommendation` |
| 8 | **Partial geospatial coverage** | Cross-border polygon triggers Wilaya overlap warnings (`< 99%`) while executing clipped Guelma extraction cleanly | `test_06_partial_geospatial_coverage_and_missing_environmental_datasets` |
| 9 | **Missing environmental datasets** | Simulated unavailable `SoilGrids` & `Sentinel-2` degrades completeness cleanly (`< 0.60`), sets `soil_improvement = PARTIAL`, zero crashes | `test_06_partial_geospatial_coverage_and_missing_environmental_datasets` |
| 10 | **Recommendation schema validation** | `validate_final_recommendation()` returns `valid = True` (`0` errors) across all analyzed outputs; `/api/v1/health`, `/api/v1/reference/*`, `/` tested | `test_01_*` .. `test_07_*` |
| 11 | **Reproducibility of identical requests** | Identical payloads produce equal `analysis_id`, `payload_sha256`, and `recommendation` (`reused_existing = True`); altered polygon or water on the same `field_id` produces a distinct `analysis_id` | `test_07_reproducibility_and_distinct_analysis_ids_for_same_field_id` |

---

## 3. Defects Caught & Fixed During Phase L Integration Testing

1. **Error-Code Misclassification Fixed (`src/api/app.py`):** Initial test run exposed `ValueError` from Phase I zero-weight rejection being labeled `INVALID_FIELD_POLYGON`. Fixed error classifier to separate `INVALID_FIELD_POLYGON`, `INVALID_PRIORITY_WEIGHTS`, and `INVALID_ANALYSIS_INPUT`.
2. **All-Zero Priority Payload Guard (`frontend/app.js`):** Selecting `"forage_value_weight = 0.0"` without other priority weights caused Phase I to reject zero positive priorities. Updated UI serialization so `forageMode = zero` supplies explicit baseline positive weights (`0.25 / 0.30 / 0.20 / 0.25`) alongside `forage_value_weight: 0.0`, while `"null"` continues keeping `forage_value_weight: null` inactive.

---

## 4. Supervised Field Pilot Readiness Assessment

- **Ready for a *Supervised* Advisory / Extension-Agent Pilot (`YES — CONDITIONAL`):**  
  Yes, the integrated web UI + FastAPI API + local SQLite 8-table persistence pipeline is verified end-to-end (`71/71` tests passing) for **supervised trials with ITGC/DSA advisors** (using the desktop/mobile web UI at `GET /`), provided advisors visibly enforce missing DEM drainage checks, irrigation `ECe` lab tests, and offline disclaimers.
- **Not Yet Ready for *Unsupervised* Farmers or Production Multi-Tenant Rollout (`BLOCKED`):**  
  Requires provisioning host `postgis` + `psycopg` driver (`db/schema_postgis.sql`), adding OAuth2/JWT advisor authentication, completing Phase E Pillars 2–5 field calibration, and implementing native French/Arabic prose translation for rule explanations.
