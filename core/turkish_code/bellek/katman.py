"""Memory layer/scope/kind vocabulary (doc 11 §4)."""

from __future__ import annotations

from enum import StrEnum


class MemoryLayer(StrEnum):
    """The five memory layers, each with distinct lifetime/scope (doc 11 §4)."""

    WORKING = "working"
    """Session lifetime, session scope — current conversation/active plan."""
    EPISODIC = "episodic"
    """Durable, workspace scope — summaries of past sessions/runs."""
    SEMANTIC = "semantic"
    """Durable, workspace (+ global opt) — distilled project/domain facts."""
    PROFILE = "profile"
    """Durable, global scope — stable facts about the user."""
    FEEDBACK = "feedback"
    """Durable, global + workspace — behavioral corrections, with rationale."""


class MemoryScope(StrEnum):
    """How widely a memory item is visible (doc 11 §4)."""

    SESSION = "session"
    WORKSPACE = "workspace"
    GLOBAL = "global"


class MemoryKind(StrEnum):
    """What kind of content a memory item holds (doc 11 §5)."""

    FACT = "fact"
    PREFERENCE = "preference"
    FEEDBACK = "feedback"
    EPISODE = "episode"
    ENTITY_NOTE = "entity-note"
