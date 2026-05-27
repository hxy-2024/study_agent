"""learning routes

Revision ID: 0003_learning_routes
Revises: 0002_rag_foundation
Create Date: 2026-05-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_learning_routes"
down_revision: str | None = "0002_rag_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    route_status = postgresql.ENUM("draft", "active", "archived", name="learning_route_status")
    chapter_status = postgresql.ENUM("not_started", "active", "completed", name="chapter_status")
    route_status.create(op.get_bind(), checkfirst=True)
    chapter_status.create(op.get_bind(), checkfirst=True)

    route_status_column = postgresql.ENUM(
        "draft",
        "active",
        "archived",
        name="learning_route_status",
        create_type=False,
    )
    chapter_status_column = postgresql.ENUM(
        "not_started",
        "active",
        "completed",
        name="chapter_status",
        create_type=False,
    )

    op.create_table(
        "learning_routes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("study_space_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("study_spaces.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", route_status_column, nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("generation_strategy", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("study_space_id", "version", name="uq_learning_routes_space_version"),
    )
    op.create_index("ix_learning_routes_tenant_id", "learning_routes", ["tenant_id"])
    op.create_index("ix_learning_routes_study_space_id", "learning_routes", ["study_space_id"])
    op.create_index(
        "uq_learning_routes_one_active_per_space",
        "learning_routes",
        ["tenant_id", "study_space_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "chapters",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("study_space_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("study_spaces.id"), nullable=False),
        sa.Column("learning_route_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("learning_routes.id"), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("estimated_days", sa.Integer(), nullable=False),
        sa.Column("status", chapter_status_column, nullable=False),
        sa.Column("source_chunk_refs", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("learning_route_id", "order_index", name="uq_chapters_route_order"),
    )
    op.create_index("ix_chapters_tenant_id", "chapters", ["tenant_id"])
    op.create_index("ix_chapters_study_space_id", "chapters", ["study_space_id"])
    op.create_index("ix_chapters_learning_route_id", "chapters", ["learning_route_id"])


def downgrade() -> None:
    op.drop_index("ix_chapters_learning_route_id", table_name="chapters")
    op.drop_index("ix_chapters_study_space_id", table_name="chapters")
    op.drop_index("ix_chapters_tenant_id", table_name="chapters")
    op.drop_table("chapters")
    op.drop_index("uq_learning_routes_one_active_per_space", table_name="learning_routes")
    op.drop_index("ix_learning_routes_study_space_id", table_name="learning_routes")
    op.drop_index("ix_learning_routes_tenant_id", table_name="learning_routes")
    op.drop_table("learning_routes")
    postgresql.ENUM(name="chapter_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="learning_route_status").drop(op.get_bind(), checkfirst=True)
