import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


AnnotationKind = Literal["note", "highlight"]


class ChapterAnnotationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: AnnotationKind
    content: str | None = Field(default=None, max_length=8000)
    quote: str | None = Field(default=None, max_length=4000)
    source_chunk_id: uuid.UUID | None = None
    anchor: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_annotation_body(self) -> "ChapterAnnotationCreateRequest":
        if self.kind == "note" and not (self.content or "").strip():
            raise ValueError("Notes require content")
        if self.kind == "highlight" and not (self.quote or "").strip():
            raise ValueError("Highlights require quote")
        return self


class ChapterAnnotationUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str | None = Field(default=None, max_length=8000)
    quote: str | None = Field(default=None, max_length=4000)
    anchor: dict | None = None


class ChapterAnnotationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    user_id: uuid.UUID
    study_space_id: uuid.UUID
    chapter_id: uuid.UUID
    source_chunk_id: uuid.UUID | None
    kind: str
    content: str | None
    quote: str | None
    anchor: dict
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ChapterAnnotationListResponse(BaseModel):
    annotations: list[ChapterAnnotationResponse]


class ChapterAnnotationMutationResponse(BaseModel):
    annotation: ChapterAnnotationResponse
