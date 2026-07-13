"""The provider-independent interface (doc 21 §5).

Each provider is a single-responsibility adapter implementing :class:`Provider`
(SOLID, ADR-0014). Callers ask for a capability via the router (doc 45); they
never depend on a specific vendor (ADR-0002/ADR-0012). Model non-determinism is
confined here (PR-15); inputs/outputs are recorded upstream (doc 15/26).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal, Protocol, runtime_checkable

from turkish_code.gomme import EmbeddingKind
from turkish_code.yonlendirme.capability import CapabilitySet, Role

RATE_LIMIT_CODE = "provider.rate_limited"
"""The stable :class:`~turkish_code.hata.AppError` code adapters use to signal
a rate-limit (doc 48 §8); the resilience loop (doc 45 §6) matches on it to
decide cooldown vs. plain failover."""

CAPABILITY_UNSUPPORTED_CODE = "provider.capability_unsupported"
"""The stable code for a provider that doesn't implement a given capability
(e.g. rerank) at all — not a transient failure, never retried."""


class ProviderKind(StrEnum):
    """Where a provider's models run (doc 21 §4)."""

    CLOUD = "cloud"
    LOCAL = "local"


class HealthStatus(StrEnum):
    """Live provider health (doc 21 §5/§9, doc 45 §5)."""

    UP = "up"
    DEGRADED = "degraded"
    COOLING_DOWN = "cooling_down"
    DOWN = "down"


@dataclass(frozen=True, slots=True)
class TierInfo:
    """A provider's plan level and its raw quota limits (doc 21 §5, doc 48 §4).

    ``quota_limits`` is an opaque ``{limitName: value}`` map (e.g.
    ``{"requests_per_minute": 30}``); doc 48's quota tracker owns interpreting
    it against usage — this type only carries what the provider declares.
    """

    tier: str
    quota_limits: Mapping[str, int]


@dataclass(frozen=True, slots=True)
class ModelInfo:
    """A model a provider offers, feeding the registry + model cache (doc 21 §5)."""

    id: str
    provider_id: str
    roles: frozenset[Role]
    capabilities: CapabilitySet
    context_window: int
    pricing: Mapping[str, float] | None
    tier: str | None
    latency_profile: str | None
    quality: float | None


@dataclass(frozen=True, slots=True)
class ChatMessage:
    """A single turn in a chat request (doc 21 §5)."""

    role: Literal["system", "user", "assistant"]
    content: str


@dataclass(frozen=True, slots=True)
class Usage:
    """Token accounting for a completed call — feeds quota tracking (doc 48 §5)."""

    prompt_tokens: int
    completion_tokens: int


@dataclass(frozen=True, slots=True)
class ChatChunk:
    """One streamed piece of a chat response (doc 21 §8).

    ``finish_reason``/``usage`` are set only on the final chunk of a stream.
    """

    delta: str
    finish_reason: str | None = None
    usage: Usage | None = None


@dataclass(frozen=True, slots=True)
class RankedCandidate:
    """A rerank result: which input candidate, and its relevance score."""

    index: int
    score: float


@runtime_checkable
class Provider(Protocol):
    """A single-responsibility adapter over one model backend (doc 21 §5).

    Adding a provider means implementing this interface and registering it —
    nothing else changes (ADR-0014, doc 21 §22 #2).
    """

    @property
    def id(self) -> str:
        """Stable provider identifier, e.g. ``"gemini"``, ``"ollama"``."""
        ...

    @property
    def kind(self) -> ProviderKind:
        """Whether this provider's models run in the cloud or locally.

        Independent of :attr:`is_offline_fallback` — a self-hosted NVIDIA NIM
        is ``kind=local`` but still a primary (doc 22 §5.4), while Ollama is
        ``kind=local`` *and* the offline fallback.
        """
        ...

    @property
    def is_offline_fallback(self) -> bool:
        """True only for the offline/last-resort fallback role (doc 21 §4).

        Exactly one provider is expected to report ``True`` (Ollama); the
        router keeps it structurally separate from the scored primaries
        (doc 45 §6) regardless of ``kind``.
        """
        ...

    @property
    def tier_info(self) -> TierInfo:
        """This provider's current plan tier and declared quota limits."""
        ...

    async def list_models(self) -> Sequence[ModelInfo]:
        """Enumerate this provider's available models (feeds doc 21 §6, doc 49)."""
        ...

    def chat(
        self,
        model: str,
        messages: Sequence[ChatMessage],
        *,
        tools: Sequence[Mapping[str, object]] | None = None,
        opts: Mapping[str, object] | None = None,
    ) -> AsyncIterator[ChatChunk]:
        """Stream a chat completion (doc 21 §5/§8).

        Cancellable via doc 10 `$/cancel`.
        """
        ...

    async def embed(
        self, model: str, texts: Sequence[str], kind: EmbeddingKind
    ) -> Sequence[Sequence[float]]:
        """Embed ``texts`` as ``kind`` (document|query — doc 14 §4, doc 21 §5)."""
        ...

    async def rerank(
        self, model: str, query: str, candidates: Sequence[str]
    ) -> Sequence[RankedCandidate]:
        """Rerank ``candidates`` against ``query`` (doc 21 §5, doc 13 §8)."""
        ...

    async def health(self) -> HealthStatus:
        """Current health, used for routing/failover (doc 21 §9, doc 45 §5)."""
        ...

    def capabilities(self, model: str) -> CapabilitySet:
        """The declared :class:`CapabilitySet` for one of this provider's models."""
        ...
