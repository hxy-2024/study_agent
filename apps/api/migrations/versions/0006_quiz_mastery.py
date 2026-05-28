"""quiz mastery persistence

Revision ID: 0006_quiz_mastery
Revises: 0005_chapter_mentor_state
Create Date: 2026-05-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_quiz_mastery"
down_revision: str | None = "0005_chapter_mentor_state"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

quiz_status = postgresql.ENUM("draft", "active", "submitted", name="quiz_status", create_type=False)
mastery_level = postgresql.ENUM(
    "new",
    "developing",
    "proficient",
    "mastered",
    name="mastery_level",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    quiz_status.create(bind, checkfirst=True)
    mastery_level.create(bind, checkfirst=True)

    op.create_table(
        "quizzes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
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
        sa.Column("status", quiz_status, nullable=False, server_default=sa.text("'active'")),
        sa.Column(
            "generation_strategy",
            sa.String(length=80),
            nullable=False,
            server_default=sa.text("'deterministic'"),
        ),
        sa.Column("question_count", sa.Integer(), nullable=False, server_default=sa.text("3")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_quizzes_tenant_id", "quizzes", ["tenant_id"])
    op.create_index("ix_quizzes_user_id", "quizzes", ["user_id"])
    op.create_index("ix_quizzes_study_space_id", "quizzes", ["study_space_id"])
    op.create_index("ix_quizzes_chapter_id", "quizzes", ["chapter_id"])

    op.create_table(
        "quiz_questions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            nullable=False,
        ),
        sa.Column(
            "quiz_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("quizzes.id"),
            nullable=False,
        ),
        sa.Column(
            "chapter_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chapters.id"),
            nullable=False,
        ),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("options", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("correct_option_index", sa.Integer(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("evidence", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("quiz_id", "order_index", name="uq_quiz_questions_quiz_order"),
    )
    op.create_index("ix_quiz_questions_tenant_id", "quiz_questions", ["tenant_id"])
    op.create_index("ix_quiz_questions_quiz_id", "quiz_questions", ["quiz_id"])
    op.create_index("ix_quiz_questions_chapter_id", "quiz_questions", ["chapter_id"])

    op.create_table(
        "quiz_submissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            nullable=False,
        ),
        sa.Column(
            "quiz_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("quizzes.id"),
            nullable=False,
        ),
        sa.Column(
            "chapter_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chapters.id"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("answers", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("score_percent", sa.Integer(), nullable=False),
        sa.Column("correct_count", sa.Integer(), nullable=False),
        sa.Column("question_count", sa.Integer(), nullable=False),
        sa.Column("results", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("weak_points", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_quiz_submissions_tenant_id", "quiz_submissions", ["tenant_id"])
    op.create_index("ix_quiz_submissions_quiz_id", "quiz_submissions", ["quiz_id"])
    op.create_index("ix_quiz_submissions_chapter_id", "quiz_submissions", ["chapter_id"])
    op.create_index("ix_quiz_submissions_user_id", "quiz_submissions", ["user_id"])

    op.create_table(
        "mastery_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
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
        sa.Column("score_percent", sa.Integer(), nullable=False),
        sa.Column("level", mastery_level, nullable=False, server_default=sa.text("'new'")),
        sa.Column("weak_points", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column(
            "last_quiz_submission_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("quiz_submissions.id"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tenant_id", "chapter_id", "user_id", name="uq_mastery_records_tenant_chapter_user"),
    )
    op.create_index("ix_mastery_records_tenant_id", "mastery_records", ["tenant_id"])
    op.create_index("ix_mastery_records_user_id", "mastery_records", ["user_id"])
    op.create_index("ix_mastery_records_study_space_id", "mastery_records", ["study_space_id"])
    op.create_index("ix_mastery_records_chapter_id", "mastery_records", ["chapter_id"])
    op.create_index("ix_mastery_records_last_quiz_submission_id", "mastery_records", ["last_quiz_submission_id"])


def downgrade() -> None:
    op.drop_index("ix_mastery_records_last_quiz_submission_id", table_name="mastery_records")
    op.drop_index("ix_mastery_records_chapter_id", table_name="mastery_records")
    op.drop_index("ix_mastery_records_study_space_id", table_name="mastery_records")
    op.drop_index("ix_mastery_records_user_id", table_name="mastery_records")
    op.drop_index("ix_mastery_records_tenant_id", table_name="mastery_records")
    op.drop_table("mastery_records")

    op.drop_index("ix_quiz_submissions_user_id", table_name="quiz_submissions")
    op.drop_index("ix_quiz_submissions_chapter_id", table_name="quiz_submissions")
    op.drop_index("ix_quiz_submissions_quiz_id", table_name="quiz_submissions")
    op.drop_index("ix_quiz_submissions_tenant_id", table_name="quiz_submissions")
    op.drop_table("quiz_submissions")

    op.drop_index("ix_quiz_questions_chapter_id", table_name="quiz_questions")
    op.drop_index("ix_quiz_questions_quiz_id", table_name="quiz_questions")
    op.drop_index("ix_quiz_questions_tenant_id", table_name="quiz_questions")
    op.drop_table("quiz_questions")

    op.drop_index("ix_quizzes_chapter_id", table_name="quizzes")
    op.drop_index("ix_quizzes_study_space_id", table_name="quizzes")
    op.drop_index("ix_quizzes_user_id", table_name="quizzes")
    op.drop_index("ix_quizzes_tenant_id", table_name="quizzes")
    op.drop_table("quizzes")

    bind = op.get_bind()
    mastery_level.drop(bind, checkfirst=True)
    quiz_status.drop(bind, checkfirst=True)
