"""Tests for conversation context assembly — history window + memory (doc 11 §6)."""

from __future__ import annotations

from collections.abc import Sequence

import pytest
from turkish_code.sohbet.baglam import ConversationContext
from turkish_code.sohbet.gecmis import HistoryBuilder
from turkish_code.sohbet.modeller import ConversationId, Message, Role, Turn
from turkish_code.sohbet.oturum import Conversation
from turkish_code.sohbet.protocol import MemorySource


class _FixedMemory:
    """A :class:`MemorySource` returning fixed snippets and recording the call."""

    def __init__(self, snippets: Sequence[str]) -> None:
        self._snippets = tuple(snippets)
        self.calls: list[tuple[str, int]] = []

    async def recall(self, query: str, *, limit: int) -> Sequence[str]:
        self.calls.append((query, limit))
        return self._snippets[:limit]


def _conversation(*, agent_id: str = "a") -> Conversation:
    return Conversation(ConversationId("c1"), agent_id=agent_id)


def _turn(turn_id: str, user: str, agent: str) -> Turn:
    return Turn(
        turn_id=turn_id,
        user=Message(role=Role.USER, content=user),
        agent=Message(role=Role.AGENT, content=agent),
    )


# --- context rendering --------------------------------------------------------


def test_render_flattens_system_memory_history_message() -> None:
    ctx = ConversationContext(
        conversation_id="c1",
        message="şimdi ne?",
        history=(
            Message(role=Role.USER, content="merhaba"),
            Message(role=Role.AGENT, content="selam"),
        ),
        memory=("kullanıcı Python sever",),
        system="Sen yardımcı bir asistansın.",
    )
    rendered = ctx.render()
    assert "Sen yardımcı bir asistansın." in rendered
    assert "İlgili hafıza:\nkullanıcı Python sever" in rendered
    assert "user: merhaba" in rendered
    assert "agent: selam" in rendered
    assert rendered.endswith("user: şimdi ne?")


def test_render_minimal_is_just_the_message() -> None:
    ctx = ConversationContext(conversation_id="c1", message="tek mesaj")
    assert ctx.render() == "user: tek mesaj"


# --- memory protocol ----------------------------------------------------------


def test_fixed_memory_satisfies_protocol() -> None:
    assert isinstance(_FixedMemory([]), MemorySource)


# --- history builder ----------------------------------------------------------


@pytest.mark.asyncio
async def test_build_without_memory_has_no_snippets() -> None:
    conversation = _conversation()
    conversation.add_turn(_turn("t1", "s1", "a1"))
    ctx = await HistoryBuilder().build(conversation, "yeni soru")
    assert ctx.message == "yeni soru"
    assert ctx.memory == ()
    assert [(m.role, m.content) for m in ctx.history] == [
        (Role.USER, "s1"),
        (Role.AGENT, "a1"),
    ]


@pytest.mark.asyncio
async def test_build_injects_memory_snippets() -> None:
    conversation = _conversation()
    memory = _FixedMemory(["fact-1", "fact-2", "fact-3"])
    ctx = await HistoryBuilder(memory_limit=2).build(
        conversation, "soru", memory=memory
    )
    assert ctx.memory == ("fact-1", "fact-2")
    assert memory.calls == [("soru", 2)]  # queried with the message + limit


@pytest.mark.asyncio
async def test_build_windows_history_to_max_turns() -> None:
    conversation = _conversation()
    for i in range(5):
        conversation.add_turn(_turn(f"t{i}", f"s{i}", f"a{i}"))
    ctx = await HistoryBuilder(max_turns=2).build(conversation, "soru")
    # only the last 2 turns → 4 messages
    assert [m.content for m in ctx.history] == ["s3", "a3", "s4", "a4"]


@pytest.mark.asyncio
async def test_build_zero_memory_limit_skips_recall() -> None:
    memory = _FixedMemory(["fact"])
    ctx = await HistoryBuilder(memory_limit=0).build(
        _conversation(), "soru", memory=memory
    )
    assert ctx.memory == ()
    assert memory.calls == []  # recall never invoked


@pytest.mark.asyncio
async def test_build_attaches_system_preamble() -> None:
    ctx = await HistoryBuilder(system="Kurallar...").build(_conversation(), "soru")
    assert ctx.system == "Kurallar..."
