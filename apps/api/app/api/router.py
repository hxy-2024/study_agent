from fastapi import APIRouter

from app.api import (
    routes_health,
    routes_ingestion,
    routes_retrieval,
    routes_study_spaces,
    routes_uploads,
)

api_router = APIRouter()
api_router.include_router(routes_health.router)
api_router.include_router(routes_ingestion.router)
api_router.include_router(routes_retrieval.router)
api_router.include_router(routes_study_spaces.router)
api_router.include_router(routes_uploads.router)
