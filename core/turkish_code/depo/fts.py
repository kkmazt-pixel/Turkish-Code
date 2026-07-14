"""SQLite FTS5-backed ``LexicalIndex`` (doc 13 §6, doc 29 §7).

BM25 keyword search over RAG chunk text, implementing the ``LexicalIndex``
Protocol declared in :mod:`turkish_code.getirim.depo`. The ``unicode61``
tokenizer runs with ``remove_diacritics 0`` so Turkish characters survive
intact — the RAG layer (doc 13 §6) is responsible for code-identifier splitting
before text reaches this substrate. Free-text queries are sanitised into quoted
FTS5 phrases so operator/punctuation input can never raise a syntax error, and
scores are returned as ``-bm25()`` (higher = more relevant) to match the
``VectorIndex`` convention.
"""

from __future__ import annotations

from collections.abc import Sequence

from turkish_code.depo.db import Database


class SqliteLexicalIndex:
    """A :class:`~turkish_code.getirim.depo.LexicalIndex` over one workspace DB."""

    def __init__(self, db: Database) -> None:
        self._db = db

    async def upsert(self, chunk_id: str, text: str) -> None:
        """Insert or replace ``chunk_id``'s indexed text (doc 13 §6).

        FTS5 has no native upsert, so we delete any prior row for this id and
        re-insert within a single transaction — the write stays atomic.
        """
        async with self._db.transaction() as tx:
            await tx.execute("DELETE FROM chunk_fts WHERE chunk_id = ?", (chunk_id,))
            await tx.execute(
                "INSERT INTO chunk_fts (chunk_id, body) VALUES (?, ?)",
                (chunk_id, text),
            )

    async def search(
        self, query_text: str, *, top_k: int
    ) -> Sequence[tuple[str, float]]:
        """Return up to ``top_k`` best ``(chunk_id, score)`` matches (doc 13 §6)."""
        match = _to_match_query(query_text)
        if match is None:
            return []
        rows = await self._db.fetchall(
            "SELECT chunk_id, -bm25(chunk_fts) AS score FROM chunk_fts "
            "WHERE chunk_fts MATCH ? ORDER BY rank LIMIT ?",
            (match, top_k),
        )
        return [(str(row["chunk_id"]), float(row["score"])) for row in rows]


def _to_match_query(text: str) -> str | None:
    """Turn free text into a safe FTS5 MATCH expression, or ``None`` if empty.

    Each whitespace token becomes a double-quoted phrase (embedded quotes
    doubled) so FTS5 operators and punctuation in user input can never trigger a
    syntax error. Tokens are OR-combined for recall in the fusion stage; ``bm25``
    ranking still surfaces the strongest matches first (doc 13 §6).
    """
    tokens = [tok for tok in text.split() if tok]
    if not tokens:
        return None
    return " OR ".join('"' + tok.replace('"', '""') + '"' for tok in tokens)
