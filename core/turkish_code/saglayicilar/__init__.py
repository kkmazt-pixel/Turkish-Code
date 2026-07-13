"""Provider system (doc 21) — Sağlayıcılar.

The provider-independent abstraction over model backends (chat/embed/rerank).
Model-first: the rest of the system asks for a capability and gets the best
model, never a specific vendor (ADR-0005/ADR-0012).
"""

from turkish_code.saglayicilar.manager import ProviderManager
from turkish_code.saglayicilar.provider import (
    ChatChunk,
    ChatMessage,
    HealthStatus,
    ModelInfo,
    Provider,
    ProviderKind,
    RankedCandidate,
    TierInfo,
    Usage,
)

__all__ = [
    "Provider",
    "ProviderKind",
    "ModelInfo",
    "TierInfo",
    "HealthStatus",
    "ChatMessage",
    "ChatChunk",
    "Usage",
    "RankedCandidate",
    "ProviderManager",
]
