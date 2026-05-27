from app.db.models import ChapterMentorState


def test_chapter_mentor_state_model_has_expected_table_and_columns() -> None:
    assert ChapterMentorState.__tablename__ == "chapter_mentor_states"

    columns = ChapterMentorState.__table__.columns
    assert "tenant_id" in columns
    assert "study_space_id" in columns
    assert "chapter_id" in columns
    assert "summary" in columns
    assert "weak_points" in columns
    assert "next_actions" in columns
    assert "evidence" in columns
    assert "source_session_count" in columns
    assert "source_message_count" in columns
