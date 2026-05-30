import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import StudySpace, StudySpaceStatus
from app.domain.learning_routes.generator import DeterministicRouteGenerator, RouteGenerationRequest
from app.domain.study_spaces.schemas import StudySpaceCreate


def create_route_outline(goal: str, target_days: int) -> list[dict]:
    request = RouteGenerationRequest(
        tenant_id=uuid.uuid4(),
        study_space_id=uuid.uuid4(),
        study_space_name="Study space",
        goal=goal,
        level="beginner",
        intensity="normal",
        target_days=target_days,
        max_chapters=5,
        chunks=[],
    )
    chapters = DeterministicRouteGenerator()._fallback_chapters(request)
    return [
        {
            "order": index,
            "title": chapter.title,
            "description": chapter.summary,
            "estimated_days": chapter.estimated_days,
        }
        for index, chapter in enumerate(chapters, start=1)
    ]


async def create_study_space(
    session: AsyncSession,
    payload: StudySpaceCreate,
    tenant_id: uuid.UUID,
    owner_user_id: uuid.UUID,
) -> StudySpace:
    study_space = StudySpace(
        tenant_id=tenant_id,
        owner_user_id=owner_user_id,
        name=payload.name,
        goal=payload.goal,
        level=payload.level,
        intensity=payload.intensity,
        target_days=payload.target_days,
        route_outline=create_route_outline(payload.goal, payload.target_days),
    )
    session.add(study_space)
    await session.commit()
    await session.refresh(study_space)
    return study_space


async def list_study_spaces(session: AsyncSession, tenant_id) -> list[StudySpace]:
    result = await session.execute(
        select(StudySpace)
        .where(StudySpace.tenant_id == tenant_id)
        .where(StudySpace.status != StudySpaceStatus.archived)
        .order_by(StudySpace.created_at.desc())
    )
    return list(result.scalars().all())


async def list_archived_study_spaces(session: AsyncSession, tenant_id) -> list[StudySpace]:
    result = await session.execute(
        select(StudySpace)
        .where(StudySpace.tenant_id == tenant_id)
        .where(StudySpace.status == StudySpaceStatus.archived)
        .order_by(StudySpace.updated_at.desc(), StudySpace.created_at.desc())
    )
    return list(result.scalars().all())


async def archive_study_space(session: AsyncSession, tenant_id, study_space_id) -> StudySpace:
    result = await session.execute(
        select(StudySpace)
        .where(StudySpace.tenant_id == tenant_id)
        .where(StudySpace.id == study_space_id)
    )
    study_space = result.scalar_one_or_none()
    if study_space is None:
        raise ValueError("Study space not found for tenant")
    study_space.status = StudySpaceStatus.archived
    await session.commit()
    await session.refresh(study_space)
    return study_space


async def restore_study_space(session: AsyncSession, tenant_id, study_space_id) -> StudySpace:
    result = await session.execute(
        select(StudySpace)
        .where(StudySpace.tenant_id == tenant_id)
        .where(StudySpace.id == study_space_id)
    )
    study_space = result.scalar_one_or_none()
    if study_space is None:
        raise ValueError("Study space not found for tenant")
    study_space.status = StudySpaceStatus.active
    await session.commit()
    await session.refresh(study_space)
    return study_space
