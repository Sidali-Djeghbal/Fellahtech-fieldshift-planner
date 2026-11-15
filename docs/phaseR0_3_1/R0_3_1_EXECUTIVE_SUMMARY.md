# Phase R0.3.1 — Scientific Evidence Quality Audit Executive Summary

**Target System:** Field Shift — Deterministic, Explainable Crop Rotation Decision-Support System (Guelma Wilaya, Algeria)  
**Scope:** Independent scientific audit of all **34 sources**, **416 evidence matrix records**, **25 geospatial-to-requirement domains**, **salinity (`ECw/ECe`) claims**, **high-impact agronomic parameters**, and **18 documented calibration candidates** produced in Phase R0.3. No production code, JSON profiles, rules, weights, or Phase P–R0.3 files were altered.

---

## 1. Key Numerical Findings Before vs After Audit

| Audit Dimension | Phase R0.3 Claimed | **Phase R0.3.1 Verified After Audit** | Primary Scientific Cause of Adjustment |
|---|---|---|---|
| **Sources (`SRC-01..34`, total `34`)** | All `34` treated as valid citations | **`12`** `VERIFIED_PRIMARY_SOURCE`, **`2`** `VERIFIED_INSTITUTIONAL_SOURCE`, **`1`** `VERIFIED_SECONDARY_SOURCE`, **`15`** `PARTIALLY_VERIFIED`, **`2`** `UNVERIFIED`, **`2`** `INVALID_OR_MISMATCHED` | `SRC-34` synthetic summary (`0` DOIs), `SRC-33` unlinked pathology bucket (`0` DOIs), `SRC-16` wrong DOI (`Kassam 2012`), `SRC-14` misattributed press quote, broken FAO-33/66 URLs, wrong author/year in `SRC-12` & `SRC-31`. |
| **`LOCAL_VALIDATED` Matrix Rows (`416`)** | **`3`** (`TOMATO_IND` salinity, pathogens, machinery) | **`0` (`0.0%`)** | Seybouse water **$\text{EC}_w$** (`4.21 dS/m`) ≠ crop root-zone **$\text{EC}_e$**; Assassi (`SRC-01/02`) covers land leasing only (NOT tomato pathogens); `L286` holds DSA `800 qx/ha` yield quotes citing wrong `SRC-14`. |
| **Evidence Tier Reclassification (`416`)** | `INTL=248, ALG=66, MED=36, EST=9, NA=54, LOCAL=3` | **`INTL=199, NA=66, EST=60, ALG=56, MED=35, LOCAL=0`** | `48` sole-`SRC-34` + `6` sole-`SRC-33` rows + `4` `SRC-14` citations demoted to `GENERAL_ESTIMATE`; un-cited `NOT_APPLICABLE` rows standardized to `NOT_AVAILABLE`; manual citations claiming regional trials returned to `INTERNATIONAL_REFERENCE`. |
| **Confidence Distribution (`416`)** | **`267` `HIGH`** (`64.2%`), `85` `MEDIUM`, `10` `LOW`, `54` `NONE` | **`26` `HIGH` (`6.3%`)**, `188` `MEDIUM`, `136` `LOW`, `66` `NONE` | Downgraded all `44` `HIGH` claims built on synthetic `SRC-34`, `23` built on unverified `SRC-33`, `3` on `SRC-14`, `9` on wrong-DOI `SRC-16`, plus secondary/uncalibrated transfer parameters. |
| **Implementation Readiness (`416`)** | *(not classified in R0.3)* | **`14` `IMPLEMENTATION_READY` (`3.4%`)**, `151` `REFERENCE_ONLY`, `111` `LOCAL_CALIBRATION_REQUIRED`, `24` `CONFLICTED`, `116` `NOT_AVAILABLE` | Only clean scalars backed by verified primary/institutional sources with zero local/basis blockers pass (`11` FAO-56 Table 22 `depletion_p` values `SRC-22` + `3` cereal zero symbiotic N credits `SRC-30`). |
| **Calibration Candidates (`18` documented; `19` matrix flags)** | All listed toward R0.4 (`8` Tier A, `6` Tier B, `4` Tier C) | **`2` `APPROVE_FOR_DESIGN`**, **`4` `REQUIRES_MORE_EVIDENCE`**, **`8` `BLOCKED_BY_LOCAL_DATA`**, **`4` `REJECT_OR_REFORMULATE`** | Caught verified FAO-56 `Zr` misquotes in `CAND-05`, mixed BNF/NPK units & Unkovich `2008->2010` error in `CAND-04`, `SRC-34` dominance in `CAND-07`, `ECw->ECe` conflation in `TIER_B_05`, and confirmed matrix `19th` flag (`SUNFLOWER` `L341`) is a `ETc` vs rainfed floor category error. |

---

## 2. Critical Scientific Errors Uncovered by This Audit

1. **False High-Confidence Foundation Built on Unverified Sources (`SRC-34` & `SRC-33`):** `66` thermal rows rely on synthetic placeholder **`SRC-34`** (`48` as sole source, `44` labeled `HIGH`) and `24` pathology/scab rows rely on anonymous bucket **`SRC-33`** (`23` labeled `HIGH`). Neither has DOIs, URLs, or verifiable experimental data.
2. **Wrong DOIs, Broken FAO URLs & Attribution Errors:** **`SRC-16`** cites Kassam et al. (`10.1016/j.fcr.2012.02.023`) instead of Mrabet et al. (`10.1016/j.fcr.2011.11.017`); **`SRC-31`** attributes Unkovich et al. **2010** (`10.1007/s11104-009-0136-5`) root factors (`1.56`, `1.82`) to 2008 ACIAR MN136; **`SRC-12`** omits first author **Guetteche** (`2022/2023`); **`SRC-23`** (`s2022e` = Training Manual 3) & **`SRC-24`** (`404`) point to wrong/dead FAO pages; **`SRC-14`** misattributes external *El Watan/L'Expression* DSA yields (`800 qx/ha`) to internal repo docs.
3. **Verbatim Misquotations of FAO-56 Table 22 & FAO-29 Table 4 (`CAND-05` Danger):**
   - Primary FAO-56 Table 22 (`x0490e0e.htm`) reports **`Chick pea Zr = 0.6–1.0 m`** (`Fababean Dry = 0.5–0.7 m`, `Lentil = 0.6–0.8 m`). Phase R0.3 and `CAND-05` misquoted FAO-56 as `Chickpea 0.9–1.5 m`, `Faba 0.6–0.9 m`, `Lentil 0.6–1.0 m` — which would corrupt accurate existing Chickpea KB bounds (`0.6–1.0 m`) if implemented unverified!
   - Primary FAO-29 Table 4 (`T0234E03.htm`) has **NO numeric `a/b` salinity threshold (`2.7 dS/m`, `5.0%`) for `OLIVE`** — contrary to matrix L366–367 citing `SRC-25`.
   - `ITCMI` (`SRC-06`) `1.9–3.2 g/L` explicitly maps to **`3–5 mmhos/cm (dS/m)` TDS-converted**, yet `POTATO L302` (`1.7..3.2`) mixes `1.7 dS/m ECe` with `3.2 g/L` in one numeric interval.
4. **Salinity (`ECw` vs `ECe`) & N-Balance (`Gross BNF` vs `Net Credit`) Conflation:** Direct comparison of Seybouse river/groundwater **$\text{EC}_w$** (`SRC-03/04`, up to `4.21 dS/m`) against Maas-Hoffman root-zone **$\text{EC}_e$** violates FAO-29 Table 3 leaching assumptions (`1.5×` only at $\text{LF}=0.15\text{–}0.20$). Likewise, gross pulse BNF cannot be converted to succeeding N credits without subtracting high grain N export (`SRC-30` Liu et al. 2019/2024).
5. **Schema Concatenation Inside Matrix Numeric Bounds:** Four multi-metric fields (`nutrient_uptake_npk_kg_t`, `fertilizer_rec_algeria_kg_ha`, `forage_nutritive_value`, `algerian_costs_prices_context`) pack incompatible nutrients/prices/costs (`DA/q` + `DZD/ha`; `% CP` + `% NDF`; `N` + `K2O`) into one `[value_min..value_max]` interval, while `BARE_FALLOW L396/400/405` and `TOMATO_IND L286` store metrics in incompatible parameter slots.

---

## 3. Decision-Engine Verdict on Readiness for Phase R0.4 (Model Design)

> [!IMPORTANT]
> **Audit Decision: DO NOT proceed directly into broad agronomic parameter or scoring redesign (`CAND-04, CAND-05, CAND-07`, `TIER_B_01..06`).**  
> **Phase R0.4 MUST operate on a strictly scoped two-track mandate:**
> - **Track 1 (Safe Immediate R0.4 Design Candidates — Low Scientific Risk):**
>   1. **`CAND-02` (Scoped Redesign):** Reframe `POTATO` `ph_0_30cm >= 6.5` output semantics from naive incompatibility into a calcareous scab-management advisory and restore downstream `tol_max` execution cleanly.
>   2. **`CAND-03` (Parity Fix):** Map `CHICKPEA_WINTER` `no_sprayer` consistently with existing Ascochyta spraying text in `crop_profiles.json` (plus isolated code/schema hygiene: clean unused `REM-01/02/03` keys, align `SMAP 0.20 vs 0.21` doc/spec defect, resolve `BARLEY 8.0 < wheat 8.5` inversion and null pH fallback documentation, and split matrix/KB future schemas into atomic scalar properties).
> - **Track 2 (Blocked Until P0/P1 Scientific & Data Prerequisites Clear):**
>   Hold ALL continuous hydrological (`FAO-56`/`ET0`), thermal (`GDD`/`frost`/`heat`), nitrogen-budget (`CAND-04`), salinity-gating (`TIER_B_05`/`CAND-08`), clay/DEM (`TIER_B_01`), and economic (`TIER_B_04`/`TIER_C_01`) model changes until verified primary replacements for `SRC-33`/`SRC-34`, repaired FAO-56/FAO-29/Unkovich 2010/Mrabet 2012 citations, and upstream `DEM` / `WS2M` / typed lab input schemas (`ECe, ECw, SAR, FC, PWP, CaCO3, Nmin`) are established.
