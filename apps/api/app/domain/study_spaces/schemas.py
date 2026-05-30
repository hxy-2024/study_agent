import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RouteChapter(BaseModel):
    order: int
    title: str
    description: str
    estimated_days: int


class StudySpaceCreate(BaseModel):
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


class StudySpaceImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payload: dict
    dry_run: bool = True


class StudySpaceImportResult(BaseModel):
    dry_run: bool
    can_restore: bool
    schema_version: int
    original_study_space_id: str
    summary: dict[str, int]
    tenant_rewrite: dict[str, str | None]
    user_rewrite: dict[str, str | None]
    id_remap: dict[str, dict[str, str]]
    warnings: list[str] = Field(default_factory=list)
    unsupported_write_models: list[str] = Field(default_factory=list)
