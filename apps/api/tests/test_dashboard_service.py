import uuid

import pytest

from app.db.models import (
    AgentRun,
    AgentRunStatus,
    AgentType,
    Chapter,
    ChapterStatus,
    PlannerAction,
    PlannerActionStatus,
    PlannerActionType,
    Quiz,
    QuizStatus,
    SpacePlannerState,
    StudySpace,
)
from app.domain.dashboard.schemas import DashboardRecommendationRequest
from app.domain.dashboard.service import get_dashboard_summary, get_main_agent_recommendation


class FakeScalarRows:
    def __init__(self, rows) -> None:
        self._rows = rows

    def __iter__(self):
        return iter(self._rows)


class FakeCommitSession:
    def __init__(self, rows) -> None:
        self.calls = 0
        self.rows = rows
        self.added = []
        self.committed = False

    async def scalars(self, _statement):
        result = self.rows[self.calls] if self.calls < len(self.rows) else []
        self.calls += 1
        return FakeScalarRows(result)

    def add(self, row) -> None:
        row.id = row.id or uuid.uuid4()
        self.added.append(row)

    async def commit(self) -> None:
        self.committed = True


@pytest.mark.anyio
async def test_dashboard_summary_collects_local_learning_work() -> None:
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    study_space_id = uuid.uuid4()
    captured = {}
    rows = [
        [
            StudySpace(
                id=study_space_id,
                tenant_id=tenant_id,
                owner_user_id=user_id,
                name="Linear Algebra",
                goal="Master eigenvectors",
                target_days=21,
            )
        ],
        [
            PlannerAction(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                user_id=user_id,
                study_space_id=study_space_id,
                action_type=PlannerActionType.review_chapter,
                status=PlannerActionStatus.proposed,
                title="Review retrieval",
                rationale="Reason",
                payload={},
            )
        ],
        [
            SpacePlannerState(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                user_id=user_id,
                study_space_id=study_space_id,
                summary="Plan",
                evidence=[{"needs_supervision_refresh": True}, {"needs_supervision_refresh": False}],
            )
        ],
        [
            AgentRun(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                study_space_id=study_space_id,
                agent_type=AgentType.session_tutor,
                status=AgentRunStatus.completed,
                output_payload={"summary": "Tutor answered with citations."},
            )
        ],
        [],
    ]

    class FakeSession:
        def __init__(self) -> None:
            self.calls = 0

        async def scalars(self, _statement):
            captured[f"query_{self.calls}"] = str(_statement.compile(compile_kwargs={"literal_binds": True}))
            result = rows[self.calls] if self.calls < len(rows) else []
            self.calls += 1
            return FakeScalarRows(result)

    response = await get_dashboard_summary(
        session=FakeSession(),
        tenant_id=tenant_id,
        user_id=user_id,
    )

    assert response.spaces[0].name == "Linear Algebra"
    assert "archived" in captured["query_0"]
    assert "study_spaces" in captured["query_1"]
    assert "archived" in captured["query_1"]
    assert "study_spaces" in captured["query_2"]
    assert "archived" in captured["query_2"]
    assert "study_spaces" in captured["query_3"]
    assert "archived" in captured["query_3"]
    assert "study_spaces" in captured["query_4"]
    assert "archived" in captured["query_4"]
    assert response.pending_actions[0].title == "Review retrieval"
    assert response.supervision_refresh_count == 1
    assert response.recent_agent_runs[0].summary == "Tutor answered with citations."


@pytest.mark.anyio
async def test_dashboard_summary_includes_main_agent_recommendation() -> None:
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    study_space_id = uuid.uuid4()
    chapter_id = uuid.uuid4()

    class FakeSession:
        def __init__(self) -> None:
            self.calls = 0

        async def scalars(self, _statement):
            self.calls += 1
            if self.calls == 1:
                return FakeScalarRows(
                    [
                        StudySpace(
                            id=study_space_id,
                            tenant_id=tenant_id,
                            owner_user_id=user_id,
                            name="RAG Basics",
                            goal="Learn retrieval",
                            target_days=14,
                        )
                    ]
                )
            if self.calls == 5:
                return FakeScalarRows(
                    [
                        Chapter(
                            id=chapter_id,
                            tenant_id=tenant_id,
                            study_space_id=study_space_id,
                            title="Retrieval",
                            status=ChapterStatus.active,
                            order_index=1,
                        )
                    ]
                )
            return FakeScalarRows([])

    response = await get_dashboard_summary(
        session=FakeSession(),
        tenant_id=tenant_id,
        user_id=user_id,
    )

    assert response.today_recommendation is not None
    assert response.today_recommendation.agent_type == "main_agent"
    assert response.today_recommendation.action_url == f"/chapters/{chapter_id}"


@pytest.mark.anyio
async def test_dashboard_summary_includes_empty_state_recommendation() -> None:
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()

    class FakeSession:
        async def scalars(self, _statement):
            return FakeScalarRows([])

    response = await get_dashboard_summary(
        session=FakeSession(),
        tenant_id=tenant_id,
        user_id=user_id,
    )

    assert response.today_recommendation is not None
    assert response.today_recommendation.recommendation_type == "create_space"
    assert response.today_recommendation.action_url == "/spaces/new"


@pytest.mark.anyio
async def test_get_main_agent_recommendation_persists_completed_run() -> None:
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    study_space_id = uuid.uuid4()
    chapter_id = uuid.uuid4()
    fake_session = FakeCommitSession(
        [
            [
                StudySpace(
                    id=study_space_id,
                    tenant_id=tenant_id,
                    owner_user_id=user_id,
                    name="RAG Basics",
                    goal="Learn retrieval",
                    target_days=14,
                )
            ],
            [
                Chapter(
                    id=chapter_id,
                    tenant_id=tenant_id,
                    study_space_id=study_space_id,
                    title="Retrieval",
                    status=ChapterStatus.active,
                    order_index=1,
                )
            ],
            [],
            [],
            [],
        ]
    )

    recommendation = await get_main_agent_recommendation(
        session=fake_session,
        tenant_id=tenant_id,
        user_id=user_id,
        request=DashboardRecommendationRequest(available_minutes=30, intent="balanced"),
    )

    assert fake_session.committed is True
    assert len(fake_session.added) == 1
    run = fake_session.added[0]
    assert run.agent_type == AgentType.main_agent
    assert run.status == AgentRunStatus.completed
    assert run.model == "deterministic"
    assert run.input_payload["request"]["available_minutes"] == 30
    assert run.input_payload["signal_counts"]["chapters"] == 1
    assert run.output_payload["strategy_version"] == "main_agent_agenda_v2"
    assert recommendation.agent_run_id == run.id


@pytest.mark.anyio
async def test_get_main_agent_recommendation_uses_quiz_intent() -> None:
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    study_space_id = uuid.uuid4()
    chapter_id = uuid.uuid4()
    quiz_id = uuid.uuid4()
    fake_session = FakeCommitSession(
        [
            [
                StudySpace(
                    id=study_space_id,
                    tenant_id=tenant_id,
                    owner_user_id=user_id,
                    name="RAG Basics",
                    goal="Learn retrieval",
                    target_days=14,
                )
            ],
            [
                Chapter(
                    id=chapter_id,
                    tenant_id=tenant_id,
                    study_space_id=study_space_id,
                    title="Retrieval",
                    status=ChapterStatus.completed,
                    order_index=1,
                )
            ],
            [],
            [],
            [
                Quiz(
                    id=quiz_id,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    study_space_id=study_space_id,
                    chapter_id=chapter_id,
                    title="Retrieval quiz",
                    status=QuizStatus.active,
                )
            ],
        ]
    )

    recommendation = await get_main_agent_recommendation(
        session=fake_session,
        tenant_id=tenant_id,
        user_id=user_id,
        request=DashboardRecommendationRequest(available_minutes=15, intent="quiz"),
    )

    assert recommendation.recommendation_type == "quiz_chapter"
    assert recommendation.action_url == f"/quizzes/{quiz_id}"
    assert recommendation.chapter_id == chapter_id
