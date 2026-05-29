from functools import lru_cache

from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "study-agent-api"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "postgresql+asyncpg://study_agent:study_agent@localhost:15432/study_agent"
    redis_url: str = "redis://localhost:6379/0"
    api_cors_origins: list[AnyHttpUrl] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    s3_endpoint_url: str = "http://localhost:9000"
    s3_public_endpoint_url: str = "http://localhost:9000"
    s3_access_key_id: str = "minioadmin"
    s3_secret_access_key: str = "minioadmin"
    s3_bucket: str = "study-agent-local"
    storage_text_max_bytes: int = 2_000_000
    rag_embedding_dimension: int = 16
    rag_chunk_max_chars: int = 1200
    rag_chunk_overlap_chars: int = 180
    dev_auth_enabled: bool = True
    auth_user_header: str = "X-User-Id"
    auth_tenant_header: str = "X-Tenant-Id"
    llm_provider: str = "deterministic"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4.1-mini"
    llm_timeout_seconds: int = 30
    session_tutor_graph_enabled: bool = True
    session_tutor_graph_checkpoint_backend: str = "memory"
    session_tutor_web_search_enabled: bool = False
    session_tutor_web_search_timeout_seconds: int = 5
    session_tutor_web_search_max_results: int = 3

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
