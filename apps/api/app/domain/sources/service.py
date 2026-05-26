import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Source, StudySpace
from app.domain.sources.schemas import UploadPresignRequest
from app.infrastructure.storage import create_presigned_put_url

SUPPORTED_CONTENT_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "text/plain",
    "text/markdown",
}


def validate_content_type(content_type: str) -> None:
    if content_type not in SUPPORTED_CONTENT_TYPES:
        raise ValueError(f"Unsupported content type: {content_type}")


def slugify_filename(filename: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", filename.strip()).strip("-")
    return cleaned or "source"


def build_object_key(tenant_id: uuid.UUID, study_space_id: uuid.UUID, filename: str) -> str:
    source_id = uuid.uuid4()
    safe_name = slugify_filename(filename)
    return f"tenants/{tenant_id}/spaces/{study_space_id}/sources/{source_id}/{safe_name}"


async def ensure_study_space_in_tenant(
    session: AsyncSession,
    study_space_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> StudySpace:
    study_space = await session.scalar(
        select(StudySpace).where(
            StudySpace.id == study_space_id,
            StudySpace.tenant_id == tenant_id,
        )
    )
    if study_space is None:
        raise ValueError("Study space not found for tenant")
    return study_space


async def create_upload_request(
    session: AsyncSession,
    payload: UploadPresignRequest,
    tenant_id: uuid.UUID,
) -> tuple[Source, str]:
    validate_content_type(payload.content_type)
    await ensure_study_space_in_tenant(session, payload.study_space_id, tenant_id)
    object_key = build_object_key(tenant_id, payload.study_space_id, payload.filename)
    source = Source(
        tenant_id=tenant_id,
        study_space_id=payload.study_space_id,
        filename=payload.filename,
        content_type=payload.content_type,
        object_key=object_key,
    )
    session.add(source)
    await session.commit()
    await session.refresh(source)
    upload_url = create_presigned_put_url(object_key=object_key, content_type=payload.content_type)
    return source, upload_url
