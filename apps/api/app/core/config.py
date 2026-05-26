from functools import lru_cache

from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "study-agent-api"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "postgresql+asyncpg://study_agent:study_agent@localhost:5432/study_agent"
    redis_url: str = "redis://localhost:6379/0"
    api_cors_origins: list[AnyHttpUrl] = []
    s3_endpoint_url: str = "http://localhost:9000"
    s3_public_endpoint_url: str = "http://localhost:9000"
    s3_access_key_id: str = "minioadmin"
    s3_secret_access_key: str = "minioadmin"
    s3_bucket: str = "study-agent-local"
    rag_embedding_dimension: int = 16
    rag_chunk_max_chars: int = 1200
    rag_chunk_overlap_chars: int = 180
    dev_auth_enabled: bool = True
    auth_user_header: str = "X-User-Id"
    auth_tenant_header: str = "X-Tenant-Id"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
