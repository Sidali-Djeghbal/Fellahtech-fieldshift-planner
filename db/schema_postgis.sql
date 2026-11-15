-- Field Shift (Guelma Wilaya, Algeria) — Authoritative PostgreSQL + PostGIS Schema (Phase L)
-- Requires: PostgreSQL >= 15 and PostGIS extension (postgis >= 3.x)
-- Purpose: Stores normalized field boundaries (EPSG:4326 & EPSG:32632), farmer accounts,
--          reproducible original request snapshots, auto-extracted Field Profiles,
--          ranked candidate strategies, validated Phase J recommendation payloads,
--          and dataset provenance/quality metadata.

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 1. Farmers or Agricultural Advisors
CREATE TABLE IF NOT EXISTS farmers_users (
    user_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    role               TEXT NOT NULL CHECK (role IN ('farmer', 'advisor', 'admin', 'anonymous_pilot')),
    display_name       TEXT NOT NULL,
    phone_hash         TEXT,
    commune_name       TEXT,
    preferred_language TEXT NOT NULL DEFAULT 'en' CHECK (preferred_language IN ('en', 'fr', 'ar')),
    created_at_utc     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. Fields (Exactly One Valid Simple Polygon per Field Record; EPSG:4326 intake + EPSG:32632 canonical)
CREATE TABLE IF NOT EXISTS fields (
    field_record_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    farmer_id          UUID REFERENCES farmers_users(user_id) ON DELETE SET NULL,
    external_field_id  TEXT NOT NULL,
    field_name         TEXT,
    geometry_wgs84     GEOMETRY(Polygon, 4326) NOT NULL,
    geometry_utm32n    GEOMETRY(Polygon, 32632) NOT NULL,
    area_ha            DOUBLE PRECISION NOT NULL CHECK (area_ha > 0),
    perimeter_m        DOUBLE PRECISION NOT NULL CHECK (perimeter_m > 0),
    wilaya_overlap_pct DOUBLE PRECISION NOT NULL CHECK (wilaya_overlap_pct > 0 AND wilaya_overlap_pct <= 100.0),
    primary_commune    TEXT,
    created_at_utc     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_geom_valid_wgs CHECK (ST_IsValid(geometry_wgs84)),
    CONSTRAINT chk_geom_valid_utm CHECK (ST_IsValid(geometry_utm32n))
);

CREATE INDEX IF NOT EXISTS idx_fields_geom_wgs84_gist ON fields USING GIST (geometry_wgs84);
CREATE INDEX IF NOT EXISTS idx_fields_geom_utm32n_gist ON fields USING GIST (geometry_utm32n);
CREATE INDEX IF NOT EXISTS idx_fields_external_id ON fields (external_field_id);

-- 3. Analysis Requests (Immutable Request Snapshot + Reproducibility Hash + Null vs [] Completeness Flags)
CREATE TABLE IF NOT EXISTS analysis_requests (
    analysis_id                    TEXT PRIMARY KEY,
    field_record_id                UUID NOT NULL REFERENCES fields(field_record_id) ON DELETE RESTRICT,
    farmer_id                      UUID REFERENCES farmers_users(user_id) ON DELETE SET NULL,
    payload_sha256                 TEXT NOT NULL,
    language                       TEXT NOT NULL DEFAULT 'en' CHECK (language IN ('en', 'fr', 'ar')),
    water_availability             TEXT NOT NULL CHECK (water_availability IN ('limited', 'moderate', 'abundant', 'unknown')),
    water_source                   TEXT NOT NULL CHECK (water_source IN ('groundwater', 'well', 'reservoir', 'river', 'rainfed', 'other')),
    irrigation_system              TEXT NOT NULL CHECK (irrigation_system IN ('drip', 'sprinkler', 'surface', 'none', 'unknown')),
    start_season                   TEXT NOT NULL CHECK (start_season IN ('Winter', 'Spring', 'Summer', 'Autumn')),
    start_year                     INTEGER NOT NULL CHECK (start_year BETWEEN 2024 AND 2035),
    horizon_seasons                INTEGER NOT NULL CHECK (horizon_seasons BETWEEN 2 AND 4),
    crop_history_flag              TEXT NOT NULL CHECK (crop_history_flag IN ('PROVIDED', 'EXPLICITLY_CONFIRMED_EMPTY', 'NOT_PROVIDED')),
    equipment_constraints_flag     TEXT NOT NULL CHECK (equipment_constraints_flag IN ('PROVIDED', 'EXPLICITLY_CONFIRMED_EMPTY', 'NOT_PROVIDED')),
    forage_weight_flag             TEXT NOT NULL CHECK (forage_weight_flag IN ('PROVIDED', 'NOT_PROVIDED')),
    request_status                 TEXT NOT NULL CHECK (request_status IN ('COMPLETED', 'FAILED')),
    original_request_json          JSONB NOT NULL,
    created_at_utc                 TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_analysis_requests_payload_sha ON analysis_requests (payload_sha256);
CREATE INDEX IF NOT EXISTS idx_analysis_requests_field_time ON analysis_requests (field_record_id, created_at_utc DESC);

-- 4. Crop History Records (Normalized User-Reported Antecedent Crop Logs)
CREATE TABLE IF NOT EXISTS crop_history_records (
    history_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_id             TEXT NOT NULL REFERENCES analysis_requests(analysis_id) ON DELETE CASCADE,
    field_record_id         UUID NOT NULL REFERENCES fields(field_record_id) ON DELETE CASCADE,
    season                  TEXT NOT NULL CHECK (season IN ('Winter', 'Spring', 'Summer', 'Autumn')),
    crop_year               INTEGER NOT NULL CHECK (crop_year BETWEEN 2010 AND 2035),
    planting_month          INTEGER CHECK (planting_month BETWEEN 1 AND 12),
    crop_id_resolved        TEXT,
    crop_name_raw           TEXT NOT NULL,
    normalization_status    TEXT NOT NULL,
    yield_tons_per_hectare  DOUBLE PRECISION CHECK (yield_tons_per_hectare >= 0),
    notes                   TEXT,
    provenance              TEXT NOT NULL DEFAULT 'USER_REPORTED'
);

CREATE INDEX IF NOT EXISTS idx_crop_history_analysis ON crop_history_records (analysis_id);

-- 5. Field Profiles (Automatically Extracted Phase F 4-Section Scientific Context)
CREATE TABLE IF NOT EXISTS field_profiles (
    profile_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_id             TEXT NOT NULL UNIQUE REFERENCES analysis_requests(analysis_id) ON DELETE CASCADE,
    profile_schema_version  TEXT NOT NULL,
    generated_at_utc        TIMESTAMPTZ NOT NULL,
    full_field_profile_json JSONB NOT NULL
);

-- 6. Recommendation Results (Validated Phase J Final Recommendation Output)
CREATE TABLE IF NOT EXISTS recommendation_results (
    recommendation_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_id                 TEXT NOT NULL UNIQUE REFERENCES analysis_requests(analysis_id) ON DELETE CASCADE,
    engine_request_id           TEXT NOT NULL,
    dataset_version_used        TEXT NOT NULL,
    decision_engine_version     TEXT NOT NULL,
    root_status                 TEXT NOT NULL CHECK (root_status IN ('COMPLETE', 'PARTIAL', 'FAILED')),
    field_plan_status           TEXT NOT NULL CHECK (field_plan_status IN ('COMPLETE', 'PARTIAL', 'NO_ELIGIBLE_STRATEGY')),
    recommendation_status       TEXT NOT NULL,
    suggested_strategy_id       TEXT,
    completeness_score          DOUBLE PRECISION NOT NULL CHECK (completeness_score BETWEEN 0.0 AND 1.0),
    climate_dataset_agreement   TEXT,
    stability_index             DOUBLE PRECISION,
    schema_valid                BOOLEAN NOT NULL CHECK (schema_valid IS TRUE),
    final_recommendation_json   JSONB NOT NULL,
    generated_at_utc            TIMESTAMPTZ NOT NULL
);

-- 7. Candidate Strategies (Indexed Strategy-Level Summary Rows for Advisory Dashboards & Filtering)
CREATE TABLE IF NOT EXISTS candidate_strategies (
    strategy_row_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_id           TEXT NOT NULL REFERENCES analysis_requests(analysis_id) ON DELETE CASCADE,
    strategy_id           TEXT NOT NULL,
    strategy_name         TEXT NOT NULL,
    is_existing_rotation  BOOLEAN NOT NULL,
    feasibility_status    TEXT NOT NULL,
    eligible_for_ranking  BOOLEAN NOT NULL,
    rank                  INTEGER,
    pareto_status         TEXT NOT NULL,
    weighted_score        DOUBLE PRECISION,
    seasons_json          JSONB NOT NULL,
    scores_snapshot_json  JSONB NOT NULL,
    UNIQUE (analysis_id, strategy_id)
);

CREATE INDEX IF NOT EXISTS idx_candidate_strategies_analysis_rank ON candidate_strategies (analysis_id, rank);

-- 8. Data Provenance & Quality Metadata (Dataset Audit Trail & Explicit Limitations per Analysis)
CREATE TABLE IF NOT EXISTS data_provenance_quality_metadata (
    provenance_id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_id                 TEXT NOT NULL UNIQUE REFERENCES analysis_requests(analysis_id) ON DELETE CASCADE,
    dataset_version_used        TEXT NOT NULL,
    quality_status_counts_json  JSONB NOT NULL,
    input_completeness_json     JSONB NOT NULL,
    missing_data_json           JSONB NOT NULL,
    warnings_json               JSONB NOT NULL,
    limitations_json            JSONB NOT NULL,
    recorded_at_utc             TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
