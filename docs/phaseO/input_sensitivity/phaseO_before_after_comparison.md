# Phase O — Before vs After Verification Comparison

Comparison between the pre-fix 39-scenario baseline (`scratch/full_audit_out.json`) and the post-fix 50-scenario re-audit (`docs/phaseO/input_sensitivity/scenario_results.json`), executed via FastAPI `TestClient` with isolated `:memory:` SQLite persistence.

---

## 1. Baseline & Non-Regression Check

| Metric | Baseline Before Fixes | Baseline After Fixes | Delta / Verdict |
| :--- | :---: | :---: | :--- |
| `analysis_id` | `ANAL_241B50895CE3FED6` | `ANAL_241B50895CE3FED6` | **Unchanged (0 drift)** |
| `suggested_strategy_id` | `STRAT_SOIL_IMPROVEMENT` | `STRAT_SOIL_IMPROVEMENT` | **Unchanged** |
| `top_score` | `0.879238` | `0.879238` | **Unchanged** |
| `ranking_margin` | `0.04176` | `0.04176` | **Unchanged** |
| `stability_index` | `1.0` | `1.0` | **Unchanged** |
| `completeness_score` | `0.8846` | `0.8846` | **Unchanged** |
| `decision_gate` | `REQUIRES_LOCAL_VERIFICATION` | `REQUIRES_LOCAL_VERIFICATION` | **Unchanged** |
| Geospatial `invariance_failures` | `[]` | `[]` | **0 failures across 47 runs** |

---

## 2. Changed Scenarios Across Original 39 Cases

Exactly **13 scenarios** changed behavior as intended by Fixes 1–6; all other **26 original scenarios** matched 100% verbatim across `http_status`, `top_score`, `suggested_strategy_id`, normalized weights, `SEQ_10`, and objective scores.

| Scenario | Before Fix | After Fix | Reason / Fix Verified |
| :--- | :--- | :--- | :--- |
| `A4_unknown_literal` | `HTTP 422` (`literal_error` on `water.source='unknown'`) | `HTTP 200`, `top=0.879238`, `STRAT_SOIL_IMPROVEMENT`, `water=0.9041`, `Q_WATER_MATERIAL` | **FIX 1:** `"unknown"` water source accepted & treated conservatively rainfed without inferring irrigation |
| `B2_hist_durum_2025`, `B3_hist_faba_2025`, `B4_hist_barley_2025`, `X4`, `X5` | `crop_history="PROVIDED"` | `crop_history="PROVIDED_PARTIAL"` (`scores`/`SEQ_10`/`rankings` unchanged) | **FIX 4:** Single-season provided history accurately labeled `PROVIDED_PARTIAL` instead of conflating with multi-year complete history |
| `B2b_hist_durum_2026_winter` | `SEQ_10=UNKNOWN`, `pest=PARTIAL:1.0`, `stab=1.0`, `crop_history="PROVIDED"` | `SEQ_10=PASS`, `pest=SCORED:1.0`, `margin=0.00576`, `stab=0.8947`, `crop_history="PROVIDED_PARTIAL"` | **FIX 4:** `Winter 2026` chronologically recognized before `Autumn 2026` (`T-1 = DURUM_WHEAT`) |
| `C1_forage_0_isolated` | `HTTP 422` (`INVALID_PRIORITY_WEIGHTS` inside `detail`) | `HTTP 200`, `top=0.879238`, `forage=NOT_APPLICABLE`, core weights `0.25/0.30/0.20/0.25` | **FIX 3:** Isolated `forage_value_weight=0.0` marks forage inactive while preserving `DEFAULT_FARMER_WEIGHTS` |
| `C2_forage_030_isolated` | `HTTP 200`, `top=0.4833`, `forage=1.0` (all core weights wiped to `0.0`) | `HTTP 200`, `top=0.771255`, `water=0.227273`, `forage=0.272727` (exact match to `C2b_paired`) | **FIX 3:** Omitted core weights preserved cleanly instead of collapsing to `0.0` |
| `C3_forage_060_isolated` | `HTTP 200`, `top=0.4833`, `forage=1.0` (all core weights wiped to `0.0`) | `HTTP 200`, `top=0.709548`, `water=0.178571`, `forage=0.428571` (exact match to `C3b_paired`) | **FIX 3:** Full API/UI parity verified for `forage_value_weight=0.60` |
| `D2_equip_no_sprayer` | `HTTP 200`, `fit=SCORED:0.95`, `top=0.892909` (false `PASS`) | `HTTP 200`, `fit=PARTIAL:0.825`, `top=0.879238` + `[UNSUPPORTED_EQUIPMENT_TAG]` warning | **FIX 2:** Unmodeled `no_sprayer` returns `UNKNOWN` (`PARTIAL` fit), never coerced to `PASS` |
| `D3_equip_no_harvester` | `HTTP 200`, `fit=SCORED:0.95`, `top=0.892909` (false `PASS`) | `HTTP 200`, `fit=PARTIAL:0.825`, `top=0.879238` + `[UNSUPPORTED_EQUIPMENT_TAG]` warning | **FIX 2:** Unmodeled `no_harvester` returns `UNKNOWN` (not mapped to `no_mower`/`no_hay_baler`) |
| `X3_no_harvester_target_barley` | `HTTP 200`, `fit=SCORED:1.0`, `top=0.856619` | `HTTP 200`, `fit=PARTIAL:0.875`, `top=0.842947` + `[UNSUPPORTED_EQUIPMENT_TAG]` warning | **FIX 2:** Cross-input unmodeled equipment honesty preserved without changing target Barley choice |
| `E4_target_and_exclude_faba` | `HTTP 200`, `sug=STRAT_SOIL_IMPROVEMENT` (`0.871084`) | `HTTP 422`, `error_code="TARGET_EXCLUDED_CROP_CONFLICT"`, `details=[{"conflicting_crop_ids": ["FABA_BEAN"]}]` | **FIX 5 & FIX 6:** Target/exclusion contradiction cleanly rejected in unified `422` envelope |

---

## 3. Additional Post-Fix Verification Scenarios (11 New Cases)

| New Scenario | Outcome | Key Verified Assertion |
| :--- | :--- | :--- |
| `A4c_moderate_unknown_drip` | `HTTP 200` (`top=0.879238`, `water=0.9041`) | `source="unknown"` prevents irrigation activation even when `availability="moderate"` & `system="drip"` |
| `A4d_moderate_other_drip` | `HTTP 200` (`top=0.894863`, `water=0.9541`) | `"other"` remains distinct from `"unknown"` and permits irrigated break eligibility |
| `B2c_hist_chickpea_2026_spring` | `HTTP 200` (`top=0.841259`, `STRAT_CEREAL_FORAGE`, `SEQ_10=PASS`) | `Spring 2026` chickpea shifts top strategy due to short pulse return interval |
| `B2d_hist_tomato_2026_summer` | `HTTP 200` (`top=0.879238`, `pest=SCORED:1.0`, `SEQ_10=PASS`) | `Summer 2026` recognized chronologically before `Autumn 2026` |
| `B2e_hist_complete_2024_2025` | `HTTP 200` (`crop_history="PROVIDED_COMPLETE"`, `followups=[]`) | `>= 2` resolved prior seasons produce `PROVIDED_COMPLETE` & zero follow-up prompts |
| `B2f_hist_unresolved_2025` | `HTTP 200` (`crop_history="PROVIDED_PARTIAL"`, `SEQ_10=UNKNOWN`) | Unresolved crop name never falsely clears `SEQ_10` |
| `B2g_hist_concurrent_2026_422` | `HTTP 422` (`CROP_HISTORY_AFTER_PLANNING_START`) | Concurrent (`Autumn 2026` for `Autumn 2026`) history rejected cleanly in unified envelope |
| `C4_all_zero_core_weights_422` | `HTTP 422` (`INVALID_PRIORITY_WEIGHTS`) | Explicit all-zero core+forage weights cleanly rejected in unified envelope |
| `D5_equip_no_hay_baler` | `HTTP 200` (`fit=SCORED:0.8583`, `top=0.88288`) | Modeled KB tag behaves identically to `no_mower` (`VETCH_OAT` `WARNING`) |
| `D6_equip_no_potato_harvester` | `HTTP 200` (`fit=SCORED:0.95`, `top=0.892909`) | Dryland candidates unaffected (`PASS` for non-potato systems) |
| `D7_equip_mixed_baler_sprayer` | `HTTP 200` (`fit=PARTIAL:0.775`, `top=0.873769`) | Combines `WARNING` (`no_hay_baler` on Vetch-Oat) with `[UNSUPPORTED_EQUIPMENT_TAG]` (`no_sprayer`) |
