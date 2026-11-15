# Phase D Cross-Dataset Integration & Validation Report — Field Shift

**Study Domain:** Guelma Wilaya, Algeria (`3683.2311 km²`, `34` Communes, `EPSG:32632`)  
**Generated UTC:** `2026-11-15T02:29:04.831969+00:00`  
**Execution Mode:** `100%` Local / Non-Destructive (Zero GEE tasks submitted; zero raw datasets overwritten; no crop modeling started)  
**Validation Outcome:** **`PASS = 11` | `CHECK = 1` | `FAIL = 0`**

---

## 1. Empirical Source Audit Corrections Discovered on Disk
During Task 1 verification against actual workspace files (rather than filenames/docs alone), Phase D caught and handled three critical data realities:
1. **Empty `ESRI:54009` Raw SoilGrids Raster:** `data/SoilGrids/drive-download-20261114T174721Z-1-001/guelma_soilgrids_42bands_250m.tif` contains **`0` finite pixels** across all `42` bands. Integration extracts soil layers exclusively from verified `guelma_soilgrids_42bands_250m_V6_MERGED.tif` inside `guelma_soilgrids_V6_complete_package.zip` (`59,041–59,050` valid UTM32N `250 m` pixels).
2. **GPM IMERG & SMAP L4 Cadence Availability:** Both datasets exist locally at **Seasonal (`DJF/MAM/JJA/SON`) and Annual (`2016–2025`) cadences only** — **no monthly GPM or SMAP files exist on disk**. Phase D leaves `gpm_monthly_available_on_disk = False` and `smap_monthly_available_on_disk = False` rather than inventing synthetic monthly values.
3. **ESA Crop Frequency (`10 m`) Grid-Origin Shift:** `guelma_crop_frequency_2021_2025_utm32n.tif` was shifted `964.876 m` E / `901.969 m` N relative to Sentinel-2 `10 m` (`[315490.0, 4059820.0]`). Phase D snaps it cleanly to [guelma_crop_frequency_2021_2025_aligned_s2_10m.tif](file:///home/lokman/Desktop/FeildShit-SI-Model/data/INTEGRATED/spatial/guelma_crop_frequency_2021_2025_aligned_s2_10m.tif) before `250 m`/Commune downward aggregation, and blocks its use on `2017–2020` historical rows.

---

## 2. Canonical Layers & Analytical Feature Outputs Produced

| Output Tier | File | Records | Temporal Scope | Spatial Support |
|---|---|---:|---|---|
| **Inventory** | [data_inventory.csv](file:///home/lokman/Desktop/FeildShit-SI-Model/data/INTEGRATED/metadata/data_inventory.csv) | `27` datasets | `2016–2025` / Static | Multi-scale verified |
| **Canonical Layers** | `data/INTEGRATED/canonical/{spatial_reference,climate_observations,precipitation_observations,soil_moisture_observations,soil_properties,vegetation_observations}/` | `34` communes, `59,050` soil px, `3,653` days, `108` S2 mo | Native per source | Preserves native support |
| **Wilaya Monthly Features** | [wilaya_monthly_panel_2016_2025.csv](file:///home/lokman/Desktop/FeildShit-SI-Model/data/INTEGRATED/features/wilaya_monthly_panel_2016_2025.csv) | `120` | `2016-01..2025-12` (`107` eligible S2 mo) | Wilaya (`3683.23 km²`) |
| **Wilaya Seasonal Features** | [wilaya_seasonal_panel_2016_2025.csv](file:///home/lokman/Desktop/FeildShit-SI-Model/data/INTEGRATED/features/wilaya_seasonal_panel_2016_2025.csv) | `40` | `Winter 2016..Autumn 2025` | Wilaya (`all sources`) |
| **Commune Static Features** | [commune_static_soil_and_land_features.csv](file:///home/lokman/Desktop/FeildShit-SI-Model/data/INTEGRATED/features/commune_static_soil_and_land_features.csv) | `34` | Static Soil + `2016–2025` clim | `34` Communes (`EPSG:32632`) |
| **Commune Seasonal Panel** | [commune_seasonal_panel_2016_2025.csv](file:///home/lokman/Desktop/FeildShit-SI-Model/data/INTEGRATED/features/commune_seasonal_panel_2016_2025.csv) | `1360` | `2016–2025 × 4 seasons` | `34` Communes |
| **Landscape `250 m` Table** | [landscape_250m_static_features.csv](file:///home/lokman/Desktop/FeildShit-SI-Model/data/INTEGRATED/features/landscape_250m_static_features.csv) | `59,050` | Static Soil + `2016–2025` MODIS | `250 m` (`286×367`) |

---

## 3. Automated Validation Summary (`11 PASS`, `1 CHECK`, `0 FAIL`)

| Check ID | Category | Measured | Status | Notes |
|---|---|---|---|---|
| `VAL_01_SCHEMA_COMPLETENESS` | Schema Validity | `inventory=27 sources; wm=120, ws=40, c_stat=34, c_sea=1360, l250=59050` | **PASS** | Also verified raw ESRI:54009 SoilGrids defect caught cleanly (excluded; V6_MERGED UTM32N used). |
| `VAL_02_UNIT_CONSISTENCY` | Unit Consistency | `tex_sum=[99.90..100.10]%, RH=[37.9..84.6]%` | **PASS** | SoilGrids Nitrogen kept unvalidated (N > SOC subsoil anomaly flagged UNVALIDATED_TRACEABILITY_ONLY). |
| `VAL_03_DATE_AND_NO_FABRICATION` | Date Coverage | `NASA_POWER=120 mo, S2=108 mo, gpm_monthly_fabricated=False` | **PASS** | Monthly GPM & SMAP explicitly marked unavailable on disk; integrated cleanly at seasonal/annual tiers only. |
| `VAL_04_DUPLICATE_RECORDS` | Duplicate Records | `0` | **PASS** | Checked Wilaya monthly/seasonal, Commune static/seasonal, and 59,050 250m pixel keys. |
| `VAL_05_MISSINGNESS_AND_INCOMPLETE_PERIODS` | Missingness & Incomplete Flags | `2017-01_eligible=False (cov=1.4173%), Winter17_complete=False, nodata_leaks=0` | **PASS** | Zero-fill outside boundaries masked cleanly; -9999 never averaged into numeric values. |
| `VAL_06_SPATIAL_COVERAGE` | Spatial Coverage | `wilaya=3683.2311 km2, communes_34=3683.2308 km2, rural_33_min_soil_frac=0.9568, urban_Guelma_soil_frac=0.7518` | **PASS** | All 33 non-capital communes >=95.68% SoilGrids coverage; Guelma urban commune has 536/713 (75.18%) due to genuine ISRIC SoilGrids sealed-urban masking (177 px). |
| `VAL_07_GRID_ALIGNMENT_FIX` | Grid Alignment | `raw_cf_shift=(964.88, 901.97)m -> aligned_S2_10m_match=True; 250m_exact_match=True` | **PASS** | Crop Frequency origin shift fixed cleanly into guelma_crop_frequency_2021_2025_aligned_s2_10m.tif before 250m/commune aggregation. |
| `VAL_08_AGGREGATION_CORRECTNESS` | Aggregation Correctness | `max_depth_err=3.33e-05, max_lag1_err=4.99e-05` | **PASS** | Verified 0-30cm horizon thickness weights (5+10+15=30cm) and strictly past-only lag computation. |
| `VAL_09_FEATURE_RANGES` | Feature Ranges | `S2_medians_in_-1_1=True; soil_physical_ok=True (soc_na=100/59050)` | **PASS** | All finite values within physical bounds; 100/59050 (0.17%) SoilGrids 250m pixels have native masked SOC NaNs preserved explicitly. |
| `VAL_10_LEAKAGE_CONTROLS` | Leakage Risks | `cf_2017_2020_blocked=True` | **PASS** | Explicit guards attached for Crop Frequency look-ahead, contemporaneous VI target leakage, and S2 seasonal monthly aggregation. |
| `VAL_11_SCALE_MISMATCH_GOVERNANCE` | Scale Governance | `coarse_tags_present=True` | **PASS** | NASA POWER (~55-111km), SMAP (11km), GPM (9.6km) retained strictly with regional/macro context tags. |
| `VAL_12_DEFERRED_S2_SPATIAL_RASTERS` | Multi-Year S2 Rasters | `RESTRICTED_MODE_DEFERRED (2024-03 snapshot only on disk)` | **CHECK** | Wilaya-monthly integrated table is COMPLETE (107 eligible mo); Commune/250m Sentinel-2 multi-year columns await GEE quota reset. |

---

## 4. Remaining Limitations & Readiness Recommendation

- **Remaining Scientific & Technical Limitations:**
  1. **No monthly GPM / SMAP files locally:** Sub-seasonal water-balance features rely on NASA POWER daily/monthly `PRECTOTCORR` at the monthly tier and `GPM`/`SMAP` at the seasonal tier (`DJF/MAM/JJA/SON`).
  2. **Multi-year Sentinel-2 `10 m`/`20 m` GeoTIFFs deferred by GEE `restricted mode`:** Sub-Wilaya (`34` Communes & `250 m`) multi-year Sentinel-2 columns (`2017–2025`) are not yet populated spatially; only the March 2024 `10 m`/`20 m` snapshot is available pixel-wise on disk.
  3. **SoilGrids Nitrogen (`N > SOC` subsoil anomaly):** Kept strictly unvalidated for traceability; exclude from quantitative soil scoring.
  4. **Coarse macro-climate homogeneity across Communes:** `NASA POWER (2 RE / 5 AG cells)` & `SMAP/GPM (11 km)` share broad spatial footprints across adjacent communes.
- **Readiness Verdict:**
  - **READY NOW** for exploratory **Wilaya-scale monthly/seasonal hydro-climatic & phenology modeling** (`2017-02..2025-12`, `107` complete months) AND **`34`-Commune / `250 m` MODIS + SoilGrids + GPM/SMAP multi-year (`2016–2025`) modeling**.
  - **DEFER fine `10 m`/`20 m` multi-year Sentinel-2 commune/field modeling** until GEE quota resets and Priority 1–3 Sentinel-2 GeoTIFF exports resume.
