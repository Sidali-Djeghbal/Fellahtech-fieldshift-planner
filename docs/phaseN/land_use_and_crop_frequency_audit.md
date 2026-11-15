# Phase N — Land-Use Verification & ESA Crop Frequency Root-Cause Audit

## 1. Root-Cause Diagnosis of `ANAL_248892E4C4DFE796` (`crop_frequency = 0.0008`)

Prior to Phase N, `frontend/app.js` defined `PRESETS.belkheir` with polygon bounds `[[[7.435, 36.443], [7.441, 36.443], [7.441, 36.447], [7.435, 36.447], [7.435, 36.443]]]` despite labeling it *"Belkheir / Boumahra Alluvial Parcel"*. Spatial overlay and raster extraction confirm:

- **Administrative Location:** `100.0%` within **Guelma** commune (`gid_2 = DZA.21.18_1`, `23.8693 ha`), on the urbanized/peri-urban south-east fringe of Guelma city—NOT Belkheir rural farmland.
- **ESA/Annual Crop Frequency (`guelma_crop_frequency_2021_2025_aligned_s2_10m.tif`):** `2487` valid `10 m` pixels (`100.0%` coverage), area-weighted mean **`0.0008`** (`p25 = 0.0`, `p50 = 0.0`, `p75 = 0.0`, `max = 0.0622`, `cropland_share_ge_05_pct = 0.0%`). Zero pixels show recurring annual cropland.
- **SoilGrids 250 m Urban Mask (`guelma_soilgrids_V6_complete_package.zip`):** Only **`1`** valid `250 m` pixel overlaps the `23.87 ha` polygon (`polygon_coverage_pct = 3.01%` for `clay_0_30cm`, `0.51%` for `soc`); the remainder is urban/built-up masked.
- **Vegetation Signature:** `s2_2024_03_ndvi_10m = 0.203` (`p50 = 0.145`), `modis_ndvi_spring_2016_2025_mean = 0.2245`—characteristic of built-up/bare peri-urban surfaces rather than active winter cereal/legume canopies.

By contrast, genuine rural Belkheir alluvial farmland (`[7.48..7.486, 36.47..36.474]`, `23.8605 ha`, `91.014%` Belkheir) yields **`crop_frequency = 0.9253`** (`cropland_share_ge_05_pct = 96.72%` across `2487` px), `soilgrids_clay_coverage_pct = 100.0%` (`9` valid px), and `s2_2024_03_ndvi_10m = 0.5386`.

No bug existed in the `rasterio` aggregation routine; the v1.0.0 defect was **accepting unverified/masked non-cropland coordinates without a multi-signal land-use classification gate**.

---

## 2. Multi-Signal Classification Model (`src/agronomic/land_use_assessment.py`)

Phase N introduces `assess_land_use(field_profile, *, thresholds=DEFAULT_LAND_USE_THRESHOLDS)` synthesizing five geospatial and farmer signals:
1. `crop_frequency_2021_2025` (`value`, `cropland_share_ge_05_pct`, `valid_pixel_count`, `quality_status`)
2. `soilgrids_v6.clay_0_30cm` (`polygon_coverage_pct`, `valid_pixel_count`, `quality_status`)
3. Spring/winter greenness cross-check (`s2_2024_03_ndvi_10m`, `modis_ndvi_spring_2016_2025_mean`, `modis_ndvi_winter_2016_2025_mean`)
4. Wilaya overlap percentage (`wilaya_overlap_pct`) and polygon vs raster pixel scale (`soilgrids_pixel_to_polygon_area_ratio`)
5. Farmer-declared non-fallow cropping history (`crop_history`)

### Output Taxonomy

| Status | Trigger Criteria (Default `LandUseThresholds`) | Downstream Effect |
|---|---|---|
| `LAND_USE_SUPPORTED` | `cf >= 0.40` or `share >= 40%`, and SoilGrids interior coverage adequate (`>= 25%` or edge-explained) | Normal agronomic evaluation; `is_provisional = False`. |
| `LAND_USE_LOW_EVIDENCE` | `0.05 <= cf < 0.40` without SoilGrids+history contradiction (e.g. mosaic, intermittent fallow, tree-mixed) | `requires_local_verification = True`; allowed for conditional ranking with explicit local arable confirmation warning. |
| `LAND_USE_UNVERIFIED` | `cf < 0.05` and `share < 5%` with no conflicting high NDVI or claimed recent crops | `is_provisional = True`; forces `EXPLORATORY_ONLY`, `endorsed_recommendation_id = None`, `provisional = True` on all candidate strategies. |
| `LAND_USE_CONFLICTING_EVIDENCE` | Near-zero CF (`< 0.05`) paired with claimed cropping OR high green NDVI (`>= 0.40`); OR active cropping/high CF paired with severe SoilGrids urban masking (`< 25%` inside `>= 99%` Wilaya overlap) | `is_provisional = True`; forces `EXPLORATORY_ONLY`, `endorsed_recommendation_id = None`, diagnostic `CON_10_LAND_USE` (`PROVISIONAL_FLAG`). |
| `LAND_USE_DATA_UNAVAILABLE` | `crop_frequency_2021_2025` missing / temporal-guard excluded (`TEMPORAL_GUARD_EXCLUDED`, etc.) | `requires_local_verification = True` (never silently assumes irrigated cropland); respects causal backtests with masked 2021–2025 rasters. |

---

## 3. UI Preset Correction (`frontend/app.js` & `frontend/index.html`)

- **Fixed `PRESETS.belkheir`:** Updated coordinates to verified Belkheir alluvial farmland `[[[7.48, 36.47], [7.486, 36.47], [7.486, 36.474], [7.48, 36.474], [7.48, 36.47]]]` (`LAND_USE_SUPPORTED`, `crop_frequency = 0.9253`).
- **Added `PRESETS.periurban` (`Sample: Peri-Urban Check`):** Preserved `[7.435..7.441, 36.443..36.447]` transparently as an explicit boundary-check demo illustrating `EXPLORATORY_ONLY` / `INSUFFICIENT` critical adequacy gating.
