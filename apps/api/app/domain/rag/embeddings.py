import hashlib
import math
from abc import ABC, abstractmethod
from typing import Any

import httpx

LOCAL_DETERMINISTIC_PRESET = "local-deterministic"
CONFIGURED_PRESET_PREFIX = "configured:"
EMBEDDING_MODEL_MARKERS = (
    "embedding",
    "embed",
    "bge",
    "gte",
    "jina",
    "e5-",
)


class EmbeddingProvider(ABC):
    @property
    def provider_key(self) -> str:
        return self.__class__.__name__

    @property
    def model_name(self) -> str:
        return self.provider_key

    @property
    @abstractmethod
    def dimension(self) -> int:
        raise NotImplementedError

    @abstractmethod
    def embed_text(self, text: str) -> list[float]:
        raise NotImplementedError


class DeterministicEmbeddingProvider(EmbeddingProvider):
    def __init__(self, dimension: int) -> None:
        if dimension <= 0:
            raise ValueError("Embedding dimension must be positive")
        self._dimension = dimension

    @property
    def provider_key(self) -> str:
        return LOCAL_DETERMINISTIC_PRESET

    @property
    def model_name(self) -> str:
        return LOCAL_DETERMINISTIC_PRESET

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_text(self, text: str) -> list[float]:
        normalized = " ".join(text.lower().split())
        values: list[float] = []
        for index in range(self._dimension):
            digest = hashlib.sha256(f"{index}:{normalized}".encode("utf-8")).digest()
            integer = int.from_bytes(digest[:8], "big", signed=False)
            values.append((integer / ((1 << 64) - 1)) * 2.0 - 1.0)
        length = math.sqrt(sum(value * value for value in values))
        if length == 0:
            return [0.0 for _ in values]
        return [value / length for value in values]


class OpenAICompatibleEmbeddingProvider(EmbeddingProvider):
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        dimensions: int | None = None,
        timeout_seconds: int,
    ) -> None:
        if not base_url.strip():
            raise ValueError("Embedding base URL is required")
        if not api_key.strip():
            raise ValueError("Embedding API key is required")
        if not model.strip():
            raise ValueError("Embedding model is required")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.requested_dimensions = dimensions
        self.timeout_seconds = timeout_seconds
        self._dimension = 0

    @property
    def provider_key(self) -> str:
        return "openai-compatible"

    @property
    def model_name(self) -> str:
        return self.model

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_text(self, text: str) -> list[float]:
        payload: dict[str, Any] = {"model": self.model, "input": text}
        if self.requested_dimensions is not None:
            payload["dimensions"] = self.requested_dimensions
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(
                    f"{self.base_url}/embeddings",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=payload,
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Embedding request failed: {exc}") from exc
        vector = _extract_embedding_vector(response.json())
        self._dimension = len(vector)
        return _normalize_vector(vector)


def is_likely_embedding_model(model: str) -> bool:
    normalized = model.strip().lower()
    return any(marker in normalized for marker in EMBEDDING_MODEL_MARKERS)


def _extract_embedding_vector(payload: dict[str, Any]) -> list[float]:
    data = payload.get("data")
    if not isinstance(data, list) or not data:
        raise RuntimeError("Embedding response did not include data")
    first = data[0]
    if not isinstance(first, dict):
        raise RuntimeError("Embedding response data is invalid")
    embedding = first.get("embedding")
    if not isinstance(embedding, list) or not embedding:
        raise RuntimeError("Embedding response did not include an embedding vector")
    return [float(value) for value in embedding]


def _normalize_vector(values: list[float]) -> list[float]:
    length = math.sqrt(sum(value * value for value in values))
    if length == 0:
        return [0.0 for _ in values]
    return [value / length for value in values]


def create_embedding_provider_from_preset(
    preset: str | None,
    *,
    dimension: int,
    local_ai_settings: Any | None = None,
    runtime_settings: Any | None = None,
    timeout_seconds: int = 30,
) -> EmbeddingProvider:
    configured_default = ""
    if local_ai_settings is not None:
        configured_default = str(getattr(local_ai_settings, "embedding_model", "") or "").strip()
    if not configured_default and runtime_settings is not None:
        configured_default = str(getattr(runtime_settings, "embedding_model", "") or "").strip()
    normalized = (preset or "").strip()
    if not normalized:
        normalized = (
            f"{CONFIGURED_PRESET_PREFIX}{configured_default}"
            if configured_default
            else LOCAL_DETERMINISTIC_PRESET
        )
    if normalized == LOCAL_DETERMINISTIC_PRESET:
        return DeterministicEmbeddingProvider(dimension)
    if normalized.startswith(CONFIGURED_PRESET_PREFIX):
        model = normalized.removeprefix(CONFIGURED_PRESET_PREFIX).strip()
        if not is_likely_embedding_model(model):
            raise ValueError(
                f"Model '{model}' is not a retrieval embedding model. "
                "Use the local retrieval index for now, or configure a dedicated embedding model."
            )
        if local_ai_settings is None and runtime_settings is None:
            raise ValueError("AI settings are required for configured embedding models")
        base_url = (
            str(getattr(local_ai_settings, "embedding_base_url", "") or "").strip()
            or str(getattr(runtime_settings, "embedding_base_url", "") or "").strip()
            or str(getattr(local_ai_settings, "llm_base_url", "") or "").strip()
            or str(getattr(runtime_settings, "llm_base_url", "") or "").strip()
        )
        api_key = (
            str(getattr(local_ai_settings, "embedding_api_key", "") or "").strip()
            or str(getattr(runtime_settings, "embedding_api_key", "") or "").strip()
            or str(getattr(local_ai_settings, "llm_api_key", "") or "").strip()
            or str(getattr(runtime_settings, "llm_api_key", "") or "").strip()
        )
        dimensions = getattr(local_ai_settings, "embedding_dimensions", None) or getattr(
            runtime_settings,
            "embedding_dimensions",
            None,
        )
        return OpenAICompatibleEmbeddingProvider(
            base_url=base_url,
            api_key=api_key,
            model=model,
            dimensions=dimensions,
            timeout_seconds=timeout_seconds,
        )
    raise ValueError(f"Unknown embedding preset: {normalized}")
