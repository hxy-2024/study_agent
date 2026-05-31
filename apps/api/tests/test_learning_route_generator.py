import uuid
import json

import httpx
import pytest

from app.domain.learning_routes.generator import (
    DeterministicRouteGenerator,
    LLMRouteGenerator,
    RouteGenerationRequest,
    SourceChunkExcerpt,
)


@pytest.mark.anyio
async def test_deterministic_generator_uses_goal_without_chunks() -> None:
    generator = DeterministicRouteGenerator()

    result = await generator.generate(
        RouteGenerationRequest(
            tenant_id=uuid.uuid4(),
            study_space_id=uuid.uuid4(),
            study_space_name="Linear Algebra",
            goal="Understand matrices",
            level="beginner",
            intensity="normal",
            target_days=14,
            max_chapters=5,
            chunks=[],
        )
    )

    assert result.generation_strategy == "deterministic"
    assert result.title == "Linear Algebra learning route"
    assert len(result.chapters) == 3
    assert result.chapters[0].title == "Clarify the learning goal"
    assert "Understand matrices" in result.chapters[0].goal
    assert sum(chapter.estimated_days for chapter in result.chapters) == 14


@pytest.mark.anyio
async def test_deterministic_generator_groups_chunk_references_into_minimum_chapters() -> None:
    source_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    generator = DeterministicRouteGenerator()

    result = await generator.generate(
        RouteGenerationRequest(
            tenant_id=uuid.uuid4(),
            study_space_id=uuid.uuid4(),
            study_space_name="RAG Basics",
            goal="Learn retrieval",
            level="intermediate",
            intensity="normal",
            target_days=10,
            max_chapters=4,
            chunks=[
                SourceChunkExcerpt(
                    source_id=source_id,
                    chunk_id=chunk_id,
                    chunk_index=0,
                    text="Embeddings convert text into vectors for semantic retrieval.",
                )
            ],
        )
    )

    assert len(result.chapters) == 3
    assert result.chapters[0].title == "Embeddings convert text into vectors"
    assert result.chapters[0].source_chunk_refs == [
        {
            "source_id": str(source_id),
            "chunk_id": str(chunk_id),
            "chunk_index": 0,
        }
    ]
    assert sum(chapter.estimated_days for chapter in result.chapters) == 10


@pytest.mark.anyio
async def test_deterministic_generator_caps_chunk_chapters_at_six() -> None:
    generator = DeterministicRouteGenerator()

    result = await generator.generate(
        RouteGenerationRequest(
            tenant_id=uuid.uuid4(),
            study_space_id=uuid.uuid4(),
            study_space_name="RAG Basics",
            goal="Learn retrieval",
            level="intermediate",
            intensity="normal",
            target_days=12,
            max_chapters=8,
            chunks=[
                SourceChunkExcerpt(
                    source_id=uuid.uuid4(),
                    chunk_id=uuid.uuid4(),
                    chunk_index=index,
                    text=f"Topic {index} explains retrieval foundations.",
                )
                for index in range(8)
            ],
        )
    )

    assert len(result.chapters) == 6
    assert sum(len(chapter.source_chunk_refs) for chapter in result.chapters) == 6


@pytest.mark.anyio
async def test_llm_route_generator_posts_evidence_and_parses_json_route() -> None:
    source_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
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
                            "content": json.dumps(
                                {
                                    "title": "RAG study route",
                                    "summary": "Learn retrieval in a source-grounded order.",
                                    "chapters": [
                                        {
                                            "title": "Understand embeddings",
                                            "goal": "Explain how vectors support retrieval.",
                                            "summary": "Study the embedding evidence and practice recall.",
                                            "estimated_days": 3,
                                            "source_chunk_indexes": [1],
                                        }
                                    ],
                                }
                            )
                        }
                    }
                ]
            },
        )

    request = RouteGenerationRequest(
        tenant_id=uuid.uuid4(),
        study_space_id=uuid.uuid4(),
        study_space_name="RAG Basics",
        goal="Learn retrieval",
        level="beginner",
        intensity="normal",
        target_days=7,
        max_chapters=4,
        chunks=[
            SourceChunkExcerpt(
                source_id=source_id,
                chunk_id=chunk_id,
                chunk_index=2,
                text="Embeddings convert text into vectors for semantic retrieval.",
            )
        ],
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await LLMRouteGenerator(
            base_url="https://llm.example/v1",
            api_key="secret-key",
            model="study-model",
            timeout_seconds=10,
            client=client,
        ).generate(request)

    assert captured["url"] == "https://llm.example/v1/chat/completions"
    assert captured["authorization"] == "Bearer secret-key"
    assert captured["payload"]["model"] == "study-model"
    assert "Embeddings convert text" in captured["payload"]["messages"][1]["content"]
    assert result.generation_strategy == "llm_rag"
    assert result.title == "RAG study route"
    assert result.chapters[0].title == "Understand embeddings"
    assert result.chapters[0].source_chunk_refs == [
        {
            "source_id": str(source_id),
            "chunk_id": str(chunk_id),
            "chunk_index": 2,
        }
    ]


@pytest.mark.anyio
async def test_llm_route_generator_falls_back_on_invalid_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "not json"}}]},
        )

    request = RouteGenerationRequest(
        tenant_id=uuid.uuid4(),
        study_space_id=uuid.uuid4(),
        study_space_name="RAG Basics",
        goal="Learn retrieval",
        level="beginner",
        intensity="normal",
        target_days=7,
        max_chapters=4,
        chunks=[
            SourceChunkExcerpt(
                source_id=uuid.uuid4(),
                chunk_id=uuid.uuid4(),
                chunk_index=0,
                text="Retrieval evidence.",
            )
        ],
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await LLMRouteGenerator(
            base_url="https://llm.example/v1",
            api_key="secret-key",
            model="study-model",
            timeout_seconds=10,
            client=client,
        ).generate(request)

    assert result.generation_strategy == "deterministic"
