"""Conversation value objects — id, role, message, turn, and history.

The immutable building blocks of a conversation: a :class:`ConversationId`, the
:class:`Role` of a message, a :class:`Message` (role + text), a :class:`Turn`
(one completed user→agent exchange), and a :class:`History` snapshot (the ordered
turns so far). Pure data — the registry, context assembly, engine, and lifecycle
build on these. This phase runs conversations; it does not reason for them
(doc 15 is out of scope).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Role(StrEnum):
    """Who produced a message in a conversation."""

    USER = "user"
    AGENT = "agent"
    SYSTEM = "system"


class ConversationState(StrEnum):
    """A conversation's lifecycle state.

    ``OPEN`` (accepting messages) ⇄ ``SUSPENDED`` (paused) → ``CLOSED`` (ended)
    → ``ARCHIVED`` (retained, excluded from the active set). The lifecycle drives
    these transitions; the registry archives.
    """

    OPEN = "open"
    SUSPENDED = "suspended"
    CLOSED = "closed"
    ARCHIVED = "archived"


@dataclass(frozen=True, slots=True)
class ConversationId:
    """The stable id of one conversation."""

    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("ConversationId.value must be non-empty")


@dataclass(frozen=True, slots=True)
class Message:
    """One message in a conversation — a role and its text."""

    role: Role
    content: str

    def __post_init__(self) -> None:
        if not self.content:
            raise ValueError("Message.content must be non-empty")


@dataclass(frozen=True, slots=True)
class Turn:
    """One completed exchange — a user message and the agent's response.

    Attributes:
        turn_id: Unique id of this turn (ordering + correlation).
        user: The user's message (role ``USER``).
        agent: The agent's response message (role ``AGENT``).
    """

    turn_id: str
    user: Message
    agent: Message

    def __post_init__(self) -> None:
        if not self.turn_id:
            raise ValueError("Turn.turn_id must be non-empty")
        if self.user.role is not Role.USER:
            raise ValueError("Turn.user must have role USER")
        if self.agent.role is not Role.AGENT:
            raise ValueError("Turn.agent must have role AGENT")


@dataclass(frozen=True, slots=True)
class ConversationChunk:
    """A streamed fragment of a turn's agent response (doc 10 §11).

    The engine bridges the agent's streamed output to these before the final
    :class:`Turn` is persisted.

    Attributes:
        conversation_id: The conversation this chunk belongs to.
        delta: The incremental response text for this fragment (Turkish).
    """

    conversation_id: str
    delta: str


@dataclass(frozen=True, slots=True)
class History:
    """An immutable snapshot of a conversation's turns, oldest first."""

    turns: tuple[Turn, ...] = field(default_factory=tuple)

    @property
    def turn_count(self) -> int:
        return len(self.turns)

    def last(self) -> Turn | None:
        """The most recent turn, or ``None`` if the conversation is empty."""
        return self.turns[-1] if self.turns else None

    def append(self, turn: Turn) -> History:
        """A new history with ``turn`` added at the end (immutable)."""
        return History(turns=(*self.turns, turn))

    def window(self, size: int) -> History:
        """The most recent ``size`` turns (a context-limit window).

        ``size <= 0`` yields an empty history; a size beyond the length yields
        the whole history.
        """
        if size <= 0:
            return History()
        return History(turns=self.turns[-size:])

    def messages(self) -> tuple[Message, ...]:
        """The turns flattened to an alternating user/agent message sequence."""
        return tuple(
            message for turn in self.turns for message in (turn.user, turn.agent)
        )
