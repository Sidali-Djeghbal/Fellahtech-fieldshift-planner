# Data Gaps & Phased Collection Plan — Field Shift (Guelma Wilaya)

**Goal:** Prioritize missing agronomic, institutional, and remote-sensing variables by **decision impact** and **realistic acquisition pathway**, separating zero-cost local improvements from institutional partnerships and field surveys.

---

## 1. Critical Data Gaps Ranked by Modeling Priority

| Priority | Missing Variable / Dataset | Current Local State | Why It Blocks High-Confidence Decisions | Realistic Collection Method | Target Phase |
|---|---|---|---|---|---|
| **P1 (Critical)** | **Irrigated Perimeter Boundaries & Dam Water Quotas** (`Guelma–Bouchegouf` sectors, boreholes, `ECw` salinity) | Absent locally (only qualitative literature citations) | Cannot distinguish rainfed vs. irrigated fields automatically; cannot gate `Processing Tomato` or `Potato` without runtime user declaration or warn accurately on drought-year rationing. | Formal request to **DSA Guelma**, **ONID** (Office National de l'Irrigation et du Drainage), and **ABH Constantinois–Seybouse–Mellegue**; fallback: mandatory user runtime toggle. | **Pre-MVP / Field Pilot** |
| **P1 (Critical)** | **Commune-Level Historical Crop Areas & Campaign Yields** (`Durum wheat`, `Barley`, `Faba bean`, `Chickpea`, `Lentil`, `Tomato`, `Forage`) | Absent locally (`Guelma_Annual_Seasonal_Crop_Analysis.csv` is ONLY an `NDVI > 0.4` greenness mask) | Needed to validate Commune plausibility (e.g., verify `Tamlouka` fallow hypothesis vs. cereal dominance) and calibrate local $K_y$/water-productivity benchmarks. | Annual campaign spreadsheets from **DSA Guelma / MADR** (`2016–2025` aggregated by commune/daïra). | **Validation Stage** |
| **P1 (Critical)** | **Local Rain-Gauge & Weather Station Records** (`Tmin`, `Tmax`, `Precip`, wind `U2M`) | Absent locally (`NASA POWER` exceeds `GPM` by **`+132 mm/yr`**; wind `WS2M` missing) | Essential to bias-correct `NASA POWER` vs. `GPM` rainfall divergence and validate interior frost risk (`Tamlouka`, `Ain Makhlouf`). | **ONM** (Office National de la Météorologie — Belkheir/Guelma station) & **ANRH** / DSA rainfall station time series (`2016–2025`). | **Pre-Deployment Calibration** |
| **P2 (High)** | **Topographic Slope, Aspect & Drainage Index (DEM `30 m`)** | Absent locally | Heavy Clay Loams (`96.95%`) behave completely differently on flat flood-prone Seybouse alluvial bottoms (waterlogging risk for Chickpea/Lentil/Olive) vs. `>8%` slopes (erosion risk under winter Bare Fallow). | Free open download & local processing of **SRTMGL1 / Copernicus GLO-30 DEM** (`30 m`) -> derive slope %, Topographic Wetness Index (`TWI`) aggregated cleanly to `250 m` & Communes. | **Phase F Quick Win** (No GEE needed) |
| **P2 (High)** | **Perennial / Orchard / Urban / Forest Mask (`10 m`)** | Absent locally (only `ESA Crop Frequency` cropland intensity) | Prevents accidentally applying annual crop rotation advice to olive groves, forests, or peri-urban zones (`Guelma`, `Bouchekouf`, `Roknia`). | Download free **ESA WorldCover (`10 m`, 2021)** tiles locally + verify against `CropFreq >= 0.5` and DSA tree-crop census. | **Phase F Quick Win** |
| **P2 (High)** | **Soil Laboratory Measurements (`ECe`, `CaCO₃`, Olsen-`P`, Exch. `K`, Mineral `N`, `Depth`)** | Absent locally (`SoilGrids N` is unvalidated & excluded; zero salinity/P/K/depth layers) | Essential for irrigated `ECe` secondary salinization safety, calcareous P fixation/iron chlorosis management, and calibrating SoilGrids `SOC/pH` bias. | Archived lab test records from **ITGC Constantine / Guelma**, **INRAA**, or local private soil labs, plus a small targeted `30–50` stratified soil-sample validation campaign across valley vs. dry plain communes. | **Validation & Pilot** |
| **P3 (Medium)** | **Participatory Farmer Constraints & Parcel Sequence Histories** (`T-2`, `T-1`, livestock need, tenure, tillage window) | Absent locally | Short-term rental leases (e.g., tomato renters), sheep stubble-grazing value (Vetch-Oat vs. fallow), and Ascochyta-resistant seed availability often drive real adoption more than pure water math. | Short **15–20 minute structured survey** with `30–60` representative farmers across 3 strata (Irrigated Valley, Semi-Arid Plain, Piedmont) + interactive intake form in prototype. | **Pilot Co-Design** |
| **P3 (Deferred)** | **Multi-Year Sentinel-2 `10 m`/`20 m` Seasonal GeoTIFFs + Monthly GPM/SMAP** | Deferred due to GEE Restricted Mode; zero monthly GPM/SMAP on disk | Enables intra-commune `250 m`/sub-commune seasonal vegetation/water-stress anomaly tracking (`NDMI` drought response) without claiming parcel boundaries. | Resume Phase C Priority 1–3 GEE exports once noncommercial quota resets; keep Phase F runnable entirely from existing local data. | **Post-Quota Upgrade** |

---

## 2. Explicit Collection Guardrails

1. **Do NOT synthesize DSA yields** or treat `Guelma_Annual_Seasonal_Crop_Analysis.csv` (`NDVI > 0.4` regional area) as planted crop hectares.
2. **Do NOT substitute `soil_nitrogen_0_30cm_unvalidated`** for field mineral soil nitrogen measurements.
3. **Do NOT infer parcel irrigation automatically from summer NDVI** (perennials, orchards, and riparian vegetation remain green in JJA).
4. **Do NOT submit GEE tasks during Phase E** — Phase F research prototyping remains fully executable locally from `data/INTEGRATED/`.
