"""History builder — assembles a turn's context from history + memory (doc 11 §6).

:class:`HistoryBuilder` turns a :class:`Conversation`'s history and the current
user message into a :class:`ConversationContext`: it windows the history to a
turn budget (the context limit, PR-14), injects relevant memory snippets through
the :class:`MemorySource` port (never touching Storage directly), and attaches an
optional system preamble. Memory injection is optional — with no source or a
zero limit, none is added.
"""

from __future__ import annotations

from turkish_code.sohbet.baglam import ConversationContext
from turkish_code.sohbet.oturum import Conversation
from turkish_code.sohbet.protocol import MemorySource


class HistoryBuilder:
    """Assembles conversation context under a turn/memory budget (doc 11 §6)."""

    def __init__(
        self,
        *,
        max_turns: int = 10,
        memory_limit: int = 5,
        system: str | None = None,
    ) -> None:
        self._max_turns = max_turns
        self._memory_limit = memory_limit
        self._system = system

    async def build(
        self,
        conversation: Conversation,
        user_message: str,
        *,
        memory: MemorySource | None = None,
    ) -> ConversationContext:
        """Build the assembled context for ``user_message`` (doc 11 §6, PR-14)."""
        window = conversation.history.window(self._max_turns)
        snippets: tuple[str, ...] = ()
        if memory is not None and self._memory_limit > 0:
            recalled = await memory.recall(user_message, limit=self._memory_limit)
            snippets = tuple(recalled)
        return ConversationContext(
            conversation_id=conversation.id.value,
            message=user_message,
            history=window.messages(),
            memory=snippets,
            system=self._system,
        )
