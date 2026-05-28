import os
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models import (
    AgentRun,
    AgentRunStatus,
    AgentType,
    Chapter,
    ChapterMentorState,
    ChapterStatus,
    LearningRoute,
    LearningRouteStatus,
    Message,
    MessageRole,
    Session,
    SessionStatus,
    StudySpace,
    Tenant,
    User,
)
from app.domain.chapter_mentor_state.service import build_signal_insights, generate_chapter_mentor_state
from app.domain.chapter_mentor_state import service as chapter_mentor_service


class FakeScalarResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows

    def __iter__(self):
        return iter(self._rows)


def make_chapter(tenant_id: uuid.UUID, study_space_id: uuid.UUID, chapter_id: uuid.UUID) -> Chapter:
    return Chapter(
        id=chapter_id,
        tenant_id=tenant_id,
        study_space_id=study_space_id,
        learning_route_id=uuid.uuid4(),
        order_index=1,
        title="Retrieval basics",
        goal="Understand grounded answers",
        summary="Use citations in answers",
        estimated_days=2,
        source_chunk_refs=[],
    )


def make_message(tenant_id: uuid.UUID, study_space_id: uuid.UUID, session_id: uuid.UUID, content: str) -> Message:
    return Message(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        study_space_id=study_space_id,
        session_id=session_id,
        role=MessageRole.user,
        content=content,
        metadata_={},
        created_at=datetime.now(UTC),
    )


def test_build_signal_insights_converts_learning_signals_to_state_inputs() -> None:
    insights = build_signal_insights(
        [
            {
                "run_id": "run-1",
                "session_id": "session-1",
                "signals": [
                    {
                        "type": "confusion_detected",
                        "value": True,
                        "rationale": "Learner question includes confusion markers.",
                    },
                    {
                        "type": "needs_review",
                        "value": True,
                        "rationale": "Review is useful.",
                    },
                    {
                        "type": "evidence_used",
                        "value": False,
                        "rationale": "Assistant answer included 0 citations.",
                    },
                ],
            }
        ]
    )

    assert "Recent tutor sessions show learner confusion." in insights.weak_points
    assert "Tutor answers need stronger cited evidence." in insights.weak_points
    assert "Run a focused review based on recent tutor confusion signals." in insights.next_actions
    assert insights.evidence[0]["run_id"] == "run-1"


def test_build_signal_insights_ignores_malformed_helper_inputs() -> None:
    insights = build_signal_insights(
        [
            {"run_id": "bad-signals", "session_id": "session-1", "signals": "not-a-list"},
            {
                "run_id": "mixed-signals",
                "session_id": "session-2",
                "signals": [
                    None,
                    "not-a-dict",
                    {"type": None, "value": True},
                    {"type": "needs_review", "value": "true"},
                    {"type": "confusion_detected", "value": True},
                    {"type": "evidence_used", "value": False},
                ],
            },
        ]
    )

    assert insights.weak_points == [
        "Recent tutor sessions show learner confusion.",
        "Tutor answers need stronger cited evidence.",
    ]
    assert insights.next_actions == []
    assert insights.evidence == [
        {
            "kind": "learning_signal",
            "run_id": "mixed-signals",
            "session_id": "session-2",
            "signal_types": ["confusion_detected", "evidence_used"],
        }
    ]


def test_build_signal_insights_deduplicates_and_limits_evidence() -> None:
    duplicate_run = {
        "run_id": "run-1",
        "session_id": "session-1",
        "signals": [
            {"type": "chapter_supervision_used", "value": True},
            {"type": "needs_review", "value": True},
        ],
    }
    unique_runs = [
        {
            "run_id": f"run-{index}",
            "session_id": f"session-{index}",
            "signals": [{"type": "confusion_detected", "value": True}],
        }
        for index in range(2, 8)
    ]

    insights = build_signal_insights([duplicate_run, duplicate_run, *unique_runs])

    assert len(insights.evidence) == 5
    assert insights.evidence.count(insights.evidence[0]) == 1
    assert insights.evidence[0] == {
        "kind": "learning_signal",
        "run_id": "run-1",
        "session_id": "session-1",
        "signal_types": ["chapter_supervision_used", "needs_review"],
    }


def test_build_signal_insights_no_signal_behavior_keeps_existing_empty_outputs() -> None:
    insights = build_signal_insights(
        [
            {"run_id": "run-1", "session_id": "session-1", "signals": []},
            {"run_id": "run-2", "session_id": "session-2"},
        ]
    )

    assert insights.weak_points == []
    assert insights.next_actions == []
    assert insights.evidence == []


def test_build_signal_runs_statement_filters_completed_session_tutor_runs_for_chapter() -> None:
    tenant_id = uuid.uuid4()
    chapter_id = uuid.uuid4()

    statement = chapter_mentor_service._build_signal_runs_statement(tenant_id, chapter_id)
    compiled = statement.compile(compile_kwargs={"literal_binds": True})
    sql = str(compiled)

    assert "agent_runs.tenant_id" in sql
    assert tenant_id.hex in sql
    assert "agent_runs.agent_type" in sql
    assert AgentType.session_tutor.value in sql
    assert "agent_runs.status" in sql
    assert AgentRunStatus.completed.value in sql
    assert "sessions.chapter_id" in sql
    assert chapter_id.hex in sql


@pytest.mark.anyio
async def test_generate_writes_chapter_mentor_state_and_agent_run() -> None:
    tenant_id = uuid.uuid4()
    study_space_id = uuid.uuid4()
    chapter_id = uuid.uuid4()
    session_id = uuid.uuid4()
    chapter = make_chapter(tenant_id, study_space_id, chapter_id)
    messages = [
        make_message(tenant_id, study_space_id, session_id, "What is retrieval?"),
        make_message(tenant_id, study_space_id, session_id, "I am confused about citations."),
    ]
    added = []

    class FakeSession:
        def __init__(self):
            self.scalar_calls = 0
            self.scalars_calls = 0
            self.committed = False

        async def scalar(self, _statement):
            self.scalar_calls += 1
            if self.scalar_calls == 1:
                return chapter
            return None

        async def scalars(self, _statement):
            self.scalars_calls += 1
            if self.scalars_calls == 1:
                return FakeScalarResult(messages)
            return FakeScalarResult([])

        def add(self, obj) -> None:
            added.append(obj)

        async def commit(self) -> None:
            self.committed = True

        async def refresh(self, obj) -> None:
            if obj.id is None:
                obj.id = uuid.uuid4()
            if getattr(obj, "created_at", None) is None:
                obj.created_at = datetime.now(UTC)
            if getattr(obj, "updated_at", None) is None:
                obj.updated_at = datetime.now(UTC)

    fake_session = FakeSession()

    result = await generate_chapter_mentor_state(
        session=fake_session,
        tenant_id=tenant_id,
        chapter_id=chapter_id,
    )

    states = [obj for obj in added if obj.__class__.__name__ == "ChapterMentorState"]
    runs = [obj for obj in added if isinstance(obj, AgentRun)]
    assert len(states) == 1
    assert len(runs) == 1
    assert fake_session.committed is True
    assert result.chapter_id == chapter_id
    assert result.source_message_count == 2
    assert result.source_session_count == 1
    assert result.summary
    assert result.weak_points
    assert all(isinstance(weak_point, str) for weak_point in result.weak_points)
    assert result.next_actions
    assert all(isinstance(next_action, str) for next_action in result.next_actions)

    run = runs[0]
    assert run.agent_type == AgentType.chapter_mentor
    assert run.status == AgentRunStatus.completed
    assert run.model == "deterministic"
    assert run.study_space_id == study_space_id
    assert run.session_id is None
    assert run.message_id is None
    assert run.input_payload["chapter_id"] == str(chapter_id)
    assert run.input_payload["message_count"] == 2
    assert run.output_payload["chapter_id"] == str(chapter_id)
    assert run.output_payload["state_id"] == str(result.id)


@pytest.mark.anyio
async def test_generate_enriches_state_from_completed_session_tutor_learning_signals() -> None:
    tenant_id = uuid.uuid4()
    study_space_id = uuid.uuid4()
    chapter_id = uuid.uuid4()
    session_id = uuid.uuid4()
    chapter = make_chapter(tenant_id, study_space_id, chapter_id)
    messages = [
        make_message(tenant_id, study_space_id, session_id, "What is retrieval practice?"),
    ]
    signal_runs = [
        AgentRun(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            study_space_id=study_space_id,
            session_id=session_id,
            message_id=None,
            agent_type=AgentType.session_tutor,
            status=AgentRunStatus.completed,
            model="deterministic",
            input_payload={},
            output_payload={
                "learning_signals": [
                    {
                        "type": "confusion_detected",
                        "value": True,
                        "rationale": "Learner question includes confusion markers.",
                    },
                    {
                        "type": "needs_review",
                        "value": True,
                        "rationale": "Review is useful.",
                    },
                ]
            },
        )
    ]
    added = []

    class FakeSession:
        def __init__(self):
            self.scalar_calls = 0
            self.scalars_calls = 0

        async def scalar(self, _statement):
            self.scalar_calls += 1
            if self.scalar_calls == 1:
                return chapter
            return None

        async def scalars(self, _statement):
            self.scalars_calls += 1
            if self.scalars_calls == 1:
                return FakeScalarResult(messages)
            return FakeScalarResult(signal_runs)

        def add(self, obj) -> None:
            added.append(obj)

        async def commit(self) -> None:
            return None

        async def refresh(self, obj) -> None:
            if obj.id is None:
                obj.id = uuid.uuid4()
            if getattr(obj, "created_at", None) is None:
                obj.created_at = datetime.now(UTC)
            if getattr(obj, "updated_at", None) is None:
                obj.updated_at = datetime.now(UTC)

    result = await generate_chapter_mentor_state(
        session=FakeSession(),
        tenant_id=tenant_id,
        chapter_id=chapter_id,
    )

    assert any("learner confusion" in item.lower() for item in result.weak_points)
    assert any("focused review" in item.lower() for item in result.next_actions)
    assert any(item.get("kind") == "learning_signal" for item in result.evidence)


@pytest.mark.anyio
async def test_generate_treats_non_dict_output_payload_as_no_learning_signals() -> None:
    tenant_id = uuid.uuid4()
    study_space_id = uuid.uuid4()
    chapter_id = uuid.uuid4()
    session_id = uuid.uuid4()
    chapter = make_chapter(tenant_id, study_space_id, chapter_id)
    messages = [
        make_message(tenant_id, study_space_id, session_id, "I am confused about citations."),
    ]
    signal_runs = [
        AgentRun(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            study_space_id=study_space_id,
            session_id=session_id,
            message_id=None,
            agent_type=AgentType.session_tutor,
            status=AgentRunStatus.completed,
            model="deterministic",
            input_payload={},
            output_payload="not-a-dict",
        )
    ]

    class FakeSession:
        def __init__(self):
            self.scalar_calls = 0
            self.scalars_calls = 0

        async def scalar(self, _statement):
            self.scalar_calls += 1
            if self.scalar_calls == 1:
                return chapter
            return None

        async def scalars(self, _statement):
            self.scalars_calls += 1
            if self.scalars_calls == 1:
                return FakeScalarResult(messages)
            return FakeScalarResult(signal_runs)

        def add(self, _obj) -> None:
            return None

        async def commit(self) -> None:
            return None

        async def refresh(self, obj) -> None:
            if obj.id is None:
                obj.id = uuid.uuid4()
            if getattr(obj, "created_at", None) is None:
                obj.created_at = datetime.now(UTC)
            if getattr(obj, "updated_at", None) is None:
                obj.updated_at = datetime.now(UTC)

    result = await generate_chapter_mentor_state(
        session=FakeSession(),
        tenant_id=tenant_id,
        chapter_id=chapter_id,
    )

    assert result.weak_points == ["Needs clarification: I am confused about citations."]
    assert result.next_actions == [
        "Review the latest discussion and restate the key idea in your own words.",
        "Answer one follow-up question using cited evidence from the chapter sources.",
    ]
    assert all(item.get("kind") != "learning_signal" for item in result.evidence)


@pytest.mark.anyio
async def test_generate_raises_value_error_when_chapter_missing() -> None:
    tenant_id = uuid.uuid4()
    chapter_id = uuid.uuid4()

    class FakeSession:
        async def scalar(self, _statement):
            return None

    with pytest.raises(ValueError, match="Chapter not found for tenant"):
        await generate_chapter_mentor_state(
            session=FakeSession(),
            tenant_id=tenant_id,
            chapter_id=chapter_id,
        )


@pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_TESTS") != "1",
    reason="Postgres integration tests require RUN_POSTGRES_TESTS=1 and DATABASE_URL",
)
@pytest.mark.anyio
async def test_generate_upserts_state_and_persists_agent_run_with_postgres() -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    rows = None
    try:
        async with session_factory() as session:
            rows = await _create_chapter_with_session(session)
            await _add_message(session, rows, "What is retrieval?")
            await session.commit()

            first_result = await generate_chapter_mentor_state(
                session=session,
                tenant_id=rows.tenant.id,
                chapter_id=rows.chapter.id,
            )

            await _add_message(session, rows, "I am confused about citations.")
            await session.commit()

            second_result = await generate_chapter_mentor_state(
                session=session,
                tenant_id=rows.tenant.id,
                chapter_id=rows.chapter.id,
            )

            states = (
                (
                    await session.execute(
                        select(ChapterMentorState).where(
                            ChapterMentorState.chapter_id == rows.chapter.id
                        )
                    )
                )
                .scalars()
                .all()
            )
            runs = (
                (
                    await session.execute(
                        select(AgentRun)
                        .where(
                            AgentRun.tenant_id == rows.tenant.id,
                            AgentRun.agent_type == AgentType.chapter_mentor,
                        )
                        .order_by(AgentRun.created_at, AgentRun.id)
                    )
                )
                .scalars()
                .all()
            )
    finally:
        if rows is not None:
            async with session_factory() as cleanup_session:
                await _cleanup_rows(cleanup_session, rows)
        await engine.dispose()

    assert first_result.id == second_result.id
    assert len(states) == 1
    assert states[0].id == second_result.id
    assert states[0].source_message_count == 2
    assert all(isinstance(point, str) for point in states[0].weak_points)
    assert all(isinstance(action, str) for action in states[0].next_actions)
    assert len(runs) == 2
    assert runs[-1].output_payload["state_id"] == str(states[0].id)


class CreatedChapterRows:
    def __init__(
        self,
        tenant: Tenant,
        user: User,
        study_space: StudySpace,
        learning_route: LearningRoute,
        chapter: Chapter,
        tutor_session: Session,
    ) -> None:
        self.tenant = tenant
        self.user = user
        self.study_space = study_space
        self.learning_route = learning_route
        self.chapter = chapter
        self.tutor_session = tutor_session


async def _create_chapter_with_session(session) -> CreatedChapterRows:
    unique_id = uuid.uuid4()
    tenant = Tenant(name=f"Chapter Mentor Tenant {unique_id}")
    user = User(
        email=f"chapter-mentor-{unique_id}@example.com",
        display_name="Chapter Mentor User",
    )
    session.add_all([tenant, user])
    await session.flush()

    study_space = StudySpace(
        tenant_id=tenant.id,
        owner_user_id=user.id,
        name="Chapter Mentor Space",
        goal="Learn grounded tutoring",
    )
    session.add(study_space)
    await session.flush()

    learning_route = LearningRoute(
        tenant_id=tenant.id,
        study_space_id=study_space.id,
        version=1,
        status=LearningRouteStatus.active,
        title="Grounded Tutor Route",
        summary="Route for mentor state tests.",
        generation_strategy="deterministic",
    )
    session.add(learning_route)
    await session.flush()

    chapter = Chapter(
        tenant_id=tenant.id,
        study_space_id=study_space.id,
        learning_route_id=learning_route.id,
        order_index=1,
        title="Retrieval basics",
        goal="Understand grounded answers",
        summary="Use citations in answers",
        estimated_days=2,
        status=ChapterStatus.active,
        source_chunk_refs=[],
    )
    session.add(chapter)
    await session.flush()

    tutor_session = Session(
        tenant_id=tenant.id,
        study_space_id=study_space.id,
        chapter_id=chapter.id,
        title="Mentor state session",
        status=SessionStatus.active,
    )
    session.add(tutor_session)
    await session.flush()

    return CreatedChapterRows(
        tenant=tenant,
        user=user,
        study_space=study_space,
        learning_route=learning_route,
        chapter=chapter,
        tutor_session=tutor_session,
    )


async def _add_message(session, rows: CreatedChapterRows, content: str) -> None:
    session.add(
        Message(
            tenant_id=rows.tenant.id,
            study_space_id=rows.study_space.id,
            session_id=rows.tutor_session.id,
            role=MessageRole.user,
            content=content,
            metadata_={},
        )
    )


async def _cleanup_rows(session, rows: CreatedChapterRows) -> None:
    await session.execute(delete(AgentRun).where(AgentRun.study_space_id == rows.study_space.id))
    await session.execute(delete(ChapterMentorState).where(ChapterMentorState.chapter_id == rows.chapter.id))
    await session.execute(delete(Message).where(Message.session_id == rows.tutor_session.id))
    await session.execute(delete(Session).where(Session.id == rows.tutor_session.id))
    await session.execute(delete(Chapter).where(Chapter.id == rows.chapter.id))
    await session.execute(delete(LearningRoute).where(LearningRoute.id == rows.learning_route.id))
    await session.execute(delete(StudySpace).where(StudySpace.id == rows.study_space.id))
    await session.execute(delete(User).where(User.id == rows.user.id))
    await session.execute(delete(Tenant).where(Tenant.id == rows.tenant.id))
    await session.commit()
