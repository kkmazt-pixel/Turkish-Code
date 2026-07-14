"""Skill runtime value objects (doc 19 §4) — metadata, request, result.

The declarative pieces the Skill Runtime is built from: a :class:`SkillMetadata`
record (the ``SKILL.md`` frontmatter — id, trigger description, referenced tools,
scope, doc 19 §4) and the :class:`SkillRequest`/:class:`SkillResult` pair that
frames one invocation. A skill is a small, reusable, independent unit of work —
not a tool, not an agent, not a workflow (it defines how it *runs*, never how to
plan). Pure data here; registry/dispatch/lifecycle live in their own modules.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum


class SkillScope(StrEnum):
    """The reuse scope a skill is authored for (doc 19 §4)."""

    WORKSPACE = "workspace"
    GLOBAL = "global"


class SkillState(StrEnum):
    """A loaded skill's lifecycle state (doc 19 §10).

    A skill loads ``DISABLED`` (registered, not invocable); ``ENABLED`` means it
    is live in the invocable registry; ``FAILED`` marks a skill quarantined after
    repeated failures until recovered/reloaded (doc 19 §14).
    """

    DISABLED = "disabled"
    ENABLED = "enabled"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class SkillMetadata:
    """A skill's declarative contract — the ``SKILL.md`` frontmatter (doc 19 §4).

    Attributes:
        id: Stable skill id the registry keys on, e.g. ``"tauri-komut-yaz"``.
        description: The trigger surface — precisely *when* to use the skill
            (doc 19 §4/§6); indexed for discovery.
        allowed_tools: Tool names this skill may reference — a subset, least
            privilege (doc 19 §4/§15); intersected with the agent's grants.
        requires: Ids of skills this one depends on (doc 19 §4).
        scope: Whether the skill is workspace- or global-scoped (doc 19 §4).
        timeout_ms: Upper bound on one invocation, must be positive.
        version: Additive frontmatter version of this skill (doc 19 §23).
    """

    id: str
    description: str
    allowed_tools: frozenset[str] = field(default_factory=frozenset)
    requires: frozenset[str] = field(default_factory=frozenset)
    scope: SkillScope = SkillScope.WORKSPACE
    timeout_ms: int = 30_000
    version: int = 1

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("SkillMetadata.id must be non-empty")
        if not self.description:
            raise ValueError("SkillMetadata.description must be non-empty")
        if self.timeout_ms <= 0:
            raise ValueError(
                f"SkillMetadata.timeout_ms must be positive, got {self.timeout_ms}"
            )
        if self.version < 1:
            raise ValueError(f"SkillMetadata.version must be >= 1, got {self.version}")

    def allows_tool(self, tool_name: str) -> bool:
        """Whether the skill may reference ``tool_name`` (doc 19 §4/§15)."""
        return tool_name in self.allowed_tools


@dataclass(frozen=True, slots=True)
class SkillRequest:
    """One skill invocation's inputs (doc 19 §9) — the target, inputs, and ids.

    Attributes:
        skill_id: The skill to invoke; resolved against the registry (doc 19 §7).
        inputs: The skill's structured inputs as the caller produced them.
        invocation_id: Unique id for this invocation — correlates cancellation,
            results, and trace (doc 19 §6).
        run_id: The agent run this invocation belongs to (provenance), or ``None``.
    """

    skill_id: str
    inputs: Mapping[str, object]
    invocation_id: str
    run_id: str | None = None


@dataclass(frozen=True, slots=True)
class SkillResult:
    """A skill invocation's typed result (doc 19 §9) — the final output.

    Failure is a raised :class:`~turkish_code.hata.AppError`, never a result
    value, so a ``SkillResult`` always denotes a completed invocation.

    Attributes:
        invocation_id: Echoes :attr:`SkillRequest.invocation_id` for correlation.
        output: The skill-specific, JSON-serialisable result payload.
    """

    invocation_id: str
    output: object


@dataclass(frozen=True, slots=True)
class SkillChunk:
    """A streamed fragment of a skill invocation's output (doc 19 §9).

    A skill emits zero or more of these before its final :class:`SkillResult`;
    they map to ``$/progress`` notifications on the wire (doc 10 §11).

    Attributes:
        invocation_id: Correlates the chunk with its invocation.
        delta: The incremental output text for this fragment (Turkish).
    """

    invocation_id: str
    delta: str
