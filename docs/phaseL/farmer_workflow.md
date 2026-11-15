# Phase L — Farmer & Agricultural Advisor Workflow Design

> **Implemented Client:** [`frontend/index.html`](file:///home/lokman/Desktop/FeildShit-SI-Model/frontend/index.html), [`frontend/styles.css`](file:///home/lokman/Desktop/FeildShit-SI-Model/frontend/styles.css), [`frontend/app.js`](file:///home/lokman/Desktop/FeildShit-SI-Model/frontend/app.js)  
> **Serving Endpoint:** `GET /` on FastAPI backend (`uvicorn src.api.app:app`)

---

## 1. Mobile-Friendly 7-Step User Journey

1. **Draw Field on Interactive Wilaya Map Canvas:**  
   Farmer clicks field corners directly on the Guelma Wilaya boundary canvas (offline-capable via `/api/v1/reference/guelma-boundary`) or selects a regional pilot preset (`Belkheir Valley` / `Tamlouka South`). Exactly one closed GeoJSON `Polygon` is constructed—no `MultiPolygon` confusion.
2. **Enter Only Farmer-Known Operational Inputs (Zero Technical Fields):**  
   Farmer sets `Field ID`, optional `Field Name`, `Water Availability` (`limited | moderate | abundant | unknown`), `Source`, `Irrigation System`, `Planning Start Season/Year` + `Horizon (2–4)`, and optional `Target/Excluded Crops`. **No soil pH, clay %, SOC, NDVI, or rainfall fields exist anywhere in the UI.**
3. **Explicit `null` vs `[]` & Optional Inputs Discipline:**  
   - **Crop History:** Dropdown separates `Provide remembered crops`, `Not Provided / Unknown (null)`, and `Confirmed No Recent Crop ([])`.
   - **Livestock Forage:** Separates `Not Provided (null — keep inactive)` from `None Needed (0.0)` and positive weights (`0.30` / `0.60`).
   - **Equipment Constraints:** Separates `Not Provided (null — unknown)` from `Confirmed No Constraints ([])` and specific limits.
4. **Optional Polygon Pre-Check (`POST /api/v1/fields/validate`):**  
   Displays mapped area (`ha`), primary Guelma commune overlap, and boundary warnings before running extraction.
5. **Inspect Auto-Extracted Field Profile Summary:**  
   Displays `SoilGrids 250 m` USDA texture / Clay / SOC / pH explicitly labeled **`MODELED_SPATIAL_ESTIMATE` (Not Lab)**, `11–55 km` `GPM` vs `NASA POWER` annual precipitation spread, **`DEM = UNAVAILABLE_NOT_INTEGRATED`**, and `data_quality.completeness_score` explicitly labeled separate from agronomic confidence.
6. **Review Categorized Rotation Strategies with Clear Decision Badges:**  
   Cards distinguish four statuses visually and semantically:
   - **`Recommended`** (`FEASIBLE_PASS`)
   - **`Conditionally Recommended` / `Top Conditional Choice`** (`CONDITIONALLY_FEASIBLE_WITH_WARNINGS_OR_UNKNOWNS`)
   - **`Insufficient Evidence / Unknown`** (`UNVERIFIED_HARD_UNKNOWN`)
   - **`Infeasible`** (`INFEASIBLE_HARD_CONSTRAINT`, with `rank = null`, never recommended)
7. **Inspect Explainability, Limitations & Verification Checklist:**  
   Every strategy displays chronological season slots (`order, season, year, crop_name`), relative composite score + Pareto status (with explicit banner: **NOT predicted yield `t/ha`, net profit, or statistical probability**), expandable Water / Soil / Sequence (`SEQ_*`) explanations, `EvidenceItem[]` sources, missing data, and on-farm verification items (drainage puddling check, irrigation `ECe` test).
