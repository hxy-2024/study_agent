"""planner actions

Revision ID: 0008_planner_actions
Revises: 0007_space_planner_state
Create Date: 2026-05-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_planner_actions"
down_revision: str | None = "0007_space_planner_state"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

planner_action_type = postgresql.ENUM(
    "review_chapter",
    "route_adjustment",
    name="planner_action_type",
    create_type=False,
)
planner_action_status = postgresql.ENUM(
    "proposed",
    "accepted",
    "completed",
    "dismissed",
    name="planner_action_status",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    planner_action_type.create(bind, checkfirst=True)
    planner_action_status.create(bind, checkfirst=True)

    op.create_table(
        "planner_actions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("study_space_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("study_spaces.id"), nullable=False),
        sa.Column("chapter_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("chapters.id"), nullable=True),
        sa.Column(
            "source_planner_state_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("space_planner_states.id"),
            nullable=True,
        ),
        sa.Column("action_type", planner_action_type, nullable=False),
        sa.Column("status", planner_action_status, nullable=False, server_default=sa.text("'proposed'")),
        sa.Column("title", sa.String(length=220), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_planner_actions_tenant_id", "planner_actions", ["tenant_id"])
    op.create_index("ix_planner_actions_user_id", "planner_actions", ["user_id"])
    op.create_index("ix_planner_actions_study_space_id", "planner_actions", ["study_space_id"])
    op.create_index("ix_planner_actions_chapter_id", "planner_actions", ["chapter_id"])
    op.create_index("ix_planner_actions_source_planner_state_id", "planner_actions", ["source_planner_state_id"])


def downgrade() -> None:
    op.drop_index("ix_planner_actions_source_planner_state_id", table_name="planner_actions")
    op.drop_index("ix_planner_actions_chapter_id", table_name="planner_actions")
    op.drop_index("ix_planner_actions_study_space_id", table_name="planner_actions")
    op.drop_index("ix_planner_actions_user_id", table_name="planner_actions")
    op.drop_index("ix_planner_actions_tenant_id", table_name="planner_actions")
    op.drop_table("planner_actions")
    planner_action_status.drop(op.get_bind(), checkfirst=True)
    planner_action_type.drop(op.get_bind(), checkfirst=True)
