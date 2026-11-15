# Phase F — Field Profile Scientific & Geospatial Audit Report

**Project:** Field Shift — Crop Rotation Decision-Support System (Guelma Wilaya, Algeria)  
**Scope:** Scientific, geospatial, schema-contract, and provenance audit of [field_input_schema.json](file:///home/lokman/Desktop/FeildShit-SI-Model/field_input_schema.json), [field_geospatial_processor.py](file:///home/lokman/Desktop/FeildShit-SI-Model/field_geospatial_processor.py), and [field_profile_builder.py](file:///home/lokman/Desktop/FeildShit-SI-Model/field_profile_builder.py) prior to implementing the Phase G Crop Rotation Decision Engine.  
**Constraints Respected:** Phases A–E untouched; zero Earth Engine jobs submitted; zero crop rotation optimization implemented; no missing values fabricated; optional farmer inputs strictly distinguish `null` / omitted (`NOT_PROVIDED`) from `[]` (`EXPLICITLY_CONFIRMED_EMPTY`).

---

## 1. Executive Verdict Summary by Audit Category

| # | Audit Category | Verdict | Evidence & Key Verification Result |
|---|---|---|---|
| 1 | **Minimal Farmer Input Contract** | **PASS** | Corrected [field_input_schema.json](file:///home/lokman/Desktop/FeildShit-SI-Model/field_input_schema.json) & [field_profile_builder.py](file:///home/lokman/Desktop/FeildShit-SI-Model/field_profile_builder.py) so `crop_history`, `preferences`, forage weight, and equipment constraints are genuinely optional; `input_completeness_flags` preserves `NOT_PROVIDED` (`null`/omitted) strictly separate from `EXPLICITLY_CONFIRMED_EMPTY` (`[]`) and `PROVIDED` (`0.0`). Technical soil/weather/RS/quality keys remain recursively forbidden (`FarmerInputValidationError`). |
| 2 | **Coordinate Systems, Polygon Validation & Area Math** | **PASS** | Hardened `validate_and_project_polygon()` to strictly reject bowties, self-intersections, degenerate collinear rings, and `MultiPolygon` inputs rather than calling `make_valid` or silently dropping sub-polygons. Verified cross-CRS parity across `EPSG:4326`, `EPSG:3857`, and `EPSG:32632` (`area_ha`, SoilGrids, Sentinel-2 `10 m`). Verified partial Wilaya overlap warnings (`52.64%` Roknia border parcel) and `0%` out-of-Wilaya rejection. |
| 3 | **Area-Weighted Raster Extraction & Alignment** | **PASS** | Independently cross-verified `s2_2024_03_ndvi_10m` (`0.5277`) against a standalone `rasterio` + `shapely` pixel-intersection loop (`test_10`). Verified `SoilGrids V6` (`250 m`) physical sums (`clay+sand+silt` ~`100%`), `USDA` texture class equivalence (`valid == (USDA > 0)`), and `S2` valid-obs mask parity (`10 m` & `20 m`). Added `shapely.prepared.prep` fast interior path + precomputed `250 m` weight caching across `40` MODIS extractions and `12` SoilGrids extractions (`1,073.52 ha` / `108,028` `10 m` pixels extracted in `6.39 s`). |
| 4 | **Seasonal & Hydrologic Time Alignment** | **PASS** | Audited and fixed a critical meteorological bug in `_extract_nasa_power()`: `nasa_power_daily_cell_values.csv` assigns calendar `year` to `month == 12` (`2016-12-01` had `year=2016, season="Winter"`). Updated `_extract_nasa_power()` to group seasonal averages by **`season_year = np.where(month == 12, year + 1, year)`** and filter complete winters (`>= 80` days, excluding partial `Winter 2016` and `Winter 2026`, averaging over the `9` complete `DJF` winters `2017–2025`). Documented GPM hydrologic annual sum (`Dec Y-1..Nov Y`, `545.48 mm/yr`) vs calendar mean (`557.00 mm/yr`) directly in metric metadata. |
| 5 | **NoData, Masked Pixels & Missing Dataset Resilience** | **PASS** | Verified `45,912` masked `NaN` SoilGrids pixels (e.g., water/urban `1.0 ha` box in Bouati Mahmoud, `NDVI = -0.634`) yield `value=None` and `UNAVAILABLE_MASKED_PIXEL` across `13` soil metrics; `100` `Clay-valid / SOC-NaN` pixels (e.g., `34.45%` clay while `SOC=None`) transition only `soc_0_30cm` and `soc_30_100cm` to `UNAVAILABLE_MASKED_PIXEL`. Missing local files (SoilGrids/MODIS/CropFreq/S2/GPM/SMAP/NASA POWER) degrade gracefully to complete schema keys tagged `UNAVAILABLE_NOT_INTEGRATED`. |
| 6 | **Data Quality Provenance & Regional Fallback Separation** | **PASS** | Across `245` audited metric records (`49` per profile × `5` diverse test cases in [data_quality_audit.csv](file:///home/lokman/Desktop/FeildShit-SI-Model/docs/phaseF/data_quality_audit.csv)), all `MOD13Q1`/`GPM`/`CropFreq`/`S2 2024-03` metrics carry `REMOTE_SENSING_DERIVED`, `SoilGrids`/`SMAP`/`NASA POWER` carry `MODELED_SPATIAL_ESTIMATE`, `DEM` stays `UNAVAILABLE_NOT_INTEGRATED`, `Nitrogen` stays `UNVALIDATED_EXCLUDED` (`null`), and multi-year Wilaya S2 climatology stays `REGIONAL_FALLBACK_ONLY`. `USER_REPORTED` count updates truthfully (`3` minimal vs `5` full payload). |
| 7 | **Empirical Spatial Gradient & Regression Suite** | **PASS** | Verified realistic agro-climatic north-south discrimination (`Boumahra Ahmed`: GPM `587.56 mm/yr`, NASA POWER `736.84 mm/yr`, S2 NDVI `0.5277` vs semi-arid `Tamlouka`: GPM `440.13 mm/yr`, NASA POWER `508.07 mm/yr`, S2 NDVI `0.3889`). Full automated test suite (`test_phaseD_integration.py`, `test_field_profile.py`, `test_phaseF_audit.py`) passes **`20/20` tests in `51.249 s` (`OK`)**. |

---

## 2. Five Concrete Defects Found & Fixed During Phase F

1. **Contract Mismatch on Optional Preferences & History ([field_profile_builder.py](file:///home/lokman/Desktop/FeildShit-SI-Model/field_profile_builder.py)):**  
   `validate_farmer_input()` still rejected omitted or `null` `crop_history` and required all `8` subfields of `preferences` non-null. Rebuilt validation with `_classify_list_input()` and `_classify_weight_input()` to preserve `NOT_PROVIDED` (`null`/omitted), `EXPLICITLY_CONFIRMED_EMPTY` (`[]`), and `PROVIDED` (`0.0` or non-empty lists) explicitly inside `input_completeness_flags`, updating `USER_REPORTED` ledger counts dynamically (`3`–`5`).
2. **Permissive Geometry Auto-Repair ([field_geospatial_processor.py](file:///home/lokman/Desktop/FeildShit-SI-Model/field_geospatial_processor.py)):**  
   `validate_and_project_polygon()` previously ran `make_valid` and kept the largest sub-polygon when encountering `MultiPolygon` or bowtie geometries. Replaced with strict validation rejecting invalid, self-intersecting, collinear, or `MultiPolygon` geometries immediately on both raw and projected `EPSG:32632` geometries.
3. **NASA POWER Winter Calendar-Year Mixing ([field_geospatial_processor.py](file:///home/lokman/Desktop/FeildShit-SI-Model/field_geospatial_processor.py)):**  
   `_extract_nasa_power()` previously grouped `"Winter"` by calendar `year`, combining `Jan–Feb Y` with `Dec Y` (two disconnected winters) and averaging partial boundary winters (`Winter 2016`, `Winter 2026`). Updated to meteorological `season_year = np.where(month == 12, year + 1, year)` with `>= 80`-day season completeness filtering (`Winter 2017–2025`, `Boumahra Winter PRECTOTCORR = 258.45 mm/season`).
4. **Windowed Extraction Performance Bottleneck ([field_geospatial_processor.py](file:///home/lokman/Desktop/FeildShit-SI-Model/field_geospatial_processor.py)):**  
   Separated `_compute_window_area_weights()` using `shapely.prepared.prep(geom_utm)` + `contains_properly()` fast interior pixel checks, plus grid caching across `40` MODIS seasonal extractions (`250 m`) and `12` SoilGrids property/depth extractions (`250 m`). Benchmark on `LARGE_1200HA_PLAIN` (`1,073.52 ha`, `108,028` valid `10 m` Sentinel-2 pixels) completed end-to-end in `6.39 s`.
5. **Missing-File & Masked-Pixel Schema Gaps ([field_geospatial_processor.py](file:///home/lokman/Desktop/FeildShit-SI-Model/field_geospatial_processor.py)):**  
   Eliminated key-dropping degradation when `SOILGRIDS_V6_ZIP`, `SOILGRIDS_USDA_TIF`, `WILAYA_MONTHLY_CSV`, `MODIS`, `GPM/SMAP`, or `NASA POWER` assets are absent, returning full schema-consistent `UNAVAILABLE_NOT_INTEGRATED` dicts; aligned `_extract_crop_frequency()` and `_extract_sentinel2()` so zero-valid-pixel masks report `UNAVAILABLE_MASKED_PIXEL`.

---

## 3. Multi-Scenario Empirical Audit Results ([spatial_extraction_audit.csv](file:///home/lokman/Desktop/FeildShit-SI-Model/docs/phaseF/spatial_extraction_audit.csv))

| `test_case_id` | Area (ha) | Wilaya % | Primary Commune | Time (ms) | Clay 0–30 (%) | SOC 0–30 (g/kg) | CropFreq | S2 NDVI 10m | GPM (mm/yr) | NASA POWER (mm/yr) |
|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|
| `TINY_02HA_BOUMAHRA` | `0.1988` | `100.0` | Boumahra Ahmed | `6036.8`* | `33.0333` | `12.8833` | `0.9931` | `0.7908` | `587.56` | `736.84` |
| `MED_04HA_BOUMAHRA` | `3.9768` | `100.0` | Boumahra Ahmed | `3219.9` | `33.0333` | `12.8833` | `0.9479` | `0.5277` | `587.56` | `736.84` |
| `LARGE_1200HA_PLAIN` | `1073.5183` | `100.0` | Helliopolis | `6394.1` | `35.3697` | `15.5220` | `0.6651` | `0.6716` | `587.57` | `736.84` |
| `DRY_SOUTH_TAMLOUKA` | `8.8978` | `100.0` | Tamlouka | `3038.7` | `29.7904` | `13.2208` | `0.4255` | `0.3889` | `440.13` | `508.07` |
| `WET_NORTH_BOUCHEKOUF` | `8.8590` | `100.0` | Djebala El Khemissi | `3010.6` | `33.4344` | `16.8556` | `0.8803` | `0.6218` | `566.28` | `736.84` |
| `BORDER_STRADDLE` | `25.0000` | `52.6415` | Roknia (`1` warning) | `3022.7` | `36.5611` (`63.5%`) | `17.8819` | `0.4434` (`53.32%`) | `0.6910` | `612.22` | `736.84` |
| `SOILGRIDS_URBAN_MASKED` | `1.0000` | `100.0` | Bouati Mahmoud | `3083.0` | `null` (`0%` cov) | `null` | `0.0000` | `-0.6340` | `611.43` | `736.84` |
| `SOILGRIDS_SOC_NAN` | `2.5600` | `100.0` | Bouati Mahmoud | `2957.9` | `34.4500` | `null` (`MASKED`) | `0.6163` | `0.5448` | `611.43` | `736.84` |

*\*Includes one-time `@lru_cache` boundary/CSV warmup on first call (`~3 s` warm runtime afterward).*

---

## 4. Verification & Readiness for Phase G

- **Full Test Run:** `PYTHONPATH=. /home/lokman/Desktop/FeildShit-SI-Model/venv/bin/python -m unittest discover -s tests -v` -> **`Ran 20 tests in 51.249s` — `OK`** (`5` Phase D tests + `5` Field Profile contract tests + `10` Phase F audit tests; `0` failures, `0` skips).
- **Phase F Deliverables Written:**
  - [docs/phaseF/field_profile_scientific_audit.md](file:///home/lokman/Desktop/FeildShit-SI-Model/docs/phaseF/field_profile_scientific_audit.md)
  - [docs/phaseF/spatial_extraction_audit.csv](file:///home/lokman/Desktop/FeildShit-SI-Model/docs/phaseF/spatial_extraction_audit.csv)
  - [docs/phaseF/data_quality_audit.csv](file:///home/lokman/Desktop/FeildShit-SI-Model/docs/phaseF/data_quality_audit.csv)
  - [docs/phaseF/known_limitations.md](file:///home/lokman/Desktop/FeildShit-SI-Model/docs/phaseF/known_limitations.md)
  - [tests/test_phaseF_audit.py](file:///home/lokman/Desktop/FeildShit-SI-Model/tests/test_phaseF_audit.py)
- **Go / No-Go Verdict:** **GO FOR PHASE G** — The Farmer Input & Field Profile layer is scientifically calibrated, scale-transparent, fault-tolerant to missing files and masked pixels, deterministic, and strictly non-fabricating. Remaining external limits documented in [known_limitations.md](file:///home/lokman/Desktop/FeildShit-SI-Model/docs/phaseF/known_limitations.md) (`DEM`, lab `ECe`/`P`/`K`, multi-year field-scale Sentinel-2 rasters, and cross-product GPM/NASA POWER precip spread) must be consumed explicitly as uncertainty bounds by the future Phase G Crop Rotation Engine.
