"""learning signals review schedule

Revision ID: 0011_learning_signals_review_schedule
Revises: 0010_main_agent_types
Create Date: 2026-05-30 18:10:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0011_learning_signals_review_schedule"
down_revision: str | None = "0010_main_agent_types"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    signal_status = postgresql.ENUM("active", "completed", "dismissed", "snoozed", name="learning_signal_status")
    signal_status.create(op.get_bind(), checkfirst=True)
    signal_status_column = postgresql.ENUM(
        "active",
        "completed",
        "dismissed",
        "snoozed",
        name="learning_signal_status",
        create_type=False,
    )

    op.create_table(
        "learning_signals",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("study_space_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chapter_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("quiz_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("agent_type", postgresql.ENUM(name="agent_type", create_type=False), nullable=False),
        sa.Column("signal_type", sa.String(length=80), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("status", signal_status_column, nullable=False),
        sa.Column("dedupe_key", sa.String(length=240), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["chapter_id"], ["chapters.id"]),
        sa.ForeignKeyConstraint(["quiz_id"], ["quizzes.id"]),
        sa.ForeignKeyConstraint(["study_space_id"], ["study_spaces.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "user_id", "dedupe_key", name="uq_learning_signals_tenant_user_dedupe"),
    )
    op.create_index(op.f("ix_learning_signals_chapter_id"), "learning_signals", ["chapter_id"], unique=False)
    op.create_index(op.f("ix_learning_signals_quiz_id"), "learning_signals", ["quiz_id"], unique=False)
    op.create_index(op.f("ix_learning_signals_study_space_id"), "learning_signals", ["study_space_id"], unique=False)
    op.create_index(op.f("ix_learning_signals_tenant_id"), "learning_signals", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_learning_signals_user_id"), "learning_signals", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_learning_signals_user_id"), table_name="learning_signals")
    op.drop_index(op.f("ix_learning_signals_tenant_id"), table_name="learning_signals")
    op.drop_index(op.f("ix_learning_signals_study_space_id"), table_name="learning_signals")
    op.drop_index(op.f("ix_learning_signals_quiz_id"), table_name="learning_signals")
    op.drop_index(op.f("ix_learning_signals_chapter_id"), table_name="learning_signals")
    op.drop_table("learning_signals")
    postgresql.ENUM(name="learning_signal_status").drop(op.get_bind(), checkfirst=True)
