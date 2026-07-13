"""The retrieval query (doc 13 §7) — what a caller asks Getirim for."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RetrievalQuery:
    """A retrieval request, with the scope filters doc 13 §7 lists.

    ``scope_file_paths``/``scope_languages`` narrow the search (doc 13 §7);
    ``top_k`` bounds how many candidates each retriever may return (PR-14).
    """

    text: str
    scope_file_paths: Sequence[str] | None = None
    scope_languages: Sequence[str] | None = None
    top_k: int = 10
