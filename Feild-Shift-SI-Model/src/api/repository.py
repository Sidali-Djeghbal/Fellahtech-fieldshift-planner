"""Persistence repositories for Field Shift Phase L (8 normalized entities).

Implements:
- AnalysisRepository (abstract contract)
- SQLiteAnalysisRepository (runnable local database matching all 8 PostGIS tables)
- PostgresPostGISRepository (PostgreSQL + PostGIS adapter aligned with db/schema_postgis.sql,
  explicitly reporting disconnected when host PostGIS extension / psycopg driver is absent)
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from fieldshift_integration.config import DATA_DIR

DEFAULT_SQLITE_DB_PATH = DATA_DIR / "app_state" / "fieldshift_analyses.db"


class DatabaseUnavailableError(RuntimeError):
    """Raised when an unconfigured or disconnected database backend (e.g., PostGIS) is requested."""


class AnalysisRepository(ABC):
    """Persistence contract covering all 8 entities in db/schema_postgis.sql."""

    backend_name: str = "abstract"

    @abstractmethod
    def status_info(self) -> Dict[str, Any]:
        """Return health/connectivity status for /api/v1/health."""

    @abstractmethod
    def save_analysis(
        self,
        *,
        analysis_id: str,
        payload_sha256: str,
        original_request: Dict[str, Any],
        field_profile: Dict[str, Any],
        field_profile_summary: Dict[str, Any],
        recommendation: Dict[str, Any],
        farmer_account: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Persist complete normalized analysis transactionally across 8 entities."""

    @abstractmethod
    def get_analysis(self, analysis_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve persisted analysis envelope + recommendation by analysis_id."""


class SQLiteAnalysisRepository(AnalysisRepository):
    """Zero-dependency SQLite 3 implementation mirroring the 8 PostgreSQL/PostGIS entities."""

    backend_name = "sqlite_local"

    def __init__(self, db_path: Path | str = DEFAULT_SQLITE_DB_PATH) -> None:
        self.db_path_str = str(db_path)
        if self.db_path_str != ":memory:":
            Path(self.db_path_str).parent.mkdir(parents=True, exist_ok=True)
        self._conn_memory: Optional[sqlite3.Connection] = (
            sqlite3.connect(":memory:", check_same_thread=False) if self.db_path_str == ":memory:" else None
        )
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        if self._conn_memory is not None:
            conn = self._conn_memory
        else:
            conn = sqlite3.connect(self.db_path_str, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _close_if_file(self, conn: sqlite3.Connection) -> None:
        if self._conn_memory is None:
            conn.close()

    def _init_schema(self) -> None:
        conn = self._connect()
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS farmers_users (
                    user_id TEXT PRIMARY KEY,
                    role TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    phone_hash TEXT,
                    commune_name TEXT,
                    preferred_language TEXT NOT NULL DEFAULT 'en',
                    created_at_utc TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS fields (
                    field_record_id TEXT PRIMARY KEY,
                    farmer_id TEXT REFERENCES farmers_users(user_id) ON DELETE SET NULL,
                    external_field_id TEXT NOT NULL,
                    field_name TEXT,
                    geometry_wgs84_geojson TEXT NOT NULL,
                    centroid_lon REAL NOT NULL,
                    centroid_lat REAL NOT NULL,
                    area_ha REAL NOT NULL,
                    perimeter_m REAL NOT NULL,
                    wilaya_overlap_pct REAL NOT NULL,
                    primary_commune TEXT,
                    created_at_utc TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS analysis_requests (
                    analysis_id TEXT PRIMARY KEY,
                    field_record_id TEXT NOT NULL REFERENCES fields(field_record_id) ON DELETE RESTRICT,
                    farmer_id TEXT REFERENCES farmers_users(user_id) ON DELETE SET NULL,
                    payload_sha256 TEXT NOT NULL,
                    language TEXT NOT NULL,
                    water_availability TEXT NOT NULL,
                    water_source TEXT NOT NULL,
                    irrigation_system TEXT NOT NULL,
                    start_season TEXT NOT NULL,
                    start_year INTEGER NOT NULL,
                    horizon_seasons INTEGER NOT NULL,
                    crop_history_flag TEXT NOT NULL,
                    equipment_constraints_flag TEXT NOT NULL,
                    forage_weight_flag TEXT NOT NULL,
                    request_status TEXT NOT NULL,
                    original_request_json TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS crop_history_records (
                    history_id TEXT PRIMARY KEY,
                    analysis_id TEXT NOT NULL REFERENCES analysis_requests(analysis_id) ON DELETE CASCADE,
                    field_record_id TEXT NOT NULL REFERENCES fields(field_record_id) ON DELETE CASCADE,
                    season TEXT NOT NULL,
                    crop_year INTEGER NOT NULL,
                    planting_month INTEGER,
                    crop_id_resolved TEXT,
                    crop_name_raw TEXT NOT NULL,
                    normalization_status TEXT NOT NULL,
                    yield_tons_per_hectare REAL,
                    notes TEXT,
                    provenance TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS field_profiles (
                    profile_id TEXT PRIMARY KEY,
                    analysis_id TEXT NOT NULL UNIQUE REFERENCES analysis_requests(analysis_id) ON DELETE CASCADE,
                    profile_schema_version TEXT NOT NULL,
                    generated_at_utc TEXT NOT NULL,
                    field_profile_summary_json TEXT NOT NULL,
                    full_field_profile_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS recommendation_results (
                    recommendation_id TEXT PRIMARY KEY,
                    analysis_id TEXT NOT NULL UNIQUE REFERENCES analysis_requests(analysis_id) ON DELETE CASCADE,
                    engine_request_id TEXT NOT NULL,
                    dataset_version_used TEXT NOT NULL,
                    decision_engine_version TEXT NOT NULL,
                    root_status TEXT NOT NULL,
                    field_plan_status TEXT NOT NULL,
                    recommendation_status TEXT NOT NULL,
                    suggested_strategy_id TEXT,
                    completeness_score REAL NOT NULL,
                    climate_dataset_agreement TEXT,
                    stability_index REAL,
                    schema_valid INTEGER NOT NULL CHECK (schema_valid = 1),
                    final_recommendation_json TEXT NOT NULL,
                    generated_at_utc TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS candidate_strategies (
                    strategy_row_id TEXT PRIMARY KEY,
                    analysis_id TEXT NOT NULL REFERENCES analysis_requests(analysis_id) ON DELETE CASCADE,
                    strategy_id TEXT NOT NULL,
                    strategy_name TEXT NOT NULL,
                    is_existing_rotation INTEGER NOT NULL,
                    feasibility_status TEXT NOT NULL,
                    eligible_for_ranking INTEGER NOT NULL,
                    rank INTEGER,
                    pareto_status TEXT NOT NULL,
                    weighted_score REAL,
                    seasons_json TEXT NOT NULL,
                    scores_snapshot_json TEXT NOT NULL,
                    UNIQUE (analysis_id, strategy_id)
                );

                CREATE TABLE IF NOT EXISTS data_provenance_quality_metadata (
                    provenance_id TEXT PRIMARY KEY,
                    analysis_id TEXT NOT NULL UNIQUE REFERENCES analysis_requests(analysis_id) ON DELETE CASCADE,
                    dataset_version_used TEXT NOT NULL,
                    quality_status_counts_json TEXT NOT NULL,
                    input_completeness_json TEXT NOT NULL,
                    missing_data_json TEXT NOT NULL,
                    warnings_json TEXT NOT NULL,
                    limitations_json TEXT NOT NULL,
                    recorded_at_utc TEXT NOT NULL
                );
                """
            )
            conn.commit()
        finally:
            self._close_if_file(conn)

    def status_info(self) -> Dict[str, Any]:
        conn = self._connect()
        try:
            tables = [
                r["name"]
                for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
            ]
            count = conn.execute("SELECT COUNT(*) AS n FROM analysis_requests").fetchone()["n"]
            return {
                "active_backend": self.backend_name,
                "sqlite_path": self.db_path_str,
                "entities_present": tables,
                "stored_analyses_count": int(count),
                "postgres_postgis_status": "DISCONNECTED (DDL ready in db/schema_postgis.sql; host PostGIS extension & psycopg driver not provisioned)",
            }
        finally:
            self._close_if_file(conn)

    def save_analysis(
        self,
        *,
        analysis_id: str,
        payload_sha256: str,
        original_request: Dict[str, Any],
        field_profile: Dict[str, Any],
        field_profile_summary: Dict[str, Any],
        recommendation: Dict[str, Any],
        farmer_account: Optional[Dict[str, Any]] = None,
    ) -> str:
        conn = self._connect()
        now_utc = datetime.now(timezone.utc).isoformat()
        sec_a = field_profile["section_a_farmer_provided"]
        sv = field_profile["section_b_extracted_geospatial"]["spatial_validation"]
        sec_d = field_profile["section_d_quality_and_uncertainty"]
        flags = sec_a["input_completeness_flags"]
        plan = sec_a["planning"]
        water = sec_a["water"]
        fld = sec_a["field"]
        fplan = recommendation["field_plans"][0]
        sens = fplan.get("sensitivity_summary", {})
        clim_ag = sens.get("climate_sensitivity", {}).get("climate_dataset_agreement")

        try:
            existing = conn.execute(
                "SELECT analysis_id FROM analysis_requests WHERE analysis_id = ?",
                (analysis_id,),
            ).fetchone()
            if existing is not None:
                return analysis_id

            acct = farmer_account or {}
            user_id = acct.get("user_id") or "USR_ANONYMOUS_PILOT"
            conn.execute(
                """
                INSERT OR IGNORE INTO farmers_users (
                    user_id, role, display_name, phone_hash, commune_name, preferred_language, created_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    acct.get("role", "anonymous_pilot"),
                    acct.get("display_name", "Guelma Pilot User"),
                    None,
                    acct.get("commune_name") or (sv.get("primary_commune") or {}).get("name_2"),
                    recommendation.get("language", "en"),
                    now_utc,
                ),
            )

            field_record_id = f"FLD_{uuid.uuid5(uuid.NAMESPACE_URL, analysis_id)}"
            conn.execute(
                """
                INSERT INTO fields (
                    field_record_id, farmer_id, external_field_id, field_name,
                    geometry_wgs84_geojson, centroid_lon, centroid_lat,
                    area_ha, perimeter_m, wilaya_overlap_pct, primary_commune, created_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    field_record_id,
                    user_id,
                    fld["field_id"],
                    fld.get("field_name"),
                    json.dumps(fld["geometry"], separators=(",", ":")),
                    float(sv["centroid_lon_lat"][0]),
                    float(sv["centroid_lon_lat"][1]),
                    float(sv["area_ha"]),
                    float(sv["perimeter_m"]),
                    float(sv["wilaya_overlap_pct"]),
                    (sv.get("primary_commune") or {}).get("name_2"),
                    now_utc,
                ),
            )

            conn.execute(
                """
                INSERT INTO analysis_requests (
                    analysis_id, field_record_id, farmer_id, payload_sha256, language,
                    water_availability, water_source, irrigation_system,
                    start_season, start_year, horizon_seasons,
                    crop_history_flag, equipment_constraints_flag, forage_weight_flag,
                    request_status, original_request_json, created_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    analysis_id,
                    field_record_id,
                    user_id,
                    payload_sha256,
                    recommendation.get("language", "en"),
                    water["availability"],
                    water["source"],
                    water["irrigation_system"],
                    plan["start_season"],
                    int(plan["start_year"]),
                    int(plan["horizon_seasons"]),
                    flags.get("crop_history", "NOT_PROVIDED"),
                    flags.get("equipment_constraints", "NOT_PROVIDED"),
                    flags.get("forage_value_weight", "NOT_PROVIDED"),
                    "COMPLETED",
                    json.dumps(original_request, ensure_ascii=False),
                    now_utc,
                ),
            )

            for item in sec_a.get("crop_history") or []:
                conn.execute(
                    """
                    INSERT INTO crop_history_records (
                        history_id, analysis_id, field_record_id, season, crop_year,
                        planting_month, crop_id_resolved, crop_name_raw, normalization_status,
                        yield_tons_per_hectare, notes, provenance
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        analysis_id,
                        field_record_id,
                        item["season"],
                        int(item["year"]),
                        item.get("planting_month"),
                        item.get("crop_id_resolved"),
                        item["crop_name_raw"],
                        item["normalization_status"],
                        item.get("yield_tons_per_hectare"),
                        item.get("notes"),
                        item.get("provenance", "USER_REPORTED"),
                    ),
                )

            conn.execute(
                """
                INSERT INTO field_profiles (
                    profile_id, analysis_id, profile_schema_version, generated_at_utc,
                    field_profile_summary_json, full_field_profile_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    analysis_id,
                    field_profile["profile_schema_version"],
                    field_profile["generated_at_utc"],
                    json.dumps(field_profile_summary, ensure_ascii=False),
                    json.dumps(field_profile, ensure_ascii=False),
                ),
            )

            conn.execute(
                """
                INSERT INTO recommendation_results (
                    recommendation_id, analysis_id, engine_request_id, dataset_version_used,
                    decision_engine_version, root_status, field_plan_status, recommendation_status,
                    suggested_strategy_id, completeness_score, climate_dataset_agreement,
                    stability_index, schema_valid, final_recommendation_json, generated_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    analysis_id,
                    recommendation["request_id"],
                    recommendation["dataset_version_used"],
                    recommendation["decision_engine_version"],
                    recommendation["status"],
                    fplan["status"],
                    fplan["recommendation_status"],
                    fplan["suggested_strategy_id"],
                    float(fplan["data_quality"]["completeness_score"]),
                    clim_ag,
                    sens.get("stability_index"),
                    1,
                    json.dumps(recommendation, ensure_ascii=False),
                    recommendation["generated_at"],
                ),
            )

            for s in fplan["strategies"]:
                conn.execute(
                    """
                    INSERT INTO candidate_strategies (
                        strategy_row_id, analysis_id, strategy_id, strategy_name,
                        is_existing_rotation, feasibility_status, eligible_for_ranking,
                        rank, pareto_status, weighted_score, seasons_json, scores_snapshot_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        analysis_id,
                        s["strategy_id"],
                        s["name"],
                        1 if s["is_existing_rotation"] else 0,
                        s["feasibility_status"],
                        1 if s["rank"] is not None or s["pareto_status"] != "EXCLUDED_INFEASIBLE" else 0,
                        s["rank"],
                        s["pareto_status"],
                        s["weighted_score"],
                        json.dumps(s["seasons"], ensure_ascii=False),
                        json.dumps(
                            {k: {"score": v["score"], "status": v["status"]} for k, v in s["scores"].items()},
                            ensure_ascii=False,
                        ),
                    ),
                )

            dq = fplan["data_quality"]
            conn.execute(
                """
                INSERT INTO data_provenance_quality_metadata (
                    provenance_id, analysis_id, dataset_version_used,
                    quality_status_counts_json, input_completeness_json,
                    missing_data_json, warnings_json, limitations_json, recorded_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    analysis_id,
                    recommendation["dataset_version_used"],
                    json.dumps(sec_d["quality_status_counts"], ensure_ascii=False),
                    json.dumps(dq["input_completeness_flags"], ensure_ascii=False),
                    json.dumps(dq["missing_data"], ensure_ascii=False),
                    json.dumps(dq["warnings"], ensure_ascii=False),
                    json.dumps(dq["limitations"], ensure_ascii=False),
                    now_utc,
                ),
            )

            conn.commit()
            return analysis_id
        except Exception:
            conn.rollback()
            raise
        finally:
            self._close_if_file(conn)

    def get_analysis(self, analysis_id: str) -> Optional[Dict[str, Any]]:
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT
                    ar.analysis_id,
                    ar.created_at_utc,
                    ar.payload_sha256,
                    ar.original_request_json,
                    fp.field_profile_summary_json,
                    rr.final_recommendation_json
                FROM analysis_requests ar
                JOIN field_profiles fp ON fp.analysis_id = ar.analysis_id
                JOIN recommendation_results rr ON rr.analysis_id = ar.analysis_id
                WHERE ar.analysis_id = ?
                """,
                (analysis_id,),
            ).fetchone()
            if row is None:
                return None
            return {
                "analysis_id": row["analysis_id"],
                "created_at_utc": row["created_at_utc"],
                "payload_sha256": row["payload_sha256"],
                "persistence_backend": self.backend_name,
                "original_request": json.loads(row["original_request_json"]),
                "field_profile_summary": json.loads(row["field_profile_summary_json"]),
                "recommendation": json.loads(row["final_recommendation_json"]),
            }
        finally:
            self._close_if_file(conn)


class PostgresPostGISRepository(AnalysisRepository):
    """PostgreSQL + PostGIS repository adapter aligned with db/schema_postgis.sql.

    Reports DISCONNECTED until host PostGIS extension + psycopg driver + DSN are configured.
    """

    backend_name = "postgresql_postgis"

    def __init__(self, dsn: Optional[str] = None) -> None:
        self.dsn = dsn

    def status_info(self) -> Dict[str, Any]:
        return {
            "active_backend": "DISCONNECTED",
            "configured_dsn": bool(self.dsn),
            "ddl_schema": "db/schema_postgis.sql",
            "reason": "Host PostGIS extension and psycopg driver are not installed in this environment.",
        }

    def save_analysis(self, **kwargs: Any) -> str:
        raise DatabaseUnavailableError(
            "PostgreSQL+PostGIS runtime is disconnected: install host postgis package, psycopg driver, and configure FIELDSHIFT_PG_DSN."
        )

    def get_analysis(self, analysis_id: str) -> Optional[Dict[str, Any]]:
        raise DatabaseUnavailableError(
            "PostgreSQL+PostGIS runtime is disconnected: install host postgis package, psycopg driver, and configure FIELDSHIFT_PG_DSN."
        )
