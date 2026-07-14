"""Skill lifecycle (doc 19 §10) — load, enable, disable, unload skills.

:class:`SkillLifecycle` owns the loaded-skill store and drives each skill's
:class:`SkillState`. It keeps the shared :class:`SkillRegistry` holding **only
enabled** skills — enabling registers a skill (making it invocable), disabling
withdraws it — so a disabled skill is genuinely un-invocable by the dispatcher
(doc 19 §10). Loading is fail-safe (duplicate ids rejected, doc 19 §7); a skill
that keeps failing can be quarantined ``FAILED`` and later recovered (doc 19 §14).
Skills are stateless knowledge, so there is nothing to activate beyond registry
membership.
"""

from __future__ import annotations

from turkish_code.yetenekler.hata import duplicate_skill, skill_not_found
from turkish_code.yetenekler.kayit import SkillRegistry
from turkish_code.yetenekler.modeller import SkillState
from turkish_code.yetenekler.protocol import Skill


class SkillLifecycle:
    """Drives skill state over the shared invocable registry (doc 19 §10)."""

    def __init__(self, registry: SkillRegistry) -> None:
        self._registry = registry
        self._loaded: dict[str, Skill] = {}
        self._states: dict[str, SkillState] = {}

    def load(self, skill: Skill) -> None:
        """Load a skill as DISABLED; reject a duplicate id (fail-safe, doc 19 §7)."""
        skill_id = skill.metadata.id
        if skill_id in self._loaded:
            raise duplicate_skill(skill_id)
        self._loaded[skill_id] = skill
        self._states[skill_id] = SkillState.DISABLED

    def enable(self, skill_id: str) -> None:
        """Make the skill invocable: register it, mark ENABLED (doc 19 §10)."""
        skill = self._require_loaded(skill_id)
        if self._states[skill_id] is SkillState.ENABLED:
            return
        self._registry.register(skill)
        self._states[skill_id] = SkillState.ENABLED

    def disable(self, skill_id: str) -> None:
        """Withdraw the skill from the invocable set, mark DISABLED (doc 19 §10)."""
        self._require_loaded(skill_id)
        if self._states[skill_id] is SkillState.ENABLED:
            self._registry.unregister(skill_id)
        self._states[skill_id] = SkillState.DISABLED

    def mark_failed(self, skill_id: str) -> None:
        """Quarantine the skill as FAILED, withdrawing it if enabled (doc 19 §14)."""
        self._require_loaded(skill_id)
        if self._states[skill_id] is SkillState.ENABLED:
            self._registry.unregister(skill_id)
        self._states[skill_id] = SkillState.FAILED

    def recover(self, skill_id: str) -> None:
        """Reset a FAILED skill to DISABLED so it can be retried (doc 19 §14)."""
        self._require_loaded(skill_id)
        if self._states[skill_id] is SkillState.FAILED:
            self._states[skill_id] = SkillState.DISABLED

    def unload(self, skill_id: str) -> Skill:
        """Withdraw (if enabled) then forget the skill entirely (doc 19 §10)."""
        skill = self._require_loaded(skill_id)
        if self._states[skill_id] is SkillState.ENABLED:
            self._registry.unregister(skill_id)
        del self._loaded[skill_id]
        del self._states[skill_id]
        return skill

    def state_of(self, skill_id: str) -> SkillState:
        """The skill's lifecycle state, or raise ``skill_not_found``."""
        self._require_loaded(skill_id)
        return self._states[skill_id]

    def is_enabled(self, skill_id: str) -> bool:
        """Whether the skill is loaded and ENABLED."""
        return self._states.get(skill_id) is SkillState.ENABLED

    def loaded_ids(self) -> list[str]:
        """All loaded skill ids, sorted."""
        return sorted(self._loaded)

    def enabled_ids(self) -> list[str]:
        """Every ENABLED skill id, sorted — the invocable set (doc 19 §10)."""
        return sorted(
            skill_id
            for skill_id, state in self._states.items()
            if state is SkillState.ENABLED
        )

    def _require_loaded(self, skill_id: str) -> Skill:
        skill = self._loaded.get(skill_id)
        if skill is None:
            raise skill_not_found(skill_id)
        return skill
