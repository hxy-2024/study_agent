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


class DashboardResponse(BaseModel):
    spaces: list[DashboardSpace] = Field(default_factory=list)
    pending_actions: list[DashboardAction] = Field(default_factory=list)
    supervision_refresh_count: int = 0
    recent_agent_runs: list[DashboardAgentRun] = Field(default_factory=list)
