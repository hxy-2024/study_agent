import uuid

import pytest

from app.db.models import Membership, Tenant, User
from scripts.seed_dev import DevIdentity, seed_dev_identity


class FakeSession:
    def __init__(self) -> None:
        self.rows = {}
        self.added = []
        self.committed = False

    async def get(self, model, row_id):
        return self.rows.get((model, row_id))

    def add(self, row):
        self.added.append(row)
        self.rows[(type(row), row.id)] = row

    async def commit(self):
        self.committed = True


@pytest.mark.anyio
async def test_seed_dev_identity_creates_missing_rows() -> None:
    session = FakeSession()
    identity = DevIdentity(
        tenant_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        user_id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
        membership_id=uuid.UUID("00000000-0000-0000-0000-000000000003"),
        tenant_name="Local Tenant",
        user_email="local@example.com",
        user_display_name="Local User",
    )

    result = await seed_dev_identity(session, identity)

    assert result == {
        "tenant": "created",
        "user": "created",
        "membership": "created",
    }
    assert [type(row) for row in session.added] == [Tenant, User, Membership]
    assert session.committed is True


@pytest.mark.anyio
async def test_seed_dev_identity_is_idempotent() -> None:
    session = FakeSession()
    identity = DevIdentity()
    session.rows[(Tenant, identity.tenant_id)] = Tenant(id=identity.tenant_id, name="Existing")
    session.rows[(User, identity.user_id)] = User(
        id=identity.user_id,
        email=identity.user_email,
        display_name=identity.user_display_name,
    )
    session.rows[(Membership, identity.membership_id)] = Membership(
        id=identity.membership_id,
        tenant_id=identity.tenant_id,
        user_id=identity.user_id,
        role="owner",
    )

    result = await seed_dev_identity(session, identity)

    assert result == {
        "tenant": "exists",
        "user": "exists",
        "membership": "exists",
    }
    assert session.added == []
    assert session.committed is True
