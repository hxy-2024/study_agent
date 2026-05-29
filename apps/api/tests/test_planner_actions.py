import uuid

import pytest

from app.db.models import (
    AgentRun,
    AgentRunStatus,
    AgentType,
    Chapter,
    PlannerAction,
    PlannerActionStatus,
    PlannerActionType,
    Session,
    StudySpace,
)
from app.domain.planner_actions.service import (
    _runtime_action_kind,
    _runtime_action_rationale,
    _runtime_action_title,
    _runtime_signal_types,
    create_actions_from_runtime_signals,
)


def test_runtime_signal_types_maps_truthy_signals_and_missing_evidence() -> None:
    signal_types = _runtime_signal_types(
        {
            "learning_signals": [
                {"type": "confusion_detected", "value": True},
                {"type": "needs_review", "value": False},
                {"type": "evidence_used", "value": False},
                {"type": "ignored"},
                "not-a-dict",
            ]
        }
    )

    assert signal_types == ["confusion_detected", "evidence_missing"]


@pytest.mark.parametrize(
    ("signal_types", "kind"),
    [
        (["needs_review", "confusion_detected", "evidence_missing"], "review_confusion"),
        (["needs_review", "evidence_missing"], "review_chapter"),
        (["evidence_missing"], "strengthen_evidence"),
        (["other"], None),
    ],
)
def test_runtime_action_kind_uses_expected_priority(signal_types: list[str], kind: str | None) -> None:
    assert _runtime_action_kind(signal_types) == kind


def test_runtime_action_title_and_rationale_match_kind() -> None:
    assert _runtime_action_title("review_confusion", "Retrieval") == "Review confusion in Retrieval"
    assert _runtime_action_title("strengthen_evidence", "Retrieval") == "Strengthen evidence for Retrieval"
    assert _runtime_action_title("review_chapter", "Retrieval") == "Review Retrieval"
    assert "confusion" in _runtime_action_rationale(["confusion_detected"])
    assert "needs review" in _runtime_action_rationale(["needs_review"])
    assert "evidence" in _runtime_action_rationale(["evidence_missing"])


@pytest.mark.anyio
async def test_create_actions_from_runtime_signals_builds_new_runtime_actions() -> None:
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    study_space_id = uuid.uuid4()
    chapter_id = uuid.uuid4()
    session_id = uuid.uuid4()
    run_id = uuid.uuid4()
    chapter = Chapter(
        id=chapter_id,
        tenant_id=tenant_id,
        study_space_id=study_space_id,
        learning_route_id=uuid.uuid4(),
        order_index=1,
        title="Retrieval Practice",
        goal="Goal",
        summary="Summary",
        estimated_days=2,
    )
    runtime_session = Session(
        id=session_id,
        tenant_id=tenant_id,
        study_space_id=study_space_id,
        chapter_id=chapter_id,
        title="Tutor session",
    )
    agent_run = AgentRun(
        id=run_id,
        tenant_id=tenant_id,
        study_space_id=study_space_id,
        session_id=session_id,
        agent_type=AgentType.session_tutor,
        status=AgentRunStatus.completed,
        output_payload={"learning_signals": [{"type": "needs_review", "value": True}]},
    )
    added: list[PlannerAction] = []

    class FakeRows:
        def __init__(self, rows: list) -> None:
            self._rows = rows

        def all(self) -> list:
            return self._rows

    class FakeSession:
        def __init__(self) -> None:
            self.scalar_calls = 0
            self.execute_calls = 0
            self.committed = False

        async def scalar(self, _statement):
            self.scalar_calls += 1
            if self.scalar_calls == 1:
                return StudySpace(id=study_space_id, tenant_id=tenant_id, owner_user_id=user_id, name="Space", goal="Goal")
            return chapter

        async def execute(self, _statement):
            self.execute_calls += 1
            if self.execute_calls == 1:
                return FakeRows([(agent_run, runtime_session, chapter)])
            return FakeRows([])

        def add(self, obj: PlannerAction) -> None:
            added.append(obj)

        async def commit(self) -> None:
            self.committed = True

    response = await create_actions_from_runtime_signals(
        session=FakeSession(),
        tenant_id=tenant_id,
        user_id=user_id,
        study_space_id=study_space_id,
        chapter_id=chapter_id,
    )

    assert len(added) == 1
    assert added[0].action_type == PlannerActionType.review_chapter
    assert added[0].status == PlannerActionStatus.proposed
    assert added[0].payload == {
        "source": "runtime_signal",
        "action_kind": "review_chapter",
        "agent_run_id": str(run_id),
        "session_id": str(session_id),
        "signal_types": ["needs_review"],
    }
    assert response.actions[0].chapter_id == chapter_id


@pytest.mark.anyio
async def test_create_actions_from_runtime_signals_skips_duplicate_active_actions() -> None:
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    study_space_id = uuid.uuid4()
    chapter_id = uuid.uuid4()
    run_id = uuid.uuid4()
    session_id = uuid.uuid4()
    chapter = Chapter(
        id=chapter_id,
        tenant_id=tenant_id,
        study_space_id=study_space_id,
        learning_route_id=uuid.uuid4(),
        order_index=1,
        title="Evidence",
        goal="Goal",
        summary="Summary",
        estimated_days=2,
    )
    runtime_session = Session(
        id=session_id,
        tenant_id=tenant_id,
        study_space_id=study_space_id,
        chapter_id=chapter_id,
        title="Tutor session",
    )
    agent_run = AgentRun(
        id=run_id,
        tenant_id=tenant_id,
        study_space_id=study_space_id,
        session_id=session_id,
        agent_type=AgentType.session_tutor,
        status=AgentRunStatus.completed,
        output_payload={"learning_signals": [{"type": "evidence_used", "value": False}]},
    )
    duplicate = PlannerAction(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        user_id=user_id,
        study_space_id=study_space_id,
        chapter_id=chapter_id,
        action_type=PlannerActionType.review_chapter,
        status=PlannerActionStatus.proposed,
        title="Strengthen evidence",
        rationale="Missing evidence.",
        payload={
            "source": "runtime_signal",
            "action_kind": "strengthen_evidence",
            "agent_run_id": str(run_id),
        },
    )
    added: list[PlannerAction] = []

    class FakeRows:
        def __init__(self, rows: list) -> None:
            self._rows = rows

        def all(self) -> list:
            return self._rows

    class FakeSession:
        async def scalar(self, _statement):
            return StudySpace(id=study_space_id, tenant_id=tenant_id, owner_user_id=user_id, name="Space", goal="Goal")

        async def execute(self, _statement):
            if not hasattr(self, "called"):
                self.called = True
                return FakeRows([(agent_run, runtime_session, chapter)])
            return FakeRows([duplicate])

        def add(self, obj: PlannerAction) -> None:
            added.append(obj)

        async def commit(self) -> None:
            pass

    response = await create_actions_from_runtime_signals(
        session=FakeSession(),
        tenant_id=tenant_id,
        user_id=user_id,
        study_space_id=study_space_id,
    )

    assert added == []
    assert response.actions == []
