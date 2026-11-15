# Decision Unit Assessment — Field Shift (Guelma Wilaya)

**Phase:** E (Architecture & Spatial Scale Governance)

---

## 1. Empirical Scale Audit of Available Project Data

To prevent scale-mismatch fallacies (ecological fallacy at coarse units or false precision at fine pixels), every candidate decision unit must be judged strictly against **verified native resolutions currently on disk**:

| Dataset | Native Resolution on Disk | Local Temporal Availability | Effective Independent Degrees of Freedom Across Guelma (`3,683 km²`) |
|---|---|---|---|
| **NASA POWER (`AG` & `RE`)** | `0.5° × 0.625°` (`~55–69 km`) & `1.0°` (`~111 km`) | Daily, Monthly, Seasonal, Annual (`2016–2025`) | **Low (`5` AG cells, `2` RE cells — 1 RE cell covers `98.15%`)** |
| **SMAP L4 Soil Moisture** | `11,000 m × 11,000 m` | Seasonal (`DJF/MAM/JJA/SON`) & Annual (`2016–2025`) **ONLY** | **Moderate-Low (`45` valid cells)** |
| **GPM IMERG Precipitation** | `~9,634 m` (aligned `11,000 m`) | Seasonal & Annual (`2016–2025`) **ONLY** | **Moderate (`61` GPM / `45` aligned cells)** |
| **SoilGrids 2.0 `V6_MERGED`** | `250 m × 250 m` | Static (`6` depths, `0–200 cm`) | **High (`59,050` pixels)**; urban-masked in Guelma core (`75.18%` valid), `95.68–100%` in 33 communes |
| **MODIS `MOD13Q1`** | `250 m × 250 m` | Seasonal & Annual (`2016–2025`) | **High (`59,737` pixels)** |
| **ESA Crop Frequency** | `10 m × 10 m` (snapped to S2 grid) | Static `2021–2025` fraction | **Very High (`36.85M` valid px)** |
| **Sentinel-2 Monthly Stats / Raster** | `10 m`/`20 m` -> **Wilaya tables only** + single `2024-03` GeoTIFF | Monthly regional (`2017–2025`, `107` eligible); spatial raster `2024-03` only | **Temporal only (`1` regional unit)**; multi-year spatial GeoTIFFs deferred in GEE |
| **Parcel Boundaries / Crop History** | **NOT AVAILABLE ON DISK** | None | `0` parcels |

---

## 2. Systematic Evaluation of Candidate Decision Units

| Candidate Unit | Physical Size | Data Readiness Today | Agronomic & Institutional Relevance | Critical Failure Modes / Limitations |
|---|---|---|---|---|
| **A. Wilaya (`1` Unit)** | `3,683.23 km²` | `100%` ready (monthly S2 + daily/seasonal climate + hydro) | Useful only for Wilaya-level drought early warning & macro phenology tracking. | **Agronomically too coarse for rotation decisions:** collapses `436 mm` semi-arid `Tamlouka` and `607 mm` sub-humid `Ain Ben Beida`, mixes irrigated valley (`Boumahra Ahmed`) with mountain olive hills (`Bouchekouf`), and cannot rank localized soil constraints. |
| **B. Commune (`34` Units) — Cropland-Masked** | `36.2–317.4 km²` (`34` GADM 4.1 units) | **`100%` integrated (`1,360` seasonal rows + `34` static profiles)**; aligns naturally with `11 km` GPM/SMAP cells and `250 m` SoilGrids/MODIS summaries (`95.68–100%` rural soil coverage) | **Direct operational alignment:** corresponds to Algerian administrative/extension delivery (`DSA` subdivision statistics, commune agricultural extension bureaus, Bouhamdane dam sector allocations) and captures real inter-commune rainfall (`436–607 mm`), `SOC` (`13.6–24.1 g/kg`), and cropland share (`13.5–83.3%`) gradients. | Intra-commune heterogeneity exists (e.g., alluvial valley floor vs. sloping foothills inside `Hammam Debagh` or `Bou Hamdane`); cannot see individual farmer water contracts or parcel drainage without local survey inputs. |
| **C. Landscape Cell (`250 m` Cropland-Filtered)** | `6.25 ha` (`250×250 m`); `19,553` pixels at `crop_freq >= 0.5` | Ready locally for **static soil (`0–30 / 30–100 cm`) + MODIS seasonal (`2016–2025`) + Crop Frequency** | Captures sub-commune edaphic heterogeneity (e.g., Loam vs Clay pockets, local SOC hot spots, greenness anomalies) and forms the natural gridded backbone for future GEE Sentinel-2 (`250 m` zonal or `10–20 m` sub-tile) expansion. | **Severe hydro-climate scale gap:** assigns the same `11 km` GPM/SMAP cell (~1,936 `250 m` px/cell) and `55–111 km` NASA POWER temperature to adjacent cells; SoilGrids `250 m` is a modeled interpolation, not parcel soil tests; **risk of false precision** if presented to farmers as plot-specific prescription. |
| **D. Agricultural Parcel / Field (`~0.5–10 ha`)** | Actual plot polygon | **UNSUPPORTED TODAY:** zero parcel boundaries, zero multi-year `10 m` Sentinel-2 time series on disk, zero plot soil/irrigation/history records | True farmer decision level where real crop sequence, weed carryover, irrigation pipe access, and tillage occur. | **Scientifically indefensible right now:** claiming field-level accuracy without field boundaries, parcel histories, or multi-year `10 m` imagery violates core spatial-statistics principles. |

---

## 3. Recommended Decision Unit Architecture

Field Shift MUST adopt an explicit **Two-Tier Decision Hierarchy** rather than claiming field-level precision:

1. **Primary Decision & Advisory Unit (Phase F MVP): Cropland-Masked Commune Zone (`34` Communes)**
   - **Definition:** Each of Guelma's `34` communes restricted to its `ESA Crop Frequency >= 0.5` (`2021–2025`) agricultural footprint for soil/vegetation priors (`crop_mask_commune` summary alongside whole-commune stats), paired with area-weighted `GPM (11 km)`, `SMAP (11 km)`, and `NASA POWER` seasonal climate series.
   - **Why Scientifically Defensible Now:**
     1. Zero fake spatial upsampling — `34` communes (`36–317 km²`) match the physical footprints of `11 km` GPM/SMAP cells (`121 km²`) far more honestly than `250 m` (`0.0625 km²`) pixels.
     2. Directly maps to local agricultural governance (**DSA Guelma** campaign planning, **ITGC** extension zones, and the **Guelma–Bouchegouf** irrigated corridor).
     3. Supports transparent **within-commune soil dispersion reporting** (`p05–p50–p95` across `250 m` cropland pixels inside each commune) so users know whether a commune is uniform or spans lighter/heavier soils.

2. **Secondary Spatial Screening & Visualization Unit: `250 m` Cropland-Filtered Landscape Cell (`19,553` pixels)**
   - **Strict Role:** Used **solely for static soil screening (`SoilGrids 250 m`), multi-year MODIS phenological clustering (`2016–2025`), and within-commune spatial risk mapping**, with an explicit UI/API metadata tag: `COARSER_HYDROCLIMATE_SUPPORT_11KM_TO_111KM — SCREENING_ONLY_NOT_PARCEL_PRESCRIPTION`.
   - **Upgrade Path:** When Earth Engine quota resets and Priority 1–3 multi-year `10 m`/`20 m` Sentinel-2 composites are exported (plus SRTM DEM + ESA WorldCover + local plot survey), the same constraint engine can accept **user-drawn/verified parcel coordinates (`lat/lon`) + farmer questionnaire inputs** (soil texture feel/lab report, drainage, actual irrigation type, previous 2–3 crops) to execute **parcel-conditioned decision support** *explicitly anchored on farmer-supplied plot facts rather than inferred coarse pixels*.
