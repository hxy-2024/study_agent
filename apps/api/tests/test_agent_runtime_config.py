import pytest

from app.core.config import Settings
from app.domain.agent_runtime.checkpoints import create_checkpointer
from app.domain.agent_runtime.config import GraphRuntimeConfig, graph_runtime_config_from_settings


def test_graph_runtime_config_defaults_to_enabled_memory_backend() -> None:
    settings = Settings()

    config = graph_runtime_config_from_settings(settings)

    assert config.session_tutor_graph_enabled is True
    assert config.checkpoint_backend == "memory"


def test_graph_runtime_config_accepts_none_checkpoint_backend() -> None:
    settings = Settings(session_tutor_graph_checkpoint_backend="none")

    config = graph_runtime_config_from_settings(settings)

    assert config.checkpoint_backend == "none"


def test_graph_runtime_config_rejects_unknown_checkpoint_backend() -> None:
    settings = Settings(session_tutor_graph_checkpoint_backend="bad")

    with pytest.raises(ValueError):
        graph_runtime_config_from_settings(settings)


def test_create_checkpointer_returns_none_for_none_backend() -> None:
    config = GraphRuntimeConfig(session_tutor_graph_enabled=True, checkpoint_backend="none")

    assert create_checkpointer(config) is None


def test_create_checkpointer_accepts_memory_backend() -> None:
    config = GraphRuntimeConfig(session_tutor_graph_enabled=True, checkpoint_backend="memory")

    assert create_checkpointer(config) is not None


def test_create_checkpointer_fails_closed_for_postgres_backend() -> None:
    config = GraphRuntimeConfig(session_tutor_graph_enabled=True, checkpoint_backend="postgres")

    with pytest.raises(ValueError, match="Postgres graph checkpointing is not configured"):
        create_checkpointer(config)
