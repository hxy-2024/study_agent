import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


QuizMasteryTrend = Literal["single_attempt", "improving", "declining", "flat"]


class QuizMasterySignal(BaseModel):
    study_space_id: uuid.UUID
    chapter_id: uuid.UUID
    attempt_count: int = Field(ge=1)
    latest_score: int = Field(ge=0, le=100)
    trend: QuizMasteryTrend
    weak_points: list[str] = Field(default_factory=list)
    retake_recommended: bool
    reason: str
    latest_submission_id: uuid.UUID | None = None
    latest_submitted_at: datetime | None = None
