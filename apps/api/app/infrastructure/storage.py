from abc import ABC, abstractmethod
import asyncio
from typing import Protocol

import boto3

from app.core.config import get_settings

TEXT_CONTENT_TYPES = {"text/plain", "text/markdown"}


class TextSourceReader(ABC):
    @abstractmethod
    async def read_text(self, object_key: str) -> str:
        raise NotImplementedError


class S3ClientProtocol(Protocol):
    def get_object(self, Bucket: str, Key: str):
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


def create_runtime_text_source_reader() -> S3TextSourceReader:
    settings = get_settings()
    client = boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key_id,
        aws_secret_access_key=settings.s3_secret_access_key,
    )
    return S3TextSourceReader(
        client=client,
        bucket=settings.s3_bucket,
        max_bytes=settings.storage_text_max_bytes,
    )


def create_presigned_put_url(object_key: str, content_type: str) -> str:
    settings = get_settings()
    client = boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key_id,
        aws_secret_access_key=settings.s3_secret_access_key,
    )
    return client.generate_presigned_url(
        ClientMethod="put_object",
        Params={
            "Bucket": settings.s3_bucket,
            "Key": object_key,
            "ContentType": content_type,
        },
        ExpiresIn=900,
    )
