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
    state = SessionTutorGraphState(
        tenant_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        content="Explain grounded answers.",
        node_trace=[],
        learning_signals=[],
    )

    assert state["content"] == "Explain grounded answers."
    assert state["node_trace"] == []


def test_session_tutor_graph_state_uses_string_source_filename_keys() -> None:
    source_id = str(uuid.uuid4())
    state = SessionTutorGraphState(
        tenant_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        session_id=uuid.uuid4(),
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
        tenant_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        content="Explain grounded answers.",
        citations=[citation],
        node_trace=[],
        learning_signals=[],
    )

    assert state["citations"][0]["source_id"] == citation["source_id"]
    assert state["citations"][0]["chunk_id"] == citation["chunk_id"]
    citations_type = get_args(SessionTutorGraphState.__annotations__["citations"])[0]
    assert get_args(citations_type) == (AnswerCitation,)
