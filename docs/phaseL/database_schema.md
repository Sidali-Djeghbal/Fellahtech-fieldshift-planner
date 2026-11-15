# Phase L — Database Schema & Persistence Evaluation

> **PostGIS DDL:** [`db/schema_postgis.sql`](file:///home/lokman/Desktop/FeildShit-SI-Model/db/schema_postgis.sql)  
> **Active Local Repository:** [`src/api/repository.py`](file:///home/lokman/Desktop/FeildShit-SI-Model/src/api/repository.py) (`SQLiteAnalysisRepository` + `PostgresPostGISRepository` adapter)

---

## 1. PostgreSQL + PostGIS Evaluation

### Why PostgreSQL + PostGIS Fits Production Deployment
1. **Native Dual-CRS Spatial Indexing:** Stores farmer-drawn `EPSG:4326` input polygons alongside canonical `EPSG:32632` UTM Zone 32N geometries with `GiST` indexes and database-level `CHECK (ST_IsValid(...))` topological enforcement.
2. **Relational Integrity + JSONB Provenance:** Normalized FKs link users, fields, crop history, and strategy summaries for fast commune/advisor queries (`SELECT ... WHERE primary_commune = 'Bouchekouf'`), while `JSONB` columns preserve the immutable original input payload, full 4-section Field Profile, and validated Phase J output verbatim for audit replay.

### Observed Local Host Constraint (Explicitly Reported)
- `psql (PostgreSQL) 18.6` is running locally on `/var/run/postgresql:5432`, **however** `/usr/share/postgresql/*/extension/postgis*` and `psycopg`/`psycopg2` drivers are **not** installed on this host.
- Therefore, Phase L supplies:
  1. The authoritative PostgreSQL + PostGIS DDL ([`db/schema_postgis.sql`](file:///home/lokman/Desktop/FeildShit-SI-Model/db/schema_postgis.sql)) and `PostgresPostGISRepository` (`DISCONNECTED` until PostGIS + `psycopg` are provisioned).
  2. A live runnable `SQLiteAnalysisRepository` (using stdlib `sqlite3 3.51.2`) mirroring all **8 entities** cleanly for pilot testing, API persistence, and automated integration tests.

---

## 2. The 8 Normalized Entities Implemented

| # | Table Name | Role & Reproducibility Guarantee | Key Columns / FKs |
|---:|---|---|---|
| 1 | `farmers_users` | Farmers, DSA advisors, administrators, or default pilot session owner | `user_id` (PK), `role`, `display_name`, `commune_name`, `preferred_language` |
| 2 | `fields` | Spatial field parcel record (exact GeoJSON / `Polygon` + UTM 32N metrics) | `field_record_id` (PK), `farmer_id` (FK), `external_field_id`, `geometry_wgs84` (`Polygon, 4326`), `geometry_utm32n` (`Polygon, 32632`), `area_ha`, `wilaya_overlap_pct`, `primary_commune` |
| 3 | `analysis_requests` | Content-addressed analysis envelope preserving `null` vs `[]` flags & full input JSON | `analysis_id` (PK), `field_record_id` (FK), `farmer_id` (FK), `payload_sha256`, `water_*`, `start_*`, `crop_history_flag`, `equipment_constraints_flag`, `forage_weight_flag`, `original_request_json` |
| 4 | `crop_history_records` | Normalized user-reported prior seasonal crops (`USER_REPORTED`) | `history_id` (PK), `analysis_id` (FK), `field_record_id` (FK), `season`, `crop_year`, `crop_id_resolved`, `crop_name_raw`, `normalization_status`, `yield_tons_per_hectare` |
| 5 | `field_profiles` | Generated Phase F 4-part Field Profile linked 1:1 to `analysis_requests` | `profile_id` (PK), `analysis_id` (UNIQUE FK), `profile_schema_version`, `full_field_profile_json` |
| 6 | `recommendation_results` | Schema-validated (`schema_valid = TRUE`) Phase J final output linked 1:1 to `analysis_requests` | `recommendation_id` (PK), `analysis_id` (UNIQUE FK), `engine_request_id`, `dataset_version_used`, `decision_engine_version`, `recommendation_status`, `suggested_strategy_id`, `completeness_score`, `climate_dataset_agreement`, `stability_index`, `final_recommendation_json` |
| 7 | `candidate_strategies` | Queryable strategy summary rows (avoids duplicating bulky evidence strings per rule) | `strategy_row_id` (PK), `analysis_id` (FK), `strategy_id`, `feasibility_status`, `eligible_for_ranking`, `rank`, `pareto_status`, `weighted_score`, `seasons_json`, `scores_snapshot_json` |
| 8 | `data_provenance_quality_metadata` | Explicit missing data, warnings, SoilGrids/climate/DEM status counts & limitations ledger | `provenance_id` (PK), `analysis_id` (UNIQUE FK), `dataset_version_used`, `quality_status_counts_json`, `input_completeness_json`, `missing_data_json`, `warnings_json`, `limitations_json` |

### Duplication Avoidance Check
- Bulk geospatial rasters (`SoilGrids`, `GPM`, `SMAP`, `S2`) and static knowledge catalogs stay in their versioned disk archives (`dataset_version_used`) rather than being duplicated per row, while field-specific extracted values and `EvidenceItem[]` live once inside `field_profiles` and `recommendation_results` (`1:1` with `analysis_requests`).
