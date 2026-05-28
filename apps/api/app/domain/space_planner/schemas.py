import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RunSpacePlannerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    study_space_id: uuid.UUID


class PlannerChapterRisk(BaseModel):
    chapter_id: uuid.UUID
    title: str
    reason: str
    score_percent: int | None = None


class PlannerReviewRecommendation(BaseModel):
    chapter_id: uuid.UUID
    title: str
    action: str
    reason: str


class PlannerRouteAdjustment(BaseModel):
    kind: str
    chapter_id: uuid.UUID | None = None
    title: str
    rationale: str


class SpacePlannerStateResponse(BaseModel):
    id: uuid.UUID
    study_space_id: uuid.UUID
    summary: str
    next_chapter_id: uuid.UUID | None = None
    risk_chapters: list[PlannerChapterRisk] = Field(default_factory=list)
    review_recommendations: list[PlannerReviewRecommendation] = Field(default_factory=list)
    route_adjustments: list[PlannerRouteAdjustment] = Field(default_factory=list)
    evidence: list[dict] = Field(default_factory=list)
    updated_at: datetime | None = None
