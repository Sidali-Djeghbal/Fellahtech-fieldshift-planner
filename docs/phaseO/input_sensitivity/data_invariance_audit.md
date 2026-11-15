# Phase O — Geospatial & Scientific Data Invariance Audit

**Verification Scope:** 50 API scenarios executed through FastAPI `TestClient` against an isolated in-memory SQLite database (`47` HTTP `200` + `3` HTTP `422`), plus direct Phase F -> H -> I object mutation test (`field_profile_builder.build_field_profile` -> `generate_rotation_candidates` -> `rank_rotation_candidates`).

---

## 1. Spatial, Soil, Climate & Vegetation Invariance Checks

Across all **47 successful requests (`http_status = 200`)** spanning water regimes, crop history permutations, forage priority weights, equipment constraints, and crop target/exclusion lists:
- **`invariance_failures`:** `[]` (**0 / 47** deviations)
- **`schema_failures`:** `[]` (**0 / 47** Draft 2020-12 contract failures)
- **`field_profile_mutated_by_pipeline`:** `False` (`copy.deepcopy(field_profile)` before Phase H matches `field_profile` after Phase H & Phase I byte-for-byte)
- **`unique_payload_hashes_count`:** `39` unique SHA-256 keys across 47 HTTP 200 requests (reused requests matched exact canonical inputs only: `BASE`, `A0`, `B0`, `C0`, `D0`, `E0` -> `ANAL_241B50895CE3FED6`; `E1`/`X2` -> `ANAL_1DADB2FDF29EC5EF`; `C3b`/`X1`/`X6` -> `ANAL_B8858E18311DD014`). Zero cross-request cache leakage occurred.

| Extracted Scientific Metric / Provenance Field | Observed Invariant Value Across All 47 HTTP 200 Runs |
| :--- | :--- |
| `spatial_validation.primary_commune` | `Belkheir` |
| `spatial_validation.area_ha` | `23.8605` |
| `spatial_validation.wilaya_overlap_pct` | `100.0` |
| `crop_frequency.crop_frequency_2021_2025` | `0.9253` |
| `soilgrids_v6.clay_0_30cm` | `34.6748` (`100.0%` polygon coverage) |
| `soilgrids_v6.sand_0_30cm` | `30.8614` |
| `soilgrids_v6.silt_0_30cm` | `34.4625` |
| `soilgrids_v6.ph_0_30cm` | `7.2485` |
| `soilgrids_v6.soc_0_30cm` | `14.6422` (`g/kg`) |
| `soilgrids_v6.cec_0_30cm` | `21.852` (`cmol/kg`) |
| `soilgrids_v6.nitrogen_0_30cm` | Strictly quarantined (`UNVALIDATED_EXCLUDED`) |
| `gpm_and_smap.gpm_annual_precip_2016_2025_mean_mm` | `587.56` (`mm/yr`) |
| `nasa_power.nasa_power_annual_precip_2016_2025_mean_mm` | `736.84` (`mm/yr`) |
| `nasa_power.nasa_power_t2m_2016_2025_mean_c` | `17.91` (`C`) |
| `sentinel2.s2_2024_03_ndvi_10m` | `0.5386` |
| `terrain_dem.dem_elevation_m.quality_status` | `UNAVAILABLE_NOT_INTEGRATED` |
| `provenance_disclosures.soilgrids_vs_laboratory_distinction` | Fixed verbatim disclosure preserved |
| `provenance_disclosures.regional_climate_vs_field_distinction` | Fixed verbatim disclosure preserved |
| `provenance_disclosures.missing_values_policy` | Fixed verbatim disclosure preserved |

---

## 2. Anti-Fabrication & Decision Gate Integrity

- **`decision_gate`:** Every single Belkheir scenario returns `REQUIRES_LOCAL_VERIFICATION` (`endorsed_recommendation_id = null`), never auto-promoting an endorsement while DEM relief, ECe/ECw salinity, SoilGrids N, and local crop yields remain unverified.
- **Null vs `[]` Separation:** Verified distinct across `crop_history` (`NOT_PROVIDED` -> `comp=0.8846` vs `EXPLICITLY_CONFIRMED_EMPTY` -> `comp=0.9038`) and `equipment_constraints` (`NOT_PROVIDED` -> `0.8846`, `fit=PARTIAL:0.825` vs `EXPLICITLY_CONFIRMED_EMPTY` -> `0.9038`, `fit=SCORED:0.95`), while keeping both missing-history cases at `SEQ_10 = UNKNOWN`.
- **Single Normalization Check:** Priority weights normalize once in `src/optimization/scoring_engine.py` (`active_weighted_objectives` sum `= 1.0`), preventing omitted core priorities or unavailable `income_potential` from corrupting active objective shares.
