"""Streaming progress for tool calls (doc 20 §7/§17, doc 10 §11).

A tool reports incremental work by emitting :class:`ToolProgress` events to a
:class:`ProgressSink`; the dispatcher wires one in per call, and the final
:class:`~turkish_code.araclar.modeller.ToolResult` is the call's return value.
The sink is the seam to the transport — in production it forwards ``$/progress``
notifications over the Core Channel (doc 10 §11); here two in-process sinks cover
the "drop it" default and "collect it" (tests/simple callers) cases.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from turkish_code.araclar.modeller import ToolProgress


@runtime_checkable
class ProgressSink(Protocol):
    """Receives a tool call's progress events (doc 20 §7)."""

    async def emit(self, progress: ToolProgress) -> None:
        """Deliver one progress event; ordering follows emission order."""
        ...


class NullProgressSink:
    """A :class:`ProgressSink` that drops every event — the default when a caller
    wants only the final result (doc 20 §5)."""

    async def emit(self, progress: ToolProgress) -> None:
        return None


class CollectingProgressSink:
    """A :class:`ProgressSink` that appends events in order (tests/simple use)."""

    def __init__(self) -> None:
        self.events: list[ToolProgress] = []

    async def emit(self, progress: ToolProgress) -> None:
        self.events.append(progress)
