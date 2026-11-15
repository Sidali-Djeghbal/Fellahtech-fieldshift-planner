# Phase M — Stratified Pilot Field Sampling Strategy (Guelma Wilaya)

> **Status:** **PROPOSED SAMPLING DESIGN (Zero Farmers Selected / Zero Field Observations Collected Yet)**  
> **Empirical Basis Used for Stratification:** Verified `2016–2025` commune GPM precipitation means extracted directly from `data/INTEGRATED/canonical/spatial_reference/guelma_communes_utm32n.gpkg` (`34` communes) and `commune_seasonal_panel_2016_2025.csv`.

---

## 1. Observed Agro-Climatic & Spatial Stratification in Guelma

| Pilot Stratum | Observed 2016–2025 GPM Range (`mm/yr`) | Illustrative Guelma Communes (Verified Names) | Primary Agronomic Stressors & Regimes to Stress-Test |
|---|---|---|---|
| **`NORTHERN_HUMID`** | `~590 – 621 mm/yr` | `Ain Ben Beida` (`620.84 mm`), `Oued Fragha` (`613.52 mm`), `Nechemaya` (`613.02 mm`), `Bouati Mahmoud` (`609.63 mm`), `Bouchekouf` (`603.95 mm`), `Roknia` (`597.10 mm`), `Helliopolis` (`592.90 mm`) | Winter waterlogging risk on heavy clays (missing DEM), Solanaceae (`TOMATO_IND`) break intervals (`SEQ_03`), irrigation `ECe` risk, `POTATO` / `SUNFLOWER` local feasibility |
| **`CENTRAL_VALLEY`** | `~547 – 577 mm/yr` | `Hammam Debagh` (`576.83 mm`), `Medjaz Ammar` (`573.50 mm`), `Bou Hamdane` (`570.96 mm`), `Guelma` (`568.60 mm`), `Boumahra Ahmed` (`567.33 mm`), `Belkheir` (`564.09 mm`), `Ben Djerrah` (`554.47 mm`) | Dense cereal–faba bean–forage corridor (`FABA_BEAN` `450 mm` drought-boundary `PRECIP_SENSITIVE_RANK_SHIFT` in dry years), Seybouse alluvial clay workability, reservoir/river vs rainfed comparison |
| **`SOUTHERN_SEMI_ARID`** | `~444 – 526 mm/yr` | `Tamlouka` (`444.28 mm`), `Ain Makhlouf` (`477.47 mm`), `Ain Rekada` (`486.90 mm`), `Oued Zenati` (`495.32 mm`), `Ain Larbi` (`509.03 mm`), `Ain Sandel` (`516.12 mm`), `Selaoua Announa` (`520.57 mm`) | Low rainfall (`< 500 mm`), `Barley / Chickpea / Lentil / Vetch-Oat` drought-escape vs continuous wheat risk, fallow (`crop_freq`) dominance, urban-edge `SoilGrids 250 m` pixel masking (`Oued Zenati`) |

---

## 2. Proposed Purposive Sample Size & Quota Matrix (`N = 36` Parcels)

Consistent with Phase E Pillar 5 (`30–60` farms; [`validation_strategy.md`](file:///home/lokman/Desktop/FeildShit-SI-Model/docs/phaseE/validation_strategy.md)), Phase M proposes **`N = 36` pilot fields** (`12` per climatic stratum), validated programmatically via [`validate_sampling_plan`](file:///home/lokman/Desktop/FeildShit-SI-Model/src/pilot/models.py#L250):

| Stratum | Rainfed Target | Irrigated / Supplemental Target | Stratum Total | Target Size Bands Covered (`Small <5 ha`, `Med 5–30 ha`, `Large >30 ha`) |
|---|---:|---:|---:|---|
| `NORTHERN_HUMID` | `6` | `6` *(river / reservoir / groundwater)* | `12` | `4` Small (`< 5 ha`), `5` Med (`5–30 ha`), `3` Large (`> 30 ha`) |
| `CENTRAL_VALLEY` | `7` | `5` *(Bouhamdane / Seybouse perimeter)* | `12` | `4` Small (`< 5 ha`), `5` Med (`5–30 ha`), `3` Large (`> 30 ha`) |
| `SOUTHERN_SEMI_ARID` | `9` | `3` *(well / supplementary drip)* | `12` | `3` Small (`< 5 ha`), `5` Med (`5–30 ha`), `4` Large (`> 30 ha`) |
| **Total Proposed** | **`22`** | **`14`** | **`36`** | **`11` Small, `15` Medium, `10` Large** |

### Required Operational Diversity Across the `36` Fields
- **Crop History Coverage:** Include at least `8` continuous-cereal parcels (`SEQ_02` guard test), `6` cereal–legume rotations (`SEQ_07`), `6` irrigated horticulture fields (`TOMATO_IND` / `POTATO` `SEQ_03`), `6` parcels with livestock forage priorities (`forage_value_weight > 0`), and `6` parcels with missing/unknown crop history or unknown water availability (`null` vs `[]` safety checks).
- **Spatial Edge Coverage:** Deliberately include `>= 4` sub-5 ha parcels (to observe `SoilGrids 250 m` pixel masking behavior flagged in Phase K `SPAT_BOU_SMALL_2HA_RAINFED`) and `>= 2` peri-urban or Wilaya-edge parcels.

---

## 3. Explicit Sample Size & Statistical Limitations

1. **Purposive Convenience Sample — Not Statistically Representative:** Recruiting through `DSA`/`ITGC`/`ONID` extension networks introduces voluntary cooperator bias (participating farms are often better mechanized or more connected than average). Results **must not** be extrapolated as unbiased wilaya-wide population rates.
2. **Low Power for Rare Sub-Cells:** With `n = 12` per stratum (and `3–6` parcels in smaller irrigated sub-cells), confidence intervals around per-commune proportions are wide (`+/- 25–30%`); commune-level statistical generalization is invalid.
3. **Single-Season / Pre-Sowing Cross-Section (`No Longitudinal Yield Proof`):** Evaluating 2–4 season rotation advisories in a 1-season pilot tests **agronomic acceptability and feasibility**, NOT realized multi-year crop yield response (`t/ha`) or soil organic carbon change (`g/kg`).
4. **No Fabricated Quotas Claimed Complete:** All `36` slots remain `PLANNED` until partner institutions select real consenting farms.
