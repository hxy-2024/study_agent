from sqlalchemy.dialects.postgresql import JSONB

from app.db.models import AgentType, SpacePlannerState, StudySpace


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


def test_space_planner_state_json_columns_use_jsonb() -> None:
    assert isinstance(SpacePlannerState.__table__.columns["risk_chapters"].type, JSONB)
    assert isinstance(SpacePlannerState.__table__.columns["review_recommendations"].type, JSONB)
    assert isinstance(SpacePlannerState.__table__.columns["route_adjustments"].type, JSONB)
    assert isinstance(SpacePlannerState.__table__.columns["evidence"].type, JSONB)


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
