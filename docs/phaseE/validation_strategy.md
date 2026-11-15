# Validation & Pre-Deployment Verification Strategy — Field Shift (Phase E)

**Non-Negotiable Rule:** Zero accuracy, yield-prediction, or precision claims may be reported before empirical ground validation is executed. Every check below evaluates **agronomic plausibility, physical consistency, uncertainty sensitivity, and local expert consensus**—not post-hoc curve fitting without labels.

---

## 1. Seven-Pillar Validation Framework

### Pillar 1: Agronomic Literature & Parameter Traceability Audit
- **Scope:** Verify all parameters in [crop_system_inventory.csv](file:///home/lokman/Desktop/FeildShit-SI-Model/docs/phaseE/crop_system_inventory.csv) and [agronomic_constraints_framework.csv](file:///home/lokman/Desktop/FeildShit-SI-Model/docs/phaseE/agronomic_constraints_framework.csv) (`Kc`, `Ky`, root depth `Zr`, pH limits, sequence return gaps).
- **Method:** Dual check against international standards (`FAO-56`, `Sys et al. 1993`, `FAO-29` salinity, `AquaCrop`) AND regional North African sources (`ITGC Algeria`, `ICARDA winter chickpea`, `REFORMA/CIHEAM ArimNet vetch-oat`).
- **Pass Criterion:** Zero unattributed universal thresholds; every heuristic flagged explicitly as `LOCAL_VERIFIED_REGIONAL`, `REGIONAL_ALGERIAN_ITGC`, or `HYPOTHESIS_NEEDS_DSA_CHECK`.

### Pillar 2: Local Agronomist & Institutional Expert Review (Structured Delphi)
- **Participants:** `ITGC` Constantine/Guelma cereal-legume specialists, `DSA Guelma` subdivision engineers, and `ONID` / `Guelma–Bouchegouf` irrigation technicians.
- **Protocol:** Present generated `2–4` year rotation recommendations, exclusions, and constraint diagnostics across **6 contrasting benchmark communes** (`Boumahra Ahmed`, `Guelma`, `Oued Zenati`, `Ain Makhlouf`, `Tamlouka`, `Bouchekouf`) under **blind scenario cards** (Rainfed vs. Irrigated; Wet vs. Dry Year).
- **Target Metrics:** Expert agronomic safety acceptance (`0` dangerous sequence errors, e.g., Tomato->Potato or rainfed summer Tomato), inter-expert agreement (`Fleiss' kappa` / rubric concordance), and documented rule refinements.

### Pillar 3: Macro Plausibility Benchmarking Against Algerian Agricultural Statistics (`DSA / MADR`)
- **Scope:** Compare Phase F model feasibility profiles (`Suitability` & `Crop System Shares`) against **held-out official DSA Guelma municipal statistics** (`2016–2025`, once acquired).
- **Strict Non-Leakage Rule:** DSA statistics are **strictly external verification targets**—never fitted as regression weights inside Phase F!
- **Checks:**
  - Verify whether irrigated-perimeter communes (`Boumahra Ahmed`, `El Fedjoudj`, `Belkheir`, `Bouchegouf/Ain Ben Beida`) align with verified Processing Tomato + Cereal hubs when `Irrig=True`.
  - Verify whether drier western/southern plains (`Tamlouka`, `Ain Makhlouf`, `Ain Rekada`, `Oued Zenati`) align with Barley/Durum Wheat/Pulse/Fallow dominance when `Irrig=False` (specifically testing our `Tamlouka` low `CropFreq` fallow hypothesis!).

### Pillar 4: Soil Laboratory & Station Climate Ground-Truthing
- **Soil Verification:** Compare `SoilGrids V6 250 m` (`pH`, `clay`, `SOC`, `CEC`) at matching coordinates against archived or newly sampled `30–50` laboratory soil cores across Guelma's 3 agro-ecological strata (`RMSE`, bias, rank correlation `Spearman rho`), and measure true **`ECe`**, **`CaCO₃`**, and **`Olsen-P`** to quantify missing constraint risk.
- **Climate Bias Calibration:** Compare `NASA POWER` (`~55–69 km`) and `GPM IMERG` (`11 km`) seasonal precipitation and `Tmin`/`Tmax` against `ONM / ANRH` local meteorological stations (`2016–2025`), verifying how the observed **`+132 mm/yr` `NASA POWER` vs `GPM` offset** maps to true station rainfall.

### Pillar 5: Participatory Farmer Feasibility & Operational Audit
- **Participants:** `30–60` farmers stratified by water regime (Guelma–Bouchegouf irrigators vs. Oued Zenati/Tamlouka dryland cereal-livestock farms vs. northern piedmont smallholders).
- **Questions Audited:** Seed availability (`Ascochyta`-tolerant winter chickpea vs. spring chickpea), machinery workability bottlenecks on Seybouse Clay Loams (`Nov–Dec` planting risk), tenant contract length barriers (`Bouchegouf` annual rentals), and economic/forage value of `Vetch-Oat` vs. traditional grazed fallow.

### Pillar 6: Quantitative Sensitivity & Uncertainty Analysis
- **Mandatory Perturbation Experiments (Executable in Phase F Before Any Farmer Release):**
  1. **Cross-Product Rainfall Switching:** Compare rankings under `GPM` vs. `NASA POWER` precipitation (`-20%` offset). Measure % of communes/seasons whose top-ranked rotation flips; assign **`PRECIP_SENSITIVE`** confidence badge wherever flips occur.
  2. **Soil Property Percentile Envelope:** Re-run each commune at `p05`, `p50`, and `p95` of its cropland `SoilGrids 250 m` pixels (`clay`, `pH`, `SOC`) to quantify intra-commune fragility.
  3. **Wind Speed (`WS2M`) `ETo` Sensitivity:** Test Penman-Monteith `ETo` across `[1.0, 2.0, 3.5 m/s]` default wind bounds while `WS2M` is absent locally.
  4. **Preference Weight Robustness:** Perturb multi-objective weights (`±25%` across Water Safety vs. Soil SOC Restoration vs. Break Value) using One-At-A-Time / Morris screening.

### Pillar 7: Spatial Leave-Commune-Out & Temporal Wet/Dry Backtesting
- **Temporal Backtesting (No Future Leakage):** Run rolling causal origin evaluation over `2017–2025` (conditioning Season `T` strictly on `<= T-1` antecedent `SMAP` rootzone moisture, `GPM`/`NASA POWER` lags, and blocking `2021–2025 CropFreq` for `2017–2020`). Inspect behavior across extreme observed contrasts:
  - **Wettest observed baseline:** `2019` (`760.7 mm` GPM / `961.9 mm` POWER, Spring NDVI high).
  - **Driest observed baseline:** `2022` (`403.6 mm` GPM / `561.4 mm` POWER, Spring drought stress).
- **Spatial Plausibility:** Leave-commune-out check verifying geographic smoothness and physical interpretability across Guelma's rainfall (`436–607 mm`) and clay/SOC (`13.6–24.1 g/kg`) gradients.

---

## 2. Hard Gate Criteria Required Before Farmer-Facing Deployment

Field Shift **MUST NOT** emit farmer-facing advisory cards directly to agricultural practitioners until ALL FIVE gates pass:
1. `0` critical agronomic safety violations confirmed by local ITGC/DSA agronomists.
2. `NASA POWER` vs. `GPM` vs. `ONM` station precipitation bias quantified and applied (no silent `+132 mm/yr` ambiguity).
3. Explicit handling of irrigation status + Seybouse `ECe` salinity risk verified against ONID/DSA perimeter boundaries.
4. `SoilGrids 250 m` accuracy checked against local soil laboratory samples (`30+` sites minimum across major plains).
5. UI/output tested with local farmers & extension agents to confirm clear communication of uncertainty, confidence badges, and **no illusion of parcel-level measurement precision**.
