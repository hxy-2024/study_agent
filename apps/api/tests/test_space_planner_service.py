import uuid
from types import SimpleNamespace

import pytest

from app.db.models import AgentRun, AgentType, ChapterStatus, MasteryLevel, SpacePlannerState, StudySpace
from app.domain.space_planner.service import (
    build_evidence,
    build_review_recommendations,
    build_risk_chapters,
    build_route_adjustments,
    build_supervision_freshness,
    choose_next_chapter,
    generate_space_planner_state,
)


def make_chapter(title: str, status: ChapterStatus, order_index: int) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        title=title,
        status=status,
        order_index=order_index,
    )


def test_choose_next_chapter_prefers_active_low_mastery() -> None:
    chapter_a = make_chapter("Retrieval", ChapterStatus.active, 1)
    chapter_b = make_chapter("Generation", ChapterStatus.not_started, 2)
    mastery = {chapter_a.id: SimpleNamespace(score_percent=40, level=MasteryLevel.developing)}

    assert choose_next_chapter([chapter_b, chapter_a], mastery) == chapter_a.id


def test_choose_next_chapter_falls_back_to_first_not_completed() -> None:
    chapter_a = make_chapter("Retrieval", ChapterStatus.completed, 1)
    chapter_b = make_chapter("Generation", ChapterStatus.not_started, 2)

    assert choose_next_chapter([chapter_a, chapter_b], {}) == chapter_b.id


def test_risk_review_and_adjustment_builders_use_mastery_and_mentor_state() -> None:
    chapter = make_chapter("Citations", ChapterStatus.active, 1)
    mastery = {
        chapter.id: SimpleNamespace(score_percent=35, level=MasteryLevel.new, weak_points=["Missed citation support"])
    }
    mentor_states = {chapter.id: SimpleNamespace(weak_points=["Confused about grounding"])}

    risks = build_risk_chapters([chapter], mastery, mentor_states)
    reviews = build_review_recommendations([chapter], mastery, mentor_states)
    adjustments = build_route_adjustments([chapter], mastery)

    assert risks[0]["chapter_id"] == str(chapter.id)
    assert risks[0]["score_percent"] == 35
    assert reviews[0]["action"] == "Retake chapter quiz after evidence review."
    assert adjustments[0]["kind"] == "insert_review"


def test_build_evidence_counts_learning_signal_mentor_evidence() -> None:
    chapter = make_chapter("Citations", ChapterStatus.active, 1)
    mentor_states = {
        chapter.id: SimpleNamespace(
            weak_points=[],
            evidence=[
                {"kind": "learning_signal", "summary": "Confused by citations"},
                {"kind": "quiz_result", "summary": "Passed review"},
                {"kind": "learning_signal", "summary": "Needs examples"},
            ],
        )
    }

    evidence = build_evidence([chapter], {}, mentor_states)

    assert evidence[0]["mentor_signal_count"] == 2


def test_build_supervision_freshness_marks_newer_tutor_signal_as_stale() -> None:
    chapter = make_chapter("Citations", ChapterStatus.active, 1)
    mentor_states = {
        chapter.id: SimpleNamespace(updated_at="2026-05-29T08:00:00+00:00"),
    }
    latest_tutor_runs = {
        chapter.id: "2026-05-29T08:05:00+00:00",
    }

    freshness = build_supervision_freshness([chapter], mentor_states, latest_tutor_runs)

    assert freshness[chapter.id]["mentor_state_updated_at"] == "2026-05-29T08:00:00+00:00"
    assert freshness[chapter.id]["latest_session_tutor_run_at"] == "2026-05-29T08:05:00+00:00"
    assert freshness[chapter.id]["needs_supervision_refresh"] is True


def test_build_evidence_and_recommendations_surface_stale_supervision() -> None:
    chapter = make_chapter("Citations", ChapterStatus.active, 1)
    freshness = {
        chapter.id: {
            "mentor_state_updated_at": "2026-05-29T08:00:00+00:00",
            "latest_session_tutor_run_at": "2026-05-29T08:05:00+00:00",
            "needs_supervision_refresh": True,
        }
    }

    evidence = build_evidence([chapter], {}, {}, freshness)
    risks = build_risk_chapters([chapter], {}, {}, freshness)
    reviews = build_review_recommendations([chapter], {}, {}, freshness)

    assert evidence[0]["needs_supervision_refresh"] is True
    assert risks[0]["reason"] == "New tutor signals need chapter mentor assessment."
    assert reviews[0]["action"] == "Refresh chapter mentor assessment from recent tutor signals."


def test_signal_evidence_creates_risk_and_review_without_low_mastery() -> None:
    chapter = make_chapter("Citations", ChapterStatus.active, 1)
    mastery = {chapter.id: SimpleNamespace(score_percent=85, level=MasteryLevel.proficient, weak_points=[])}
    mentor_states = {
        chapter.id: SimpleNamespace(
            weak_points=[],
            evidence=[{"kind": "learning_signal", "summary": "Confused by citations"}],
        )
    }

    risks = build_risk_chapters([chapter], mastery, mentor_states)
    reviews = build_review_recommendations([chapter], mastery, mentor_states)

    assert risks == [
        {
            "chapter_id": str(chapter.id),
            "title": "Citations",
            "reason": "Recent tutor signals indicate this chapter needs attention.",
            "score_percent": 85,
        }
    ]
    assert reviews == [
        {
            "chapter_id": str(chapter.id),
            "title": "Citations",
            "action": "Review recent tutor confusion signals with the chapter mentor.",
            "reason": "Recent tutor signals indicate this chapter needs attention.",
        }
    ]


def test_low_mastery_reason_and_action_take_priority_over_signal_evidence() -> None:
    chapter = make_chapter("Citations", ChapterStatus.active, 1)
    mastery = {chapter.id: SimpleNamespace(score_percent=35, level=MasteryLevel.new, weak_points=[])}
    mentor_states = {
        chapter.id: SimpleNamespace(
            weak_points=[],
            evidence=[{"kind": "learning_signal", "summary": "Confused by citations"}],
        )
    }

    risks = build_risk_chapters([chapter], mastery, mentor_states)
    reviews = build_review_recommendations([chapter], mastery, mentor_states)

    assert risks[0]["reason"] == "Mastery score is 35%, below the review threshold."
    assert reviews[0]["action"] == "Retake chapter quiz after evidence review."


def test_malformed_mentor_evidence_is_ignored_for_signal_count_risks_and_reviews() -> None:
    chapters = [
        make_chapter("Non-list evidence", ChapterStatus.active, 1),
        make_chapter("Non-dict evidence", ChapterStatus.active, 2),
        make_chapter("Missing kind evidence", ChapterStatus.active, 3),
    ]
    mentor_states = {
        chapters[0].id: SimpleNamespace(weak_points=[], evidence={"kind": "learning_signal"}),
        chapters[1].id: SimpleNamespace(weak_points=[], evidence=["learning_signal"]),
        chapters[2].id: SimpleNamespace(weak_points=[], evidence=[{"summary": "Missing kind"}]),
    }

    evidence = build_evidence(chapters, {}, mentor_states)

    assert [item["mentor_signal_count"] for item in evidence] == [0, 0, 0]
    assert build_risk_chapters(chapters, {}, mentor_states) == []
    assert build_review_recommendations(chapters, {}, mentor_states) == []


@pytest.mark.anyio
async def test_generate_space_planner_state_upserts_state_and_agent_run(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    study_space_id = uuid.uuid4()
    chapter_id = uuid.uuid4()
    added = []

    study_space = StudySpace(
        id=study_space_id,
        tenant_id=tenant_id,
        owner_user_id=user_id,
        name="AI Study",
        goal="Learn RAG",
    )
    chapter = SimpleNamespace(id=chapter_id, title="Retrieval", status=ChapterStatus.active, order_index=1)
    mastery = {chapter_id: SimpleNamespace(score_percent=50, level=MasteryLevel.developing, weak_points=["Citations"])}
    mentor = {chapter_id: SimpleNamespace(weak_points=["Needs better grounding"])}

    class FakeSession:
        async def scalar(self, _statement):
            return None

        def add(self, obj) -> None:
            added.append(obj)

        async def commit(self) -> None:
            pass

        async def refresh(self, obj) -> None:
            if obj.updated_at is None:
                obj.updated_at = None

    async def fake_snapshot(**kwargs):
        return study_space, [chapter], mastery, mentor

    async def fake_latest_tutor_runs(**kwargs):
        return {}

    monkeypatch.setattr("app.domain.space_planner.service.build_space_planner_snapshot", fake_snapshot)
    monkeypatch.setattr("app.domain.space_planner.service.load_latest_session_tutor_run_times", fake_latest_tutor_runs)

    response = await generate_space_planner_state(
        session=FakeSession(),
        tenant_id=tenant_id,
        user_id=user_id,
        study_space_id=study_space_id,
    )

    states = [obj for obj in added if isinstance(obj, SpacePlannerState)]
    agent_runs = [obj for obj in added if isinstance(obj, AgentRun)]

    assert len(states) == 1
    assert states[0].tenant_id == tenant_id
    assert states[0].user_id == user_id
    assert states[0].next_chapter_id == chapter_id
    assert states[0].risk_chapters[0]["chapter_id"] == str(chapter_id)
    assert len(agent_runs) == 1
    assert agent_runs[0].agent_type == AgentType.space_planner
    assert response.next_chapter_id == chapter_id
