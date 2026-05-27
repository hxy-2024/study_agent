"""sessions messages agent runs

Revision ID: 0004_sessions_messages_agent_runs
Revises: 0003_learning_routes
Create Date: 2026-05-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_sessions_messages_agent_runs"
down_revision: str | None = "0003_learning_routes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    session_status = postgresql.ENUM("active", "archived", name="session_status")
    message_role = postgresql.ENUM("user", "assistant", "system", name="message_role")
    agent_type = postgresql.ENUM(
        "space_planner",
        "chapter_mentor",
        "session_tutor",
        name="agent_type",
    )
    agent_run_status = postgresql.ENUM(
        "pending",
        "running",
        "completed",
        "failed",
        name="agent_run_status",
    )
    session_status.create(op.get_bind(), checkfirst=True)
    message_role.create(op.get_bind(), checkfirst=True)
    agent_type.create(op.get_bind(), checkfirst=True)
    agent_run_status.create(op.get_bind(), checkfirst=True)

    session_status_column = postgresql.ENUM(
        "active",
        "archived",
        name="session_status",
        create_type=False,
    )
    message_role_column = postgresql.ENUM(
        "user",
        "assistant",
        "system",
        name="message_role",
        create_type=False,
    )
    agent_type_column = postgresql.ENUM(
        "space_planner",
        "chapter_mentor",
        "session_tutor",
        name="agent_type",
        create_type=False,
    )
    agent_run_status_column = postgresql.ENUM(
        "pending",
        "running",
        "completed",
        "failed",
        name="agent_run_status",
        create_type=False,
    )

    op.create_table(
        "sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            nullable=False,
        ),
        sa.Column(
            "study_space_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("study_spaces.id"),
            nullable=False,
        ),
        sa.Column(
            "chapter_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chapters.id"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("status", session_status_column, nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_sessions_tenant_id", "sessions", ["tenant_id"])
    op.create_index("ix_sessions_study_space_id", "sessions", ["study_space_id"])
    op.create_index("ix_sessions_chapter_id", "sessions", ["chapter_id"])

    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            nullable=False,
        ),
        sa.Column(
            "study_space_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("study_spaces.id"),
            nullable=False,
        ),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sessions.id"),
            nullable=False,
        ),
        sa.Column("role", message_role_column, nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_messages_tenant_id", "messages", ["tenant_id"])
    op.create_index("ix_messages_study_space_id", "messages", ["study_space_id"])
    op.create_index("ix_messages_session_id", "messages", ["session_id"])

    op.create_table(
        "message_citations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            nullable=False,
        ),
        sa.Column(
            "message_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("messages.id"),
            nullable=False,
        ),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sources.id"),
            nullable=False,
        ),
        sa.Column(
            "source_chunk_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("source_chunks.id"),
            nullable=False,
        ),
        sa.Column("quote", sa.Text(), nullable=False),
        sa.Column(
            "citation",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_message_citations_tenant_id", "message_citations", ["tenant_id"])
    op.create_index("ix_message_citations_message_id", "message_citations", ["message_id"])
    op.create_index("ix_message_citations_source_id", "message_citations", ["source_id"])
    op.create_index(
        "ix_message_citations_source_chunk_id",
        "message_citations",
        ["source_chunk_id"],
    )

    op.create_table(
        "agent_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            nullable=False,
        ),
        sa.Column(
            "study_space_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("study_spaces.id"),
            nullable=False,
        ),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sessions.id"),
            nullable=True,
        ),
        sa.Column(
            "message_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("messages.id"),
            nullable=True,
        ),
        sa.Column("agent_type", agent_type_column, nullable=False),
        sa.Column("status", agent_run_status_column, nullable=False),
        sa.Column("model", sa.String(length=120), nullable=True),
        sa.Column(
            "input_payload",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "output_payload",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_agent_runs_tenant_id", "agent_runs", ["tenant_id"])
    op.create_index("ix_agent_runs_study_space_id", "agent_runs", ["study_space_id"])
    op.create_index("ix_agent_runs_session_id", "agent_runs", ["session_id"])
    op.create_index("ix_agent_runs_message_id", "agent_runs", ["message_id"])


def downgrade() -> None:
    op.drop_index("ix_agent_runs_message_id", table_name="agent_runs")
    op.drop_index("ix_agent_runs_session_id", table_name="agent_runs")
    op.drop_index("ix_agent_runs_study_space_id", table_name="agent_runs")
    op.drop_index("ix_agent_runs_tenant_id", table_name="agent_runs")
    op.drop_table("agent_runs")
    op.drop_index("ix_message_citations_source_chunk_id", table_name="message_citations")
    op.drop_index("ix_message_citations_source_id", table_name="message_citations")
    op.drop_index("ix_message_citations_message_id", table_name="message_citations")
    op.drop_index("ix_message_citations_tenant_id", table_name="message_citations")
    op.drop_table("message_citations")
    op.drop_index("ix_messages_session_id", table_name="messages")
    op.drop_index("ix_messages_study_space_id", table_name="messages")
    op.drop_index("ix_messages_tenant_id", table_name="messages")
    op.drop_table("messages")
    op.drop_index("ix_sessions_chapter_id", table_name="sessions")
    op.drop_index("ix_sessions_study_space_id", table_name="sessions")
    op.drop_index("ix_sessions_tenant_id", table_name="sessions")
    op.drop_table("sessions")
    postgresql.ENUM(name="agent_run_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="agent_type").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="message_role").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="session_status").drop(op.get_bind(), checkfirst=True)
