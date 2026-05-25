from app.db.models import IngestionJob, IngestionJobStatus, SourceChunk


def test_rag_models_are_importable() -> None:
    assert IngestionJob.__tablename__ == "ingestion_jobs"
    assert SourceChunk.__tablename__ == "source_chunks"
    assert IngestionJobStatus.pending.value == "pending"
