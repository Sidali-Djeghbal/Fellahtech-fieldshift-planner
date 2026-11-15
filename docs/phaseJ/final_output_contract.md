# Phase J — Final Recommendation Output Contract

**Builder Module:** [`src/output/recommendation_builder.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/src/output/recommendation_builder.py) (`build_final_recommendation`)  
**Validator Module:** [`src/output/output_validator.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/src/output/output_validator.py) (`validate_final_recommendation`)  
**JSON Schema (Draft 2020-12):** [`schemas/final_recommendation_output.schema.json`](file:///home/lokman/Desktop/FeildShit-SI-Model/schemas/final_recommendation_output.schema.json)  
**Verified Sample Response:** [`docs/phaseJ/sample_final_recommendation.json`](file:///home/lokman/Desktop/FeildShit-SI-Model/docs/phaseJ/sample_final_recommendation.json)

---

## 1. Architectural Purpose & Upstream Isolation

Phase J is a pure assembly, formatting, provenance-preservation, and schema-validation layer combining:
- **Phase F (`Field Profile`):** Farmer-reported boundary, water, history, planning/preferences completeness flags, SoilGrids 250 m / GPM / SMAP / NASA POWER / MODIS / ESA / DEM extractions, and descriptive field diagnostics.
- **Phase G (`Agronomic Knowledge & Constraints`):** Crop metadata, sequence/single-crop rule evaluations, and perennial vs annual scope rules.
- **Phase H (`Candidate Generator`):** Synthesized multi-year sequences, season calendars, and farmer target/exclusion tracing.
- **Phase I (`Multi-Objective Optimization`):** Eight objective evaluations (`SCORED`, `PARTIAL`, `UNKNOWN`, `NOT_APPLICABLE`), Pareto dominance partitioning, normalized active weights, and OAT + climate sensitivity analysis.

Phase J **does not** re-implement agronomic rules, re-generate candidates, or alter scores. All phases A–I remain unmodified.

---

## 2. Top-Level & Nested Output Schema Contract

### 2.1 Root Envelope
- `schema_version` (`"1.0.0"`), `request_id` (`REQ_<field_id>_<hash10>` deterministic by default), `dataset_version_used`, `generated_at` (ISO-8601 UTC; overridable for deterministic builds), `status` (`"COMPLETE"` | `"PARTIAL"` | `"FAILED"`), `language` (`"en"` | `"fr"` | `"ar"`), `decision_engine_version` (`"FieldShift-PhaseFJ-1.0.0"`), `overall_summary`, `disclaimer`, and `field_plans` (exact length `1`, enforcing the single-field-per-request architecture).

### 2.2 `field_plans[0]`
- **Identity & Status:** `field_id`, `field_name`, `status` (`"COMPLETE"` | `"PARTIAL"` | `"NO_ELIGIBLE_STRATEGY"`), `partial_reason`.
- **`field_insights`:** `bare_field_periods`, `stress_periods`, `climate_trend_summary` — built exclusively from observed Phase F layers and explicit 2016–2025 regional caveats.
- **`strategies[]`:**
  - `strategy_id`, `name`, `is_existing_rotation`, `description`
  - `seasons[]`: `{order, season, year, planting_month, crop_id, crop_name, category, role, selection_status, notes}`
  - `feasibility_status`: authoritative Phase G/H verdict (`FEASIBLE_PASS`, `CONDITIONALLY_FEASIBLE_WITH_WARNINGS_OR_UNKNOWNS`, `UNVERIFIED_HARD_UNKNOWN`, `INFEASIBLE_HARD_CONSTRAINT`)
  - `scores`: all 8 objectives (`water_efficiency`, `soil_improvement`, `nitrogen_contribution`, `pest_disease_disruption`, `erosion_protection`, `income_potential`, `forage_value`, `farmer_priority_fit`); `null` scores stay `null` and carry `normalized_weight = 0.0` (including zeroed weights on excluded infeasible candidates).
  - `confidence`: kept strictly distinct from `data_quality.completeness_score`.
  - `pareto_status`, `dominated_by`, `rank`, `weighted_score` (`rank = null`, `weighted_score = null`, `pareto_status = "EXCLUDED_INFEASIBLE"` on infeasible candidates).
  - `explanation`: `{summary, reasons, evidence[], benefits, risks, assumptions, information_gaps, needs_local_review, review_checklist}` where every `EvidenceItem` records `{data_source, parameter, observed_value, unit, period, derived, interpretation, spatial_resolution, quality_status}`.
- **Decision & Trade-Off Metadata:** `suggested_strategy_id` (`null` when zero eligible candidates exist), `recommendation_status`, `pareto_summary`, `ranking_methodology`, `sensitivity_summary` (with explicit note that `stability_index` is NOT scientific confidence).
- **`requested_crop_results[]`:** Every requested target crop resolved into `"included"`, `"excluded"`, `"not_evaluated"`, or `"unavailable_due_to_insufficient_evidence"`.
- **`data_quality`:** `{completeness_score, confidence_note, missing_data, warnings, limitations, input_completeness_flags}` preserving `NOT_PROVIDED` (`null`) vs `EXPLICITLY_CONFIRMED_EMPTY` (`[]`).

---

## 3. Compatibility Documentation (Phases F–I -> Phase J)

To match the frontend-ready Section 3 contract without changing upstream Phases F–I:
1. Phase H's per-season keys (`season_order`, `agricultural_season`, `calendar_year`, `canonical_name`, `crop_category`, `agronomic_role`, `supporting_notes`) are mapped cleanly to `{order, season, year, crop_name, category, role, notes}`.
2. Phase I's flat strategy keys (`explanation`, `reasons`, `evidence`, `benefits`, `risks`, `assumptions`, `information_gaps`, `needs_local_review`, `review_checklist`) are grouped under `strategy.explanation` (`summary` + `reasons` + structured `EvidenceItem[]`), keeping Phases H & I untouched.
3. Excluded infeasible candidates have their per-objective `active_in_ranking = false` and `normalized_weight = 0.0` normalized cleanly at serialization without mutating `score` (`null` stays `null`) or Phase I artifacts.
