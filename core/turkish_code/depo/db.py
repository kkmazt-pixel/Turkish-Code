"""The Database abstraction (doc 29 §8/§14, ADR-A/ADR-D) — WAL, single-writer.

One :class:`Database` owns one SQLite file through a **dedicated writer-actor
thread** (ADR-A: stdlib ``sqlite3`` + a single-worker executor). Every call is
marshalled onto that one thread, which simultaneously (a) keeps the asyncio
event loop unblocked (doc 09 §6) and (b) *is* the single-writer discipline
(doc 29 §14) — there is structurally never a second concurrent writer.

Transactions are serialized by an :class:`asyncio.Lock` so only one unit of
work is open at a time; the block commits on success and rolls back on any
exception (all-or-nothing, doc 29 §8). Raw ``sqlite3`` errors are mapped to
typed :class:`AppError` (:mod:`hata_eslem`).
"""

from __future__ import annotations

import asyncio
import sqlite3
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from turkish_code.depo.baglanti import Params, Row, SqliteConnection
from turkish_code.depo.hata_eslem import map_sqlite_error
from turkish_code.depo.islem import Transaction
from turkish_code.yapilandirma.depolama import StorageConfig, VectorBackend


class Database:
    """An async, single-writer handle over one SQLite file (doc 29 §8/§14)."""

    def __init__(
        self,
        executor: ThreadPoolExecutor,
        connection: SqliteConnection,
        *,
        vector_ready: bool = False,
    ) -> None:
        self._executor = executor
        self._conn = connection
        self._txn_lock = asyncio.Lock()
        self._closed = False
        self._vector_ready = vector_ready

    @classmethod
    async def open(cls, path: Path, *, config: StorageConfig) -> Database:
        """Open (creating parent dirs) ``path`` with WAL + durable pragmas.

        The connection is created *on* the writer thread so ``sqlite3``'s
        thread-affinity guard stays active — any accidental off-thread use
        would raise rather than corrupt silently.
        """
        executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="tc-depo-writer"
        )
        connection = await _run_on(executor, lambda: _connect(path, config))
        # Load the optional vector backend on the writer thread (ADR-C): if it
        # can't load, the store still opens — only vector search is unavailable.
        vector_ready = False
        if config.vector_backend is VectorBackend.SQLITE_VEC:
            vector_ready = await _run_on(executor, connection.try_load_vector_backend)
        return cls(executor, connection, vector_ready=vector_ready)

    @property
    def vector_ready(self) -> bool:
        """Whether the optional sqlite-vec backend loaded on this DB (ADR-C)."""
        return self._vector_ready

    def transaction(self) -> _TransactionScope:
        """A serialized, all-or-nothing transaction scope (doc 29 §8/§14).

        Usage: ``async with db.transaction() as tx: ...`` — commits on a clean
        exit, rolls back on any exception.
        """
        self._ensure_open()
        return _TransactionScope(self)

    async def fetchall(self, sql: str, params: Params = ()) -> list[Row]:
        """Run a read query outside a transaction (autocommit)."""
        self._ensure_open()
        return await self._run(lambda: self._conn.fetchall(sql, params))

    async def fetchone(self, sql: str, params: Params = ()) -> Row | None:
        """Run a read query for the first row outside a transaction."""
        self._ensure_open()
        return await self._run(lambda: self._conn.fetchone(sql, params))

    async def executescript(self, script: str) -> None:
        """Run a multi-statement DDL script (migration runner, doc 29 §10)."""
        self._ensure_open()
        await self._run(lambda: self._conn.executescript(script))

    async def aclose(self) -> None:
        """Close the connection and stop the writer thread. Idempotent."""
        if self._closed:
            return
        self._closed = True
        await self._run(self._conn.close)
        self._executor.shutdown(wait=True)

    async def _run[T](self, fn: Callable[[], T]) -> T:
        return await _run_on(self._executor, fn)

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("database is closed")


class _TransactionScope:
    """Async context manager wrapping one BEGIN…COMMIT/ROLLBACK (doc 29 §8)."""

    def __init__(self, db: Database) -> None:
        self._db = db

    async def __aenter__(self) -> Transaction:
        await self._db._txn_lock.acquire()
        try:
            await self._db._run(self._db._conn.begin)
        except BaseException:
            self._db._txn_lock.release()
            raise
        return Transaction(self._db._conn, self._db._run)

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        try:
            if exc_type is None:
                await self._db._run(self._db._conn.commit)
            else:
                await self._db._run(self._db._conn.rollback)
        finally:
            self._db._txn_lock.release()


async def _run_on[T](executor: ThreadPoolExecutor, fn: Callable[[], T]) -> T:
    """Submit ``fn`` to the writer thread, mapping ``sqlite3`` errors (doc 38)."""
    try:
        return await asyncio.wrap_future(executor.submit(fn))
    except sqlite3.Error as exc:
        raise map_sqlite_error(exc) from exc


def _connect(path: Path, config: StorageConfig) -> SqliteConnection:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = sqlite3.connect(path, isolation_level=None)
    raw.row_factory = sqlite3.Row
    raw.execute("PRAGMA journal_mode=WAL")
    raw.execute(f"PRAGMA busy_timeout={config.busy_timeout_ms}")
    raw.execute("PRAGMA foreign_keys=ON")
    raw.execute(f"PRAGMA synchronous={'FULL' if config.fsync_durable else 'NORMAL'}")
    return SqliteConnection(raw)
