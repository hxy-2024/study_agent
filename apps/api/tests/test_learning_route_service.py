import uuid
from types import SimpleNamespace

import pytest

from app.db.models import ChapterStatus, LearningRouteStatus, SourceChunk, StudySpace
from app.domain.learning_routes.generator import DeterministicRouteGenerator
from app.domain.learning_routes.service import (
    build_route_outline,
    collect_chunk_excerpts,
    persist_generated_route,
)


def make_study_space(tenant_id: uuid.UUID, study_space_id: uuid.UUID) -> StudySpace:
    return StudySpace(
        id=study_space_id,
        tenant_id=tenant_id,
        owner_user_id=uuid.uuid4(),
        name="RAG Basics",
        goal="Learn retrieval",
        level="beginner",
        intensity="normal",
        target_days=9,
    )


def test_collect_chunk_excerpts_limits_text() -> None:
    source_id = uuid.uuid4()
    chunk = SourceChunk(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        study_space_id=uuid.uuid4(),
        source_id=source_id,
        chunk_index=0,
        text="x" * 600,
        token_count=10,
        citation={},
        embedding=[0.1] * 16,
        is_active=True,
    )

    excerpts = collect_chunk_excerpts([chunk], max_excerpt_chars=500)

    assert len(excerpts) == 1
    assert excerpts[0].source_id == source_id
    assert len(excerpts[0].text) == 500


@pytest.mark.anyio
async def test_persist_generated_route_creates_draft_route_and_chapters() -> None:
    tenant_id = uuid.uuid4()
    study_space_id = uuid.uuid4()
    study_space = make_study_space(tenant_id, study_space_id)
    added = []

    class FakeSession:
        def add(self, obj) -> None:
            added.append(obj)

        async def flush(self) -> None:
            for obj in added:
                if getattr(obj, "id", None) is None:
                    obj.id = uuid.uuid4()

    route, chapters = await persist_generated_route(
        session=FakeSession(),
        study_space=study_space,
        version=1,
        chunks=[],
        generator=DeterministicRouteGenerator(),
        max_chapters=5,
    )

    assert route.status == LearningRouteStatus.draft
    assert route.tenant_id == tenant_id
    assert route.study_space_id == study_space_id
    assert len(chapters) == 3
    assert chapters[0].status == ChapterStatus.not_started
    assert chapters[0].learning_route_id == route.id


def test_build_route_outline_maps_chapters() -> None:
    chapters = [
        SimpleNamespace(order_index=1, title="Intro", summary="Start", estimated_days=2),
        SimpleNamespace(order_index=2, title="Practice", summary="Apply", estimated_days=3),
    ]

    assert build_route_outline(chapters) == [
        {"order": 1, "title": "Intro", "description": "Start", "estimated_days": 2},
        {"order": 2, "title": "Practice", "description": "Apply", "estimated_days": 3},
    ]
