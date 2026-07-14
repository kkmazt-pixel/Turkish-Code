"""The transaction seam (doc 29 §8, ADR-D) — an open unit of work.

A :class:`Transaction` is handed to repository code inside a
``async with db.transaction()`` block. Its statements run on the single
writer-actor thread (ADR-A) via the injected ``runner``; the enclosing
:class:`~turkish_code.depo.db.Database` guarantees exactly one transaction is
open at a time (single-writer discipline, doc 29 §14) and that the block is
committed on success or rolled back on any exception (all-or-nothing, doc 29 §8).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from typing import Protocol

from turkish_code.depo.baglanti import Connection, Params, Row


class Runner(Protocol):
    """Marshals a synchronous DB call onto the writer-actor thread (ADR-A)."""

    async def __call__[T](self, fn: Callable[[], T]) -> T: ...


class Transaction:
    """An open, single-writer unit of work over one :class:`Connection`."""

    def __init__(self, connection: Connection, runner: Runner) -> None:
        self._conn = connection
        self._run = runner

    async def execute(self, sql: str, params: Params = ()) -> None:
        """Run one statement within the transaction."""
        await self._run(lambda: self._conn.execute(sql, params))

    async def executemany(self, sql: str, seq_params: Iterable[Params]) -> None:
        """Run one statement per parameter tuple within the transaction."""
        rows = list(seq_params)
        await self._run(lambda: self._conn.executemany(sql, rows))

    async def fetchall(self, sql: str, params: Params = ()) -> Sequence[Row]:
        """Query all rows within the transaction (read-your-writes)."""
        return await self._run(lambda: self._conn.fetchall(sql, params))

    async def fetchone(self, sql: str, params: Params = ()) -> Row | None:
        """Query the first row within the transaction, or ``None``."""
        return await self._run(lambda: self._conn.fetchone(sql, params))
