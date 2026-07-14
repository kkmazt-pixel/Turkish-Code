"""Ajanlar — the Agent Runtime (doc 18).

A thin, stable runtime for *running* agents on top of the existing Tool, Plugin,
Storage, and Provider runtimes — how an agent runs, not how it reasons (doc 15 /
planner / council are out of scope). This package defines the agent contract
(:class:`Agent`), its metadata, the request/response value objects, and the
session lifecycle; the registry, context, session, dispatcher, and lifecycle
build on them across later increments. The runtime depends only on the
:class:`Agent` Protocol (DIP); agents reach subsystems only through their
context (doc 18 §7/§16).
"""

from turkish_code.ajanlar.baglam import (
    AGENT_TOOL_OUT_OF_SCOPE_CODE,
    AgentContext,
    AgentEventSink,
    CollectingEventSink,
    ConversationContext,
    ExecutionContext,
    NullEventSink,
    SessionContext,
)
from turkish_code.ajanlar.dagitici import (
    AGENT_CANCELLED_CODE,
    AGENT_FAILED_CODE,
    AGENT_TIMEOUT_CODE,
    AgentDispatcher,
)
from turkish_code.ajanlar.durum import ConversationState, RunRecord, RunState
from turkish_code.ajanlar.iptal import CancellationRegistry, CancellationToken
from turkish_code.ajanlar.kayit import (
    AGENT_DUPLICATE_CODE,
    AGENT_NO_DEFAULT_CODE,
    AGENT_NOT_FOUND_CODE,
    AgentRegistry,
)
from turkish_code.ajanlar.kompozisyon import AgentRuntime, build_agent_runtime
from turkish_code.ajanlar.modeller import (
    AgentChunk,
    AgentMetadata,
    AgentRequest,
    AgentResponse,
    ConversationTurn,
    MemoryScope,
    SessionState,
    TurnRole,
)
from turkish_code.ajanlar.oturum import (
    AGENT_RUN_DUPLICATE_CODE,
    AGENT_RUN_NOT_FOUND_CODE,
    AgentSession,
)
from turkish_code.ajanlar.protocol import Agent
from turkish_code.ajanlar.yasam import (
    AGENT_INVALID_TRANSITION_CODE,
    AGENT_SESSION_DUPLICATE_CODE,
    AGENT_SESSION_NOT_FOUND_CODE,
    SessionLifecycle,
)

__all__ = [
    "Agent",
    "AgentContext",
    "ConversationContext",
    "ExecutionContext",
    "SessionContext",
    "AgentMetadata",
    "AgentRequest",
    "AgentResponse",
    "ConversationTurn",
    "TurnRole",
    "MemoryScope",
    "SessionState",
    "AGENT_TOOL_OUT_OF_SCOPE_CODE",
    "AgentRegistry",
    "AGENT_DUPLICATE_CODE",
    "AGENT_NOT_FOUND_CODE",
    "AGENT_NO_DEFAULT_CODE",
    "AgentSession",
    "ConversationState",
    "RunRecord",
    "RunState",
    "AGENT_RUN_NOT_FOUND_CODE",
    "AGENT_RUN_DUPLICATE_CODE",
    "AgentDispatcher",
    "CancellationToken",
    "CancellationRegistry",
    "AgentChunk",
    "AgentEventSink",
    "NullEventSink",
    "CollectingEventSink",
    "AGENT_TIMEOUT_CODE",
    "AGENT_CANCELLED_CODE",
    "AGENT_FAILED_CODE",
    "SessionLifecycle",
    "AGENT_SESSION_NOT_FOUND_CODE",
    "AGENT_SESSION_DUPLICATE_CODE",
    "AGENT_INVALID_TRANSITION_CODE",
    "AgentRuntime",
    "build_agent_runtime",
]
