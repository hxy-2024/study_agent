from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import StudySpace
from app.domain.study_spaces.schemas import StudySpaceCreate


def create_route_outline(goal: str, target_days: int) -> list[dict]:
    first_block = max(1, target_days // 4)
    middle_block = max(1, target_days // 2)
    final_block = max(1, target_days - first_block - middle_block)
    return [
        {
            "order": 1,
            "title": "学习目标梳理",
            "description": f"明确 {goal} 的学习范围、已有基础和完成标准。",
            "estimated_days": first_block,
        },
        {
            "order": 2,
            "title": "核心概念学习",
            "description": "围绕资料和目标拆解关键概念，建立基础知识结构。",
            "estimated_days": middle_block,
        },
        {
            "order": 3,
            "title": "综合复习与测评",
            "description": "通过小测、错题和复习卡片检查掌握情况。",
            "estimated_days": final_block,
        },
    ]


async def create_study_space(session: AsyncSession, payload: StudySpaceCreate) -> StudySpace:
    study_space = StudySpace(
        tenant_id=payload.tenant_id,
        owner_user_id=payload.owner_user_id,
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
        .order_by(StudySpace.created_at.desc())
    )
    return list(result.scalars().all())
