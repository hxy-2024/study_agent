import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


LearningSignalStatusValue = Literal["active", "completed", "dismissed", "snoozed"]


class LearningSignalDraft(BaseModel):
    tenant_id: uuid.UUID
    user_id: uuid.UUID
    study_space_id: uuid.UUID
    chapter_id: uuid.UUID | None = None
    quiz_id: uuid.UUID | None = None
    agent_type: str
    signal_type: str
    priority: int = Field(ge=0, le=100)
    status: LearningSignalStatusValue = "active"
    dedupe_key: str
    available_at: datetime | None = None
    expires_at: datetime | None = None
    payload: dict = Field(default_factory=dict)


class LearningSignalResponse(LearningSignalDraft):
    id: uuid.UUID
    created_at: datetime | None = None
    updated_at: datetime | None = None


class LearningSignalSnoozeRequest(BaseModel):
    minutes: int = Field(default=60, ge=5, le=60 * 24 * 30)
