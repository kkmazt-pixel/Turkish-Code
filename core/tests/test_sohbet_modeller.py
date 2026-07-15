"""Tests for conversation models — id, role, message, turn, history."""

from __future__ import annotations

import pytest
from turkish_code.sohbet.modeller import (
    ConversationId,
    History,
    Message,
    Role,
    Turn,
)


def _turn(turn_id: str, user: str = "soru", agent: str = "cevap") -> Turn:
    return Turn(
        turn_id=turn_id,
        user=Message(role=Role.USER, content=user),
        agent=Message(role=Role.AGENT, content=agent),
    )


def test_role_wire_values() -> None:
    assert Role.USER.value == "user"
    assert Role.AGENT.value == "agent"
    assert Role.SYSTEM.value == "system"


def test_conversation_id_rejects_empty() -> None:
    with pytest.raises(ValueError, match="value must be non-empty"):
        ConversationId("")


def test_message_rejects_empty_content() -> None:
    with pytest.raises(ValueError, match="content must be non-empty"):
        Message(role=Role.USER, content="")


def test_turn_rejects_empty_id() -> None:
    with pytest.raises(ValueError, match="turn_id must be non-empty"):
        _turn("")


def test_turn_enforces_user_and_agent_roles() -> None:
    agent_msg = Message(role=Role.AGENT, content="x")
    with pytest.raises(ValueError, match="user must have role USER"):
        Turn(turn_id="t1", user=agent_msg, agent=agent_msg)
    user_msg = Message(role=Role.USER, content="x")
    with pytest.raises(ValueError, match="agent must have role AGENT"):
        Turn(turn_id="t1", user=user_msg, agent=user_msg)


def test_turn_is_immutable() -> None:
    turn = _turn("t1")
    with pytest.raises(AttributeError):
        turn.turn_id = "t2"  # type: ignore[misc]


def test_empty_history() -> None:
    history = History()
    assert history.turn_count == 0
    assert history.last() is None
    assert history.messages() == ()


def test_history_append_is_immutable() -> None:
    base = History()
    grown = base.append(_turn("t1"))
    assert base.turn_count == 0  # original unchanged
    assert grown.turn_count == 1
    last = grown.last()
    assert last is not None and last.turn_id == "t1"


def test_history_messages_flatten_in_order() -> None:
    history = History().append(_turn("t1", "s1", "a1")).append(_turn("t2", "s2", "a2"))
    assert [(m.role, m.content) for m in history.messages()] == [
        (Role.USER, "s1"),
        (Role.AGENT, "a1"),
        (Role.USER, "s2"),
        (Role.AGENT, "a2"),
    ]


def test_history_window_keeps_most_recent() -> None:
    history = History()
    for i in range(5):
        history = history.append(_turn(f"t{i}"))
    windowed = history.window(2)
    assert [t.turn_id for t in windowed.turns] == ["t3", "t4"]


def test_history_window_edge_sizes() -> None:
    history = History().append(_turn("t1")).append(_turn("t2"))
    assert history.window(0).turn_count == 0
    assert history.window(-1).turn_count == 0
    assert history.window(10).turn_count == 2  # beyond length → whole history
