# Phase B Report — Cost Assessment, Scientific QA Validation & Benchmark Results

**Project:** Field Shift (NASA Space Apps Challenge 2026)  
**GEE Project:** `spry-framework-514800-j2` (`REGISTERED_NOT_COMMERCIALLY`)  
**Benchmark Month:** March 2024 (`2024-03-01` to `2024-04-01`, `35` Sentinel-2 L2A scenes)  
**Benchmark Artifacts:** `/home/lokman/Desktop/FeildShit-SI-Model/data/SENTINEL2/raw/phaseB_benchmark_2024_03/`  
**Phase A Baseline (Untouched):** `/home/lokman/Desktop/FeildShit-SI-Model/data/SENTINEL2/raw/phaseA_2024_03/`  
**Status:** Phase B.1, B.2, and B.3 complete — **Phase C NOT started** (awaiting user approval).

---

## 1. Phase A Baseline Cost Breakdown (`March 2024`)

### 1.1 Measured Execution Metrics (Phase A — Pre-Optimization)

| Batch Task | Kind | Scale | Runtime (s) | Wall Time (s) | Measured EECU-s | % of Total EECU | Local Size |
|---|---|---:|---:|---:|---:|---:|---:|
| `sentinel2_2024_03_summary` | Table (CSV) | 10 m + 20 m | 32.49 | 37.10 | 12,221.34 | 56.67% | 1,116 B |
| `sentinel2_2024_03_indices_10m` | Image (2 bands) | 10 m | 341.29 | 348.93 | 4,749.67 | 22.03% | 413.65 MB |
| `sentinel2_2024_03_valid_obs_10m` | Image (1 band) | 10 m | 246.08 | 252.21 | 2,724.10 | 12.63% | 8.75 MB |
| `sentinel2_2024_03_indices_20m` | Image (2 bands) | 20 m | 202.36 | 207.17 | 1,008.98 | 4.68% | 107.17 MB |
| `sentinel2_2024_03_valid_obs_20m` | Image (1 band) | 20 m | 1,001.93 | 1,038.96 | 859.50 | 3.99% | 2.64 MB |
| `sentinel2_2024_03_scenes` | Table (CSV) | Metadata | 2.79 | 9.02 | 0.42 | 0.002% | 5,779 B |
| **Total (Phase A)** | **6 tasks** | **10 m / 20 m** | — | — | **21,564.01** (`~5.99` EECU-h) | **100.0%** | **532.22 MB** |

### 1.2 Batch Export vs. Interactive Execution Limits

Using `ee.batch.Export.*` does **not** make computation cheaper in Earth Engine. Batch jobs charge full EECU-seconds for every pixel read, join, mask, and reduction; they simply run asynchronously on dedicated workers with higher memory and runtime limits rather than failing on interactive `getInfo()` timeout/payload caps.

### 1.3 Why `sentinel2_2024_03_summary` Consumed `12,221.34` EECU-s

The unoptimized summary job consumed **56.67% of Phase A compute** because it executed:
1. **Five separate whole-region `reduceRegion()` scans** across Guelma (`comp_10m`, `obs10`, `comp_20m`, `obs20`, `scl2_sums`), plus repeated static `ones.reduceRegion()` pixel-count scans.
2. **Repeated evaluation of the joined 35-scene collection (`ee.Join.saveFirst` + masking)** across unshared graphs.
3. **High `tileScale=8` (`64` sub-tiles) combined with weighted reducers (`median + mean + stdDev + minMax + count`)** on `~36.85M` 10 m pixels.

---

## 2. Phase B.1 Measured Diagnostics & Applied Fixes

### A. EVI Reflectance & Denominator Sensitivity (`phaseB_diag_report.json`)

We evaluated all `326,957,262` valid March 2024 10 m pixel-observations and composite distributions across Guelma (`36,831,907` valid NDVI pixels) under candidate denominator thresholds (`> 0.00`, `> 0.05`, `> 0.10`, `> 0.20`) plus non-negative reflectance checks (`B2 >= 0 & B4 >= 0 & B8 >= 0`):

- **Negative surface reflectance count (`any_sr_neg`):** `0` out of `326,957,262` observations (`b2_neg = 0`, `b4_neg = 0`, `b8_neg = 0`) in these PB 04.00+ `S2_SR_HARMONIZED` scenes (non-negative guard retained as defensive protection across 2017–2025).
- **EVI denominator `D = B8 + 6*B4 - 7.5*B2 + 1` distribution:**
  - Normal median-composite landscape range: `p0.1 = 1.1338`, `p5 = 1.2582`, `p50 = 1.4141`, `p95 = 1.6639`, `p100 = 2.1639` (per-obs range `-0.3628` to `+3.4081`).
  - Near-zero / negative observations out of `326,957,262`:
    - `D <= 0.00`: `364` obs (`0.00011%`)
    - `D <= 0.05`: `497` obs (`0.00015%`)
    - `D <= 0.10`: `689` obs (`0.00021%`)
    - `D <= 0.20`: `1,301` obs (`0.00040%`)

| EVI Variant | Threshold Rule | Valid Composite Pixels | EVI `min` | EVI `mean` | EVI `max` | `|EVI| > 2` px | `EVI < -1` px | `EVI > +1` px |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Baseline (`evi_base`) | `\|D\| >= 1e-6` only | 36,831,907 | -11.6737 | 0.46936 | +16.0164 | 79 | 32 | 5,683 |
| Sensitivity `t005` | `SR >= 0 & D > 0.05` | 36,831,890 | -1.8807 | 0.46936 | +8.8833 | 70 | 1 | 5,700 |
| **Selected (`t010`)** | **`SR >= 0 & D > 0.10`** | **36,831,883** | **-2.5287** | **0.46936** | **+5.3760** | **57** | **1** | **5,692** |

**Scientific Decision:**
- Adopted **`EVI_DENOM_THRESHOLD = 0.10`** plus **`B2 >= 0 & B4 >= 0 & B8 >= 0`** in `sentinel2_pipeline/config.py` and `sentinel2_pipeline/phase2_gee_client.py`.
- Moving from unguarded `1e-6` to `D > 0.10` removes extreme division-by-zero singularities (`-11.67` and `+16.02` cut to `[-2.53, +5.38]`, `EVI < -1` drops from `32` to `1` pixel) while masking only **24 composite pixels (`0.000065%`)** and leaving landscape mean (`0.46936`) untouched.
- **No silent clipping to `[-1, 1]`** is applied: the `~5,692` dense vegetation pixels (`1.00–1.05`, `NDVI ~ 0.92`) are legitimate unclipped EVI values.

### B. Exterior NoData Validation (`10 km × 10 km` Boundary Crop)

A `10 km × 10 km` boundary-straddling test crop (`EPSG:32632` `[315000, 4020000, 325000, 4030000]`, `69.4%` inside Guelma, `30.6%` outside) was exported using `mask_10m` / `mask_20m` and `.unmask(-9999, False)` + `noData: -9999`:

- **`phaseB_2024_03_crop_valid_obs_10m.tif` (`1000 × 1000`, `10 m`, `EPSG:32632`):**
  - `nodata = -9999.0`, exterior zero count = **`0`**, `100%` of `305,916` exterior pixels (`all_touched=False`) equal **`-9999`**; interior valid observations range `1..11` (`3` unmasked/cloud-gapped NoData `-9999` interior pixels).
- **`phaseB_2024_03_crop_valid_obs_20m.tif` (`500 × 500`, `20 m`, `EPSG:32632`):**
  - `nodata = -9999.0`, exterior zero count = **`0`**, `76,478 / 76,479` pixels outside pixel-center mask equal **`-9999`** (and `100%` of strictly exterior pixels under `all_touched=True` equal `-9999`; the single pixel difference at `all_touched=False` is one boundary pixel touching the polygon with GEE fractional coverage `>= 0.5`).
- This completely eliminates the Phase A defect where `28,367,800` exterior 10 m pixels were written as `0`.

### C. Unified Binary Boundary Mask (`valid_pct <= 100.0%`)

Replaced inconsistent fractional `.clip()` counting (`100.054%` in Phase A) with deterministic binary interior masks (`ee.Image.constant(1).clip(guelma_geom).mask().gte(0.5)` at native `10 m` and `20 m`), pre-computing static domain counts once:
- `total_pixels_10m = 36,832,135` (`3,683.21 km²` vs vector area `3,683.37 km²`)
- `total_pixels_20m = 9,207,986` (`3,683.19 km²`)

### D. Deterministic Google Drive Export Manager

Implemented `sentinel2_pipeline/drive_export_manager.py` to:
- Pre-create or resolve a single canonical Google Drive folder ID (`1m8c2eavFEhGkLTo-QemLKOeb7H9no1Hq` for Phase B benchmark) before launching tasks.
- Extract destination folder IDs directly from `task.status()["destination_uris"]` and verify file size + `md5Checksum` on every downloaded file.

---

## 3. Phase B.2 Controlled March 2024 Benchmark Results

**Benchmark Task:** `phaseB_2024_03_summary_optimized` (`MDHQ6UHKHIFVGAWRSIRDYTNC`)  
**Architecture Tested:** Pre-computed static domain counts + single-pass temporal `median().combine(count())` + 2 stacked `reduceRegion(.unweighted())` calls (`1` at `10 m` for `[NDVI, EVI, valid_obs_10m, evi_valid_obs_10m]`, `1` at `20 m` for `[NDMI, NDRE, valid_obs_20m, scl2_obs]`), `tileScale=4`.

| Metric | Phase A Baseline (`sentinel2_2024_03_summary`) | Phase B.2 Optimized (`phaseB_2024_03_summary_optimized`) | Delta / Verification |
|---|---:|---:|---|
| **Whole-region `reduceRegion` passes** | `5` (plus `2` static) | **`2`** (static precomputed) | **-60% scans** |
| **Measured EECU-seconds** | **`12,221.3408`** | **`5,823.6221`** | **`-52.35%` (`-6,397.72` EECU-s)** |
| **GEE compute runtime / wall time** | `32.49 s` / `37.10 s` | `128.89 s` / `130.95 s` | Completes cleanly, 0 quota warnings |
| **Output CSV (MD5 verified)** | `1,116 B` | `1,961 B` (`c9712c28...`) | `checksum_verified: true` |
| `NDVI` mean / p50 | `0.6412` / `0.6914` | `0.6412` / `0.6914` | Identical |
| `NDVI_valid_pct` | `100.054%` (defect) | **`99.9994%`** (`36,831,907 / 36,832,135`) | **Fixed (`<= 100.0%`)** |
| `EVI_valid_pct` (`D > 0.10`) | `100.054%` (unguarded) | **`99.9993%`** (`36,831,883 / 36,832,135`) | `24` extreme composite px excluded |
| `NDMI_valid_pct` / `NDRE_valid_pct` | `100.109%` (defect) | **`99.9995%`** (`9,207,941 / 9,207,986`) | **Fixed (`<= 100.0%`)** |
| Mean valid obs (10 m / 20 m) | `8.877` / `8.882` | `8.87695` / `8.88187` | Identical |
| `SCL=2` dark-pixel share (20 m) | `0.299%` (`244,525 / 81,784,148`) | **`0.299%`** (`244,525 / 81,784,148`) | Identical |

---

## 4. Updated 3-Scenario Comparison Across Full Study Period (`2017–2025`, `108` Months)

> **Empirical Basis:** Monthly summary costs use the directly measured Phase A (`12,221.34` EECU-s/mo) and Phase B.2 optimized (`5,823.62` EECU-s/mo) March 2024 benchmarks (`35` scenes). Note that across all `108` months (`2017–2025`), there are `3,592` scenes (`33.26` scenes/month average), so March 2024 is highly representative of average monthly workload. Totals below are explicit extrapolations from these measurements.

| Metric | Scenario 1: All 108 Monthly Full-Res GeoTIFFs + Unoptimized Tables | Scenario 2: Unoptimized Monthly Tables + Selected GeoTIFFs | Scenario 3 (Validated Recommended): Optimized Hybrid Architecture |
|---|---|---|---|
| **Total Export Tasks** | `648` tasks (`108 × 6`) | `~136+` tasks | **`~30–40` checkpointed tasks** (`1` global scene table + `9–18` batched monthly/seasonal/annual tables + `~18–20` GeoTIFFs) |
| **Estimated Local Storage** | `~45–57 GB` (`108 × 532 MB`) | `~3.5–5.5 GB` | **`~3.5–5.5 GB`** (full 108-month CSVs, seasonal/annual CSVs + selected annual/seasonal/coverage GeoTIFFs) |
| **108-Month Summary Table EECU-s** | `~1.320M` (`108 × 12,221`) | `~1.320M` (`108 × 12,221`) | **`~629k` EECU-s (`~174.7` EECU-h)** (`108 × 5,823.62`, **measured `-52.35%`**) |
| **Selected GeoTIFF / Other EECU-s** | `~1.009M` (`108 × 9,342`) | `~110k–160k` (est.) | **`~110k–160k` EECU-s** (if exporting `2` annual 10 m/20 m + `4` multi-year seasonal 10 m/20 m + `1` 20 m `valid_obs_count` + selected benchmark GeoTIFFs; seasonal/annual summary tables would add incremental compute if exported) |
| **Total Estimated EECU-s** | **~2.33M EECU-s** (`~647` EECU-h) | **~1.43M–1.48M EECU-s** (`~397–411` EECU-h) | **`~740k–790k` EECU-s** (`~205–219` EECU-h) for full 108-month tables + selected GeoTIFFs (**~66–68% lower than Scenario 1**) |
| **Resolution Preservation** | 10 m / 20 m (`EPSG:32632`) | 10 m / 20 m (`EPSG:32632`) | **10 m (`NDVI/EVI`) & 20 m (`NDMI/NDRE`) strictly preserved**, `valid_obs` raster exported at 20 m (saves `3.17×` EECU vs 10 m) |

---

## 5. Production Pipeline Updates Implemented in Phase B

All Phase B fixes have been propagated into the production pipeline modules (verified in `phaseB_benchmark_2024_03`, while leaving Phase A files untouched):
- **`sentinel2_pipeline/config.py`**: Added `EVI_DENOM_THRESHOLD = 0.10` and `NODATA_VALUE = -9999`.
- **`sentinel2_pipeline/drive_export_manager.py`**: Canonical single-folder creation/resolution, transient OAuth/network retries, `destination_uris` folder lookup, byte-size and MD5 verification.
- **`sentinel2_pipeline/phase2_gee_client.py`**:
  - Added `_build_boundary_masks` (`mask_10m`, `mask_20m`) and `_compute_static_boundary_counts`.
  - Updated `_mask_and_indices` with `B2/B4/B8 >= 0 & evi_denom > 0.10` (no silent `[-1, 1]` clipping).
  - Refactored `run_gee_summary_exports` to use the benchmarked 2-pass stacked `reduceRegion(.unweighted())` architecture.
  - Updated `submit_gee_batch_raster_exports` & `_download_image_tiled` to use `unmask(-9999, False)`, `noData: -9999`, and `ensure_single_drive_folder`.
- **`sentinel2_pipeline/phase3_postprocess_qa.py`**:
  - Updated `QA_07_SPATIAL_COVERAGE` to enforce `0 < pct <= 100.0%` (`FAIL` if `> 100.0%`).
  - Updated `QA_16_PIXEL_EXTREMES_UNCLIPPED` to report raw unclipped NDVI and EVI bounds.
  - Added `QA_17_NODATA_EXTERIOR_CHECK` verifying all strictly exterior raster pixels equal `-9999` (`0` zero-fill tolerance).

---

## 6. Authorization Gate Before Phase C

Phase B is complete. No Phase C multi-month exports (`2017–2025`) have been started. Please confirm if you authorize **Phase C** execution under **Scenario 3 (Validated Optimized Hybrid Architecture)**, specifying whether you want:
1. Full **108 monthly summary tables (`2017–2025`)** in checkpointed annual Drive batches + `1` global scenes table, and
2. Which **composite GeoTIFF rasters** to export alongside (e.g., annual `2017` & `2025`, multi-year seasonal composites `2018–2025`, and `2017–2025` `valid_obs_count` at `20 m`).
