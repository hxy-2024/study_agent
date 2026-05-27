from app.db.models import (
    Chapter,
    ChapterStatus,
    LearningRoute,
    LearningRouteStatus,
    Source,
    StudySpace,
    Tenant,
    User,
)


def test_core_tables_are_tenant_aware() -> None:
    assert Tenant.__tablename__ == "tenants"
    assert User.__tablename__ == "users"
    assert StudySpace.__tablename__ == "study_spaces"
    assert Source.__tablename__ == "sources"
    assert "tenant_id" in StudySpace.__table__.columns
    assert "tenant_id" in Source.__table__.columns


def test_learning_route_models_have_expected_tables() -> None:
    assert LearningRoute.__tablename__ == "learning_routes"
    assert Chapter.__tablename__ == "chapters"
    assert LearningRouteStatus.draft.value == "draft"
    assert LearningRouteStatus.active.value == "active"
    assert LearningRouteStatus.archived.value == "archived"
    assert ChapterStatus.not_started.value == "not_started"
