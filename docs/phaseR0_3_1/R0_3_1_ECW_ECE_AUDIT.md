# Phase R0.3.1 — Salinity & ECw / ECe Scientific Audit

**Scope:** Strict methodological audit of every salinity, water-chemistry, and crop salt-tolerance claim in [docs/phaseR0_3/](file:///home/lokman/Desktop/FeildShit-SI-Model/docs/phaseR0_3/R0_3_EXECUTIVE_SUMMARY.md) across all 13 crops and current Guelma engine interfaces.

---

## 1. Core Physical Problem: ECe vs ECw vs ECa vs TDS (`g/L`)

Phase R0.3 conflated four physically non-interchangeable salinity measurement bases into `soil_salinity_ece_threshold_dsm` and calibration candidates:

| Symbol | Quantity & Matrix | Typical Field Relationship | Governing Assumptions / Caveats |
|---|---|---|---|
| **$\text{EC}_e$** | Saturated soil paste extract electrical conductivity (`dS/m` at 25 °C) | Standard reference basis of Maas & Hoffman (1977) & FAO-29 Table 4 | Standardizes moisture heterogeneity across textures; requires lab saturation extract or calibrated soil probe. |
| **$\text{EC}_w$** | Irrigation water electrical conductivity (`dS/m` at 25 °C) | Steady-state FAO-29 Table 3 relation: $\text{EC}_e \approx 1.5 \times \text{EC}_w$ (**only** at $\text{LF} = 0.15\text{–}0.20$ with $\sim 15\text{–}20\%$ LF leaching; FAO-29 Table 3 explicitly derives $X = 1.6$ at $\text{LF}=0.15$ and $X = 1.3$ at $\text{LF}=0.20$) | Invalid if drainage is impeded (clay Vertisols with $\text{LF} < 0.10$), if capillary rise occurs, or under 450–550 mm sub-humid Guelma winter rainfall that leaches surface salts seasonally. |
| **$\text{EC}_a$** | Bulk apparent soil electrical conductivity (`dS/m`) | Depends nonlinearly on water content, clay mineralogy, CEC, and bulk density | Must NOT be compared directly against $\text{EC}_e$ Maas-Hoffman curves without site calibration. |
| **$\text{TDS}$ (`g/L`)** | Total dissolved solids concentration in water or extract (`g/L` or `mg/L`) | Approximate freshwater/mixed-ion heuristic: $1\ \text{dS/m} \approx 640\ \text{mg/L} = 0.64\ \text{g/L}$ (rising toward `0.75–0.80 g/L` in Ca/SO4-rich brines) | `ITCMI` (`SRC-06`) reports **`1.92–3.2 g/L`** for tomato and **`1.9–3.2 g/L`** for potato, explicitly paired with **`3–5 mmhos/cm (dS/m)`** in ITCMI tables — i.e., **TDS-converted `3–5 dS/m`**, not `1.9–3.2 dS/m`! |

> [!CAUTION]
> **Direct Audit Finding — Seybouse Basin Water ($\text{EC}_w$) vs Crop Soil Thresholds ($\text{EC}_e$):**
> `SRC-03` (Bouchemal et al., 2024, `DOI:10.1007/s11356-024-32716-0`) measures Seybouse groundwater **`ECw` up to `4.21 dS/m`** (`Na+` up to `684.7 mg/L`, `Cl-` up to `980 mg/L`) and `SRC-04` (Kouadra et al., 2026, `DOI:10.1038/s41598-026-51852-w`) measures river **$\text{EC}_w$** and **SAR** sodicity hazard (`Na+/Ca2+/Mg2+` dispersion on Guelma clay soils). Phase R0.3 improperly cited `SRC-03;SRC-04` as `LOCAL_VALIDATED` support inside **`TOMATO_IND::soil_salinity_ece_threshold_dsm`** (`L270`), even though **neither paper reports tomato yield trials or root-zone $\text{EC}_e$ thresholds in Guelma**!

Under FAO-29 Table 3 steady-state irrigation without winter rainfall leaching ($\text{LF}=0.15\text{–}0.20$), irrigating with **`ECw = 4.21 dS/m`** would push equilibrium root-zone **`ECe` toward `~5.5–6.7 dS/m`** — far above FAO-29 thresholds for faba bean (`1.6 dS/m`), potato (`1.7 dS/m`), lentil (`1.7 dS/m`), chickpea (`1.9 dS/m`), and processing tomato (`2.5 dS/m`), and even encroaching on durum wheat (`5.7–5.9 dS/m`). Conversely, winter cereals receiving 450–550 mm sub-humid Guelma winter rain and supplemental irrigation follow a transient salt balance governed by winter leaching fraction, clay drainage, and $\text{Na}^+$/SAR permeability hazard rather than steady-state summer $\text{EC}_e = 1.5\,\text{EC}_w$.

---

## 2. Specific Provenance & Numeric Errors Identified in Phase R0.3

1. **`TOMATO_IND` False `LOCAL_VALIDATED` Reclassification:** Matrix line L270 (`R0_3_AGRONOMIC_EVIDENCE_MATRIX.csv`) claimed `LOCAL_VALIDATED` by pooling FAO-29 (`ECe = 2.5 dS/m`, `b = 9.9%`), secondary ITCMI (`1.92–3.2 g/L`), and Seybouse water chemistry (`SRC-03/04`). Reclassified to **`CONFLICTING_EVIDENCE`** scientifically and **`INTERNATIONAL_REFERENCE` / `CONFLICTED`** (`LOW` confidence) in [R0_3_1_CORRECTED_EVIDENCE_MATRIX.csv](file:///home/lokman/Desktop/FeildShit-SI-Model/docs/phaseR0_3_1/R0_3_1_CORRECTED_EVIDENCE_MATRIX.csv).
2. **`POTATO` Numeric Range Mixing (`1.7` to `3.2`):** Matrix line L302 entered `value_min = 1.7`, `value_max = 3.2`, directly mixing Maas-Hoffman/FAO-29 **`1.7 dS/m` ($\text{EC}_e$)** as the lower bound with ITCMI **`3.2 g/L` (TDS mass concentration `= ~5 dS/m` at `0.64 g/L per dS/m`)** as the upper bound! Verified ITCMI guides explicitly write **`1.9–3.2 g/L (= 3–5 mmhos/cm)`** without specifying whether `3–5 dS/m` denotes saturation-paste `ECe` or soil-solution/irrigation `ECw`.
3. **`OLIVE` Phantom `2.7 dS/m` Threshold & `5.0%` Slope Attribution Error:** Matrix L366–367 cite `SRC-25` (`FAO-29`) for **`ECe = 2.7 dS/m`** and **`5.0% / dS/m`** slope. Direct HTML inspection of live FAO-29 Table 4 ([T0234E03.htm](https://www.fao.org/4/T0234E/T0234E03.htm)) confirms **Olive (`Olea europaea`) is listed only qualitatively (`Moderately tolerant`) in FAO-29 Table 4 with ZERO numeric $a$ (`ECe`) threshold or $b$ slope!** Chartzoulakis (2005, `SRC-20`, `DOI:10.1016/j.agwat.2005.04.025`) documents wide cultivar and ion-specific (`Cl-`/`Na+`) spread (`~3.0–6.0 dS/m` soil/solution regimes across sensitive vs tolerant olive cultivars).
4. **Katerji Conversano Lysimeter Transferability (`CHICKPEA_*`, `LENTIL`):** Katerji et al. (2001, `SRC-18`, `DOI:10.1016/S0378-3774(00)00109-8` and `SRC-17`) measured legume `Ct = 1.7 dS/m` (lentil) and `1.9 dS/m` (chickpea) with extreme yield slopes (**`37%/dS/m`** chickpea, **`62%/dS/m`** lentil) in confined Mediterranean concrete lysimeters (`ECe` inferred from drainage/soil water extracts) irrigated with saline water `ECw = 2.0–3.8 dS/m`. Those confined-root slopes cannot be applied directly as open-field linear penalties on Guelma Vertisols.
5. **Unlinked `SRC-26` DOIs & `DURUM_WHEAT` / `SUNFLOWER`:** FAO-29 Table 4 lists Bread wheat (`6.0 dS/m`, `7.1%`) and Broadbean (`1.5–1.6 dS/m`, `9.6%`) verbatim, whereas **Durum wheat (`5.7–5.9 dS/m`, `3.8%`)**, **semi-dwarf Bread wheat (`8.6 dS/m`, `3.0%`)**, and **Sunflower (`4.8 dS/m`, `5.0%`)** derive from Maas/Francois (`SRC-26` external DOIs `10.2134/agronmonogr38.c3`, `agronj1986.00021962007800060023x`, `agronj1996.00021962008800020016x` — all omitted from `R0_3_SOURCE_REGISTER.md`). Moreover, `SUNFLOWER` conflicts directly between Francois (1996) field plots (`4.8 dS/m`) and early-stage/Katerji reports (`1.2–1.7 dS/m`).
6. **Faba Bean Nodulation Constraint (`SRC-19`):** Abdelly et al. (`SRC-19`, verified `DOI:10.1016/S0378-3774(01)00114-7`) show that salinity severely inhibits faba bean symbiotic $\text{N}_2$ fixation and pod fill around **`ECe ~1.5 dS/m`**, confirming why salinity cannot be separated from legume BNF credits.
7. **Complete Runtime Sensor Absence:** SoilGrids 250 m has **no salinity or EC band**, and the HTTP API (`FieldAnalyzeRequest`) accepts **no soil `ECe`, irrigation `ECw`, or water `SAR`**. `local_hydrology_inputs` is Python-only and omitted from REST endpoints.

---

## 3. Per-Crop ECw / ECe Status Matrix (All 13 Profiles)

| Crop Profile | Threshold & Slope in `R0.3` Matrix | Primary Verified Basis | Audit C Salinity Status | Matrix Readiness & Rationale |
|---|---|---|---|---|
| **DURUM_WHEAT** | `ECe = 5.7–5.9 dS/m`; slope `3.8%/dS/m` | `ECe` saturation paste (Francois et al. 1986; Katerji 2005) | **`ECe_THRESHOLD_VERIFIED`** *(citation repair needed)* | `REFERENCE_ONLY` (`MEDIUM`) — `SRC-26/17` omit DOIs in R0.3; parcel `ECe` unmeasured in engine. |
| **SOFT_WHEAT** | `ECe = 6.0 dS/m` (`8.6` semi-dwarf); slope `7.1%` (`3.0%` semi-dwarf) | `ECe` FAO-29 Table 4 (`6.0 / 7.1%` verbatim); Francois 1994 (`8.6 / 3.0%`) | **`ECe_THRESHOLD_VERIFIED`** *(standard cultivar verbatim; semi-dwarf variant requires DOI split)* | `REFERENCE_ONLY` (`MEDIUM`) — two cultivar series packed into `unit`; parcel `ECe` unmeasured. |
| **BARLEY** | `ECe = 8.0 dS/m`; slope `5.0%/dS/m` | `ECe` FAO-29 Table 4 verbatim (`8.0 / 5.0%`) | **`ECe_THRESHOLD_VERIFIED`** | `REFERENCE_ONLY` (`HIGH` source confidence) — verbatim FAO-29 `ECe` benchmark, held pending parcel `ECe`/`ECw` inputs. |
| **FABA_BEAN** | `ECe = 1.5–1.6 dS/m`; slope `9.6%/dS/m` | `ECe` FAO-29 Table 4 (`1.6 / 9.6%`) + `SRC-19` (`1.5 dS/m`) | **`ECe_THRESHOLD_VERIFIED`** | `REFERENCE_ONLY` (`HIGH` source confidence) — verified `ECe` + BNF sensitivity; blocked on missing parcel `ECe`/`ECw`. |
| **CHICKPEA_WINTER** | `ECe = 1.9 dS/m`; slope `37.0%/dS/m` | Lysimeter `ECe` (`SRC-17`, Katerji et al. Conversano) | **`BASIS_UNCLEAR`** *(threshold lysimeter `ECe`, slope tank artifact)* | Threshold `REFERENCE_ONLY` (`MEDIUM`); Slope `LOCAL_CALIBRATION_REQUIRED` (`LOW`) — `37%/dS/m` lysimeter slope non-transferable to field. |
| **CHICKPEA_SPRING** | `ECe = 1.9 dS/m`; slope `37.0%/dS/m` | Lysimeter `ECe` (`SRC-17`, Katerji et al. Conversano) | **`BASIS_UNCLEAR`** *(same non-split lysimeter basis as winter chickpea)* | Threshold `REFERENCE_ONLY` (`MEDIUM`); Slope `LOCAL_CALIBRATION_REQUIRED` (`LOW`). |
| **LENTIL** | `ECe = 1.7 dS/m`; slope `62.0%/dS/m` | Lysimeter `ECe` (`SRC-18`, Katerji et al. 2001 `10.1016/S0378-3774(00)00109-8`) | **`ECe_THRESHOLD_VERIFIED`** *(lysimeter `ECe` verified `1.7`, `62%` slope tank-confined)* | Threshold `REFERENCE_ONLY` (`MEDIUM`); Slope `LOCAL_CALIBRATION_REQUIRED` (`LOW`). |
| **VETCH_OAT** | `3.0–5.0 dS/m`; slope `11–45%` | Common vetch `ECe = 3.0 dS/m` in FAO-29 Table 4; Oats missing numeric $a/b$ | **`BASIS_UNCLEAR`** *(mixed species estimate)* | `LOCAL_CALIBRATION_REQUIRED` (`LOW`) — intercrop vetch:oat botanical ratio dictates community tolerance. |
| **TOMATO_IND** | `2.5 dS/m` + ITCMI `1.92–3.2 g/L` + Seybouse `ECw 4.21 dS/m` | FAO-29 Table 4 (`2.5 ECe`, `9.9%`); ITCMI `g/L` (`3–5 dS/m` equiv); Seybouse water `ECw` | **`CONFLICTING_EVIDENCE`** | `CONFLICTED` (`LOW`) — mixes `ECe`, unclarified `g/L` (`~3–5 dS/m`), and untreated Seybouse water `ECw`. |
| **POTATO** | `1.7–3.2` (`1.7` Maas `ECe` vs `1.9–3.2 g/L` ITCMI); slope `12.0%` | FAO-29 Table 4 (`1.7 ECe`, `12.0%`) mixed directly with ITCMI `g/L` (`= 3–5 dS/m`) | **`CONFLICTING_EVIDENCE`** | `CONFLICTED` (`LOW`) — heterogeneous scalar mixing `dS/m ECe` and `g/L TDS` in `[min..max]`. |
| **SUNFLOWER** | `1.2–4.8 dS/m`; slope `5.0%` | Francois (1996) field `ECe = 4.8 dS/m` vs `1.2–1.7` sensitive phase literature | **`CONFLICTING_EVIDENCE`** | `CONFLICTED` (`MEDIUM`) — emergence vs late-season field tolerance unresolved. |
| **OLIVE** | `2.7–6.0 dS/m`; slope `5.0%` (`SRC-25`) | **Erroneous FAO-29 citation** (`2.7`/`5.0%` absent from Table 4); Chartzoulakis `3–6 dS/m` (`SRC-20`) | **`CONFLICTING_EVIDENCE`** | `CONFLICTED` (`LOW`/`MEDIUM`) — untraced `2.7 dS/m` & cultivar-specific $\text{Cl}^-/\text{Na}^+$ toxicity (`SRC-20`). |
| **BARE_FALLOW** | `NOT_APPLICABLE` | Capillary wicking warning only | **`NOT_AVAILABLE`** *(non-crop fallow state)* | `NOT_AVAILABLE` (`NONE`). |

---

## 4. Safe Design Guardrails Before Any Salinity Implementation (`R0.4` Prerequisites)

1. **Strict Schema Separation:** Never accept a single overloaded salinity field. Any future farmer/lab schema (`TIER_B_05` reformulated) MUST separate:
   - `soil_ece_dsm` (`dS/m`, saturation paste extract at 25 °C)
   - `irrigation_ecw_dsm` (`dS/m`, irrigation water conductivity)
   - `irrigation_sar` (`(mmol/L)^0.5` sodicity hazard alongside `water_cl_mg_l`)
   - `drainage_or_leaching_regime` (rainfall winter leaching vs impeded Vertisol drainage)
2. **Prohibit Direct $\text{EC}_w \rightarrow \text{EC}_e$ Comparison:** Water **`ECw`** from Seybouse (`SRC-03/04`) MUST NOT be evaluated directly against FAO-29 **`ECe`** thresholds without an explicit leaching-fraction/soil-drainage conversion model and rainfall dilution adjustment.
3. **Hold FAO-29 Thresholds at `REFERENCE_ONLY` Until Input Capture Exists:** Although **`BARLEY` (`8.0/5.0`), `FABA_BEAN` (`1.5–1.6/9.6`), `SOFT_WHEAT` (`6.0/7.1` standard), and `DURUM_WHEAT` (`5.7–5.9/3.8`)** have verified $\text{EC}_e$ scientific baselines, the runtime engine currently has zero `ECe`/`ECw` data on disk or HTTP input — blocking active numerical gating (`BLOCKED_BY_LOCAL_DATA` for automated rules).
