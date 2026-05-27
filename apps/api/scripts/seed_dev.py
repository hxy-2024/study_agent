import asyncio
import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Membership, Tenant, User
from app.db.session import AsyncSessionLocal


@dataclass(frozen=True)
class DevIdentity:
    tenant_id: uuid.UUID = uuid.UUID("00000000-0000-0000-0000-000000000001")
    user_id: uuid.UUID = uuid.UUID("00000000-0000-0000-0000-000000000002")
    membership_id: uuid.UUID = uuid.UUID("00000000-0000-0000-0000-000000000003")
    tenant_name: str = "Local Tenant"
    user_email: str = "local@example.com"
    user_display_name: str = "Local User"
    role: str = "owner"


async def seed_dev_identity(session: AsyncSession, identity: DevIdentity) -> dict[str, str]:
    result: dict[str, str] = {}

    tenant = await session.get(Tenant, identity.tenant_id)
    if tenant is None:
        session.add(Tenant(id=identity.tenant_id, name=identity.tenant_name))
        result["tenant"] = "created"
    else:
        result["tenant"] = "exists"

    user = await session.get(User, identity.user_id)
    if user is None:
        session.add(
            User(
                id=identity.user_id,
                email=identity.user_email,
                display_name=identity.user_display_name,
            )
        )
        result["user"] = "created"
    else:
        result["user"] = "exists"

    membership = await session.get(Membership, identity.membership_id)
    if membership is None:
        session.add(
            Membership(
                id=identity.membership_id,
                tenant_id=identity.tenant_id,
                user_id=identity.user_id,
                role=identity.role,
            )
        )
        result["membership"] = "created"
    else:
        result["membership"] = "exists"

    await session.commit()
    return result


async def main() -> None:
    identity = DevIdentity()
    async with AsyncSessionLocal() as session:
        result = await seed_dev_identity(session, identity)

    print("Development identity ready:")
    print(f"  tenant_id={identity.tenant_id} ({result['tenant']})")
    print(f"  user_id={identity.user_id} ({result['user']})")
    print(f"  membership_id={identity.membership_id} ({result['membership']})")
    print("Use headers:")
    print(f"  X-User-Id: {identity.user_id}")
    print(f"  X-Tenant-Id: {identity.tenant_id}")


if __name__ == "__main__":
    asyncio.run(main())

