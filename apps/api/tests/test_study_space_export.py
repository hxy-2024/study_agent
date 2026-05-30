import uuid
from types import SimpleNamespace

from app.domain.study_spaces.export import EXPORT_SCHEMA_VERSION, format_study_space_markdown, serialize_study_space_export


def test_serialize_study_space_export_keeps_learning_artifacts() -> None:
    tenant_id = uuid.uuid4()
    study_space_id = uuid.uuid4()
    source_id = uuid.uuid4()
    chapter_id = uuid.uuid4()
    quiz_id = uuid.uuid4()
    question_id = uuid.uuid4()
    submission_id = uuid.uuid4()
    message_id = uuid.uuid4()
    planner_state_id = uuid.uuid4()
    session_id = uuid.uuid4()
    route_id = uuid.uuid4()

    payload = serialize_study_space_export(
        study_space=SimpleNamespace(
            id=study_space_id,
            tenant_id=tenant_id,
            owner_user_id=uuid.uuid4(),
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
        routes=[
            SimpleNamespace(
                id=route_id,
                version=1,
                status="active",
                title="Main route",
                summary="Study RAG",
                generation_strategy="deterministic",
                created_at=None,
                activated_at=None,
            )
        ],
        chapters=[
            SimpleNamespace(
                id=chapter_id,
                learning_route_id=route_id,
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
        sessions=[
            SimpleNamespace(
                id=session_id,
                chapter_id=chapter_id,
                title="Mentor chat",
                status="active",
                summary=None,
                created_at=None,
                updated_at=None,
            )
        ],
        messages=[
            SimpleNamespace(
                id=message_id,
                session_id=session_id,
                role="assistant",
                content="Use citations.",
                metadata_={"tone": "direct"},
                created_at=None,
            )
        ],
        message_citations=[
            SimpleNamespace(
                id=uuid.uuid4(),
                message_id=message_id,
                source_id=source_id,
                source_chunk_id=uuid.uuid4(),
                quote="Retrieval grounds answers",
                citation={"heading": "Retrieval"},
                created_at=None,
            )
        ],
        quizzes=[
            SimpleNamespace(
                id=quiz_id,
                user_id=uuid.uuid4(),
                chapter_id=chapter_id,
                title="Retrieval Quiz",
                status="submitted",
                generation_strategy="deterministic",
                question_count=3,
                created_at=None,
                updated_at=None,
            )
        ],
        quiz_questions=[
            SimpleNamespace(
                id=question_id,
                quiz_id=quiz_id,
                chapter_id=chapter_id,
                order_index=0,
                prompt="What grounds an answer?",
                options=["Evidence", "Guessing"],
                correct_option_index=0,
                explanation="Evidence grounds answers.",
                evidence={"source_chunk_id": "chunk-1"},
                created_at=None,
            )
        ],
        quiz_submissions=[
            SimpleNamespace(
                id=submission_id,
                quiz_id=quiz_id,
                chapter_id=chapter_id,
                user_id=uuid.uuid4(),
                answers=[0],
                score_percent=100,
                correct_count=1,
                question_count=1,
                results=[{"question_id": str(question_id), "is_correct": True}],
                weak_points=[],
                created_at=None,
            )
        ],
        mastery_records=[
            SimpleNamespace(
                id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                chapter_id=chapter_id,
                score_percent=100,
                level="mastered",
                weak_points=[],
                last_quiz_submission_id=submission_id,
                updated_at=None,
            )
        ],
        mentor_states=[
            SimpleNamespace(
                id=uuid.uuid4(),
                chapter_id=chapter_id,
                summary="Learner cites evidence well.",
                weak_points=[],
                next_actions=["Continue"],
                evidence=[{"kind": "quiz_result"}],
                source_session_count=1,
                source_message_count=1,
                created_at=None,
                updated_at=None,
            )
        ],
        planner_states=[
            SimpleNamespace(
                id=planner_state_id,
                user_id=uuid.uuid4(),
                summary="Continue to retrieval practice.",
                next_chapter_id=chapter_id,
                risk_chapters=[],
                review_recommendations=[],
                route_adjustments=[],
                evidence=[],
                created_at=None,
                updated_at=None,
            )
        ],
        planner_actions=[
            SimpleNamespace(
                id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                chapter_id=chapter_id,
                source_planner_state_id=planner_state_id,
                action_type="review_chapter",
                status="proposed",
                title="Review retrieval",
                rationale="Refresh before continuing.",
                payload={"chapter_id": str(chapter_id)},
                created_at=None,
                updated_at=None,
            )
        ],
        agent_runs=[
            SimpleNamespace(
                id=uuid.uuid4(),
                session_id=None,
                message_id=message_id,
                agent_type="session_tutor",
                status="completed",
                model="deterministic",
                input_payload={"content": "question"},
                output_payload={"content": "answer"},
                error_message=None,
                latency_ms=10,
                prompt_tokens=1,
                completion_tokens=2,
                total_tokens=3,
                created_at=None,
                completed_at=None,
            )
        ],
        notes=[
            SimpleNamespace(
                id=uuid.uuid4(),
                chapter_id=chapter_id,
                source_chunk_id=None,
                kind="note",
                content="Review citations",
                quote=None,
                anchor={},
                created_at=None,
                updated_at=None,
            )
        ],
    )

    assert payload["schema_version"] == EXPORT_SCHEMA_VERSION
    assert payload["study_space"]["name"] == "RAG Basics"
    assert payload["study_space"]["owner_user_id"]
    assert payload["sources"][0]["chunks"][0]["text"] == "Retrieval grounds answers in uploaded evidence."
    assert payload["chapters"][0]["title"] == "Retrieval"
    assert payload["sessions"][0]["title"] == "Mentor chat"
    assert payload["sessions"][0]["messages"][0]["metadata"] == {"tone": "direct"}
    assert payload["sessions"][0]["messages"][0]["citations"][0]["quote"] == "Retrieval grounds answers"
    assert payload["quizzes"][0]["title"] == "Retrieval Quiz"
    assert payload["quizzes"][0]["questions"][0]["prompt"] == "What grounds an answer?"
    assert payload["quizzes"][0]["submissions"][0]["results"][0]["is_correct"] is True
    assert payload["mastery_records"][0]["last_quiz_submission_id"] == str(submission_id)
    assert payload["mentor_states"][0]["summary"] == "Learner cites evidence well."
    assert payload["planner_states"][0]["next_chapter_id"] == str(chapter_id)
    assert payload["planner_actions"][0]["source_planner_state_id"] == str(planner_state_id)
    assert payload["agent_runs"][0]["message_id"] == str(message_id)
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
