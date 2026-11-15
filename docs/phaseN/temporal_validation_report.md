# Phase N — Temporal Planning Validation & Calendar Architecture Report

## 1. Identified Temporal Defect in v1.0.0

Prior to Phase N:
- `frontend/index.html` hardcoded `<input type="number" id="startYear" value="2025" ... />`.
- Neither [`field_input_schema.json`](file:///home/lokman/Desktop/FeildShit-SI-Model/field_input_schema.json), [`field_profile_builder.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/field_profile_builder.py), [`src/api/app.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/src/api/app.py), nor [`src/rotation/candidate_generator.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/src/rotation/candidate_generator.py) enforced temporal validation against the current planning date.
- Consequently, live requests such as `ANAL_248892E4C4DFE796` (`start_season = "Autumn", start_year = 2025`) generated operational-looking plans for already-past seasons without rejection or historical simulation disclosure.

---

## 2. Two-Mode Temporal Architecture (`src/agronomic/temporal_planning.py`)

| Mode | Default | Behavior on Past Start Window (`ref_date > window_end`) | Behavior on Past `planting_month` | Output Flagging |
|---|---|---|---|---|
| `CURRENT_PLANNING` | **Yes** | Raises `TemporalPlanningError` (`error_code = "PAST_PLANNING_SEASON"`), returns `recommended_start_season` + `recommended_start_year`. API maps to HTTP **422**. | Raises `TemporalPlanningError` (`error_code = "PAST_PLANTING_MONTH"`). | `VALID_CURRENT_WINDOW` or `VALID_FUTURE_WINDOW` (`is_historical_simulation = False`). |
| `HISTORICAL_SIMULATION` | Explicit opt-in (`planning.planning_mode`) | Permitted for backtesting / validation studies. | Permitted. | `HISTORICAL_SIMULATION_PAST_HORIZON` (or `..._CURRENT_OR_FUTURE`); attaches explicit warning to `data_quality.warnings`. |

Additional strict integrity checks in `validate_and_build_planning_timeline(...)`:
- **Chronological History Check (`CROP_HISTORY_AFTER_PLANNING_START`):** Rejects in `CURRENT_PLANNING` (and warns in `HISTORICAL_SIMULATION`) if any `crop_history` entry has a season start later than the requested `planning` slot 1 start.
- **Injectable Reference Clock (`reference_date` / `clock`):** Supported across `validate_farmer_input`, `build_field_profile`, `generate_rotation_candidates`, `validate_farmer_submission`, and `run_field_analysis_pipeline` so automated tests and historical simulations never depend on mutable system clocks.

---

## 3. Guelma Regional Sowing Windows & Unified Timeline Progression

`AgriculturalCalendarConfig.default_guelma()` defines inclusive Guelma planning windows:

| Season | Window Start | Window End | Default Planting Month |
|---|---|---|---|
| `Winter` | Dec 1 (`Y - 1`) | Mar 15 (`Y`) | `1` (Jan) |
| `Spring` | Mar 1 (`Y`) | May 31 (`Y`) | `3` (Mar) |
| `Summer` | Jun 1 (`Y`) | Aug 31 (`Y`) | `6` (Jun) |
| `Autumn` | Sep 1 (`Y`) | Dec 31 (`Y`) | `11` (Nov) |

Both `validate_and_build_planning_timeline(...)` and [`candidate_generator.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/src/rotation/candidate_generator.py) advance subsequent annual campaigns identically:
- `Autumn 2026` (`horizon = 3`) → `Autumn 2026` → `Autumn 2027` → `Autumn 2028`
- `Winter 2027` (`horizon = 3`) → `Winter 2027` → `Autumn 2027` (following main rainfed campaign in the same year, avoiding skipping a year) → `Autumn 2028`
- `Spring 2027` (`horizon = 3`) → `Spring 2027` → `Autumn 2027` → `Autumn 2028`

---

## 4. API & Frontend Enforcement

- [`src/api/schemas.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/src/api/schemas.py): Added optional `planning_mode: Optional[Literal["CURRENT_PLANNING", "HISTORICAL_SIMULATION"]] = None` on `PlanningInputContract` (preserving default `CURRENT_PLANNING` server-side when omitted).
- [`src/api/app.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/src/api/app.py): Upgraded `FarmerInputValidationError` exception handler to return `exc.error_code` (e.g., `PAST_PLANNING_SEASON`) and `exc.details` (`recommended_start_season`, `recommended_start_year`) on HTTP `422`.
- [`src/api/pipeline_service.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/src/api/pipeline_service.py): Included `DECISION_ENGINE_VERSION` in `compute_payload_sha256` so stale `1.0.0` DB caches never replay for `1.1.0` queries.
- [`frontend/index.html`](file:///home/lokman/Desktop/FeildShit-SI-Model/frontend/index.html) & [`frontend/app.js`](file:///home/lokman/Desktop/FeildShit-SI-Model/frontend/app.js): Added `defaultOpenPlanningPeriod(new Date())` dynamic default selection and `<select id="planningMode">` selector.
