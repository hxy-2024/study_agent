import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RouteDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_chapters: int = Field(default=5, ge=3, le=8)


class LearningRouteResponse(BaseModel):
    id: uuid.UUID
    study_space_id: uuid.UUID
    version: int
    status: str
    title: str
    summary: str
    generation_strategy: str
    created_at: datetime | None = None
    activated_at: datetime | None = None


class ChapterResponse(BaseModel):
    id: uuid.UUID
    learning_route_id: uuid.UUID
    order_index: int
    title: str
    goal: str
    summary: str
    estimated_days: int
    status: str
    source_chunk_refs: list[dict]


class RouteWithChaptersResponse(BaseModel):
    route: LearningRouteResponse
    chapters: list[ChapterResponse]


class RoutesListResponse(BaseModel):
    routes: list[RouteWithChaptersResponse]


class ChaptersListResponse(BaseModel):
    chapters: list[ChapterResponse]
