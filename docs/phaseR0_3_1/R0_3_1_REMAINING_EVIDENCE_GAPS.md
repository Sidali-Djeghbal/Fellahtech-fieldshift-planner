# Phase R0.3.1 — Remaining Scientific, Bibliographic & Data Evidence Gaps

**Summary Scale of Unresolved Evidence:** Out of `416` agronomic evidence cells audited across 13 crop profiles in [R0_3_1_CORRECTED_EVIDENCE_MATRIX.csv](file:///home/lokman/Desktop/FeildShit-SI-Model/docs/phaseR0_3_1/R0_3_1_CORRECTED_EVIDENCE_MATRIX.csv), **`116` (`27.9%`)** remain `NOT_AVAILABLE`, **`111` (`26.7%`)** require local calibration (`LOCAL_CALIBRATION_REQUIRED`), **`24` (`5.8%`)** retain unresolved scientific conflicts (`CONFLICTED`), and **`0` (`0.0%`)** achieve true parcel-level Guelma agronomic validation (`LOCAL_VALIDATED = 0`).

---

## Priority 0 — Immediate Scientific & Bibliographic Corrections (Required Before R0.4 Model Design)

1. **Replace Synthetic Placeholder `SRC-34` (`66` Matrix Citations, `48` Sole):**
   - `SRC-34` ("Batch 7a search summary") has zero named authors, DOIs, or primary papers yet previously underpinned `44` `HIGH`-confidence temperature threshold claims.
   - **Action Needed:** Replace all `temp_germ_min_c`, `temp_opt_growth_c`, `temp_frost_kill_veg_c`, `temp_frost_repr_c`, `temp_heat_stress_repr_c`, `vernalization_chilling_req`, and `thermal_time_gdd_degcd` values with primary peer-reviewed cultivar studies and verified FAO/ICARDA monographs, and fix the misframed annual `OLIVE::temp_germ_min_c` entry.
2. **Replace Unverified Pathology Bucket `SRC-33` (`24` Matrix Citations) & Fix Misattributed `SRC-01/02`:**
   - Separate social/contracting findings in Assassi et al. (`SRC-01/02`) from pathogen biology (`TOMATO_IND` `L285`) and replace `SRC-33` with explicit primary Algerian/Mediterranean DOIs on *Fusarium*, *Verticillium*, *Orobanche crenata/ramosa/cumana*, and *Streptomyces scabies* (e.g., Chlef/Ain Defla isolates).
3. **Repair Incorrect & Omitted DOIs/URLs in Source Register:**
   - **`SRC-16` (Wrong DOI):** Replace Kassam et al. (`10.1016/j.fcr.2012.02.023`) with **Mrabet et al. (2012), `10.1016/j.fcr.2011.11.017`** and resolve sub-humid (`>400 mm`) vs semi-arid (`200–300 mm`, `SRC-15`) fallow storage transferability.
   - **`SRC-31` (Wrong Year Attribution):** Explicitly add **Unkovich, Baldock & Peoples (2010), *Plant Soil* `329:75–89` (`10.1007/s11104-009-0136-5`)** for the `1.56` lentil and `1.82` chickpea whole-plant root factors.
   - **`SRC-23` / `SRC-24` (Broken/Wrong FAO URLs):** Replace FAO-33 URL `s2022e` (Brouwer & Heibloem *Training Manual 3*) and HTTP-404 FAO-66 URL `/aquacrop/en/` (canonical doc code `i2800e`).
   - **`SRC-12` (Wrong First Authors/Year):** Correct to **Guetteche, Jarrar, Khiyel, Djekkoun, Rouabah, Rouabah, Benbelkacem & Nick (2022/2023)**.
   - **`SRC-14` (Misattributed Repository Citation):** Remove internal repo docs `phaseE/phaseN` from DSA `800 qx/ha` newspaper yield citations and cite primary DSA/MADR bulletins if verified.
   - **Unbundle Aggregated Citations:** Supply primary PDF URLs/tables for **`SRC-05` (`ITGC`, currently HTTP 406)**, **`SRC-06` (`ITCMI` primary vs Scribd)**, **`SRC-07` (`ITAFV`)**, **`SRC-08` (exact JORA Décret `22-56` / OAIC circular refs)**, **`SRC-17` (4 distinct Katerji 2000–2005 DOIs)**, **`SRC-21` (CIHEAM/ICARDA papers)**, **`SRC-26` (3 external Francois/Maas DOIs)**, **`SRC-28` (`Sys 1993 Part III` exact tables + 4th author Beernaert)**, **`SRC-29` (GAEZ v4 snapshot ID)**, and **`SRC-32` (`Vicia faba` Feedipedia node)**.
4. **Correct Verified FAO-56 & FAO-29 Numeric & Schema Errors:**
   - Correct **`CHICKPEA_WINTER/SPRING` (`0.6–1.0 m`, NOT `0.9–1.5 m`)**, **`FABA_BEAN` (`0.5–0.7 m`, NOT `0.6–0.9 m`)**, **`LENTIL` (`0.6–0.8 m`, NOT `0.6–1.0 m`)**, **`OLIVE Kc` (`0.65 / 0.70 / 0.70` at 40–60% cover)**, **`OLIVE` FAO-29 Table 4 false citation (`2.7 dS/m` & `5.0%` absent)**, and strip multi-metric concatenations (`nutrient_uptake_npk_kg_t`, `forage_nutritive_value`, `algerian_costs_prices_context`, `BARE_FALLOW` wrong slots `L396/400/405`, `TOMATO_IND` `L286`).

---

## Priority 1 — Upstream Geospatial & API Schema Gaps Blocking Runtime Deployment

5. **30 m Copernicus / SRTM DEM, Slope (`%`), Aspect, and TWI (`TIER_B_01`, Domain 17):** Permanently blocks waterlogging differentiation across `33.7%` median-clay Guelma parcels, erosion cutoffs (`>5%`), and temperature lapse-rate downscaling.
6. **NASA POWER `WS2M` (2 m Wind Speed) & Daily Extreme Integration (`TIER_B_03`, Domains 1–5):** Missing `WS2M` blocks FAO-56 Penman-Monteith $\text{ET}_0$ (`COMPUTED_FULL`) and Eq. 62/65 $K_c$ adjustment; decadal seasonal `T2M` means cannot diagnose acute frost/heat events.
7. **Monthly GPM Bias Resolution (`-132.3 mm/yr`, Domain 6):** Monthly GPM does not exist on disk and annual GPM underestimates NASA POWER by `132.3 mm/yr`; monthly USDA SCS $P_{\text{eff}}$ and dual precipitation gate bounds need rain-gauge validation in Guelma (e.g., ONM Guelma/Boumahra stations).
8. **Typed Lab Soil & Water Schema in HTTP API (`TIER_B_02`, `TIER_B_05`, Domains 9, 15, 16, 18):** Add optional separated fields (`soil_ece_dsm`, `water_ecw_dsm`, `water_sar`, `fc_m3_m3`, `pwp_m3_m3`, `active_caco3_pct`, `soil_depth_cm`, `soil_nmin_kg_ha`, `olsen_p_ppm`, `exch_k_ppm`, `pest_history_tags`) so missing local lab data are explicitly declared rather than hidden behind coarse SMAP (`0.20`/`0.21`) or SoilGrids (`nitrogen_0_30cm` permanently quarantined) surrogates.

---

## Priority 2 — Local Guelma Field, Agronomic & Socio-Economic Calibration Needed

9. **Local Guelma Soil & Irrigation Water Validation:** Pair soil lab saturation extracts ($\text{EC}_e$), bulk density, FC/PWP, active $\text{CaCO}_3$ (`%`), and Seybouse aquifer/river $\text{EC}_w$ + $\text{SAR}$ monitoring against `SoilGrids 250 m` (confirming V6 CEC scaling factors) and `SMAP 11 km` before deploying numerical soil-moisture or salinity rules.
10. **Algerian Cultivar Phenology, Sowing Windows & NRV Trials (`CAND-04`, `CAND-05`):** Collect ITGC Guelma/Sub-Humid East phenology (`L_ini..L_late`, anthesis frost/heat dates) and local $^{15}\text{N}$ / Fertilizer-Response N Replacement Value (NRV) trials quantifying true faba bean, chickpea, and lentil net residual N carryover after grain export.
11. **Multi-Year Guelma Commune Farm Enterprise Budgets & Yields (`TIER_B_04` / `TIER_C_01`):** Acquire DSA commune multi-year yields, open-market tomato/potato/vetch-oat hay prices, volumetric water supply ($\text{m}^3/\text{ha}$), pumping costs, and verified land-leasing budgets (`SRC-01/02`) to safely activate `income_potential` and recalibrate irrigation scoring caps (`REM-10`).
12. **Parcel Pest & Infestation Incidence Mapping (`TIER_C_04`):** Document actual *Orobanche* (*O. crenata*, *O. ramosa*) and soilborne disease prevalence across Guelma communes so 4–6 year break gates reflect true biological risk rather than blanket exclusions.
