import uuid
import json

import httpx
import pytest

from app.core.config import Settings
from app.domain.chapter_mentor.providers import (
    DeterministicAnswerProvider,
    OpenAICompatibleAnswerProvider,
    create_answer_provider,
)
from app.domain.rag.retrieval import RetrievedChunk


def retrieved_chunk(text: str, *, chunk_index: int = 0) -> RetrievedChunk:
    return RetrievedChunk(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        study_space_id=uuid.uuid4(),
        source_id=uuid.uuid4(),
        chunk_index=chunk_index,
        text=text,
        citation={},
        embedding=[0.1] * 16,
        score=0.9,
    )


@pytest.mark.anyio
async def test_deterministic_provider_returns_grounded_answer() -> None:
    chunks = [retrieved_chunk("RAG retrieves evidence before answering.")]
    provider = DeterministicAnswerProvider()

    response = await provider.answer(
        question="How does RAG work?",
        chunks=chunks,
        source_filenames={chunks[0].source_id: "rag.md"},
    )

    assert "RAG retrieves evidence" in response.answer
    assert response.citations[0].source_filename == "rag.md"


@pytest.mark.anyio
async def test_openai_compatible_provider_posts_grounded_prompt() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers["authorization"]
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "Use retrieval evidence first, then explain the idea."
                        }
                    }
                ]
            },
        )

    chunks = [retrieved_chunk("Retrieval evidence text.", chunk_index=3)]
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAICompatibleAnswerProvider(
            base_url="https://llm.example/v1",
            api_key="test-key",
            model="mentor-model",
            timeout_seconds=10,
            client=client,
        )
        response = await provider.answer(
            question="What should I focus on?",
            chunks=chunks,
            source_filenames={chunks[0].source_id: "notes.md"},
        )

    assert captured["url"] == "https://llm.example/v1/chat/completions"
    assert captured["authorization"] == "Bearer test-key"
    assert captured["payload"]["model"] == "mentor-model"
    assert "concise explanation" in captured["payload"]["messages"][0]["content"]
    assert "Retrieval evidence text." in captured["payload"]["messages"][1]["content"]
    assert response.answer == "Use retrieval evidence first, then explain the idea."
    assert response.citations[0].source_filename == "notes.md"


@pytest.mark.anyio
async def test_openai_compatible_provider_uses_custom_system_prompt() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "Custom mentor answer."}}]},
        )

    chunks = [retrieved_chunk("Evidence for the custom prompt.")]
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAICompatibleAnswerProvider(
            base_url="https://llm.example/v1",
            api_key="test-key",
            model="mentor-model",
            timeout_seconds=10,
            answer_style="exam_review",
            system_prompt="Use the user's custom chapter mentor policy.",
            client=client,
        )
        await provider.answer(
            question="What should I do?",
            chunks=chunks,
            source_filenames={chunks[0].source_id: "notes.md"},
        )

    system_prompt = captured["payload"]["messages"][0]["content"]
    assert "Use the user's custom chapter mentor policy." in system_prompt
    assert "exam review style" in system_prompt


@pytest.mark.anyio
async def test_openai_compatible_provider_adds_thinking_effort_instruction() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "Detailed answer."}}]},
        )

    chunks = [retrieved_chunk("Evidence for high effort.")]
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAICompatibleAnswerProvider(
            base_url="https://llm.example/v1",
            api_key="test-key",
            model="mentor-model",
            timeout_seconds=10,
            client=client,
        )
        await provider.answer(
            question="Explain carefully.",
            chunks=chunks,
            source_filenames={chunks[0].source_id: "notes.md"},
            thinking_effort="high",
        )

    system_prompt = captured["payload"]["messages"][0]["content"]
    assert "high reasoning depth" in system_prompt


@pytest.mark.anyio
async def test_openai_compatible_provider_includes_web_search_context() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "Use the web context carefully."}}]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAICompatibleAnswerProvider(
            base_url="https://llm.example/v1",
            api_key="test-key",
            model="mentor-model",
            timeout_seconds=10,
            answer_style="socratic",
            client=client,
        )
        response = await provider.answer(
            question="What changed recently?",
            chunks=[],
            source_filenames={},
            web_search_results=[
                {
                    "title": "Recent RAG context",
                    "url": "https://example.test/rag",
                    "snippet": "A recent note about retrieval augmented generation.",
                }
            ],
        )

    assert "Socratic style" in captured["payload"]["messages"][0]["content"]
    user_prompt = captured["payload"]["messages"][1]["content"]
    assert "No uploaded chapter evidence retrieved." in user_prompt
    assert "Web search context:" in user_prompt
    assert "Recent RAG context" in user_prompt
    assert "https://example.test/rag" in user_prompt
    assert response.answer == "Use the web context carefully."


@pytest.mark.anyio
async def test_openai_compatible_provider_falls_back_when_no_chunks() -> None:
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(500))) as client:
        provider = OpenAICompatibleAnswerProvider(
            base_url="https://llm.example/v1",
            api_key="test-key",
            model="mentor-model",
            timeout_seconds=10,
            client=client,
        )
        response = await provider.answer(
            question="What should I focus on?",
            chunks=[],
            source_filenames={},
        )

    assert "could not find enough source material" in response.answer
    assert response.citations == []


def test_create_answer_provider_uses_deterministic_without_api_key() -> None:
    provider = create_answer_provider(
        Settings(_env_file=None, llm_provider="openai-compatible", llm_api_key="")
    )

    assert isinstance(provider, DeterministicAnswerProvider)


def test_create_answer_provider_uses_openai_compatible_with_api_key() -> None:
    provider = create_answer_provider(
        Settings(
            _env_file=None,
            llm_provider="openai-compatible",
            llm_api_key="test-key",
            llm_base_url="https://llm.example/v1",
            llm_model="mentor-model",
        )
    )

    assert isinstance(provider, OpenAICompatibleAnswerProvider)
