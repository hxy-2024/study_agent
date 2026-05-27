"""foundation tables

Revision ID: 0001_foundation
Revises:
Create Date: 2026-05-25
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001_foundation"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

study_space_status = postgresql.ENUM(
    "draft",
    "active",
    "archived",
    name="study_space_status",
    create_type=False,
)
source_status = postgresql.ENUM(
    "pending_upload",
    "uploaded",
    "processing",
    "ready",
    "failed",
    name="source_status",
    create_type=False,
)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    bind = op.get_bind()
    study_space_status.create(bind, checkfirst=True)
    source_status.create(bind, checkfirst=True)

    op.create_table(
        "tenants",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_table(
        "memberships",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(length=40), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_memberships_tenant_id", "memberships", ["tenant_id"])
    op.create_index("ix_memberships_user_id", "memberships", ["user_id"])
    op.create_table(
        "study_spaces",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("owner_user_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("level", sa.String(length=60), nullable=False),
        sa.Column("intensity", sa.String(length=60), nullable=False),
        sa.Column("target_days", sa.Integer(), nullable=False),
        sa.Column("status", study_space_status, nullable=False),
        sa.Column("route_outline", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_study_spaces_owner_user_id", "study_spaces", ["owner_user_id"])
    op.create_index("ix_study_spaces_tenant_id", "study_spaces", ["tenant_id"])
    op.create_table(
        "sources",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("study_space_id", sa.UUID(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("object_key", sa.String(length=500), nullable=False),
        sa.Column("status", source_status, nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["study_space_id"], ["study_spaces.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sources_study_space_id", "sources", ["study_space_id"])
    op.create_index("ix_sources_tenant_id", "sources", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_sources_tenant_id", table_name="sources")
    op.drop_index("ix_sources_study_space_id", table_name="sources")
    op.drop_table("sources")
    op.drop_index("ix_study_spaces_tenant_id", table_name="study_spaces")
    op.drop_index("ix_study_spaces_owner_user_id", table_name="study_spaces")
    op.drop_table("study_spaces")
    op.drop_index("ix_memberships_user_id", table_name="memberships")
    op.drop_index("ix_memberships_tenant_id", table_name="memberships")
    op.drop_table("memberships")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
    op.drop_table("tenants")
    bind = op.get_bind()
    source_status.drop(bind, checkfirst=True)
    study_space_status.drop(bind, checkfirst=True)
