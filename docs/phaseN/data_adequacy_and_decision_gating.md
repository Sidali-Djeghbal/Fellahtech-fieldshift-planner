# Phase N — Critical Data Adequacy & Multi-State Decision Gating Report

## 1. Separation of Catalog Completeness vs Critical Data Adequacy

In v1.0.0, `ANAL_248892E4C4DFE796` displayed `completeness_score = 0.9038` (because most raster keys returned non-null values) despite having `crop_frequency = 0.0008`, only `3.01%` unmasked SoilGrids coverage, no DEM, no ECe salinity, quarantined SoilGrids Nitrogen, and no enterprise budgets.

Phase N preserves `data_quality.completeness_score` (`0.9038` catalog non-null metric for backward compatibility) while adding [`recommendation_builder.py::_assess_critical_data_adequacy`](file:///home/lokman/Desktop/FeildShit-SI-Model/src/output/recommendation_builder.py) under `data_quality.critical_data_adequacy`:

| `adequacy_status` | Trigger Conditions | Interpretation |
|---|---|---|
| `ADEQUATE` | Zero `CRITICAL_BLOCKER`, zero `CRITICAL_VERIFICATION_REQUIRED`, zero `ADVISORY_GAP` | All spatial, land-use, terrain, soil lab, FAO-56 hydrology, history, and budget inputs verified. |
| `PARTIAL` | Land use supported/low-evidence & SoilGrids coverage adequate (`>= 25%`), eligible strategies exist, but unresolved `CRITICAL_VERIFICATION_REQUIRED` or `ADVISORY_GAP` remains (e.g., DEM, ECe/ECw, lab N/P/K, FAO-56 wind/FC/PWP, enterprise budgets) | Observed for genuine rural Guelma fields (`BELKHEIR_CROPLAND`, `TAMLOUKA_SEMIARID`): usable as conditional guidance pending listed field verifications. |
| `INSUFFICIENT` | Any `CRITICAL_BLOCKER` (e.g. `LAND_USE_UNVERIFIED`, `LAND_USE_CONFLICTING_EVIDENCE`, SoilGrids coverage `< 25%`, or `eligible_for_ranking_count == 0`) | Observed for `ANAL_248892_PERIURBAN` (`3.01%` SoilGrids coverage, `LAND_USE_CONFLICTING_EVIDENCE`) regardless of a `0.9038` catalog completeness score. |
| `NOT_ASSESSABLE` | Core geospatial extraction or both GPM/NASA POWER precipitation series unavailable | Pipeline lacks baseline agroclimatic envelope to evaluate suitability. |

---

## 2. Explicit `decision_gate` Contract

Phase I (`scoring_engine.py`) and Phase J (`recommendation_builder.py`, [`schemas/final_recommendation_output.schema.json`](file:///home/lokman/Desktop/FeildShit-SI-Model/schemas/final_recommendation_output.schema.json)) now emit a structured `field_plans[*].decision_gate` object with six non-ambiguous decision states:

| `decision_status` | `endorsed_recommendation_id` | `provisional_only` | Trigger & Operational Meaning |
|---|---|---|---|
| `FEASIBLE_PASS` | Top `strategy_id` | `False` | Supported land use, all candidate rules & FAO-56 layers satisfied (`PARTIAL`/`UNKNOWN` checks resolved). |
| `CONDITIONALLY_FEASIBLE` | Top `strategy_id` | `False` | Supported land use with soft agronomic cautions only and complete verification layers. |
| `REQUIRES_LOCAL_VERIFICATION` | Top `strategy_id` | `False` | Supported/low-evidence land use with eligible rotations, requiring site verification for unresolved `UNKNOWN` inputs (DEM drainage/slope, ECe salinity, history, local crop budgets, or FAO-56). |
| `EXPLORATORY_ONLY` | **`None` (`null`)** | **`True`** | `LAND_USE_UNVERIFIED` or `LAND_USE_CONFLICTING_EVIDENCE`. Preserves `exploratory_candidate_id` and marks strategies `provisional = True` for transparency, while strictly withholding endorsement. |
| `INFEASIBLE` | **`None` (`null`)** | `False` | Zero candidates satisfy hard agronomic/water constraints (`suggested_strategy_id = None`). |
| `NO_RECOMMENDATION` | **`None` (`null`)** | `False` | No scorable objectives active or no candidates available. |

---

## 3. Schema & Validator Enforcement

- [`schemas/final_recommendation_output.schema.json`](file:///home/lokman/Desktop/FeildShit-SI-Model/schemas/final_recommendation_output.schema.json): Added optional Phase N fields (`critical_data_adequacy`, `decision_gate`, `land_use_assessment`, `temporal_validation`, `water_balance_assessment`, strategy `provisional`, `land_use_status`, `stability_metrics`) under Draft 2020-12 strict `additionalProperties: false` objects, maintaining compatibility with legacy artifacts (`docs/phaseJ/sample_final_recommendation.json`).
- [`src/output/output_validator.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/src/output/output_validator.py): Enforces hard semantic invariants—including verifying that `EXPLORATORY_ONLY` outputs must always have `endorsed_recommendation_id = None` and `provisional_only = True`, and preventing strategy IDs or `recommended == True` contradictions under gated states.
