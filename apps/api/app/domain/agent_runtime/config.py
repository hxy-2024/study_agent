from dataclasses import dataclass
from typing import Literal, cast

from app.core.config import Settings


CheckpointBackend = Literal["memory", "none", "postgres"]

SUPPORTED_CHECKPOINT_BACKENDS: set[CheckpointBackend] = {"memory", "none", "postgres"}


@dataclass(frozen=True)
class GraphRuntimeConfig:
    session_tutor_graph_enabled: bool
    checkpoint_backend: CheckpointBackend


def graph_runtime_config_from_settings(settings: Settings) -> GraphRuntimeConfig:
    raw_backend = settings.session_tutor_graph_checkpoint_backend.strip().lower()
    if raw_backend not in SUPPORTED_CHECKPOINT_BACKENDS:
        raise ValueError("Unsupported graph checkpoint backend")
    backend = cast(CheckpointBackend, raw_backend)
    return GraphRuntimeConfig(
        session_tutor_graph_enabled=settings.session_tutor_graph_enabled,
        checkpoint_backend=backend,
    )
