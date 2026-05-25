import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class RouteChapter(BaseModel):
    order: int
    title: str
    description: str
    estimated_days: int


class StudySpaceCreate(BaseModel):
    tenant_id: uuid.UUID
    owner_user_id: uuid.UUID
    name: str = Field(min_length=1, max_length=160)
    goal: str = Field(min_length=1, max_length=4000)
    level: str = Field(default="beginner", max_length=60)
    intensity: str = Field(default="normal", max_length=60)
    target_days: int = Field(default=30, ge=1, le=365)


class StudySpaceRead(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    owner_user_id: uuid.UUID
    name: str
    goal: str
    level: str
    intensity: str
    target_days: int
    status: str
    route_outline: list[RouteChapter]
    created_at: datetime

    model_config = {"from_attributes": True}
