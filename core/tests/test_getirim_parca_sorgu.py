"""Tests for the chunk model and retrieval query (doc 13 §5/§7)."""

from __future__ import annotations

from turkish_code.getirim.parca import Chunk, FileChunkSource, MemoryChunkSource
from turkish_code.getirim.sorgu import RetrievalQuery


def test_chunk_with_file_source() -> None:
    chunk = Chunk(
        id="c1",
        source=FileChunkSource(file_path="src/auth.py", start_line=1, end_line=20),
        language="python",
        symbol=None,
        content_hash="abc123",
        tokens=120,
        embedding_ref=None,
    )
    assert isinstance(chunk.source, FileChunkSource)
    assert chunk.source.file_path == "src/auth.py"


def test_chunk_with_memory_source() -> None:
    chunk = Chunk(
        id="c2",
        source=MemoryChunkSource(memory_id="m1"),
        language=None,
        symbol=None,
        content_hash="def456",
        tokens=30,
        embedding_ref=None,
    )
    assert isinstance(chunk.source, MemoryChunkSource)
    assert chunk.source.memory_id == "m1"


def test_retrieval_query_defaults() -> None:
    query = RetrievalQuery(text="auth token nasıl doğrulanıyor?")
    assert query.top_k == 10
    assert query.scope_file_paths is None


def test_retrieval_query_scope_filters() -> None:
    query = RetrievalQuery(
        text="x", scope_file_paths=["src/"], scope_languages=["python"], top_k=5
    )
    assert query.scope_file_paths == ["src/"]
    assert query.top_k == 5
