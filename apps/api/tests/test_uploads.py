import uuid
from types import SimpleNamespace

import pytest

from app.domain.sources.schemas import UploadPresignRequest
from app.domain.sources.service import (
    build_object_key,
    create_upload_request,
    ensure_study_space_in_tenant,
    validate_content_type,
)


def test_build_object_key_is_tenant_and_space_scoped() -> None:
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    space_id = uuid.UUID("00000000-0000-0000-0000-000000000002")

    object_key = build_object_key(tenant_id, space_id, "algebra notes.pdf")

    assert object_key.startswith("tenants/00000000-0000-0000-0000-000000000001/")
    assert "/spaces/00000000-0000-0000-0000-000000000002/sources/" in object_key
    assert object_key.endswith("/algebra-notes.pdf")


def test_validate_content_type_accepts_supported_types() -> None:
    validate_content_type("application/pdf")
    validate_content_type("image/png")
    validate_content_type("text/markdown")


def test_validate_content_type_rejects_unsupported_types() -> None:
    with pytest.raises(ValueError, match="Unsupported content type"):
        validate_content_type("application/x-msdownload")


async def test_ensure_study_space_in_tenant_accepts_matching_space() -> None:
    study_space = SimpleNamespace(id=uuid.uuid4())

    class FakeSession:
        async def scalar(self, statement):
            self.statement = statement
            return study_space

    session = FakeSession()

    result = await ensure_study_space_in_tenant(
        session,
        study_space_id=study_space.id,
        tenant_id=uuid.uuid4(),
    )

    assert result is study_space
    assert session.statement is not None


async def test_ensure_study_space_in_tenant_rejects_missing_space() -> None:
    class FakeSession:
        async def scalar(self, statement):
            return None

    with pytest.raises(ValueError, match="Study space not found for tenant"):
        await ensure_study_space_in_tenant(
            FakeSession(),
            study_space_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
        )


async def test_create_upload_request_uses_explicit_tenant_id(monkeypatch) -> None:
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    study_space_id = uuid.UUID("00000000-0000-0000-0000-000000000002")
    payload = UploadPresignRequest(
        study_space_id=study_space_id,
        filename="algebra notes.pdf",
        content_type="application/pdf",
    )

    class FakeSession:
        def add(self, source):
            self.source = source

        async def commit(self):
            self.committed = True

        async def refresh(self, source):
            source.id = uuid.uuid4()

        async def scalar(self, statement):
            return SimpleNamespace(id=study_space_id)

    session = FakeSession()
    class FakeSettings:
        storage_backend = "s3"
        api_public_url = "http://127.0.0.1:8000"
        api_v1_prefix = "/api/v1"

    monkeypatch.setattr("app.domain.sources.service.get_settings", lambda: FakeSettings())
    monkeypatch.setattr(
        "app.domain.sources.service.create_presigned_put_url",
        lambda *, object_key, content_type: f"https://storage.example/{object_key}",
    )

    source, upload_url = await create_upload_request(session, payload, tenant_id=tenant_id)

    assert source is session.source
    assert source.tenant_id == tenant_id
    assert source.study_space_id == study_space_id
    assert source.object_key.startswith(f"tenants/{tenant_id}/spaces/{study_space_id}/sources/")
    assert source.object_key.endswith("/algebra-notes.pdf")
    assert upload_url == f"https://storage.example/{source.object_key}"


async def test_create_upload_request_returns_local_upload_path_for_filesystem(
    monkeypatch,
) -> None:
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    study_space_id = uuid.UUID("00000000-0000-0000-0000-000000000002")
    source_id = uuid.UUID("00000000-0000-0000-0000-000000000003")
    payload = UploadPresignRequest(
        study_space_id=study_space_id,
        filename="notes.md",
        content_type="text/markdown",
    )

    class FakeSettings:
        storage_backend = "filesystem"
        api_public_url = "http://127.0.0.1:8000"
        api_v1_prefix = "/api/v1"

    class FakeSession:
        def add(self, source):
            self.source = source

        async def commit(self):
            self.committed = True

        async def refresh(self, source):
            source.id = source_id

        async def scalar(self, statement):
            return SimpleNamespace(id=study_space_id)

    def fail_s3_presign(*, object_key, content_type):
        raise AssertionError("filesystem upload requests must not create S3 presigned URLs")

    monkeypatch.setattr("app.domain.sources.service.get_settings", lambda: FakeSettings())
    monkeypatch.setattr("app.domain.sources.service.create_presigned_put_url", fail_s3_presign)

    source, upload_url = await create_upload_request(
        FakeSession(),
        payload,
        tenant_id=tenant_id,
    )

    assert source.id == source_id
    assert upload_url == f"http://127.0.0.1:8000/api/v1/uploads/local/{source_id}"
