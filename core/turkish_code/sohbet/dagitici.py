"""Conversation dispatcher — bounded, cancellable send over the registry.

:class:`ConversationDispatcher` is the runtime entry point for sending a message
to a conversation: it resolves the conversation, mints a turn id, runs the
:class:`ConversationEngine`, and tracks the in-flight turn so a conversation can
be cancelled by id (propagating to the agent run). Independent conversations run
in parallel — each ``send`` is self-contained and keyed by conversation id.
"""

from __future__ import annotations

import itertools

from turkish_code.hata import AppError, ErrorKind
from turkish_code.sohbet.baglam import ConversationEventSink
from turkish_code.sohbet.modeller import ConversationId, ConversationState, Turn
from turkish_code.sohbet.motor import ConversationEngine
from turkish_code.sohbet.oturum import ConversationRegistry

CONVERSATION_NOT_OPEN_CODE = "conversation.not_open"


class ConversationDispatcher:
    """Routes a message to its conversation and runs one bounded turn."""

    def __init__(
        self, registry: ConversationRegistry, engine: ConversationEngine
    ) -> None:
        self._registry = registry
        self._engine = engine
        self._active: dict[str, str] = {}
        self._counter = itertools.count()

    async def send(
        self,
        conversation_id: ConversationId,
        content: str,
        *,
        sink: ConversationEventSink | None = None,
        timeout_ms: int | None = None,
    ) -> Turn:
        """Run one turn for ``conversation_id`` (doc 09 §7).

        Resolves the conversation (raises ``conversation.not_found``), mints a
        turn id, and runs the engine bounded by ``timeout_ms``. Streamed chunks
        go to ``sink``; the completed :class:`Turn` is returned and persisted.
        """
        conversation = self._registry.resolve(conversation_id)
        if conversation.state is not ConversationState.OPEN:
            raise _not_open(conversation_id, conversation.state)
        key = conversation_id.value
        turn_id = f"{key}:{next(self._counter)}"
        self._active[key] = turn_id
        try:
            return await self._engine.send(
                conversation,
                content,
                turn_id=turn_id,
                sink=sink,
                timeout_ms=timeout_ms,
            )
        finally:
            self._active.pop(key, None)

    def cancel(self, conversation_id: ConversationId) -> None:
        """Cancel the conversation's in-flight turn; no-op if none (doc 18 §9)."""
        turn_id = self._active.get(conversation_id.value)
        if turn_id is not None:
            self._engine.cancel(turn_id)


def _not_open(conversation_id: ConversationId, state: ConversationState) -> AppError:
    return AppError(
        kind=ErrorKind.CONFLICT,
        code=CONVERSATION_NOT_OPEN_CODE,
        message_key=f"hata.{CONVERSATION_NOT_OPEN_CODE}",
        retryable=False,
        detail=f"conversation {conversation_id.value!r} is {state.value!r}, not open",
        context={"conversation": conversation_id.value},
    )
