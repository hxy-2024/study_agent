from app.db.models import AgentType, SpacePlannerState, StudySpace
from tests.model_type_helpers import assert_json_column_compiles_for_supported_dialects


def test_space_planner_state_model_has_expected_columns() -> None:
    columns = SpacePlannerState.__table__.columns

    assert "tenant_id" in columns
    assert "user_id" in columns
    assert "study_space_id" in columns
    assert "summary" in columns
    assert "next_chapter_id" in columns
    assert "risk_chapters" in columns
    assert "review_recommendations" in columns
    assert "route_adjustments" in columns
    assert "evidence" in columns
    assert "created_at" in columns
    assert "updated_at" in columns


def test_space_planner_state_json_columns_compile_for_supported_dialects() -> None:
    assert_json_column_compiles_for_supported_dialects(
        SpacePlannerState.__table__.columns["risk_chapters"]
    )
    assert_json_column_compiles_for_supported_dialects(
        SpacePlannerState.__table__.columns["review_recommendations"]
    )
    assert_json_column_compiles_for_supported_dialects(
        SpacePlannerState.__table__.columns["route_adjustments"]
    )
    assert_json_column_compiles_for_supported_dialects(SpacePlannerState.__table__.columns["evidence"])


def test_space_planner_state_unique_and_relationships() -> None:
    constraints = {
        constraint.name: {column.name for column in constraint.columns}
        for constraint in SpacePlannerState.__table__.constraints
    }

    assert constraints["uq_space_planner_states_tenant_space_user"] == {
        "tenant_id",
        "study_space_id",
        "user_id",
    }
    assert "space_planner_states" in StudySpace.__mapper__.relationships
    assert AgentType.space_planner.value == "space_planner"
