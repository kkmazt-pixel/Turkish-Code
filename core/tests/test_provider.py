"""Tests for the provider-independent interface (doc 21 §5)."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence

import pytest
from turkish_code.gomme import EmbeddingKind
from turkish_code.saglayicilar import (
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


class _FakeProvider:
    """A minimal, real (non-mocked business logic) Provider conformance fixture."""

    def __init__(self) -> None:
        self._capset = CapabilitySet(
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

    @property
    def id(self) -> str:
        return "fake"

    @property
    def kind(self) -> ProviderKind:
        return ProviderKind.CLOUD

    @property
    def is_offline_fallback(self) -> bool:
        return False

    @property
    def tier_info(self) -> TierInfo:
        return TierInfo(tier="free", quota_limits={"requests_per_minute": 30})

    async def list_models(self) -> Sequence[ModelInfo]:
        return [
            ModelInfo(
                id="fake-chat",
                provider_id="fake",
                roles=frozenset({Role.CHAT}),
                capabilities=self._capset,
                context_window=32_000,
                pricing=None,
                tier="free",
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
        yield ChatChunk(delta="Merhaba")
        yield ChatChunk(
            delta="",
            finish_reason="stop",
            usage=Usage(prompt_tokens=5, completion_tokens=2),
        )

    async def embed(
        self, model: str, texts: Sequence[str], kind: EmbeddingKind
    ) -> Sequence[Sequence[float]]:
        return [[0.1, 0.2] for _ in texts]

    async def rerank(
        self, model: str, query: str, candidates: Sequence[str]
    ) -> Sequence[RankedCandidate]:
        return [
            RankedCandidate(index=i, score=1.0 - i * 0.1)
            for i in range(len(candidates))
        ]

    async def health(self) -> HealthStatus:
        return HealthStatus.UP

    def capabilities(self, model: str) -> CapabilitySet:
        return self._capset


def test_fake_provider_satisfies_protocol() -> None:
    assert isinstance(_FakeProvider(), Provider)


@pytest.mark.asyncio
async def test_list_models_returns_model_info() -> None:
    models = await _FakeProvider().list_models()
    assert models[0].id == "fake-chat"
    assert Role.CHAT in models[0].roles


@pytest.mark.asyncio
async def test_chat_streams_chunks_and_final_usage() -> None:
    message = ChatMessage(role="user", content="hi")
    stream = _FakeProvider().chat("fake-chat", [message])
    chunks = [chunk async for chunk in stream]
    assert chunks[0].delta == "Merhaba"
    assert chunks[-1].finish_reason == "stop"
    assert chunks[-1].usage == Usage(prompt_tokens=5, completion_tokens=2)


@pytest.mark.asyncio
async def test_embed_requires_kind() -> None:
    provider = _FakeProvider()
    vectors = await provider.embed("fake-chat", ["a", "b"], EmbeddingKind.DOCUMENT)
    assert len(vectors) == 2


@pytest.mark.asyncio
async def test_rerank_returns_scored_candidates() -> None:
    ranked = await _FakeProvider().rerank("fake-chat", "q", ["a", "b", "c"])
    assert [r.index for r in ranked] == [0, 1, 2]
    assert ranked[0].score > ranked[1].score


@pytest.mark.asyncio
async def test_health_reports_status() -> None:
    assert await _FakeProvider().health() is HealthStatus.UP


def test_tier_info_carries_opaque_quota_limits() -> None:
    tier = TierInfo(tier="paid", quota_limits={"tokens_per_day": 1_000_000})
    assert tier.quota_limits["tokens_per_day"] == 1_000_000
