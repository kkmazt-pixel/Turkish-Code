"""Skill registry (doc 19 §7) — the discovered skills, indexed for lookup.

Holds every registered skill keyed by its metadata id. Registration is
**fail-safe**: a duplicate id is rejected (doc 19 §7). Skills are selectable by
**scope** (workspace/global), and :meth:`catalog` exposes the Level-0 metadata
surface used for discovery (doc 19 §5). The registry owns storage and lookup
only; it runs nothing and never mutates other registries.
"""

from __future__ import annotations

from collections.abc import Iterable

from turkish_code.yetenekler.hata import duplicate_skill, skill_not_found
from turkish_code.yetenekler.modeller import SkillMetadata, SkillScope
from turkish_code.yetenekler.protocol import Skill


class SkillRegistry:
    """An in-memory id→:class:`Skill` registry (doc 19 §7)."""

    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        """Add ``skill``; reject a duplicate id (fail-safe, doc 19 §7)."""
        skill_id = skill.metadata.id
        if skill_id in self._skills:
            raise duplicate_skill(skill_id)
        self._skills[skill_id] = skill

    def register_all(self, skills: Iterable[Skill]) -> None:
        """Register each skill in order; the first duplicate aborts (doc 19 §7)."""
        for skill in skills:
            self.register(skill)

    def unregister(self, skill_id: str) -> None:
        """Remove the skill registered as ``skill_id``, or raise ``skill_not_found``.

        The inverse of :meth:`register` — lets the lifecycle withdraw a skill
        from the invocable set when it is disabled/unloaded (doc 19 §10).
        """
        if skill_id not in self._skills:
            raise skill_not_found(skill_id)
        del self._skills[skill_id]

    def resolve(self, skill_id: str) -> Skill:
        """The skill registered as ``skill_id``, or raise ``skill_not_found``."""
        skill = self._skills.get(skill_id)
        if skill is None:
            raise skill_not_found(skill_id)
        return skill

    def get(self, skill_id: str) -> Skill | None:
        """The skill registered as ``skill_id``, or ``None`` if absent."""
        return self._skills.get(skill_id)

    def __contains__(self, skill_id: object) -> bool:
        return isinstance(skill_id, str) and skill_id in self._skills

    def __len__(self) -> int:
        return len(self._skills)

    def ids(self) -> list[str]:
        """All registered skill ids, sorted."""
        return sorted(self._skills)

    def catalog(self) -> list[SkillMetadata]:
        """Every skill's metadata, id-sorted — the Level-0 catalog (doc 19 §5)."""
        return [self._skills[skill_id].metadata for skill_id in sorted(self._skills)]

    def by_scope(self, scope: SkillScope) -> list[Skill]:
        """Every skill authored for ``scope``, id-sorted (doc 19 §4)."""
        return [
            self._skills[skill_id]
            for skill_id in sorted(self._skills)
            if self._skills[skill_id].metadata.scope is scope
        ]

    def version_of(self, skill_id: str) -> int:
        """The registered version of ``skill_id`` (doc 19 §23), or raise not-found."""
        return self.resolve(skill_id).metadata.version
