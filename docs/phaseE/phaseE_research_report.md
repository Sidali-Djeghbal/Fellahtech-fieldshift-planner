# Phase E Research Report — Agricultural Decision Formalization & Modeling Architecture

**Project:** Field Shift (Guelma Wilaya, Algeria — NASA Space Apps Challenge 2026)  
**Scope:** Strictly research & system architecture design (no model training, no suitability scoring implementation, no GEE calls, Phases A–D untouched)  
**Date:** `2026-11-15`

---

## 1. Executive Synthesis of Phase E Findings

Auditing the integrated Phase D tables ([data/INTEGRATED/](file:///home/lokman/Desktop/FeildShit-SI-Model/data/INTEGRATED/)) alongside auxiliary datasets and regional Algerian/Mediterranean agronomy established four foundational realities shaping Field Shift's architecture:

1. **Strong Empirical Spatial Contrasts Within Guelma (`3,683.23 km²`, `34` Communes):**
   - **Alluvial Valley & Central Plains** (`Boumahra Ahmed 83.3%` cropland, `555 mm` GPM, `pH 7.33`, `SOC 16.8 g/kg`; `El Fedjoudj`, `Helliopolis`, `Belkheir`, `Ain Ben Beida`) support cereal–pulse–forage systems plus the **Guelma–Bouchegouf irrigated perimeter** (`Bouhamdane Dam`, major *tomate industrielle* hub).
   - **Southern/Western Semi-Arid Cereal–Pulse Plains** (`Tamlouka 436.0 mm` GPM, `SOC 13.58 g/kg`; `Ain Makhlouf 467.5 mm`; `Ain Rekada 476.7 mm`; `Oued Zenati 484.8 mm`, `65.6%` cropland) exhibit depleted arable organic carbon (`13.6–18.3 g/kg`), cooler springs (`14.2 °C`), and high drought risk.
   - **Northern Uplands & Foothills** (`Bouchekouf`, `Roknia`, `Bou Hamdane`, `Medjaz Sfa`, `Nechemaya`) show higher rainfall (`559–600 mm` GPM), higher `SOC` (`22.0–24.1 g/kg`), and low annual cropland share (`16.7–26.7%`) dominated by forests, maquis, and perennial olive orchards (excluded from annual rotation switching).
2. **Pervasive Heavy Clay Loam & Near-Neutral/Alkaline Soils:** `96.95%` of classified `0–5 cm` pixels are **Clay Loam** (`cropland 0–30 cm pH` median `7.13`, `p95 = 7.43`). This physically favors cereals and faba bean (with drainage), constrains acid-preferring potato (`pH 5.0–6.2` optimal -> scab hazard), constrains poorly drained lentil depressions, and creates narrow Seybouse Vertisol tillage windows.
3. **Climate Uncertainty & Missing Ground Labels Disqualify Black-Box Supervised ML Today:**
   - Annual `NASA POWER` (`677.8 mm` 10-yr mean) exceeds `GPM` (`545.5 mm`) by **`+132.3 mm/yr` (`+24%`)**; Spring `GPM` swings nearly **`4.3×` (`51.0–220.8 mm`)**.
   - [Guelma_Annual_Seasonal_Crop_Analysis.csv](file:///home/lokman/Desktop/FeildShit-SI-Model/data/tables/Guelma_Annual_Seasonal_Crop_Analysis.csv) is purely an `NDVI > 0.4` regional greenness area—zero crop-type maps, observed yields, rotation histories, or field boundaries exist on disk. `SoilGrids Nitrogen` carries an unvalidated `N > SOC` subsoil anomaly and stays excluded.

---

## 2. Strategic Recommendations (Answering the Six Core Decisions)

### Q1. What problem should Field Shift solve first?
Solve **Constraint-Driven Multi-Year Annual Crop Rotation Planning & Soil–Water Risk Diagnosis** at commune scale: specifically evaluating **cereal–legume–forage (`Durum Wheat / Barley` + `Faba Bean / Winter-Spring Chickpea / Lentil / Vetch-Oat`) fallow-replacement strategies** for rainfed zones, and **Irrigation-Gated `Processing Tomato – Cereal – Legume` Break-Crop Sequences** where user/institutional irrigation access is confirmed—coupled with explicit soil (`SOC < 18 g/kg`, clay workability, alkaline potato scab warning) and seasonal drought diagnostics (`2019` wet vs. `2022` dry). *Do not start with uncalibrated yield (`qx/ha`) prediction or field-level crop classification.*

### Q2. Which decision unit is scientifically defensible?
Adopt a **Two-Tier Spatial Hierarchy** ([decision_unit_assessment.md](file:///home/lokman/Desktop/FeildShit-SI-Model/docs/phaseE/decision_unit_assessment.md)):
- **Primary Operational Unit (MVP):** **Cropland-Masked Commune Zone (`34` GADM 4.1 Communes restricted to `ESA Crop Frequency >= 0.5` for soil/vegetation priors)**, carrying intra-commune `p05–p50–p95` SoilGrids dispersion and area-weighted `11 km` GPM/SMAP + `NASA POWER` climate regimes.
- **Secondary Analytical Screening Unit:** **`250 m` Cropland-Filtered Pixels (`19,553` px)** used *only* for static soil + MODIS phenological clustering, permanently tagged with coarse `11 km` climate caveats. **Field-level prescriptions are explicitly withheld** unless anchored on runtime user-supplied plot traits (irrigation, drainage, prior crops) and future cadastral/S2 data.

### Q3. Which model architecture should be implemented?
Implement a **5-Layer Hybrid Architecture** ([proposed_model_architecture.md](file:///home/lokman/Desktop/FeildShit-SI-Model/docs/phaseE/proposed_model_architecture.md)) combining:
1. **FAO-56 Physics Water-Balance Module** (deriving Penman-Monteith `ETo` from `NASA POWER` + bounded `GPM` low vs. `NASA POWER` high rainfall envelopes).
2. **Attributed Agronomic Rule Engine** (hard safety exclusion gates & return-interval graph from ITGC/ICARDA/FAO).
3. **Parametric Continuous Stress Scoring (`0..1`)** across soil workability, pH, SOC deficit, moisture adequacy, and heat/frost exposure.
4. **Deterministic Multi-Objective Sequence Generator & Ranker (`2–4` year sequences)** outputting coupled **D → A → C → B → E** advisories.
5. **Explainability & Uncertainty Audit Card** tracking limiting factors, climate dataset sensitivity flips, and pre-planting verification checklists.

### Q4. Which missing data must be collected?
Prioritized in [data_gaps_and_collection_plan.md](file:///home/lokman/Desktop/FeildShit-SI-Model/docs/phaseE/data_gaps_and_collection_plan.md):
- **Immediate Free Quick Wins (Local):** `SRTM 30 m` DEM (slope & drainage/TWI) and `ESA WorldCover 10 m` (separating perennial olives/forests/urban areas cleanly).
- **Institutional P1 Priority:** **DSA Guelma** commune crop areas/yields (external validation holdout), **ONID/ABH** `Guelma–Bouchegouf` irrigated perimeter boundaries & Bouhamdane Dam quotas, and **ONM/ANRH** gauge rainfall/wind (`WS2M`) records to debias `GPM` vs `NASA POWER`.
- **Soil & Field P2/P3:** `30–50` laboratory soil cores (`ECe` salinity, `CaCO₃`, `Olsen-P`, `K`, validated `Nmin`, depth) plus structured `30–60` farmer interviews covering tenure, livestock fodder trade-offs, and `Ascochyta`-tolerant seed access.

### Q5. What is the minimum viable research prototype (Phase F MVP)?
Build a **100% locally runnable Python Decision-Support Research Engine** over the `34` integrated communes (`data/INTEGRATED/`) executing:
1. `FAO-56` daily/seasonal `ETo` & dual `GPM`/`NASA POWER` water-balance engine (`wet-2019` vs. `normal` vs. `dry-2022` counterfactuals).
2. Attributed JSON/YAML **Crop & Rotation Compatibility Ontology** (starting with the `12` verified crop/fallow systems + `Olive` perennial guard).
3. Runtime CLI/API accepting `(commune_name, irrigation_access, crop_t_minus_1, crop_t_minus_2, livestock_forage_priority, soil_p05_p50_p95_mode)`.
4. Structured **`D → A → C → B → E` JSON + Markdown Advisory Generator** plus automated sensitivity & logical-invariant test suite (`0` fake profit/yield numbers).

### Q6. What must be validated before producing farmer-facing recommendations?
All five deployment gates in [validation_strategy.md](file:///home/lokman/Desktop/FeildShit-SI-Model/docs/phaseE/validation_strategy.md) must pass:
1. Local **ITGC / DSA Guelma** agronomist sign-off (`0` dangerous rotational or drainage errors).
2. Empirical **`GPM` vs `NASA POWER` vs `ONM`** rain-gauge bias calibration.
3. Verified **ONID/DSA irrigated perimeter & `ECe` salinity** boundaries/alerts.
4. Ground laboratory soil comparison (`SoilGrids V6` vs `30+` cores, `ECe/CaCO₃/P`).
5. **Farmer usability & uncertainty comprehension testing** confirming users clearly understand commune-scale confidence limits and run-time plot checks before field action.

---

## 3. Complete Phase E Deliverable Index

1. [agricultural_problem_definition.md](file:///home/lokman/Desktop/FeildShit-SI-Model/docs/phaseE/agricultural_problem_definition.md)
2. [crop_system_inventory.csv](file:///home/lokman/Desktop/FeildShit-SI-Model/docs/phaseE/crop_system_inventory.csv)
3. [decision_unit_assessment.md](file:///home/lokman/Desktop/FeildShit-SI-Model/docs/phaseE/decision_unit_assessment.md)
4. [candidate_model_comparison.md](file:///home/lokman/Desktop/FeildShit-SI-Model/docs/phaseE/candidate_model_comparison.md)
5. [agronomic_constraints_framework.csv](file:///home/lokman/Desktop/FeildShit-SI-Model/docs/phaseE/agronomic_constraints_framework.csv)
6. [proposed_model_architecture.md](file:///home/lokman/Desktop/FeildShit-SI-Model/docs/phaseE/proposed_model_architecture.md)
7. [data_gaps_and_collection_plan.md](file:///home/lokman/Desktop/FeildShit-SI-Model/docs/phaseE/data_gaps_and_collection_plan.md)
8. [validation_strategy.md](file:///home/lokman/Desktop/FeildShit-SI-Model/docs/phaseE/validation_strategy.md)
9. [phaseE_research_report.md](file:///home/lokman/Desktop/FeildShit-SI-Model/docs/phaseE/phaseE_research_report.md)
