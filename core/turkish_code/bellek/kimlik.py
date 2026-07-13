"""Memory item identity (doc 11 §5)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MemoryId:
    """A stable memory item identifier (doc 11 §5)."""

    value: str
