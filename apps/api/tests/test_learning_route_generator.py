import uuid

import pytest

from app.domain.learning_routes.generator import (
    DeterministicRouteGenerator,
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
