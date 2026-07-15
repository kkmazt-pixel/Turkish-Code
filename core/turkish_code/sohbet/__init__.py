"""Sohbet — the Conversation Runtime.

A thin, DIP-compliant conversation engine that orchestrates one chain per user
message: conversation state → context assembly → memory injection → skill
selection → agent dispatch → streaming response → history persist. It *uses* the
Agent, Skill, Storage, Provider, and Memory runtimes through their facades — it
never opens SQLite, calls a provider, or runs a tool directly. This is not a
planner, workflow, or reasoning engine (doc 15 out of scope): it runs
conversations, it does not reason for them. This package defines the value
models first; the registry, context, engine, dispatcher, and lifecycle build on
them across later increments.
"""

from turkish_code.sohbet.baglam import (
    CollectingEventSink,
    ConversationContext,
    ConversationEventSink,
    NullEventSink,
)
from turkish_code.sohbet.dagitici import (
    CONVERSATION_NOT_OPEN_CODE,
    ConversationDispatcher,
)
from turkish_code.sohbet.gecmis import HistoryBuilder
from turkish_code.sohbet.kompozisyon import (
    ConversationRuntime,
    RepositoryMemorySource,
    build_conversation_runtime,
)
from turkish_code.sohbet.modeller import (
    ConversationChunk,
    ConversationId,
    ConversationState,
    History,
    Message,
    Role,
    Turn,
)
from turkish_code.sohbet.motor import ConversationEngine
from turkish_code.sohbet.oturum import (
    CONVERSATION_DUPLICATE_CODE,
    CONVERSATION_NOT_FOUND_CODE,
    Conversation,
    ConversationRegistry,
)
from turkish_code.sohbet.protocol import MemorySource
from turkish_code.sohbet.yasam import (
    CONVERSATION_INVALID_TRANSITION_CODE,
    ConversationLifecycle,
)

__all__ = [
    "ConversationId",
    "Role",
    "Message",
    "Turn",
    "History",
    "ConversationState",
    "Conversation",
    "ConversationRegistry",
    "CONVERSATION_NOT_FOUND_CODE",
    "CONVERSATION_DUPLICATE_CODE",
    "ConversationContext",
    "HistoryBuilder",
    "MemorySource",
    "ConversationChunk",
    "ConversationEventSink",
    "NullEventSink",
    "CollectingEventSink",
    "ConversationEngine",
    "ConversationDispatcher",
    "ConversationLifecycle",
    "CONVERSATION_INVALID_TRANSITION_CODE",
    "CONVERSATION_NOT_OPEN_CODE",
    "ConversationRuntime",
    "build_conversation_runtime",
    "RepositoryMemorySource",
]
