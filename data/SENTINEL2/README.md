# Sentinel-2 Vegetation Monitoring Pipeline — Guelma Wilaya (2017–2025)

**Status:** `PHASE_C_FINAL_AUDIT_COMPLETE_GEE_RESTRICTED_MODE` (`108/108` monthly statistical summaries & `3,593` scene metadata rows MD5-verified; `39` deferred GEE GeoTIFF/pixel-composite tasks queued for resumption upon quota reset on `spry-framework-514800-j2`)  
**GEE Project:** `spry-framework-514800-j2` (`REGISTERED_NOT_COMMERCIALLY`)  
**Collection:** `COPERNICUS/S2_SR_HARMONIZED` (paired with `COPERNICUS/S2_CLOUD_PROBABILITY`)  
**Boundary:** `data/boundaries/processed/guelma_wilaya_boundary.geojson.gpkg` (`3683.2311 km²` in `EPSG:32632`; `34` communes in `guelma_communes_boundaries.gpkg`)

## Resolution & Masking Policy
- **Reflectance scaling:** `DN × 0.0001` applied before all index calculations.
- **Cloud & shadow masking:** Exclude `SCL` classes `[0, 1, 3, 8, 9, 10, 11]` plus `S2_CLOUD_PROBABILITY >= 40%` (where matched by `system:index`; `99.05%` matched across `3,593` scenes). `SCL` Class 2 (`Dark area pixels`) is retained (`median 0.3962%` across `108` months) to preserve topographic/moist-soil pixels.
- **EVI numerical stability:** Require `B2 >= 0, B4 >= 0, B8 >= 0` and denominator `B8 + 6*B4 - 7.5*B2 + 1 > 0.1` without silently clipping extreme composite pixels (`534,281` unstable obs & `1,262` composite pixels excluded cleanly).
- **Spatial resolution:**
  - `NDVI` (`B8, B4`) & `EVI` (`B8, B4, B2`): native **`10 m`** (`EPSG:32632`).
  - `NDMI` (`B8, B11`) & `NDRE` (`B8A, B5`): native **`20 m`** (`EPSG:32632`; `B8` aggregated to 20 m, never upsampled to 10 m).

## Verified Deliverables & Audit Reports
- **Monthly statistical time series (`108` months `2017-01`–`2025-12`):** `processed/monthly/sentinel2_monthly_indices_2017_2025.csv` (`2017-01` flagged `PARTIAL_LOW_COVERAGE` at `1.4173%` from `1` scene; `107` months `95.94%–100.0%`)
- **Scene metadata inventory (`3,593` scenes `2016-12`–`2025-12`):** `raw/phaseC_2017_2025/sentinel2_scenes_2017_2025.csv`
- **Exploratory monthly-aggregated seasonal/annual tables (distinct from deferred GEE pixel-median composites):** `processed/seasonal/sentinel2_seasonal_from_monthly_2017_2025.csv`, `processed/annual/sentinel2_annual_from_monthly_2017_2025.csv`
- **Phase C Final Audit Suite:**
  - Final Sentinel-2 audit report: `processed/metadata/final_sentinel2_audit_report.md`
  - Monthly dataset validation report: `processed/quality/monthly_dataset_validation_report.md` (`16 PASS`, `1 CHECK`, `0 FAIL` in `sentinel2_quality_report.csv`)
  - Seasonal & annual aggregation limitations report: `processed/metadata/seasonal_annual_limitations_report.md`
  - Cross-dataset integration specification: `processed/metadata/cross_dataset_integration_specification.md` & `processed/metadata/integration_readiness_report.md`
  - Deferred GEE task inventory (`39` tasks): `processed/quality/deferred_gee_task_inventory.md` & `processed/quality/deferred_gee_task_inventory.csv`
  - Metadata & schema: `processed/metadata/processing_metadata.json`, `processed/metadata/data_dictionary.csv`
- **Visualizations & Spatial Maps:** `processed/analysis/figures/*.png`, `processed/spatial/maps/*.png`, `processed/spatial/sentinel2_guelma_vegetation_maps.gpkg`

## Pipeline Scripts & Quota-Safe Resumption
- **Offline status & dry-run deferred queue (zero GEE calls):**
  - `python -m sentinel2_pipeline.phaseC_runner --step status`
  - `python -m sentinel2_pipeline.phaseC_runner --step resume-deferred --group all`
- **Resume deferred tasks strictly after quota resets (skips all `37` verified completed batches):**
  - `python -m sentinel2_pipeline.phaseC_runner --step preflight`
  - `python -m sentinel2_pipeline.phaseC_runner --step resume-deferred --group rasters-monthly --live`
- **Offline post-processing & QA suite:**
  - `python -m sentinel2_pipeline.phaseC_finalize_local`
