import uuid

import pytest

from app.db.models import PlannerAction, PlannerActionStatus, PlannerActionType, Session, SpacePlannerState, StudySpace
from app.domain.planner_actions.service import (
    build_actions_from_planner_state,
    create_actions_from_latest_planner_state,
    list_planner_actions,
    planner_action_response,
    start_review_for_planner_action,
    update_planner_action_status,
)


def test_build_actions_from_planner_state_maps_reviews_and_route_proposals() -> None:
    chapter_id = uuid.uuid4()
    state = SpacePlannerState(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        study_space_id=uuid.uuid4(),
        summary="Plan",
        risk_chapters=[],
        review_recommendations=[
            {
                "chapter_id": str(chapter_id),
                "title": "Retrieval",
                "action": "Retake chapter quiz after evidence review.",
                "reason": "Current mastery is 52%.",
            }
        ],
        route_adjustments=[
            {
                "kind": "insert_review",
                "chapter_id": str(chapter_id),
                "title": "Review before continuing: Retrieval",
                "rationale": "Low mastery suggests review.",
            }
        ],
        evidence=[],
    )

    actions = build_actions_from_planner_state(state)

    assert len(actions) == 2
    assert actions[0].action_type == PlannerActionType.review_chapter
    assert actions[0].chapter_id == chapter_id
    assert actions[0].status == PlannerActionStatus.proposed
    assert actions[1].action_type == PlannerActionType.route_adjustment


@pytest.mark.anyio
async def test_create_actions_from_latest_planner_state_writes_actions() -> None:
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    study_space_id = uuid.uuid4()
    chapter_id = uuid.uuid4()
    state = SpacePlannerState(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        user_id=user_id,
        study_space_id=study_space_id,
        summary="Plan",
        risk_chapters=[],
        review_recommendations=[
            {
                "chapter_id": str(chapter_id),
                "title": "Retrieval",
                "action": "Review Retrieval",
                "reason": "Weak citations.",
            }
        ],
        route_adjustments=[],
        evidence=[],
    )
    added = []

    class FakeSession:
        def __init__(self) -> None:
            self.scalar_calls = 0
            self.committed = False

        async def scalar(self, _statement):
            self.scalar_calls += 1
            if self.scalar_calls == 1:
                return StudySpace(id=study_space_id, tenant_id=tenant_id, owner_user_id=user_id, name="Space", goal="Goal")
            return state

        def add(self, obj) -> None:
            added.append(obj)

        async def commit(self) -> None:
            self.committed = True

    session = FakeSession()

    response = await create_actions_from_latest_planner_state(
        session=session,
        tenant_id=tenant_id,
        user_id=user_id,
        study_space_id=study_space_id,
    )

    assert session.committed is True
    assert len(added) == 1
    assert isinstance(added[0], PlannerAction)
    assert response.actions[0].title == "Review Retrieval"


@pytest.mark.anyio
async def test_list_planner_actions_filters_by_user_space() -> None:
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    study_space_id = uuid.uuid4()
    action = PlannerAction(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        user_id=user_id,
        study_space_id=study_space_id,
        action_type=PlannerActionType.review_chapter,
        status=PlannerActionStatus.proposed,
        title="Review",
        rationale="Reason",
        payload={},
    )

    class FakeSession:
        async def scalar(self, _statement):
            return StudySpace(id=study_space_id, tenant_id=tenant_id, owner_user_id=user_id, name="Space", goal="Goal")

        async def scalars(self, _statement):
            return [action]

    response = await list_planner_actions(
        session=FakeSession(),
        tenant_id=tenant_id,
        user_id=user_id,
        study_space_id=study_space_id,
    )

    assert response.actions[0].id == action.id


@pytest.mark.anyio
async def test_update_planner_action_status_rejects_invalid_transition() -> None:
    action = PlannerAction(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        study_space_id=uuid.uuid4(),
        action_type=PlannerActionType.review_chapter,
        status=PlannerActionStatus.dismissed,
        title="Review",
        rationale="Reason",
        payload={},
    )

    class FakeSession:
        async def scalar(self, _statement):
            return action

    with pytest.raises(ValueError, match="Cannot update dismissed planner action"):
        await update_planner_action_status(
            session=FakeSession(),
            tenant_id=action.tenant_id,
            user_id=action.user_id,
            action_id=action.id,
            status=PlannerActionStatus.completed.value,
        )


@pytest.mark.anyio
async def test_update_planner_action_status_accepts_proposed_action() -> None:
    action = PlannerAction(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        study_space_id=uuid.uuid4(),
        action_type=PlannerActionType.review_chapter,
        status=PlannerActionStatus.proposed,
        title="Review",
        rationale="Reason",
        payload={},
    )

    class FakeSession:
        async def scalar(self, _statement):
            return action

        async def commit(self) -> None:
            pass

        async def refresh(self, _action) -> None:
            pass

    response = await update_planner_action_status(
        session=FakeSession(),
        tenant_id=action.tenant_id,
        user_id=action.user_id,
        action_id=action.id,
        status=PlannerActionStatus.accepted.value,
    )

    assert response.status == "accepted"


def test_planner_action_response_uses_enum_values() -> None:
    action = PlannerAction(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        study_space_id=uuid.uuid4(),
        action_type=PlannerActionType.review_chapter,
        status=PlannerActionStatus.accepted,
        title="Review Retrieval",
        rationale="Low mastery.",
        payload={"score": 52},
    )

    response = planner_action_response(action)

    assert response.action_type == "review_chapter"
    assert response.status == "accepted"
    assert response.payload == {"score": 52}


@pytest.mark.anyio
async def test_start_review_for_planner_action_creates_session_and_accepts_action() -> None:
    action = PlannerAction(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        study_space_id=uuid.uuid4(),
        chapter_id=uuid.uuid4(),
        action_type=PlannerActionType.review_chapter,
        status=PlannerActionStatus.proposed,
        title="Review Retrieval",
        rationale="Recent tutor signals need review.",
        payload={"source": "runtime_signal"},
    )
    added = []

    class FakeSession:
        async def scalar(self, _statement):
            return action

        def add(self, obj) -> None:
            added.append(obj)

        async def flush(self) -> None:
            for obj in added:
                if isinstance(obj, Session) and obj.id is None:
                    obj.id = uuid.uuid4()

        async def commit(self) -> None:
            pass

        async def refresh(self, obj) -> None:
            if obj.id is None:
                obj.id = uuid.uuid4()

    response = await start_review_for_planner_action(
        session=FakeSession(),
        tenant_id=action.tenant_id,
        user_id=action.user_id,
        action_id=action.id,
    )

    review_session = next(obj for obj in added if isinstance(obj, Session))
    assert review_session.chapter_id == action.chapter_id
    assert review_session.title == "Review: Review Retrieval"
    assert action.status == PlannerActionStatus.accepted
    assert action.payload["execution"]["review_session_id"] == str(review_session.id)
    assert response.session.id == review_session.id
    assert response.action.status == "accepted"


@pytest.mark.anyio
async def test_start_review_for_planner_action_reuses_existing_review_session() -> None:
    review_session = Session(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        study_space_id=uuid.uuid4(),
        chapter_id=uuid.uuid4(),
        title="Review: Retrieval",
    )
    action = PlannerAction(
        id=uuid.uuid4(),
        tenant_id=review_session.tenant_id,
        user_id=uuid.uuid4(),
        study_space_id=review_session.study_space_id,
        chapter_id=review_session.chapter_id,
        action_type=PlannerActionType.review_chapter,
        status=PlannerActionStatus.accepted,
        title="Review Retrieval",
        rationale="Recent tutor signals need review.",
        payload={"execution": {"review_session_id": str(review_session.id)}},
    )
    added = []

    class FakeSession:
        def __init__(self) -> None:
            self.scalar_calls = 0

        async def scalar(self, _statement):
            self.scalar_calls += 1
            return action if self.scalar_calls == 1 else review_session

        def add(self, obj) -> None:
            added.append(obj)

        async def commit(self) -> None:
            pass

        async def refresh(self, _obj) -> None:
            pass

    response = await start_review_for_planner_action(
        session=FakeSession(),
        tenant_id=action.tenant_id,
        user_id=action.user_id,
        action_id=action.id,
    )

    assert added == []
    assert response.session.id == review_session.id
    assert response.action.payload["execution"]["review_session_id"] == str(review_session.id)
