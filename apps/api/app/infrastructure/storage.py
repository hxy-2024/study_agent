from abc import ABC, abstractmethod
import asyncio
import json
from pathlib import Path
from typing import NamedTuple
from typing import Protocol

import boto3

from app.core.config import get_settings

TEXT_CONTENT_TYPES = {"text/plain", "text/markdown"}


class TextSourceReader(ABC):
    @abstractmethod
    async def read_text(self, object_key: str) -> str:
        raise NotImplementedError


class TextSourceWriter(ABC):
    @abstractmethod
    async def write_text(self, object_key: str, content: str, content_type: str) -> None:
        raise NotImplementedError


class TextSourceReadResult(str):
    def __new__(cls, text: str, content_type: str) -> "TextSourceReadResult":
        instance = str.__new__(cls, text)
        instance.text = text
        instance.content_type = content_type
        return instance


class _FilesystemObjectPaths(NamedTuple):
    content: Path
    metadata: Path


class S3ClientProtocol(Protocol):
    def get_object(self, Bucket: str, Key: str):
        ...

    def put_object(self, Bucket: str, Key: str, Body: bytes, ContentType: str):
        ...


class S3TextSourceReader(TextSourceReader):
    def __init__(self, client: S3ClientProtocol, bucket: str, max_bytes: int) -> None:
        self._client = client
        self._bucket = bucket
        self._max_bytes = max_bytes

    async def read_text(self, object_key: str) -> str:
        return await asyncio.to_thread(self._read_text_sync, object_key)

    def _read_text_sync(self, object_key: str) -> str:
        response = self._client.get_object(Bucket=self._bucket, Key=object_key)
        content_type = response.get("ContentType", "").split(";")[0].strip().lower()
        if content_type not in TEXT_CONTENT_TYPES:
            raise ValueError("Runtime text ingestion supports only text sources")
        content_length = int(response.get("ContentLength") or 0)
        if content_length > self._max_bytes:
            raise ValueError("Source object exceeds maximum text ingestion size")
        payload = response["Body"].read()
        if len(payload) > self._max_bytes:
            raise ValueError("Source object exceeds maximum text ingestion size")
        return payload.decode("utf-8")


class S3TextSourceWriter(TextSourceWriter):
    def __init__(self, client: S3ClientProtocol, bucket: str, max_bytes: int) -> None:
        self._client = client
        self._bucket = bucket
        self._max_bytes = max_bytes

    async def write_text(self, object_key: str, content: str, content_type: str) -> None:
        await asyncio.to_thread(self._write_text_sync, object_key, content, content_type)

    def _write_text_sync(self, object_key: str, content: str, content_type: str) -> None:
        normalized_content_type = content_type.split(";")[0].strip().lower()
        if normalized_content_type not in TEXT_CONTENT_TYPES:
            raise ValueError("Runtime text storage supports only text sources")
        payload = content.encode("utf-8")
        if len(payload) > self._max_bytes:
            raise ValueError("Source object exceeds maximum text ingestion size")
        self._client.put_object(
            Bucket=self._bucket,
            Key=object_key,
            Body=payload,
            ContentType=normalized_content_type,
        )


class FilesystemTextSourceReader(TextSourceReader):
    def __init__(self, root: str | Path, max_bytes: int) -> None:
        self._root = Path(root)
        self._max_bytes = max_bytes

    async def read_text(self, object_key: str) -> TextSourceReadResult:
        return await asyncio.to_thread(self._read_text_sync, object_key)

    def _read_text_sync(self, object_key: str) -> TextSourceReadResult:
        paths = _filesystem_object_paths(self._root, object_key)
        metadata = _read_filesystem_metadata(paths.metadata)
        content_type = metadata["content_type"]
        if content_type not in TEXT_CONTENT_TYPES:
            raise ValueError("Runtime text ingestion supports only text sources")

        content_length = paths.content.stat().st_size
        if content_length > self._max_bytes:
            raise ValueError("Source object exceeds maximum text ingestion size")

        payload = paths.content.read_bytes()
        if len(payload) > self._max_bytes:
            raise ValueError("Source object exceeds maximum text ingestion size")
        text = payload.decode("utf-8")
        return TextSourceReadResult(text=text, content_type=content_type)


class FilesystemTextSourceWriter(TextSourceWriter):
    def __init__(self, root: str | Path, max_bytes: int) -> None:
        self._root = Path(root)
        self._max_bytes = max_bytes

    async def write_text(self, object_key: str, content: str, content_type: str) -> None:
        await asyncio.to_thread(self._write_text_sync, object_key, content, content_type)

    def _write_text_sync(self, object_key: str, content: str, content_type: str) -> None:
        normalized_content_type = content_type.split(";")[0].strip().lower()
        if normalized_content_type not in TEXT_CONTENT_TYPES:
            raise ValueError("Runtime text storage supports only text sources")

        payload = content.encode("utf-8")
        if len(payload) > self._max_bytes:
            raise ValueError("Source object exceeds maximum text ingestion size")

        paths = _filesystem_object_paths(self._root, object_key)
        paths.content.parent.mkdir(parents=True, exist_ok=True)
        paths.content.write_bytes(payload)
        paths.metadata.write_text(
            json.dumps({"content_type": normalized_content_type}),
            encoding="utf-8",
        )


async def write_runtime_upload_object(
    object_key: str,
    payload: bytes,
    content_type: str,
) -> None:
    settings = get_settings()
    if settings.storage_backend != "filesystem":
        raise ValueError("Runtime upload object writes require filesystem storage")
    await asyncio.to_thread(
        _write_filesystem_object_sync,
        Path(settings.local_storage_root),
        settings.storage_text_max_bytes,
        object_key,
        payload,
        content_type,
    )


def _write_filesystem_object_sync(
    root: Path,
    max_bytes: int,
    object_key: str,
    payload: bytes,
    content_type: str,
) -> None:
    normalized_content_type = content_type.split(";")[0].strip().lower()
    if not normalized_content_type:
        raise ValueError("Upload content type is required")
    if len(payload) > max_bytes:
        raise ValueError("Source object exceeds maximum text ingestion size")

    paths = _filesystem_object_paths(root, object_key)
    paths.content.parent.mkdir(parents=True, exist_ok=True)
    paths.content.write_bytes(payload)
    paths.metadata.write_text(
        json.dumps({"content_type": normalized_content_type}),
        encoding="utf-8",
    )


def _filesystem_object_paths(root: Path, object_key: str) -> _FilesystemObjectPaths:
    content = _safe_filesystem_path(root, object_key)
    return _FilesystemObjectPaths(
        content=content,
        metadata=content.with_name(f"{content.name}.metadata.json"),
    )


def _safe_filesystem_path(root: Path, object_key: str) -> Path:
    if not object_key or object_key.startswith(("/", "\\")):
        raise ValueError("Invalid storage object key")
    key_path = Path(object_key)
    if key_path.is_absolute() or any(part in {"..", ""} for part in key_path.parts):
        raise ValueError("Invalid storage object key")

    resolved_root = root.resolve()
    resolved_path = (resolved_root / key_path).resolve()
    if resolved_path != resolved_root and resolved_root not in resolved_path.parents:
        raise ValueError("Invalid storage object key")
    return resolved_path


def _read_filesystem_metadata(metadata_path: Path) -> dict[str, str]:
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    content_type = str(metadata.get("content_type", "")).split(";")[0].strip().lower()
    return {"content_type": content_type}


def create_s3_client() -> S3ClientProtocol:
    settings = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key_id,
        aws_secret_access_key=settings.s3_secret_access_key,
    )


def create_runtime_text_source_reader() -> TextSourceReader:
    settings = get_settings()
    if settings.storage_backend == "filesystem":
        return FilesystemTextSourceReader(
            root=settings.local_storage_root,
            max_bytes=settings.storage_text_max_bytes,
        )
    client = create_s3_client()
    return S3TextSourceReader(
        client=client,
        bucket=settings.s3_bucket,
        max_bytes=settings.storage_text_max_bytes,
    )


def create_runtime_text_source_writer() -> TextSourceWriter:
    settings = get_settings()
    if settings.storage_backend == "filesystem":
        return FilesystemTextSourceWriter(
            root=settings.local_storage_root,
            max_bytes=settings.storage_text_max_bytes,
        )
    client = create_s3_client()
    return S3TextSourceWriter(
        client=client,
        bucket=settings.s3_bucket,
        max_bytes=settings.storage_text_max_bytes,
    )


def create_presigned_put_url(object_key: str, content_type: str) -> str:
    settings = get_settings()
    client = create_s3_client()
    return client.generate_presigned_url(
        ClientMethod="put_object",
        Params={
            "Bucket": settings.s3_bucket,
            "Key": object_key,
            "ContentType": content_type,
        },
        ExpiresIn=900,
    )
