"""The connection seam (doc 29 §4, ADR-D) — one open DB connection.

:class:`Connection` is the **synchronous** driver surface the store needs,
kept deliberately minimal so a future backend (DuckDB, libSQL, PostgreSQL —
ADR-D) can implement it without touching the async :class:`~turkish_code.depo.
db.Database` layer above. :class:`SqliteConnection` is the stdlib ``sqlite3``
implementation (ADR-A), driven entirely from the writer-actor thread so its
default thread-affinity guard stays intact.

These methods run *inside* the actor thread and may raise raw ``sqlite3``
errors; the async layer maps them to typed errors (:mod:`hata_eslem`).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Sequence
from typing import Any, Protocol, runtime_checkable

Row = sqlite3.Row
"""One result row. A future backend maps its rows to this shape (ADR-D)."""

Params = Sequence[Any]


@runtime_checkable
class Connection(Protocol):
    """A single open database connection (doc 29 §4, ADR-D) — synchronous."""

    def execute(self, sql: str, params: Params = ()) -> None:
        """Run one statement (no result)."""
        ...

    def executemany(self, sql: str, seq_params: Iterable[Params]) -> None:
        """Run one statement for each parameter tuple."""
        ...

    def executescript(self, script: str) -> None:
        """Run a multi-statement DDL script (migrations, doc 29 §10)."""
        ...

    def fetchall(self, sql: str, params: Params = ()) -> list[Row]:
        """Run a query and return all rows."""
        ...

    def fetchone(self, sql: str, params: Params = ()) -> Row | None:
        """Run a query and return the first row, or ``None``."""
        ...

    def begin(self) -> None:
        """Open a transaction with an immediate write lock (doc 29 §14)."""
        ...

    def commit(self) -> None:
        """Commit the open transaction."""
        ...

    def rollback(self) -> None:
        """Roll back the open transaction."""
        ...

    def close(self) -> None:
        """Close the underlying connection."""
        ...


class SqliteConnection:
    """A :class:`Connection` over stdlib ``sqlite3`` (ADR-A).

    Opened with ``isolation_level=None`` so transaction boundaries are explicit
    (``BEGIN IMMEDIATE``/``COMMIT``) rather than driver-managed — the store owns
    the durability discipline (doc 29 §8), not the driver.
    """

    def __init__(self, raw: sqlite3.Connection) -> None:
        self._raw = raw

    def execute(self, sql: str, params: Params = ()) -> None:
        self._raw.execute(sql, params)

    def executemany(self, sql: str, seq_params: Iterable[Params]) -> None:
        self._raw.executemany(sql, seq_params)

    def executescript(self, script: str) -> None:
        self._raw.executescript(script)

    def fetchall(self, sql: str, params: Params = ()) -> list[Row]:
        rows: list[Row] = self._raw.execute(sql, params).fetchall()
        return rows

    def fetchone(self, sql: str, params: Params = ()) -> Row | None:
        row: Row | None = self._raw.execute(sql, params).fetchone()
        return row

    def begin(self) -> None:
        self._raw.execute("BEGIN IMMEDIATE")

    def commit(self) -> None:
        self._raw.execute("COMMIT")

    def rollback(self) -> None:
        self._raw.execute("ROLLBACK")

    def close(self) -> None:
        self._raw.close()

    def try_load_vector_backend(self) -> bool:
        """Best-effort load of the sqlite-vec extension on this connection.

        Returns ``True`` when vector search is available. Never raises: the
        optional backend (ADR-C, doc 29 §6) must not prevent the store from
        opening. SQLite-specific, so it lives on the concrete adapter, not the
        backend-agnostic :class:`Connection` Protocol.
        """
        from turkish_code.depo.vec import load_vector_extension

        return load_vector_extension(self._raw)
