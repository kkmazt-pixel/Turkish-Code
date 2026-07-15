"""Tests for the conversation state + registry."""

from __future__ import annotations

import pytest
from turkish_code.hata import AppError, ErrorKind
from turkish_code.sohbet.modeller import (
    ConversationId,
    ConversationState,
    Message,
    Role,
    Turn,
)
from turkish_code.sohbet.oturum import (
    CONVERSATION_DUPLICATE_CODE,
    CONVERSATION_NOT_FOUND_CODE,
    ConversationRegistry,
)


def _cid(value: str) -> ConversationId:
    return ConversationId(value)


def _turn(turn_id: str) -> Turn:
    return Turn(
        turn_id=turn_id,
        user=Message(role=Role.USER, content="soru"),
        agent=Message(role=Role.AGENT, content="cevap"),
    )


def test_create_makes_open_conversation() -> None:
    registry = ConversationRegistry()
    conversation = registry.create(_cid("c1"), agent_id="yonetici")
    assert conversation.state is ConversationState.OPEN
    assert conversation.agent_id == "yonetici"
    assert conversation.history.turn_count == 0
    assert _cid("c1") in registry


def test_duplicate_create_is_rejected() -> None:
    registry = ConversationRegistry()
    registry.create(_cid("c1"), agent_id="a")
    with pytest.raises(AppError) as exc_info:
        registry.create(_cid("c1"), agent_id="a")
    assert exc_info.value.code == CONVERSATION_DUPLICATE_CODE
    assert exc_info.value.kind is ErrorKind.CONFLICT


def test_resolve_missing_raises_not_found() -> None:
    with pytest.raises(AppError) as exc_info:
        ConversationRegistry().resolve(_cid("absent"))
    assert exc_info.value.code == CONVERSATION_NOT_FOUND_CODE
    assert exc_info.value.kind is ErrorKind.NOT_FOUND


def test_get_returns_none_for_missing() -> None:
    assert ConversationRegistry().get(_cid("absent")) is None


def test_add_turn_grows_history() -> None:
    registry = ConversationRegistry()
    conversation = registry.create(_cid("c1"), agent_id="a")
    conversation.add_turn(_turn("t1"))
    conversation.add_turn(_turn("t2"))
    assert [t.turn_id for t in conversation.history.turns] == ["t1", "t2"]


def test_delete_removes_conversation() -> None:
    registry = ConversationRegistry()
    registry.create(_cid("c1"), agent_id="a")
    registry.delete(_cid("c1"))
    assert _cid("c1") not in registry
    with pytest.raises(AppError):
        registry.resolve(_cid("c1"))


def test_delete_missing_raises_not_found() -> None:
    with pytest.raises(AppError) as exc_info:
        ConversationRegistry().delete(_cid("absent"))
    assert exc_info.value.code == CONVERSATION_NOT_FOUND_CODE


def test_archive_marks_and_excludes_from_active() -> None:
    registry = ConversationRegistry()
    registry.create(_cid("c1"), agent_id="a")
    registry.create(_cid("c2"), agent_id="a")
    registry.archive(_cid("c1"))
    assert registry.resolve(_cid("c1")).state is ConversationState.ARCHIVED
    assert registry.ids() == ["c1", "c2"]  # still stored
    assert registry.active_ids() == ["c2"]  # but off the active set


def test_archive_missing_raises_not_found() -> None:
    with pytest.raises(AppError) as exc_info:
        ConversationRegistry().archive(_cid("absent"))
    assert exc_info.value.code == CONVERSATION_NOT_FOUND_CODE


def test_contains_and_len() -> None:
    registry = ConversationRegistry()
    registry.create(_cid("c1"), agent_id="a")
    assert _cid("c1") in registry
    assert _cid("absent") not in registry
    assert "c1" not in registry  # a bare str is not a ConversationId
    assert len(registry) == 1


def test_ids_are_sorted() -> None:
    registry = ConversationRegistry()
    for cid in ("z", "a", "m"):
        registry.create(_cid(cid), agent_id="a")
    assert registry.ids() == ["a", "m", "z"]


def test_set_state_updates_state() -> None:
    registry = ConversationRegistry()
    conversation = registry.create(_cid("c1"), agent_id="a")
    conversation.set_state(ConversationState.SUSPENDED)
    assert conversation.state is ConversationState.SUSPENDED
