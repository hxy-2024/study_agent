from __future__ import annotations

import uuid
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, String, TypeDecorator
from sqlalchemy.dialects import postgresql


class GUID(TypeDecorator):
    """Platform-independent UUID type.

    Postgres stores native UUID values; SQLite stores canonical UUID strings.
    """

    impl = String(36)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(postgresql.UUID(as_uuid=True))
        return dialect.type_descriptor(String(36))

    def process_bind_param(self, value: Any, dialect) -> str | uuid.UUID | None:
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
        return str(value if isinstance(value, uuid.UUID) else uuid.UUID(str(value)))

    def process_result_value(self, value: Any, dialect) -> uuid.UUID | None:
        if value is None:
            return None
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


JSONValue = JSON().with_variant(postgresql.JSONB(), "postgresql")


class EmbeddingVector(TypeDecorator):
    """Vector type that uses pgvector on Postgres and JSON storage on SQLite."""

    impl = JSON
    cache_ok = True

    def __init__(self, dimensions: int) -> None:
        super().__init__()
        self.dimensions = dimensions

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(Vector(self.dimensions))
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value: Any, dialect) -> list[float] | None:
        if value is None:
            return None
        return [float(item) for item in value]

    def process_result_value(self, value: Any, dialect) -> list[float] | None:
        if value is None:
            return None
        return [float(item) for item in value]
