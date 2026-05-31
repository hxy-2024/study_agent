from types import SimpleNamespace

import httpx
import pytest

from app.domain.rag.embeddings import (
    DeterministicEmbeddingProvider,
    OpenAICompatibleEmbeddingProvider,
    create_embedding_provider_from_preset,
)


def test_deterministic_embedding_provider_returns_configured_dimension() -> None:
    provider = DeterministicEmbeddingProvider(dimension=16)

    vector = provider.embed_text("gradient descent optimizes loss")
    repeated_vector = provider.embed_text("gradient descent optimizes loss")

    assert isinstance(vector, list)
    assert len(vector) == 16
    assert all(isinstance(value, float) for value in vector)
    assert any(value != 0.0 for value in vector)
    assert repeated_vector == vector


def test_embedding_preset_factory_uses_local_retrieval_vectors() -> None:
    provider = create_embedding_provider_from_preset("local-deterministic", dimension=16)

    assert isinstance(provider, DeterministicEmbeddingProvider)
    assert len(provider.embed_text("chunk")) == 16


def test_embedding_preset_factory_rejects_chat_models() -> None:
    with pytest.raises(ValueError, match="not a retrieval embedding model"):
        create_embedding_provider_from_preset("configured:deepseek-chat", dimension=16)


def test_embedding_preset_factory_creates_configured_embedding_provider() -> None:
    provider = create_embedding_provider_from_preset(
        "configured:text-embedding-v4",
        dimension=16,
        local_ai_settings=SimpleNamespace(
            embedding_base_url="https://dashscope.example.test/compatible-mode/v1",
            embedding_api_key="embedding-secret",
            embedding_dimensions=1024,
            llm_base_url="",
            llm_api_key="",
        ),
        timeout_seconds=12,
    )

    assert isinstance(provider, OpenAICompatibleEmbeddingProvider)
    assert provider.base_url == "https://dashscope.example.test/compatible-mode/v1"
    assert provider.model == "text-embedding-v4"
    assert provider.requested_dimensions == 1024


def test_openai_compatible_embedding_provider_posts_embeddings(monkeypatch) -> None:
    captured = {}

    class FakeClient:
        def __init__(self, *, timeout: int) -> None:
            captured["timeout"] = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback) -> None:
            return None

        def post(self, url: str, *, headers: dict[str, str], json: dict) -> httpx.Response:
            captured["url"] = url
            captured["authorization"] = headers["Authorization"]
            captured["payload"] = json
            return httpx.Response(
                200,
                json={"data": [{"embedding": [3.0, 4.0]}]},
                request=httpx.Request("POST", url),
            )

    monkeypatch.setattr(httpx, "Client", FakeClient)
    provider = OpenAICompatibleEmbeddingProvider(
        base_url="https://dashscope.example.test/compatible-mode/v1",
        api_key="embedding-secret",
        model="text-embedding-v4",
        dimensions=1024,
        timeout_seconds=12,
    )

    vector = provider.embed_text("retrieval text")

    assert captured["url"] == "https://dashscope.example.test/compatible-mode/v1/embeddings"
    assert captured["authorization"] == "Bearer embedding-secret"
    assert captured["payload"] == {
        "model": "text-embedding-v4",
        "input": "retrieval text",
        "dimensions": 1024,
    }
    assert vector == [0.6, 0.8]
    assert provider.dimension == 2
