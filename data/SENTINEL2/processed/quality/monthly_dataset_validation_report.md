# Sentinel-2 Monthly Dataset Validation Report — Guelma Wilaya (2017–2025)

**Validated Dataset:** [sentinel2_monthly_indices_2017_2025.csv](file:///home/lokman/Desktop/FeildShit-SI-Model/data/SENTINEL2/processed/monthly/sentinel2_monthly_indices_2017_2025.csv)  
**Source Raw Exports:** [gee_monthly_indices_raw.csv](file:///home/lokman/Desktop/FeildShit-SI-Model/data/SENTINEL2/raw/gee_exports/gee_monthly_indices_raw.csv) (`36/36` quarterly GEE batch CSVs, `100%` MD5 verified)  
**Study Domain:** Guelma Wilaya (`3683.2311 km²`, `EPSG:32632`; static `10 m` binary domain = `36,832,135 px`, `20 m` binary domain = `9,207,986 px`)  
**Audit Date UTC:** `2026-11-15`

---

## 1. Executive Validation Matrix

| Audit Criterion | Result | Evidence / Measured Range | Status |
|---|---|---|---|
| **Row Count & Temporal Extent** | `108` rows (`2017-01` through `2025-12`) | Exact match to 108 calendar months | **PASS** |
| **Duplicate Timestamps** | `0` duplicates | `year_month` strictly unique across all `108` rows | **PASS** |
| **Chronological Ordering** | Strictly ascending | Exact equality with `[2017-01 .. 2025-12]` | **PASS** |
| **Missing / Empty Months** | `0` empty months (`0` NaN cells) | All `108 × 101` cells populated; `0` empty composites | **PASS** |
| **Incomplete Periods (`<90%` cov.)** | `1` month flagged (`2017-01`) | `2017-01` = `1.4173%` (`1` scene); remaining `107` months = `95.94%–100.0%` | **PASS (Flagged)** |
| **Scene & Cloud-Prob Availability** | `1–52` scenes/mo (`median 33.5`) | `3,592` scenes (`2017–2025`); `99.03%` matched to `S2_CLOUD_PROBABILITY` (`+1` Dec 2016 = `3,593`) | **PASS** |
| **Valid Observations / Pixel** | `0.0142–17.74 obs/px` (`10 m`), `0.0142–17.75` (`20 m`) | Median across `108` months = `7.47 obs/px` (`10 m & 20 m`); `2025` jumped to `10.13` via Sentinel-2C | **PASS** |
| **Spatial Coverage Consistency** | `1.4173% – 100.0000%` (`10 m`), `1.4220% – 100.0000%` (`20 m`) | `+3` px (`0.000008%`) edge-rounding delta observed in `valid_obs_10m_count` (`36,832,138` vs `36,832,135`) and `5` full clear months; `0` delta at `20 m` | **PASS (Audited)** |
| **Index Statistical Ordering** | Exact `min <= p5 <= median <= p95 <= max`, `stdDev >= 0` | Verified on every row for all `4` indices (`NDVI, EVI, NDMI, NDRE`) | **PASS** |
| **Index Medians Physical Bounds** | Zero monthly medians outside `[-1, 1]` | `NDVI [0.1308, 0.7071]`, `EVI [0.0957, 0.4842]`, `NDMI [-0.1914, 0.2539]`, `NDRE [0.0840, 0.4805]` | **PASS** |
| **EVI Exclusion Diagnostics** | `534,281` obs + `1,262` composite px excluded | Guard: `B2,B4,B8 >= 0` & `denom > 0.1`; no silent clipping of raw tail (`[-2.5287, +10.6913]`) | **PASS** |
| **NoData & Masking Compliance** | `-9999` verified on Phase B crops & Phase C raster code | Pre-fix Phase A March 2024 baseline GeoTIFFs retained untouched for lineage; Phase C multi-year GeoTIFFs pending quota reset | **PASS (Scoped)** |
| **Units & Resolution Consistency** | `NDVI/EVI` @ `10 m`, `NDMI/NDRE` @ `20 m`, `EPSG:32632` | Reflectance scaling `0.0001`; all `6` existing GeoTIFFs verified in `EPSG:32632` at native `10 m`/`20 m` | **PASS** |

---

## 2. Deep-Dive Spotlight: January 2017 (`PARTIAL_LOW_COVERAGE`)

- **Timestamp:** `2017-01` (`2017-01-01` to `2017-01-31`)
- **Scene Count:** `1` distinct Sentinel-2A L2A scene intersecting Guelma (matched `1/1` to `COPERNICUS/S2_CLOUD_PROBABILITY`).
- **Spatial Coverage:**
  - `10 m`: **`522,022`** valid composite pixels out of `36,832,135` domain pixels = **`1.4173%`** valid coverage (**`98.5827%`** missing/unobserved). Mean valid observations across the full Wilaya = **`0.0142` obs/px** (`p5=0, p50=0, p95=0, max=1`).
  - `20 m`: **`130,938`** valid composite pixels out of `9,207,986` domain pixels = **`1.4220%`** valid coverage (**`98.5780%`** missing).
- **Index Values (Non-Representative Sample of `~52.2 km²` Corner Swath):**
  - `NDVI`: median `0.1308`, mean `0.1459`, stdDev `0.0684`, p5..p95 `[0.0449, 0.2738]`.
  - `EVI`: median `0.0957`, mean `0.1053`, stdDev `0.0595`, p5..p95 `[0.0293, 0.2168]`.
  - `NDMI`: median `-0.1504`, mean `-0.1448`; `NDRE`: median `0.0840`, mean `0.0916`.
  - `SCL=2` (dark area pixels): `317` of `130,938` `20 m` observations (`0.2421%`). `EVI` exclusions: `0`.
- **Modeling Mandate:** Because `2017-01` samples only `1.42%` of Guelma along a single orbital swath edge rather than a Wilaya-wide baseline, **do not treat `2017-01` as a spatially representative monthly feature**. Exclude `2017-01` (or down-weight by coverage fraction / flag `PARTIAL_LOW_COVERAGE`) in trend regressions and agricultural modeling.

---

## 3. Cloud Coverage & Observation Nuances Across the 108 Months

### Months Below `99.0%` Spatial Coverage
Only `5` months out of `108` fell below `99.0%` valid spatial coverage; `4` of the `5` exceeded `95.9%` coverage (`COMPLETE`):
1. `2017-01`: `1.4173%` (`1` scene, `0.0142 obs/px`) — `PARTIAL_LOW_COVERAGE`
2. `2023-05`: `95.9356%` (`32` scenes, `3.11 obs/px`, `4.0644%` persistent cloud gap) — `COMPLETE`
3. `2019-05`: `97.3871%` (`31` scenes, `3.83 obs/px`) — `COMPLETE`
4. `2020-03`: `98.8887%` (`36` scenes, `3.11 obs/px`) — `COMPLETE`
5. `2025-01`: `98.9096%` (`34` scenes, `3.41 obs/px`) — `COMPLETE`

### Domain Edge Rounding (`+3` Pixels at `10 m`)
- At `20 m`, `valid_obs_20m_count` equals static `total_pixels_20m` (`9,207,986`) identically across all `108` months (`diff = 0`).
- At `10 m`, GEE's float `unmask(0)` `valid_obs_10m` raster included `36,832,138` boundary-center pixels vs the `36,832,135` count cached in `total_pixels_10m` (`+3` edge pixels = `0.000008%`). In `5` cloud-free spring/summer months (`2017-04`, `2017-05`, `2017-06`, `2021-08`, `2023-08`), raw `NDVI_count` reached `36,832,137` or `36,832,138`, which rounds/caps cleanly to `100.0000%` (`phaseC_finalize_local.py`). No bias (`< 10^-7`) is introduced into any index statistic.

### Cloud-Probability Match & Constellation Evolution
- **Total Scenes (`2017–2025`):** `3,592` (`+1` Dec 2016 = `3,593`), across Sentinel-2A (`1,739`), Sentinel-2B (`1,681`), and Sentinel-2C (`173` starting `2025`, lifting `2025` to `534` scenes and `10.13 obs/px` vs `6.93–7.83 obs/px` during `2018–2024`).
- **Missing `S2_CLOUD_PROBABILITY` Pairs:** `34 / 3,593` scenes (`0.95%`: `25` in `2017`, `1` in `2018`, `5` in `2023`, `3` in `2025`) were not present in `COPERNICUS/S2_CLOUD_PROBABILITY` and gracefully fell back to `SCL` cloud/shadow masking via the GEE outer join.

---

## 4. Index Distributions, EVI Stability & SCL=2 Diagnostics

- **Overall `108`-Month Spatial-Median Summary:**
  - `NDVI (10 m)`: min `0.1308` (`2017-01`), max `0.7071` (`2020-04`), 108-month mean `0.4108` (`p5..p95` reflects bare/senescent summer valleys vs dense spring cereal/forest canopies).
  - `EVI (10 m)`: min `0.0957` (`2017-01`), max `0.4842` (`2019-04`), 108-month mean `0.2544`.
  - `NDMI (20 m)`: min `-0.1914`, max `0.2539`, 108-month mean `-0.0078` (canopy moisture proxy; negative in dry summer bare soil/stubble, positive in peak spring).
  - `NDRE (20 m)`: min `0.0840`, max `0.4805`, 108-month mean `0.2815` (red-edge chlorophyll proxy).
- **EVI Numerical Guard Effectiveness (`B2,B4,B8 >= 0` & `denom > 0.1`):**
  - Across `108` months, `534,281` unstable pixel-observations and `1,262` single-pixel composite values were masked before compositing.
  - Exclusions were heavily concentrated in `2017` (`109,998` obs) and `2018` (`254,354` obs, notably `126,131` obs in `2018-03`) compared to `10,375–21,193` obs/yr in `2020–2025`, reflecting darker low-reflectance terrain/shadow edge pixels in pre-PB-04.00 scenes.
  - Raw unclipped pixel `min`/`max` remained bounded only by valid surface optics (`EVI_min = -2.5287`, `EVI_max = 10.6913` in `2024-04`), while `EVI_p5`, `EVI_median`, and `EVI_p95` remained strictly physical and stable (`max EVI_median = 0.4842`). **Recommendation:** Use `EVI_median` / `p5–p95` over `EVI_mean` for unclipped regional sensitivity analysis.
- **`SCL=2` Dark Area Pixels:** Median monthly share = `0.3962%` (`range: 0.0079% – 7.9512%`), declining after ESA `PB 04.00` harmonization (`1.27%–1.36%` median in `2018–2021` vs `0.20%–0.28%` in `2022–2025`). Retaining `SCL=2` preserved moist soil and topographic north-facing slopes without inflating anomalies.
