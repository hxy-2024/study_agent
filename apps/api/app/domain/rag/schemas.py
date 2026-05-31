import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class IngestSourceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    embedding_preset: str | None = Field(default=None, max_length=200)


class IngestSourceResponse(BaseModel):
    job_id: uuid.UUID
    source_id: uuid.UUID
    status: str
    chunk_count: int


class RetrieveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    study_space_id: uuid.UUID
    query: str = Field(min_length=1, max_length=2000)
    limit: int = Field(default=5, ge=1, le=20)


class RetrievedChunkResponse(BaseModel):
    chunk_id: uuid.UUID
    source_id: uuid.UUID
    chunk_index: int
    text: str
    citation: dict[str, Any]
    score: float


class RetrieveResponse(BaseModel):
    query: str
    chunks: list[RetrievedChunkResponse]
