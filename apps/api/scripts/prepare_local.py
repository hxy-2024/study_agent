import asyncio
from pathlib import Path

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings
from app.db.local_schema import prepare_local_database


async def main() -> None:
    settings = get_settings()
    if settings.database_url.startswith("sqlite+aiosqlite:///"):
        database_path = make_url(settings.database_url).database
        if database_path and database_path != ":memory:":
            Path(database_path).parent.mkdir(parents=True, exist_ok=True)
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    result = await prepare_local_database(engine)
    await engine.dispose()
    print("Local SQLite database ready:")
    print(f"  database_url={settings.database_url}")
    print(f"  tenant={result['tenant']}")
    print(f"  user={result['user']}")
    print(f"  membership={result['membership']}")


if __name__ == "__main__":
    asyncio.run(main())
