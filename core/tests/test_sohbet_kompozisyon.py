"""Tests for conversation-runtime composition + container wiring (doc 09 §7)."""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence

import pytest
from turkish_code.ajanlar.baglam import AgentContext
from turkish_code.ajanlar.kompozisyon import build_agent_runtime
from turkish_code.ajanlar.modeller import AgentMetadata, AgentRequest, AgentResponse
from turkish_code.araclar.dagitici import ToolDispatcher
from turkish_code.araclar.izin import (
    PermissionMode,
    PermissionPolicy,
    PolicyPermissionGate,
)
from turkish_code.araclar.kayit import ToolRegistry
from turkish_code.bellek.durum import MemoryState
from turkish_code.bellek.katman import MemoryKind, MemoryLayer, MemoryScope
from turkish_code.bellek.kayit import MemoryItem
from turkish_code.bellek.kimlik import MemoryId
from turkish_code.sohbet.dagitici import ConversationDispatcher
from turkish_code.sohbet.kompozisyon import (
    ConversationRuntime,
    RepositoryMemorySource,
    build_conversation_runtime,
)
from turkish_code.sohbet.modeller import ConversationId
from turkish_code.sohbet.oturum import ConversationRegistry

_TS = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)


class _Bot:
    def __init__(self, capture: dict[str, str] | None = None) -> None:
        self._capture = capture

    @property
    def metadata(self) -> AgentMetadata:
        return AgentMetadata(id="bot", name="bot", role="chat", summary="s")

    async def run(self, request: AgentRequest, context: AgentContext) -> AgentResponse:
        if self._capture is not None:
            self._capture["message"] = request.message
        return AgentResponse(run_id=request.run_id, output="cevap")


def _agents(bot: _Bot | None = None) -> object:
    tools = ToolDispatcher(
        ToolRegistry(), PolicyPermissionGate(PermissionPolicy(mode=PermissionMode.AUTO))
    )
    return build_agent_runtime(tools, agents=[bot or _Bot()])


class _FixedMemory:
    async def recall(self, query: str, *, limit: int) -> Sequence[str]:
        return ("kullanıcı Türkçe konuşur",)[:limit]


def _item(body: str) -> MemoryItem:
    return MemoryItem(
        id=MemoryId(body),
        layer=MemoryLayer.SEMANTIC,
        scope=MemoryScope.WORKSPACE,
        kind=MemoryKind.FACT,
        state=MemoryState.ACTIVE,
        title="t",
        body=body,
        links=(),
        embedding_ref=None,
        salience=0.5,
        source=None,
        pinned=False,
        created_at=_TS,
        last_used_at=_TS,
        use_count=0,
        confidence=1.0,
    )


class _StubRepo:
    """A minimal MemoryRepository returning fixed items from recall."""

    def __init__(self, items: Sequence[MemoryItem]) -> None:
        self._items = tuple(items)
        self.calls: list[tuple[MemoryScope, int]] = []

    async def get(self, memory_id: object) -> None:  # pragma: no cover
        return None

    async def save(self, item: object) -> None:  # pragma: no cover
        return None

    async def recall(
        self, *, scope: MemoryScope, layers: object = None, limit: int
    ) -> Sequence[MemoryItem]:
        self.calls.append((scope, limit))
        return self._items[:limit]

    async def pin(self, memory_id: object) -> None:  # pragma: no cover
        return None

    async def unpin(self, memory_id: object) -> None:  # pragma: no cover
        return None

    async def forget(self, memory_id: object) -> None:  # pragma: no cover
        return None

    async def purge(self, memory_id: object) -> None:  # pragma: no cover
        return None


def test_build_returns_wired_graph() -> None:
    runtime = build_conversation_runtime(_agents())  # type: ignore[arg-type]
    assert isinstance(runtime, ConversationRuntime)
    assert isinstance(runtime.registry, ConversationRegistry)
    assert isinstance(runtime.dispatcher, ConversationDispatcher)
    assert len(runtime.registry) == 0


@pytest.mark.asyncio
async def test_end_to_end_open_and_send_via_runtime() -> None:
    runtime = build_conversation_runtime(_agents())  # type: ignore[arg-type]
    runtime.lifecycle.open(ConversationId("c1"), agent_id="bot")
    turn = await runtime.dispatcher.send(ConversationId("c1"), "selam")
    assert turn.agent.content == "cevap"
    assert runtime.registry.resolve(ConversationId("c1")).history.turn_count == 1


@pytest.mark.asyncio
async def test_memory_is_injected_into_the_prompt() -> None:
    capture: dict[str, str] = {}
    runtime = build_conversation_runtime(
        _agents(_Bot(capture)),  # type: ignore[arg-type]
        memory=_FixedMemory(),
        memory_limit=3,
    )
    runtime.lifecycle.open(ConversationId("c1"), agent_id="bot")
    await runtime.dispatcher.send(ConversationId("c1"), "merhaba")
    assert "İlgili hafıza:\nkullanıcı Türkçe konuşur" in capture["message"]


@pytest.mark.asyncio
async def test_repository_memory_source_returns_item_bodies() -> None:
    repo = _StubRepo([_item("fact-1"), _item("fact-2")])
    source = RepositoryMemorySource(repo, scope=MemoryScope.WORKSPACE)
    snippets = await source.recall("soru", limit=5)
    assert list(snippets) == ["fact-1", "fact-2"]
    assert repo.calls == [(MemoryScope.WORKSPACE, 5)]


def test_container_exposes_conversation_runtime() -> None:
    from turkish_code.kompozisyon import build_container
    from turkish_code.yapilandirma.yukleyici import load_settings

    container = build_container(load_settings(environ={}))
    assert isinstance(container.conversation_runtime, ConversationRuntime)
    assert len(container.conversation_runtime.registry) == 0
