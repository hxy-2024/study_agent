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
