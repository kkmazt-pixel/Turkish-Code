"""Conversation engine — the one chain per user message (doc 09 §7).

:class:`ConversationEngine` runs a single turn: assemble the context (windowed
history + injected memory), dispatch the conversation's agent through the **Agent
Runtime facade**, bridge the agent's streamed output to a conversation sink, and
persist the completed :class:`Turn`. It never opens SQLite, calls a provider, or
runs a tool directly — everything flows through the runtimes (PR-9). Skill
*selection* (trigger matching, doc 19 §6) is a reasoning concern out of scope
here: the agent reaches skills through its own runtime; the engine just runs the
turn.
"""

from __future__ import annotations

from turkish_code.ajanlar.baglam import AgentEventSink
from turkish_code.ajanlar.kompozisyon import AgentRuntime
from turkish_code.ajanlar.modeller import AgentChunk, AgentRequest
from turkish_code.sohbet.baglam import ConversationEventSink
from turkish_code.sohbet.gecmis import HistoryBuilder
from turkish_code.sohbet.modeller import (
    ConversationChunk,
    Message,
    Role,
    Turn,
)
from turkish_code.sohbet.oturum import Conversation
from turkish_code.sohbet.protocol import MemorySource


class ConversationEngine:
    """Runs one conversation turn through the assemble→dispatch→persist chain."""

    def __init__(
        self,
        agents: AgentRuntime,
        *,
        history_builder: HistoryBuilder | None = None,
        memory: MemorySource | None = None,
    ) -> None:
        self._agents = agents
        self._builder = (
            history_builder if history_builder is not None else HistoryBuilder()
        )
        self._memory = memory

    async def send(
        self,
        conversation: Conversation,
        content: str,
        *,
        turn_id: str,
        sink: ConversationEventSink | None = None,
        timeout_ms: int | None = None,
    ) -> Turn:
        """Run one turn for ``content`` and persist it (doc 09 §7).

        Assembles context (history + memory), dispatches the conversation's
        agent, streams chunks to ``sink``, and appends the resulting
        :class:`Turn`. Raises the agent's typed error (timeout/cancelled/failed)
        if the run does not complete — in which case no turn is persisted.
        """
        context = await self._builder.build(conversation, content, memory=self._memory)
        agent = self._agents.registry.resolve(conversation.agent_id)
        bridge: AgentEventSink | None = (
            _AgentSinkBridge(conversation.id.value, sink) if sink is not None else None
        )
        response = await self._agents.dispatcher.dispatch(
            AgentRequest(
                agent_id=conversation.agent_id,
                message=context.render(),
                run_id=turn_id,
                session_id=conversation.id.value,
            ),
            execution=self._agents.execution_for(agent),
            sink=bridge,
            timeout_ms=timeout_ms,
        )
        turn = Turn(
            turn_id=turn_id,
            user=Message(role=Role.USER, content=content),
            agent=Message(role=Role.AGENT, content=response.output),
        )
        conversation.add_turn(turn)
        return turn

    def cancel(self, turn_id: str) -> None:
        """Cancel an in-flight turn — propagates to the agent run (doc 18 §9)."""
        self._agents.dispatcher.cancel(turn_id)


class _AgentSinkBridge:
    """An :class:`AgentEventSink` that re-emits agent chunks at conversation level."""

    def __init__(self, conversation_id: str, sink: ConversationEventSink) -> None:
        self._conversation_id = conversation_id
        self._sink = sink

    async def emit(self, chunk: AgentChunk) -> None:
        await self._sink.emit(
            ConversationChunk(conversation_id=self._conversation_id, delta=chunk.delta)
        )
