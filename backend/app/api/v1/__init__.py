"""API v1 router aggregator."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.analysis import router as analysis_router
from app.api.v1.auth import router as auth_router
from app.api.v1.catalog import router as catalog_router
from app.api.v1.demo import router as demo_router
from app.api.v1.farms import router as farms_router
from app.api.v1.fields import router as fields_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(analysis_router)
api_v1_router.include_router(auth_router)
api_v1_router.include_router(catalog_router)
api_v1_router.include_router(demo_router)
api_v1_router.include_router(farms_router)
api_v1_router.include_router(fields_router)

__all__ = ["api_v1_router"]
