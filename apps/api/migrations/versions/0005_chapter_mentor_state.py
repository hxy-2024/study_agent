"""chapter mentor state

Revision ID: 0005_chapter_mentor_state
Revises: 0004_sessions_messages
Create Date: 2026-05-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_chapter_mentor_state"
down_revision: str | None = "0004_sessions_messages"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "chapter_mentor_states",
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
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column(
            "weak_points",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "next_actions",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "evidence",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "source_session_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "source_message_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
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
        sa.UniqueConstraint("chapter_id", name="uq_chapter_mentor_states_chapter"),
    )
    op.create_index("ix_chapter_mentor_states_tenant_id", "chapter_mentor_states", ["tenant_id"])
    op.create_index("ix_chapter_mentor_states_study_space_id", "chapter_mentor_states", ["study_space_id"])
    op.create_index("ix_chapter_mentor_states_chapter_id", "chapter_mentor_states", ["chapter_id"])


def downgrade() -> None:
    op.drop_index("ix_chapter_mentor_states_chapter_id", table_name="chapter_mentor_states")
    op.drop_index("ix_chapter_mentor_states_study_space_id", table_name="chapter_mentor_states")
    op.drop_index("ix_chapter_mentor_states_tenant_id", table_name="chapter_mentor_states")
    op.drop_table("chapter_mentor_states")
