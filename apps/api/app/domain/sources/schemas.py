import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.db.models import SourceStatus


class UploadPresignRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    study_space_id: uuid.UUID
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=120)


class UploadPresignResponse(BaseModel):
    source_id: uuid.UUID
    object_key: str
    upload_url: str
    method: str = "PUT"


class SourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    study_space_id: uuid.UUID
    filename: str
    content_type: str
    object_key: str
    status: SourceStatus
    error_message: str | None
    created_at: datetime


class SourceListResponse(BaseModel):
    sources: list[SourceResponse]


class SourceUploadedResponse(BaseModel):
    source: SourceResponse


class SourceChunkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_id: uuid.UUID
    chunk_index: int
    text: str
    token_count: int
    citation: dict
    is_active: bool
    created_at: datetime


class SourceChunkListResponse(BaseModel):
    chunks: list[SourceChunkResponse]
