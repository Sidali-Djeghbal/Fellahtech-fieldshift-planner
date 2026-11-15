# Technical Data Integration Report — Field Shift (Guelma Wilaya, 2016–2025)

This technical report documents every verifiable operation executed on the Field Shift environmental, soil, climate, and vegetation datasets—from raw source audit through canonical layer generation, spatial/temporal harmonization, and final CSV feature table construction.

Every statement in this document reflects only code, schemas, documentation, and dataset files directly inspected in the repository (`/home/lokman/Desktop/FeildShit-SI-Model`). Operations or datasets that were **not** used or do **not** exist in the workspace (such as Landsat imagery, monthly GPM/SMAP/MODIS series, Sentinel-2 multi-year pixel composites, or a single forced flat CSV merging all spatial scales) are explicitly marked as absent or deferred.

---

## Executive Summary & Provenance Distinction

| Aspect | Verified Repository Reality |
| :--- | :--- |
| **Canonical Coordinate Reference System** | `EPSG:32632` (WGS 84 / UTM Zone 32N), defined in [`config.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/fieldshift_integration/config.py) |
| **Study Period & Seasons** | `STUDY_START_YEAR = 2016` to `STUDY_END_YEAR = 2025`; `SEASON_ORDER = ["Winter", "Spring", "Summer", "Autumn"]` |
| **NoData Sentinel Policy** | `NODATA_VALUE = -9999.0` internally; validated to have `0` leaks into output tables (`VAL_05`) |
| **Landsat Usage** | **Never used.** Repository search (`grep -rni "landsat"`) yields zero matches. Optical vegetation and cropland mapping use **Sentinel-2**, **MODIS**, and **ESA Crop Frequency** instead. |
| **Notebooks** | **Zero** `.ipynb` Jupyter notebooks exist in the repository; all automated processing is implemented in Python scripts (`.py`). |
| **Pipelines Implemented Locally in Python** | **NASA POWER** ([`run_nasa_power_pipeline.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/run_nasa_power_pipeline.py), [`nasa_power_pipeline/`](file:///home/lokman/Desktop/FeildShit-SI-Model/nasa_power_pipeline/)), **Sentinel-2** ([`run_sentinel2_pipeline.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/run_sentinel2_pipeline.py), [`sentinel2_pipeline/`](file:///home/lokman/Desktop/FeildShit-SI-Model/sentinel2_pipeline/)), and **Phase D Integration** ([`run_phaseD_integration.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/run_phaseD_integration.py), [`fieldshift_integration/`](file:///home/lokman/Desktop/FeildShit-SI-Model/fieldshift_integration/)). |
| **Pre-Built Disk Assets (No Local Generator Script)** | **GADM 4.1** commune polygons, **SoilGrids V6**, **GPM**, **SMAP**, **MODIS**, **ESA Crop Frequency**, [`guelma_environmental_spatiotemporal_dataset_2016_2025.csv`](file:///home/lokman/Desktop/FeildShit-SI-Model/data/tables/dataset/guelma_environmental_spatiotemporal_dataset_2016_2025.csv), and [`guelma_integrated_agricultural_database_v1.zip`](file:///home/lokman/Desktop/FeildShit-SI-Model/data/tables/dataset/guelma_integrated_agricultural_database_v1.zip). |
| **Final Integration Architecture** | Rather than forcing four incompatible spatial scales into a single flat CSV, Phase D outputs **5 scale-consistent analytical CSVs** across **4 spatial tiers (`Tier 1..4`)** under [`data/INTEGRATED/features/`](file:///home/lokman/Desktop/FeildShit-SI-Model/data/INTEGRATED/features/). |

---

## 1. Spatial Coordinates

### 1.1 Do all datasets contain geographic or projected coordinates?
No single uniform coordinate representation is used across raw sources; coordinates exist at three distinct spatial representations depending on the source and target table:

1. **Coarse `11 km` Grid Cell Coordinates (`EPSG:32632`):**
   - In the pre-built seasonal environmental package [`guelma_environmental_spatiotemporal_dataset_2016_2025.csv`](file:///home/lokman/Desktop/FeildShit-SI-Model/data/tables/dataset/guelma_environmental_spatiotemporal_dataset_2016_2025.csv), every row represents a **grid cell** in a specific `(Year, Season)`, identified by:
     - `Cell_Row`, `Cell_Col` (grid indices)
     - `X_UTM32N_m`, `Y_UTM32N_m` (projected easting/northing coordinates in `EPSG:32632`)
   - There are **45 unique `11 km` cells** (`7` unique Y coordinates × `9` unique X coordinates):
     - `X_UTM32N_m`: `313500.0` to `401500.0` m
     - `Y_UTM32N_m`: `3987500.0` to `4053500.0` m
   - These coordinates identify individual **11 km grid cells**, **not** commune names directly.

2. **`250 m` Pixel Grid Coordinates (`EPSG:32632`):**
   - In [`landscape_250m_static_features.csv`](file:///home/lokman/Desktop/FeildShit-SI-Model/data/INTEGRATED/features/landscape_250m_static_features.csv), every row represents an individual **`250 m` pixel** on the canonical SoilGrids/MODIS `286 × 367` raster grid in `EPSG:32632`, identified by:
     - `grid_250m_id`, `row_250m`, `col_250m`
     - `x_utm32n_m`, `y_utm32n_m`
   - Of the `59,050` valid pixels in that table, `58,246` carry non-null administrative commune identifiers (`commune_gid_2`, `commune_name`, `commune_num_id`) and `804` pixels have null commune tags.

3. **Administrative Polygon / Wilaya Aggregations (No Pixel Coordinates):**
   - **Commune-level tables** ([`commune_static_soil_and_land_features.csv`](file:///home/lokman/Desktop/FeildShit-SI-Model/data/INTEGRATED/features/commune_static_soil_and_land_features.csv) and [`commune_seasonal_panel_2016_2025.csv`](file:///home/lokman/Desktop/FeildShit-SI-Model/data/INTEGRATED/features/commune_seasonal_panel_2016_2025.csv)) identify regions via GADM 4.1 commune identifiers (`commune_num_id`, `GID_2`, `NAME_2`), covering **34 communes** in Guelma Wilaya (for example, `commune_num_id = 4`, `GID_2 = 'DZA.21.13_1'`, `NAME_2 = 'Bouchekouf'`; `commune_num_id = 10`, `GID_2 = 'DZA.21.19_1'`, `NAME_2 = 'Hammam Debagh'`). They do not store per-pixel `X/Y` or `Lat/Lon` columns.
   - **Wilaya-level tables** ([`wilaya_monthly_panel_2016_2025.csv`](file:///home/lokman/Desktop/FeildShit-SI-Model/data/INTEGRATED/features/wilaya_monthly_panel_2016_2025.csv) and [`wilaya_seasonal_panel_2016_2025.csv`](file:///home/lokman/Desktop/FeildShit-SI-Model/data/INTEGRATED/features/wilaya_seasonal_panel_2016_2025.csv)) contain province-wide values (`spatial_unit` / `spatial_support`) with no `Lat/Lon` or pixel coordinate columns.

4. **Raw NASA POWER Geographic Grid vs. Polygon Extraction:**
   - Raw NASA POWER uses separate `AG` and `RE` grids. In [`nasa_power_pipeline/audit.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/nasa_power_pipeline/audit.py) (alongside root scripts [`extract_nasa_power_guelma_region.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/extract_nasa_power_guelma_region.py), [`build_nasa_power_intersections.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/build_nasa_power_intersections.py), [`build_nasa_power_RE_intersections.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/build_nasa_power_RE_intersections.py), and [`process_nasa_power_spatial.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/process_nasa_power_spatial.py)), `_densified_cell_polygon()` builds cell polygons and intersects them against the Guelma boundary loaded by `load_and_audit_boundary()`.

### 1.2 How is the geographic region assigned to each value?
- **Landscape `250 m` Pixels:** Each pixel is linked to its GADM 4.1 commune (`commune_gid_2`, `commune_name`, `commune_num_id`), with `804` edge pixels remaining unassigned (`NaN`).
- **Commune Tables:** Polygon zonal aggregation sums or averages `250 m` pixels inside each of the 34 GADM 4.1 commune polygons (`_build_commune_zonal_tables()`), while `11 km` GPM/SMAP cells are intersected by polygon overlap area against each commune (`_area_weighted_grid_to_communes()`).
- **Wilaya Tables & Live Field Inference:**
  - Historical Wilaya panels aggregate across the entire Guelma Wilaya boundary (Guelma Wilaya polygon area: `3683.2311 km²`; sum of 34 commune areas: `3683.2308 km²`).
  - At runtime during farmer API inference, [`field_geospatial_processor.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/field_geospatial_processor.py) extracts values directly inside the user-submitted GeoJSON field polygon.

---

## 2. Spatial Matching

### 2.1 Was geographic region matching performed prior to merging datasets?
Yes—in two distinct stages:
1. **Source Extraction Stage (NASA POWER):** Before building Wilaya time series, [`nasa_power_pipeline/audit.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/nasa_power_pipeline/audit.py) intersects each raw NASA POWER cell polygon (`_densified_cell_polygon()`) against the Guelma Wilaya polygon and records areal coverage fractions (`min_coverage_fraction_AG`, `mean_coverage_fraction_AG`, `min_coverage_fraction_RE`, `mean_coverage_fraction_RE`).
2. **Phase D Integration Stage:** In [`fieldshift_integration/spatial_harmonization.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/fieldshift_integration/spatial_harmonization.py), every dataset is first reprojected/aligned to the canonical `EPSG:32632` spatial reference and placed into its appropriate spatial tier before table joins occur.

### 2.2 How were multi-source datasets (GPM, SMAP, MODIS, SoilGrids, Sentinel-2, NASA POWER) verified to belong to the same region, and what about Landsat?
- **Landsat was NOT used.** There are zero Landsat files or code references in the repository.
- **GPM, SMAP, and MODIS:** Already delivered aligned on the `EPSG:32632` regional grid in Guelma (`45` cells at `11 km` for GPM/SMAP in the climate/moisture table and `guelma_environmental_spatiotemporal_dataset_2016_2025.csv`, and `250 m` UTM32N grid for MODIS/SoilGrids). Phase D audits and harmonizes them into commune and `250 m` canonical layers rather than re-downloading raw GPM/SMAP/MODIS swaths.
- **Boundary Consistency Check:** Sum of the 34 GADM 4.1 commune areas equals `3683.2308 km²` against the Wilaya boundary area of `3683.2311 km²`.
- **Guelma `11 km` Overlay Coverage:** When area-weighting `11 km` GPM/SMAP cells onto the 34 communes via `_area_weighted_grid_to_communes()`, each commune row explicitly tracks `coarse_11km_covered_m2` alongside `area_km2`.

### 2.3 Were commune polygons (`Polygon`) or raw coordinates used?
Both were used, depending on the target table:
- **GADM 4.1 Commune Polygons:** Used in [`spatial_harmonization.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/fieldshift_integration/spatial_harmonization.py) for `_build_commune_zonal_tables()` (aggregating `250 m` SoilGrids, MODIS, ESA Crop Frequency, and Sentinel-2 `2024-03`) and `_area_weighted_grid_to_communes()` (transferring `11 km` GPM precipitation and SMAP soil moisture onto the 34 communes).
- **Wilaya Boundary Polygon:** Used by [`nasa_power_pipeline/audit.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/nasa_power_pipeline/audit.py) to clip and area-weight NASA POWER cells.
- **Raster Pixel Coordinates (`250 m` & `11 km`):** Used directly in [`landscape_250m_static_features.csv`](file:///home/lokman/Desktop/FeildShit-SI-Model/data/INTEGRATED/features/landscape_250m_static_features.csv) (`grid_250m_id`, `row_250m`, `col_250m`, `x_utm32n_m`, `y_utm32n_m`) and [`guelma_environmental_spatiotemporal_dataset_2016_2025.csv`](file:///home/lokman/Desktop/FeildShit-SI-Model/data/tables/dataset/guelma_environmental_spatiotemporal_dataset_2016_2025.csv) (`Cell_Row`, `Cell_Col`, `X_UTM32N_m`, `Y_UTM32N_m`).

### 2.4 How were differences in spatial resolution handled?
According to [`spatial_harmonization_specification.md`](file:///home/lokman/Desktop/FeildShit-SI-Model/data/INTEGRATED/docs/spatial_harmonization_specification.md) and [`spatial_harmonization.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/fieldshift_integration/spatial_harmonization.py), Phase D enforces a **4-tier spatial hierarchy** and a strict **downward-only aggregation rule** (coarse macro-climate layers are **never** statistically downscaled or interpolated onto fine `250 m` pixels):

| Spatial Tier | Native / Target Resolution | Datasets & Tables | Key Harmonization Rule |
| :--- | :--- | :--- | :--- |
| **Fine Plot / Cropland Mask** | `10 m` / `20 m` → `250 m` | Sentinel-2 (`2024-03` snapshot), ESA Crop Frequency (`2021–2025`) | ESA Crop Frequency had an origin offset `(964.88 m E, 901.97 m N)` vs. Sentinel-2 `10 m`; aligned to the `10 m` grid with `Resampling.nearest` (`align_crop_frequency_to_s2_10m()`), then downward-averaged to the `250 m` canonical grid with `Resampling.average` (`_downward_aggregate_to_250m()`). |
| **Soil & Landscape Grid** | `250 m` (`286 × 367` UTM32N) | SoilGrids V6 (`V6_MERGED`), MODIS NDVI/EVI seasonal climatologies, aligned Crop Frequency & S2 `2024-03` | Merged onto `grid_250m_id` (`59,050` pixels) in [`landscape_250m_static_features.csv`](file:///home/lokman/Desktop/FeildShit-SI-Model/data/INTEGRATED/features/landscape_250m_static_features.csv). Macro-climate variables (NASA POWER, GPM, SMAP) are deliberately excluded from this table. |
| **Administrative Commune** | 34 GADM 4.1 Communes | Static soil/land/climatology + seasonal `2016–2025` commune panel | Fine `250 m` layers aggregated via zonal statistics (`_build_commune_zonal_tables()`); `11 km` GPM/SMAP transferred via area-weighted polygon intersection (`_area_weighted_grid_to_communes()`); explicit support warnings (`macro_climate_scale_warning`, `gpm_smap_support_tag`, `nasa_power_support_tag`). |
| **Coarse Climate / Wilaya** | `11 km` grid & Wilaya-wide NASA POWER (`AG`/`RE`) | `guelma_environmental_spatiotemporal_dataset_2016_2025.csv`, Wilaya Monthly (`120` rows) & Seasonal (`40` rows) panels | Combined only at matching Wilaya or `11 km` coarse resolution with explicit `spatial_support` / `climate_spatial_support` metadata. |

---

## 3. Temporal Matching

### 3.1 Was temporal matching performed after spatial harmonization, and what are the native cadences?
Yes. Once each source is spatially mapped to Wilaya, Commune, `11 km` grid, or `250 m` static grid, temporal matching aligns records according to [`temporal_harmonization_specification.md`](file:///home/lokman/Desktop/FeildShit-SI-Model/data/INTEGRATED/docs/temporal_harmonization_specification.md):

| Dataset | Native Cadence Available on Disk | Target Temporal Panels |
| :--- | :--- | :--- |
| **NASA POWER** | Daily (`2016–2025`) | Aggregated in [`processing.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/nasa_power_pipeline/processing.py) to **Daily**, **Monthly** (`120` months), **Seasonal** (`40` seasons), and **Annual**. |
| **Sentinel-2** | **Monthly Wilaya statistics** (`2017-01` to `2025-12`, 108 months) + **Single pixel-level GeoTIFF** (`2024-03`) | Joined to **Monthly Wilaya** panel (`2016` = missing) and aggregated to **Seasonal Wilaya** panel via 3-month medians (`s2_*_median_of_months`). `2024-03` used only as a static snapshot. |
| **GPM & SMAP** | **Seasonal & Annual only** (**no monthly GPM/SMAP files exist on disk**) | Seasonal Wilaya, Seasonal Commune (`2016–2025`), and `11 km` grid (`2016–2025`). |
| **MODIS** | **Seasonal & Annual only** (**no 16-day or monthly MODIS files exist on disk**) | Seasonal Wilaya, Seasonal Commune (`2016–2025`), `11 km` grid (`2016–2025`), and seasonal multi-year (`2016–2025`) static means at `250 m`. |
| **SoilGrids V6** | Static (time-invariant) | Static Commune and `250 m` landscape tables only. |
| **ESA Crop Frequency** | Multi-year `2021–2025` aggregate | Static Commune and `250 m` tables; guarded against temporal look-ahead in [`commune_seasonal_panel_2016_2025.csv`](file:///home/lokman/Desktop/FeildShit-SI-Model/data/INTEGRATED/features/commune_seasonal_panel_2016_2025.csv) via `crop_freq_usable_for_year` (`2017–2020` leakage prevention). |

### 3.2 How were differences in temporal resolution and missing dates handled?
- **Canonical Temporal Keys:**
  - Monthly table: `year_month` (`YYYY-MM`, `2016-01` through `2025-12`, joined with `how="left"` on `nasa_power_monthly_canonical.csv`).
  - Seasonal tables: `(season_year, season)` with `SEASON_ORDER = ["Winter", "Spring", "Summer", "Autumn"]`.
  - Meteorological Winter (`DJF`) follows the convention assigning December to `season_year = year + 1` (noted in [`temporal_harmonization_specification.md`](file:///home/lokman/Desktop/FeildShit-SI-Model/data/INTEGRATED/docs/temporal_harmonization_specification.md), where boundary winters `Winter 2016` has `60` days and `Winter 2026` has `31` days).
- **Handling Missing Data & Partial Periods (No Synthetic Imputation):**
  - **Sentinel-2 `2016` Gap:** Sentinel-2 data is absent for all `12` months of `2016`. Left join (`how="left"`) preserves all `120` NASA POWER months and leaves `s2_*` vegetation metrics as `NaN` (with `sentinel2_available` and `s2_is_model_eligible_monthly = False`). Likewise, in [`wilaya_seasonal_panel_2016_2025.csv`](file:///home/lokman/Desktop/FeildShit-SI-Model/data/INTEGRATED/features/wilaya_seasonal_panel_2016_2025.csv), the `4` seasons of `2016` have `NaN` in the 8 seasonal Sentinel-2 columns (`s2_months_included`, `s2_min_month_valid_pct_10m`, `s2_ndvi_median_of_months`, `s2_evi_median_of_months`, `s2_ndmi_median_of_months`, `s2_ndre_median_of_months`, `s2_completeness_status`, `s2_aggregation_basis`).
  - **Partial Sentinel-2 Month (`2017-01`):** Flagged with partial coverage (`1.4173%` valid pixels), reflected in `s2_completeness_status` and `s2_is_model_eligible_monthly`.
  - **Incomplete Winter 2017:** Explicitly tracked in [`wilaya_seasonal_panel_2016_2025.csv`](file:///home/lokman/Desktop/FeildShit-SI-Model/data/INTEGRATED/features/wilaya_seasonal_panel_2016_2025.csv) via `is_winter_2017_incomplete` and `is_complete_season`.
  - **Monthly GPM/SMAP Absence:** Because no monthly GPM or SMAP files exist on disk, they are **not** interpolated from seasonal values into the monthly panel; instead, [`wilaya_monthly_panel_2016_2025.csv`](file:///home/lokman/Desktop/FeildShit-SI-Model/data/INTEGRATED/features/wilaya_monthly_panel_2016_2025.csv) explicitly includes boolean/availability indicator columns `gpm_monthly_available_on_disk` and `smap_monthly_available_on_disk`.
  - **Antecedent Lag NaNs:** Lead/lag shift features leave initial boundary periods as `NaN` rather than backfilling (`prectot_lag1_mm` missing `1`, `prectot_lag2_mm` missing `2`, `prectot_antecedent_3m_sum_mm` missing `3`, `t2m_lag1_mean_c` missing `1`, `rh2m_lag1_mean_pct` missing `1`; seasonal lag-1 columns missing `1` row in the Wilaya seasonal panel and `34` rows—one season across 34 communes—in the commune seasonal panel).

### 3.3 At what temporal level were timestamps unified?
Timestamps were **not** forced to a single daily or monthly cadence where datasets lacked sub-seasonal observations:
- **Monthly (`120` rows):** NASA POWER + Sentinel-2 only (`year_month`).
- **Seasonal (`40` seasons × 1 Wilaya, `40` seasons × 34 Communes, `40` seasons × 45 `11 km` cells):** Common multi-sensor cadence combining NASA POWER, GPM, SMAP, MODIS, and Sentinel-2 (Wilaya only).

---

## 4. Dataset Transformation & Cleaning

Key dataset transformations verified in [`canonical_layers.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/fieldshift_integration/canonical_layers.py), [`spatial_harmonization.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/fieldshift_integration/spatial_harmonization.py), [`feature_engineering.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/fieldshift_integration/feature_engineering.py), and [`processing.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/nasa_power_pipeline/processing.py):

1. **NASA POWER Temporal Pivoting & Aggregation ([`processing.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/nasa_power_pipeline/processing.py)):**
   - Daily cell outputs (`build_daily_cell_dataset()`) and Wilaya averages (`build_daily_guelma_dataset()`) are pivoted wide (`_pivot_daily_wide()`) and rolled up into Monthly (`build_monthly_dataset()`), Seasonal (`build_seasonal_dataset()`), and Annual (`build_annual_dataset()`) canonical tables.
   - Engineered features in [`feature_engineering.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/fieldshift_integration/feature_engineering.py): `diurnal_temp_range_mean_c`, monthly lags (`prectot_lag1_mm`, `prectot_lag2_mm`, `prectot_antecedent_3m_sum_mm`, `t2m_lag1_mean_c`, `rh2m_lag1_mean_pct`), and seasonal lag-1 predictors (`np_prectot_lag1_season_mm`).

2. **SoilGrids Depth-Weighted Averaging & Anomaly Screening ([`config.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/fieldshift_integration/config.py), [`canonical_layers.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/fieldshift_integration/canonical_layers.py), [`guelma_soilgrids_V6_quality_assessment.csv`](file:///home/lokman/Desktop/FeildShit-SI-Model/data/SoilGrids/guelma_soilgrids_V6_quality_assessment.csv)):**
   - Standard SoilGrids depth intervals are aggregated using thickness weights (`SOIL_DEPTH_THICKNESS_CM`: `0-5cm: 5.0`, `5-15cm: 10.0`, `15-30cm: 15.0`, `30-60cm: 30.0`, `60-100cm: 40.0`, `100-200cm: 100.0`) inside `_weighted_depth_mean()` to derive:
     - Topsoil (`0–30 cm`): `clay_0_30cm`, `sand_0_30cm`, `silt_0_30cm`, `ph_0_30cm`, `soc_0_30cm`, `cec_0_30cm`
     - Subsoil (`30–100 cm`): `clay_30_100cm`, `sand_30_100cm` *(commune static table)*, `silt_30_100cm` *(commune static table)*, `ph_30_100cm`, `soc_30_100cm`, `cec_30_100cm`
   - Texture classification: `usda_texture_0_5cm` mapped to human-readable `usda_texture_0_5cm_label` via `USDA_TEXTURE_NAMES`.
   - **Critical Audit Corrections on Raw SoilGrids:**
     - Raw `ESRI:54009` raster had **0 finite pixels** and was bypassed in favor of `V6_MERGED` UTM32N (`EPSG:32632`).
     - SoilGrids nitrogen exhibits an `N > SOC` anomaly across depth (documented in [`guelma_soilgrids_V6_quality_assessment.csv`](file:///home/lokman/Desktop/FeildShit-SI-Model/data/SoilGrids/guelma_soilgrids_V6_quality_assessment.csv): `1.99%` of pixels at `0-5cm`, increasing to `92.84%` at `100-200cm`). Consequently, soil nitrogen is isolated in `soil_nitrogen_0_30cm_unvalidated` and flagged via `nitrogen_scaling_flag` (`UNVALIDATED_TRACEABILITY_ONLY`).
   - **Urban Sealing Mask:** Sealed urban pixels without soil coverage are masked rather than filled with `-9999.0` or synthetic values: across 33 rural communes the minimum valid soil fraction (`soil_valid_fraction`) is `0.9568`, while urban Guelma commune has `0.7518` (`177` of `713` sealed urban pixels masked).

3. **Sentinel-2 Spatial & Temporal Safeguards ([`sentinel2_pipeline/phase2_gee_client.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/sentinel2_pipeline/phase2_gee_client.py), [`data/SENTINEL2/README.md`](file:///home/lokman/Desktop/FeildShit-SI-Model/data/SENTINEL2/README.md), [`cross_dataset_integration_specification.md`](file:///home/lokman/Desktop/FeildShit-SI-Model/data/SENTINEL2/processed/metadata/cross_dataset_integration_specification.md)):**
   - Monthly Wilaya outputs provide mean/median/stdDev/percentiles (`p5`, `p95`) and IQR spans (`s2_ndvi_iqr_p95_p5`, `s2_evi_iqr_p95_p5`) for NDVI and EVI, plus NDMI and NDRE (`mean`, `median`), along with data quality diagnostics (`s2_image_count`, `s2_cloud_prob_matched_images`, `s2_NDVI_valid_pixels`, `s2_NDVI_valid_pct`, `s2_NDMI_valid_pct`, `s2_mean_valid_obs_per_px_10m`, `s2_mean_valid_obs_per_px_20m`, `s2_EVI_excluded_composite_pixels`, `s2_evi_obs_excluded_total_10m`, `s2_scl2_share_pct`).
   - **Deferred Pixel Composites:** Multi-year Sentinel-2 pixel-median seasonal/annual GEE GeoTIFF exports were **deferred** under `restricted mode` (`sentinel2_pixel_composite_deferred`), so seasonal Sentinel-2 series in [`wilaya_seasonal_panel_2016_2025.csv`](file:///home/lokman/Desktop/FeildShit-SI-Model/data/INTEGRATED/features/wilaya_seasonal_panel_2016_2025.csv) represent monthly Wilaya medians (`s2_ndvi_median_of_months`, etc.), not pixel-level composites.
   - **Single Pixel GeoTIFF (`2024-03`):** The sole pixel-level Sentinel-2 GeoTIFF on disk (`2024-03`) is explicitly marked with `s2_snapshot_note` / `s2_snapshot_temporal_validity`, and `contemporaneous_vi_leakage_risk` is surfaced in the monthly panel to warn downstream models against target leakage.

4. **ESA Crop Frequency Realignment & Leakage Control ([`spatial_harmonization.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/fieldshift_integration/spatial_harmonization.py)):**
   - Raw `Crop Frequency` raster exhibited a spatial origin shift of `(964.88 m E, 901.97 m N)` relative to Sentinel-2 `10 m`. `align_crop_frequency_to_s2_10m()` snaps it onto the canonical `10 m` grid using `Resampling.nearest`.
   - `_downward_aggregate_to_250m()` aggregates the aligned `10 m` crop frequency onto the `250 m` grid using `Resampling.average` (`crop_freq_2021_2025_mean_250m`) and computes binary cropland indicator `is_cropland_ge_05_2021_2025` (as well as commune share `crop_share_ge_05_2021_2025_pct`).
   - Look-ahead validity across `2016–2025` is flagged in `crop_freq_usable_for_year` (blocking `2021–2025` look-ahead leakage into `2017–2020` rows).

---

## 5. Individual Dataset Processing Summary

The complete data landscape audited in [`data_inventory.csv`](file:///home/lokman/Desktop/FeildShit-SI-Model/data/INTEGRATED/metadata/data_inventory.csv) spans **27 inventoried sources** across raw and pre-processed layers. The table below summarizes how each dataset family enters Phase D:

| Dataset Family | Raw Origin / Pipeline | Spatial Resolution / Support | Temporal Extent on Disk | Special Handling / Caveats |
| :--- | :--- | :--- | :--- | :--- |
| **GADM 4.1 Boundaries** | Pre-built disk shapefile/vector (`34` communes) | `34` Commune Polygons + Wilaya (`3683.2311 km²`) | Static | Sum of 34 communes = `3683.2308 km²`; anchors all zonal aggregations and NASA POWER intersections. |
| **NASA POWER (`AG` & `RE`)** | Local Python pipeline ([`nasa_power_pipeline/`](file:///home/lokman/Desktop/FeildShit-SI-Model/nasa_power_pipeline/)) | Raw grid cells → Wilaya area-weighted | Daily (`2016–2025`) → Monthly, Seasonal, Annual | Separate `AG` and `RE` coverage fractions tracked (`min_coverage_fraction_AG`, `mean_coverage_fraction_AG`, `min_coverage_fraction_RE`, `mean_coverage_fraction_RE`); no `250 m` downscaling. |
| **Sentinel-2** | Local GEE client + Python pipeline ([`sentinel2_pipeline/`](file:///home/lokman/Desktop/FeildShit-SI-Model/sentinel2_pipeline/)) | Wilaya summary stats (`10 m` / `20 m` native) + `2024-03` pixel GeoTIFF (`→ 250 m`) | Monthly (`2017–2025`; `2016` missing) + `2024-03` snapshot | Pixel-median seasonal/annual GEE exports deferred (`restricted mode`); `2017-01` partial (`1.4173%`). |
| **SoilGrids V6** | Pre-built `V6_MERGED` GeoTIFFs in UTM32N | `250 m` (`286 × 367` grid, `59,050` pixels) | Static | `ESRI:54009` file rejected (0 finite px); weighted means over `0–30 cm` & `30–100 cm`; urban pixels masked; `N > SOC` anomaly isolated. |
| **GPM (Rainfall)** | Pre-built seasonal/annual raster & table assets | `11 km` native grid (`45` cells) → Commune area-weighted | Seasonal & Annual (`2016–2025`) | **No monthly data on disk.** Explicit lag-1 and coarse support metadata added. |
| **SMAP (Soil Moisture)** | Pre-built seasonal/annual raster & table assets | `11 km` native grid (`45` cells) → Commune area-weighted | Seasonal & Annual (`2016–2025`) | Surface & Rootzone SM (`m3m3`). **No monthly data on disk.** |
| **MODIS (NDVI / EVI)** | Pre-built `250 m` & `11 km` seasonal/climatology assets | `250 m` (`59,050` px) → Commune & Wilaya | Seasonal & Annual (`2016–2025`) | **No 16-day or monthly data on disk.** Tracks `modis_valid_obs_mean`. |
| **ESA Crop Frequency** | Pre-built raster asset | `10 m` raw → `250 m` & Commune | `2021–2025` composite frequency | Origin shift `(964.88 m E, 901.97 m N)` corrected (`Resampling.nearest`), then averaged to `250 m`; temporal look-ahead flagged via `crop_freq_usable_for_year`. |
| **Landsat** | **Not used** | N/A | N/A | Absent from entire codebase (`NO_LANDSAT_FOUND`). |

---

## 6. Final Integration Pipeline (Phase D)

The automated integration pipeline is executed via [`run_phaseD_integration.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/run_phaseD_integration.py) in a deterministic sequence across three modules:

1. **Canonical Layer Construction ([`canonical_layers.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/fieldshift_integration/canonical_layers.py)):**
   - `build_canonical_layers()` reads verified raw/pre-processed assets and writes **6 canonical subfolders** under [`data/INTEGRATED/canonical/`](file:///home/lokman/Desktop/FeildShit-SI-Model/data/INTEGRATED/canonical/), performing depth-weighted soil aggregation (`_weighted_depth_mean()`) and canonical schema normalization.
2. **Spatial Harmonization ([`spatial_harmonization.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/fieldshift_integration/spatial_harmonization.py)):**
   - `run_spatial_harmonization()` aligns ESA Crop Frequency to Sentinel-2 `10 m` (`align_crop_frequency_to_s2_10m()`), downward-aggregates `10 m` layers to `250 m` (`_downward_aggregate_to_250m()`), builds commune zonal tables from `250 m` pixels (`_build_commune_zonal_tables()`), and transfers `11 km` GPM/SMAP grids to communes via area-weighted overlay (`_area_weighted_grid_to_communes()`).
3. **Feature Engineering & CSV Emission ([`feature_engineering.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/fieldshift_integration/feature_engineering.py)):**
   - `build_feature_tables()` executes clean tabular joins per spatial tier, computes temporal lags, antecedent precipitation, diurnal temperature range, IQR spans, and scale/leakage/availability flags, and emits the **5 final CSV feature tables** in [`data/INTEGRATED/features/`](file:///home/lokman/Desktop/FeildShit-SI-Model/data/INTEGRATED/features/).
4. **Automated Validation Suite (`validation_suite.py` & [`phaseD_integration_report.md`](file:///home/lokman/Desktop/FeildShit-SI-Model/data/INTEGRATED/docs/phaseD_integration_report.md)):**
   - Runs checks `VAL_01..VAL_12`, achieving **`11 PASS | 1 CHECK | 0 FAIL`**:
     - `0` duplicate primary keys (`VAL_04`).
     - `0` residual `-9999.0` NoData sentinel leaks (`VAL_05`).
     - Exact commune-to-Wilaya geometric area reconciliation (`3683.2308 km²` vs. `3683.2311 km²`).

*(Note: During live web/API predictions, [`field_geospatial_processor.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/field_geospatial_processor.py) and [`field_profile_builder.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/field_profile_builder.py) extract spatial statistics for user-submitted polygons dynamically from the harmonized geospatial sources without modifying the historical Phase D tables.)*

---

## 7. Final CSVs: Shapes, Join Keys, Column Lists & Missingness

There is **no single monolithic flat CSV** forcing `10 m`, `250 m`, `11 km`, and Wilaya tables into one file. Instead, the workspace contains **(A) two pre-built raw/packaged datasets** and **(B) the 5 final scale-consistent Phase D CSVs**.

### 7.1 Overview Comparison Table

| Dataset / Final CSV | Spatial Unit | Temporal Extent | Exact Shape `(rows, cols)` | Join Type & Key(s) | Missing Value Summary |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **[`guelma_environmental_spatiotemporal_dataset_2016_2025.csv`](file:///home/lokman/Desktop/FeildShit-SI-Model/data/tables/dataset/guelma_environmental_spatiotemporal_dataset_2016_2025.csv)** *(pre-built; SHA-256 identical copy in `data/seasonal/...`)* | `45` cells (`11 km`, UTM32N) | `40` seasons (`2016–2025`) | `(1800, 12)` | Cell `(Cell_Row, Cell_Col)` × `(Year, Season)` | **0 missing** across all 12 columns |
| **[`wilaya_monthly_panel_2016_2025.csv`](file:///home/lokman/Desktop/FeildShit-SI-Model/data/INTEGRATED/features/wilaya_monthly_panel_2016_2025.csv)** | Guelma Wilaya | `120` months (`2016-01..2025-12`) | `(120, 58)` | `how="left"` on `year_month` (`nasa_power_monthly_canonical.csv` + `sentinel2_monthly_wilaya_canonical.csv`) | `12` rows missing in `s2_*` (`2016`); `1–3` rows missing in lag/antecedent cols |
| **[`wilaya_seasonal_panel_2016_2025.csv`](file:///home/lokman/Desktop/FeildShit-SI-Model/data/INTEGRATED/features/wilaya_seasonal_panel_2016_2025.csv)** | Guelma Wilaya | `40` seasons (`Winter 2016..Autumn 2025`) | `(40, 41)` | `how="left"` on `["season_year", "season"]` | `4` missing in `s2_*` cols (`2016`); `1` missing in each `lag1` col |
| **[`commune_static_soil_and_land_features.csv`](file:///home/lokman/Desktop/FeildShit-SI-Model/data/INTEGRATED/features/commune_static_soil_and_land_features.csv)** | `34` GADM Communes | Static + Multi-year means | `(34, 37)` | Join on `commune_num_id` | **0 missing** across all 37 columns |
| **[`commune_seasonal_panel_2016_2025.csv`](file:///home/lokman/Desktop/FeildShit-SI-Model/data/INTEGRATED/features/commune_seasonal_panel_2016_2025.csv)** | `34` GADM Communes | `40` seasons (`2016–2025`) | `(1360, 28)` | Inner join on `["commune_num_id", "GID_2", "NAME_2", "season_year", "season"]` | `34` missing in each of the 3 `lag1` cols (`1` season × `34` communes) |
| **[`landscape_250m_static_features.csv`](file:///home/lokman/Desktop/FeildShit-SI-Model/data/INTEGRATED/features/landscape_250m_static_features.csv)** | `59,050` pixels (`250 m` grid) | Static + Multi-year means | `(59050, 39)` | Inner join on `grid_250m_id` | `commune_*`: `804`; `soc_*`: `100`; `crop_freq_*`: `1`; `s2_2024_03_ndmi/ndre_250m`: `2` |

---

### 7.2 Pre-Built Archive & `11 km` Environmental Table

#### A. `guelma_environmental_spatiotemporal_dataset_2016_2025.csv`
- **File Links:** [`data/tables/dataset/guelma_environmental_spatiotemporal_dataset_2016_2025.csv`](file:///home/lokman/Desktop/FeildShit-SI-Model/data/tables/dataset/guelma_environmental_spatiotemporal_dataset_2016_2025.csv) (verified byte-for-byte identical via SHA-256 `957dea3b23db755819610ed8aa7f13845e94aefb6b7417f3f9805ed21f559f24` to [`data/seasonal/guelma_environmental_seasonal_aligned_2016_2025_package/guelma_environmental_spatiotemporal_dataset_2016_2025.csv`](file:///home/lokman/Desktop/FeildShit-SI-Model/data/seasonal/guelma_environmental_seasonal_aligned_2016_2025_package/guelma_environmental_spatiotemporal_dataset_2016_2025.csv)).
- **Shape:** `(1800, 12)` (`45` cells × `40` seasons).
- **Columns (12):**
  `Year`, `Season`, `Cell_Row`, `Cell_Col`, `X_UTM32N_m`, `Y_UTM32N_m`, `Rainfall_mm`, `Surface_SM_m3m3`, `Rootzone_SM_m3m3`, `NDVI`, `EVI`, `MODIS_valid_obs_mean`
- **Missing Values:** None (`{}`).

#### B. `guelma_integrated_agricultural_database_v1.zip`
- **File Link:** [`data/tables/dataset/guelma_integrated_agricultural_database_v1.zip`](file:///home/lokman/Desktop/FeildShit-SI-Model/data/tables/dataset/guelma_integrated_agricultural_database_v1.zip)
- **Packaged Contents (`unzip -l`):** Three separate tables keeping their respective spatial resolutions intact:
  1. `guelma_soil_static_250m.csv`: `58,950` rows
  2. `guelma_vegetation_seasonal_250m_2016_2025.csv`: `2,358,000` rows
  3. `guelma_climate_moisture_seasonal_native_grid_2016_2025.csv`: `1,800` rows

---

### 7.3 Phase D Final Integrated CSVs (`data/INTEGRATED/features/`)

#### 1. [`wilaya_monthly_panel_2016_2025.csv`](file:///home/lokman/Desktop/FeildShit-SI-Model/data/INTEGRATED/features/wilaya_monthly_panel_2016_2025.csv)
- **Shape:** `(120, 58)`
- **Join Specification:** `how="left"` on `year_month` combining `nasa_power_monthly_canonical.csv` + `sentinel2_monthly_wilaya_canonical.csv`
- **Columns (58):**
  `year`, `month`, `year_month`, `T2M_mean_C`, `T2M_MAX_mean_C`, `T2M_MIN_mean_C`, `PRECTOTCORR_sum_mm`, `RH2M_mean_pct`, `ALLSKY_SFC_SW_DWN_mean_kwh_m2_day`, `ALLSKY_SFC_SW_DWN_sum_kwh_m2`, `valid_days_AG`, `valid_days_RE`, `min_coverage_fraction_AG`, `mean_coverage_fraction_AG`, `min_coverage_fraction_RE`, `mean_coverage_fraction_RE`, `expected_days`, `spatial_support`, `s2_image_count`, `s2_cloud_prob_matched_images`, `s2_NDVI_mean`, `s2_NDVI_median`, `s2_NDVI_stdDev`, `s2_NDVI_p5`, `s2_NDVI_p95`, `s2_EVI_mean`, `s2_EVI_median`, `s2_EVI_stdDev`, `s2_EVI_p5`, `s2_EVI_p95`, `s2_NDMI_mean`, `s2_NDMI_median`, `s2_NDRE_mean`, `s2_NDRE_median`, `s2_NDVI_valid_pixels`, `s2_NDVI_valid_pct`, `s2_NDMI_valid_pct`, `s2_mean_valid_obs_per_px_10m`, `s2_mean_valid_obs_per_px_20m`, `s2_EVI_excluded_composite_pixels`, `s2_evi_obs_excluded_total_10m`, `s2_scl2_share_pct`, `s2_completeness_status`, `s2_is_model_eligible_monthly`, `s2_ndvi_iqr_p95_p5`, `s2_evi_iqr_p95_p5`, `diurnal_temp_range_mean_c`, `prectot_lag1_mm`, `prectot_lag2_mm`, `prectot_antecedent_3m_sum_mm`, `t2m_lag1_mean_c`, `rh2m_lag1_mean_pct`, `sentinel2_available`, `gpm_monthly_available_on_disk`, `smap_monthly_available_on_disk`, `spatial_unit`, `climate_spatial_support`, `contemporaneous_vi_leakage_risk`
- **Missing Values:**
  - `s2_*` Sentinel-2 columns: `12` rows each (all 12 months of `2016`; `s2_is_model_eligible_monthly` is filled `False` rather than null)
  - `prectot_lag1_mm`: `1`
  - `prectot_lag2_mm`: `2`
  - `prectot_antecedent_3m_sum_mm`: `3`
  - `t2m_lag1_mean_c`: `1`
  - `rh2m_lag1_mean_pct`: `1`

#### 2. [`wilaya_seasonal_panel_2016_2025.csv`](file:///home/lokman/Desktop/FeildShit-SI-Model/data/INTEGRATED/features/wilaya_seasonal_panel_2016_2025.csv)
- **Shape:** `(40, 41)`
- **Join Specification:** `how="left"` on `["season_year", "season"]` combining NASA POWER + GPM + SMAP + MODIS + Sentinel-2
- **Columns (41):**
  `season_year`, `season`, `T2M_mean_C`, `T2M_MAX_mean_C`, `T2M_MIN_mean_C`, `PRECTOTCORR_sum_mm`, `RH2M_mean_pct`, `ALLSKY_SFC_SW_DWN_mean_kwh_m2_day`, `valid_days_AG`, `valid_days_RE`, `min_coverage_fraction_AG`, `mean_coverage_fraction_AG`, `min_coverage_fraction_RE`, `mean_coverage_fraction_RE`, `expected_days`, `is_complete_season`, `spatial_support`, `gpm_precip_cell_mean_mm`, `gpm_precip_cell_std_mm`, `smap_sm_surface_m3m3`, `smap_sm_rootzone_m3m3`, `modis_evi_mean`, `modis_ndvi_mean`, `modis_valid_obs_mean`, `modis_ndvi_median`, `modis_evi_median`, `spatial_resolution_m`, `s2_months_included`, `s2_min_month_valid_pct_10m`, `s2_ndvi_median_of_months`, `s2_evi_median_of_months`, `s2_ndmi_median_of_months`, `s2_ndre_median_of_months`, `s2_completeness_status`, `s2_is_complete_season`, `s2_aggregation_basis`, `np_prectot_lag1_season_mm`, `gpm_precip_lag1_season_mm`, `smap_rootzone_lag1_season_m3m3`, `sentinel2_pixel_composite_deferred`, `is_winter_2017_incomplete`
- **Missing Values:**
  - `s2_months_included`: `4`
  - `s2_min_month_valid_pct_10m`: `4`
  - `s2_ndvi_median_of_months`: `4`
  - `s2_evi_median_of_months`: `4`
  - `s2_ndmi_median_of_months`: `4`
  - `s2_ndre_median_of_months`: `4`
  - `s2_completeness_status`: `4`
  - `s2_aggregation_basis`: `4`
  - `np_prectot_lag1_season_mm`: `1`
  - `gpm_precip_lag1_season_mm`: `1`
  - `smap_rootzone_lag1_season_m3m3`: `1`

#### 3. [`commune_static_soil_and_land_features.csv`](file:///home/lokman/Desktop/FeildShit-SI-Model/data/INTEGRATED/features/commune_static_soil_and_land_features.csv)
- **Shape:** `(34, 37)`
- **Join Specification:** Join key `commune_num_id` across 34 GADM 4.1 communes
- **Columns (37):**
  `commune_num_id`, `GID_2`, `NAME_2`, `area_km2`, `soil_valid_250m_px`, `clay_0_30cm`, `sand_0_30cm`, `silt_0_30cm`, `ph_0_30cm`, `soc_0_30cm`, `cec_0_30cm`, `soil_nitrogen_0_30cm_unvalidated`, `clay_30_100cm`, `sand_30_100cm`, `silt_30_100cm`, `ph_30_100cm`, `soc_30_100cm`, `cec_30_100cm`, `commune_total_250m_px`, `soil_valid_fraction`, `crop_freq_2021_2025_mean`, `crop_share_ge_05_2021_2025_pct`, `s2_2024_03_ndvi_median`, `s2_2024_03_evi_median`, `s2_2024_03_ndmi_median`, `s2_2024_03_ndre_median`, `crop_freq_temporal_validity`, `s2_snapshot_note`, `modis_ndvi_spring_2016_2025_mean`, `modis_evi_spring_2016_2025_mean`, `gpm_spring_precip_2016_2025_mean_mm`, `smap_spring_rootzone_2016_2025_mean`, `np_spring_t2m_2016_2025_mean_c`, `gpm_annual_2017_2025_mean_mm`, `spatial_unit`, `macro_climate_scale_warning`, `nitrogen_scaling_flag`
- **Missing Values:** None (`{}`).

#### 4. [`commune_seasonal_panel_2016_2025.csv`](file:///home/lokman/Desktop/FeildShit-SI-Model/data/INTEGRATED/features/commune_seasonal_panel_2016_2025.csv)
- **Shape:** `(1360, 28)` (`34` communes × `40` seasons)
- **Join Specification:** Inner join on `["commune_num_id", "GID_2", "NAME_2", "season_year", "season"]`
- **Columns (28):**
  `commune_num_id`, `season_year`, `season`, `modis_ndvi_mean`, `modis_evi_mean`, `modis_valid_obs_mean`, `modis_valid_250m_px`, `GID_2`, `NAME_2`, `area_km2`, `coarse_11km_covered_m2`, `gpm_precip_mm`, `smap_sm_surface_m3m3`, `smap_sm_rootzone_m3m3`, `np_t2m_mean_c`, `np_t2m_max_c`, `np_t2m_min_c`, `np_rh2m_mean_pct`, `np_prectot_sum_mm`, `np_sw_dwn_mean_kwh_m2_day`, `is_complete_season`, `fine_veg_support_m`, `gpm_smap_support_tag`, `nasa_power_support_tag`, `gpm_precip_lag1_season_mm`, `smap_rootzone_lag1_season_m3m3`, `np_prectot_lag1_season_mm`, `crop_freq_usable_for_year`
- **Missing Values:**
  - `gpm_precip_lag1_season_mm`: `34`
  - `smap_rootzone_lag1_season_m3m3`: `34`
  - `np_prectot_lag1_season_mm`: `34`

#### 5. [`landscape_250m_static_features.csv`](file:///home/lokman/Desktop/FeildShit-SI-Model/data/INTEGRATED/features/landscape_250m_static_features.csv)
- **Shape:** `(59050, 39)` (`286 × 367` UTM32N grid)
- **Join Specification:** Inner join on `grid_250m_id`
- **Columns (39):**
  `grid_250m_id`, `row_250m`, `col_250m`, `x_utm32n_m`, `y_utm32n_m`, `commune_gid_2`, `commune_name`, `commune_num_id`, `clay_0_30cm`, `sand_0_30cm`, `silt_0_30cm`, `ph_0_30cm`, `soc_0_30cm`, `cec_0_30cm`, `clay_30_100cm`, `ph_30_100cm`, `soc_30_100cm`, `cec_30_100cm`, `soil_nitrogen_0_30cm_unvalidated`, `usda_texture_0_5cm`, `usda_texture_0_5cm_label`, `nitrogen_scaling_flag`, `crop_freq_2021_2025_mean_250m`, `is_cropland_ge_05_2021_2025`, `s2_2024_03_ndvi_250m`, `s2_2024_03_evi_250m`, `s2_2024_03_ndmi_250m`, `s2_2024_03_ndre_250m`, `modis_ndvi_winter_2016_2025_mean`, `modis_evi_winter_2016_2025_mean`, `modis_ndvi_spring_2016_2025_mean`, `modis_evi_spring_2016_2025_mean`, `modis_ndvi_summer_2016_2025_mean`, `modis_evi_summer_2016_2025_mean`, `modis_ndvi_autumn_2016_2025_mean`, `modis_evi_autumn_2016_2025_mean`, `spatial_unit`, `crop_freq_temporal_validity`, `s2_snapshot_temporal_validity`
- **Missing Values:**
  - `commune_gid_2`: `804`
  - `commune_name`: `804`
  - `commune_num_id`: `804`
  - `soc_0_30cm`: `100`
  - `soc_30_100cm`: `100`
  - `crop_freq_2021_2025_mean_250m`: `1`
  - `s2_2024_03_ndmi_250m`: `2`
  - `s2_2024_03_ndre_250m`: `2`
