"""Tests for entity identity (doc 12 §5)."""

from __future__ import annotations

from turkish_code.graf.kimlik import compute_entity_id


def test_same_inputs_yield_same_id() -> None:
    a = compute_entity_id("python", "pkg.module.func", 2)
    b = compute_entity_id("python", "pkg.module.func", 2)
    assert a == b


def test_different_qualified_name_yields_different_id() -> None:
    a = compute_entity_id("python", "pkg.module.func", 2)
    b = compute_entity_id("python", "pkg.module.other_func", 2)
    assert a != b


def test_different_arity_yields_different_id() -> None:
    """Overloaded/differently-aritied symbols must not collide."""
    a = compute_entity_id("python", "pkg.module.func", 1)
    b = compute_entity_id("python", "pkg.module.func", 2)
    assert a != b


def test_different_language_yields_different_id() -> None:
    a = compute_entity_id("python", "pkg.module.func", 1)
    b = compute_entity_id("typescript", "pkg.module.func", 1)
    assert a != b


def test_id_is_a_stable_string() -> None:
    entity_id = compute_entity_id("python", "a.b.c", 0)
    assert isinstance(entity_id.value, str)
    assert len(entity_id.value) > 0
