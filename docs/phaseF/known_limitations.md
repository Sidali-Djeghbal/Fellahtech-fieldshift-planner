# Field Shift — Known Data, Spatial & Methodological Limitations (Phase F Audit)

> **Scope:** Authoritative registry of verified data gaps, scale mismatches, excluded variables, and scientific constraints discovered across Phases A–F for the Field Profile pipeline (`field_input_schema.json`, `field_geospatial_processor.py`, `field_profile_builder.py`). These constraints **must** remain visible to downstream modeling and end-users; no missing value may be silently replaced with an unverified guess.

---

## 1. Spatial Resolution & Support-Size Disparity

| Dataset Layer | Native Support Size | Parcel Area Comparison (e.g., `4.0 ha` Field) | Scientific Impact & Modeling Safeguard |
|---|---|---|---|
| **Sentinel-2 (March 2024 snapshot)** | `10 m` (`0.01 ha`: NDVI/EVI) / `20 m` (`0.04 ha`: NDMI/NDRE) | True sub-field resolution (`~437` valid `10 m` pixels in `4.0 ha`). | Temporally restricted to a **single March 2024 snapshot**; multi-year `10 m`/`20 m` Sentinel-2 composites were deferred under Earth Engine Restricted Mode. |
| **ESA Crop Frequency (aligned)** | `10 m` (`0.01 ha`), `2021–2025` only | True sub-field pixel alignment to Sentinel-2 `10 m` grid. | Valid strictly for `2021–2025`; **blocked** from `2017–2020` historical crop attribution. |
| **SoilGrids 2.0 V6 & USDA Texture** | `250 m` (`6.25 ha` pixel) | Larger than small smallholder plots (`< 6.25 ha`), typically `1–4` cells intersected. | Global digital soil mapping model (`MODELED_SPATIAL_ESTIMATE`), **NOT laboratory soil sample data**. Does not capture parcel-level salinity (`ECe`), extractable P/K, or historical manure/liming heterogeneity. |
| **MODIS MOD13Q1 Seasonal** | `250 m` (`6.25 ha` pixel) | Often mixes target field with neighboring plots, tree rows, or bare soil roads. | Local archive holds **seasonal composites (`2016–2025`) only**; 16-day phenological trajectories are unavailable locally. |
| **GPM IMERG & SMAP L4 (aligned)** | `11 km` grid (`12,100 ha` cell) | Over `3,000×` larger than a `4 ha` plot; identical macro cell across nearby fields. | Macro hydro-climate background only; no monthly GPM/SMAP rasters on disk; SMAP `11 km` root-zone moisture cannot reflect plot-level drip or sprinkler irrigation. |
| **NASA POWER AG / RE** | `0.5° × 0.625°` (`~55–69 km` MERRA-2) / `1.0°` (`~111 km` CERES) | Wilaya-scale cells (`~1–4` cells intersect entire Wilaya / plot centroid). | Resolves regional gradients (`Tamlouka` ~`508 mm/yr` vs northern plain ~`737 mm/yr`) but misses valley frost pockets, windbreaks, and convective storm spatial variability. |

---

## 2. Temporally & Spatially Missing or Quarantined Variables

1. **Terrain / Topographic DEM (`dem_elevation_m`, `dem_slope_pct`):**
   - **Status:** `UNAVAILABLE_NOT_INTEGRATED` (`value = null`).
   - **Impact:** Local drainage ponding risk for heavy clay soils (`>= 32%` clay) cannot be computed geospatially yet. Safeguard: the builder asks a simple qualitative puddling question (`Q_DRAINAGE_QUALITATIVE`) when drainage-sensitive crops (`Lentil`, `Chickpea`, `Potato`) are targeted rather than forcing farmers to estimate `% slope`.
2. **Multi-Year Field-Scale Sentinel-2 Rasters (`2017–2025`):**
   - **Status:** Deferred (`REGIONAL_FALLBACK_ONLY` via `wilaya_monthly_panel_2016_2025.csv`, `2017-01` excluded due to `1.42%` coverage).
   - **Impact:** Cannot derive parcel-level historical NDVI anomalies across `2017–2025` locally; only `2024-03` spatial GeoTIFFs and Wilaya monthly climatologies exist.
3. **SoilGrids Total Nitrogen (`nitrogen_0_30cm`):**
   - **Status:** `UNVALIDATED_EXCLUDED` (`value = null`).
   - **Reason:** Phase D QA audit identified a physical inversion anomaly (`N > SOC` in subsoil layers). Strictly excluded from agronomic inference while preserved in schema for traceability.
4. **SoilGrids SOC `NaN` Anomaly (`100` Pixels) & Urban/Water Masked Pixels (`45,912` Pixels):**
   - **Empirical Audit Result:** `45,912` of `104,962` (`286 × 367`) grid pixels in `guelma_soilgrids_42bands_250m_V6_MERGED.tif` are urban/water masked (`NaN`; matched identically by `USDA == 0`), and **`100` pixels** inside Guelma (e.g., `UTM 348375.0, 4057375.0` in Bouati Mahmoud) have valid Clay (`34.45%`) while `SOC` is `NaN` (`UNAVAILABLE_MASKED_PIXEL`). The pipeline preserves `soc_0_30cm.value = null` cleanly without fabricating replacements.
5. **Unobserved Field Chemistry & Water Salinity (`ECe`, Available `P`/`K`, Soil Depth to Bedrock):**
   - Not present in any integrated spatial layer. Irrigated parcels trigger advisory reminder `Q_IRRIGATION_SALINITY_SIGN` based on regional Seybouse salinity evidence without halting planning.

---

## 3. Cross-Dataset Cadence & Bias Divergences Preserved Explicitly

1. **Precipitation Product Spread (`GPM` vs `NASA POWER`):**
   - `NASA POWER` averages **`+132 mm/yr` wetter** regionally than `GPM` across Guelma (`~736.84 mm/yr` vs `~587.56 mm/yr` in Boumahra Ahmed; `508.07 mm/yr` vs `440.13 mm/yr` in Tamlouka). Both bounds are preserved via `CON_06_PRECIP` so water-balance rules do not rely optimistically on a single uncalibrated product.
2. **Hydrologic Year vs. Calendar Year Annual Sums (`GPM`):**
   - `gpm_seasonal_11km_canonical.csv` sums hydrologic **`DJF + MAM + JJA + SON` (`Dec Y-1 .. Nov Y`)**, yielding a 10-yr Guelma mean of `545.48 mm/yr`, whereas calendar `Jan..Dec` (`gpm_annual_wilaya_canonical.csv`) averages `557.00 mm/yr` (~`2%` 10-yr offset, individual years up to `-131.9 mm` / `+90.0 mm` when December rain shifts year boundaries). Provenance metadata in `field_geospatial_processor.py` explicitly labels `gpm_annual_precip_2016_2025_mean_mm` as `"2016-2025 hydrologic annual sum (DJF+MAM+JJA+SON across Dec Y-1..Nov Y)"`.
3. **Meteorological Winter Alignment (`NASA POWER`):**
   - `nasa_power_daily_cell_values.csv` labels daily `year` by calendar date (`2016-12-01` has `year=2016, season=Winter`). Phase F corrected `_extract_nasa_power()` to group seasonal metrics by meteorological **`season_year` (`month == 12 ? year + 1 : year`)** and drop incomplete boundary winters (`Winter 2016` ~59 days, `Winter 2026` 31 days), averaging over the `9` complete contiguous `DJF` winters (`2017–2025`).

---

## 4. Farmer Input Contract Boundaries

- Farmers are **never** asked for soil pH, clay %, SOC, weather numbers, NDVI, slope degrees, or quality flags.
- Optional farmer arrays (`crop_history`, `target_crop_ids`, `excluded_crop_ids`, `equipment_constraints`) and weights (`forage_value_weight`, etc.) distinguish **`null` / omitted (`NOT_PROVIDED`)** from **`[]` (`EXPLICITLY_CONFIRMED_EMPTY`)** or **`0.0` (`PROVIDED`)** via `input_completeness_flags`. Future rotation optimization (Phase G+) **must** inspect `input_completeness_flags` before applying default assumptions about livestock forage needs or machinery availability.
