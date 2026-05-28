"""space planner state

Revision ID: 0007_space_planner_state
Revises: 0006_quiz_mastery
Create Date: 2026-05-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_space_planner_state"
down_revision: str | None = "0006_quiz_mastery"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "space_planner_states",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("study_space_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("study_spaces.id"), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("next_chapter_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("chapters.id"), nullable=True),
        sa.Column("risk_chapters", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("review_recommendations", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("route_adjustments", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("evidence", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tenant_id", "study_space_id", "user_id", name="uq_space_planner_states_tenant_space_user"),
    )
    op.create_index("ix_space_planner_states_tenant_id", "space_planner_states", ["tenant_id"])
    op.create_index("ix_space_planner_states_user_id", "space_planner_states", ["user_id"])
    op.create_index("ix_space_planner_states_study_space_id", "space_planner_states", ["study_space_id"])
    op.create_index("ix_space_planner_states_next_chapter_id", "space_planner_states", ["next_chapter_id"])


def downgrade() -> None:
    op.drop_index("ix_space_planner_states_next_chapter_id", table_name="space_planner_states")
    op.drop_index("ix_space_planner_states_study_space_id", table_name="space_planner_states")
    op.drop_index("ix_space_planner_states_user_id", table_name="space_planner_states")
    op.drop_index("ix_space_planner_states_tenant_id", table_name="space_planner_states")
    op.drop_table("space_planner_states")
