import pytest

from app.core.config import get_settings
from app.infrastructure.storage import (
    FilesystemTextSourceReader,
    FilesystemTextSourceWriter,
    create_runtime_text_source_reader,
    create_runtime_text_source_writer,
    write_runtime_upload_object,
)


@pytest.mark.anyio
async def test_filesystem_writer_and_reader_round_trip(tmp_path) -> None:
    writer = FilesystemTextSourceWriter(root=tmp_path, max_bytes=1024)
    reader = FilesystemTextSourceReader(root=tmp_path, max_bytes=1024)

    await writer.write_text("tenant/source.md", "# Local source", "text/markdown")
    result = await reader.read_text("tenant/source.md")

    assert result == "# Local source"
    assert result.text == "# Local source"
    assert result.content_type == "text/markdown"


@pytest.mark.anyio
async def test_filesystem_writer_rejects_path_traversal(tmp_path) -> None:
    writer = FilesystemTextSourceWriter(root=tmp_path, max_bytes=1024)

    with pytest.raises(ValueError, match="Invalid storage object key"):
        await writer.write_text("../source.md", "# Local source", "text/markdown")


def test_runtime_factories_select_filesystem_storage(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("RUNTIME_PROFILE", "local")
    monkeypatch.setenv("STORAGE_BACKEND", "filesystem")
    monkeypatch.setenv("LOCAL_STORAGE_ROOT", str(tmp_path))
    get_settings.cache_clear()
    try:
        reader = create_runtime_text_source_reader()
        writer = create_runtime_text_source_writer()
    finally:
        get_settings.cache_clear()

    assert isinstance(reader, FilesystemTextSourceReader)
    assert isinstance(writer, FilesystemTextSourceWriter)


@pytest.mark.anyio
async def test_runtime_upload_object_writes_payload_to_filesystem(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("RUNTIME_PROFILE", "local")
    monkeypatch.setenv("STORAGE_BACKEND", "filesystem")
    monkeypatch.setenv("LOCAL_STORAGE_ROOT", str(tmp_path))
    get_settings.cache_clear()
    try:
        await write_runtime_upload_object(
            object_key="tenants/local/spaces/demo/sources/source-id/notes.md",
            payload=b"# Uploaded locally",
            content_type="text/markdown",
        )
    finally:
        get_settings.cache_clear()

    stored = tmp_path / "tenants/local/spaces/demo/sources/source-id/notes.md"
    assert stored.read_bytes() == b"# Uploaded locally"
