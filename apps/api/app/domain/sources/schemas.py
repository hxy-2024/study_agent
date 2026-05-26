import uuid

from pydantic import BaseModel, ConfigDict, Field


class UploadPresignRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    study_space_id: uuid.UUID
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=120)


class UploadPresignResponse(BaseModel):
    source_id: uuid.UUID
    object_key: str
    upload_url: str
    method: str = "PUT"
