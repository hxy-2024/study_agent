from app.db.models import (
    Chapter,
    MasteryLevel,
    MasteryRecord,
    Quiz,
    QuizQuestion,
    QuizStatus,
    QuizSubmission,
    StudySpace,
)
from tests.model_type_helpers import assert_json_column_compiles_for_supported_dialects


def _column_names(model: type) -> set[str]:
    return set(model.__table__.columns.keys())


def _default_value(model: type, column_name: str) -> object:
    default = model.__table__.columns[column_name].default
    assert default is not None
    if default.is_callable:
        return default.arg(None)
    return default.arg


def test_quiz_mastery_enums_have_expected_values() -> None:
    assert QuizStatus.draft.value == "draft"
    assert QuizStatus.active.value == "active"
    assert QuizStatus.submitted.value == "submitted"
    assert MasteryLevel.new.value == "new"
    assert MasteryLevel.developing.value == "developing"
    assert MasteryLevel.proficient.value == "proficient"
    assert MasteryLevel.mastered.value == "mastered"


def test_quiz_mastery_models_have_expected_tables() -> None:
    assert Quiz.__tablename__ == "quizzes"
    assert QuizQuestion.__tablename__ == "quiz_questions"
    assert QuizSubmission.__tablename__ == "quiz_submissions"
    assert MasteryRecord.__tablename__ == "mastery_records"


def test_quiz_mastery_tables_have_expected_columns() -> None:
    assert {
        "tenant_id",
        "user_id",
        "study_space_id",
        "chapter_id",
        "title",
        "status",
        "generation_strategy",
        "question_count",
        "created_at",
        "updated_at",
    } <= _column_names(Quiz)
    assert {
        "tenant_id",
        "quiz_id",
        "chapter_id",
        "order_index",
        "prompt",
        "options",
        "correct_option_index",
        "explanation",
        "evidence",
        "created_at",
    } <= _column_names(QuizQuestion)
    assert {
        "tenant_id",
        "quiz_id",
        "chapter_id",
        "user_id",
        "answers",
        "score_percent",
        "correct_count",
        "question_count",
        "results",
        "weak_points",
        "created_at",
    } <= _column_names(QuizSubmission)
    assert {
        "tenant_id",
        "user_id",
        "study_space_id",
        "chapter_id",
        "score_percent",
        "level",
        "weak_points",
        "last_quiz_submission_id",
        "updated_at",
    } <= _column_names(MasteryRecord)


def test_quiz_mastery_tables_do_not_include_superseded_columns() -> None:
    assert "answer" not in _column_names(QuizQuestion)
    assert "score" not in _column_names(QuizSubmission)
    assert "score" not in _column_names(MasteryRecord)


def test_quiz_mastery_models_have_expected_defaults() -> None:
    assert _default_value(Quiz, "status") == QuizStatus.active
    assert _default_value(Quiz, "generation_strategy") == "deterministic"
    assert _default_value(Quiz, "question_count") == 3
    assert _default_value(QuizQuestion, "options") == []
    assert _default_value(QuizQuestion, "evidence") == {}
    assert _default_value(QuizSubmission, "answers") == []
    assert _default_value(QuizSubmission, "results") == []
    assert _default_value(QuizSubmission, "weak_points") == []
    assert _default_value(MasteryRecord, "level") == MasteryLevel.new
    assert _default_value(MasteryRecord, "weak_points") == []


def test_quiz_mastery_json_columns_compile_for_supported_dialects() -> None:
    assert_json_column_compiles_for_supported_dialects(QuizQuestion.__table__.columns["options"])
    assert_json_column_compiles_for_supported_dialects(QuizQuestion.__table__.columns["evidence"])
    assert_json_column_compiles_for_supported_dialects(QuizSubmission.__table__.columns["answers"])
    assert_json_column_compiles_for_supported_dialects(QuizSubmission.__table__.columns["results"])
    assert_json_column_compiles_for_supported_dialects(QuizSubmission.__table__.columns["weak_points"])
    assert_json_column_compiles_for_supported_dialects(MasteryRecord.__table__.columns["weak_points"])


def test_quiz_mastery_tables_have_expected_unique_constraints() -> None:
    quiz_question_constraints = {
        constraint.name: {column.name for column in constraint.columns}
        for constraint in QuizQuestion.__table__.constraints
    }
    mastery_constraints = {
        constraint.name: {column.name for column in constraint.columns}
        for constraint in MasteryRecord.__table__.constraints
    }

    assert quiz_question_constraints["uq_quiz_questions_quiz_order"] == {"quiz_id", "order_index"}
    assert mastery_constraints["uq_mastery_records_tenant_chapter_user"] == {
        "tenant_id",
        "chapter_id",
        "user_id",
    }


def test_quiz_mastery_relationships_are_registered() -> None:
    assert "quizzes" in StudySpace.__mapper__.relationships
    assert "mastery_records" in StudySpace.__mapper__.relationships
    assert "quizzes" in Chapter.__mapper__.relationships
    assert "mastery_records" in Chapter.__mapper__.relationships
    assert "mastery_records" in QuizSubmission.__mapper__.relationships
