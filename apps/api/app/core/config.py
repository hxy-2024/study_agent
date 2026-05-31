from functools import lru_cache

from pydantic import AnyHttpUrl
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_POSTGRES_DATABASE_URL = "postgresql+asyncpg://study_agent:study_agent@localhost:15432/study_agent"
DEFAULT_SQLITE_DATABASE_URL = "sqlite+aiosqlite:///.local/study_agent.db"


class Settings(BaseSettings):
    app_name: str = "study-agent-api"
    api_v1_prefix: str = "/api/v1"
    runtime_profile: str = "docker"
    api_public_url: str = "http://127.0.0.1:8000"
    database_url: str = DEFAULT_POSTGRES_DATABASE_URL
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
    storage_backend: str = "s3"
    local_database_path: str = ".local/study_agent.db"
    local_storage_root: str = ".local/storage"
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
    embedding_base_url: str = ""
    embedding_api_key: str = ""
    embedding_model: str = ""
    embedding_dimensions: int | None = None
    session_tutor_graph_enabled: bool = True
    session_tutor_graph_checkpoint_backend: str = "memory"
    session_tutor_web_search_enabled: bool = False
    session_tutor_web_search_provider: str = "duckduckgo"
    tavily_api_key: str = ""
    session_tutor_web_search_timeout_seconds: int = 5
    session_tutor_web_search_max_results: int = 3
    local_settings_path: str = ".local/settings.json"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @model_validator(mode="after")
    def apply_runtime_profile_defaults(self) -> "Settings":
        profile = self.runtime_profile.strip().lower()
        self.runtime_profile = profile
        if profile in {"local", "dev", "local-lite"}:
            if self.database_url == DEFAULT_POSTGRES_DATABASE_URL:
                self.database_url = DEFAULT_SQLITE_DATABASE_URL
            if self.storage_backend == "s3":
                self.storage_backend = "filesystem"
        elif profile in {"docker", "docker-dev"}:
            if self.database_url == DEFAULT_SQLITE_DATABASE_URL:
                self.database_url = DEFAULT_POSTGRES_DATABASE_URL
            if self.storage_backend == "filesystem":
                self.storage_backend = "s3"
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
