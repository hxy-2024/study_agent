import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ChapterMentorStateRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ChapterMentorStateResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    study_space_id: uuid.UUID
    chapter_id: uuid.UUID
    summary: str
    weak_points: list[str]
    next_actions: list[str]
    evidence: list[dict]
    source_session_count: int
    source_message_count: int
    latest_session_tutor_run_at: datetime | None = None
    needs_supervision_refresh: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None
