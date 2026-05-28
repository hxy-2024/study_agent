from app.core.config import Settings
from app.domain.agent_runtime.config import graph_runtime_config_from_settings


def test_graph_runtime_config_defaults_to_enabled_memory_backend() -> None:
    settings = Settings()

    config = graph_runtime_config_from_settings(settings)

    assert config.session_tutor_graph_enabled is True
    assert config.checkpoint_backend == "memory"


def test_graph_runtime_config_accepts_none_checkpoint_backend() -> None:
    settings = Settings(session_tutor_graph_checkpoint_backend="none")

    config = graph_runtime_config_from_settings(settings)

    assert config.checkpoint_backend == "none"
