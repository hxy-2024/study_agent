from typing import NotRequired, TypedDict

from app.domain.agent_runtime.state import LearningSignal


class ChapterSupervision(TypedDict):
    summary: str
    weak_points: list[str]
    next_actions: list[str]


class RetrievedEvidence(TypedDict):
    source_id: str
    chunk_id: str
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


class WebSearchResult(TypedDict):
    title: str
    url: str
    snippet: str


class MessageCitationPayload(TypedDict):
    id: str
    message_id: str
    source_id: str
    source_chunk_id: str
    chunk_id: str
    source_filename: str
    chunk_index: int
    text: str
    quote: str
    citation: dict


class MessageResponsePayload(TypedDict):
    id: str
    session_id: str
    role: str
    content: str
    metadata: dict
    citations: list[MessageCitationPayload]
    created_at: str | None


class SessionTutorGraphState(TypedDict):
    tenant_id: str
    user_id: str
    session_id: str
    content: str
    study_space_id: NotRequired[str]
    chapter_id: NotRequired[str]
    user_message_id: NotRequired[str]
    assistant_message_id: NotRequired[str]
    retrieved_chunks: NotRequired[list[RetrievedEvidence]]
    source_filenames: NotRequired[dict[str, str]]
    web_search_results: NotRequired[list[WebSearchResult]]
    web_search_error: NotRequired[str]
    answer: NotRequired[str]
    citations: NotRequired[list[AnswerCitation]]
    assistant_response: NotRequired[MessageResponsePayload]
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
