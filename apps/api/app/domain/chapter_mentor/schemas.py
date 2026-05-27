import uuid

from pydantic import BaseModel, ConfigDict, Field


class ChapterMentorQuestionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=2000)


class ChapterMentorCitationResponse(BaseModel):
    chunk_id: uuid.UUID
    source_id: uuid.UUID
    source_filename: str
    chunk_index: int
    text: str


class ChapterMentorResponse(BaseModel):
    question: str
    answer: str
    citations: list[ChapterMentorCitationResponse]

