# Phase G — Agronomic Knowledge Base Report

**Project:** Field Shift — Crop Rotation Decision-Support System (Guelma Wilaya, Algeria)  
**Scope:** Structured, scientifically traceable agronomic knowledge base ([agronomic_knowledge/](file:///home/lokman/Desktop/FeildShit-SI-Model/agronomic_knowledge/)) built strictly upon Phase E verified inventories ([crop_system_inventory.csv](file:///home/lokman/Desktop/FeildShit-SI-Model/docs/phaseE/crop_system_inventory.csv) and [agronomic_constraints_framework.csv](file:///home/lokman/Desktop/FeildShit-SI-Model/docs/phaseE/agronomic_constraints_framework.csv)) with zero fabricated parameters, zero Earth Engine tasks, and zero rotation optimization.

---

## 1. Crop System Inventory Coverage (`13` Phase E Systems)

All `13` crop / land-rest systems defined in Phase E are codified inside [crop_profiles.json](file:///home/lokman/Desktop/FeildShit-SI-Model/agronomic_knowledge/crop_profiles.json):

| Crop ID | Canonical Name | Category | Lifecycle | Annual Scope | Guelma Evidence Status |
|---|---|---|---|---|---|
| `DURUM_WHEAT` | Durum Wheat (*Triticum durum*) | Winter Cereal | Annual | `true` | `LOCAL_VERIFIED_REGIONAL` |
| `SOFT_WHEAT` | Soft Wheat (*Triticum aestivum*) | Winter Cereal | Annual | `true` | `REGIONAL_ALGERIAN_ITGC` |
| `BARLEY` | Barley (*Hordeum vulgare*) | Winter Cereal | Annual | `true` | `LOCAL_VERIFIED_REGIONAL` |
| `FABA_BEAN` | Faba Bean (*Vicia faba*) | Winter Food Legume | Annual | `true` | `LOCAL_VERIFIED_REGIONAL` |
| `CHICKPEA_WINTER` | Winter Chickpea (*Cicer arietinum*) | Winter Food Legume | Annual | `true` | `REGIONAL_ALGERIAN_ITGC` |
| `CHICKPEA_SPRING` | Spring Chickpea (*Cicer arietinum*) | Spring Food Legume | Annual | `true` | `LOCAL_VERIFIED_REGIONAL` |
| `LENTIL` | Lentil (*Lens culinaris*) | Winter/Early-Spring Pulse | Annual | `true` | `LOCAL_VERIFIED_REGIONAL` |
| `VETCH_OAT` | Vetch-Oat (*Vicia sativa + Avena sativa*) | Forage Legume-Cereal Mix | Annual | `true` | `REGIONAL_ALGERIAN_ITGC` |
| `TOMATO_IND` | Processing Tomato (*Solanum lycopersicum*) | Irrigated Vegetable / Cash | Annual | `true` | `LOCAL_VERIFIED_REGIONAL` |
| `POTATO` | Potato (*Solanum tuberosum*) | Irrigated Tuber Crop | Annual | `true` | `HYPOTHESIS_NEEDS_DSA_CHECK` |
| `SUNFLOWER` | Sunflower (*Helianthus annuus*) | Spring/Summer Oilseed | Annual | `true` | `HYPOTHESIS_NEEDS_DSA_CHECK` |
| `OLIVE` | Olive (*Olea europaea*) | Perennial Tree Crop | **Perennial** | **`false` (Excluded)** | `LOCAL_VERIFIED_REGIONAL` |
| `BARE_FALLOW` | Bare Fallow (Worked/Grazed Rest) | Traditional Rest / Weed Fallow | Annual Period | `true` | `LOCAL_VERIFIED_REGIONAL` |

No undocumented or unverified crops were added. Olive (`OLIVE`) is permanently isolated via `in_annual_rotation_scope = false`.

---

## 2. Parameter Provenance & Evidence Classification Distribution

Each crop holds `18` standardized agronomic parameter entries (`234` total parameter records across all `13` crops, defined in [knowledge_data_dictionary.csv](file:///home/lokman/Desktop/FeildShit-SI-Model/agronomic_knowledge/knowledge_data_dictionary.csv)). Every entry records `value`, `unit`, `source`, `evidence_classification`, `confidence`, and `geographic_applicability`.

| Evidence Classification | Count (`n = 234`) | Share | Agronomic Role |
|---|---:|---:|---|
| `HARD_CONSTRAINT` | `47` | `20.1%` | Strict biophysical or pathological boundaries (`suitable_planting_seasons`, `STRICTLY_IRRIGATED` gates, `0 kg N/ha` non-legume physiology, `>=3 yr` Solanaceae/pulse return breaks, perennial Olive guard). |
| `SOFT_CONSTRAINT` | `150` | `64.1%` | FAO-56 Kc/Ky/Zr values, optimal pH & clay thresholds (`CON_01`, `CON_02`), rainfall bands (`CON_06`), drought sensitivities, and ITGC residue/machinery considerations. |
| `EXPERT_ASSUMPTION` | `21` | `9.0%` | Direction-of-effect qualitative balances (`som_contribution` where field C balance varies with management, machinery lists without farm inventory, untested `500 mm` Sunflower rainfed assumption). |
| `UNKNOWN` | `16` | `6.8%` | Uncalibrated or unmeasured local quantities preserved explicitly as **`value = null`** (e.g. quantitative `nutrient_requirements_quantitative` kg N-P-K/ha curves across field crops; local nodulation-dependent `kg N/ha` for Chickpea, Lentil, and Vetch-Oat; while `OLIVE` duration & `TOMATO_IND`/`POTATO`/`BARE_FALLOW` rainfed N/A entries bring total explicit `null` `value` fields to `21`). |

---

## 3. Sequence Compatibility Graph ([sequence_compatibility.json](file:///home/lokman/Desktop/FeildShit-SI-Model/agronomic_knowledge/sequence_compatibility.json))

- **Strict Annual/Perennial Separation (`SEQ_01_PERENNIAL_GUARD`, `HARD_CONSTRAINT`):** Rejects any annual rotation containing `OLIVE`.
- **Cereal Monoculture & Grass-Weed Guard (`SEQ_02_CEREAL_REPETITION`, `HARD_CONSTRAINT`):** `WARNING` on `2` consecutive cereal campaigns (`Durum -> Durum`, `Soft -> Barley`, etc.) and **`FAIL`** if a cumulative streak reaches `>= 3` consecutive cereal years across prior history (`crop_history` at `T-2`, `T-1`) + planned sequence slots.
- **Solanaceae Return Interval (`SEQ_03_SOLANACEAE_BREAK`, `HARD_CONSTRAINT`):** **`FAIL`** on `< 3`-year gap between `TOMATO_IND` and/or `POTATO` (*Verticillium*, *Fusarium*, nematodes, late blight, *Orobanche*).
- **Food Legume Broomrape / Ascochyta Break (`SEQ_04_PULSE_BROOMRAPE_BREAK`, `HARD_CONSTRAINT`):** **`FAIL`** on `< 3`-year return of same pulse or `FABA_BEAN <-> LENTIL` (*Orobanche crenata*, *Botrytis*, *Ascochyta*); `WARNING` on cross-legume intervals (`FABA_BEAN <-> CHICKPEA`).
- **Oilseed Return Interval (`SEQ_05_SUNFLOWER_BREAK`, `HARD_CONSTRAINT`):** **`FAIL`** on `< 3`-year repeated `SUNFLOWER` (*Sclerotinia*, *Orobanche cumana*).
- **Fallow Replacement & Cereal-Legume Synergy (`SEQ_06`, `SEQ_07`, `SOFT_CONSTRAINT`):** Validates `VETCH_OAT` (Apr-May cut before weed seed shed) and `Food Legume -> Cereal` transitions (`PASS`), flagging `Vetch-Oat -> Vetch-Oat` oat-host risk (`WARNING`).
- **Bare Soil Cover & Subsoil Competition (`SEQ_08`, `SEQ_09`, `SEQ_10`):** Prohibits consecutive `BARE_FALLOW -> BARE_FALLOW` (`FAIL`), flags low-SOC/no-DEM fallow erosion (`WARNING`), warns deep-taproot `SUNFLOWER -> rainfed Cereal` and `Autumn POTATO -> Winter Cereal` overlap (`WARNING`), and returns **`UNKNOWN`** when preceding crop history (`T-1`) is missing or unmapped (`SEQ_10`).

---

## 4. Scientific Limitations Preserved

1. **Zero Quantitative Yield / Profit Numbers:** No crop revenue, gross margin, or `qx/ha` yield prediction exists anywhere in Phase G.
2. **Local Calibration Gaps:** `POTATO` and `SUNFLOWER` retain `HYPOTHESIS_NEEDS_DSA_CHECK`; `FABA_BEAN` biological N fixation (`100–200 kg N/ha`) reflects Mediterranean/ITGC ranges rather than plot-measured `Nmin`; `SoilGrids Nitrogen` remains quarantined (`UNVALIDATED_EXCLUDED`).
3. **Coarse Macro Climate vs Field Boundary:** Rainfall, temperature, soil moisture, and DEM gaps remain explicitly surfaced as rule caveats or `UNKNOWN` statuses rather than hidden inside deterministic thresholds.
