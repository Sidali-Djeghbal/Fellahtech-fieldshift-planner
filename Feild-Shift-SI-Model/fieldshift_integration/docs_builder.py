"""Task 8: Generate Canonical Data Dictionary, Specifications, Phase D Report & Root README."""

from datetime import datetime, timezone
from typing import Dict

import pandas as pd

from .config import (
    DOCS_INT_DIR,
    METADATA_INT_DIR,
    PROJECT_ROOT,
)


def build_all_documentation(
    inv_df: pd.DataFrame,
    canon_counts: Dict,
    spatial_info: Dict,
    feat_counts: Dict,
    val_df: pd.DataFrame,
) -> None:
    """Create canonical_data_dictionary.csv, 3 harmonization/feature specs, phaseD_integration_report.md & root README.md."""
    METADATA_INT_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_INT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Canonical Data Dictionary
    dd_rows = [
        # Spatial Reference
        ("spatial_reference/guelma_wilaya_utm32n.gpkg", "spatial_unit_id", "string", "-", "Static", "Wilaya polygon identifier (GUELMA_WILAYA, 3683.2311 km2, EPSG:32632)", "None"),
        ("spatial_reference/guelma_communes_utm32n.gpkg", "GID_2 / NAME_2 / commune_num_id", "string/int", "-", "Static", "34 GADM 4.1 commune identifiers, names & sequential IDs (sum 3683.2311 km2)", "None"),
        ("spatial_reference/grid_250m_utm32n_master.csv", "grid_250m_id / x_utm32n_m / y_utm32n_m", "string/float", "m (EPSG:32632)", "250 m", "59,050 valid UTM32N 250m pixels aligned to (315250, 4060000) & commune join", "None"),
        ("spatial_reference/grid_11km_utm32n_master.csv", "cell_id / X_UTM32N_m / Y_UTM32N_m", "string/float", "m (EPSG:32632)", "11,000 m", "45 valid SMAP/aligned seasonal cells on (308000, 4070000)", "Macro climate grid only"),
        # Climate
        ("climate_observations/nasa_power_daily_canonical.csv", "T2M / T2M_MAX / T2M_MIN / PRECTOTCORR / RH2M / ALLSKY_SFC_SW_DWN", "float", "degC; mm/day; %; kWh/m2/day", "AG 0.5x0.625 / RE 1.0 deg", "Daily area-weighted regional weather across Guelma (2016-01-01..2025-12-31, 3,653 days)", "Regional context, NOT field station"),
        ("climate_observations/nasa_power_monthly_canonical.csv", "T2M_mean_C / PRECTOTCORR_sum_mm / RH2M_mean_pct / ALLSKY_SFC_SW_DWN_*", "float", "degC; mm/mo; %; kWh/m2", "AG / RE regional", "Monthly regional weather aggregates (120 months, 2016-01..2025-12)", "Regional context"),
        # Precipitation
        ("precipitation_observations/gpm_seasonal_11km_canonical.csv", "gpm_precip_mm", "float", "mm/season", "11 km aligned (from 9.63 km)", "Seasonal total precipitation per 11km cell (2016-2025 x 4 seasons; NO monthly GPM on disk)", "Do not interpolate to monthly or 10m"),
        # Soil Moisture
        ("soil_moisture_observations/smap_seasonal_11km_canonical.csv", "smap_sm_surface_m3m3 / smap_sm_rootzone_m3m3", "float", "m3/m3", "11,000 m", "Seasonal surface (0-5cm) & rootzone (0-100cm) volumetric moisture (NO monthly SMAP on disk)", "Coarse 11km macro wetness"),
        # Soil Properties
        ("soil_properties/soilgrids_250m_canonical.csv", "clay/sand/silt_* / ph_* / soc_* / cec_* / usda_texture_*", "float/int", "% ; pH ; g/kg ; cmol(c)/kg ; class", "250 m (EPSG:32632)", "6-depth V6_MERGED properties + thickness-weighted 0-30cm & 30-100cm aggregates", "Gridded predictions, not lab samples"),
        ("soil_properties/soilgrids_250m_canonical.csv", "nitrogen_* / nitrogen_scaling_flag", "float/str", "unvalidated unit", "250 m", "Raw Nitrogen retained solely for traceability; subsoil N>SOC anomaly observed", "UNVALIDATED_TRACEABILITY_ONLY — exclude from scoring"),
        # Vegetation
        ("vegetation_observations/sentinel2_monthly_wilaya_canonical.csv", "NDVI_*/EVI_*/NDMI_*/NDRE_* / NDVI_valid_pct / is_model_eligible_monthly", "float/bool", "unitless; px; %", "10m (NDVI,EVI) / 20m (NDMI,NDRE)", "108 monthly Guelma regional statistics (2017-01..2025-12); 2017-01 flagged PARTIAL_LOW_COVERAGE (1.42%)", "No species/yield/rotation inference"),
        ("vegetation_observations/modis_seasonal_wilaya_canonical.csv", "modis_ndvi_mean / modis_evi_mean / modis_valid_obs_mean", "float", "unitless; obs count", "250 m", "MODIS MOD13Q1 40 seasonal regional stats (2016-2025)", "Coarse greenness proxy"),
        # Engineered Features
        ("features/wilaya_monthly_panel_2016_2025.csv", "prectot_lag1_mm / prectot_antecedent_3m_sum_mm / t2m_lag1_mean_c / rh2m_lag1_mean_pct", "float", "mm; degC; %", "Wilaya (3683.23 km2)", "Strictly causal lagged climate covariates paired with monthly S2 outcomes", "Exclude 2017-01; beware same-month VI leakage"),
        ("features/wilaya_seasonal_panel_2016_2025.csv", "GPM/SMAP/MODIS/NASA_POWER/S2 seasonal merged", "mixed", "mm; m3/m3; degC; unitless", "Wilaya regional", "40 seasonal rows (2016-2025 x 4 seasons) combining all dynamic domains; S2 explicitly flagged monthly-aggregated", "Winter 2016 incomplete climate; Winter 2017 incomplete S2"),
        ("features/commune_static_soil_and_land_features.csv", "clay/ph/soc/cec_0_30cm / crop_freq_2021_2025_mean / s2_2024_03_*", "float", "mixed", "34 Communes", "Commune zonal soil/cropland/climate profile; 2024-03 S2 snapshot only", "CropFreq restricted to 2021-2025"),
        ("features/commune_seasonal_panel_2016_2025.csv", "modis_* / gpm_precip_mm / smap_* / np_* / *_lag1_season_*", "float", "unitless; mm; m3/m3; degC", "34 Communes x 40 seasons", "1,360 commune-season records preserving macro context warning tags", "Coarse climate varies gently across communes"),
        ("features/landscape_250m_static_features.csv", "Soil 0-30cm + MODIS 2016-2025 seasonal means + CropFreq_250m + S2_2024_03_250m", "float", "mixed", "250 m grid (59,050 px)", "Landscape static soil + downward-aggregated 10m/20m baseline table", "Zero coarse upsampling included"),
    ]
    pd.DataFrame(
        dd_rows,
        columns=["dataset_rel_path", "column_or_band_group", "dtype", "unit", "spatial_support", "description", "guardrail_or_limitation"],
    ).to_csv(METADATA_INT_DIR / "canonical_data_dictionary.csv", index=False, encoding="utf-8")

    # 2. Temporal Harmonization Specification
    temp_doc = """# Temporal Harmonization Specification — Field Shift (Phase D)

## 1. Authoritative Source Cadences Verified on Disk
- **NASA POWER (`AG` & `RE`):** Daily (`2016-01-01`..`2025-12-31`, `3,653` days), Monthly (`120` months), Seasonal (`41` rows `Winter 2016..Winter 2026`), Annual (`10` years).
- **Sentinel-2 (`COPERNICUS/S2_SR_HARMONIZED`):** Monthly (`2017-01`..`2025-12`, `108` months), Scene Inventory (`2016-12`..`2025-12`, `3,593` scenes). Pixel-level seasonal/annual GEE tasks remain deferred due to noncommercial `restricted mode`; exploratory seasonal/annual summaries are strictly tagged `Mean of monthly medians`.
- **GPM IMERG & SMAP L4:** Verified on disk at **Seasonal (`DJF/MAM/JJA/SON`, `2016–2025`)** and **Annual (`2016–2025`)** cadences ONLY. **Zero monthly GPM or SMAP files exist locally** — no monthly disaggregation or interpolation was invented.
- **MODIS `MOD13Q1`:** Verified on disk at **Seasonal (`2016–2025`)** and **Annual (`2016–2025`)** cadences (`250 m`).
- **Static Baselines:** `SoilGrids 2.0 V6` (time-invariant profile) & `ESA Crop Frequency` (static fraction over **`2021–2025` only**).

## 2. Common Analytical Windows & Seasonal Convention
- **Full Climate & Macro-Hydrology Window:** `2016-01` through `2025-12` (`120` months, `40` full year-seasons). `2016` serves as antecedent baseline (`Winter 2017` pre-season moisture/rainfall) and is never joined into Sentinel-2 monthly regressions.
- **Overlapping Monthly Sentinel-2 + Climate Window:** `2017-01` through `2025-12` (`108` months), with **`2017-02..2025-12` (`107` months)** eligible for modeling (`is_model_eligible_monthly = True`).
- **Meteorological Seasons:** Uniform across every dataset: `Winter = DJF` (December shifted to `season_year = year + 1`), `Spring = MAM`, `Summer = JJA`, `Autumn = SON`.

## 3. Incomplete Periods & Zero vs. Missing Distinction
- **`2017-01` (Sentinel-2):** Contains `1` L2A scene covering `1.4173%` (`522,022 / 36,832,135 px`). Explicitly flagged `PARTIAL_LOW_COVERAGE` and `is_model_eligible_monthly = False`.
- **`Winter 2017` (`2016-12..2017-02`):** Incomplete across Sentinel-2 (`1` scene in `2016-12`, `1` in `2017-01`) — flagged `is_winter_2017_incomplete = True`.
- **`Winter 2016` & `Winter 2026` (NASA POWER):** Boundary-truncated (`60` days & `31` days respectively vs. `90/91`) — flagged `is_complete_season = False`.
- **Missing vs. True Zero:** Raster `-9999.0` NoData values and sealed/non-soil masks (`USDA_texture == 0` / SoilGrids NaN) are strictly masked prior to every reduction and never treated as `0` precipitation, `0` NDVI, or `0` soil carbon.
"""
    (DOCS_INT_DIR / "temporal_harmonization_specification.md").write_text(temp_doc, encoding="utf-8")

    # 3. Spatial Harmonization Specification
    cf = spatial_info["crop_freq_align"]
    spat_doc = f"""# Spatial Harmonization Specification — Field Shift (Phase D)

## 1. Multi-Resolution Architecture (`EPSG:32632`, Zero Fake Upsampling)
Field Shift spans four physical scale regimes (`10 m` to `~111 km`). Every canonical table and feature matrix records its exact analytical support (`spatial_unit`) and **only permits downward aggregation (fine -> coarse)**:

| Analytical Tier | Common Spatial Unit | Grid Origin / Geometry (`EPSG:32632`) | Integrated Sources & Support Rule |
|---|---|---|---|
| **Tier 1: Wilaya Monthly / Seasonal Panel** | `1` Guelma polygon (`3683.2311 km²`) | `guelma_wilaya_utm32n.gpkg` | Sentinel-2 (`10 m`/`20 m` medians), NASA POWER (`AG`/`RE` area-weighted), plus seasonal `GPM`, `SMAP`, `MODIS` |
| **Tier 2: Commune Decision Units** | `34` GADM 4.1 Communes (`36.23–317.35 km²`, sum `3683.2311 km²`) | `guelma_communes_utm32n.gpkg` | Downward zonal SoilGrids (`250 m`), MODIS (`250 m`), Crop Frequency (`10 m` snapped), S2 `2024-03` baseline; **area-weighted polygon intersections** for `GPM/SMAP (11 km)` & `NASA POWER (AG/RE)` tagged explicitly as macro-climate context |
| **Tier 3: Landscape Pixel Grid** | `59,050` valid Soil/Land pixels (`250 m × 250 m`) | `(315250.0, 4060000.0)`, `286 × 367` | SoilGrids `V6_MERGED`, SoilGrids `USDA Texture`, MODIS `MOD13Q1` (exact same grid!), plus downward `25×25` averaged Crop Frequency (`10 m`) & S2 `2024-03` snapshot (`10 m`/`20 m`) |
| **Tier 4: Coarse Hydro-Climate Grid** | `45` SMAP/aligned cells (`11,000 m × 11,000 m`) | `(308000.0, 4070000.0)`, `8 × 9` | `SMAP L4`, `GPM IMERG` aligned (`~9.63 km -> 11 km`), downward MODIS (`250 m -> 11 km`) |

## 2. Verified Raster Grid-Alignment Fixes Applied
1. **ESA Crop Frequency vs. Sentinel-2 `10 m` Origin Shift Fixed:**
   - Raw `guelma_crop_frequency_2021_2025_utm32n.tif` had origin `{cf['raw_origin']}` (`7341 × 9268`), shifted by **`{cf['origin_shift_before_fix_m'][0]} m` East / `{cf['origin_shift_before_fix_m'][1]} m` North** relative to Sentinel-2 `10 m` (`{cf['s2_10m_origin']}`, `{cf['aligned_shape_hw'][0]} × {cf['aligned_shape_hw'][1]}`).
   - **Action Executed:** Reprojected cleanly via `Resampling.nearest` onto the exact Sentinel-2 `10 m` transform (`guelma_crop_frequency_2021_2025_aligned_s2_10m.tif`) before any `250 m` or Commune aggregation, keeping original files untouched.
2. **Defective Raw SoilGrids File Bypassed:**
   - Verified empirically that `data/SoilGrids/drive-download-20261114T174721Z-1-001/guelma_soilgrids_42bands_250m.tif` (`ESRI:54009`) contains **`0` finite pixels across all `42` bands**.
   - **Action Executed:** Extracted SoilGrids strictly from the verified UTM32N archive `guelma_soilgrids_42bands_250m_V6_MERGED.tif` inside `guelma_soilgrids_V6_complete_package.zip` (`59,041–59,050` valid pixels), matching the exact `(315250.0, 4060000.0)` `250 m` grid of `MODIS MOD13Q1` and `guelma_USDA_texture_classes_6depths_250m.tif`.
3. **Pre-Phase-B March 2024 Sentinel-2 Zero-Exterior Masking:**
   - Because Phase A `2024-03` GeoTIFFs retain `0` outside Guelma, all `250 m` & Commune reductions mask exterior pixels using `geometry_mask` / `rasterize` (`all_touched=False`) before aggregation so exterior zeros never contaminate averages.
"""
    (DOCS_INT_DIR / "spatial_harmonization_specification.md").write_text(spat_doc, encoding="utf-8")

    # 4. Feature Engineering Specification
    feat_doc = """# Feature Engineering Specification — Field Shift (Phase D)

## 1. Strict Scientific Scope
All engineered features in Phase D are **strictly descriptive physical/spectral observations and causal temporal lags**. No synthetic crop suitability labels, species identifications, crop rotation histories, irrigation flags, or yield estimates are derived from vegetation indices or climate features in this stage.

## 2. Feature Catalog by Domain

| Domain | Tables | Engineered Features | Physical / Statistical Method | Explicit Safeguards |
|---|---|---|---|---|
| **Climate (NASA POWER)** | `wilaya_monthly_panel`, `commune_seasonal_panel` | `T2M_mean_C`, `T2M_MAX_mean_C`, `T2M_MIN_mean_C`, `diurnal_temp_range_mean_c`, `PRECTOTCORR_sum_mm`, `RH2M_mean_pct`, `ALLSKY_SFC_SW_DWN_mean_kwh_m2_day`; **causal lags**: `prectot_lag1_mm`, `prectot_lag2_mm`, `prectot_antecedent_3m_sum_mm`, `t2m_lag1_mean_c`, `rh2m_lag1_mean_pct` | Exact polygon intersection area-weighted means (`AG` & `RE` kept separate); `shift(1..3)` past-only rolling windows | Macro regional context (`~55–111 km`); never interpreted as field weather stations |
| **Precipitation & Moisture (GPM + SMAP)** | `wilaya_seasonal_panel`, `commune_seasonal_panel` | `gpm_precip_cell_mean_mm`, `gpm_precip_cell_std_mm`, `smap_sm_surface_m3m3`, `smap_sm_rootzone_m3m3`; causal `lag1_season` counterparts | Area-weighted overlay (`11 km` cells onto `34` communes / Wilaya mean); seasonal cadence only (`gpm_monthly_available=False`, `smap_monthly_available=False`) | Never upsampled to `10 m`/`250 m` or interpolated to monthly |
| **Soil Properties (SoilGrids V6)** | `soilgrids_250m_canonical`, `commune_static_soil_and_land_features`, `landscape_250m_static_features` | Depth-weighted rootzone averages **`0–30 cm`** (`clay, sand, silt, ph, soc, cec`) and **`30–100 cm`**; `usda_texture_0_5cm`; `soil_valid_fraction` per commune | Horizon thickness weighting: `(5*d1 + 10*d2 + 15*d3)/30` for `0–30 cm` and `(30*d4 + 40*d5)/70` for `30–100 cm` | **`soil_nitrogen_0_30cm_unvalidated` carried for traceability ONLY (`N > SOC` subsoil scaling anomaly)**; gridded estimates, not soil lab samples |
| **Vegetation & Cropland Masking** | `wilaya_monthly_panel`, `wilaya_seasonal_panel`, `commune_*`, `landscape_250m_*` | `s2_NDVI_*/EVI_*/NDMI_*/NDRE_*` medians & `s2_ndvi_iqr_p95_p5`, `s2_valid_pct`, `s2_mean_valid_obs_per_px_10m`, `s2_evi_obs_excluded_total_10m`, `s2_scl2_share_pct`; `modis_ndvi/evi` (`250 m`); `crop_freq_2021_2025_mean` | Native `10 m` (`NDVI, EVI`) & `20 m` (`NDMI, NDRE`); downward `Resampling.average` onto `250 m` & commune polygons after fixing `CropFreq` grid shift | `2017-01` (`1.42%`) ineligible; `contemporaneous_vi_leakage_risk` flagged; `crop_freq_usable_for_year = (season_year >= 2021)` blocks `2017–2020` look-ahead leakage |
"""
    (DOCS_INT_DIR / "feature_engineering_specification.md").write_text(feat_doc, encoding="utf-8")

    # 5. Phase D Integration Report
    pass_cnt = int((val_df["status"] == "PASS").sum())
    chk_cnt = int((val_df["status"] == "CHECK").sum())
    fail_cnt = int((val_df["status"] == "FAIL").sum())
    val_md = "\n".join(
        [f"| `{r['check_id']}` | {r['category']} | `{r['measured_value']}` | **{r['status']}** | {r['notes']} |" for _, r in val_df.iterrows()]
    )

    rep_doc = f"""# Phase D Cross-Dataset Integration & Validation Report — Field Shift

**Study Domain:** Guelma Wilaya, Algeria (`3683.2311 km²`, `34` Communes, `EPSG:32632`)  
**Generated UTC:** `{datetime.now(timezone.utc).isoformat()}`  
**Execution Mode:** `100%` Local / Non-Destructive (Zero GEE tasks submitted; zero raw datasets overwritten; no crop modeling started)  
**Validation Outcome:** **`PASS = {pass_cnt}` | `CHECK = {chk_cnt}` | `FAIL = {fail_cnt}`**

---

## 1. Empirical Source Audit Corrections Discovered on Disk
During Task 1 verification against actual workspace files (rather than filenames/docs alone), Phase D caught and handled three critical data realities:
1. **Empty `ESRI:54009` Raw SoilGrids Raster:** `data/SoilGrids/drive-download-20261114T174721Z-1-001/guelma_soilgrids_42bands_250m.tif` contains **`0` finite pixels** across all `42` bands. Integration extracts soil layers exclusively from verified `guelma_soilgrids_42bands_250m_V6_MERGED.tif` inside `guelma_soilgrids_V6_complete_package.zip` (`59,041–59,050` valid UTM32N `250 m` pixels).
2. **GPM IMERG & SMAP L4 Cadence Availability:** Both datasets exist locally at **Seasonal (`DJF/MAM/JJA/SON`) and Annual (`2016–2025`) cadences only** — **no monthly GPM or SMAP files exist on disk**. Phase D leaves `gpm_monthly_available_on_disk = False` and `smap_monthly_available_on_disk = False` rather than inventing synthetic monthly values.
3. **ESA Crop Frequency (`10 m`) Grid-Origin Shift:** `guelma_crop_frequency_2021_2025_utm32n.tif` was shifted `{cf['origin_shift_before_fix_m'][0]} m` E / `{cf['origin_shift_before_fix_m'][1]} m` N relative to Sentinel-2 `10 m` (`{cf['s2_10m_origin']}`). Phase D snaps it cleanly to [guelma_crop_frequency_2021_2025_aligned_s2_10m.tif](file:///home/lokman/Desktop/FeildShit-SI-Model/data/INTEGRATED/spatial/guelma_crop_frequency_2021_2025_aligned_s2_10m.tif) before `250 m`/Commune downward aggregation, and blocks its use on `2017–2020` historical rows.

---

## 2. Canonical Layers & Analytical Feature Outputs Produced

| Output Tier | File | Records | Temporal Scope | Spatial Support |
|---|---|---:|---|---|
| **Inventory** | [data_inventory.csv](file:///home/lokman/Desktop/FeildShit-SI-Model/data/INTEGRATED/metadata/data_inventory.csv) | `{len(inv_df)}` datasets | `2016–2025` / Static | Multi-scale verified |
| **Canonical Layers** | `data/INTEGRATED/canonical/{{spatial_reference,climate_observations,precipitation_observations,soil_moisture_observations,soil_properties,vegetation_observations}}/` | `34` communes, `{canon_counts['soilgrids_250m_pixels']:,}` soil px, `{canon_counts['climate_daily']:,}` days, `{canon_counts['s2_monthly_rows']}` S2 mo | Native per source | Preserves native support |
| **Wilaya Monthly Features** | [wilaya_monthly_panel_2016_2025.csv](file:///home/lokman/Desktop/FeildShit-SI-Model/data/INTEGRATED/features/wilaya_monthly_panel_2016_2025.csv) | `{feat_counts['wilaya_monthly_panel']}` | `2016-01..2025-12` (`107` eligible S2 mo) | Wilaya (`3683.23 km²`) |
| **Wilaya Seasonal Features** | [wilaya_seasonal_panel_2016_2025.csv](file:///home/lokman/Desktop/FeildShit-SI-Model/data/INTEGRATED/features/wilaya_seasonal_panel_2016_2025.csv) | `{feat_counts['wilaya_seasonal_panel']}` | `Winter 2016..Autumn 2025` | Wilaya (`all sources`) |
| **Commune Static Features** | [commune_static_soil_and_land_features.csv](file:///home/lokman/Desktop/FeildShit-SI-Model/data/INTEGRATED/features/commune_static_soil_and_land_features.csv) | `{feat_counts['commune_static_features']}` | Static Soil + `2016–2025` clim | `34` Communes (`EPSG:32632`) |
| **Commune Seasonal Panel** | [commune_seasonal_panel_2016_2025.csv](file:///home/lokman/Desktop/FeildShit-SI-Model/data/INTEGRATED/features/commune_seasonal_panel_2016_2025.csv) | `{feat_counts['commune_seasonal_panel']}` | `2016–2025 × 4 seasons` | `34` Communes |
| **Landscape `250 m` Table** | [landscape_250m_static_features.csv](file:///home/lokman/Desktop/FeildShit-SI-Model/data/INTEGRATED/features/landscape_250m_static_features.csv) | `{feat_counts['landscape_250m_features']:,}` | Static Soil + `2016–2025` MODIS | `250 m` (`286×367`) |

---

## 3. Automated Validation Summary (`{pass_cnt} PASS`, `{chk_cnt} CHECK`, `{fail_cnt} FAIL`)

| Check ID | Category | Measured | Status | Notes |
|---|---|---|---|---|
{val_md}

---

## 4. Remaining Limitations & Readiness Recommendation

- **Remaining Scientific & Technical Limitations:**
  1. **No monthly GPM / SMAP files locally:** Sub-seasonal water-balance features rely on NASA POWER daily/monthly `PRECTOTCORR` at the monthly tier and `GPM`/`SMAP` at the seasonal tier (`DJF/MAM/JJA/SON`).
  2. **Multi-year Sentinel-2 `10 m`/`20 m` GeoTIFFs deferred by GEE `restricted mode`:** Sub-Wilaya (`34` Communes & `250 m`) multi-year Sentinel-2 columns (`2017–2025`) are not yet populated spatially; only the March 2024 `10 m`/`20 m` snapshot is available pixel-wise on disk.
  3. **SoilGrids Nitrogen (`N > SOC` subsoil anomaly):** Kept strictly unvalidated for traceability; exclude from quantitative soil scoring.
  4. **Coarse macro-climate homogeneity across Communes:** `NASA POWER (2 RE / 5 AG cells)` & `SMAP/GPM (11 km)` share broad spatial footprints across adjacent communes.
- **Readiness Verdict:**
  - **READY NOW** for exploratory **Wilaya-scale monthly/seasonal hydro-climatic & phenology modeling** (`2017-02..2025-12`, `107` complete months) AND **`34`-Commune / `250 m` MODIS + SoilGrids + GPM/SMAP multi-year (`2016–2025`) modeling**.
  - **DEFER fine `10 m`/`20 m` multi-year Sentinel-2 commune/field modeling** until GEE quota resets and Priority 1–3 Sentinel-2 GeoTIFF exports resume.
"""
    (DOCS_INT_DIR / "phaseD_integration_report.md").write_text(rep_doc, encoding="utf-8")

    # 6. Project Root README.md
    root_readme = f"""# Field Shift — Guelma Wilaya Agro-Environmental Data Foundation (`2016–2025`)

Data-driven agricultural decision-support data engineering repository for **Guelma Wilaya, Algeria** (`3683.2311 km²`, `34` communes, `EPSG:32632`), prepared for **NASA Space Apps Challenge 2026**.

## Project Pipeline Stages Completed
1. **NASA POWER Regional Climate (`2016–2025`):** Daily, monthly, seasonal, and annual area-weighted climate variables (`AG` `0.5°×0.625°` MERRA-2 + `RE` `1.0°×1.0°` CERES SYN1deg) -> `data/NASA_POWER_REGIONAL/processed/` (`run_nasa_power_pipeline.py`).
2. **Sentinel-2 Vegetation Indices (`2017–2025`, GEE Project `spry-framework-514800-j2`):** `108` monthly statistical summaries (`10 m` NDVI/EVI with `denom>0.1` + `SR>=0`; `20 m` NDMI/NDRE) + `3,593` scene metadata rows MD5-verified (`16 PASS, 1 CHECK, 0 FAIL`); deferred multi-year GeoTIFFs & pixel-median seasonal/annual tasks queued cleanly on noncommercial `restricted mode` -> `data/SENTINEL2/` (`sentinel2_pipeline/phaseC_runner.py`).
3. **Phase D Cross-Dataset Integration & Feature Engineering Foundation:** Canonical 6-layer normalization (`NASA POWER`, `GPM IMERG`, `SMAP L4`, `MODIS MOD13Q1`, `SoilGrids 2.0 V6`, `ESA Crop Frequency`, `Sentinel-2`, `GADM 4.1`), raster alignment fix (`Crop Frequency 10 m -> Sentinel-2 10 m`), downward-only `250 m` & `34`-Commune aggregations, causal lagged feature tables, and `{pass_cnt} PASS / {chk_cnt} CHECK / {fail_cnt} FAIL` automated validation -> `data/INTEGRATED/` (`run_phaseD_integration.py`).

## Key Phase D Integration Entrypoints & Deliverables
- **Run full reproducible Phase D pipeline locally (zero GEE calls):**
  ```bash
  ./venv/bin/python run_phaseD_integration.py
  ./venv/bin/python -m unittest discover -s tests -v
  ```
- **Inventory & Schema:**
  - `data/INTEGRATED/metadata/data_inventory.csv`
  - `data/INTEGRATED/metadata/canonical_data_dictionary.csv`
- **Specifications & Reports:**
  - `data/INTEGRATED/docs/phaseD_integration_report.md`
  - `data/INTEGRATED/docs/temporal_harmonization_specification.md`
  - `data/INTEGRATED/docs/spatial_harmonization_specification.md`
  - `data/INTEGRATED/docs/feature_engineering_specification.md`
  - `data/INTEGRATED/quality/phaseD_validation_report.csv`
- **Feature Matrices (`data/INTEGRATED/features/`):**
  - `wilaya_monthly_panel_2016_2025.csv` (`{feat_counts['wilaya_monthly_panel']}` rows)
  - `wilaya_seasonal_panel_2016_2025.csv` (`{feat_counts['wilaya_seasonal_panel']}` rows)
  - `commune_static_soil_and_land_features.csv` (`{feat_counts['commune_static_features']}` communes)
  - `commune_seasonal_panel_2016_2025.csv` (`{feat_counts['commune_seasonal_panel']}` rows)
  - `landscape_250m_static_features.csv` (`{feat_counts['landscape_250m_features']:,}` valid `250 m` pixels)

## Important Guardrails
- Coarse regional datasets (`NASA POWER ~55–111 km`, `SMAP 11 km`, `GPM 9.6 km`) are **never** upsampled to `10 m` field pixels.
- Monthly `GPM`/`SMAP` files do not exist on disk and are not fabricated; `2017-01` (`1.4173%` coverage) and `Winter 2017` are explicitly flagged ineligible.
- `Crop Frequency (2021–2025)` is blocked from predicting `2017–2020`, and `SoilGrids Nitrogen` is retained strictly for traceability pending unit validation.
"""
    (PROJECT_ROOT / "README.md").write_text(root_readme, encoding="utf-8")
