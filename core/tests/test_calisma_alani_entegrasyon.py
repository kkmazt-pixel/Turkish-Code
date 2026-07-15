"""End-to-end integration tests for the Workspace Runtime (doc 25 §7).

Drives the whole runtime — registry → manager → lifecycle → bound Conversation
Runtime — through :func:`build_workspace_runtime`, plus per-workspace storage
isolation at the Storage Engine level.
"""

from __future__ import annotations

import asyncio
import datetime as dt
from pathlib import Path

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
from turkish_code.calisma_alani.hata import WORKSPACE_DUPLICATE_CODE
from turkish_code.calisma_alani.kompozisyon import (
    WorkspaceRuntime,
    build_workspace_runtime,
)
from turkish_code.calisma_alani.modeller import (
    WorkspaceConfig,
    WorkspaceId,
    WorkspaceMetadata,
    WorkspaceState,
)
from turkish_code.depo.alan import StorageEngine
from turkish_code.depo.yerlesim import StorageLayout
from turkish_code.eklentiler.izin import PluginGrantStore
from turkish_code.eklentiler.kompozisyon import build_plugin_runtime
from turkish_code.hata import AppError
from turkish_code.sohbet.modeller import ConversationId
from turkish_code.yapilandirma.depolama import StorageConfig
from turkish_code.yetenekler.kompozisyon import build_skill_runtime


class _Bot:
    @property
    def metadata(self) -> AgentMetadata:
        return AgentMetadata(id="bot", name="bot", role="chat", summary="s")

    async def run(self, request: AgentRequest, context: AgentContext) -> AgentResponse:
        return AgentResponse(run_id=request.run_id, output="cevap")


def _workspace_runtime() -> WorkspaceRuntime:
    tools = ToolDispatcher(
        ToolRegistry(), PolicyPermissionGate(PermissionPolicy(mode=PermissionMode.AUTO))
    )
    agents = build_agent_runtime(tools, agents=[_Bot()])
    plugins = build_plugin_runtime(
        ToolRegistry(), PluginGrantStore(), app_version="0.0.0"
    )
    skills = build_skill_runtime(tools, agents=agents)
    return build_workspace_runtime(agents=agents, skills=skills, plugins=plugins)


def _wid(value: str) -> WorkspaceId:
    return WorkspaceId(value)


def _meta() -> WorkspaceMetadata:
    return WorkspaceMetadata(name="P", root="/p")


def _cid(value: str) -> ConversationId:
    return ConversationId(value)


# --- create / open / conversation ---------------------------------------------


@pytest.mark.asyncio
async def test_create_open_and_run_a_conversation() -> None:
    runtime = _workspace_runtime()
    runtime.manager.create(_wid("w1"), _meta())
    session = runtime.manager.open(_wid("w1"))
    assert session.state is WorkspaceState.ACTIVE
    ctx = session.context
    assert ctx is not None

    ctx.conversation.lifecycle.open(_cid("c1"), agent_id="bot")
    turn = await ctx.conversation.dispatcher.send(_cid("c1"), "merhaba")
    assert turn.agent.content == "cevap"


@pytest.mark.asyncio
async def test_conversation_isolation_between_workspaces() -> None:
    runtime = _workspace_runtime()
    runtime.manager.create(_wid("a"), _meta())
    runtime.manager.create(_wid("b"), _meta())
    ctx_a = runtime.manager.open(_wid("a")).context
    ctx_b = runtime.manager.open(_wid("b")).context
    assert ctx_a is not None and ctx_b is not None

    # the same conversation id in both workspaces — isolated registries
    ctx_a.conversation.lifecycle.open(_cid("c1"), agent_id="bot")
    ctx_b.conversation.lifecycle.open(_cid("c1"), agent_id="bot")
    await ctx_a.conversation.dispatcher.send(_cid("c1"), "a-mesaj")
    await ctx_b.conversation.dispatcher.send(_cid("c1"), "b-mesaj")

    hist_a = ctx_a.conversation.registry.resolve(_cid("c1")).history
    hist_b = ctx_b.conversation.registry.resolve(_cid("c1")).history
    assert [t.user.content for t in hist_a.turns] == ["a-mesaj"]
    assert [t.user.content for t in hist_b.turns] == ["b-mesaj"]


# --- switch / current ---------------------------------------------------------


def test_create_open_switch_and_current() -> None:
    runtime = _workspace_runtime()
    runtime.manager.create(_wid("a"), _meta())
    runtime.manager.create(_wid("b"), _meta())
    runtime.manager.open(_wid("a"))
    assert runtime.manager.current_id() == _wid("a")
    runtime.manager.switch(_wid("b"))
    assert runtime.manager.current_id() == _wid("b")


# --- duplicate / archive / restore / delete -----------------------------------


def test_duplicate_workspace_is_rejected() -> None:
    runtime = _workspace_runtime()
    runtime.manager.create(_wid("w1"), _meta())
    with pytest.raises(AppError) as exc_info:
        runtime.manager.create(_wid("w1"), _meta())
    assert exc_info.value.code == WORKSPACE_DUPLICATE_CODE


def test_archive_and_restore_flow() -> None:
    runtime = _workspace_runtime()
    runtime.manager.create(_wid("w1"), _meta())
    runtime.lifecycle.activate(_wid("w1"))
    runtime.lifecycle.deactivate(_wid("w1"))
    runtime.lifecycle.archive(_wid("w1"))
    assert runtime.registry.active_ids() == []  # off the active set
    assert runtime.registry.ids() == ["w1"]  # still stored
    runtime.lifecycle.restore(_wid("w1"))
    assert runtime.registry.resolve(_wid("w1")).state is WorkspaceState.INACTIVE
    assert runtime.registry.active_ids() == ["w1"]


def test_delete_removes_and_clears_current() -> None:
    runtime = _workspace_runtime()
    runtime.manager.create(_wid("w1"), _meta())
    runtime.manager.open(_wid("w1"))
    runtime.manager.delete(_wid("w1"))
    assert runtime.manager.current_id() is None
    assert _wid("w1") not in runtime.registry


def test_create_with_custom_config() -> None:
    runtime = _workspace_runtime()
    config = WorkspaceConfig(default_agent_id="bot", max_history_turns=3)
    session = runtime.manager.create(_wid("w1"), _meta(), config=config)
    assert session.config is config


# --- parallel workspaces ------------------------------------------------------


@pytest.mark.asyncio
async def test_parallel_workspaces_run_independently() -> None:
    runtime = _workspace_runtime()
    contexts = {}
    for n in range(4):
        runtime.manager.create(_wid(f"w{n}"), _meta())
        session = runtime.manager.open(_wid(f"w{n}"))
        assert session.context is not None
        session.context.conversation.lifecycle.open(_cid("chat"), agent_id="bot")
        contexts[n] = session.context

    turns = await asyncio.gather(
        *(
            contexts[n].conversation.dispatcher.send(_cid("chat"), f"m-{n}")
            for n in range(4)
        )
    )
    assert all(turn.agent.content == "cevap" for turn in turns)
    # each workspace's conversation registry has exactly its own turn
    for n in range(4):
        history = contexts[n].conversation.registry.resolve(_cid("chat")).history
        assert [t.user.content for t in history.turns] == [f"m-{n}"]


# --- storage isolation (Storage Engine level) ---------------------------------


def _memory_item(body: str) -> MemoryItem:
    ts = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)
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
        created_at=ts,
        last_used_at=ts,
        use_count=0,
        confidence=1.0,
    )


@pytest.mark.asyncio
async def test_storage_is_isolated_per_workspace(tmp_path: Path) -> None:
    engine = await StorageEngine.open(StorageLayout(tmp_path), StorageConfig())
    store_a = await engine.open_workspace("wa")
    store_b = await engine.open_workspace("wb")
    try:
        await store_a.memory.save(_memory_item("fact-a"))
        recalled_a = await store_a.memory.recall(scope=MemoryScope.WORKSPACE, limit=10)
        recalled_b = await store_b.memory.recall(scope=MemoryScope.WORKSPACE, limit=10)
        assert [item.body for item in recalled_a] == ["fact-a"]
        assert list(recalled_b) == []  # a's data is not visible in b's store
    finally:
        await store_a.aclose()
        await store_b.aclose()
        await engine.aclose()
