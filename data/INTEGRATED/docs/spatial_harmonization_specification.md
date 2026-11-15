# Spatial Harmonization Specification — Field Shift (Phase D)

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
   - Raw `guelma_crop_frequency_2021_2025_utm32n.tif` had origin `[314525.12, 4060721.97]` (`7341 × 9268`), shifted by **`964.876 m` East / `901.969 m` North** relative to Sentinel-2 `10 m` (`[315490.0, 4059820.0]`, `7131 × 9146`).
   - **Action Executed:** Reprojected cleanly via `Resampling.nearest` onto the exact Sentinel-2 `10 m` transform (`guelma_crop_frequency_2021_2025_aligned_s2_10m.tif`) before any `250 m` or Commune aggregation, keeping original files untouched.
2. **Defective Raw SoilGrids File Bypassed:**
   - Verified empirically that `data/SoilGrids/drive-download-20261114T174721Z-1-001/guelma_soilgrids_42bands_250m.tif` (`ESRI:54009`) contains **`0` finite pixels across all `42` bands**.
   - **Action Executed:** Extracted SoilGrids strictly from the verified UTM32N archive `guelma_soilgrids_42bands_250m_V6_MERGED.tif` inside `guelma_soilgrids_V6_complete_package.zip` (`59,041–59,050` valid pixels), matching the exact `(315250.0, 4060000.0)` `250 m` grid of `MODIS MOD13Q1` and `guelma_USDA_texture_classes_6depths_250m.tif`.
3. **Pre-Phase-B March 2024 Sentinel-2 Zero-Exterior Masking:**
   - Because Phase A `2024-03` GeoTIFFs retain `0` outside Guelma, all `250 m` & Commune reductions mask exterior pixels using `geometry_mask` / `rasterize` (`all_touched=False`) before aggregation so exterior zeros never contaminate averages.
