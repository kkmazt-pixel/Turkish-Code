"""Tests for the SQLite FTS5 LexicalIndex (doc 13 §6, doc 29 §7)."""

from __future__ import annotations

from pathlib import Path

import pytest
from turkish_code.depo.db import Database
from turkish_code.depo.fts import SqliteLexicalIndex
from turkish_code.depo.migrate import load_migrations, migrate
from turkish_code.getirim.depo import LexicalIndex
from turkish_code.yapilandirma.depolama import StorageConfig


async def _index(tmp_path: Path) -> tuple[Database, SqliteLexicalIndex]:
    db = await Database.open(tmp_path / "workspace.db", config=StorageConfig())
    await migrate(db, load_migrations("workspace"))
    return db, SqliteLexicalIndex(db)


@pytest.mark.asyncio
async def test_index_satisfies_the_protocol(tmp_path: Path) -> None:
    db, index = await _index(tmp_path)
    try:
        assert isinstance(index, LexicalIndex)
    finally:
        await db.aclose()


@pytest.mark.asyncio
async def test_upsert_and_search_returns_match(tmp_path: Path) -> None:
    db, index = await _index(tmp_path)
    try:
        await index.upsert("c1", "verifyToken authenticates the request")
        await index.upsert("c2", "parseConfig reads the yaml file")
        hits = await index.search("verifyToken", top_k=10)
        assert [cid for cid, _ in hits] == ["c1"]
    finally:
        await db.aclose()


@pytest.mark.asyncio
async def test_search_ranks_by_relevance(tmp_path: Path) -> None:
    db, index = await _index(tmp_path)
    try:
        await index.upsert("strong", "token token token token")
        await index.upsert("weak", "token amid many other unrelated words here")
        hits = await index.search("token", top_k=10)
        assert [cid for cid, _ in hits] == ["strong", "weak"]
        assert hits[0][1] >= hits[1][1]  # higher score = more relevant
    finally:
        await db.aclose()


@pytest.mark.asyncio
async def test_upsert_replaces_prior_text(tmp_path: Path) -> None:
    db, index = await _index(tmp_path)
    try:
        await index.upsert("c1", "alpha beta")
        await index.upsert("c1", "gamma delta")  # replace
        assert await index.search("alpha", top_k=10) == []
        assert [cid for cid, _ in await index.search("gamma", top_k=10)] == ["c1"]
        # exactly one row remains for the id
        row = await db.fetchone(
            "SELECT count(*) AS n FROM chunk_fts WHERE chunk_id = ?", ("c1",)
        )
        assert row is not None and row["n"] == 1
    finally:
        await db.aclose()


@pytest.mark.asyncio
async def test_search_respects_top_k(tmp_path: Path) -> None:
    db, index = await _index(tmp_path)
    try:
        for i in range(5):
            await index.upsert(f"c{i}", "shared keyword content")
        hits = await index.search("keyword", top_k=3)
        assert len(hits) == 3
    finally:
        await db.aclose()


@pytest.mark.asyncio
async def test_turkish_characters_are_preserved(tmp_path: Path) -> None:
    db, index = await _index(tmp_path)
    try:
        await index.upsert("tr", "İstanbul şehir güncelleme çalışması")
        # diacritics are not stripped: the exact Turkish token matches
        assert [cid for cid, _ in await index.search("şehir", top_k=5)] == ["tr"]
        # and an ASCII-folded spelling does NOT match (remove_diacritics 0)
        assert await index.search("sehir", top_k=5) == []
    finally:
        await db.aclose()


@pytest.mark.asyncio
async def test_multiple_terms_are_or_combined(tmp_path: Path) -> None:
    db, index = await _index(tmp_path)
    try:
        await index.upsert("a", "authentication middleware")
        await index.upsert("b", "database migration")
        hits = await index.search("authentication migration", top_k=10)
        assert sorted(cid for cid, _ in hits) == ["a", "b"]
    finally:
        await db.aclose()


@pytest.mark.asyncio
async def test_operator_and_punctuation_input_is_safe(tmp_path: Path) -> None:
    db, index = await _index(tmp_path)
    try:
        await index.upsert("a", "config file parser")
        # FTS5 operators / injection-looking punctuation must not raise
        for query in ["config OR file", "a-b (c)", '"; DROP TABLE', "* AND *"]:
            assert isinstance(await index.search(query, top_k=5), list)
    finally:
        await db.aclose()


@pytest.mark.asyncio
async def test_empty_query_returns_no_matches(tmp_path: Path) -> None:
    db, index = await _index(tmp_path)
    try:
        await index.upsert("a", "content")
        assert await index.search("", top_k=5) == []
        assert await index.search("   ", top_k=5) == []
    finally:
        await db.aclose()
