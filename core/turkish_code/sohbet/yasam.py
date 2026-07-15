"""Conversation lifecycle — open, suspend, resume, close, archive.

:class:`ConversationLifecycle` drives a conversation's
:class:`ConversationState` over the shared :class:`ConversationRegistry` with
validated transitions: open → (suspend ⇄ resume) → close → archive. Illegal
transitions are rejected (fail-safe); ``ARCHIVED`` is terminal. Only ``OPEN``
conversations accept messages (enforced by the dispatcher), so suspend/close
genuinely pause a conversation and resume re-opens it.
"""

from __future__ import annotations

from collections.abc import Iterable

from turkish_code.hata import AppError, ErrorKind
from turkish_code.sohbet.modeller import ConversationId, ConversationState
from turkish_code.sohbet.oturum import Conversation, ConversationRegistry

CONVERSATION_INVALID_TRANSITION_CODE = "conversation.invalid_transition"


class ConversationLifecycle:
    """Creates conversations and drives their lifecycle state (fail-safe)."""

    def __init__(self, registry: ConversationRegistry) -> None:
        self._registry = registry

    def open(self, conversation_id: ConversationId, *, agent_id: str) -> Conversation:
        """Open a fresh conversation with an agent; reject a duplicate id."""
        return self._registry.create(conversation_id, agent_id=agent_id)

    def suspend(self, conversation_id: ConversationId) -> None:
        """Pause an open conversation: OPEN → SUSPENDED."""
        conversation = self._registry.resolve(conversation_id)
        self._require(conversation, (ConversationState.OPEN,))
        conversation.set_state(ConversationState.SUSPENDED)

    def resume(self, conversation_id: ConversationId) -> None:
        """Resume a suspended conversation: SUSPENDED → OPEN."""
        conversation = self._registry.resolve(conversation_id)
        self._require(conversation, (ConversationState.SUSPENDED,))
        conversation.set_state(ConversationState.OPEN)

    def close(self, conversation_id: ConversationId) -> None:
        """End a conversation: OPEN/SUSPENDED → CLOSED."""
        conversation = self._registry.resolve(conversation_id)
        self._require(
            conversation, (ConversationState.OPEN, ConversationState.SUSPENDED)
        )
        conversation.set_state(ConversationState.CLOSED)

    def archive(self, conversation_id: ConversationId) -> None:
        """Archive a conversation: any non-archived state → ARCHIVED."""
        conversation = self._registry.resolve(conversation_id)
        self._require(
            conversation,
            (
                ConversationState.OPEN,
                ConversationState.SUSPENDED,
                ConversationState.CLOSED,
            ),
        )
        conversation.set_state(ConversationState.ARCHIVED)

    def _require(
        self, conversation: Conversation, allowed: Iterable[ConversationState]
    ) -> None:
        if conversation.state not in allowed:
            raise _invalid_transition(conversation.id, conversation.state)


def _invalid_transition(
    conversation_id: ConversationId, state: ConversationState
) -> AppError:
    return AppError(
        kind=ErrorKind.CONFLICT,
        code=CONVERSATION_INVALID_TRANSITION_CODE,
        message_key=f"hata.{CONVERSATION_INVALID_TRANSITION_CODE}",
        retryable=False,
        detail=(
            f"illegal transition for {conversation_id.value!r} "
            f"in state {state.value!r}"
        ),
        context={"conversation": conversation_id.value},
    )
