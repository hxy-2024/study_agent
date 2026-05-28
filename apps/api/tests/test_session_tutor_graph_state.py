import uuid
from typing import get_args

from app.domain.session_tutor_graph.state import (
    AnswerCitation,
    ChapterSupervision,
    SessionTutorGraphState,
    build_learning_signals,
)


def test_build_learning_signals_detects_confusion_and_evidence() -> None:
    signals = build_learning_signals(
        content="I am confused about citations.",
        citation_count=2,
        chapter_supervision=ChapterSupervision(
            summary="Needs stronger evidence use.",
            weak_points=["Citation grounding"],
            next_actions=["Review cited chunks"],
        ),
    )

    by_type = {signal["type"]: signal for signal in signals}
    assert by_type["confusion_detected"]["value"] is True
    assert by_type["needs_review"]["value"] is True
    assert by_type["evidence_used"]["value"] is True
    assert by_type["chapter_supervision_used"]["value"] is True


def test_session_tutor_graph_state_accepts_required_ids() -> None:
    tenant_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    state = SessionTutorGraphState(
        tenant_id=tenant_id,
        user_id=user_id,
        session_id=session_id,
        content="Explain grounded answers.",
        node_trace=[],
        learning_signals=[],
    )

    assert state["tenant_id"] == tenant_id
    assert state["user_id"] == user_id
    assert state["session_id"] == session_id
    assert state["content"] == "Explain grounded answers."
    assert state["node_trace"] == []
    assert SessionTutorGraphState.__annotations__["tenant_id"] is str
    assert SessionTutorGraphState.__annotations__["user_id"] is str
    assert SessionTutorGraphState.__annotations__["session_id"] is str


def test_session_tutor_graph_state_uses_string_optional_ids_and_evidence_ids() -> None:
    source_id = str(uuid.uuid4())
    chunk_id = str(uuid.uuid4())
    state = SessionTutorGraphState(
        tenant_id=str(uuid.uuid4()),
        user_id=str(uuid.uuid4()),
        session_id=str(uuid.uuid4()),
        study_space_id=str(uuid.uuid4()),
        chapter_id=str(uuid.uuid4()),
        user_message_id=str(uuid.uuid4()),
        assistant_message_id=str(uuid.uuid4()),
        content="Explain grounded answers.",
        retrieved_chunks=[
            {
                "source_id": source_id,
                "chunk_id": chunk_id,
                "chunk_index": 1,
                "text": "Evidence",
                "score": 0.8,
            }
        ],
        node_trace=[],
        learning_signals=[],
    )

    assert state["retrieved_chunks"][0]["source_id"] == source_id
    assert state["retrieved_chunks"][0]["chunk_id"] == chunk_id
    assert get_args(SessionTutorGraphState.__annotations__["study_space_id"])[0] is str
    assert get_args(SessionTutorGraphState.__annotations__["chapter_id"])[0] is str
    assert get_args(SessionTutorGraphState.__annotations__["user_message_id"])[0] is str
    assert get_args(SessionTutorGraphState.__annotations__["assistant_message_id"])[0] is str


def test_session_tutor_graph_state_uses_string_source_filename_keys() -> None:
    source_id = str(uuid.uuid4())
    state = SessionTutorGraphState(
        tenant_id=str(uuid.uuid4()),
        user_id=str(uuid.uuid4()),
        session_id=str(uuid.uuid4()),
        content="Explain grounded answers.",
        source_filenames={source_id: "vectors.md"},
        node_trace=[],
        learning_signals=[],
    )

    assert state["source_filenames"][source_id] == "vectors.md"
    source_filenames_type = get_args(
        SessionTutorGraphState.__annotations__["source_filenames"]
    )[0]
    assert get_args(source_filenames_type) == (str, str)


def test_session_tutor_graph_state_uses_json_safe_citation_ids() -> None:
    citation = AnswerCitation(
        source_id=str(uuid.uuid4()),
        chunk_id=str(uuid.uuid4()),
        source_filename="vectors.md",
        chunk_index=3,
        text="Vector search retrieves semantically related chunks.",
        score=0.87,
    )
    state = SessionTutorGraphState(
        tenant_id=str(uuid.uuid4()),
        user_id=str(uuid.uuid4()),
        session_id=str(uuid.uuid4()),
        content="Explain grounded answers.",
        citations=[citation],
        node_trace=[],
        learning_signals=[],
    )

    assert state["citations"][0]["source_id"] == citation["source_id"]
    assert state["citations"][0]["chunk_id"] == citation["chunk_id"]
    citations_type = get_args(SessionTutorGraphState.__annotations__["citations"])[0]
    assert get_args(citations_type) == (AnswerCitation,)
