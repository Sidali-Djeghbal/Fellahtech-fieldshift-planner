# Phase R0.3.1 — High-Impact Agronomic Parameters Scientific Audit

**Purpose:** Rigorously test the highest-impact scientific domains in Phase R0.3 before any Phase R0.4 model design: (A) Thermal requirements, (B) Biological $\text{N}_2$ fixation and N carryover, (C) FAO-56 water-balance constants, (D) Rainfall viability cutoffs, (E) Soil suitability constraints (`pH`, `clay`, `CaCO3`, `CEC`), and (F) Nutrient uptake and economics parameterization.

---

## A. Thermal Requirements (`104` Matrix Rows Across `8` Parameters × `13` Crops)

Phase R0.3 thermal claims suffer from severe source-traceability and spatial-scale failures:

1. **Synthetic Placeholder `SRC-34` Contamination:**
   - `SRC-34` (*"Consolidated Agronomic Thermal & Growing Degree Day Constants synthesized in Batch 7a search summary"*) has **zero authors, DOIs, journals, or experimental tables** (**`UNVERIFIED`**).
   - It is cited in **`66` matrix rows** (`48` times as the **SOLE source**), with **`44` rows erroneously marked `HIGH` confidence** in Phase R0.3!
   - All `60` purely `SRC-34` or non-applicable thermal rows (excluding `cycle_duration_days` and verifiable mixed envelopes) are downgraded to **`NOT_AVAILABLE`** readiness (`LOW` / `NONE` confidence).
2. **`SRC-29` (EcoCrop / FAO) Limitations:**
   - The `SRC-29` DOI (`10.1080/17538947.2013.781242`) resolves to Ramirez-Villegas et al. (2013) *method paper* only; the standalone **`ecocrop.fao.org`** portal is retired into FAO GAEZ v4 without an archived snapshot hash. Broad global EcoCrop suitability windows (`T_opmn..T_opmx`, `T_kmp`) cannot substitute for cultivar-specific Algerian frost/heat thresholds.
3. **Biologically Misframed Parameter Slot:**
   - **`OLIVE::temp_germ_min_c` (`15–25 °C`)** applies annual **seed germination** temperature bounds (`SRC-29;SRC-34`) to a **clonally propagated perennial orchard tree** transplanted as saplings! Furthermore, `OLIVE::thermal_time_gdd_degcd` and `cycle_duration_days` (`180–240` annual harvest cycle vs 365-day orchard) cannot use annual crop phenology schemas.
4. **Telemetry Mismatch (`CAND-07`):**
   - Current runtime consumes **10-year seasonal means** (`nasa_power_t2m_min/max` at `0.5° × 0.625° ≈ 55–69 km`) on only 4 crops (`REM-05`). Acute freeze nights (e.g., `-2` to `-5 °C` flowering frost) and anthesis heatwaves (`>32–35 °C`) cannot be detected from 10-year decadal seasonal means or without DEM elevation downscaling.
   - **Verdict on `CAND-07`:** **`REJECT_OR_REFORMULATE`** — isolate safe code hygiene (deprecating/cleaning unused rule catalog keys `REM-01/02/03`) from adopting unverified `SRC-34` numbers.

---

## B. Biological Nitrogen Fixation (BNF) & Residual N Carryover (`26` Matrix Rows)

Phase R0.3 merged incompatible concepts into **`bnf_fixed_kg_n_ha`**, **`residual_n_carryover_kg_n_ha`**, and **`CAND-04`**, violating modern N-balance science verified in **Liu et al. (2019, `10.1007/s11104-019-04167-x`; 2024, `10.1016/j.fcr.2024.109412`, `SRC-30`, `VERIFIED_PRIMARY_SOURCE`)**:

1. **Mandatory 6-Way Conceptual Separation:**
   Any future Field Shift design (`R0.4+`) MUST keep these six quantities strictly separate rather than collapsing them:
   1. **Above-ground Shoot Fixed N** (`kg N/ha`, $^{15}\text{N}$ `%Ndfa` × shoot N)
   2. **Whole-Plant Gross BNF** (`kg N/ha`, shoot fixed N × Unkovich et al. **2010** root factor, e.g. `×1.56` lentil, `×1.82` chickpea)
   3. **Below-ground Rhizodeposit + Root N Pool** (`kg N/ha`)
   4. **Harvested Grain/Straw N Export** (`kg N/ha`; e.g., faba bean removes ~50 kg N per tonne grain!)
   5. **Field Net N Balance** (`Gross BNF − Grain N Export`, frequently **near zero or negative** on high-HI grain pulses as proven by Liu et al., `SRC-30`!)
   6. **Estimated Rotational Residual N Carryover / N Replacement Value (NRV)** (`kg N/ha` equiv available to succeeding cereal, which also includes rotational moisture/disease "non-N break effects")
2. **Verified Citation Error in `SRC-31`:**
   - Phase R0.3 attributed the species root correction factors (**`1.56` lentil**, **`1.82` chickpea**) to Unkovich et al. **(2008)** ACIAR Monograph No. 136 (`SRC-31`). Cross-check verifies ACIAR MN136 is a methods manual without those species multipliers; the actual values originate in **Unkovich, Baldock & Peoples (2010), *Plant and Soil* 329:75–89 (`DOI:10.1007/s11104-009-0136-5`)**!
   - Furthermore, matrix rows L131/135/139 store shoot-only BNF (`18–82`, `32–82`) in `[min..max]` while referencing whole-plant multiplication (`×1.56`, `×1.82`) inside text notes — creating direct numerical basis ambiguity (`CONFLICTED`).
3. **Environmental Modulation Ignored:**
   - Faba bean BNF collapses under drought or **`ECe > ~1.5 dS/m`** (`SRC-19` Abdelly et al., `VERIFIED_PRIMARY_SOURCE`). Unlinked ITGC estimates (`30–40 kg N/ha` faba credit) lack published Guelma $^{15}\text{N}$ or fertilizer-response NRV trials.
4. **Only Clean Ready Rows in Nitrogen Domain (`3` Rows):**
   - **`DURUM_WHEAT`, `SOFT_WHEAT`, `BARLEY` `residual_n_carryover_kg_n_ha = 0.0 kg N/ha`** (`SRC-30` `VERIFIED_PRIMARY_SOURCE`): clean, physically sound scalar (`IMPLEMENTATION_READY` for *symbiotic N carryover = 0*, distinct from residual fertilizer mineral `Nmin`).
   - Wait for `TOMATO_IND`, `POTATO`, `SUNFLOWER` (`0.0` in matrix): downgraded to **`REFERENCE_ONLY`** because horticultural crops apply 150–300 kg N/ha mineral N leaving unmeasured `Nmin`, sunflower residues immobilize N / deplete deep soil moisture, and `SUNFLOWER` cites unverified `SRC-33`.
   - **`SoilGrids nitrogen_0_30cm` Quarantine:** Confirmed physically anomalous (`N > SOC` ratio in repository canonical dataset) — MUST remain permanently quarantined (`TIER_C_03 = BLOCKED_BY_LOCAL_DATA`).

---

## C. FAO-56 Water Balance Parameters (`52` Matrix Rows) — Verbatim Primary Comparison

Direct inspection of Allen et al. (1998) live FAO HTML tables (**`SRC-22`**, [x0490e0e.htm](https://www.fao.org/4/X0490E/x0490e0e.htm) Table 22 & [x0490e0b.htm](https://www.fao.org/4/X0490E/x0490e0b.htm) Table 12 & `x0490e0b.htm` Table 11) caught **major Phase R0.3 misquotations inside BOTH the matrix and `CAND-05`:**

| Crop Profile | Current KB `root_depth_m` | R0.3 Claimed "FAO-56 Table 22" (`CAND-05`!) | **Actual Verbatim FAO-56 Table 22 (`SRC-22`)** | Audit Verdict |
|---|---|---|---|---|
| **CHICKPEA_WINTER / SPRING** | `0.6–1.0` / `0.6–0.9` | **Misquoted `0.9–1.5 m`** (`L147, L179`) | **`0.6–1.0 m`** (`Chick pea` / `Grabanzo`) | **`CRITICAL MISQUOTE CAUGHT:`** `CAND-05` proposed overwriting accurate `0.6–1.0 m` with false `0.9–1.5 m`! (`CONFLICTED` / **`REJECT_OR_REFORMULATE`**) |
| **FABA_BEAN** | `0.8–1.0` | **Misquoted `0.6–0.9 m`** (`L115`) | **`0.5–0.7 m`** (`Fababean Dry/Seed`) | **`MISQUOTE CAUGHT:`** FAO-56 Table 22 says `0.5–0.7 m`, shallower than both KB and `R0.3` (`CONFLICTED`). |
| **LENTIL** | `0.5–0.8` | **Misquoted `0.6–1.0 m`** (`L211`) | **`0.6–0.8 m`** (`Lentil`) | **`MISQUOTE CAUGHT:`** Actual FAO-56 Table 22 upper bound is `0.8 m`, not `1.0 m` (`CONFLICTED`). |
| **DURUM / SOFT WHEAT** | `1.0–1.5` | `1.0–1.8 m` (`L019, L051`) | `Spring Wheat 1.0–1.5 m`, `Winter Wheat 1.5–1.8 m` | `VERIFIED_MATCH` globally, held `REFERENCE_ONLY` pending local root pans (`CON_05`). |
| **BARLEY / TOMATO / POTATO / SUNFLOWER** | `1.0–1.5` / `0.7–1.2` / `0.4–0.6` / `1.0–1.5` | `1.0–1.5` / `0.7–1.5` / `0.4–0.6` / `0.8–1.5` | Identical in FAO-56 Table 22! | `VERIFIED_MATCH` globally (`REFERENCE_ONLY` pending caliche pan / drip bulb depth checks). |
| **VETCH_OAT** | `0.5–0.9` | `0.6–1.5 m` (`L243`) | **Oats `1.0–1.5 m`; Common vetch ABSENT** | `LOCAL_CALIBRATION_REQUIRED` — cannot impose oat `1.5 m` onto mixed hay. |
| **OLIVE** | `1.0–1.5` | `1.0–1.7 m` (`L371`) | `Olives (40–60% ground cover) = 1.2–1.7 m` | `REFERENCE_ONLY` — tree depth strongly governed by stony hillside depth (`CON_05`). |

Additional verbatim FAO-56 findings:
- **Verified `IMPLEMENTATION_READY` Constants (`11` Rows):** **`fao56_depletion_p`** (`DURUM_WHEAT 0.55`, `SOFT_WHEAT 0.55`, `BARLEY 0.55`, `FABA_BEAN 0.45`, `CHICKPEA_WINTER 0.50`, `CHICKPEA_SPRING 0.50`, `LENTIL 0.50`, `TOMATO_IND 0.40`, `POTATO 0.35`, `SUNFLOWER 0.45`, `OLIVE 0.65`) match FAO-56 Table 22 verbatim as clean dimensionless scalars at $\text{ET}_c \approx 5\ \text{mm/d}$ (requiring FAO-56 Eq. 8 dynamic adjustment in runtime design). `VETCH_OAT` lacks Table 22 coverage (`LOCAL_CALIBRATION_REQUIRED`).
- **`fao56_kc_profile` Table 12 Discrepancies:** Table 12 lists `Chick pea Kc_mid = 1.00` (not `1.00–1.05`), `Fababean Dry = 0.50 / 1.15 / 0.30` (matrix wrote `0.40 / 1.15 / 0.35`), `Lentil = 1.10`, `Olives 40–60% cover = 0.65 / 0.70 / 0.70` (matrix broadened to `0.40–0.65 / 0.65–0.85`). Moreover, all FAO-56 Table 12 values require $\text{RH}_{\min}$ and **`WS2M`** adjustment (Eq. 62/65), yet `WS2M` is absent from runtime! Meanwhile **`BARE_FALLOW`** static `Kc = 0.15–0.30` violates FAO-56 Chapter 7 (`K_e` ranges dynamically from `0.1` to `1.15` by wetting event frequency and topsoil $REW$).
- **`fao56_stage_lengths_days`:** FAO-56 Table 11 *Arid Region Oct/Nov* actually reports **Lentil = `25 / 35 / 70 / 40 = 170 d`**, confirming winter sowing cycles exist alongside Europe `150 d` (`SRC-22`), though local ITGC Guelma phenology calibration is still needed (`LOCAL_CALIBRATION_REQUIRED` / `REFERENCE_ONLY`). Note all `Kc` and `L_ini/L_dev/L_mid/L_late` profiles must be split from single strings into atomic numeric fields before any scoring engine reads them.
- **FAO-33 (`SRC-23`) & FAO-66 (`SRC-24`) Citation & Method Errors:** The `SRC-23` URL (`s2022e`) points to **Brouwer & Heibloem Training Manual 3**, NOT FAO-33 (`Doorenbos & Kassam 1979`); the `SRC-24` URL `/aquacrop/en/` returns **HTTP 404** (FAO-66 is `i2800e`). For **`OLIVE`**, classic FAO-33 **`Ky = 0.80`** conflicts directly with FAO-66 regulated deficit irrigation **`Ky = 0.30–0.50`** (`CONFLICTED`). And matrix row `L341` (**`SUNFLOWER::fao33_seasonal_etc_mm = 600–1000 mm`**) was misflagged as a `DIFFERS_CALIBRATION_CANDIDATE` by comparing **irrigated potential $\text{ET}_c$** against the KB's **rainfed minimum precipitation (`500 mm`)**!

---

## D. Rainfall Thresholds & Precipitation Bias (`26` Matrix Rows)

1. **Biological Survival vs Viable Commercial Yield Conflation:** `DURUM_WHEAT::rainfed_min_precip_mm` (`300–375 mm`, `CAND-05`) relies on **Sétif High Plateaus cultivar stability studies (`SRC-09/10`, `300–350 mm`)** showing which breeding lines survive sub-humid deficits rather than profitable sub-humid **Guelma agronomic viability (`~400 mm` floor)**.
2. **Systemic Telemetry Bias Ignored by Threshold Debates:** Repository **GPM (`11 km`) carries a verified `-132.3 mm/yr` negative bias** vs NASA POWER (`~55–69 km`), and **monthly GPM data do NOT exist on disk**. Lowering durum's gate from `400 mm` to `300–350 mm` on dry-biased GPM would expose drought-prone shallow fields to unhedged durum failure while dismantling the `<460 mm` barley diversification candidate rule.
3. **BARE_FALLOW Over-Transfer (`CAND-06`):** `BARE_FALLOW` water storage (`18%` / `54 mm` worked vs `28%` / `84 mm` no-till, `10–28%` wrongly placed into `fao33_seasonal_etc_mm` slot L405!) derives from Morocco **`200–300 mm` semi-arid Settat (`SRC-15`, Bouzza 1990)** and cites **an invalid DOI in `SRC-16`** (`10.1016/j.fcr.2012.02.023` belongs to Kassam et al. 2012; Mrabet et al. 2012 is **`10.1016/j.fcr.2011.11.017`**). In `436–555 mm` Guelma communes, autumn-spring worked fallow risks serious soil erosion (`>5%` slope) and $\text{NO}_3^-$ leaching, making fixed `water_efficiency = 0.60` vs undifferentiated fallback invalid without knowing farmer tillage/weed management (`REQUIRES_MORE_EVIDENCE`).

---

## E. Soil Constraints (`pH`, `Clay`, `CEC`, `SOC`, `CaCO3`, `Scab`)

1. **`SoilGrids 250 m` Is Unvalidated Locally Against Guelma Soil Labs:** All soil inputs come from 250 m ISRIC global regressions (`~6.25 ha/pixel`) without Guelma bulk density, active $\text{CaCO}_3$, or parcel-boundary alluvial edge separation.
2. **Potato pH ≥ 6.5 Warning (`CAND-02`):** High bicarbonate buffering in calcareous Guelma soils (`p05 = 6.78`, `median = 7.13`, `max = 7.65`) renders field acidification to `pH <= 5.5` agronomically infeasible (`APPROVE_FOR_DESIGN` ONLY to reframe the early return into an **active scab risk management advisory + restore downstream `tol_max` check**, while requiring active $\text{CaCO}_3$ + resistant-cultivar guidance until lab $\text{CaCO}_3$ exists).
3. **Soil pH Bounds (`CAND-01`):** Barley `tol_max = 8.0 < Wheat 8.5` inversion and null fallbacks (`4.5–8.8`) are real code/KB hygiene bugs, but tightening wheat `tol_max = 8.3` relies on unarchived EcoCrop (`SRC-29`) and uninspected Sys 1993 (`SRC-28`) tables -> **`REQUIRES_MORE_EVIDENCE`**.
4. **Clay `32–35%` Waterlogging Cutoffs (`TIER_B_01`):** Guelma farmland median clay (`33.7%`) triggers false chronic warnings without **DEM slope (`%`), TWI, or surface drainage**, all of which are completely absent on disk (`BLOCKED_BY_LOCAL_DATA`).
5. **`CEC` Uncalibrated (`soil_cec_fertility_note`):** Both Sys 1993 (`SRC-28`) table citations and SoilGrids V6 native CEC unit scaling check remain unverified (`LOCAL_CALIBRATION_REQUIRED`), and `BARE_FALLOW::soil_cec_fertility_note` (L400) misuses the CEC slot for SOM oxidation notes!

---

## F. Nutrient Uptake, Fertilization & Economic Metrics (`52` Matrix Rows)

1. **Scalar Unit-Concatenation Structural Bug (`31`+ Matrix Rows):**
   - `nutrient_uptake_npk_kg_t` stores distinct macronutrients (**`N`, `P2O5`, `K2O` in `kg/t`**) packed into a single **`value_min..value_max`** pair (e.g., Potato `3.0–7.0` mixes `3.0–4.5 N`, `1.0–2.0 P2O5`, `4.0–7.0 K2O`; Tomato `2.5–6.0`; Sunflower `35–100`).
   - `forage_nutritive_value` mixes `% CP`, `% NDF`, and `t DM/ha` (`BARLEY 3.8..80.5`; `VETCH_OAT 3.0..8.0`).
   - `algerian_costs_prices_context` pairs **admin prices (`6,000 DA/q`)** with **FTV hectare costs (`153,615 DZD/ha`)** inside `value_min..value_max`.
   None of these concatenated columns can be parsed safely by software (`REFERENCE_ONLY` / `LOCAL_CALIBRATION_REQUIRED` pending schema normalization into atomic nutrient/forage/economic fields).
2. **Uptake ≠ Fertilizer Requirement:** `FAO Bull. 16` (`SRC-27`, `PARTIALLY_VERIFIED`) provides *crop physiological nutrient removal per tonne*, NOT local fertilizer recommendations. Applying fertilizer recommendations requires measured soil $\text{N}_{\min}$, Olsen-P, exchangeable K, yield target, and organic manure history.
3. **National Costs/Prices vs Guelma Farm Budgets (`TIER_B_04` / `TIER_C_01`):** ITGC FTV costs (`153,615`, `112,484`, `197,209`, `205,849 DZD/ha`) and OAIC guaranteed prices (`6,000 / 5,000 / 3,400 / 20,000 / 19,000 DA/q` — externally confirmed, missing exact JORA/OAIC circular IDs in `SRC-08`) cover selected national cereals/pulses ONLY. Tomato (`800 qx/ha drip vs 250–300 qx/ha sprinkler` press quote falsely blamed on `SRC-14` repo docs), potato, olive, hay, irrigation volumetric cost ($\text{m}^3/\text{ha}$), and Guelma commune yields remain **unmeasured (`BLOCKED_BY_LOCAL_DATA`)**.
