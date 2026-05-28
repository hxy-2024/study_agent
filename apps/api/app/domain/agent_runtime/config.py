from dataclasses import dataclass

from app.core.config import Settings


SUPPORTED_CHECKPOINT_BACKENDS = {"memory", "none", "postgres"}


@dataclass(frozen=True)
class GraphRuntimeConfig:
    session_tutor_graph_enabled: bool
    checkpoint_backend: str


def graph_runtime_config_from_settings(settings: Settings) -> GraphRuntimeConfig:
    backend = settings.session_tutor_graph_checkpoint_backend.strip().lower()
    if backend not in SUPPORTED_CHECKPOINT_BACKENDS:
        raise ValueError("Unsupported graph checkpoint backend")
    return GraphRuntimeConfig(
        session_tutor_graph_enabled=settings.session_tutor_graph_enabled,
        checkpoint_backend=backend,
    )
