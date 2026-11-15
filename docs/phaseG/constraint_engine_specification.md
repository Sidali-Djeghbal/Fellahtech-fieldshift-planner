# Phase G — Agronomic Constraint Engine Specification

**Module:** [src/agronomic/constraint_engine.py](file:///home/lokman/Desktop/FeildShit-SI-Model/src/agronomic/constraint_engine.py)  
**Knowledge Schemas:** [crop_profiles.json](file:///home/lokman/Desktop/FeildShit-SI-Model/agronomic_knowledge/crop_profiles.json), [constraint_rules.json](file:///home/lokman/Desktop/FeildShit-SI-Model/agronomic_knowledge/constraint_rules.json), [sequence_compatibility.json](file:///home/lokman/Desktop/FeildShit-SI-Model/agronomic_knowledge/sequence_compatibility.json)

---

## 1. Architecture & Non-Goals

The Constraint Engine sits directly between **Field Profile Assembly** (Phase F) and the future **Crop Rotation Optimizer** (Phase H+). Its strict function is **deterministic feasibility filtering and multi-rule traceability**—it does **not** enumerate all rotations, rank competing strategies economically, or impute missing field parameters.

### Core API

1. `load_knowledge_base() -> AgronomicKnowledgeBase`: Cached deterministic loader reading Phase G JSON artifacts.
2. `evaluate_crop_for_field(field_profile, crop_id, target_season=None, kb=None) -> Dict`: Evaluates all `15` rules in [constraint_rules.json](file:///home/lokman/Desktop/FeildShit-SI-Model/agronomic_knowledge/constraint_rules.json) for one candidate crop against one Field Profile.
3. `evaluate_all_crops_for_field(field_profile, target_season=None, kb=None) -> Dict`: Evaluates all `13` inventory crops without scoring or optimization ranking.
4. `evaluate_crop_sequence(field_profile, sequence_crops, slot_seasons=None, kb=None) -> Dict`: Evaluates `2–4` crop sequences by combining per-slot single-crop field checks with the `10` sequence rules in [sequence_compatibility.json](file:///home/lokman/Desktop/FeildShit-SI-Model/agronomic_knowledge/sequence_compatibility.json), anchored onto resolved recent `crop_history`.

---

## 2. Rule Evaluation Contract & Hard/Soft Feasibility Semantics

Every evaluated rule produces a frozen `RuleEvaluation` record with:
- `rule_id`, `domain`, `source`, `uncertainty_note`, `observed_inputs`
- `evidence_classification` strictly in `{HARD_CONSTRAINT, SOFT_CONSTRAINT, EXPERT_ASSUMPTION, UNKNOWN}`
- `status` strictly in `{PASS, WARNING, FAIL, UNKNOWN}`

### Feasibility Decision Table (`feasible` & `feasibility_status`)

| Condition Evaluated Deterministically | `feasible` | `feasibility_status` | Behavior |
|---|---:|---|---|
| Any `HARD_CONSTRAINT` has `status == "FAIL"` | `False` | `INFEASIBLE_HARD_CONSTRAINT` | Blocks candidate crop or sequence (e.g., rainfed `TOMATO_IND`, `OLIVE`, `>=3` consecutive cereals, `TOMATO -> POTATO`, `<3 yr` pulse repeat). |
| No hard fails, but any `HARD_CONSTRAINT` has `status == "UNKNOWN"` | `False` | `UNVERIFIED_HARD_UNKNOWN` | **Never auto-passed** (e.g., `TOMATO_IND` / `POTATO` when `water.availability == "unknown"` or `irrigation_system == "unknown"`). |
| Non-hard constraint has `status == "FAIL"` | `False` | `INFEASIBLE_CONSTRAINT` | Blocks extreme biological mismatch (e.g., pH outside biological survival bounds). |
| No fails & no hard unknowns, but any `WARNING` or non-hard `UNKNOWN` | `True` | `CONDITIONALLY_FEASIBLE_WITH_WARNINGS_OR_UNKNOWNS` | Permitted conditionally while surfacing explicit agronomic hazards and unresolved local checks (missing DEM, unmeasured `ECe`, missing `forage_value_weight`, `SOC-NaN`). |
| Zero `FAIL`, zero `WARNING`, zero `UNKNOWN` | `True` | `FEASIBLE_PASS` | Clean feasibility verified against all active inputs. |

---

## 3. Single-Crop Rule Inventory (`15` Rules)

- **Hard Gates (`3`):** `RULE_PERENNIAL_EXCLUSION`, `RULE_PLANTING_SEASON_COMPATIBILITY`, `RULE_WATER_IRRIGATION_GATE`.
- **Soft Constraints (`9`):** `RULE_PRECIPITATION_REGIME` (dual GPM low vs NASA POWER high bounds, CON_06), `RULE_THERMAL_HEAT_FROST` (CON_07), `RULE_ROOTZONE_SOIL_MOISTURE_CONTEXT` (SMAP 11 km CON_08), `RULE_SOIL_TEXTURE_WORKABILITY` (SoilGrids 250 m clay CON_01), `RULE_SOIL_PH_SUITABILITY` (CON_02), `RULE_SOIL_SOC_PRIORITY` (CON_03), `RULE_CROPLAND_VEG_CONTEXT` (CropFreq 2021–2025 + S2 2024-03 + MODIS CON_09), `RULE_HYPOTHESIS_LOCAL_EVIDENCE_STATUS` (`POTATO`/`SUNFLOWER`), `RULE_EQUIPMENT_CONSTRAINT_CHECK` (`NOT_PROVIDED` -> `UNKNOWN`, `[]` -> `PASS`).
- **Expert Assumptions (`2`):** `RULE_DEM_DRAINAGE_UNCERTAINTY` (returns `UNKNOWN` for drainage-sensitive crops while DEM is absent locally), `RULE_FORAGE_REQUIREMENT_ALIGNMENT` (`NOT_PROVIDED` -> `UNKNOWN`, `0.0` or explicit value -> evaluated cleanly).
- **Unknown Local Evidence Gate (`1`):** `RULE_SALINITY_UNMEASURED_IRRIGATION` (returns `UNKNOWN` on irrigated fields lacking local `ECe`/`ECw` data).
- **Quarantined Input Enforcement:** `soilgrids_v6.nitrogen_0_30cm` is never read in rule thresholds and is tagged `quarantined_excluded` on every engine response.

---

## 4. Empirical Rule Outcome Counts (Phase G Verification Scenarios)

| Benchmark Scenario | Crops Evaluated | `PASS` | `WARNING` | `FAIL` | `UNKNOWN` | `INFEASIBLE` Crops |
|---|---:|---:|---:|---:|---:|---|
| `BOUMAHRA_IRRIGATED_DRIP` (`moderate/reservoir/drip`, Winter vs crop season) | `13` (`15` rules each = `195`) | `152` | `23` | `2` | `18` | `1` (`OLIVE`) |
| `BOUMAHRA_RAINFED` (`limited/rainfed/none`, `clay=33.0%`) | `13` (`195`) | `157` | `25` | `4` | `9` | `3` (`TOMATO_IND`, `POTATO`, `OLIVE`) |
| `TAMLOUKA_RAINFED` (`limited/rainfed/none`, `clay=29.8%`, GPM `440` vs POWER `508 mm`) | `13` (`195`) | `163` | `19` | `4` | `9` | `3` (`TOMATO_IND`, `POTATO`, `OLIVE`) |

Example `3`-year sequence evaluations on `BOUMAHRA_IRRIGATED_DRIP` (prior `2024 = Barley`):
- `["FABA_BEAN", "DURUM_WHEAT", "VETCH_OAT"]` -> Sequence transition rules: `PASS=6, WARNING=0, FAIL=0, UNKNOWN=0` (`CONDITIONALLY_FEASIBLE_WITH_WARNINGS_OR_UNKNOWNS` overall due to missing plot DEM & unmeasured `ECe`).
- `["DURUM_WHEAT", "DURUM_WHEAT", "BARLEY"]` -> `INFEASIBLE_HARD_CONSTRAINT` (`SEQ_02_CEREAL_REPETITION = FAIL`: `>= 3` consecutive cereals).
- `["TOMATO_IND", "POTATO", "DURUM_WHEAT"]` -> `INFEASIBLE_HARD_CONSTRAINT` (`SEQ_03_SOLANACEAE_BREAK = FAIL`).
- `["DURUM_WHEAT", "OLIVE", "FABA_BEAN"]` -> `INFEASIBLE_HARD_CONSTRAINT` (`SEQ_01_PERENNIAL_GUARD = FAIL`, `OLIVE::RULE_PERENNIAL_EXCLUSION = FAIL`).
