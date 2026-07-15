"""Conversation ports — the DIP boundaries the engine depends on (doc 11).

The Conversation Runtime injects relevant memory into a turn's context **without**
depending on the Storage/Memory implementations — it never opens SQLite (PR-9).
:class:`MemorySource` is that port: given the current message it returns
injectable memory snippets; the composition adapts it to the real
``MemoryRepository`` (doc 11 §6). Implementations are injected, never imported by
this layer (DIP).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable


@runtime_checkable
class MemorySource(Protocol):
    """Supplies memory snippets to inject into a conversation turn (doc 11 §6)."""

    async def recall(self, query: str, *, limit: int) -> Sequence[str]:
        """Return up to ``limit`` memory snippets relevant to ``query``."""
        ...
