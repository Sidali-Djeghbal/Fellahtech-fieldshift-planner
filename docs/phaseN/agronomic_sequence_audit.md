# Phase N — Agronomic Sequence Audit & Scoring Bugfix Report

## 1. Audit of `SEQ_04_PULSE_BROOMRAPE_BREAK` (`FABA_BEAN -> DURUM_WHEAT -> CHICKPEA_WINTER`)

### KB Provenance Check ([`agronomic_knowledge/crop_profiles.json`](file:///home/lokman/Desktop/FeildShit-SI-Model/agronomic_knowledge/crop_profiles.json))
- `FABA_BEAN`: `min_return_break_years = 3`, `recommended_return_break_years = 4`; `key_hazards = ['Orobanche crenata (broomrape)', 'Botrytis chocolate spot', 'Ascochyta fabae']`.
- `CHICKPEA_WINTER`: `min_return_break_years = 3`; `key_hazards = ['Ascochyta rabiei blight', 'Fusarium wilt']`.
- Pathogenic nuance: `Ascochyta fabae` and `Ascochyta rabiei` are largely host-specific between *Vicia faba* and *Cicer arietinum*, whereas shared generalist soil/stubble risks (*Sclerotinia*, *Fusarium* wilt pressure) and Mediterranean *Orobanche crenata* pressure on consecutive-cycle legume intensifications justify extending break intervals beyond 2 years when feasible.

### Implemented Alignment ([`sequence_compatibility.json`](file:///home/lokman/Desktop/FeildShit-SI-Model/agronomic_knowledge/sequence_compatibility.json) & [`constraint_engine.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/src/agronomic/constraint_engine.py))
- **Hard `FAIL` (`rule_tier = "HARD_FAIL_SAME_PULSE_OR_OROBANCHE"`):** Same legume genus (`FABA_BEAN <-> FABA_BEAN`, `CHICKPEA_* <-> CHICKPEA_*`, `LENTIL <-> LENTIL`) or shared acute broomrape susceptibility (`FABA_BEAN <-> LENTIL`) within `< 3` seasons.
- **Soft `WARNING` (`rule_tier = "SOFT_WARNING_CROSS_PULSE_2YR"`, `kb_provenance_verified = True`):** Cross-genus pairing (`FABA_BEAN -> DURUM_WHEAT -> CHICKPEA_WINTER`, interval = `2`) remains conditionally feasible with structured metadata (`short_pulse_pairs`, advisory to verify clean *Orobanche*/*Fusarium* history and extend break toward 3–4 years) and carries the Phase I soft warning penalty (`-0.12` in `pest_disease_disruption`).

---

## 2. Audit of `SEQ_06_VETCH_OAT_ROLE_AND_REPEAT` (`VETCH_OAT -> DURUM_WHEAT -> VETCH_OAT`)

### KB Provenance & Dual Botanical Role
- `VETCH_OAT` in `crop_profiles.json` has `botanical_family = "Mixed_Fabaceae_Poaceae"`, **`min_return_break_years = 2`**, and explicit hazard note: *"Oat component maintains partial Poaceae disease host if oat-heavy; avoid continuous consecutive Vetch-Oat."*
- **Agronomic nuance:**
  1. `VETCH_OAT -> DURUM_WHEAT -> VETCH_OAT` has a `2`-season interval (`slot 3 - slot 1 = 2 == min_return_break_years`), which satisfies `< 2`-year exclusion while sitting right on the 2-year frequent repeat threshold.
  2. Unlike continuous grain cereals (`SEQ_02`), Vetch-Oat is harvested green for hay in April–May *before* wild-oat / ryegrass seed shed if cut on schedule; however, frequent 2-year cycling around Durum Wheat requires strict **oat proportion control (`<= 35%`)**, **timely pre-seed-shed mowing**, and recognition that **off-field hay baling exports shoot biomass N** rather than plowing all biologically fixed N back into topsoil.

### Implemented Refinement
- [`constraint_engine.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/src/agronomic/constraint_engine.py):
  - Single occurrence per timeline (`SINGLE_BREAK`) → `PASS`.
  - 2-year repeat around cereal (`interval <= 2`, `repeat_mode = "FREQUENT_2YR_CYCLE"`) → `WARNING` with explicit oat-share, pre-seed hay cut, and N-export caution.
  - Consecutive (`VETCH_OAT -> VETCH_OAT`, `repeat_mode = "CONSECUTIVE_1YR"`) → `WARNING` (`< 2 yr break`).
- [`scoring_engine.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/src/optimization/scoring_engine.py):
  - `_eval_pest_disease_disruption` applies `-0.12` for `CONSECUTIVE_1YR` (< 2 yr break) and a proportional `-0.04` management caution for `FREQUENT_2YR_CYCLE` (avoiding artificially equating timely green hay cycles with continuous grain monoculture while flagging the warning transparently).
  - `_eval_nitrogen_contribution` explicitly documents off-field hay baling N-export variability in `missing_information` whenever `"VETCH_OAT"` appears.

---

## 3. Silent Integration Bugfixes & Regional Water Calibration Discovered in Audit

1. **Fixed Dead `SEQ_07` Transition Key in `scoring_engine.py`:** `_eval_nitrogen_contribution` previously looked up `obs07.get("beneficial_transitions")`, whereas `constraint_engine.py` emitted `obs07["transitions"]`, silently zeroing out the `+0.06/transition` legume-to-cereal carry-over bonus across every rotation. Fixed to `obs07.get("transitions") or obs07.get("beneficial_transitions")`.
2. **Fixed Dead Equipment Rule Name in `scoring_engine.py`:** `_eval_farmer_priority_fit` previously looked up `"RULE_EQUIPMENT_COMPATIBILITY"`, whereas `constraint_engine.py` emits `"RULE_EQUIPMENT_CONSTRAINT_CHECK"`, silently treating all equipment checks as `"UNKNOWN"`. Fixed to look up `"RULE_EQUIPMENT_CONSTRAINT_CHECK"` first, restoring real penalties on conflicting implements (e.g., `no_precision_planter` on Sunflower/Tomato).
3. **Humid-Regime Drought Bonus Taper (`_eval_water_efficiency`):** Previously, `cat_bonus = 0.15` for `RAINFED_SEMI_ARID_TOLERANT` applied unconditionally at all rainfall levels, capping Durum Wheat + Faba Bean at `0.95` vs `1.00` for Barley + Chickpea even under `580–617 mm` irrigated northern Bouchekouf plains—which was exposed once `STRAT_CEREAL_FORAGE` received its `SEQ_06` warning. Tapering `cat_bonus` smoothly from `0.15 -> 0.05` over `500..600 mm` preserves full drought priority under dry/semi-arid conditions (`<= 500 mm`) while allowing humid conservation rotations (`STRAT_SOIL_IMPROVEMENT`: `FABA_BEAN -> DURUM_WHEAT -> VETCH_OAT`) to rank ahead cleanly in wet northern valleys.
