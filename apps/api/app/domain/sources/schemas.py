import uuid

from pydantic import BaseModel, Field


class UploadPresignRequest(BaseModel):
    tenant_id: uuid.UUID
    study_space_id: uuid.UUID
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=120)


class UploadPresignResponse(BaseModel):
    source_id: uuid.UUID
    object_key: str
    upload_url: str
    method: str = "PUT"
