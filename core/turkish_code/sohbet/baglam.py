"""Assembled conversation context — what a turn hands to the agent.

:class:`ConversationContext` is the immutable, assembled input for one turn: the
current user message, a windowed slice of prior history (a context limit), any
injected memory snippets (doc 11 §6), and an optional system preamble. The engine
renders it into the agent's message; the assembly itself (windowing + memory
injection) is the :class:`~turkish_code.sohbet.gecmis.HistoryBuilder`'s job. This
is plain assembly — prompt *reasoning* is out of scope (doc 15).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from turkish_code.sohbet.modeller import ConversationChunk, Message


@runtime_checkable
class ConversationEventSink(Protocol):
    """Receives a turn's streamed response chunks (doc 10 §11)."""

    async def emit(self, chunk: ConversationChunk) -> None:
        """Deliver one chunk; ordering follows emission order."""
        ...


class NullEventSink:
    """A :class:`ConversationEventSink` that drops every chunk — the default."""

    async def emit(self, chunk: ConversationChunk) -> None:
        return None


class CollectingEventSink:
    """A :class:`ConversationEventSink` that appends chunks in order (tests)."""

    def __init__(self) -> None:
        self.chunks: list[ConversationChunk] = []

    async def emit(self, chunk: ConversationChunk) -> None:
        self.chunks.append(chunk)


@dataclass(frozen=True, slots=True)
class ConversationContext:
    """The assembled context for one conversation turn.

    Attributes:
        conversation_id: The conversation this turn belongs to.
        message: The current user message text.
        history: Prior messages within the context window, oldest first.
        memory: Injected memory snippets relevant to the message (doc 11 §6).
        system: An optional system preamble.
    """

    conversation_id: str
    message: str
    history: tuple[Message, ...] = field(default_factory=tuple)
    memory: tuple[str, ...] = field(default_factory=tuple)
    system: str | None = None

    def render(self) -> str:
        """Flatten the context into a single prompt string for the agent.

        A deliberately simple assembly (system → memory → history → message);
        richer prompt formatting belongs to the reasoning layer (doc 15), which
        is out of scope for this runtime.
        """
        parts: list[str] = []
        if self.system:
            parts.append(self.system)
        if self.memory:
            parts.append("İlgili hafıza:\n" + "\n".join(self.memory))
        for message in self.history:
            parts.append(f"{message.role.value}: {message.content}")
        parts.append(f"user: {self.message}")
        return "\n".join(parts)
