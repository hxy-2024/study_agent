import pytest

from app.infrastructure.storage import S3TextSourceReader


class FakeBody:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def read(self) -> bytes:
        return self.payload


class FakeS3Client:
    def __init__(self, payload: bytes, content_type: str = "text/plain") -> None:
        self.payload = payload
        self.content_type = content_type
        self.calls = []

    def get_object(self, Bucket: str, Key: str):
        self.calls.append({"Bucket": Bucket, "Key": Key})
        return {
            "Body": FakeBody(self.payload),
            "ContentType": self.content_type,
            "ContentLength": len(self.payload),
        }


@pytest.mark.anyio
async def test_s3_text_source_reader_reads_utf8_text() -> None:
    client = FakeS3Client("hello learning".encode("utf-8"), content_type="text/markdown")
    reader = S3TextSourceReader(client=client, bucket="study-agent-local", max_bytes=1024)

    text = await reader.read_text("objects/intro.md")

    assert text == "hello learning"
    assert client.calls == [{"Bucket": "study-agent-local", "Key": "objects/intro.md"}]


@pytest.mark.anyio
async def test_s3_text_source_reader_rejects_large_object() -> None:
    client = FakeS3Client(b"abcdef", content_type="text/plain")
    reader = S3TextSourceReader(client=client, bucket="study-agent-local", max_bytes=3)

    with pytest.raises(ValueError) as exc_info:
        await reader.read_text("objects/too-large.txt")

    assert str(exc_info.value) == "Source object exceeds maximum text ingestion size"


@pytest.mark.anyio
async def test_s3_text_source_reader_rejects_binary_content_type() -> None:
    client = FakeS3Client(b"%PDF", content_type="application/pdf")
    reader = S3TextSourceReader(client=client, bucket="study-agent-local", max_bytes=1024)

    with pytest.raises(ValueError) as exc_info:
        await reader.read_text("objects/file.pdf")

    assert str(exc_info.value) == "Runtime text ingestion supports only text sources"
