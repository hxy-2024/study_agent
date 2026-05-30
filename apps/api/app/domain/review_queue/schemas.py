import uuid
from typing import Literal

from pydantic import BaseModel, Field


ReviewQueueKind = Literal["continue_chapter", "review_chapter", "retake_quiz", "planner_action"]


class ReviewQueueItem(BaseModel):
    id: str
    kind: ReviewQueueKind
    learning_signal_id: uuid.UUID | None = None
    study_space_id: uuid.UUID
    chapter_id: uuid.UUID | None = None
    quiz_id: uuid.UUID | None = None
    title: str
    reason: str
    priority: int = Field(ge=0, le=100)
    estimated_minutes: int
    action_url: str
    source_signals: dict[str, int] = Field(default_factory=dict)


class ReviewQueueResponse(BaseModel):
    items: list[ReviewQueueItem] = Field(default_factory=list)
