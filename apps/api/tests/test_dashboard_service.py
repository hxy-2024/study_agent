import uuid

import pytest

from app.db.models import AgentRun, AgentRunStatus, AgentType, PlannerAction, PlannerActionStatus, PlannerActionType, SpacePlannerState, StudySpace
from app.domain.dashboard.service import get_dashboard_summary


class FakeScalarRows:
    def __init__(self, rows) -> None:
        self._rows = rows

    def __iter__(self):
        return iter(self._rows)


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
    ]

    class FakeSession:
        def __init__(self) -> None:
            self.calls = 0

        async def scalars(self, _statement):
            captured[f"query_{self.calls}"] = str(_statement.compile(compile_kwargs={"literal_binds": True}))
            result = rows[self.calls]
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
    assert response.pending_actions[0].title == "Review retrieval"
    assert response.supervision_refresh_count == 1
    assert response.recent_agent_runs[0].summary == "Tutor answered with citations."
