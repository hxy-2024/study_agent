import uuid

from pydantic import BaseModel


class ChapterStudyChapterResponse(BaseModel):
    id: uuid.UUID
    study_space_id: uuid.UUID
    learning_route_id: uuid.UUID
    order_index: int
    title: str
    goal: str
    summary: str
    estimated_days: int
    status: str
    source_chunk_refs: list[dict]


class ChapterStudyRouteResponse(BaseModel):
    id: uuid.UUID
    study_space_id: uuid.UUID
    version: int
    status: str
    title: str


class ChapterStudySpaceResponse(BaseModel):
    id: uuid.UUID
    name: str


class ChapterEvidenceResponse(BaseModel):
    source_id: uuid.UUID
    chunk_id: uuid.UUID
    chunk_index: int
    source_filename: str
    text: str
    citation: dict


class ChapterStudyDetailResponse(BaseModel):
    chapter: ChapterStudyChapterResponse
    route: ChapterStudyRouteResponse
    study_space: ChapterStudySpaceResponse
    evidence: list[ChapterEvidenceResponse]
    next_chapter_id: uuid.UUID | None = None
