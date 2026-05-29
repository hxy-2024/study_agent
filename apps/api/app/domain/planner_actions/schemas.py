import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.sessions.schemas import SessionResponse


class PlannerActionResponse(BaseModel):
    id: uuid.UUID
    study_space_id: uuid.UUID
    chapter_id: uuid.UUID | None = None
    source_planner_state_id: uuid.UUID | None = None
    action_type: str
    status: str
    title: str
    rationale: str
    payload: dict = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PlannerActionListResponse(BaseModel):
    actions: list[PlannerActionResponse]


class PlannerActionExecutionResponse(BaseModel):
    action: PlannerActionResponse
    session: SessionResponse


class CreatePlannerActionsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    study_space_id: uuid.UUID


class CreateRuntimeActionsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    study_space_id: uuid.UUID
    chapter_id: uuid.UUID | None = None


class UpdatePlannerActionStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
