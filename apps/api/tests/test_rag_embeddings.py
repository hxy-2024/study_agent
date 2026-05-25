from app.domain.rag.embeddings import DeterministicEmbeddingProvider


def test_deterministic_embedding_provider_returns_configured_dimension() -> None:
    provider = DeterministicEmbeddingProvider(dimension=16)

    vector = provider.embed_text("gradient descent optimizes loss")

    assert len(vector) == 16
    assert all(isinstance(value, float) for value in vector)
    assert any(value != 0.0 for value in vector)
