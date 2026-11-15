# Cross-Dataset Integration Specification — Field Shift (Guelma Wilaya, Algeria)

**Study Domain:** Guelma Wilaya (`3683.2311 km²` in `EPSG:32632`; `34` communes in [guelma_communes_boundaries.gpkg](file:///home/lokman/Desktop/FeildShit-SI-Model/data/boundaries/processed/guelma_communes_boundaries.gpkg))  
**Canonical Projected CRS:** `EPSG:32632` (WGS 84 / UTM Zone 32N)  
**Stage:** Local Integration Readiness Audit (No crop suitability modeling started; zero GEE calls issued)

---

## 1. Authoritative Multi-Source Inventory & Native Resolutions

| Dataset | Primary Local Source(s) | Temporal Span & Cadence | Native Spatial Resolution | Native / Target CRS | Grid Origin / Shape (`EPSG:32632`) | Valid Observations / Key Notes |
|---|---|---|---|---|---|---|
| **Sentinel-2 (`COPERNICUS/S2_SR_HARMONIZED`)** | [sentinel2_monthly_indices_2017_2025.csv](file:///home/lokman/Desktop/FeildShit-SI-Model/data/SENTINEL2/processed/monthly/sentinel2_monthly_indices_2017_2025.csv); `phaseA_2024_03/` GeoTIFFs; [sentinel2_scenes_2017_2025.csv](file:///home/lokman/Desktop/FeildShit-SI-Model/data/SENTINEL2/raw/phaseC_2017_2025/sentinel2_scenes_2017_2025.csv) | `2017-01..2025-12` (`108` monthly summaries); `2017–2025` multi-year composites deferred | `10 m` (`NDVI, EVI`), `20 m` (`NDMI, NDRE`) | `EPSG:32632` | `10 m`: `(315490, 4059820)`, `7131×9146`; `20 m`: `(315480, 4059820)`, `3566×4574` | `3,592` scenes (`2017–2025`); `107` complete months (`95.94%–100%`), `2017-01` partial (`1.42%`) |
| **ESA/GEE Crop Frequency** | [guelma_crop_frequency_2021_2025_utm32n.tif](file:///home/lokman/Desktop/FeildShit-SI-Model/data/land_cover/guelma_crop_frequency_2021_2025_utm32n.tif) | Static summary (`2021–2025`) | `10 m × 10 m` | `EPSG:32632` | `(314525.12, 4060721.97)`, `7341×9268` | `36,850,650` valid px (`nodata=-9999`), range `0.0–1.0`, mean `0.3503`; **offset `~5.1 m / 2.0 m` from S2 `10 m` grid** |
| **MODIS (`MOD13Q1`)** | [guelma_modis_seasonal_2025.tif](file:///home/lokman/Desktop/FeildShit-SI-Model/data/seasonal/guelma_modis_seasonal_2016_2025_analysis/guelma_modis_seasonal_2025.tif); [guelma_modis_vegetation_summary_2016_2025.csv](file:///home/lokman/Desktop/FeildShit-SI-Model/data/tables/guelma_modis_vegetation_summary_2016_2025.csv) | `2016–2025` (annual & `4`-season GeoTIFFs + summaries) | `250 m × 250 m` | `EPSG:32632` | `(315250, 4060000)`, `286×367` | `59,738` valid px (`45,224` masked exterior/nodata, `nodata=-9999`); provides `NDVI, EVI, valid_obs_count` |
| **SoilGrids 2.0 (`V6`)** | [guelma_soilgrids_42bands_250m.tif](file:///home/lokman/Desktop/FeildShit-SI-Model/data/SoilGrids/drive-download-20261114T174721Z-1-001/guelma_soilgrids_42bands_250m.tif); [guelma_USDA_texture_classes_6depths_250m.tif](file:///home/lokman/Desktop/FeildShit-SI-Model/data/SoilGrids/guelma_USDA_texture_classes_6depths_250m.tif); [guelma_soilgrids_pixel_dataset_250m_clean.csv](file:///home/lokman/Desktop/FeildShit-SI-Model/data/SoilGrids/guelma_soilgrids_pixel_dataset_250m_clean.csv) | Static (`6` depth intervals: `0–5, 5–15, 15–30, 30–60, 60–100, 100–200 cm`) | `250 m × 250 m` | Raw 42-band: `ESRI:54009`; `V6` & USDA: `EPSG:32632` | `ESRI`: `297×358`; UTM32N: `286×367` (`nodata=-9999` / `0` uint8) | `59,050` raster valid px (`58,317` clean complete-case rows in CSV; `45,912` masked non-soil/exterior px) |
| **GPM IMERG Precipitation** | [guelma_gpm_annual_rainfall_2016_2025_utm32n_stack.tif](file:///home/lokman/Desktop/FeildShit-SI-Model/data/GPM/guelma_gpm_annual_rainfall_2016_2025_utm32n_files/guelma_gpm_annual_rainfall_2016_2025_utm32n_stack.tif); [guelma_environmental_spatiotemporal_dataset_2016_2025.csv](file:///home/lokman/Desktop/FeildShit-SI-Model/data/tables/dataset/guelma_environmental_spatiotemporal_dataset_2016_2025.csv) | `2016–2025` (annual `10`-band GeoTIFF + seasonal aligned `11 km` table) | `~9,633.88 m × 9,633.88 m` (`~0.1°`) | `EPSG:32632` | `8×10` grid (`nodata=-9999`) | `61` valid cells (`19` exterior nodata); aligned table resamples GPM onto `11 km` SMAP grid |
| **SMAP L4 Soil Moisture** | [guelma_smap_soil_moisture_2016_2025_20bands.tif](file:///home/lokman/Desktop/FeildShit-SI-Model/data/SMAP/guelma_smap_soil_moisture_2016_2025_package/guelma_smap_soil_moisture_2016_2025_20bands.tif); [guelma_environmental_seasonal_aligned_2025.tif](file:///home/lokman/Desktop/FeildShit-SI-Model/data/seasonal/guelma_environmental_seasonal_aligned_2016_2025_package/guelma_environmental_seasonal_aligned_2025.tif) | `2016–2025` (annual `20`-band + seasonal `24`-band aligned stacks) | `11,000 m × 11,000 m` | `EPSG:32632` | `8×9` grid (`nodata=-9999`) | `45` valid `11 km` cells (`1,800` seasonal rows across `10 yr × 4 seasons × 45 cells`); `sm_surface` & `sm_rootzone` |
| **NASA POWER Regional Daily** | [nasa_power_daily_guelma.csv](file:///home/lokman/Desktop/FeildShit-SI-Model/data/NASA_POWER_REGIONAL/processed/daily/nasa_power_daily_guelma.csv); [nasa_power_monthly_guelma.csv](file:///home/lokman/Desktop/FeildShit-SI-Model/data/NASA_POWER_REGIONAL/processed/monthly/nasa_power_monthly_guelma.csv); `seasonal/` & `annual/` | `2016-01-01..2025-12-31` (`3,653` days, `120` months, `41` seasons, `10` years) | `AG` (`MERRA-2`): `0.5°×0.625°`; `RE` (`CERES`): `1.0°×1.0°` (`~55–111 km`) | Source: `EPSG:4326`; Areas: `EPSG:32632` | `5` intersecting `AG` cells, `2` intersecting `RE` cells (`100%` Wilaya coverage) | Zero missing days/values; cell boundaries estimated from centers; strictly **regional environmental context** |

---

## 2. Temporal Alignment Rules

1. **Common Overlapping Window:**
   - Full **Sentinel-2 + Climate/Soil** overlap spans **`2017-01-01` through `2025-12-31`** (`9` years / `108` months), with **`2018-01` through `2025-12` (`96` months, `32` seasons)** representing the completely cloud-unconstrained period.
   - `2016` (`NASA POWER`, `MODIS`, `GPM`, `SMAP`) contains only `1` Sentinel-2 L2A scene (`2016-12`) and **must not** be joined into Sentinel-2 modeling tables; retain `2016` strictly as pre-study climate baseline / `Winter 2017` antecedent meteorological forcing (`2016-12` rainfall/soil moisture feeding Spring `2017` green-up).
2. **Calendar Standardization:**
   - **Monthly key:** `YYYY-MM` (`108` months `2017-01..2025-12` direct inner/left join between `sentinel2_monthly_indices_2017_2025.csv` and `nasa_power_monthly_guelma.csv`).
   - **Seasonal key:** Meteorological northern-hemisphere seasons across ALL datasets: `Winter = DJF` (December assigned to `year + 1`), `Spring = MAM`, `Summer = JJA`, `Autumn = SON`.
   - **Lagged Climate Windows:** Align hydrological/thermal drivers **antecedently** to Sentinel-2 greenness (`t-1` and `t-2` monthly sums, or `Winter` / `DJF` rainfall + rootzone soil moisture joined to `Spring` / `MAM` peak `NDVI`/`EVI`).
3. **Static Layers:**
   - **SoilGrids 2.0:** Time-invariant physical/chemical baseline (`0–200 cm`), replicated across time per spatial unit (`250 m` cell or commune).
   - **ESA Crop Frequency (`2021–2025`):** Multi-year static land-cover fraction; **only valid as a static spatial stratification mask for `2021–2025`**, or explicitly restricted to permanent agricultural zones (`>0.5`) with caution on `2017–2020` look-ahead effects (see Section 7).

---

## 3. Spatial Aggregation Strategy & Common Spatial Units

Because datasets span **four orders of magnitude in linear resolution** (`10 m` to `~111 km`), integration must follow **strict downward aggregation only (fine -> coarse)** inside **Common Spatial Units (CSUs)** in `EPSG:32632`:

- **Golden Rule:** **NEVER** upsample, bilinearly interpolate, or replicate `NASA POWER` (`~55–111 km`), `SMAP` (`11 km`), `GPM` (`9.6 km`), or `MODIS/SoilGrids` (`250 m`) onto `10 m`/`20 m` pixels and present them as field-level observations.
- **Canonical Common Spatial Units (Choose One Tier per Task):**
  1. **Tier 1 — Wilaya Monthly Panel (`1` polygon = `3683.2311 km²`, `n = 107` complete months `2017-02..2025-12`):**
     - **Supported Today Locally:** Joins [sentinel2_monthly_indices_2017_2025.csv](file:///home/lokman/Desktop/FeildShit-SI-Model/data/SENTINEL2/processed/monthly/sentinel2_monthly_indices_2017_2025.csv) (`NDVI, EVI, NDMI, NDRE`) directly with [nasa_power_monthly_guelma.csv](file:///home/lokman/Desktop/FeildShit-SI-Model/data/NASA_POWER_REGIONAL/processed/monthly/nasa_power_monthly_guelma.csv) (`T2M, T2M_MAX, T2M_MIN, PRECTOTCORR, RH2M, ALLSKY_SFC_SW_DWN`), plus annual/seasonal Wilaya summaries from `MODIS`, `GPM`, and `SMAP`.
     - **Purpose:** Regional phenology-climate response analysis, drought anomaly tracking (`2019` wet vs. `2022–2023` drought).
  2. **Tier 2 — Commune Decision Units (`34` polygons in `guelma_communes_boundaries.gpkg`, `EPSG:32632`):**
     - **Target Join:** Aggregate `SoilGrids (250 m)` and `MODIS (250 m)` to commune polygons (`area-weighted zonal mean/median`), aggregate `Crop Frequency` inside agricultural strata, attach `SMAP (11 km)` / `GPM (9.6 km)` / `NASA POWER` explicitly flagged as **macro-climate context features**, and join **Sentinel-2 zonal stats** once deferred annual/seasonal/monthly GeoTIFFs (or commune GEE reductions) are exported post-quota-reset.
  3. **Tier 3 — `250 m` Landscape Grid (`286 × 367` `EPSG:32632` aligned to `(315250, 4060000)`):**
     - Matches native UTM `SoilGrids V6` (`250 m`) and `MODIS` (`250 m`). Aggregate Sentinel-2 `10 m` (`25 × 25` block mean/median) & `20 m` downward to the `250 m` grid after filtering cropland mask (`Crop Frequency >= 0.5`). Attach `SMAP`/`GPM`/`NASA POWER` only as hierarchical/regional covariates.
  4. **Tier 4 — `11 km` Existing Hydro-Climate Grid (`8 × 9`, `45` valid cells in `guelma_environmental_spatiotemporal_dataset_2016_2025.csv`):**
     - Preserves native `SMAP L4` cells alongside `GPM` & downward-aggregated `MODIS`; compatible with downward-aggregated Sentinel-2 (`10 m -> 11 km`) for broad agro-ecological zoning.

**Mandatory Pre-Join Grid Snap Check (`10 m` Layers):**
`guelma_crop_frequency_2021_2025_utm32n.tif` has origin `(314525.12, 4060721.97)` whereas Sentinel-2 `10 m` GeoTIFFs use `(315490.0, 4059820.0)`. Reproject/warp `Crop Frequency` onto the exact Sentinel-2 `10 m` transform (`Resampling.nearest`) before pixel-level masking or block aggregation.

---

## 4. Missing Data Treatment Protocol

| Dataset | Observed Missingness | Prescribed Handling Rule |
|---|---|---|
| **Sentinel-2 Monthly** | `2017-01` = `1.4173%` valid (`1` scene); `107/108` months = `95.94%–100.0%` | Filter out `2017-01` (`completeness_status == 'PARTIAL_LOW_COVERAGE'`) and `Winter 2017` (`INCOMPLETE_DEC2016(1scene)_AND_JAN2017(1.42%)`); do **not** temporally interpolate missing cloud/orbital pixels across months without explicit QC weights |
| **Sentinel-2 EVI Tail** | `534,281` obs / `1,262` composite px masked by `B2,B4,B8 >= 0` & `denom > 0.1` | Keep unclipped for `median` / `p5–p95` feature engineering; avoid unguarded `EVI_mean` if outliers (`up to 10.69`) affect linear models |
| **SoilGrids 2.0 (`250 m`)** | `45,912` masked pixels (urban/water/exterior out of `104,962` grid box); `733` CSV rows dropped (`59,050 -> 58,317` clean rows) | Enforce `valid_fraction >= 0.70` when aggregating `250 m` pixels to Communes; treat non-soil/sealed pixels (`USDA class == 0`) strictly as `NoData` (never zero-fill `pH`/`SOC`/`CEC`) |
| **GPM & SMAP** | `19/80` (`GPM`) & `27/72` (`SMAP`) exterior bounding-box pixels = `-9999.0` | Mask `-9999.0` cleanly on read (`src.read(masked=True)`); compute area-weighted intersection means over Guelma/Commune polygons rather than nearest pixel center |
| **NASA POWER** | `0` missing values across all `3,653` days (`100%` Guelma area intersection) | Boundary-truncated `Winter 2016` / `Winter 2026` have `is_complete_season = False` (exclude from complete seasonal modeling) |

---

## 5. Canonical Harmonized Feature Definitions

| Feature Name | Source | Unit | Scale / Temporal Aggregator | Interpretive Caveat |
|---|---|---|---|---|
| `s2_ndvi_med` / `s2_evi_med` | Sentinel-2 | unitless (`[-1, 1]` med) | `10 m` spatial median of pixel medians; monthly (`YYYY-MM`) | Canopy greenness/density proxy; **not** direct crop yield (`t/ha`) |
| `s2_ndmi_med` / `s2_ndre_med` | Sentinel-2 | unitless (`[-1, 1]` med) | `20 m` spatial median of pixel medians; monthly (`YYYY-MM`) | `NDMI` = canopy water proxy (**not** soil moisture); `NDRE` = red-edge chlorophyll proxy |
| `s2_valid_pct_10m` / `mean_obs_10m` | Sentinel-2 | `%` / `obs/px` | Monthly QC weight (`0–100%`) | Gate model rows (`>= 90%`) |
| `modis_ndvi_seasonal` / `evi` | MODIS `MOD13Q1` | unitless | `250 m` seasonal (`DJF/MAM/JJA/SON`, `2016–2025`) | Continuous `2016–2025` benchmark; coarse vs `10 m` plots |
| `sm_surface` / `sm_rootzone` | SMAP L4 | `m³/m³` (`% v/v ÷ 100`) | `11 km` seasonal / annual (`2016–2025`) | True volumetric soil moisture proxy (`11 km` regional/basin scale) |
| `gpm_precip_mm` | GPM IMERG | `mm` | `~9.6 km` seasonal / annual total (`2016–2025`) | Captures spatial precipitation gradients better than `~55 km` MERRA-2 (`PRECTOTCORR`) |
| `np_t2m_mean` / `tmax` / `tmin` | NASA POWER (`AG`) | `°C` | `0.5°×0.625°` area-weighted mean (`daily/monthly/seasonal`) | Regional thermal regime (`GDD`, heat-stress days `>35 °C`, frost risk) |
| `np_prectot_sum_mm` / `np_rh2m` / `np_swdwn` | NASA POWER (`AG`/`RE`) | `mm`, `%`, `kWh/m²/day` | `AG` (`0.5°×0.625°`) & `RE` (`1.0°×1.0°`) separate | Use `SW_DWN` for radiation; never blend `AG` & `RE` footprint areas |
| `soil_clay/sand/silt`, `soil_ph`, `soil_soc`, `soil_cec`, `soil_n`, `usda_texture` | SoilGrids 2.0 | `%`, `pH`, `g/kg`, `cmol(c)/kg`, raw `N` index | `250 m` static (`6` depths, prioritize `0–30 cm` depth-weighted mean) | Static edaphic baseline (`nitrogen` scaling divisor must be confirmed prior to nutrient balance calculations; see SoilGrids V6 notes) |
| `crop_freq_21_25` | ESA/GEE CropFreq | `0.0 – 1.0` | `10 m` fraction of years cropped (`2021–2025`) | Static agricultural mask (`>=0.5` cropland threshold after grid snap) |

---

## 6. Data Leakage & Scale Mismatch Risks (Mandatory Controls)

1. **Cross-Scale Ecological Fallacy (Scale Mismatch):**
   - Training a `10 m` or `250 m` suitability classifier where `NASA POWER` (`~55–111 km`, `2–5` cells over the whole Wilaya) or `SMAP` (`11 km`, `45` cells) is treated as a pixel-level predictor causes pseudo-replication and inflated feature importance. **Control:** Keep macro-climate variables as group-level / mixed-effects covariates or spatial-temporal block CV predictors (`Leave-One-Year-Out` + `Spatial Block CV`), not per-10m-pixel independent features.
2. **Temporal Target Leakage via Contemporaneous Vegetation Indices:**
   - Using May/June `NDVI`/`EVI` (`s2_ndvi_med`) to "predict" same-season agricultural suitability or yield within the same growing cycle encodes post-emergence outcome inside features. **Control:** Separate structural **inherent suitability** models (soil + climatology + terrain + antecedent pre-sowing moisture) from **in-season monitoring / anomaly** models (`t-1`/`t-2` lags).
3. **`2021–2025` Crop Frequency Look-Ahead Leakage:**
   - Applying `guelma_crop_frequency_2021_2025_utm32n.tif` to label or filter `2017–2020` training samples leaks future land-use persistence (`2021–2025`) backward into earlier years. **Control:** Restrict crop-frequency filtering strictly to `2021–2025` evaluation or static spatial masks validated independently against `2017` land cover.
4. **Conflating Monthly-Aggregated Summaries with Pixel-Level Seasonal Medians:**
   - Joining [sentinel2_seasonal_from_monthly_2017_2025.csv](file:///home/lokman/Desktop/FeildShit-SI-Model/data/SENTINEL2/processed/seasonal/sentinel2_seasonal_from_monthly_2017_2025.csv) (`mean of 3 monthly medians`) interchangeably with true `GEE pixel-median` seasonal features introduces silent distributional shift once deferred GEE tasks complete. **Control:** Version feature names explicitly (`_from_monthly` vs `_px_median`) and forbid mixing across train/test splits.
5. **Dual-Resolution Index Leakage (`10 m` vs `20 m`):**
   - Stacking `20 m` `NDMI`/`NDRE` onto `10 m` `NDVI`/`EVI` via naive nearest-neighbor duplication inflates spatial degrees of freedom by `4×`. **Control:** Perform joint 4-index modeling at `20 m` (downsampling `10 m -> 20 m`) or coarser (`250 m` / Commune).
