from dataclasses import dataclass


@dataclass(frozen=True)
class ExtractedPage:
    page_number: int
    text: str


@dataclass(frozen=True)
class ExtractedDocument:
    source_id: str
    filename: str
    pages: list[ExtractedPage]


@dataclass(frozen=True)
class ChunkCitation:
    source_id: str
    filename: str
    page_start: int
    page_end: int

    def __getitem__(self, key: str) -> str | int:
        return self.to_dict()[key]

    def to_dict(self) -> dict[str, str | int]:
        return {
            "source_id": self.source_id,
            "filename": self.filename,
            "page_start": self.page_start,
            "page_end": self.page_end,
        }


@dataclass(frozen=True)
class ChunkPayload:
    source_id: str
    text: str
    chunk_index: int
    token_count: int
    citation: ChunkCitation

    def to_source_chunk_payload(self) -> dict[str, object]:
        return {
            "chunk_index": self.chunk_index,
            "text": self.text,
            "token_count": self.token_count,
            "citation": self.citation.to_dict(),
        }


@dataclass(frozen=True)
class _PageRange:
    page_number: int
    start: int
    end: int


def estimate_token_count(text: str) -> int:
    words = text.split()
    if not words:
        return 0
    return max(1, int(len(words) * 1.3))


def normalize_text(text: str) -> str:
    lines = [" ".join(line.split()) for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def chunk_document(
    document: ExtractedDocument,
    max_chars: int,
    overlap_chars: int,
) -> list[ChunkPayload]:
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    if overlap_chars < 0 or overlap_chars >= max_chars:
        raise ValueError("overlap_chars must be non-negative and less than max_chars")

    flattened, page_ranges = _flatten_pages(document.pages)
    chunks: list[ChunkPayload] = []
    start = 0

    while start < len(flattened):
        end = _chunk_end(flattened, start, max_chars)
        chunk_text = flattened[start:end].strip()

        if chunk_text:
            page_start, page_end = _page_span(page_ranges, start, end)
            chunks.append(
                ChunkPayload(
                    source_id=document.source_id,
                    text=chunk_text,
                    chunk_index=len(chunks),
                    token_count=estimate_token_count(chunk_text),
                    citation=ChunkCitation(
                        source_id=document.source_id,
                        filename=document.filename,
                        page_start=page_start,
                        page_end=page_end,
                    ),
                )
            )

        if end >= len(flattened):
            break

        next_start = end - overlap_chars
        if next_start <= start:
            next_start = end
        start = next_start

    return chunks


def _flatten_pages(pages: list[ExtractedPage]) -> tuple[str, list[_PageRange]]:
    parts: list[str] = []
    page_ranges: list[_PageRange] = []
    offset = 0

    for page in pages:
        if parts:
            parts.append("\n\n")
            offset += 2

        text = normalize_text(page.text)
        start = offset
        parts.append(text)
        offset += len(text)
        page_ranges.append(_PageRange(page_number=page.page_number, start=start, end=offset))

    return "".join(parts), page_ranges


def _chunk_end(text: str, start: int, max_chars: int) -> int:
    hard_end = min(start + max_chars, len(text))
    if hard_end >= len(text):
        return hard_end

    min_boundary = start + int(max_chars * 0.6)
    for index in range(hard_end - 1, min_boundary - 1, -1):
        if text[index].isspace():
            return index + 1

    return hard_end


def _page_span(page_ranges: list[_PageRange], start: int, end: int) -> tuple[int, int]:
    touched = [
        page_range.page_number
        for page_range in page_ranges
        if page_range.start < end and page_range.end > start
    ]
    if touched:
        return min(touched), max(touched)

    if not page_ranges:
        return 0, 0

    nearest = min(
        page_ranges,
        key=lambda page_range: min(abs(start - page_range.start), abs(start - page_range.end)),
    )
    return nearest.page_number, nearest.page_number
