"""The skill contract (doc 19 §4) — interface only.

:class:`Skill` is the one interface every runnable skill implements: a
declarative :class:`~turkish_code.yetenekler.modeller.SkillMetadata` plus an async
:meth:`Skill.run`. The runtime (registry/dispatcher/lifecycle) depends only on
this Protocol, never on concrete skills — so first-party and (future)
plugin-contributed skills plug in without the runtime changing (doc 19 §7, DIP).
A skill defines how it *runs*, never how to plan (no reasoning/workflow here).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from turkish_code.yetenekler.baglam import SkillContext
from turkish_code.yetenekler.modeller import SkillMetadata, SkillRequest, SkillResult


@runtime_checkable
class Skill(Protocol):
    """A single runnable skill (doc 19 §4)."""

    @property
    def metadata(self) -> SkillMetadata:
        """The skill's declarative contract (doc 19 §4)."""
        ...

    async def run(self, request: SkillRequest, context: SkillContext) -> SkillResult:
        """Execute the skill for ``request`` and return its result (doc 19 §9).

        Implementations work only through ``context`` — the scoped runtime
        handles, cancellation, and streaming (doc 19 §8/§15) — never touching
        Storage/Provider/Tool/Agent subsystems directly. Failure is raised as a
        typed :class:`~turkish_code.hata.AppError` (doc 38 §7) which the
        dispatcher surfaces; a returned :class:`SkillResult` always denotes
        success.
        """
        ...
