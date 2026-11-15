# Phase N — Executive Audit Report: Decision Reliability & Scientific Hardening

**Project:** Field Shift — Guelma Crop Rotation Decision Support System (DSS)  
**Engine Version Transition:** `FieldShift-PhaseFJ-1.0.0` (Schema `1.0.0`) → `FieldShift-PhaseFJ-1.1.0` (Schema `1.1.0`)  
**Audit Date:** 2026-11-15  

---

## 1. Executive Audit Findings

A comprehensive technical and agronomic audit of the Field Shift DSS (triggered by inspecting persisted analysis `ANAL_248892E4C4DFE796` and auditing Phases F–M end-to-end) identified **seven structural reliability defects** that Phase N resolves:

| ID | Audited Defect | Evidence Observed in v1.0.0 | Scientific / Operational Risk | Phase N Resolution |
|---|---|---|---|---|
| **P0-1** | **Unverified / Peri-Urban Land Use Accepted as Arable Recommendations** | `ANAL_248892E4C4DFE796` (`[7.435..7.441, 36.443..36.447]`) yielded `crop_frequency_2021_2025 = 0.0008` (`2487` px, `cropland_share_ge_05_pct = 0.0%`), `soilgrids_v6.clay_0_30cm` coverage `3.01%` (`1` unmasked pixel), and `s2_2024_03_ndvi_10m = 0.203`, yet emitted normal conditional crop rankings under `frontend/app.js` `PRESETS.belkheir`. | Issuing multi-year cereal/pulse rotation endorsements on urban/peri-urban or unverified non-arable parcels. | Created [`src/agronomic/land_use_assessment.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/src/agronomic/land_use_assessment.py), enforced `EXPLORATORY_ONLY` gating (`endorsed_recommendation_id = None`), fixed `PRESETS.belkheir` to genuine Belkheir farmland (`cf = 0.9253`, SoilGrids `100.0%`), and exposed `PRESETS.periurban`. |
| **P0-2** | **No Temporal Planning Guard & Stale 2025 UI Default** | `frontend/index.html` defaulted `startYear = 2025`, and `ANAL_248892E4C4DFE796` accepted `start_season = "Autumn"`, `start_year = 2025` with zero temporal rejection against 2026 wall-clock time. | Farmers could accidentally generate live operational recommendations for already-expired sowing windows. | Created [`src/agronomic/temporal_planning.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/src/agronomic/temporal_planning.py) separating `CURRENT_PLANNING` (default) from `HISTORICAL_SIMULATION`, added HTTP `422` `PAST_PLANNING_SEASON` / `PAST_PLANTING_MONTH` responses, and set dynamic open-season UI defaults. |
| **P1-3** | **Dead Code Hooks & Sequence Caution Calibration Gaps** | In `scoring_engine.py`, `_eval_nitrogen_contribution` read `"beneficial_transitions"` instead of `"transitions"` (`SEQ_07`), and `_eval_farmer_priority_fit` read `"RULE_EQUIPMENT_COMPATIBILITY"` instead of `"RULE_EQUIPMENT_CONSTRAINT_CHECK"`; `SEQ_06` did not flag 2-yr `VETCH_OAT -> DURUM_WHEAT -> VETCH_OAT` cycles. | Silent loss of `SEQ_07` legume-to-cereal N carry-over bonus, silent bypass of machinery conflict penalties, and unflagged 2-year Vetch-Oat return risk. | Fixed both dead key lookups in `scoring_engine.py`, documented hard vs cross-pulse `SEQ_04` provenance, flagged 2-yr `VETCH_OAT` cycles in `SEQ_06` with `-0.04` hay management caution (`-0.12` on consecutive), and tapered semi-arid drought bonuses smoothly above `500 mm`. |
| **P1-4** | **Near-Tie Wins Presented Without Ambiguity Flagging** | `ANAL_248892E4C4DFE796` top strategies differed by `0.003394` (`0.895228` vs `0.891834`), flipping top winner in `6 / 19` scenarios (`stability_index = 0.6842`), without a `NEAR_TIE` gate. | Presenting statistically/structurally tied ordinal strategies as an unambiguous #1 pick. | Added [`MarginThresholds`](file:///home/lokman/Desktop/FeildShit-SI-Model/src/optimization/sensitivity.py) (`NEAR_TIE`, `NARROW_MARGIN`, `CLEAR_MARGIN`), `plausible_alternatives`, `winner_frequency`, `top_1_retention`, `top_2_frequency`, `rank_change_counts`, conservative/disagreement climate scenarios, and `non_confidence_note`. |
| **P1-5** | **Ordinal Water Efficiency vs Unbuilt FAO-56 Layer** | NASA POWER extract (`extraction_metadata.json`) contains `['T2M', 'T2M_MAX', 'T2M_MIN', 'PRECTOTCORR', 'RH2M']` and `['ALLSKY_SFC_SW_DWN']`—missing `WS2M` (`2 m` wind speed); `water_efficiency` risked misinterpretation as ETc water balance. | Mistaking ordinal drought suitability indices for quantitative Penman-Monteith irrigation requirements. | Clarified `ORDINAL_REGIME_SUITABILITY` scope and implemented non-fabricating FAO-56 readiness module [`src/optimization/water_balance.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/src/optimization/water_balance.py). |
| **P1-6** | **Catalog Completeness Conflated with Critical Adequacy** | `ANAL_248892E4C4DFE796` reported `completeness_score = 0.9038` despite `3.01%` SoilGrids coverage and `0.0008` cropland frequency. | High percentage score masking critical spatial/agronomic blockers. | Added `data_quality.critical_data_adequacy` (`ADEQUATE`, `PARTIAL`, `INSUFFICIENT`, `NOT_ASSESSABLE`) distinguishing non-null schema count from decision sufficiency. |
| **P2-7** | **Coarse End-of-Pipeline Recommendation Gating** | `recommendation_status` lacked a formal separation between unverified/exploratory output and operational endorsement. | Ambiguity over whether a displayed top candidate is operationally endorsed. | Added structured `decision_gate` (`FEASIBLE_PASS`, `CONDITIONALLY_FEASIBLE`, `REQUIRES_LOCAL_VERIFICATION`, `EXPLORATORY_ONLY`, `INFEASIBLE`, `NO_RECOMMENDATION`) validated by Draft 2020-12 & semantic invariants. |

---

## 2. Empirical Impact on Representative Guelma Parcels (v1.1.0 Live Output)

Running the hardened Phase F→J pipeline identically across three test parcels demonstrates clean discrimination without false confidence:

| Metric | `ANAL_248892_PERIURBAN` (Guelma Urban Fringe) | `BELKHEIR_CROPLAND` (Belkheir Seybouse Plain) | `TAMLOUKA_SEMIARID` (Tamlouka South) |
|---|---|---|---|
| **Commune & Area** | `Guelma` (`23.8693 ha`) | `Belkheir` (`23.8605 ha`) | `Tamlouka` (`23.9692 ha`) |
| **10m CropFreq 2021–2025** | `0.0008` (`share >= 0.5`: `0.0%`) | `0.9253` (`share >= 0.5`: `96.72%`) | `0.5354` (`share >= 0.5`: `63.46%`) |
| **SoilGrids Clay Coverage** | `3.01%` (`1` unmasked px) | `100.0%` (`9` px) | `100.0%` (`9` px) |
| **Land-Use Classification** | `LAND_USE_CONFLICTING_EVIDENCE` (with history) / `LAND_USE_UNVERIFIED` (without) | `LAND_USE_SUPPORTED` | `LAND_USE_SUPPORTED` |
| **`completeness_score` (Catalog)** | `0.9038` | `0.9038` | `0.9038` |
| **`critical_data_adequacy`** | **`INSUFFICIENT`** | **`PARTIAL`** (missing DEM, ECe, FAO-56 inputs) | **`PARTIAL`** (missing DEM, ECe, FAO-56 inputs) |
| **`decision_gate.decision_status`** | **`EXPLORATORY_ONLY`** | **`REQUIRES_LOCAL_VERIFICATION`** | **`REQUIRES_LOCAL_VERIFICATION`** |
| **`endorsed_recommendation_id`** | **`None` (`provisional_only=True`)** | `STRAT_SOIL_IMPROVEMENT` | `STRAT_SOIL_IMPROVEMENT` |
| **Margin Classification** | `NARROW_MARGIN` (`Δ = 0.051759`, `5.93%`) | `CLEAR_MARGIN` (`Δ = 0.066135`, `7.52%`) | **`NEAR_TIE`** (`Δ = 0.014253`, `1.67%` vs `STRAT_WATER_CONSCIOUS`) |
