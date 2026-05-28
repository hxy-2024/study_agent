import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class AgentRunGraphMetadata(BaseModel):
    graph_name: str | None = None
    thread_id: str | None = None
    checkpoint_backend: str | None = None
    state_schema_version: int | None = None
    node_trace: list[str] = Field(default_factory=list)


class AgentRunTimelineItem(BaseModel):
    id: uuid.UUID
    agent_type: str
    status: str
    model: str | None = None
    study_space_id: uuid.UUID
    chapter_id: uuid.UUID | None = None
    session_id: uuid.UUID | None = None
    message_id: uuid.UUID | None = None
    graph_name: str | None = None
    thread_id: str | None = None
    checkpoint_backend: str | None = None
    state_schema_version: int | None = None
    node_trace: list[str] = Field(default_factory=list)
    learning_signals: list[dict] = Field(default_factory=list)
    summary: str
    error_message: str | None = None
    created_at: datetime | None = None
    completed_at: datetime | None = None
    latency_ms: int | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class AgentRunTimelineResponse(BaseModel):
    runs: list[AgentRunTimelineItem] = Field(default_factory=list)
