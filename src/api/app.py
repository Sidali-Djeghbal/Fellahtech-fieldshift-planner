"""FastAPI application for Field Shift — Guelma Wilaya Crop Rotation DSS (Phase L)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from field_profile_builder import FORBIDDEN_TECHNICAL_KEYS
from fieldshift_integration.config import PROJECT_ROOT
from src.agronomic import load_knowledge_base
from src.api.pipeline_service import (
    FarmerInputValidationError,
    OutputValidationError,
    PipelineExecutionError,
    check_geospatial_assets_status,
    compute_payload_sha256,
    derive_analysis_id,
    run_field_analysis_pipeline,
    validate_farmer_submission,
)
from src.api.repository import AnalysisRepository, DEFAULT_SQLITE_DB_PATH, SQLiteAnalysisRepository
from src.api.schemas import (
    FieldAnalyzeRequest,
    FieldAnalyzeResponse,
    FieldValidationRequest,
    FieldValidationResponse,
    HealthResponse,
    StoredAnalysisResponse,
)
from src.output import DATASET_VERSION_USED, DECISION_ENGINE_VERSION

FRONTEND_DIR = PROJECT_ROOT / "frontend"
GUELMA_BOUNDARY_GEOJSON = PROJECT_ROOT / "guelma_wilaya_boundary.geojson"


def _forbidden_hint_from_errors(errors: Any) -> Optional[str]:
    for err in errors or []:
        loc = [str(p).lower() for p in err.get("loc", ())]
        if any(part in FORBIDDEN_TECHNICAL_KEYS for part in loc):
            return (
                "Forbidden technical soil, weather, remote-sensing, or data-quality input supplied. "
                "Field Shift extracts soil and climate data automatically from the polygon."
            )
    return None


def create_app(repository: Optional[AnalysisRepository] = None) -> FastAPI:
    """Create configured FastAPI app with injected persistence repository."""
    if repository is None:
        db_path = os.environ.get("FIELDSHIFT_SQLITE_PATH", str(DEFAULT_SQLITE_DB_PATH))
        repo: AnalysisRepository = SQLiteAnalysisRepository(db_path=db_path)
    else:
        repo = repository

    application = FastAPI(
        title="Field Shift API — Guelma Crop Rotation DSS",
        version=DECISION_ENGINE_VERSION,
        description=(
            "Geospatial & agronomic crop rotation recommendation API for Guelma Wilaya, Algeria. "
            "Automatically extracts SoilGrids 250 m, ESA Crop Frequency 10 m, Sentinel-2, MODIS, "
            "GPM/SMAP 11 km, and NASA POWER context from a farmer-drawn GeoJSON Polygon."
        ),
    )
    application.state.repository = repo

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    @application.exception_handler(RequestValidationError)
    async def request_validation_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = exc.errors()
        hint = _forbidden_hint_from_errors(errors)
        return JSONResponse(
            status_code=422,
            content={
                "error_code": "INVALID_FARMER_INPUT",
                "message": hint or "Request payload failed farmer input schema validation.",
                "details": [
                    {
                        "loc": list(e.get("loc", ())),
                        "msg": str(e.get("msg", "")),
                        "type": str(e.get("type", "")),
                    }
                    for e in errors
                ],
            },
        )

    @application.exception_handler(FarmerInputValidationError)
    async def farmer_input_error_handler(_request: Request, exc: FarmerInputValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error_code": "FARMER_INPUT_POLICY_ERROR",
                "message": str(exc),
                "details": [],
            },
        )

    @application.exception_handler(OutputValidationError)
    @application.exception_handler(PipelineExecutionError)
    async def pipeline_error_handler(_request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={
                "error_code": "INTERNAL_OUTPUT_VALIDATION_ERROR",
                "message": "Recommendation failed internal Draft 2020-12 safety/contract validation.",
                "details": getattr(exc, "errors", []),
            },
        )

    @application.get("/api/v1/health", response_model=HealthResponse, tags=["System"])
    def get_health() -> Dict[str, Any]:
        kb = load_knowledge_base()
        geo_status = check_geospatial_assets_status()
        db_status = application.state.repository.status_info()
        status = "ok" if geo_status["all_core_assets_present"] else "degraded"
        return {
            "status": status,
            "service": "FieldShift-PhaseL-API",
            "decision_engine_version": DECISION_ENGINE_VERSION,
            "dataset_version_used": DATASET_VERSION_USED,
            "knowledge_base": {
                "crops_count": len(kb.crops),
                "crop_rules_count": len(kb.rules_catalog),
                "sequence_rules_count": len(kb.sequence_rules),
            },
            "geospatial_assets": geo_status,
            "database": db_status,
            "disclaimers": [
                "Supervised field yield & farmgate price validation remains NOT_VALIDATABLE locally.",
                "Outputs carry CONDITIONAL readiness pending DEM relief & Seybouse irrigation ECe verification.",
            ],
        }

    @application.post("/api/v1/fields/validate", response_model=FieldValidationResponse, tags=["Fields"])
    def validate_field(req: FieldValidationRequest) -> Dict[str, Any]:
        scientific_payload = req.to_scientific_payload()
        try:
            return validate_farmer_submission(scientific_payload)
        except FarmerInputValidationError:
            raise
        except ValueError as exc:
            msg = str(exc)
            err_code = (
                "INVALID_FIELD_POLYGON"
                if any(tok in msg.lower() for tok in ("polygon", "geometry", "guelma", "epsg", "area"))
                else "INVALID_PRIORITY_WEIGHTS"
                if "weight" in msg.lower()
                else "INVALID_ANALYSIS_INPUT"
            )
            raise HTTPException(
                status_code=422,
                detail={
                    "error_code": err_code,
                    "message": msg,
                },
            ) from exc

    @application.post("/api/v1/fields/analyze", response_model=FieldAnalyzeResponse, tags=["Analyses"])
    def analyze_field(req: FieldAnalyzeRequest) -> Dict[str, Any]:
        scientific_payload = req.to_scientific_payload()
        payload_sha256 = compute_payload_sha256(scientific_payload, language=req.language)
        analysis_id = derive_analysis_id(payload_sha256)

        repo_inst: AnalysisRepository = application.state.repository
        existing = repo_inst.get_analysis(analysis_id)
        if existing is not None:
            return {
                "analysis_id": analysis_id,
                "payload_sha256": payload_sha256,
                "reused_existing": True,
                "persistence_backend": existing["persistence_backend"],
                "field_profile_summary": existing["field_profile_summary"],
                "recommendation": existing["recommendation"],
            }

        try:
            result = run_field_analysis_pipeline(
                scientific_payload,
                analysis_id=analysis_id,
                language=req.language,
            )
        except FarmerInputValidationError:
            raise
        except ValueError as exc:
            msg = str(exc)
            err_code = (
                "INVALID_FIELD_POLYGON"
                if any(tok in msg.lower() for tok in ("polygon", "geometry", "guelma", "epsg", "area"))
                else "INVALID_PRIORITY_WEIGHTS"
                if "weight" in msg.lower()
                else "INVALID_ANALYSIS_INPUT"
            )
            raise HTTPException(
                status_code=422,
                detail={
                    "error_code": err_code,
                    "message": msg,
                },
            ) from exc

        repo_inst.save_analysis(
            analysis_id=analysis_id,
            payload_sha256=payload_sha256,
            original_request={
                "language": req.language,
                **scientific_payload,
            },
            field_profile=result["field_profile"],
            field_profile_summary=result["field_profile_summary"],
            recommendation=result["recommendation"],
            farmer_account=req.farmer_account.model_dump() if req.farmer_account else None,
        )

        return {
            "analysis_id": analysis_id,
            "payload_sha256": payload_sha256,
            "reused_existing": False,
            "persistence_backend": repo_inst.backend_name,
            "field_profile_summary": result["field_profile_summary"],
            "recommendation": result["recommendation"],
        }

    @application.get("/api/v1/analyses/{analysis_id}", response_model=StoredAnalysisResponse, tags=["Analyses"])
    def get_analysis(analysis_id: str) -> Dict[str, Any]:
        stored = application.state.repository.get_analysis(analysis_id)
        if stored is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error_code": "ANALYSIS_NOT_FOUND",
                    "message": f"No stored analysis found for analysis_id '{analysis_id}'.",
                },
            )
        return stored

    @application.get("/api/v1/reference/guelma-boundary", tags=["Reference"])
    def get_guelma_boundary() -> Dict[str, Any]:
        if not GUELMA_BOUNDARY_GEOJSON.is_file():
            raise HTTPException(status_code=404, detail="Guelma boundary GeoJSON asset missing.")
        return json.loads(GUELMA_BOUNDARY_GEOJSON.read_text(encoding="utf-8"))

    @application.get("/api/v1/reference/crops", tags=["Reference"])
    def get_reference_crops() -> Dict[str, Any]:
        kb = load_knowledge_base()
        crops = [
            {
                "crop_id": cid,
                "canonical_name": cdata["canonical_name"],
                "crop_category": cdata["crop_category"],
                "in_annual_rotation_scope": cdata["in_annual_rotation_scope"],
                "guelma_evidence_status": cdata["guelma_evidence_status"],
            }
            for cid, cdata in kb.crops.items()
        ]
        return {"crops": crops}

    if FRONTEND_DIR.is_dir():
        application.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

        @application.get("/", include_in_schema=False)
        def serve_farmer_interface() -> FileResponse:
            return FileResponse(str(FRONTEND_DIR / "index.html"))

    return application


app = create_app()
