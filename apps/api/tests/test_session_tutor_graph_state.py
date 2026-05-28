import uuid

from app.domain.session_tutor_graph.state import (
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
