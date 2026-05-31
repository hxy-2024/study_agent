from logging.config import fileConfig

from alembic import context
from alembic.script import ScriptDirectory
from sqlalchemy import inspect
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import get_settings
from app.db import models  # noqa: F401
from app.db.base import Base

config = context.config
config.set_main_option("sqlalchemy.url", get_settings().database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def ensure_sqlite_schema(connection) -> None:
    target_metadata.create_all(connection)
    inspector = inspect(connection)
    if "source_chunks" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("source_chunks")}
        if "embedding_provider" not in columns:
            connection.exec_driver_sql(
                "ALTER TABLE source_chunks "
                "ADD COLUMN embedding_provider VARCHAR(80) NOT NULL DEFAULT 'local-deterministic'"
            )
        if "embedding_model" not in columns:
            connection.exec_driver_sql(
                "ALTER TABLE source_chunks "
                "ADD COLUMN embedding_model VARCHAR(200) NOT NULL DEFAULT 'local-deterministic'"
            )
        if "embedding_dimension" not in columns:
            connection.exec_driver_sql(
                "ALTER TABLE source_chunks "
                "ADD COLUMN embedding_dimension INTEGER NOT NULL DEFAULT 16"
            )


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    if connection.dialect.name == "sqlite":
        ensure_sqlite_schema(connection)
        context.configure(connection=connection, target_metadata=target_metadata)
        script = ScriptDirectory.from_config(config)
        with context.begin_transaction():
            context.get_context()._ensure_version_table()
            context.get_context().stamp(script, "head")
        return
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    import asyncio

    asyncio.run(run_migrations_online())
