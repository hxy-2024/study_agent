import uuid
from typing import NotRequired, TypedDict

from app.domain.agent_runtime.state import LearningSignal


class ChapterSupervision(TypedDict):
    summary: str
    weak_points: list[str]
    next_actions: list[str]


class RetrievedEvidence(TypedDict):
    source_id: uuid.UUID
    chunk_id: uuid.UUID
    chunk_index: int
    text: str
    score: float


class AnswerCitation(TypedDict):
    source_id: str
    chunk_id: str
    source_filename: str
    chunk_index: int
    text: str
    score: float


class SessionTutorGraphState(TypedDict):
    tenant_id: uuid.UUID
    user_id: uuid.UUID
    session_id: uuid.UUID
    content: str
    study_space_id: NotRequired[uuid.UUID]
    chapter_id: NotRequired[uuid.UUID]
    user_message_id: NotRequired[uuid.UUID]
    assistant_message_id: NotRequired[uuid.UUID]
    retrieved_chunks: NotRequired[list[RetrievedEvidence]]
    source_filenames: NotRequired[dict[str, str]]
    answer: NotRequired[str]
    citations: NotRequired[list[AnswerCitation]]
    chapter_supervision: NotRequired[ChapterSupervision | None]
    learning_signals: list[LearningSignal]
    node_trace: list[str]
    error_message: NotRequired[str]


def _has_confusion(content: str) -> bool:
    markers = (
        "confused",
        "confusing",
        "unclear",
        "stuck",
        "hard",
        "difficult",
    )
    lowered = content.lower()
    return any(marker in lowered for marker in markers)


def build_learning_signals(
    content: str,
    citation_count: int,
    chapter_supervision: ChapterSupervision | None,
) -> list[LearningSignal]:
    confusion_detected = _has_confusion(content)
    weak_points = chapter_supervision["weak_points"] if chapter_supervision else []

    return [
        {
            "type": "confusion_detected",
            "value": confusion_detected,
            "rationale": (
                "Learner question includes confusion markers."
                if confusion_detected
                else "No explicit confusion marker was detected."
            ),
        },
        {
            "type": "needs_review",
            "value": confusion_detected or bool(weak_points),
            "rationale": "Review is useful when the learner is confused or weak points exist.",
        },
        {
            "type": "evidence_used",
            "value": citation_count > 0,
            "rationale": f"Assistant answer included {citation_count} citations.",
        },
        {
            "type": "chapter_supervision_used",
            "value": chapter_supervision is not None,
            "rationale": (
                "Chapter Mentor state was loaded."
                if chapter_supervision
                else "No Chapter Mentor state was available."
            ),
        },
    ]
