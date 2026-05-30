import uuid
from types import SimpleNamespace

from app.domain.study_spaces.export import format_study_space_markdown, serialize_study_space_export


def test_serialize_study_space_export_keeps_learning_artifacts() -> None:
    tenant_id = uuid.uuid4()
    study_space_id = uuid.uuid4()
    source_id = uuid.uuid4()
    chapter_id = uuid.uuid4()

    payload = serialize_study_space_export(
        study_space=SimpleNamespace(
            id=study_space_id,
            tenant_id=tenant_id,
            name="RAG Basics",
            goal="Understand retrieval augmented generation.",
            level="beginner",
            intensity="normal",
            target_days=14,
            status="active",
            route_outline=[],
            created_at=None,
            updated_at=None,
        ),
        sources=[
            SimpleNamespace(
                id=source_id,
                filename="rag.md",
                content_type="text/markdown",
                object_key="tenants/t/spaces/s/sources/rag.md",
                status="ready",
                error_message=None,
                created_at=None,
            )
        ],
        chunks=[
            SimpleNamespace(
                id=uuid.uuid4(),
                source_id=source_id,
                chunk_index=0,
                text="Retrieval grounds answers in uploaded evidence.",
                citation={"heading": "Retrieval"},
                is_active=True,
                created_at=None,
            )
        ],
        routes=[SimpleNamespace(id=uuid.uuid4(), version=1, status="active", title="Main route", summary="Study RAG")],
        chapters=[
            SimpleNamespace(
                id=chapter_id,
                learning_route_id=uuid.uuid4(),
                order_index=1,
                title="Retrieval",
                goal="Learn retrieval.",
                summary="How search supports answers.",
                estimated_days=2,
                status="completed",
                source_chunk_refs=[],
                created_at=None,
            )
        ],
        sessions=[SimpleNamespace(id=uuid.uuid4(), chapter_id=chapter_id, title="Mentor chat", status="active", summary=None)],
        messages=[SimpleNamespace(id=uuid.uuid4(), session_id=uuid.uuid4(), role="assistant", content="Use citations.", created_at=None)],
        quizzes=[SimpleNamespace(id=uuid.uuid4(), chapter_id=chapter_id, title="Retrieval Quiz", status="submitted", question_count=3)],
        notes=[SimpleNamespace(id=uuid.uuid4(), chapter_id=chapter_id, kind="note", content="Review citations", quote=None)],
    )

    assert payload["study_space"]["name"] == "RAG Basics"
    assert payload["sources"][0]["chunks"][0]["text"] == "Retrieval grounds answers in uploaded evidence."
    assert payload["chapters"][0]["title"] == "Retrieval"
    assert payload["sessions"][0]["title"] == "Mentor chat"
    assert payload["quizzes"][0]["title"] == "Retrieval Quiz"
    assert payload["notes"][0]["content"] == "Review citations"


def test_format_study_space_markdown_is_readable() -> None:
    markdown = format_study_space_markdown(
        {
            "study_space": {"name": "RAG Basics", "goal": "Understand retrieval."},
            "sources": [{"filename": "rag.md", "status": "ready", "chunks": [{"text": "Chunk text"}]}],
            "routes": [{"title": "Main route", "status": "active"}],
            "chapters": [{"title": "Retrieval", "status": "completed", "summary": "Search evidence."}],
            "sessions": [{"title": "Mentor chat", "messages": [{"role": "assistant", "content": "Use citations."}]}],
            "quizzes": [{"title": "Retrieval Quiz", "status": "submitted"}],
            "notes": [{"content": "Review citations"}],
        }
    )

    assert markdown.startswith("# RAG Basics")
    assert "## Sources" in markdown
    assert "- rag.md (ready)" in markdown
    assert "## Chapters" in markdown
    assert "Retrieval" in markdown
    assert "Use citations." in markdown
