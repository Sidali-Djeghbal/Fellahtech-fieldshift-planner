# Phase H — Crop Rotation Candidate Generation Specification

**Project:** Field Shift — Guelma Wilaya Crop Rotation Decision-Support System  
**Module:** [`src/rotation/candidate_generator.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/src/rotation/candidate_generator.py)  
**Package Init:** [`src/rotation/__init__.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/src/rotation/__init__.py)  
**Schema Reference:** [`docs/phaseH/candidate_output_data_dictionary.csv`](file:///home/lokman/Desktop/FeildShit-SI-Model/docs/phaseH/candidate_output_data_dictionary.csv)

---

## 1. Scope & Architectural Boundaries

Phase H sits directly downstream of **Phase F (Field Profile Builder)** and **Phase G (Agronomic Knowledge Base & Constraint Engine)**, and directly upstream of **Phase I (Multi-Objective Ranking & Recommendation)**.

1. **Single-Field Architecture:** `generate_rotation_candidates(field_profile, config=None, kb=None)` operates strictly on one validated polygon `Field Profile` per invocation. Multi-polygon FeatureCollections are rejected upstream in [`field_profile_builder.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/field_profile_builder.py).
2. **Zero Phase I Ranking:** Phase H generates and evaluates diverse, agronomically structured rotation candidates. It does **not** assign overall composite scores or numeric rankings (`ranking_executed: false`). Candidate ordering reflects deterministic archetype order, not superiority.
3. **Strict Phase A–G Isolation:** Phase H reads Phase F Field Profiles and invokes Phase G functions (`load_knowledge_base`, `evaluate_all_crops_for_field`, `evaluate_crop_sequence`) via stable imports without modifying Phases A–G files.
4. **No Fabricated Facts or Hidden Unknowns:** Missing crop history, unmeasured soil salinity (`ECe`), missing DEM slope, and unknown water availability remain explicitly tracked as `UNKNOWN` or `NOT_PROVIDED` and are never coerced into `PASS` or invented historical sequences.

---

## 2. Inputs & Configuration

### 2.1 Primary Input: Phase F Field Profile
Consumed sections of `field_profile`:
- `section_a_farmer_provided`:
  - `field.field_id`, `field.field_name`
  - `water` (`availability`, `source`, `irrigation_system`)
  - `crop_history` (optional: `null` -> `NOT_PROVIDED`, `[]` -> `EXPLICITLY_CONFIRMED_EMPTY`, non-empty list -> chronological normalized history)
  - `planning` (`start_season`, `start_year`, `horizon_seasons` in `{2, 3, 4}`, optional `planting_month`)
  - `preferences` (optional: `target_crop_ids`, `excluded_crop_ids`, `equipment_constraints`, `forage_value_weight`, and other preference fields)
  - `input_completeness_flags` (`crop_history`, `preferences_block`, `equipment_constraints`, `forage_value_weight`)
- `section_b_extracted_geospatial`: SoilGrids 250 m soil attributes (`clay_0_30cm`, `ph_0_30cm`, `soc_0_30cm`, `cec_0_30cm`, `usda_texture_0_5cm`, quarantined `nitrogen_0_30cm`), GPM/SMAP climate & soil moisture, NASA POWER thermal/precipitation, MODIS NDVI, Sentinel-2 2024-03 snapshot & regional fallback, ESA 2021–2025 crop frequency, and `terrain_dem`.
- `section_d_quality_and_uncertainty`: mandatory SoilGrids vs laboratory caveat, regional climate vs field caveat, and missing values policy.

### 2.2 Configuration: `GenerationConfig`
Defined in [`candidate_generator.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/src/rotation/candidate_generator.py):
- `max_candidates: int = 8` — upper bound on deduplicated strategies returned per request.
- `min_history_entries_for_baseline: int = 2` — minimum resolved seasons within `(start_year - 4) .. (start_year - 1)` ending at `start_year - 1` required to emit `EXISTING_ROTATION_BASELINE`.
- `include_infeasible_existing_baseline: bool = True` — retains an infeasible historical baseline trace with full failure reasons (`EXISTING_BASELINE_EVALUATED`).
- `include_infeasible_requested_targets: bool = True` — emits a counterfactual candidate (`SELECTED_INFEASIBLE_COUNTERFACTUAL`) when a farmer requests a perennial or constraint-blocked crop such as `OLIVE` or rainfed `TOMATO_IND`.

---

## 3. Deterministic Generation Pipeline

### Step 1 — Horizon & Season Slot Evaluation Cache
- Enforces `2 <= planning.horizon_seasons <= 4` (raises `ValueError` otherwise).
- Calls Phase G `evaluate_all_crops_for_field(field_profile, target_season=s, kb=kb)` across `{start_season, "Winter", "Spring", "Autumn"}` to pre-cache single-crop suitability & planting-season compatibility without re-running geospatial logic.

### Step 2 — Crop History Sufficiency Assessment (`_assess_crop_history`)
- Sorts resolved entries chronologically by `(year, season_order)`.
- Extracts resolved crops inside `[start_year - 4, start_year - 1]` and locates the immediate predecessor `most_recent_predecessor` at `start_year - 1`.
- Marks `sufficient_for_existing_baseline = True` **only** when `len(recent) >= min_history_entries_for_baseline` **and** `most_recent_predecessor is not None`.
- When `crop_history` is `null`, `[]`, unmapped, or missing `start_year - 1`, `sufficient_for_existing_baseline = False`, no baseline is invented, and `SEQ_10_UNKNOWN_PREDECESSOR_GUARD` preserves `UNKNOWN`.

### Step 3 — Diverse Archetype Blueprint Synthesis (`_construct_pattern_sequences`)
Candidate synthesis generates distinct, non-repetitive crop sequences aligned to local Guelma agronomy while avoiding back-to-back cereal monoculture (including across the `T-1 -> T0` boundary) and `<3`-year same-pulse/broomrape collisions:

1. **`CEREAL_LEGUME` (`STRAT_CEREAL_LEGUME`)** — Alternates primary regional cereal (`DURUM_WHEAT`, or `BARLEY` where mean GPM precipitation < 460 mm/yr) with `N`-fixing food legumes (`FABA_BEAN`, `CHICKPEA_WINTER`, `LENTIL`, `CHICKPEA_SPRING`), prioritizing waterlogging-tolerant `FABA_BEAN` / `CHICKPEA_WINTER` on heavy clay soils (`>= 35%`) and Spring pulses when `start_season == "Spring"`.
2. **`CEREAL_FORAGE` (`STRAT_CEREAL_FORAGE`)** — Replaces fallow with `VETCH_OAT` hay mix alternating with winter grain cereals.
3. **`SOIL_IMPROVEMENT` (`STRAT_SOIL_IMPROVEMENT`)** — Starts with high-residue legume/forage break (`FABA_BEAN` / `VETCH_OAT`) before cereals to counter low modeled topsoil SOC (`< 18 g/kg`) and heavy clay structure limitations.
4. **`WATER_CONSCIOUS` (`STRAT_WATER_CONSCIOUS`)** — Selects drought-escaping `BARLEY`, chickpea/lentil, and early-cut `VETCH_OAT` avoiding high-ET summer cash crops.
5. **`IRRIGATED_CASH_BREAK` (`STRAT_IRRIGATED_CASH`)** — Triggered when declared water source/system indicates active irrigation or farmer requests `TOMATO_IND` (unless excluded). Places `TOMATO_IND` in a compatible Spring slot separated from cereal/legume breaks. Marked `SELECTED_INFEASIBLE_COUNTERFACTUAL` if irrigation availability is `unknown` or source is `rainfed`.
6. **Farmer Target Integration & Counterfactual Accounting:**
   - Iterates `preferences.target_crop_ids` in order:
     - Unknown ID -> logged in `not_included_reasons`.
     - Listed in `excluded_crop_ids` -> blocked (exclusion takes precedence over inclusion) with reason logged.
     - Non-annual system (`in_annual_rotation_scope == False`, i.e., `OLIVE`) -> logged in `not_included_reasons`; if `include_infeasible_requested_targets=True`, generates `REQUESTED_TARGET_OLIVE` (`SELECTED_INFEASIBLE_COUNTERFACTUAL`) demonstrating `RULE_PERENNIAL_EXCLUSION` and `SEQ_01_PERENNIAL_GUARD`.
     - Valid annual crop not yet covered by another archetype -> synthesizes `FARMER_TARGET_<CROP_ID>` (`STRAT_TARGET_<CROP_ID>`), placing it in the earliest compatible season slot without violating `SOLANACEAE` or boundary rules.
7. **Existing Rotation Baseline (`EXISTING_ROTATION_BASELINE`):**
   - Generated **exclusively** when `sufficient_for_existing_baseline == True` and historical crops do not overlap `excluded_crop_ids`. Projects the observed recent `2..3` crop cycle forward across `horizon_seasons` (`is_existing_rotation = True`, `selection_status = "EXISTING_BASELINE_EVALUATED"`).

### Step 4 — Deduplication & Authoritative Phase G Sequence Evaluation
- Exact crop tuples `tuple(sequence)` are deduplicated in blueprint order; duplicates are counted in `generation_summary.duplicates_skipped_count` and never emitted twice.
- Eligible candidates strictly reject any member of `excluded_crop_ids`.
- For each retained blueprint, `_slot_calendar_sequence` assigns chronological years (`start_year + idx`) and biologically valid agricultural seasons (`start_season` on slot 0, canonical crop season on subsequent slots when `start_season` differs from the crop's permitted seasons).
- Phase G `evaluate_crop_sequence(field_profile, seq_crops, slot_seasons=slot_seasons, kb=kb)` evaluates all 15 single-crop rules per slot and all 10 sequence rules across the multi-year trajectory (including historical `T-1`/`T-2` predecessors).
- Sequential contiguous IDs `CAND_01`, `CAND_02`, ... are assigned after filtering.

### Step 5 — Explicit Evidence, Gaps & Uncertainty Aggregation
Per candidate, Phase H partitions all evaluated rule outputs without flattening `UNKNOWN`:
- `reasons`: sorted `[FAIL]` -> `[UNKNOWN]` (note: `[UNKNOWN]` items sit explicitly in `information_gaps`, while `reasons` lists `[FAIL]`, `[WARNING]`, and `[PASS]` ordered FAIL -> WARNING -> PASS).
- `information_gaps`: exact `[UNKNOWN]` rule explanations requiring local verification.
- `assumptions`: uncertainty notes from rules classified `EXPERT_ASSUMPTION`.
- `evidence`: unique provenance strings across evaluated rules.
- `confidence_limitations`: copied directly from Phase F Section D caveats.
- `needs_local_review` & `review_checklist`: actionable checklist whenever any `UNKNOWN`, `WARNING`, or `FAIL` is present.
