# Field Shift — Guelma Wilaya Agro-Environmental Data Foundation (`2016–2025`)

Data-driven agricultural decision-support data engineering repository for **Guelma Wilaya, Algeria** (`3683.2311 km²`, `34` communes, `EPSG:32632`), prepared for **NASA Space Apps Challenge 2026**.

## Project Pipeline Stages Completed
1. **NASA POWER Regional Climate (`2016–2025`):** Daily, monthly, seasonal, and annual area-weighted climate variables (`AG` `0.5°×0.625°` MERRA-2 + `RE` `1.0°×1.0°` CERES SYN1deg) -> `data/NASA_POWER_REGIONAL/processed/` (`run_nasa_power_pipeline.py`).
2. **Sentinel-2 Vegetation Indices (`2017–2025`, GEE Project `spry-framework-514800-j2`):** `108` monthly statistical summaries (`10 m` NDVI/EVI with `denom>0.1` + `SR>=0`; `20 m` NDMI/NDRE) + `3,593` scene metadata rows MD5-verified (`16 PASS, 1 CHECK, 0 FAIL`); deferred multi-year GeoTIFFs & pixel-median seasonal/annual tasks queued cleanly on noncommercial `restricted mode` -> `data/SENTINEL2/` (`sentinel2_pipeline/phaseC_runner.py`).
3. **Phase D Cross-Dataset Integration & Feature Engineering Foundation:** Canonical 6-layer normalization (`NASA POWER`, `GPM IMERG`, `SMAP L4`, `MODIS MOD13Q1`, `SoilGrids 2.0 V6`, `ESA Crop Frequency`, `Sentinel-2`, `GADM 4.1`), raster alignment fix (`Crop Frequency 10 m -> Sentinel-2 10 m`), downward-only `250 m` & `34`-Commune aggregations, causal lagged feature tables, and `11 PASS / 1 CHECK / 0 FAIL` automated validation -> `data/INTEGRATED/` (`run_phaseD_integration.py`).

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
  - `wilaya_monthly_panel_2016_2025.csv` (`120` rows)
  - `wilaya_seasonal_panel_2016_2025.csv` (`40` rows)
  - `commune_static_soil_and_land_features.csv` (`34` communes)
  - `commune_seasonal_panel_2016_2025.csv` (`1360` rows)
  - `landscape_250m_static_features.csv` (`59,050` valid `250 m` pixels)

## Important Guardrails
- Coarse regional datasets (`NASA POWER ~55–111 km`, `SMAP 11 km`, `GPM 9.6 km`) are **never** upsampled to `10 m` field pixels.
- Monthly `GPM`/`SMAP` files do not exist on disk and are not fabricated; `2017-01` (`1.4173%` coverage) and `Winter 2017` are explicitly flagged ineligible.
- `Crop Frequency (2021–2025)` is blocked from predicting `2017–2020`, and `SoilGrids Nitrogen` is retained strictly for traceability pending unit validation.
