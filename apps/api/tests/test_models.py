from app.db.models import Source, StudySpace, Tenant, User


def test_core_tables_are_tenant_aware() -> None:
    assert Tenant.__tablename__ == "tenants"
    assert User.__tablename__ == "users"
    assert StudySpace.__tablename__ == "study_spaces"
    assert Source.__tablename__ == "sources"
    assert "tenant_id" in StudySpace.__table__.columns
    assert "tenant_id" in Source.__table__.columns
