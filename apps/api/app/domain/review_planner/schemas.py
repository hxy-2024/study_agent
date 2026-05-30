import uuid

from pydantic import BaseModel, Field


class ReviewCandidate(BaseModel):
    chapter_id: uuid.UUID
    study_space_id: uuid.UUID
    title: str
    reason: str
    score: int = Field(ge=0, le=100)
    weak_points: list[str] = Field(default_factory=list)
    source: str
