import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.db.models import MessageRole


class SessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=200)


class SessionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)


class SessionResponse(BaseModel):
    id: uuid.UUID
    study_space_id: uuid.UUID
    chapter_id: uuid.UUID
    title: str
    status: str
    summary: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class MessageCitationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: uuid.UUID
    source_chunk_id: uuid.UUID
    quote: str = Field(min_length=1)
    citation: dict = Field(default_factory=dict)


class MessageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: MessageRole
    content: str = Field(min_length=1)
    metadata: dict = Field(default_factory=dict)
    citations: list[MessageCitationCreate] = Field(default_factory=list)


class MessageCitationResponse(BaseModel):
    id: uuid.UUID
    message_id: uuid.UUID
    source_id: uuid.UUID
    source_chunk_id: uuid.UUID
    chunk_id: uuid.UUID
    source_filename: str
    chunk_index: int
    text: str
    quote: str
    citation: dict


class MessageResponse(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    role: str
    content: str
    metadata: dict = Field(default_factory=dict)
    citations: list[MessageCitationResponse] = Field(default_factory=list)
    created_at: datetime | None = None


class SessionsListResponse(BaseModel):
    sessions: list[SessionResponse]


class MessagesListResponse(BaseModel):
    messages: list[MessageResponse]


class TutorMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1, max_length=4000)
    web_search_enabled: bool | None = None
