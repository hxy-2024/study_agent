from fastapi import APIRouter

from app.api import (
    routes_agent_runtime,
    routes_chapter_mentor_state,
    routes_chapter_study,
    routes_dashboard,
    routes_health,
    routes_ingestion,
    routes_learning_routes,
    routes_planner_actions,
    routes_quizzes,
    routes_retrieval,
    routes_sessions,
    routes_sources,
    routes_space_planner,
    routes_study_spaces,
    routes_uploads,
)

api_router = APIRouter()
api_router.include_router(routes_agent_runtime.router)
api_router.include_router(routes_health.router)
api_router.include_router(routes_chapter_mentor_state.router)
api_router.include_router(routes_chapter_study.router)
api_router.include_router(routes_dashboard.router)
api_router.include_router(routes_ingestion.router)
api_router.include_router(routes_learning_routes.router)
api_router.include_router(routes_planner_actions.router)
api_router.include_router(routes_quizzes.router)
api_router.include_router(routes_retrieval.router)
api_router.include_router(routes_sessions.router)
api_router.include_router(routes_sources.router)
api_router.include_router(routes_space_planner.router)
api_router.include_router(routes_study_spaces.router)
api_router.include_router(routes_uploads.router)
