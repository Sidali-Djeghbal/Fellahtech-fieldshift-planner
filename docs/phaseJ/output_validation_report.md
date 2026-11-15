# Phase J — Final Output Validation Report

**Builder Module:** [`src/output/recommendation_builder.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/src/output/recommendation_builder.py)  
**Validator Module:** [`src/output/output_validator.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/src/output/output_validator.py)  
**Schema (Draft 2020-12):** [`schemas/final_recommendation_output.schema.json`](file:///home/lokman/Desktop/FeildShit-SI-Model/schemas/final_recommendation_output.schema.json)  
**Verified Sample JSON:** [`docs/phaseJ/sample_final_recommendation.json`](file:///home/lokman/Desktop/FeildShit-SI-Model/docs/phaseJ/sample_final_recommendation.json)

---

## 1. Validation Architecture Summary

`validate_final_recommendation()` validates every Phase J output across **three sequential gates**:
1. **Strict RFC-8259 JSON Serialization:** Enforces `json.dumps(payload, allow_nan=False)`, rejecting `NaN`, `Infinity`, or non-JSON native types.
2. **JSON Schema Draft 2020-12 Validation:** Validates all root, field plan, `field_insights`, `strategies`, `seasons`, 8 `ObjectiveScore` objects, `EvidenceItem[]`, `RequestedCropResult[]`, and `DataQuality` fields (`required`, `additionalProperties=false`, enumerations, bounds, nullable union types).
3. **Cross-Field Semantic Consistency Invariants:**
   - Single-field contract (`len(field_plans) == 1`).
   - Recommendation feasibility & rank #1 consistency (`suggested_strategy_id` is never an `INFEASIBLE_HARD_CONSTRAINT` or `UNVERIFIED_HARD_UNKNOWN` candidate; equals `null` when zero eligible candidates exist).
   - Rank contiguity (`1..N` on eligible pool; `rank=null`, `weighted_score=null`, `pareto_status="EXCLUDED_INFEASIBLE"` on excluded strategies).
   - Non-zero coercion invariant (`status in {"UNKNOWN", "NOT_APPLICABLE"}` strictly enforces `score=null` and `normalized_weight=0.0`).
   - Pareto front reference integrity and active weight sum `= 1.0`.

---

## 2. Sample Output Verification (`F_BOU_SAMPLE_01`)

Verified execution from minimal farmer polygon input -> Phase F Field Profile -> Phase H (`7` generated candidates incl. counterfactual `OLIVE` and `EXISTING_ROTATION_BASELINE`) -> Phase I Scoring/Pareto/Sensitivity -> Phase J Final Recommendation ([`sample_final_recommendation.json`](file:///home/lokman/Desktop/FeildShit-SI-Model/docs/phaseJ/sample_final_recommendation.json)):

- **Validation Status:** `{'valid': True, 'error_count': 0, 'errors': [], 'schema_draft': '2020-12'}`
- **Root / Field Status:** `PARTIAL` (`partial_reason`: local DEM slope, irrigation `ECe` salinity, and verified local economic budgets remain unavailable)
- **`request_id`:** `REQ_F_BOU_SAMPLE_01_15676653A8`
- **Recommended Strategy:** `suggested_strategy_id = "STRAT_SOIL_IMPROVEMENT"`, `recommendation_status = "CONDITIONAL_RECOMMENDATION_REQUIRES_LOCAL_VERIFICATION"`
- **Strategy Portfolio (`7` Total):**
  - `5` eligible conditional candidates ranked `1..5` (`STRAT_SOIL_IMPROVEMENT` `0.847803`, `STRAT_CEREAL_FORAGE` `0.800353`, `STRAT_CEREAL_LEGUME` `0.762741`, `STRAT_TARGET_SUNFLOWER` `0.742606`, `STRAT_IRRIGATED_CASH` `0.726916`)
  - `2` excluded infeasible strategies (`STRAT_REQUESTED_OLIVE` & `STRAT_EXISTING_BASELINE`, both `rank = null`, `weighted_score = null`, `pareto_status = "EXCLUDED_INFEASIBLE"`)
- **Requested Crop Outcomes (`requested_crop_results[]`):**
  - `TOMATO_IND` -> `included` (`STRAT_IRRIGATED_CASH`)
  - `SUNFLOWER` -> `included` (`STRAT_TARGET_SUNFLOWER`)
  - `OLIVE` -> `excluded` (`RULE_PERENNIAL_EXCLUSION`, counterfactual trace preserved in `STRAT_REQUESTED_OLIVE`)
- **Data Quality Separation:** `completeness_score = 0.9231` kept strictly separate from per-strategy `confidence.level = "CONDITIONAL_MEDIUM_LOW"` and sensitivity `stability_index = 0.9474`.

---

## 3. Automated Regression & Test Results

Executed full combined test suite (`PYTHONPATH=. /home/lokman/Desktop/FeildShit-SI-Model/venv/bin/python -m unittest discover -s tests -v`):
- **Result:** **`Ran 59 tests in 159.992s — OK`** (`0` failures, `0` skips across Phases D, F, G, H, I, and J).
- Verified via `git status -s` that zero Phases A–I files were modified and zero Google Earth Engine tasks were submitted.
