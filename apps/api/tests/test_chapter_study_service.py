import uuid
from types import SimpleNamespace
from typing import Any

import pytest

from app.db.models import ChapterStatus, LearningRouteStatus
from app.domain.chapter_study.service import (
    build_chapter_detail,
    chapter_response,
    complete_chapter,
    evidence_response,
    find_next_chapter,
    load_chapter_evidence,
    referenced_chunk_ids,
)


def make_chapter(order_index: int, status: ChapterStatus = ChapterStatus.not_started):
    return SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        study_space_id=uuid.uuid4(),
        learning_route_id=uuid.uuid4(),
        order_index=order_index,
        title=f"Chapter {order_index}",
        goal="Learn the concept.",
        summary="Study the core material.",
        estimated_days=3,
        status=status,
        source_chunk_refs=[],
    )


def test_chapter_response_maps_model() -> None:
    chapter = make_chapter(order_index=1, status=ChapterStatus.active)

    response = chapter_response(chapter)

    assert response.id == chapter.id
    assert response.status == "active"
    assert response.order_index == 1


def test_evidence_response_truncates_text() -> None:
    source = SimpleNamespace(id=uuid.uuid4(), filename="notes.md")
    chunk = SimpleNamespace(
        id=uuid.uuid4(),
        source_id=source.id,
        chunk_index=0,
        text="x" * 800,
        citation={"page_number": 2},
    )

    response = evidence_response(chunk=chunk, source=source, max_chars=700)

    assert response.source_filename == "notes.md"
    assert response.chunk_index == 0
    assert len(response.text) == 700
    assert response.citation == {"page_number": 2}


def test_referenced_chunk_ids_ignores_invalid_refs() -> None:
    valid_id = uuid.uuid4()

    assert referenced_chunk_ids([{"chunk_id": str(valid_id)}, {"chunk_id": "bad"}, {"source_id": str(uuid.uuid4())}]) == [
        valid_id
    ]


@pytest.mark.anyio
async def test_load_chapter_evidence_scopes_to_active_referenced_chunks() -> None:
    tenant_id = uuid.uuid4()
    study_space_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    source = SimpleNamespace(id=uuid.uuid4(), filename="notes.md")
    chunk = SimpleNamespace(
        id=chunk_id,
        tenant_id=tenant_id,
        study_space_id=study_space_id,
        source_id=source.id,
        chunk_index=2,
        text="relevant text",
        citation={},
        is_active=True,
    )
    chapter = SimpleNamespace(
        tenant_id=tenant_id,
        study_space_id=study_space_id,
        source_chunk_refs=[{"chunk_id": str(chunk_id)}, {"chunk_id": "not-a-uuid"}],
    )

    class Rows:
        def all(self) -> list[tuple[Any, Any]]:
            return [(chunk, source)]

    class FakeSession:
        statement = None

        async def execute(self, statement):
            self.statement = statement
            return Rows()

    session = FakeSession()

    responses = await load_chapter_evidence(
        session=session,
        tenant_id=tenant_id,
        chapter=chapter,
    )

    assert responses[0].chunk_id == chunk_id
    statement_text = str(session.statement)
    assert "source_chunks.id IN" in statement_text
    assert "source_chunks.tenant_id =" in statement_text
    assert "source_chunks.study_space_id =" in statement_text
    assert "source_chunks.is_active IS true" in statement_text
    assert "sources.tenant_id =" in statement_text
    assert "sources.study_space_id =" in statement_text


def test_find_next_chapter_uses_lowest_incomplete_after_current() -> None:
    current = make_chapter(order_index=1, status=ChapterStatus.active)
    completed = make_chapter(order_index=2, status=ChapterStatus.completed)
    next_chapter = make_chapter(order_index=3, status=ChapterStatus.not_started)
    later = make_chapter(order_index=4, status=ChapterStatus.not_started)

    assert find_next_chapter(current, [later, completed, next_chapter]) == next_chapter


def test_build_chapter_detail_returns_next_chapter_id() -> None:
    current = make_chapter(order_index=1, status=ChapterStatus.active)
    next_chapter = make_chapter(order_index=2, status=ChapterStatus.not_started)
    route = SimpleNamespace(
        id=current.learning_route_id,
        study_space_id=current.study_space_id,
        version=1,
        status=LearningRouteStatus.active,
        title="Route",
    )
    study_space = SimpleNamespace(id=current.study_space_id, name="Linear Algebra")

    detail = build_chapter_detail(
        chapter=current,
        route=route,
        study_space=study_space,
        evidence=[],
        route_chapters=[current, next_chapter],
    )

    assert detail.chapter.id == current.id
    assert detail.route.title == "Route"
    assert detail.study_space.name == "Linear Algebra"
    assert detail.next_chapter_id == next_chapter.id
    assert [chapter.id for chapter in detail.chapters] == [current.id, next_chapter.id]


@pytest.mark.anyio
async def test_complete_chapter_is_idempotent_when_already_completed(monkeypatch) -> None:
    chapter = make_chapter(order_index=1, status=ChapterStatus.completed)
    route = SimpleNamespace(
        id=chapter.learning_route_id,
        study_space_id=chapter.study_space_id,
        version=1,
        status=LearningRouteStatus.active,
        title="Route",
    )
    study_space = SimpleNamespace(id=chapter.study_space_id, name="Linear Algebra")

    async def fake_load_chapter_context(**kwargs):
        return chapter, route, study_space, [chapter], []

    monkeypatch.setattr("app.domain.chapter_study.service.load_chapter_context", fake_load_chapter_context)

    class FakeSession:
        committed = False

        async def commit(self) -> None:
            self.committed = True

    session = FakeSession()
    detail = await complete_chapter(
        session=session,
        tenant_id=chapter.tenant_id,
        chapter_id=chapter.id,
    )

    assert detail.chapter.status == "completed"
    assert detail.next_chapter_id is None
    assert session.committed is False


@pytest.mark.anyio
async def test_complete_chapter_activates_next_incomplete(monkeypatch) -> None:
    current = make_chapter(order_index=1, status=ChapterStatus.active)
    next_chapter = make_chapter(order_index=2, status=ChapterStatus.not_started)
    next_chapter.tenant_id = current.tenant_id
    next_chapter.study_space_id = current.study_space_id
    next_chapter.learning_route_id = current.learning_route_id
    route = SimpleNamespace(
        id=current.learning_route_id,
        study_space_id=current.study_space_id,
        version=1,
        status=LearningRouteStatus.active,
        title="Route",
    )
    study_space = SimpleNamespace(id=current.study_space_id, name="Linear Algebra")

    async def fake_load_chapter_context(**kwargs):
        return current, route, study_space, [current, next_chapter], []

    monkeypatch.setattr("app.domain.chapter_study.service.load_chapter_context", fake_load_chapter_context)

    class FakeSession:
        async def commit(self) -> None:
            return None

    detail = await complete_chapter(
        session=FakeSession(),
        tenant_id=current.tenant_id,
        chapter_id=current.id,
    )

    assert current.status == ChapterStatus.completed
    assert next_chapter.status == ChapterStatus.active
    assert detail.chapter.status == "completed"
    assert detail.next_chapter_id == next_chapter.id
