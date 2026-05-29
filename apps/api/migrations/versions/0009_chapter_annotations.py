"""chapter annotations

Revision ID: 0009_chapter_annotations
Revises: 0008_planner_actions
Create Date: 2026-05-29 15:20:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0009_chapter_annotations"
down_revision: str | None = "0008_planner_actions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    annotation_kind = postgresql.ENUM("note", "highlight", name="chapter_annotation_kind")
    annotation_kind.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "chapter_annotations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("study_space_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chapter_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_chunk_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("kind", annotation_kind, nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("quote", sa.Text(), nullable=True),
        sa.Column("anchor", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["chapter_id"], ["chapters.id"]),
        sa.ForeignKeyConstraint(["source_chunk_id"], ["source_chunks.id"]),
        sa.ForeignKeyConstraint(["study_space_id"], ["study_spaces.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_chapter_annotations_chapter_id"), "chapter_annotations", ["chapter_id"], unique=False)
    op.create_index(op.f("ix_chapter_annotations_source_chunk_id"), "chapter_annotations", ["source_chunk_id"], unique=False)
    op.create_index(op.f("ix_chapter_annotations_study_space_id"), "chapter_annotations", ["study_space_id"], unique=False)
    op.create_index(op.f("ix_chapter_annotations_tenant_id"), "chapter_annotations", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_chapter_annotations_user_id"), "chapter_annotations", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_chapter_annotations_user_id"), table_name="chapter_annotations")
    op.drop_index(op.f("ix_chapter_annotations_tenant_id"), table_name="chapter_annotations")
    op.drop_index(op.f("ix_chapter_annotations_study_space_id"), table_name="chapter_annotations")
    op.drop_index(op.f("ix_chapter_annotations_source_chunk_id"), table_name="chapter_annotations")
    op.drop_index(op.f("ix_chapter_annotations_chapter_id"), table_name="chapter_annotations")
    op.drop_table("chapter_annotations")
    postgresql.ENUM(name="chapter_annotation_kind").drop(op.get_bind(), checkfirst=True)
