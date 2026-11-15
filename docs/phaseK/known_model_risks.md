# Phase K — Known Model Risks, Scientific Limitations & Pre-Deployment Gates

> **Document Scope:** Independent scientific risk register for Field Shift Phases A–J (Guelma Wilaya, Algeria).  
> **Verification Principle:** Software determinism and clean schema execution (`PASS`) do not establish empirical field accuracy (`NOT_VALIDATABLE` where ground-truth plot data are absent).

---

## 1. Risk Summary Matrix

| Risk ID | Subsystem | Severity | Evidence Basis Observed in Audit / Phase K Tests | Current Mitigation in Code | Required Pre-Deployment Action |
|---|---|---|---|---|---|
| `RISK-K01` | Empirical Yield & Economic Calibration | **CRITICAL** | Zero local parcel crop labels, zero multi-year plot yields (`t/ha`), zero farmgate price/cost tables on disk | `income_potential` remains `UNKNOWN`; system never fabricates `t/ha` or `DZD/ha` predictions | Collect multi-year ITGC/DSA plot yield records & seasonal input/price budgets (Phase E Pillar 3) |
| `RISK-K02` | Precipitation Source Divergence & Drought Shock (`PRECIP_SENSITIVE_RANK_SHIFT`) | **HIGH** | `Belkheir / Boumahra` 2022 dry test: `GPM = 444.04 mm` (`STRAT_WATER_CONSCIOUS`, `0.859228`) vs `POWER = 608.94 mm` (`STRAT_SOIL_IMPROVEMENT`); `FABA_BEAN` threshold is `450.0 mm` | `sensitivity_analysis.climate_sensitivity` flags `PRECIP_SENSITIVE_RANK_SHIFT` live | Calibrate GPM & POWER against ANRH/ONM rain gauges across North/Central/South Guelma (Phase E Pillar 4) |
| `RISK-K03` | Climatology Averaging Masks Extreme Single-Year Failures | **HIGH** | `BACKTEST_BOU_2021_PRE_DRY2022` (`2017–2021` GPM `616.72 mm`) recommended `STRAT_SOIL_IMPROVEMENT` right before severe `2022` drought (`356.166 mm` wilaya GPM; `444.04 mm` Boumahra) | Phase I runs dual-climate stress and emits `CONDITIONAL_RECOMMENDATION_REQUIRES_LOCAL_VERIFICATION` | Add dry-decile / drought-year conditional stress warning or seasonal forecast hook in future version |
| `RISK-K04` | Missing DEM Relief / Slope & Drainage Hazard | **HIGH** | Local DEM is `UNAVAILABLE_NOT_INTEGRATED`; wet `2019` (`835.6 mm` GPM in `Belkheir/Boumahra` on `33.76%` clay) poses unmeasured waterlogging hazard | `RULE_DEM_DRAINAGE_UNCERTAINTY` (`EXPERT_ASSUMPTION`) marks drainage-sensitive crops `UNKNOWN`/`WARNING` | Integrate SRTM/ALOS/local 10–30 m DEM slope & flow accumulation index |
| `RISK-K05` | Unmeasured Irrigation & Soil Salinity (`ECe`/`ECw`) + Macro-Nutrients | **HIGH** | `Seybouse` irrigated perimeter salinity risk (`ECe`, `ECw`, `CaCO3`, `Olsen-P`, `K`) unmeasured at parcel level | `RULE_SALINITY_UNMEASURED_IRRIGATION` (`UNKNOWN`) holds `TOMATO_IND` & irrigated candidates conditional | Pre-screening lab soil/water EC & P/K test gate for irrigated recommendations (Phase E Pillar 4) |
| `RISK-K06` | `SoilGrids 250 m` Pixel Masking & Quarantined Nitrogen | **MEDIUM-HIGH** | Observed live in `SPAT_BOU_SMALL_2HA_RAINFED` (`1.79 ha`, `clay=null`) and `SPAT_OUED_ZENATI_RAINFED` (`clay=null`, `soc=null`); SoilGrids Nitrogen quarantined (`100%` artifact/NaN) | Urban/non-cropland masks emit explicit `null` + `UNKNOWN` soil rules; never imputed or zero-filled | Use `30–50` core local soil lab survey to fill masked parcels & validate `pH`/`SOC`/`texture` (Phase E Pillar 4) |
| `RISK-K07` | Heuristic `soil_improvement` Not Coupled to Soil Carbon Mass Balance | **MEDIUM** | `SENS_BOU_PARTIAL_SOILGRIDS` changes `soil_improvement.status` to `PARTIAL` when `clay`/`soc` are `null`, but numeric score remains identical (`0.876238`) because it maps qualitative `_SOM_DIRECTION_SCORES` | Explicit `status = PARTIAL` and missing-data notes surfaced in Phase I/J | Replace or augment ordinal SOM score with RothC / regional SOC balance calibration if quantitative C credits are desired |
| `RISK-K08` | Incomplete Legume N-Fixation Bounds (`PARTIAL` Nitrogen Objective) | **MEDIUM** | In `agronomic_knowledge/crop_profiles.json`, only `FABA_BEAN` has `100.0–200.0 kg N/ha`; `CHICKPEA_WINTER`, `CHICKPEA_SPRING`, `LENTIL`, `VETCH_OAT` have `None` | Phase I assigns `status = PARTIAL` instead of inventing `kg N/ha` values | Obtain ITGC/ICARDA Guelma nodulation & biological N fixation ranges for chickpea, lentil, and vetch-oat |
| `RISK-K09` | Coarse Climate Grids (`11–69 km`) & Single-Snapshot Sentinel-2 (`2024-03`) | **MEDIUM** | `GPM`/`SMAP` (`~11 km`) and `NASA POWER` (`~55–69 km`) miss field microclimate; `SENS_BOU_REDUCED_S2_NULL` confirms S2 (`2024-03`) affects `bare_field_periods` & completeness (`0.8846` vs lower) without altering ranking | Explicit spatial-scale disclaimers in `regional_caveats` & `evidence` | Expand multi-year Sentinel-2 NDVI/NDWI time series across `2017–2025` for historical vigor diagnostics |
| `RISK-K10` | Unverified Crops & Expert-Assumed Rules | **MEDIUM** | `POTATO` & `SUNFLOWER` are `HYPOTHESIS_NEEDS_DSA_CHECK`; `RULE_DEM_DRAINAGE_UNCERTAINTY`, `RULE_FORAGE_REQUIREMENT_ALIGNMENT`, `SEQ_09` are `EXPERT_ASSUMPTION`; `VETCH_OAT`/`SUNFLOWER`/`OLIVE`/`BARE_FALLOW` lack `kc_mid` | `RULE_HYPOTHESIS_LOCAL_EVIDENCE_STATUS` forces `WARNING` and blocks clean `FEASIBLE_PASS` | DSA Guelma & ITGC Delphi agronomic sign-off (Phase E Pillar 2) |
| `RISK-K11` | Cross-Border Polygons Evaluated Only Within Wilaya Clip | **MEDIUM** | `SPAT_BORDER_PARTIAL_WILAYA` (`3971.84 ha`, `wilaya_overlap_pct = 32.0043%`) evaluates only Guelma piedmont fraction (`soc = 28.0231 g/kg`) | Spatial validator emits explicit partial-boundary warning & `overlap_pct` | Reject or expand raster coverage to neighboring wilayas if cross-border farms require full-parcel coverage |
| `RISK-K12` | Confusing Weight `stability_index` with Scientific Accuracy | **MEDIUM** | High `stability_index` only indicates robustness against `+/-25%` OAT & focus perturbations of heuristic linear weights | Phase J exposes `completeness_score` separately from heuristic ranking and keeps status `CONDITIONAL` | Never market `stability_index` or weighted score as probability of agronomic success |

---

## 2. Detailed Risk Notes

### 2.1 Why Passing Unit & Schema Tests Does Not Prove Agronomic Validity
- **59+ deterministic regression tests** verify software reproducibility, temporal non-leakage guards (`CropFreq 2021–2025` excluded from pre-2021 runs), Draft 2020-12 contract compliance, and fail-closed `UNKNOWN` handling.
- However, **zero empirical ground-truth yield or crop-classification datasets** exist in the project workspace (`Section 9` verdict: `Empirical supervised yield & plot validation = NOT_VALIDATABLE`). Consequently:
  1. Actual wheat/barley/pulse `t/ha` response curves under Guelma climatic extremes cannot yet be benchmarked quantitatively (`RMSE` / `R²`).
  2. Farmgate gross margins (`income_potential`) intentionally stay `UNKNOWN`, meaning trade-offs between irrigated `TOMATO_IND` vs `BARLEY`/`VETCH_OAT` cannot reflect true net economic cash-flow until local budgets are supplied.
  3. Pest pressure intensity (e.g., *Orobanche crenata* seedbank density on specific farms or *Fusarium* levels) cannot be observed from `10 m` or `250 m` optical satellites; sequence rules act strictly as structural break-year precautions (`3–4` years).

### 2.2 Operational Guidance Until Field Validation Gates Are Passed
1. **Do NOT deploy autonomously directly to unassisted farmers** as an automated prescription engine.
2. **Safe Current Use:** Internal screening and structured advisory support for **ITGC / DSA agronomists**, accompanied explicitly by:
   - The `CONDITIONAL_RECOMMENDATION_REQUIRES_LOCAL_VERIFICATION` banner,
   - Soil salinity (`ECe`/`ECw`) verification before irrigated `TOMATO_IND` or `POTATO`,
   - Field drainage slope inspection in heavy alluvial Seybouse clays (`Belkheir`, `Boumahra`, `Bouchekouf`), and
   - Farmer livestock, machinery, and market-contract confirmation.
