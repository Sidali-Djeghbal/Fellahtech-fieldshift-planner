# Phase O — Task 0–8 Executive Summary

**Project:** Field Shift — Guelma Crop Rotation DSS (`FieldShift-PhaseFJ-1.1.0`)  
**Scope:** End-to-end sensitivity audit of farmer-provided inputs (Tasks 0–6) followed by minimal targeted engineering fixes, regression suite, and Before/After verification (Tasks 7–8).

---

## 1. Key Findings from Tasks 0–6

Across the Belkheir reference polygon (`23.8605 ha`, `crop_frequency_2021_2025 = 0.9253`, Clay `34.6748%`, pH `7.2485`, SOC `14.6422 g/kg`, GPM `587.56 mm/yr`, POWER `736.84 mm/yr`), all geospatial layers, SoilGrids nitrogen quarantine, land-use status (`LAND_USE_SUPPORTED`), and decision-gate conservatism (`REQUIRES_LOCAL_VERIFICATION`) were **strictly invariant** across farmer operational changes.

However, the pre-fix 39-scenario API audit uncovered **6 operational contract & logic defects**:
1. **`water.source = "unknown"` rejection:** Pydantic/JSON Schema/PostGIS/UI rejected `"unknown"`, while some downstream checks only inspected `availability == "unknown"`.
2. **`equipment_constraints` UI–KB mismatch & unmodeled coercion:** Frontend exposed `no_sprayer` and `no_harvester` even though `crop_profiles.json` only models `no_hay_baler`, `no_mower`, `no_drip_irrigation`, `no_precision_planter`, `no_potato_harvester`, and `no_sunflower_header`; unmodeled API tags previously evaluated as `PASS` (`0.95` fit score).
3. **`forage_value_weight` collapsing omitted core weights:** Sending `{"forage_value_weight": 0.30}` or `0.60` alone zeroed all 4 core weights (`forage_value = 1.0`, `top_score = 0.4833`), while `{"forage_value_weight": 0.0}` failed with HTTP `422`. Meanwhile the frontend secretly overrode weights with non-default constants (`0.15/0.20/0.05/0.15`).
4. **Year-only `crop_history` predecessor lookup:** `start_year - 1` (`2025`) missed `Winter 2026`, `Spring 2026`, and `Summer 2026` before `Autumn 2026` (`SEQ_10 = UNKNOWN`), lacked `PROVIDED_PARTIAL` vs `PROVIDED_COMPLETE` states, and permitted concurrent (`Autumn 2026`) history entries.
5. **Silent `target_crop_ids ∩ excluded_crop_ids` acceptance:** Requests asking for and excluding the same crop returned HTTP `200` and silently discarded the target.
6. **Inconsistent HTTP `422` error JSON:** Endpoint `ValueError` handlers wrapped responses in `{"detail": {"error_code", "message"}}`, whereas schema and farmer-policy handlers returned top-level `{"error_code", "message", "details"}`.

---

## 2. Targeted Fixes & Verification Results (Tasks 7–8)

All 6 issues were fixed cleanly without fabricating agronomic parameters, mapping `no_harvester` to hay/mower tags, weakening hard constraints, or deleting existing tests:
- **Re-audit execution (`50` scenarios via FastAPI `TestClient` + `:memory:` SQLite):**
  - `47` HTTP `200` responses + `3` intentional HTTP `422` validation rejections (`B2g_hist_concurrent_2026_422`, `C4_all_zero_core_weights_422`, `E4_target_and_exclude_faba`).
  - `invariance_failures = []` (`0/47`), `schema_failures = []` (`0/47`), `non_unified_422 = []` (`0/3`), `field_profile_mutated_by_pipeline = False`.
  - Baseline request invariance confirmed (`ANAL_241B50895CE3FED6`, `top_score = 0.879238`, `STRAT_SOIL_IMPROVEMENT`, `margin = 0.04176`, `stability_index = 1.0`, `decision_gate = REQUIRES_LOCAL_VERIFICATION`).
- **Automated Regression Suite:** Expanded existing tests with `tests/test_phaseO_input_sensitivity.py` and verified all tests cleanly via `unittest`.

---

## 3. Open Scope & Honest System Boundaries

- **Unmodeled Machinery:** Tags outside the 6 KB-modeled constraints (e.g. `no_sprayer`, `no_harvester`) remain intentionally unmodeled in `crop_profiles.json`; they resolve as `UNKNOWN` (`PARTIAL` fit score) with explicit warnings rather than fabricated crop penalties or `PASS` assumptions.
- **Deferred Physical / Economic Measurements:** Local DEM slope/elevation, field ECe/ECw irrigation salinity, SoilGrids Nitrogen (quarantined), and local crop yield/price budgets remain unavailable; `income_potential` remains `UNKNOWN` and `decision_gate` remains `REQUIRES_LOCAL_VERIFICATION` until verified in Phase M/field inspection.
- **FAO-56 Water Balance:** Precipitation/irrigation scoring remains ordinal regime suitability (`ORDINAL_REGIME_SUITABILITY`) rather than full Penman–Monteith ET0 balancing (missing wind speed WS2M and soil FC/PWP).
