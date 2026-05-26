import uuid
from dataclasses import dataclass
from typing import Protocol

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Membership
from app.db.session import get_db_session


@dataclass(frozen=True)
class CurrentUserContext:
    user_id: uuid.UUID
    tenant_id: uuid.UUID


def parse_dev_auth_headers(
    user_id_header: str | None,
    tenant_id_header: str | None,
) -> CurrentUserContext:
    if not user_id_header or not tenant_id_header:
        raise HTTPException(status_code=401, detail="Missing development auth headers")
    try:
        user_id = uuid.UUID(user_id_header)
        tenant_id = uuid.UUID(tenant_id_header)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid development auth header UUID") from exc
    return CurrentUserContext(user_id=user_id, tenant_id=tenant_id)


async def get_current_user_context(
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> CurrentUserContext:
    return parse_dev_auth_headers(user_id_header=x_user_id, tenant_id_header=x_tenant_id)


class ScalarSession(Protocol):
    async def scalar(self, statement):
        ...


async def ensure_tenant_membership(
    context: CurrentUserContext,
    session: ScalarSession,
) -> CurrentUserContext:
    membership = await session.scalar(
        select(Membership).where(
            Membership.tenant_id == context.tenant_id,
            Membership.user_id == context.user_id,
        )
    )
    if membership is None:
        raise HTTPException(status_code=403, detail="User is not a member of this tenant")
    return context


async def get_authorized_user_context(
    context: CurrentUserContext = Depends(get_current_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> CurrentUserContext:
    return await ensure_tenant_membership(context=context, session=session)
