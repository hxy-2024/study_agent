import enum
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class StudySpaceStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    archived = "archived"


class SourceStatus(str, enum.Enum):
    pending_upload = "pending_upload"
    uploaded = "uploaded"
    processing = "processing"
    ready = "ready"
    failed = "failed"


class IngestionJobStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class LearningRouteStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    archived = "archived"


class ChapterStatus(str, enum.Enum):
    not_started = "not_started"
    active = "active"
    completed = "completed"


class SessionStatus(str, enum.Enum):
    active = "active"
    archived = "archived"


class MessageRole(str, enum.Enum):
    user = "user"
    assistant = "assistant"
    system = "system"


class AgentType(str, enum.Enum):
    space_planner = "space_planner"
    chapter_mentor = "chapter_mentor"
    session_tutor = "session_tutor"


class AgentRunStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Membership(Base):
    __tablename__ = "memberships"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(40), nullable=False, default="owner")


class StudySpace(Base):
    __tablename__ = "study_spaces"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    level: Mapped[str] = mapped_column(String(60), nullable=False, default="beginner")
    intensity: Mapped[str] = mapped_column(String(60), nullable=False, default="normal")
    target_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    status: Mapped[StudySpaceStatus] = mapped_column(
        Enum(StudySpaceStatus, name="study_space_status"),
        nullable=False,
        default=StudySpaceStatus.active,
    )
    route_outline: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    sources: Mapped[list["Source"]] = relationship(back_populates="study_space")
    learning_routes: Mapped[list["LearningRoute"]] = relationship(back_populates="study_space")
    chapters: Mapped[list["Chapter"]] = relationship(back_populates="study_space")
    sessions: Mapped[list["Session"]] = relationship(back_populates="study_space")
    chapter_mentor_states: Mapped[list["ChapterMentorState"]] = relationship(back_populates="study_space")


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    study_space_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("study_spaces.id"),
        nullable=False,
        index=True,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    object_key: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[SourceStatus] = mapped_column(
        Enum(SourceStatus, name="source_status"),
        nullable=False,
        default=SourceStatus.pending_upload,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    study_space: Mapped[StudySpace] = relationship(back_populates="sources")
    ingestion_jobs: Mapped[list["IngestionJob"]] = relationship(back_populates="source")
    chunks: Mapped[list["SourceChunk"]] = relationship(back_populates="source")
    message_citations: Mapped[list["MessageCitation"]] = relationship(back_populates="source")


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    study_space_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("study_spaces.id"), nullable=False, index=True)
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id"), nullable=False, index=True)
    status: Mapped[IngestionJobStatus] = mapped_column(
        Enum(IngestionJobStatus, name="ingestion_job_status"),
        nullable=False,
        default=IngestionJobStatus.pending,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    source: Mapped["Source"] = relationship(back_populates="ingestion_jobs")


class SourceChunk(Base):
    __tablename__ = "source_chunks"
    __table_args__ = (
        UniqueConstraint("source_id", "chunk_index", name="uq_source_chunks_source_index"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    study_space_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("study_spaces.id"), nullable=False, index=True)
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id"), nullable=False, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    citation: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    embedding: Mapped[list[float]] = mapped_column(Vector(16), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    source: Mapped["Source"] = relationship(back_populates="chunks")
    message_citations: Mapped[list["MessageCitation"]] = relationship(back_populates="source_chunk")


class LearningRoute(Base):
    __tablename__ = "learning_routes"
    __table_args__ = (
        UniqueConstraint("study_space_id", "version", name="uq_learning_routes_space_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    study_space_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("study_spaces.id"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[LearningRouteStatus] = mapped_column(
        Enum(LearningRouteStatus, name="learning_route_status"),
        nullable=False,
        default=LearningRouteStatus.draft,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    generation_strategy: Mapped[str] = mapped_column(String(80), nullable=False, default="deterministic")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    study_space: Mapped["StudySpace"] = relationship(back_populates="learning_routes")
    chapters: Mapped[list["Chapter"]] = relationship(back_populates="learning_route")


class Chapter(Base):
    __tablename__ = "chapters"
    __table_args__ = (
        UniqueConstraint("learning_route_id", "order_index", name="uq_chapters_route_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    study_space_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("study_spaces.id"), nullable=False, index=True)
    learning_route_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("learning_routes.id"), nullable=False, index=True)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    estimated_days: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[ChapterStatus] = mapped_column(
        Enum(ChapterStatus, name="chapter_status"),
        nullable=False,
        default=ChapterStatus.not_started,
    )
    source_chunk_refs: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    study_space: Mapped["StudySpace"] = relationship(back_populates="chapters")
    learning_route: Mapped["LearningRoute"] = relationship(back_populates="chapters")
    sessions: Mapped[list["Session"]] = relationship(back_populates="chapter")
    mentor_state: Mapped["ChapterMentorState"] = relationship(back_populates="chapter")


class ChapterMentorState(Base):
    __tablename__ = "chapter_mentor_states"
    __table_args__ = (
        UniqueConstraint("chapter_id", name="uq_chapter_mentor_states_chapter"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    study_space_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("study_spaces.id"), nullable=False, index=True)
    chapter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chapters.id"), nullable=False, index=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    weak_points: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    next_actions: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    evidence: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    source_session_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source_message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    study_space: Mapped["StudySpace"] = relationship(back_populates="chapter_mentor_states")
    chapter: Mapped["Chapter"] = relationship(back_populates="mentor_state")


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )
    study_space_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("study_spaces.id"),
        nullable=False,
        index=True,
    )
    chapter_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chapters.id"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus, name="session_status"),
        nullable=False,
        default=SessionStatus.active,
    )
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    study_space: Mapped["StudySpace"] = relationship(back_populates="sessions")
    chapter: Mapped["Chapter"] = relationship(back_populates="sessions")
    messages: Mapped[list["Message"]] = relationship(back_populates="session")
    agent_runs: Mapped[list["AgentRun"]] = relationship(back_populates="session")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )
    study_space_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("study_spaces.id"),
        nullable=False,
        index=True,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sessions.id"),
        nullable=False,
        index=True,
    )
    role: Mapped[MessageRole] = mapped_column(
        Enum(MessageRole, name="message_role"),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped["Session"] = relationship(back_populates="messages")
    citations: Mapped[list["MessageCitation"]] = relationship(back_populates="message")
    agent_runs: Mapped[list["AgentRun"]] = relationship(back_populates="message")


class MessageCitation(Base):
    __tablename__ = "message_citations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("messages.id"),
        nullable=False,
        index=True,
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sources.id"),
        nullable=False,
        index=True,
    )
    source_chunk_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("source_chunks.id"),
        nullable=False,
        index=True,
    )
    quote: Mapped[str] = mapped_column(Text, nullable=False)
    citation: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    message: Mapped["Message"] = relationship(back_populates="citations")
    source: Mapped["Source"] = relationship(back_populates="message_citations")
    source_chunk: Mapped["SourceChunk"] = relationship(back_populates="message_citations")


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )
    study_space_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("study_spaces.id"),
        nullable=False,
        index=True,
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sessions.id"),
        nullable=True,
        index=True,
    )
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("messages.id"),
        nullable=True,
        index=True,
    )
    agent_type: Mapped[AgentType] = mapped_column(
        Enum(AgentType, name="agent_type"),
        nullable=False,
    )
    status: Mapped[AgentRunStatus] = mapped_column(
        Enum(AgentRunStatus, name="agent_run_status"),
        nullable=False,
        default=AgentRunStatus.pending,
    )
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    input_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    output_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    session: Mapped["Session"] = relationship(back_populates="agent_runs")
    message: Mapped["Message"] = relationship(back_populates="agent_runs")
