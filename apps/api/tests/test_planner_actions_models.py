from app.db.models import PlannerAction, PlannerActionStatus, PlannerActionType, StudySpace
from tests.model_type_helpers import assert_json_column_compiles_for_supported_dialects


def test_planner_action_model_shape() -> None:
    columns = PlannerAction.__table__.columns

    assert "tenant_id" in columns
    assert "user_id" in columns
    assert "study_space_id" in columns
    assert "chapter_id" in columns
    assert "action_type" in columns
    assert "status" in columns
    assert "title" in columns
    assert "rationale" in columns
    assert "payload" in columns
    assert "source_planner_state_id" in columns
    assert "created_at" in columns
    assert "updated_at" in columns


def test_planner_action_enums_and_json_column_type() -> None:
    assert PlannerActionType.review_chapter.value == "review_chapter"
    assert PlannerActionType.route_adjustment.value == "route_adjustment"
    assert PlannerActionStatus.proposed.value == "proposed"
    assert PlannerActionStatus.accepted.value == "accepted"
    assert PlannerActionStatus.completed.value == "completed"
    assert PlannerActionStatus.dismissed.value == "dismissed"
    assert_json_column_compiles_for_supported_dialects(PlannerAction.__table__.columns["payload"])


def test_planner_action_relationship() -> None:
    assert "planner_actions" in StudySpace.__mapper__.relationships
