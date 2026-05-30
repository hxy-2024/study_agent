from app.core.config import Settings


def test_local_profile_defaults_to_sqlite_and_filesystem() -> None:
    settings = Settings(_env_file=None, runtime_profile="local")

    assert settings.runtime_profile == "local"
    assert settings.storage_backend == "filesystem"
    assert settings.database_url.startswith("sqlite+aiosqlite:///")


def test_docker_profile_keeps_postgres_and_s3() -> None:
    settings = Settings(_env_file=None, runtime_profile="docker")

    assert settings.runtime_profile == "docker"
    assert settings.storage_backend == "s3"
    assert settings.database_url.startswith("postgresql+asyncpg://")
