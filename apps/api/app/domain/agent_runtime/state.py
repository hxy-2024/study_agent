from typing import Literal, TypedDict


LearningSignalType = Literal[
    "confusion_detected",
    "needs_review",
    "evidence_used",
    "chapter_supervision_used",
]


class LearningSignal(TypedDict):
    type: LearningSignalType
    value: bool
    rationale: str
