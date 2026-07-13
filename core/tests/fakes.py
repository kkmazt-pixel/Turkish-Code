"""Shared test doubles for the provider/routing test suite.

Real business logic, substituted I/O — not "fake implementations" in the
forbidden sense (no production code here), just a configurable stand-in for
a live network provider so routing/resilience logic can be tested without a
real API key or network call.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Mapping, Sequence

from turkish_code.gomme import EmbeddingKind
from turkish_code.hata import AppError
from turkish_code.saglayicilar.provider import (
    ChatChunk,
    ChatMessage,
    HealthStatus,
    ModelInfo,
    ProviderKind,
    RankedCandidate,
    TierInfo,
)
from turkish_code.yonlendirme.capability import (
    CapabilitySet,
    CodeAptitude,
    CostClass,
    LatencyClass,
    MultilingualTr,
    ReasoningDepth,
    Role,
    ToolUse,
)

DEFAULT_CAPSET = CapabilitySet(
    role=Role.CHAT,
    reasoning=ReasoningDepth.STRONG,
    code_aptitude=CodeAptitude.STRONG,
    context_window=32_000,
    tool_use=ToolUse.NATIVE,
    vision=False,
    multilingual_tr=MultilingualTr.STRONG,
    latency_class=LatencyClass.FAST,
    cost_class=CostClass.CHEAP,
    max_output=8_000,
    streaming=True,
)

ChatBehavior = Callable[[], AsyncIterator[ChatChunk]]


def success_behavior(text: str = "ok") -> ChatBehavior:
    """A chat behavior that yields one chunk and finishes successfully."""

    async def _behavior() -> AsyncIterator[ChatChunk]:
        yield ChatChunk(delta=text, finish_reason="stop")

    return _behavior


def failing_behavior(error: AppError) -> ChatBehavior:
    """A chat behavior that fails before yielding anything."""

    async def _behavior() -> AsyncIterator[ChatChunk]:
        raise error
        yield  # type: ignore[unreachable]  # unused; makes this an async generator

    return _behavior


class StubProvider:
    """A minimal, configurable, real (non-mocked-logic) Provider double."""

    def __init__(
        self,
        provider_id: str,
        *,
        kind: ProviderKind = ProviderKind.CLOUD,
        is_offline_fallback: bool = False,
        roles: frozenset[Role] = frozenset({Role.CHAT}),
        health: HealthStatus = HealthStatus.UP,
        capabilities: CapabilitySet = DEFAULT_CAPSET,
        chat_behavior: ChatBehavior | None = None,
        tier_info: TierInfo | None = None,
    ) -> None:
        self._id = provider_id
        self._kind = kind
        self._is_offline_fallback = is_offline_fallback
        self._roles = roles
        self._health = health
        self._capabilities = capabilities
        self._chat_behavior = chat_behavior or success_behavior()
        self._tier_info = tier_info or TierInfo(tier="free", quota_limits={})
        self.list_models_calls = 0

    @property
    def id(self) -> str:
        return self._id

    @property
    def kind(self) -> ProviderKind:
        return self._kind

    @property
    def is_offline_fallback(self) -> bool:
        return self._is_offline_fallback

    @property
    def tier_info(self) -> TierInfo:
        return self._tier_info

    async def list_models(self) -> Sequence[ModelInfo]:
        self.list_models_calls += 1
        return [
            ModelInfo(
                id=f"{self._id}-model",
                provider_id=self._id,
                roles=self._roles,
                capabilities=self._capabilities,
                context_window=32_000,
                pricing=None,
                tier=None,
                latency_profile=None,
                quality=None,
            )
        ]

    async def chat(
        self,
        model: str,
        messages: Sequence[ChatMessage],
        *,
        tools: Sequence[Mapping[str, object]] | None = None,
        opts: Mapping[str, object] | None = None,
    ) -> AsyncIterator[ChatChunk]:
        async for chunk in self._chat_behavior():
            yield chunk

    async def embed(
        self, model: str, texts: Sequence[str], kind: EmbeddingKind
    ) -> Sequence[Sequence[float]]:
        raise NotImplementedError

    async def rerank(
        self, model: str, query: str, candidates: Sequence[str]
    ) -> Sequence[RankedCandidate]:
        raise NotImplementedError

    async def health(self) -> HealthStatus:
        return self._health

    def capabilities(self, model: str) -> CapabilitySet:
        return self._capabilities
