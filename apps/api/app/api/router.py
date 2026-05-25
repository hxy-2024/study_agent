from fastapi import APIRouter

from app.api import routes_health, routes_study_spaces

api_router = APIRouter()
api_router.include_router(routes_health.router)
api_router.include_router(routes_study_spaces.router)
