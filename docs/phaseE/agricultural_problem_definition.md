# Agricultural Decision Problem Definition — Field Shift (Guelma Wilaya, Algeria)

**Phase:** E (Research & Architectural Design — No Model Training or Scoring Implemented)  
**Target Region:** Guelma Wilaya, Northeastern Algeria (`3,683.2311 km²`, `34` Communes, `EPSG:32632`)  
**Prepared:** `2026-11-15`

---

## 1. Phase A–D Data Foundation Audit (Verified Against Disk)

Before defining the agricultural problem, all integrated and auxiliary project datasets under [data/](file:///home/lokman/Desktop/FeildShit-SI-Model/data) were audited directly against actual schemas and file contents:

- **Verified Available Datasets (`data/INTEGRATED/`):**
  1. **Spatial Reference (`EPSG:32632`):** `1` Wilaya boundary (`3,683.2311 km²`), `34` GADM 4.1 Communes (`36.23–317.35 km²`), `59,050` valid `250 m` landscape pixels (`286×367`), and `45` aligned `11 km` hydro-climate cells.
  2. **Climate (`NASA POWER AG & RE`, `2016–2025`):** Complete daily (`3,653` days), monthly (`120` months), and seasonal (`40` full DJF/MAM/JJA/SON rows in integrated panels; raw seasonal CSV also includes boundary-truncated `Winter 2026` as row 41) regional temperature (`T2M`, `T2M_MAX`, `T2M_MIN`), precipitation (`PRECTOTCORR`), relative humidity (`RH2M`), and solar radiation (`ALLSKY_SFC_SW_DWN`).
  3. **Precipitation (`GPM IMERG`) & Soil Moisture (`SMAP L4`, `2016–2025`):** Available locally at **Seasonal (`DJF/MAM/JJA/SON`) and Annual cadences ONLY** (`11 km` cell grid and commune area-weighted joins). **No monthly GPM or SMAP files exist on disk.**
  4. **Soil Properties (`SoilGrids 2.0 V6_MERGED`, `250 m`):** Depth-weighted `0–30 cm` and `30–100 cm` `clay`, `sand`, `silt`, `pH (H₂O)`, `SOC`, `CEC`, plus `6`-depth `USDA` texture classes (`59,050` valid pixels; `100` pixels have native masked `SOC` NaNs; raw `ESRI:54009` file verified empty and excluded; `Nitrogen` flagged `UNVALIDATED_TRACEABILITY_ONLY` due to `N > SOC` subsoil scaling anomaly).
  5. **Vegetation & Cropland Mask (`Sentinel-2`, `MODIS`, `ESA Crop Frequency`):**
     - `Sentinel-2`: `108` Wilaya monthly statistics (`2017-01..2025-12`, `107` model-eligible; `2017-01` excluded at `1.4173%` coverage) + single `2024-03` `10 m`/`20 m` snapshot. Multi-year `10 m`/`20 m` GeoTIFFs remain deferred due to Earth Engine Restricted Mode.
     - `MODIS MOD13Q1`: Seasonal (`DJF/MAM/JJA/SON`) & Annual (`2016–2025`) `250 m` stacks aligned identically to SoilGrids V6.
     - `ESA Crop Frequency`: `10 m` cropland fraction over `2021–2025`, origin-aligned to Sentinel-2 `10 m` ([guelma_crop_frequency_2021_2025_aligned_s2_10m.tif](file:///home/lokman/Desktop/FeildShit-SI-Model/data/INTEGRATED/spatial/guelma_crop_frequency_2021_2025_aligned_s2_10m.tif)); `19,553 / 59,050` (`33.11%`) `250 m` cells meet `crop_freq >= 0.5`.
- **Verified Auxiliary Table Audit Clarification:**
  - [Guelma_Annual_Seasonal_Crop_Analysis.csv](file:///home/lokman/Desktop/FeildShit-SI-Model/data/tables/Guelma_Annual_Seasonal_Crop_Analysis.csv) reports seasonal green area exceeding an `NDVI > 0.4` threshold (`116,791–205,468 ha` across 2021–2025). **This is a green vegetation cover mask (including forests, maquis, pastures, and orchards), NOT crop-type planted acreage.**
- **Verified Missing Ground Truths on Disk:** Zero crop-type maps, zero field/cadastral parcel boundaries, zero observed yields/rotations, zero DSA/MADR municipal crop statistics, zero mapped irrigation perimeter polygons, zero DEM/slope layers, and zero soil lab/salinity (`ECe`, `CaCO₃`, `P`, `K`) datasets exist locally.

---

## 2. Agro-Ecological Profile of Guelma Wilaya (Observed Metrics + Literature Context)

Guelma spans the middle Seybouse River basin and adjacent Tellian Atlas / northeastern High Plains transitions (`3,683.23 km²`). Combining verified local Phase D measurements with Algerian and Mediterranean agronomic literature reveals **three strongly contrasted agro-ecological zones**:

1. **Seybouse Alluvial Valley & Central Sub-Humid Plains** *(e.g., Boumahra Ahmed, Belkheir, Guelma, El Fedjoudj, Helliopolis, Ain Ben Beida, Bouati Mahmoud)*
   - **Observed Local Data:** Cropland share (`crop_freq >= 0.5`) reaches **`40.3%–83.3%`** (`Boumahra Ahmed = 83.34%`); `GPM` annual rainfall **`552–607 mm/yr`**; Clay Loam `0–30 cm` (`33.9%–35.6%` clay); near-neutral to slightly alkaline `pH 6.68–7.33`; depleted arable `SOC 16.33–20.63 g/kg`.
   - **Literature Context (DSA Guelma / Seybouse studies):** Hosts the **Guelma–Bouchegouf irrigated perimeter** (`~10,000 ha` nominal design across sectors from Guelma/El Fedjoudj/Boumahra to Bouchegouf, supplied primarily by the **Bouhamdane Dam** at Hammam Debagh). Intensively cropped with autumn/winter cereals plus high-value irrigated **processing tomato** (*tomate industrielle*) and market vegetables, characterized by short-term land-and-water lease dynamics. *(Exact active irrigated hectares per commune require DSA/ONID confirmation.)*

2. **Southern & Western Semi-Arid Cereal–Pulse Plains** *(e.g., Oued Zenati, Ain Rekada, Ain Makhlouf, Tamlouka, Ain Larbi, Selaoua Announa, Ras El Agba)*
   - **Observed Local Data:** High arable share in `Oued Zenati` (`65.58%`), `Ain Rekada` (`63.42%`), `Ain Makhlouf` (`60.54%`); markedly drier `GPM` rainfall (**`436.0 mm/yr` in Tamlouka**, `467.5–484.8 mm/yr` across `Ain Makhlouf–Oued Zenati`); cooler spring temperatures (`Tamlouka = 14.18 °C` vs. valley `15.35 °C`); slightly lighter clay loam (`29.98%–31.63%` clay), `pH 7.05–7.33`, and the **lowest arable `SOC` in the Wilaya (`13.58 g/kg` in Tamlouka; `16.24–18.30 g/kg` elsewhere)**.
   - **Hypothesized Note Requiring Ground Validation:** `Tamlouka` shows lower `crop_freq >= 0.5` (`30.27%`) despite wide arable plains — potentially reflecting traditional **biennial cereal–bare fallow** rotations (active crop detected `~2/5` years near the `0.5` cutoff) or mixed steppe/pasture margins. *This requires field/DSA verification before assuming fallow vs. rangeland.*

3. **Northern & Foothill Forest–Orchard Uplands** *(e.g., Bouchekouf, Nechemaya, Medjaz Sfa, Roknia, Bou Hamdane, Dahouara, Oued Cheham)*
   - **Observed Local Data:** Low annual cropland share (`13.53%–26.71%`), higher rainfall (`525–600 mm/yr` GPM), and high topsoil `SOC` (`21.97–24.08 g/kg`) reflecting permanent forest, maquis, and perennial olive/orchard cover.

---

## 3. Core Agricultural Systems, Seasonal Calendars, and Rotation Scope

### 3.1 Annual Agricultural Systems (Primary Scope for Field Shift Rotation Engine)
| System Category | Key Crops | Evidence Status | Typical Window (ITGC / ICARDA / Med.) |
|---|---|---|---|
| **Winter Cereals** | Durum wheat (*Triticum durum*), Bread/soft wheat (*T. aestivum*), Barley (*Hordeum vulgare*) | **Verified dominant staple** in Guelma & NE Algeria (FAO / ITGC / DSA reports) | **Plant:** Late Oct – Mid-Dec; **Peak Canopy:** Mar–Apr; **Harvest:** Jun–Jul |
| **Food Grain Legumes** | Faba bean (*Vicia faba*), Chickpea (*Cicer arietinum* — winter & spring cultivars), Lentil (*Lens culinaris*) | **Verified major rotation partners** (ITGC / ICARDA / Algerian pulse studies) | Faba & Winter Chickpea: **Nov–Dec** to **May–Jun**; Traditional Spring Chickpea: **Feb–Mar** to **Jun–Jul** |
| **Forage / Fallow-Replacement** | Vetch–Oat (*Vicia sativa + Avena sativa*), Forage barley / Berseem (*Trifolium alexandrinum* irrigated/wet lowlands) | **Verified ITGC / REFORMA practice** for replacing bare fallow (*jachère nue*) | **Nov–Dec** to **Apr–May** (cut hay/silage before seed set) |
| **Irrigated Cash & Horticultural** | Processing tomato (*Solanum lycopersicum*), Spring/Autumn potato (*S. tuberosum*) | **Verified Guelma–Bouchegouf hub** (processing tomato major DSA campaign crop); potato regional presence | Spring Tomato: **Mar–Apr** to **Jul–Sep**; Spring Potato: **Jan/Feb–May/Jun** |
| **Oilseed / Summer Rotational** | Rainfed/supplemental Sunflower (*Helianthus annuus*) or Sorghum | **Hypothesis / National diversification target** requiring local Guelma extension verification | **Apr** to **Aug–Sep** |

### 3.2 Perennial vs. Annual Systems (Explicit Separation Boundary)
- **Olive groves (*Olea europaea*)**, stone/citrus orchards, forest, and permanent pastures cover major hill and foothill communes (`Bouchekouf`, `Roknia`, `Bou Hamdane`, piedmont slopes).
- **Architectural Boundary:** Perennials are **NOT** annual rotation candidates. Replacing multi-decade olive orchards with wheat–chickpea sequences is agronomically invalid. Until a verified `10 m` perennial/orchard mask (e.g., ESA WorldCover + local inventory) is integrated, Phase E/F must treat **`ESA crop_freq >= 0.5`** as the primary *annual-rotation candidate domain* (recognizing `crop_freq` already filters against annual seasonal-cropland detections over 2021–2025, though sparse inter-cropped young orchards require explicit caution).

---

## 4. Verified Biophysical Constraints vs. Hypotheses Requiring Field Validation

| Domain | Verified Local Empirical Evidence (Phases A–D) | Authoritative Agronomic Implications | Unverified Hypotheses Requiring Ground Survey |
|---|---|---|---|
| **Soil Texture & Workability** | **`96.95%`** of Guelma `0–5 cm` pixels are **Clay Loam** (`30–35.6%` commune mean clay; up to `43.8%` pixel clay; `4.2%` true Clay at `100–200 cm`). | Vertic/heavy clay-loam properties in Seybouse plains exhibit high water-holding potential yet a **narrow tillage moisture window** ("sticky when winter-wet, hard-clodded when summer-dry", FAO Vertisol guidance). Favors cereals/faba bean over deep root crops; penalizes potato tuber expansion & lentil drainage unless lightened/drained. | Actual clay mineralogy (smectite shrink-swell severity) and local surface drainage/slope per field. |
| **Soil pH & Nutrients** | Cropland `0–30 cm` `pH`: median **`7.13`**, p95 **`7.43`**, max **`7.65`** (all pixels `5.93–7.67`). Cropland `SOC`: median **`17.78 g/kg`** (down to **`10.10 g/kg`**; `Tamlouka` commune **`13.58 g/kg`**). | Near-neutral to slightly alkaline pH suits cereals, faba bean, chickpea, and lentil (`6.0–8.0`), **constrains acid-preferring potato (`5.0–6.2` optimal -> scab risk above `6.5–7.5`)**, and signals calcareous phosphorus/micronutrient tie-up risks. Continuous cereal SOC depletion strongly supports **legume & vetch-oat inclusion**. | Soil salinity (`ECe`), active `CaCO₃`, available `P`/`K`, and true mineral nitrogen (`SoilGrids N` unusable). |
| **Hydro-Climatic Variability** | `Spring GPM` varies **`51.0 to 220.8 mm`** across 2016–2025! Annual `GPM` (`404–761 mm`) shows a **systematic `-132 mm/yr` (`-20%`) bias vs. `NASA POWER` (`541–962 mm`)**. Summer `Tmax` averages **`35.66 °C`** with `SMAP surface = 0.089 m³/m³`. | High spring rainfall volatility exposes spring chickpea and late-sown wheat to severe **terminal heat/drought during grain-fill (Apr–May)**, strongly favoring timely autumn sowing and winter chickpea cultivars. Rainfed summer crops (tomato, summer maize/potato) are **physically infeasible** without verified irrigation! **Raw climate bias prohibits naive hard-threshold precipitation cuts.** | Commune/station bias curve vs. ONM meteorological gauges; actual dam quota allocations from Bouhamdane Dam in drought years (`2022` `404 mm` GPM). |
| **Secondary Salinization & Water Quality** | *No salinity raster locally.* | Literature warns of secondary salinization & nitrate/wastewater accumulation affecting irrigated sectors along middle/lower Seybouse (`~20%` perimeter risk cited in regional studies). | Spatial extent of `ECe > 2–4 dS/m` across Guelma–Bouchegouf perimeter soils and borehole water. |

---

## 5. Formal Definition of the Agricultural Decision Problem

**Core Problem Statement for Field Shift:**  
> *Given the verified soil (`250 m` Clay Loam/pH/SOC/CEC), hydro-climatic variability (`GPM`, `SMAP`, `NASA POWER` seasonal regimes), and cropland-intensity profile of each agricultural zone (commune or cropland-masked zone) in Guelma Wilaya—plus user-declared irrigation access and operational preferences—what are the **agronomically compatible, water-balanced, and soil-conserving multi-year annual crop rotation strategies (`2–4` years)**, and how should they be ranked with transparent physical constraints and explicit data-uncertainty disclosures?*

**Explicit Exclusions (Scientific Integrity Boundaries):**
1. Field Shift does **not** currently perform parcel-level crop yield forecasting (kg/ha) or economic profit maximization (no validated yield or price ground truth).
2. Field Shift does **not** perform field-by-field species classification from historical Sentinel-2 (`2017–2025` multi-year GeoTIFFs deferred).
3. Unconditional high-water summer vegetable recommendations (`processing tomato`, `potato`) are strictly gated behind **explicit user/institutional verification of irrigation availability and salinity safety**.
