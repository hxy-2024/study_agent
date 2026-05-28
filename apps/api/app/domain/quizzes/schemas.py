import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class GenerateQuizRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_count: int = Field(default=3, ge=1, le=5)


class SubmitQuizRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answers: list[int] = Field(min_length=1)


class QuizEvidenceResponse(BaseModel):
    source_filename: str | None = None
    chunk_index: int | None = None
    text: str | None = None


class QuizQuestionResponse(BaseModel):
    id: uuid.UUID
    order_index: int
    prompt: str
    options: list[str]
    evidence: QuizEvidenceResponse = Field(default_factory=QuizEvidenceResponse)


class QuizQuestionInternalResponse(QuizQuestionResponse):
    correct_option_index: int
    explanation: str


class QuizResponse(BaseModel):
    id: uuid.UUID
    study_space_id: uuid.UUID
    chapter_id: uuid.UUID
    title: str
    status: str
    generation_strategy: str
    question_count: int
    questions: list[QuizQuestionResponse]
    created_at: datetime | None = None
    updated_at: datetime | None = None


class QuizQuestionResultResponse(BaseModel):
    question_id: uuid.UUID
    order_index: int
    prompt: str
    selected_option_index: int
    correct_option_index: int
    is_correct: bool
    explanation: str
    evidence: QuizEvidenceResponse = Field(default_factory=QuizEvidenceResponse)


class MasteryRecordResponse(BaseModel):
    id: uuid.UUID
    study_space_id: uuid.UUID
    chapter_id: uuid.UUID
    score_percent: int
    level: str
    weak_points: list[str]
    last_quiz_submission_id: uuid.UUID
    updated_at: datetime | None = None


class QuizSubmissionResponse(BaseModel):
    id: uuid.UUID
    quiz_id: uuid.UUID
    chapter_id: uuid.UUID
    user_id: uuid.UUID
    answers: list[int]
    score_percent: int
    correct_count: int
    question_count: int
    results: list[QuizQuestionResultResponse]
    weak_points: list[str]
    mastery: MasteryRecordResponse
    created_at: datetime | None = None
