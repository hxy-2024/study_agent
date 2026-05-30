"""main agent types

Revision ID: 0010_main_agent_types
Revises: 0009_chapter_annotations
Create Date: 2026-05-30 15:00:00.000000
"""

from collections.abc import Sequence

from alembic import op


revision: str = "0010_main_agent_types"
down_revision: str | None = "0009_chapter_annotations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE agent_type ADD VALUE IF NOT EXISTS 'main_agent'")
    op.execute("ALTER TYPE agent_type ADD VALUE IF NOT EXISTS 'review_planner'")
    op.execute("ALTER TYPE agent_type ADD VALUE IF NOT EXISTS 'quiz_mastery'")


def downgrade() -> None:
    # PostgreSQL enum values cannot be removed safely without recreating the type.
    pass
