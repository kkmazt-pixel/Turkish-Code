"""Tests for the memory record schema and vocabulary (doc 11 §4/§5/§12)."""

from __future__ import annotations

from datetime import UTC, datetime

from turkish_code.bellek.durum import MemoryState
from turkish_code.bellek.katman import MemoryKind, MemoryLayer, MemoryScope
from turkish_code.bellek.kayit import MemoryItem
from turkish_code.bellek.kimlik import MemoryId

_NOW = datetime(2026, 7, 13, tzinfo=UTC)


def _item(**overrides: object) -> MemoryItem:
    base = dict(
        id=MemoryId("m1"),
        layer=MemoryLayer.FEEDBACK,
        scope=MemoryScope.GLOBAL,
        kind=MemoryKind.FEEDBACK,
        state=MemoryState.PINNED,
        title="Commit mesajları Türkçe",
        body="Kullanıcı commit mesajlarını Türkçe istiyor.",
        links=(),
        embedding_ref=None,
        salience=0.9,
        source=None,
        pinned=True,
        created_at=_NOW,
        last_used_at=_NOW,
        use_count=0,
        confidence=1.0,
    )
    base.update(overrides)
    return MemoryItem(**base)  # type: ignore[arg-type]


def test_feedback_memory_example_from_doc_11() -> None:
    item = _item()
    assert item.layer is MemoryLayer.FEEDBACK
    assert item.pinned is True
    assert item.ttl is None


def test_ttl_defaults_to_none() -> None:
    assert _item().ttl is None


def test_all_documented_layers_are_representable() -> None:
    assert {layer.value for layer in MemoryLayer} == {
        "working",
        "episodic",
        "semantic",
        "profile",
        "feedback",
    }


def test_all_documented_states_are_representable() -> None:
    assert {state.value for state in MemoryState} == {
        "candidate",
        "active",
        "pinned",
        "dormant",
        "superseded",
        "purged",
    }
