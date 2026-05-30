from __future__ import annotations

import asyncio
import sqlite3
import threading
from collections.abc import Iterable, Sequence
from typing import Any

DatabaseError = sqlite3.DatabaseError
Error = sqlite3.Error
IntegrityError = sqlite3.IntegrityError
NotSupportedError = sqlite3.NotSupportedError
OperationalError = sqlite3.OperationalError
ProgrammingError = sqlite3.ProgrammingError
sqlite_version = sqlite3.sqlite_version
sqlite_version_info = sqlite3.sqlite_version_info


class _DummyThread:
    daemon = True


class _ImmediateQueue:
    def put_nowait(self, item: tuple[asyncio.Future, Any]) -> None:
        future, function = item
        try:
            result = function()
        except Exception as exc:  # pragma: no cover - propagated by SQLAlchemy
            future.set_exception(exc)
        else:
            future.set_result(result)


class Cursor:
    def __init__(self, connection: Connection, cursor: sqlite3.Cursor) -> None:
        self._connection = connection
        self._cursor = cursor
        self.arraysize = cursor.arraysize

    @property
    def description(self) -> Any:
        return self._cursor.description

    @property
    def rowcount(self) -> int:
        return self._cursor.rowcount

    @property
    def lastrowid(self) -> int | None:
        return self._cursor.lastrowid

    async def execute(self, operation: str, parameters: Sequence[Any] | None = None) -> Cursor:
        if parameters is None:
            await self._connection._run(self._cursor.execute, operation)
        else:
            await self._connection._run(self._cursor.execute, operation, parameters)
        return self

    async def executemany(self, operation: str, seq_of_parameters: Iterable[Sequence[Any]]) -> Cursor:
        await self._connection._run(self._cursor.executemany, operation, seq_of_parameters)
        return self

    async def fetchone(self) -> Any:
        return await self._connection._run(self._cursor.fetchone)

    async def fetchmany(self, size: int | None = None) -> list[Any]:
        if size is None:
            size = self.arraysize
        return await self._connection._run(self._cursor.fetchmany, size)

    async def fetchall(self) -> list[Any]:
        return await self._connection._run(self._cursor.fetchall)

    async def close(self) -> None:
        await self._connection._run(self._cursor.close)


class Connection:
    def __init__(self, database: str, **kwargs: Any) -> None:
        kwargs.pop("iter_chunk_size", None)
        kwargs.setdefault("check_same_thread", False)
        self._database = database
        self._kwargs = kwargs
        self._conn: sqlite3.Connection | None = None
        self._closed = False
        self._lock = threading.RLock()
        self._thread = _DummyThread()
        self._tx = _ImmediateQueue()

    def __await__(self) -> Any:
        async def _connect() -> Connection:
            if self._conn is None:
                self._conn = await asyncio.to_thread(
                    sqlite3.connect,
                    self._database,
                    **self._kwargs,
                )
            return self

        return _connect().__await__()

    @property
    def isolation_level(self) -> str | None:
        return self._ready_connection.isolation_level

    @isolation_level.setter
    def isolation_level(self, value: str | None) -> None:
        self._ready_connection.isolation_level = value

    @property
    def in_transaction(self) -> bool:
        return self._ready_connection.in_transaction

    @property
    def row_factory(self) -> Any:
        return self._ready_connection.row_factory

    @row_factory.setter
    def row_factory(self, value: Any) -> None:
        self._ready_connection.row_factory = value

    @property
    def text_factory(self) -> Any:
        return self._ready_connection.text_factory

    @text_factory.setter
    def text_factory(self, value: Any) -> None:
        self._ready_connection.text_factory = value

    @property
    def _ready_connection(self) -> sqlite3.Connection:
        if self._conn is None or self._closed:
            raise ValueError("no active connection")
        return self._conn

    async def _run(self, function: Any, *args: Any, **kwargs: Any) -> Any:
        def _call() -> Any:
            with self._lock:
                return function(*args, **kwargs)

        return await asyncio.to_thread(_call)

    async def cursor(self) -> Cursor:
        cursor = await self._run(self._ready_connection.cursor)
        return Cursor(self, cursor)

    async def execute(self, operation: str, parameters: Sequence[Any] | None = None) -> Cursor:
        cursor = await self.cursor()
        return await cursor.execute(operation, parameters)

    async def executemany(self, operation: str, seq_of_parameters: Iterable[Sequence[Any]]) -> Cursor:
        cursor = await self.cursor()
        return await cursor.executemany(operation, seq_of_parameters)

    async def commit(self) -> None:
        await self._run(self._ready_connection.commit)

    async def rollback(self) -> None:
        await self._run(self._ready_connection.rollback)

    async def close(self) -> None:
        if self._conn is None or self._closed:
            return
        await self._run(self._ready_connection.close)
        self._closed = True

    async def create_function(self, *args: Any, **kwargs: Any) -> None:
        await self._run(self._ready_connection.create_function, *args, **kwargs)

    def stop(self) -> None:
        if self._conn is None or self._closed:
            return
        with self._lock:
            self._conn.close()
            self._closed = True


def connect(database: str, **kwargs: Any) -> Connection:
    return Connection(database, **kwargs)
