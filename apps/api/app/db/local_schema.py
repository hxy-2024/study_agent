from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.db.base import Base
from scripts.seed_dev import DevIdentity, seed_dev_identity


async def create_local_schema(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def prepare_local_database(engine: AsyncEngine) -> dict[str, str]:
    await create_local_schema(engine)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        return await seed_dev_identity(session=session, identity=DevIdentity())
