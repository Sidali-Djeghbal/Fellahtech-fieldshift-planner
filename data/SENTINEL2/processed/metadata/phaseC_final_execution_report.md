# Phase C Final Execution, Quota & Scientific Delivery Report

**GEE Project:** `spry-framework-514800-j2` (`REGISTERED_NOT_COMMERCIALLY`)  
**Study Period:** `2017-01` through `2025-12` (`108` months, `3,592` Sentinel-2 L2A scenes; `+1` Dec 2016 scene = `3,593` total)  
**Canonical Phase C Drive Folder:** `1ow-VqcUKfTORTlkf1js88ovF6GXVyoRE` (`FieldShift_Sentinel2_PhaseC_2017_2025`)  
**Execution Outcome:** **108/108 monthly summaries + global scene inventory COMPLETED & MD5 verified** before noncommercial `restricted mode` halted further task submissions.

---

## 1. Successfully Completed vs. Deferred Outputs

### Completed & Locally Verified (`100%` MD5 Checksum Verified)
- **Complete 108-Month Statistical Time Series (`2017-01` to `2025-12`):** `36` quarterly GEE batch CSV tasks (`2017_Q1`–`2025_Q4`), merged into [sentinel2_monthly_indices_2017_2025.csv](file:///home/lokman/Desktop/FeildShit-SI-Model/data/SENTINEL2/processed/monthly/sentinel2_monthly_indices_2017_2025.csv).
  - Spatial coverage strictly `0% < pct <= 100.0%` across all `108` months (`95.93%–100.0%` across `107` months; `2017-01` = `1.4173%` explicitly flagged `PARTIAL_LOW_COVERAGE`).
  - Applied validated `EVI_DENOM_THRESHOLD = 0.1` + `SR >= 0` (excluded `534,281` unstable pixel-observations and `1,262` extreme composite pixels across `108` months without silently clipping `EVI`).
- **Global Scene Metadata Inventory:** `sentinel2_scenes_2017_2025.csv` (`3,593` scenes, `99.05%` matched to `COPERNICUS/S2_CLOUD_PROBABILITY`).
- **March 2024 Reference Rasters (`10 m` & `20 m`):** Retained untouched in `phaseA_2024_03/` (`4` GeoTIFFs) + validated `-9999` NoData exterior crops in `phaseB_benchmark_2024_03/`.
- **Quality Assurance (`17` checks), Figures (`6` charts + `4` March 2024 spatial maps), Metadata & Data Dictionary:** Updated in `data/SENTINEL2/processed/`.

### Failed / Missing Outputs (Halted Cleanly on GEE `restricted mode` — NOT Fabricated)
After all `36` quarterly monthly tasks (`2017–2025`) succeeded on GEE workers, `spry-framework-514800-j2` emitted:
> *"Your project has exceeded its noncommercial compute quota and is now in restricted mode."*

Per protocol, zero further GEE jobs were launched and no project/account switching was attempted. The following GEE server tasks remain **deferred until quota resets**:
1. **Selected Monthly GeoTIFFs (`10 m` / `20 m`):** `2019-04` (wet spring), `2022-07` (dry summer), `2025-04` (latest spring), and Phase-B-cleaned `2024-03` re-export.
2. **Annual Pixel-Median Composites & GeoTIFFs:** `2017` and `2025` (`10 m` 6-band & `20 m` 2-band) plus server-computed pixel-level annual summary tables (`2017–2025`).
3. **Seasonal Pixel-Median Composites & GeoTIFFs (`2018–2025`):** `32` seasonal statistical summaries plus multi-year seasonal GeoTIFFs (`winter, spring, summer, autumn` at `10 m` & `20 m`).
4. **Multi-Year Coverage GeoTIFF:** `sentinel2_valid_obs_count_2017_2025_20m.tif`.

*(Note: Exploratory `sentinel2_seasonal_from_monthly_2017_2025.csv` and `sentinel2_annual_from_monthly_2017_2025.csv` were generated strictly from the `108` verified monthly tables and are explicitly flagged `Mean of GEE monthly spatial summaries` — not substituted for pixel-level multi-month medians.)*

---

## 2. Incomplete Temporal Periods

- **`2017-01`:** Only `1` Sentinel-2 L2A scene intersected Guelma (`NDVI_valid_pixels = 522,038 / 36,832,135` = **`1.4173%`** coverage). Explicitly flagged `PARTIAL_LOW_COVERAGE`.
- **`Winter 2017` (Dec 2016 – Feb 2017):** `2016-12` had only `1` L2A scene and `2017-01` had `1` scene (`1.42%` coverage). Explicitly flagged `INCOMPLETE_DEC2016(1scene)_AND_JAN2017(1.42%)`.
- **All `107` months `2017-02` through `2025-12`:** `>= 95.93%` spatial coverage (`>= 8.8` mean valid obs/px median overall), marked `COMPLETE`.

---

## 3. Measured vs. Remaining Computational Consumption

| Pipeline Stage | Verified Scope | Measured EECU-seconds | Measured EECU-hours |
|---|---|---:|---:|
| Phase A (March 2024 unoptimized baseline) | `1` month tables + `4` GeoTIFFs + scenes | 21,564.01 | 5.99 |
| Phase B (EVI diagnostics + NoData crops + benchmark) | Diagnostics + optimized `2024-03` summary | 24,124.77 | 6.70 |
| **Phase C (`36` quarterly tables + global scenes)** | **All `108` months (`2017–2025`) + `3,593` scenes** | **658,054.03** | **182.79** |
| **Grand Total Measured Project Compute** | — | **703,742.82** | **195.48** |

- **Benchmark Comparison:** Phase C averaged **`6,093.09` EECU-s/month** (`~18,279.28` per quarter), matching Phase B's `5,823.62` EECU-s benchmark closely (`2017` lower at `~3,635`/mo due to fewer scenes; `2025` Q2–Q4 higher at `~8,859`/mo due to Sentinel-2C cadence) and cutting Scenario 2's unoptimized monthly summary cost (`~1,319,905` EECU-s) by **`~50.1%`**, enabling all `108` months to complete within the single noncommercial quota cycle!
- **Estimated Remaining Consumption (Once Quota Resets):**
  - Selected Monthly GeoTIFFs (`2019-04`, `2022-07`, `2025-04`, `2024-03` at `10 m` + `20 m`): `~23,000 – 28,000` EECU-s.
  - Annual `2017` & `2025` GeoTIFFs (`10 m` 6-band + `20 m` 2-band) + `20 m` `2017–2025` coverage raster: `~60,000 – 110,000` EECU-s.
  - Multi-year Seasonal GeoTIFFs (`4` seasons `10 m` + `20 m`): `~60,000 – 120,000` EECU-s.
  - Server-side Pixel-Level Seasonal (`32`) & Annual (`9`) summary tables (if full pixel-median tables are also desired): `~450,000 – 700,000` EECU-s (already resumable one batch at a time in `phaseC_runner.py`).

---

## 4. Phase C Ledger Batch Log (`37 / 37` Executed Tasks `COMPLETED`)

| Batch Task | Group | State | Measured EECU-s |
|---|---|---|---:|
| `phaseC_monthly_2024_Q1` | monthly | `COMPLETED` | 18,891.18 |
| `sentinel2_scenes_2017_2025` | scenes_inventory | `COMPLETED` | 31.31 |
| `phaseC_monthly_2024_Q2` | monthly | `COMPLETED` | 17,639.21 |
| `phaseC_monthly_2024_Q3` | monthly | `COMPLETED` | 18,334.62 |
| `phaseC_monthly_2024_Q4` | monthly | `COMPLETED` | 17,839.35 |
| `phaseC_monthly_2025_Q1` | monthly | `COMPLETED` | 18,720.41 |
| `phaseC_monthly_2025_Q2` | monthly | `COMPLETED` | 25,867.49 |
| `phaseC_monthly_2025_Q3` | monthly | `COMPLETED` | 26,755.03 |
| `phaseC_monthly_2025_Q4` | monthly | `COMPLETED` | 27,107.15 |
| `phaseC_monthly_2022_Q1` | monthly | `COMPLETED` | 16,447.35 |
| `phaseC_monthly_2022_Q2` | monthly | `COMPLETED` | 18,055.10 |
| `phaseC_monthly_2022_Q3` | monthly | `COMPLETED` | 17,885.54 |
| `phaseC_monthly_2022_Q4` | monthly | `COMPLETED` | 16,696.08 |
| `phaseC_monthly_2023_Q1` | monthly | `COMPLETED` | 17,660.75 |
| `phaseC_monthly_2023_Q2` | monthly | `COMPLETED` | 17,576.56 |
| `phaseC_monthly_2023_Q3` | monthly | `COMPLETED` | 18,213.16 |
| `phaseC_monthly_2023_Q4` | monthly | `COMPLETED` | 17,060.97 |
| `phaseC_monthly_2020_Q1` | monthly | `COMPLETED` | 17,845.37 |
| `phaseC_monthly_2020_Q2` | monthly | `COMPLETED` | 19,711.08 |
| `phaseC_monthly_2020_Q3` | monthly | `COMPLETED` | 19,927.03 |
| `phaseC_monthly_2020_Q4` | monthly | `COMPLETED` | 18,289.77 |
| `phaseC_monthly_2021_Q1` | monthly | `COMPLETED` | 19,898.67 |
| `phaseC_monthly_2021_Q2` | monthly | `COMPLETED` | 19,394.76 |
| `phaseC_monthly_2021_Q3` | monthly | `COMPLETED` | 19,169.57 |
| `phaseC_monthly_2021_Q4` | monthly | `COMPLETED` | 17,773.64 |
| `phaseC_monthly_2019_Q4` | monthly | `COMPLETED` | 18,433.78 |
| `phaseC_monthly_2019_Q3` | monthly | `COMPLETED` | 19,633.76 |
| `phaseC_monthly_2019_Q2` | monthly | `COMPLETED` | 17,667.04 |
| `phaseC_monthly_2019_Q1` | monthly | `COMPLETED` | 19,330.64 |
| `phaseC_monthly_2018_Q4` | monthly | `COMPLETED` | 19,362.36 |
| `phaseC_monthly_2018_Q3` | monthly | `COMPLETED` | 19,821.12 |
| `phaseC_monthly_2018_Q2` | monthly | `COMPLETED` | 18,753.43 |
| `phaseC_monthly_2018_Q1` | monthly | `COMPLETED` | 18,634.89 |
| `phaseC_monthly_2017_Q4` | monthly | `COMPLETED` | 13,820.44 |
| `phaseC_monthly_2017_Q3` | monthly | `COMPLETED` | 14,256.45 |
| `phaseC_monthly_2017_Q2` | monthly | `COMPLETED` | 12,881.58 |
| `phaseC_monthly_2017_Q1` | monthly | `COMPLETED` | 2,667.41 |
