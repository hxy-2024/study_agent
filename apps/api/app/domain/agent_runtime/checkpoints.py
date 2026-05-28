from typing import Any

from langgraph.checkpoint.memory import MemorySaver

from app.domain.agent_runtime.config import GraphRuntimeConfig


def create_checkpointer(config: GraphRuntimeConfig) -> Any | None:
    if config.checkpoint_backend == "none":
        return None
    if config.checkpoint_backend == "memory":
        return MemorySaver()
    if config.checkpoint_backend == "postgres":
        raise ValueError("Postgres graph checkpointing is not configured")
    raise ValueError("Unsupported graph checkpoint backend")
