"""Conversation state + registry — the stateful conversation and its store.

:class:`Conversation` is one conversation: its id, lifecycle
:class:`ConversationState`, the agent it talks to, and its append-only
:class:`History`. :class:`ConversationRegistry` is the store the runtime looks
conversations up in — create/get/delete/archive/list. Registration is fail-safe:
a duplicate id is rejected. The registry archives (excluding a conversation from
the active set); the lifecycle drives the other transitions (Increment 5).
"""

from __future__ import annotations

from turkish_code.hata import AppError, ErrorKind
from turkish_code.sohbet.modeller import (
    ConversationId,
    ConversationState,
    History,
    Turn,
)

CONVERSATION_NOT_FOUND_CODE = "conversation.not_found"
CONVERSATION_DUPLICATE_CODE = "conversation.duplicate"


class Conversation:
    """One stateful conversation — id, state, agent, and history."""

    def __init__(self, conversation_id: ConversationId, *, agent_id: str) -> None:
        self._id = conversation_id
        self._agent_id = agent_id
        self._state = ConversationState.OPEN
        self._history = History()

    @property
    def id(self) -> ConversationId:
        return self._id

    @property
    def agent_id(self) -> str:
        return self._agent_id

    @property
    def state(self) -> ConversationState:
        return self._state

    @property
    def history(self) -> History:
        """An immutable snapshot of the conversation so far."""
        return self._history

    @property
    def is_archived(self) -> bool:
        return self._state is ConversationState.ARCHIVED

    def set_state(self, target: ConversationState) -> None:
        """Set the lifecycle state (raw). The lifecycle validates transitions."""
        self._state = target

    def add_turn(self, turn: Turn) -> None:
        """Append a completed turn to the conversation's history."""
        self._history = self._history.append(turn)


class ConversationRegistry:
    """An in-memory id→:class:`Conversation` store (create/lookup/delete/archive)."""

    def __init__(self) -> None:
        self._conversations: dict[str, Conversation] = {}

    def create(self, conversation_id: ConversationId, *, agent_id: str) -> Conversation:
        """Create a fresh OPEN conversation; reject a duplicate id (fail-safe)."""
        key = conversation_id.value
        if key in self._conversations:
            raise _duplicate(conversation_id)
        conversation = Conversation(conversation_id, agent_id=agent_id)
        self._conversations[key] = conversation
        return conversation

    def get(self, conversation_id: ConversationId) -> Conversation | None:
        """The conversation, or ``None`` if absent."""
        return self._conversations.get(conversation_id.value)

    def resolve(self, conversation_id: ConversationId) -> Conversation:
        """The conversation, or raise ``conversation.not_found``."""
        conversation = self._conversations.get(conversation_id.value)
        if conversation is None:
            raise _not_found(conversation_id)
        return conversation

    def delete(self, conversation_id: ConversationId) -> None:
        """Remove the conversation entirely, or raise ``conversation.not_found``."""
        if conversation_id.value not in self._conversations:
            raise _not_found(conversation_id)
        del self._conversations[conversation_id.value]

    def archive(self, conversation_id: ConversationId) -> None:
        """Mark the conversation ARCHIVED (retained, off the active set)."""
        self.resolve(conversation_id).set_state(ConversationState.ARCHIVED)

    def __contains__(self, conversation_id: object) -> bool:
        return (
            isinstance(conversation_id, ConversationId)
            and conversation_id.value in self._conversations
        )

    def __len__(self) -> int:
        return len(self._conversations)

    def ids(self) -> list[str]:
        """All conversation ids, sorted."""
        return sorted(self._conversations)

    def active_ids(self) -> list[str]:
        """Ids of non-archived conversations, sorted."""
        return sorted(
            key
            for key, conversation in self._conversations.items()
            if not conversation.is_archived
        )


def _not_found(conversation_id: ConversationId) -> AppError:
    return _err(
        ErrorKind.NOT_FOUND,
        CONVERSATION_NOT_FOUND_CODE,
        f"no conversation {conversation_id.value!r}",
        conversation_id,
    )


def _duplicate(conversation_id: ConversationId) -> AppError:
    return _err(
        ErrorKind.CONFLICT,
        CONVERSATION_DUPLICATE_CODE,
        f"a conversation already exists as {conversation_id.value!r}",
        conversation_id,
    )


def _err(
    kind: ErrorKind, code: str, detail: str, conversation_id: ConversationId
) -> AppError:
    return AppError(
        kind=kind,
        code=code,
        message_key=f"hata.{code}",
        retryable=False,
        detail=detail,
        context={"conversation": conversation_id.value},
    )
