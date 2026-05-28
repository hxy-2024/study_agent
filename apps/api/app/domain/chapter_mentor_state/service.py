import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AgentRun,
    AgentRunStatus,
    AgentType,
    Chapter,
    ChapterMentorState,
    Message,
    Session,
)
from app.domain.chapter_mentor_state.schemas import ChapterMentorStateResponse


@dataclass(frozen=True)
class SignalInsights:
    weak_points: list[str]
    next_actions: list[str]
    evidence: list[dict[str, Any]]


def build_chapter_mentor_state_response(state: ChapterMentorState) -> ChapterMentorStateResponse:
    return ChapterMentorStateResponse(
        id=state.id,
        tenant_id=state.tenant_id,
        study_space_id=state.study_space_id,
        chapter_id=state.chapter_id,
        summary=state.summary,
        weak_points=state.weak_points or [],
        next_actions=state.next_actions or [],
        evidence=state.evidence or [],
        source_session_count=state.source_session_count,
        source_message_count=state.source_message_count,
        created_at=state.created_at,
        updated_at=state.updated_at,
    )


def build_signal_insights(signal_runs: list[dict[str, Any]]) -> SignalInsights:
    weak_points: list[str] = []
    next_actions: list[str] = []
    evidence: list[dict[str, Any]] = []

    for run in signal_runs:
        signals = run.get("signals", [])
        if not isinstance(signals, list):
            continue
        true_signal_types = {
            signal.get("type")
            for signal in signals
            if isinstance(signal, dict) and signal.get("value") is True
        }
        false_signal_types = {
            signal.get("type")
            for signal in signals
            if isinstance(signal, dict) and signal.get("value") is False
        }
        if "confusion_detected" in true_signal_types:
            weak_points.append("Recent tutor sessions show learner confusion.")
        if "needs_review" in true_signal_types:
            next_actions.append("Run a focused review based on recent tutor confusion signals.")
        if "evidence_used" in false_signal_types:
            weak_points.append("Tutor answers need stronger cited evidence.")
        if "chapter_supervision_used" in true_signal_types:
            evidence.append(
                {
                    "kind": "learning_signal",
                    "run_id": run.get("run_id"),
                    "session_id": run.get("session_id"),
                    "signal_types": sorted(true_signal_types),
                }
            )
        elif true_signal_types or false_signal_types:
            evidence.append(
                {
                    "kind": "learning_signal",
                    "run_id": run.get("run_id"),
                    "session_id": run.get("session_id"),
                    "signal_types": sorted(true_signal_types | false_signal_types),
                }
            )

    return SignalInsights(
        weak_points=list(dict.fromkeys(weak_points))[:3],
        next_actions=list(dict.fromkeys(next_actions))[:3],
        evidence=evidence[:5],
    )


async def get_chapter_mentor_state(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    chapter_id: uuid.UUID,
) -> ChapterMentorState | None:
    return await session.scalar(
        select(ChapterMentorState).where(
            ChapterMentorState.tenant_id == tenant_id,
            ChapterMentorState.chapter_id == chapter_id,
        )
    )


def _message_preview(content: str, limit: int = 160) -> str:
    normalized = " ".join(content.split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: limit - 3]}..."


def _build_summary(chapter: Chapter, messages: list[Message], source_session_count: int) -> str:
    if not messages:
        return f"No session messages have been recorded for {chapter.title} yet."
    return (
        f"{chapter.title}: reviewed {len(messages)} messages across "
        f"{source_session_count} sessions. Latest focus: {_message_preview(messages[-1].content, 120)}"
    )


def _build_weak_points(messages: list[Message]) -> list[str]:
    confusion_terms = ("confused", "confusing", "unclear", "stuck", "hard", "difficult")
    weak_points = [
        f"Needs clarification: {_message_preview(message.content)}"
        for message in messages
        if any(term in message.content.lower() for term in confusion_terms)
    ]
    if weak_points:
        return weak_points[:3]
    if messages:
        return ["Keep checking understanding; no explicit weak point was detected."]
    return []


def _build_next_actions(messages: list[Message]) -> list[str]:
    if not messages:
        return ["Start a tutoring session and ask one concrete question about this chapter."]
    return [
        "Review the latest discussion and restate the key idea in your own words.",
        "Answer one follow-up question using cited evidence from the chapter sources.",
    ]


def _build_evidence(messages: list[Message]) -> list[dict]:
    return [
        {
            "message_id": str(message.id),
            "session_id": str(message.session_id),
            "role": message.role.value if hasattr(message.role, "value") else str(message.role),
            "text": _message_preview(message.content),
        }
        for message in messages[:5]
    ]


async def generate_chapter_mentor_state(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    chapter_id: uuid.UUID,
) -> ChapterMentorStateResponse:
    chapter = await session.scalar(
        select(Chapter).where(
            Chapter.id == chapter_id,
            Chapter.tenant_id == tenant_id,
        )
    )
    if chapter is None:
        raise ValueError("Chapter not found for tenant")

    message_rows = await session.scalars(
        select(Message)
        .join(Session, Message.session_id == Session.id)
        .where(
            Message.tenant_id == tenant_id,
            Session.chapter_id == chapter_id,
        )
        .order_by(Message.created_at, Message.id)
    )
    messages = list(message_rows.all() if hasattr(message_rows, "all") else message_rows)
    source_session_count = len({message.session_id for message in messages})
    source_message_count = len(messages)

    signal_run_rows = await session.scalars(
        select(AgentRun)
        .join(Session, AgentRun.session_id == Session.id)
        .where(
            AgentRun.tenant_id == tenant_id,
            AgentRun.agent_type == AgentType.session_tutor,
            AgentRun.status == AgentRunStatus.completed,
            Session.chapter_id == chapter_id,
        )
        .order_by(AgentRun.created_at.desc(), AgentRun.id)
    )
    signal_runs = [
        {
            "run_id": str(run.id),
            "session_id": str(run.session_id),
            "signals": (run.output_payload or {}).get("learning_signals", []),
        }
        for run in list(signal_run_rows.all() if hasattr(signal_run_rows, "all") else signal_run_rows)[:10]
    ]
    signal_insights = build_signal_insights(signal_runs)

    state = await get_chapter_mentor_state(
        session=session,
        tenant_id=tenant_id,
        chapter_id=chapter_id,
    )
    if state is None:
        state = ChapterMentorState(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            study_space_id=chapter.study_space_id,
            chapter_id=chapter.id,
            summary="",
            weak_points=[],
            next_actions=[],
            evidence=[],
            source_session_count=0,
            source_message_count=0,
        )
        session.add(state)
    elif state.id is None:
        state.id = uuid.uuid4()

    state.summary = _build_summary(chapter, messages, source_session_count)
    state.weak_points = list(dict.fromkeys(_build_weak_points(messages) + signal_insights.weak_points))[:3]
    state.next_actions = list(dict.fromkeys(_build_next_actions(messages) + signal_insights.next_actions))[:3]
    state.evidence = (_build_evidence(messages) + signal_insights.evidence)[:8]
    state.source_session_count = source_session_count
    state.source_message_count = source_message_count
    state.updated_at = datetime.now(UTC)

    session.add(
        AgentRun(
            tenant_id=tenant_id,
            study_space_id=chapter.study_space_id,
            session_id=None,
            message_id=None,
            agent_type=AgentType.chapter_mentor,
            status=AgentRunStatus.completed,
            model="deterministic",
            input_payload={
                "chapter_id": str(chapter_id),
                "message_count": source_message_count,
            },
            output_payload={
                "chapter_id": str(chapter_id),
                "state_id": str(state.id),
            },
            completed_at=datetime.now(UTC),
        )
    )

    await session.commit()
    await session.refresh(state)
    return build_chapter_mentor_state_response(state)
