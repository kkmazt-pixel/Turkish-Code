"""Embedding kind vocabulary (doc 14 §4).

Many retrieval embedders use different prefixes/encoders for documents vs.
queries (asymmetric models); the ``kind`` argument is mandatory on every embed
call so document and query embeddings are never mixed — a classic silent
retrieval-quality bug (doc 14 §4/§13).
"""

from __future__ import annotations

from enum import StrEnum


class EmbeddingKind(StrEnum):
    """Which side of an asymmetric embedding model a text is being encoded for."""

    DOCUMENT = "document"
    QUERY = "query"
