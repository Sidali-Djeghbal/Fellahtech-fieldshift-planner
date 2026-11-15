# Final Farmer Input Architecture & Automatic Field Profile Report — Field Shift

**Architecture Principle:** Farmers provide **only simple agricultural facts they know** (`drawn polygon`, `water & irrigation access`, `crop history`, `planning horizon`, `preferences`). Soil physics/chemistry (`pH`, `SOC`, `clay/sand/silt`, `CEC`), satellite indices (`Sentinel-2`, `MODIS`, `CropFreq`), macro weather (`NASA POWER`, `GPM`, `SMAP`), terrain gaps (`DEM`), and data-quality metadata are **never exposed as required farmer form fields** and are extracted or audited automatically by the backend.

---

## 1. Minimal Farmer Input Contract ([field_input_schema.json](file:///home/lokman/Desktop/FeildShit-SI-Model/field_input_schema.json))

Strict Draft 2020-12 schema with `additionalProperties: false` and explicit rejection of forbidden technical fields (`soil_ph`, `clay_pct`, `ndvi`, `rainfall_mm`, `slope_deg`, `quality_status`, etc.):

1. **`field`**: `field_id`, optional `field_name`, one GeoJSON `Polygon` (`geometry`, optional `geometry_crs` defaulting to `EPSG:4326`).
2. **`water`**: `availability` (`limited | moderate | abundant | unknown`), `source` (`groundwater | well | reservoir | river | rainfed | other`), `irrigation_system` (`drip | sprinkler | surface | none | unknown`).
3. **`crop_history`** (optional; `null`/omitted = `NOT_PROVIDED`, `[]` = `EXPLICITLY_CONFIRMED_EMPTY`): `season` (`Winter | Spring | Summer | Autumn`), `year`, optional `planting_month`, optional `crop_id`, `crop_name_raw` (mapped internally via multilingual French/Arabic/English alias table without overwriting raw input), optional `yield_tons_per_hectare`, optional `notes`.
4. **`planning`**: `start_season`, `start_year`, `horizon_seasons` (`2–4`), optional `planting_month`.
5. **`preferences`** (optional; subfields nullable/optional; `null`/omitted vs `[]` preserved via `input_completeness_flags`): `target_crop_ids`, `excluded_crop_ids`, `equipment_constraints`, `water_saving_weight`, `soil_improvement_weight`, `income_weight`, `risk_reduction_weight`, `forage_value_weight` (`[0..1]`).

---

## 2. Automatic Local Geospatial Extraction ([field_geospatial_processor.py](file:///home/lokman/Desktop/FeildShit-SI-Model/field_geospatial_processor.py))

After validating ring topology, reprojecting to `EPSG:32632`, computing exact polygon area (`ha`), and verifying overlap against Guelma Wilaya and the `34` GADM Communes, `extract_field_geospatial_context()` reads **strictly from local Phase A–D assets (zero Earth Engine calls)**:

| Source Dataset | Spatial Support & Scope | Exact Aggregation Over Drawn Polygon | Internal `quality_status` & Explicit Limitation |
|---|---|---|---|
| **SoilGrids 2.0 V6** (`guelma_soilgrids_42bands_250m_V6_MERGED.tif` + `USDA Texture`) | `250 m`, Static (`0–30 cm` & `30–100 cm`) | Windowed polygon–pixel intersection area weights + horizon thickness weights; `Nitrogen` quarantined (`value = None`) | `MODELED_SPATIAL_ESTIMATE` — clearly distinguished from laboratory soil samples; `nitrogen_0_30cm` -> `UNVALIDATED_EXCLUDED`. |
| **ESA Crop Frequency** (`aligned_s2_10m.tif`) | `10 m` snapped, `2021–2025` only | Windowed polygon–pixel area weights + `share >= 0.5` | `REMOTE_SENSING_DERIVED` — `2021–2025` validity window only. |
| **Sentinel-2** (`phaseA_2024_03` `10 m`/`20 m` + Wilaya monthly CSV) | `10 m` (`NDVI, EVI`), `20 m` (`NDMI, NDRE`), plus Wilaya `2017–2025` | Exact March `2024` spatial pixels (`valid_obs > 0`, `-9999` masked); multi-year Spring climatology tagged Wilaya fallback | `REMOTE_SENSING_DERIVED` (`2024-03`) & `REGIONAL_FALLBACK_ONLY` (multi-year S2 rasters deferred). |
| **MODIS MOD13Q1** (`seasonal 2016–2025.tif`) | `250 m`, `4` seasons × `10` yrs | Exact `250 m` polygon–pixel intersection mean across 10 seasons | `REMOTE_SENSING_DERIVED` (`250 m` mixed pixel, no 16-day files on disk). |
| **GPM IMERG & SMAP L4** (`11 km` canonical grid) | `11 km` seasonal/annual (`2016–2025`) | Exact intersection area against `11 km × 11 km` UTM boxes | `REMOTE_SENSING_DERIVED` (`GPM`) / `MODELED_SPATIAL_ESTIMATE` (`SMAP L4`); macro `11 km` support, no monthly files locally. |
| **NASA POWER** (`AG ~55–69 km`, `RE ~111 km`) | Macro cells, daily `2016–2025` | Exact intersection with `AG` & `RE` cell polygons | `MODELED_SPATIAL_ESTIMATE` — macro context; `+132 mm/yr` wetter bias vs `GPM` preserved. |
| **DEM (`Elevation`, `Slope`)** | Not yet integrated (`SRTM 30 m` planned) | Explicit null placeholder | `UNAVAILABLE_NOT_INTEGRATED` (`value = None`, never fabricated). |

Every metric embeds: `value`, `unit`, `source_dataset`, `spatial_resolution`, `temporal_coverage`, `valid_pixel_count`, `polygon_coverage_pct`, `aggregation_method`, `quality_status`, and `uncertainty_or_limitations`.

---

## 3. Field Profile Assembly, Provenance & UX Clarification Logic ([field_profile_builder.py](file:///home/lokman/Desktop/FeildShit-SI-Model/field_profile_builder.py))

1. **4-Part Profile Schema ([field_profile_data_dictionary.csv](file:///home/lokman/Desktop/FeildShit-SI-Model/docs/field_profile/field_profile_data_dictionary.csv)):** Combines `section_a_farmer_provided`, `section_b_extracted_geospatial`, `section_c_agronomic_knowledge_base` (descriptive diagnostics only—**zero rotation optimization implemented**), and `section_d_quality_and_uncertainty`.
2. **Generated Analysis Report (`render_field_analysis_report_md`):** Converts technical soil, climate, and vegetation extracts into a readable post-draw analysis summary instead of burdening the farmer with input forms.
3. **Materiality-Only Clarifications (`conditional_follow_up_questions`):** Prompts farmers in plain language *only* when missing data materially alter crop gating (unknown water availability/irrigation system, missing last-season crop history, winter field puddling on heavy clay while DEM is unavailable, or visible salt crusts on irrigated land lacking `ECe`).
