"""Tests for the provider manager (doc 21 §6)."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence

import pytest
from turkish_code.gomme import EmbeddingKind
from turkish_code.hata import AppError
from turkish_code.ortak.saat import Clock
from turkish_code.saglayicilar.cache import InMemoryModelCache
from turkish_code.saglayicilar.manager import ProviderManager
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

_CAPSET = CapabilitySet(
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


class _StubProvider:
    """A minimal, real Provider stub with configurable models/health for tests."""

    def __init__(
        self,
        provider_id: str,
        *,
        roles: frozenset[Role] = frozenset({Role.CHAT}),
        health: HealthStatus = HealthStatus.UP,
    ) -> None:
        self._id = provider_id
        self._roles = roles
        self._health = health
        self.list_models_calls = 0

    @property
    def id(self) -> str:
        return self._id

    @property
    def kind(self) -> ProviderKind:
        return ProviderKind.CLOUD

    @property
    def is_offline_fallback(self) -> bool:
        return False

    @property
    def tier_info(self) -> TierInfo:
        return TierInfo(tier="free", quota_limits={})

    async def list_models(self) -> Sequence[ModelInfo]:
        self.list_models_calls += 1
        return [
            ModelInfo(
                id=f"{self._id}-model",
                provider_id=self._id,
                roles=self._roles,
                capabilities=_CAPSET,
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
        raise NotImplementedError
        yield  # type: ignore[unreachable]  # unused; makes this an async generator

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
        return _CAPSET


def test_rejects_duplicate_provider_ids(fixed_clock: Clock) -> None:
    with pytest.raises(ValueError):
        ProviderManager(
            [_StubProvider("dup"), _StubProvider("dup")],
            cache=InMemoryModelCache(),
            clock=fixed_clock,
        )


def test_provider_lookup_by_id(fixed_clock: Clock) -> None:
    manager = ProviderManager(
        [_StubProvider("gemini")], cache=InMemoryModelCache(), clock=fixed_clock
    )
    assert manager.provider("gemini").id == "gemini"


def test_unknown_provider_raises_typed_not_found(fixed_clock: Clock) -> None:
    manager = ProviderManager([], cache=InMemoryModelCache(), clock=fixed_clock)
    with pytest.raises(AppError) as excinfo:
        manager.provider("missing")
    assert excinfo.value.code == "provider.unknown"


@pytest.mark.asyncio
async def test_refresh_stale_populates_cache(fixed_clock: Clock) -> None:
    provider = _StubProvider("groq")
    manager = ProviderManager([provider], cache=InMemoryModelCache(), clock=fixed_clock)

    await manager.refresh_stale()

    assert provider.list_models_calls == 1
    assert [m.id for m in manager.all_models()] == ["groq-model"]


@pytest.mark.asyncio
async def test_refresh_stale_skips_fresh_entries(fixed_clock: Clock) -> None:
    provider = _StubProvider("groq")
    manager = ProviderManager([provider], cache=InMemoryModelCache(), clock=fixed_clock)

    await manager.refresh_stale()
    await manager.refresh_stale()  # second call: entry is now fresh

    assert provider.list_models_calls == 1


def test_all_models_empty_before_any_refresh(fixed_clock: Clock) -> None:
    manager = ProviderManager(
        [_StubProvider("groq")], cache=InMemoryModelCache(), clock=fixed_clock
    )
    assert manager.all_models() == []


@pytest.mark.asyncio
async def test_models_for_role_filters_by_role(fixed_clock: Clock) -> None:
    chat_only = _StubProvider("chatty", roles=frozenset({Role.CHAT}))
    embed_only = _StubProvider("embedder", roles=frozenset({Role.EMBED}))
    manager = ProviderManager(
        [chat_only, embed_only], cache=InMemoryModelCache(), clock=fixed_clock
    )
    await manager.refresh_stale()

    assert [m.id for m in manager.models_for_role(Role.EMBED)] == ["embedder-model"]


@pytest.mark.asyncio
async def test_health_snapshot_reports_each_provider(fixed_clock: Clock) -> None:
    up = _StubProvider("up-provider", health=HealthStatus.UP)
    down = _StubProvider("down-provider", health=HealthStatus.DOWN)
    manager = ProviderManager([up, down], cache=InMemoryModelCache(), clock=fixed_clock)

    snapshot = await manager.health_snapshot()

    assert snapshot == {
        "up-provider": HealthStatus.UP,
        "down-provider": HealthStatus.DOWN,
    }
