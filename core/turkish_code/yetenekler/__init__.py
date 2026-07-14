"""Yetenekler — the Skill Runtime (doc 19).

A thin, reusable runtime for *running* skills — small, independent units of work
that sit between Tools and Agents (doc 19 §1). A skill is not a tool, not an
agent, not a workflow: it defines how it runs, not how to plan (no reasoning /
planner / workflow / council here). This package defines the skill contract
(:class:`Skill`), its metadata, and the request/result value objects; the
registry, context, dispatcher, lifecycle, and composition build on them across
later increments. The runtime depends only on the :class:`Skill` Protocol (DIP);
skills reach subsystems only through their context (doc 19 §8/§15).
"""

from turkish_code.yetenekler.baglam import (
    CancellationToken,
    CollectingEventSink,
    NullEventSink,
    SkillContext,
    SkillEventSink,
    SkillExecutionContext,
)
from turkish_code.yetenekler.dagitici import CancellationRegistry, SkillDispatcher
from turkish_code.yetenekler.hata import (
    SKILL_CANCELLED_CODE,
    SKILL_DUPLICATE_CODE,
    SKILL_FAILED_CODE,
    SKILL_NOT_FOUND_CODE,
    SKILL_TIMEOUT_CODE,
    SKILL_TOOL_OUT_OF_SCOPE_CODE,
    duplicate_skill,
    skill_not_found,
    tool_out_of_scope,
)
from turkish_code.yetenekler.kayit import SkillRegistry
from turkish_code.yetenekler.kompozisyon import SkillRuntime, build_skill_runtime
from turkish_code.yetenekler.modeller import (
    SkillChunk,
    SkillMetadata,
    SkillRequest,
    SkillResult,
    SkillScope,
    SkillState,
)
from turkish_code.yetenekler.protocol import Skill
from turkish_code.yetenekler.yasam import SkillLifecycle

__all__ = [
    "Skill",
    "SkillContext",
    "SkillExecutionContext",
    "CancellationToken",
    "SkillMetadata",
    "SkillRequest",
    "SkillResult",
    "SkillChunk",
    "SkillScope",
    "SkillState",
    "SkillRegistry",
    "SkillLifecycle",
    "SkillRuntime",
    "build_skill_runtime",
    "SkillDispatcher",
    "CancellationRegistry",
    "SkillEventSink",
    "NullEventSink",
    "CollectingEventSink",
    "SKILL_NOT_FOUND_CODE",
    "SKILL_DUPLICATE_CODE",
    "SKILL_TOOL_OUT_OF_SCOPE_CODE",
    "SKILL_TIMEOUT_CODE",
    "SKILL_CANCELLED_CODE",
    "SKILL_FAILED_CODE",
    "skill_not_found",
    "duplicate_skill",
    "tool_out_of_scope",
]
