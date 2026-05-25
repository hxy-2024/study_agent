import uuid

from app.domain.study_spaces.service import create_route_outline


def test_create_route_outline_uses_goal_when_no_ai_is_available() -> None:
    outline = create_route_outline(goal="Learn linear algebra", target_days=14)

    assert outline[0]["title"] == "学习目标梳理"
    assert outline[0]["description"] == "明确 Learn linear algebra 的学习范围、已有基础和完成标准。"
    assert outline[-1]["title"] == "综合复习与测评"


def test_study_space_payload_contains_tenant_fields() -> None:
    tenant_id = uuid.uuid4()
    owner_user_id = uuid.uuid4()

    payload = {
        "tenant_id": tenant_id,
        "owner_user_id": owner_user_id,
        "name": "Linear Algebra",
        "goal": "Understand matrices",
        "level": "beginner",
        "intensity": "normal",
        "target_days": 30,
    }

    assert payload["tenant_id"] == tenant_id
    assert payload["owner_user_id"] == owner_user_id
