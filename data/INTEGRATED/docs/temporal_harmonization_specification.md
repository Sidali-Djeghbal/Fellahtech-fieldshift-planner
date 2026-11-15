# Temporal Harmonization Specification — Field Shift (Phase D)

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
