# Phase M — Supervised Field Pilot Protocol (Guelma Wilaya, Algeria)

> **Status:** **PLANNED PROTOCOL (Zero Real-World Pilot Sessions Executed Yet)**  
> **Technical Baseline Audited:** Field Shift Phases D–L (`71/71` automated software/contract/integration tests passing; `Phase K` overall scientific verdict = `CONDITIONAL`, empirical yield validation = `NOT_VALIDATABLE`).  
> **Non-Negotiable Safety Rule:** **No autonomous planting decisions.** Every generated recommendation must pass agricultural expert review (`approved_for_farmer_briefing = true`) before any farmer briefing occurs.

---

## 1. Existing System Audit Summary Preceding Pilot Design

Inspecting Phases D–L verified the exact boundaries within which the supervised pilot must operate:
1. **Verified Technical Capabilities (Phases F–L):**
   - [`field_input_schema.json`](file:///home/lokman/Desktop/FeildShit-SI-Model/field_input_schema.json) and [`src/api/app.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/src/api/app.py) (`GET /api/v1/health`, `POST /api/v1/fields/validate`, `POST /api/v1/fields/analyze`, `GET /api/v1/analyses/{analysis_id}`) enforce strictly non-technical farmer inputs, single-`Polygon` EPSG:4326 -> EPSG:32632 reprojection, and `null` vs `[]` vs `0.0` preservation.
   - [`schemas/final_recommendation_output.schema.json`](file:///home/lokman/Desktop/FeildShit-SI-Model/schemas/final_recommendation_output.schema.json) enforces full provenance (`EvidenceItem[]`), distinct `data_quality.completeness_score` vs ranking confidence, and allows `NO_ELIGIBLE_STRATEGY` without forcing recommendations.
   - [`src/api/repository.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/src/api/repository.py) actively persists 8 normalized entities locally via `SQLiteAnalysisRepository` (`postgres_postgis` remains `DISCONNECTED` locally without host PostGIS/psycopg).
2. **Known Scientific & Operational Gaps Addressed by Pilot:**
   - Local DEM drainage slope (`UNAVAILABLE_NOT_INTEGRATED`), parcel salinity (`ECe`/`ECw`), `SoilGrids Nitrogen` (`UNVALIDATED_EXCLUDED`), and farmgate economic budgets (`income_potential = UNKNOWN`) remain unmeasured.
   - `POTATO` & `SUNFLOWER` remain `HYPOTHESIS_NEEDS_DSA_CHECK`.
   - `NASA POWER` (`~55–69 km`) vs `GPM IMERG` (`~11 km`) rainfall spread (`~+132 mm/yr`) can trigger `PRECIP_SENSITIVE_RANK_SHIFT` (e.g., `2022` `Belkheir` drought threshold around `FABA_BEAN`'s `450 mm` floor).
   - Engine prose outputs are English-only even when metadata `language` is `"fr"` or `"ar"`.

---

## 2. Eight Distinct Pilot Evaluation Objectives

To prevent confusing software usability with agronomic validity, the pilot evaluates **eight separate questions**:

| # | Evaluation Dimension | Question Answered | Separation Safeguard |
|---:|---|---|---|
| 1 | **Farmer Input Usability** | Can farmers/advisors understand map polygon drawing, crop aliases, water access, and `null` vs `[]` prompts in field conditions? | High UI completion rate proves **interface clarity only**, never agronomic truth. |
| 2 | **Polygon Validation Reliability** | Does GeoJSON `Polygon` intake represent real field cadastre parcels inside Guelma cleanly without frequent topological rejection? | Tracks validation failures & cross-border edge cases separately from crop quality. |
| 3 | **Extracted Field Profile Plausibility** | Do extracted 250 m SoilGrids texture/pH/SOC (`MODELED_SPATIAL_ESTIMATE`) and macro rainfall patterns look geographically reasonable to local advisors (and where 250 m masks fail on `< 5 ha` plots)? | Evaluated by experts and optional Section C lab cores (`NOT` via model stability). |
| 4 | **Agronomic Acceptability of Rotations** | Are generated 2–4 season sequences agronomically safe and practically viable in Guelma's rainfed & irrigated sub-zones? | Evaluated via Section B blind & open expert review (`ACCEPTED / MODIFIED / REJECTED / INFO_NEEDED`). |
| 5 | **Constraint Warning Intelligibility** | Do farmers & advisors understand why `TOMATO_IND` or `FABA_BEAN` triggers `UNVERIFIED_HARD_UNKNOWN`, `PRECIP_SENSITIVE`, or `RULE_SALINITY` cautions? | Logged explicitly on [`expert_evaluation_form.md`](file:///home/lokman/Desktop/FeildShit-SI-Model/docs/phaseM/expert_evaluation_form.md). |
| 6 | **Explanation & Trade-Off Utility** | Do Pareto alternatives (`STRAT_SOIL_IMPROVEMENT` vs `STRAT_WATER_CONSCIOUS` vs `STRAT_CEREAL_FORAGE`) and season timelines help real advisory conversations? | Distinct 1–5 explanation quality rating recorded per review. |
| 7 | **Expert Agreement vs. Structured Investigation** | Where advisors agree vs disagree with top strategy rank—is disagreement due to missing `DEM`/`ECe`, microclimate, socioeconomic labor barriers, or a genuine KB rule error? | Mandatory `disagreement_investigation_code` prevents blind acceptance or blind dismissal. |
| 8 | **Missing-Data & Uncertainty Honesty** | Do participants recognize that `completeness_score` != yield probability and `income_potential = UNKNOWN` without local budgets? | Verified via comprehension check (`uncertainty_communication_clear`). |

---

## 3. Governance, Roles & Human-in-the-Loop Execution Flow

1. **Stage 0 — Institutional Onboarding (`PLANNED`):** Sign pilot collaboration MoU with **DSA Guelma**, **ITGC** (Constantine/Guelma station), and **ONID** (Seybouse/Bouchekouf irrigation perimeter team); appoint multilingual (`ar`/`fr`/`en`) field enumerators since API prose is English.
2. **Stage 1 — Supervised Field Intake (`Section A`):** Enumerator + farmer map 1 parcel polygon via [`frontend/index.html`](file:///home/lokman/Desktop/FeildShit-SI-Model/frontend/index.html) (`POST /api/v1/fields/validate` -> `POST /api/v1/fields/analyze`), capturing ONLY farmer-known water access, crop history, and operational preferences (`FarmerPilotObservation`). Technical lab values are **not** shown to influence input entry.
3. **Stage 2 — Independent Expert Review (`Section B` — Mandatory Safety Gate):** Before recommendations are presented as actionable advice, an accredited `ITGC` / `DSA` / `ONID` agronomist inspects the saved `analysis_id` (`GET /api/v1/analyses/{analysis_id}`) and completes [`expert_evaluation_form.md`](file:///home/lokman/Desktop/FeildShit-SI-Model/docs/phaseM/expert_evaluation_form.md) (`ExpertReviewRecord`).
4. **Stage 3 — Advisory Briefing (Conditional Only):** Only records with `agronomic_safety_pass = true` and `approved_for_farmer_briefing = true` are reviewed with the farmer alongside verbal/printed French & Arabic caveats covering `DEM` drainage, `ECe` salinity checks, and non-yield scope.
5. **Stage 4 — Optional Empirical Ground-Truthing (`Section C`):** Where partnered labs or harvest weigh-ins exist, empirical soil cores (`ECe`, `pH`, `texture`, `SOM`, `CaCO3`, `Olsen-P`) and actual single-season yields (`t/ha`) are logged via `MeasuredFieldObservation` (`NOT_MEASURED` / `null` whenever absent—zero imputation).
