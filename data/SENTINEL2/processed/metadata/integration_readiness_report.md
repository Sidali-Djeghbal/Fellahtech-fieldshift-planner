# Field Shift Sentinel-2 Integration-Readiness Report

**Study Area:** Guelma Wilaya, Algeria (`3683.2311 km²`, `EPSG:32632`)  
**GEE Project:** `spry-framework-514800-j2` (`REGISTERED_NOT_COMMERCIALLY`)  
**Updated UTC:** `2026-11-15T02:06:20.298488+00:00`

---

## 1. Delivered vs. Pending Sentinel-2 Products

| Product | Status | Location / Notes |
|---|---|---|
| **Complete Monthly Statistical Time Series (`2017-01`..`2025-12`, `108` months)** | **COMPLETED & MD5 VERIFIED** | [sentinel2_monthly_indices_2017_2025.csv](file:///home/lokman/Desktop/FeildShit-SI-Model/data/SENTINEL2/processed/monthly/sentinel2_monthly_indices_2017_2025.csv) (`107` `COMPLETE` `>=95.9%`, `1` `PARTIAL_LOW_COVERAGE` `2017-01` at `1.42%`) |
| **Scene Inventory (`3,593` scenes `2016-12`..`2025-12`)** | **COMPLETED & MD5 VERIFIED** | [sentinel2_scenes_2017_2025.csv](file:///home/lokman/Desktop/FeildShit-SI-Model/data/SENTINEL2/raw/phaseC_2017_2025/sentinel2_scenes_2017_2025.csv) |
| **March 2024 Representative Monthly GeoTIFFs (`10 m` & `20 m`)** | **COMPLETED (Phase A)** + **Phase B `-9999` Crops** | `data/SENTINEL2/raw/phaseA_2024_03/` (untouched) & `data/SENTINEL2/raw/phaseB_benchmark_2024_03/` |
| **Seasonal Pixel-Median Composites (`2018–2025`)** | **PENDING GEE QUOTA RESET** | Blocked when `spry-framework-514800-j2` entered `restricted mode`; exploratory monthly-aggregated seasonal CSV provided cleanly labeled |
| **Annual Pixel-Median Composites & GeoTIFFs (`2017`, `2025`)** | **PENDING GEE QUOTA RESET** | Blocked by GEE `restricted mode`; exploratory monthly-aggregated annual CSV provided cleanly labeled |
| **Additional Selected Monthly GeoTIFFs & `2017–2025` `20 m` Coverage GeoTIFF** | **PENDING GEE QUOTA RESET** | `2019-04`, `2022-07`, `2025-04`, and `sentinel2_valid_obs_count_2017_2025_20m.tif` deferred |

---

## 2. Multi-Source Spatial Inventory & Integration Rules

```text
                        dataset                                                                            source_file                                           variables    period                            crs                 resolution            grid_shape
            Sentinel-2 (Target)                                                            COPERNICUS/S2_SR_HARMONIZED                 NDVI, EVI (10 m); NDMI, NDRE (20 m) 2017-2025                     EPSG:32632                10 m / 20 m                   N/A
       Crop Frequency (ESA/GEE)                             data/land_cover/guelma_crop_frequency_2021_2025_utm32n.tif                                      Crop frequency 2021-2025                     EPSG:32632            10.0 m x 10.0 m 7341 x 9268 (1 bands)
                  MODIS MOD13Q1                                       data/land_cover/guelma_modis_vegetation_2016.tif              NDVI, EVI (16-day / seasonal / annual) 2016-2025                     EPSG:32632          250.0 m x 250.0 m   286 x 367 (2 bands)
                  SoilGrids 2.0 data/SoilGrids/drive-download-20261114T174721Z-1-001/guelma_soilgrids_42bands_250m.tif Clay, Sand, Silt, pH, SOC, CEC, Nitrogen (6 depths)    Static                     ESRI:54009          250.0 m x 250.0 m  297 x 358 (42 bands)
          SMAP L4 Soil Moisture                                     data/land_cover/guelma_smap_soil_moisture_2016.tif                    Surface & Rootzone Soil Moisture 2016-2025                     EPSG:32632      11000.0 m x 11000.0 m       8 x 9 (2 bands)
        GPM IMERG Precipitation                  data/land_cover/guelma_gpm_annual_rainfall_2016_2025_utm32n_stack.tif                     Annual & Seasonal Precipitation 2016-2025                     EPSG:32632      9633.88 m x 9633.88 m     8 x 10 (10 bands)
      NASA POWER (AG — MERRA-2)                                                    data/NASA_POWER_REGIONAL/processed/            T2M, T2M_MAX, T2M_MIN, PRECTOTCORR, RH2M 2016-2025 EPSG:4326 (area in EPSG:32632) 0.5x0.625 deg (~55-111 km)  5 intersecting cells
NASA POWER (RE — CERES SYN1deg)                                                    data/NASA_POWER_REGIONAL/processed/                                   ALLSKY_SFC_SW_DWN 2016-2025 EPSG:4326 (area in EPSG:32632)   1.0x1.0 deg (~55-111 km)  2 intersecting cells
```

### Mandatory Integration Guardrails for Field Shift
1. **No Fake Downscaling / Upsampling:** Never upsample NASA POWER (`~55–111 km`), SMAP (`11 km`), GPM (`~9.6 km`), or MODIS/SoilGrids (`250 m`) to Sentinel-2 `10 m`/`20 m`.
2. **Preserve Native Sentinel-2 Resolutions:** Keep `NDVI`/`EVI` at `10 m` (`B4, B8, B2`) and `NDMI`/`NDRE` at `20 m` (`B8A, B5, B11`). Aggregate `10 m -> 20 m` or `10 m/20 m -> 250 m / 11 km` only downward when joining multi-source tables.
3. **NDMI vs. Direct Soil Moisture:** `NDMI` measures canopy leaf water content, NOT volumetric soil moisture (`SMAP`), and acts as a vegetation-moisture complement.
4. **Incomplete Period Handling:** Filter or weight `2017-01` (`1.42%` coverage, `1` scene) and `Winter 2017` (`1` scene in Dec 2016 + `1` in Jan 2017) explicitly in trend/model fits.

---

## 3. Authoritative Audit & Integration Specifications
- Full Multi-Dataset Integration Specification: [cross_dataset_integration_specification.md](file:///home/lokman/Desktop/FeildShit-SI-Model/data/SENTINEL2/processed/metadata/cross_dataset_integration_specification.md)
- Seasonal & Annual Aggregation Limitations: [seasonal_annual_limitations_report.md](file:///home/lokman/Desktop/FeildShit-SI-Model/data/SENTINEL2/processed/metadata/seasonal_annual_limitations_report.md)
- Deferred GEE Recovery Catalog (`39` tasks): [deferred_gee_task_inventory.md](file:///home/lokman/Desktop/FeildShit-SI-Model/data/SENTINEL2/processed/quality/deferred_gee_task_inventory.md)
