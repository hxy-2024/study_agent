"""variable embedding vectors

Revision ID: 0012_variable_embeddings
Revises: 0011_learning_signals
Create Date: 2026-05-31 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
from pgvector.sqlalchemy import Vector
import sqlalchemy as sa


revision: str = "0012_variable_embeddings"
down_revision: str | None = "0011_learning_signals"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.drop_index("ix_source_chunks_embedding_hnsw", table_name="source_chunks")
        op.alter_column(
            "source_chunks",
            "embedding",
            existing_type=Vector(16),
            type_=Vector(),
            postgresql_using="embedding::vector",
        )
    op.add_column(
        "source_chunks",
        sa.Column(
            "embedding_provider",
            sa.String(length=80),
            server_default="local-deterministic",
            nullable=False,
        ),
    )
    op.add_column(
        "source_chunks",
        sa.Column(
            "embedding_model",
            sa.String(length=200),
            server_default="local-deterministic",
            nullable=False,
        ),
    )
    op.add_column(
        "source_chunks",
        sa.Column("embedding_dimension", sa.Integer(), server_default="16", nullable=False),
    )
    op.create_index(
        "ix_source_chunks_embedding_family",
        "source_chunks",
        [
            "tenant_id",
            "study_space_id",
            "is_active",
            "embedding_provider",
            "embedding_model",
            "embedding_dimension",
        ],
        unique=False,
    )


def downgrade() -> None:
    bind = op.get_bind()
    op.drop_index("ix_source_chunks_embedding_family", table_name="source_chunks")
    op.drop_column("source_chunks", "embedding_dimension")
    op.drop_column("source_chunks", "embedding_model")
    op.drop_column("source_chunks", "embedding_provider")
    if bind.dialect.name != "postgresql":
        return
    op.alter_column(
        "source_chunks",
        "embedding",
        existing_type=Vector(),
        type_=Vector(16),
        postgresql_using="embedding::vector(16)",
    )
    op.create_index(
        "ix_source_chunks_embedding_hnsw",
        "source_chunks",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
