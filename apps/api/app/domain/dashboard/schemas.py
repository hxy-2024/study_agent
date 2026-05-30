import uuid

from pydantic import BaseModel, Field


class DashboardSpace(BaseModel):
    id: uuid.UUID
    name: str
    goal: str
    status: str
    target_days: int


class DashboardAction(BaseModel):
    id: uuid.UUID
    study_space_id: uuid.UUID
    chapter_id: uuid.UUID | None = None
    title: str
    status: str


class DashboardAgentRun(BaseModel):
    id: uuid.UUID
    agent_type: str
    status: str
    summary: str


class DashboardRecommendationAction(BaseModel):
    title: str
    action_label: str
    action_url: str
    recommendation_type: str
    reason: str | None = None
    estimated_minutes: int | None = None
    study_space_id: uuid.UUID | None = None
    chapter_id: uuid.UUID | None = None


class DashboardRecommendation(DashboardRecommendationAction):
    agent_type: str = "main_agent"
    freshness: str = "deterministic_fallback"
    secondary_actions: list[DashboardRecommendationAction] = Field(default_factory=list)


class DashboardResponse(BaseModel):
    spaces: list[DashboardSpace] = Field(default_factory=list)
    pending_actions: list[DashboardAction] = Field(default_factory=list)
    supervision_refresh_count: int = 0
    recent_agent_runs: list[DashboardAgentRun] = Field(default_factory=list)
    today_recommendation: DashboardRecommendation | None = None
