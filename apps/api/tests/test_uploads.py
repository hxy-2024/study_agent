import uuid

import pytest

from app.domain.sources.service import build_object_key, validate_content_type


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
