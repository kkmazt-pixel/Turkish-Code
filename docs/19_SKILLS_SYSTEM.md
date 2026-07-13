# 19 — Skills System (Yetenekler)

> Part of the **turkish.code Engineering Bible**. Canonical source of truth.
> **Status:** Canonical · **Version:** 1.0 · **Last updated:** 2026-07-12
> **Owner:** Çekirdek `yetenek/` + `skills/` (content)
> **Related:** [15_REASONING_ENGINE](./15_REASONING_ENGINE.md) · [18_AGENT_SYSTEM](./18_AGENT_SYSTEM.md) · [20_TOOL_SYSTEM](./20_TOOL_SYSTEM.md) · [23_PLUGIN_SYSTEM](./23_PLUGIN_SYSTEM.md) · [SKILLS.md](./SKILLS.md)

---

## 1. Purpose

Defines **Yetenekler** (Skills): modular, declarative capability packages that extend what the agent *knows how to do* — instructions + optional assets/scripts, loaded **on demand** via progressive disclosure when relevant to the task. Skills let turkish.code carry deep, specialized know-how (e.g., "write a Tauri command", "migrate an SQLite schema", "review Turkish localization") without bloating every prompt. They are the primary, low-risk extension mechanism, distinct from tools ([20](./20_TOOL_SYSTEM.md), executable capabilities) and plugins ([23](./23_PLUGIN_SYSTEM.md), distributable bundles).

## 2. Scope

The skill package format, discovery/triggering (progressive disclosure), loading into context, skill-provided assets/scripts, authoring/validation, and the skill registry. Out of scope: executable tool mechanics ([20](./20_TOOL_SYSTEM.md)), plugin packaging/sandbox ([23](./23_PLUGIN_SYSTEM.md)), the reasoning loop ([15](./15_REASONING_ENGINE.md)), and the authoring guide for skill writers ([SKILLS.md](./SKILLS.md)).

## 3. Goals

1. Package specialized know-how as **reusable, declarative** units (PR-11, PR-13).
2. **Progressive disclosure:** load a skill's full content only when relevant, keeping context lean (PR-14 budget discipline) — the model sees only skill *names/descriptions* until one is triggered.
3. **Composable** with agents ([18](./18_AGENT_SYSTEM.md)) and tools ([20](./20_TOOL_SYSTEM.md)): a skill can reference tools and be scoped to agents.
4. **Safe:** skills are (mostly) instructions/knowledge; any executable asset runs through the tool/permission system, never with ambient privilege ([24](./24_PERMISSION_SYSTEM.md)).
5. **Turkish-first** authoring and content (PR-12).

### Non-Goals
- A skill is not a tool (skills describe *how/when*; tools *do*). A skill is not a plugin (plugins are the distributable container that may *include* skills, [23](./23_PLUGIN_SYSTEM.md)).

## 4. Skill Package Format

A skill lives in `skills/<skill-name>/` (first-party) or is contributed by a plugin ([23](./23_PLUGIN_SYSTEM.md)). Structure:

```
skills/<name>/
  SKILL.md          # required: frontmatter + instructions (the skill)
  assets/           # optional: templates, reference files, examples
  scripts/          # optional: helper scripts (run ONLY via tools/permission, §8)
  references/       # optional: deeper docs loaded on demand (progressive disclosure)
```

`SKILL.md` frontmatter (the metadata the registry indexes):

```yaml
---
name: tauri-komut-yaz
description: >-
  Yeni bir Tauri Bridge komutu eklemek gerektiğinde kullan — ipc-schema'ya
  tanım ekleme, Rust handler ve TS binding üretimi dahil.   # TRIGGER text (critical)
version: 1.0.0
locale: tr
allowed-tools: [fs.read, fs.write]        # tools this skill may reference (subset)
scope: [workspace|global]
requires?: [otherSkillName]                # optional skill deps
---
```

- The **`description` is the trigger surface**: it must precisely say *when* to use the skill (that is what the discovery step matches on). A vague description = a skill that never fires or fires wrongly. ([SKILLS.md](./SKILLS.md) teaches writing these.)
- The **body** is the actual know-how (steps, rules, gotchas), in Turkish, referencing project docs/tools where helpful.

## 5. Progressive Disclosure (Core Mechanism)

```
Level 0 (always in context):  skill name + description (cheap, all skills)
Level 1 (on trigger):         full SKILL.md body loaded into context
Level 2 (on demand):          referenced files under references/ pulled in as needed
```

- At context assembly ([15](./15_REASONING_ENGINE.md) §6, [13](./13_RAG_SYSTEM.md) §9), the engine sees only Level-0 metadata for all available skills. When the task matches a skill's trigger (semantic + keyword match against `description`, plus explicit invocation), the engine loads Level 1; deeper references load Level 2 only if the skill body points to them.
- This keeps the base prompt small regardless of how many skills exist (dozens of skills cost ~a line each until used) — essential for budget discipline (PR-14) and offline small-model contexts (PR-6).

## 6. Discovery & Triggering

- **Automatic:** the engine matches the current goal against skill `description`s (embedding similarity [14] + keyword) and loads the top relevant skill(s), bounded by budget ([17](./17_EFFORT_MODES.md)).
- **Explicit:** the user (or an agent) can name a skill to force-load it.
- **Agent-scoped:** an `AgentDef` ([18](./18_AGENT_SYSTEM.md)) may restrict which skills a sub-agent can load.
- Triggering is recorded in the trace ([15](./15_REASONING_ENGINE.md) §5) so the user sees *which skill guided the work*.

## 7. Skill Registry

- A registry ([09](./09_PYTHON_BACKEND.md) DI, `yetenek/registry.py`) indexes all discovered skills (first-party `skills/` + plugin-contributed [23]) at startup and on change: parses/validates frontmatter, embeds descriptions for matching, resolves `requires`.
- Invalid skills (bad frontmatter, missing fields) are rejected with a clear error and excluded (fail-safe, [38](./38_ERROR_HANDLING.md)) — never crash startup.

## 8. Skill-Provided Scripts/Assets (Safety)

- A skill may ship `scripts/` and `assets/`. **Scripts do not run with ambient privilege.** If a skill's workflow needs to execute a script, it does so **through a tool** ([20](./20_TOOL_SYSTEM.md), e.g., `shell.exec`) which is **permission-gated** ([24](./24_PERMISSION_SYSTEM.md)) and snapshot/timeline-tracked. A skill is knowledge + optional inert assets; the *doing* is always via tools. (PR-2/PR-3.)
- Third-party (plugin) skill assets are treated as untrusted content ([23](./23_PLUGIN_SYSTEM.md), [30](./30_SECURITY.md)).

## 9. Architecture / Data Flow

```
skills/ + plugin skills ─▶ registry (parse/validate/embed) ─▶ Level-0 catalog
                                                                │
task ─▶ Muhakeme (15) context assembly ─▶ match triggers ─▶ load Level 1/2 ─▶ prompt
                                                                │
skill body may reference tools (20) ─▶ executed under permission (24)
```

## 10. Lifecycle

```
startup/change → discover → validate → embed descriptions → registry ready
run → match → load (progressive) → guide reasoning → trace which skill fired
authoring → write SKILL.md → validate → (bundle in plugin for distribution, 23)
```

## 11. Configuration

- Enable/disable skills, per-workspace skill sets, auto-trigger sensitivity, and max skills loaded per run (budget) are configurable ([33](./33_CONFIGURATION.md)/[17](./17_EFFORT_MODES.md)).

## 12. Dependencies

- [14_EMBEDDINGS](./14_EMBEDDINGS.md) (description matching), [15_REASONING_ENGINE](./15_REASONING_ENGINE.md) (loads them), [20_TOOL_SYSTEM](./20_TOOL_SYSTEM.md)/[24_PERMISSION_SYSTEM](./24_PERMISSION_SYSTEM.md) (script execution), [23_PLUGIN_SYSTEM](./23_PLUGIN_SYSTEM.md) (distribution), [SKILLS.md](./SKILLS.md) (authoring rules).

## 13. Edge Cases

- **Overlapping triggers:** multiple skills match — load top-K by relevance within budget; avoid loading contradictory skills (registry can mark conflicts).
- **Skill never triggers:** usually a weak `description`; authoring guidance ([SKILLS.md](./SKILLS.md)) + analytics on trigger rates help.
- **Skill bloat:** many skills is fine (Level-0 is cheap); only loaded skills cost real tokens.
- **Malformed skill:** rejected at registry load, excluded, error surfaced — startup continues.
- **Skill references a missing tool:** validation warns; at runtime the tool call simply isn't available (permission/registry denies).
- **Circular `requires`:** detected at load; rejected.
- **Turkish content correctness:** authored in Turkish with correct casing; validated ([SKILLS.md](./SKILLS.md)).

## 14. Failure Recovery

- Registry rebuild is idempotent. A skill that causes repeated failures can be auto-disabled with a notice (fail-safe). Skills never hold critical state (they're stateless knowledge), so there is nothing to recover beyond re-indexing.

## 15. Security

- Skills are primarily inert knowledge; **no ambient execution** (§8). Plugin/third-party skills are untrusted: their assets/scripts run only via permissioned tools, and their `allowed-tools` are intersected with the granting agent's tool grants ([18](./18_AGENT_SYSTEM.md)) and the permission model ([24](./24_PERMISSION_SYSTEM.md)). Malicious skill *text* (e.g., prompt-injection instructions) is mitigated: skill content is trusted only to the extent of its source, and can never itself trigger a side effect without a permissioned tool ([30](./30_SECURITY.md)). Loading a skill never egresses.

## 16. Performance

- Level-0 catalog is tiny and cached; embedding matching is fast ([14](./14_EMBEDDINGS.md)); Level-1/2 loads are budgeted. Skill matching adds negligible latency to context assembly ([31](./31_PERFORMANCE.md)).

## 17. Testing Strategy

- **Trigger tests:** given representative tasks, the intended skill(s) fire and irrelevant ones don't.
- **Validation tests:** malformed skills are rejected without crashing.
- **Progressive-disclosure tests:** only Level-0 in base context; Level-1 loads on trigger; token cost scales with usage not catalog size.
- **Scoping tests:** agent skill restrictions honored; `allowed-tools` intersection enforced.
- **Turkish content tests.** See [35_TESTING](./35_TESTING.md).

## 18. Future Extensions

- Skill marketplaces via plugins ([23](./23_PLUGIN_SYSTEM.md)); user-authored skills from within the app; skill analytics (trigger/effectiveness); auto-suggested new skills from repeated patterns; versioned skill dependencies.

## 19. Examples

`skills/turkce-yerellestirme/SKILL.md` — triggers on localization tasks; body encodes the Turkish casing rules (PR-12), the i18n key conventions ([03](./03_UI_SYSTEM.md) §11), and points to `references/casing.md` (Level 2) with the İ/ı edge cases; references the `fs.write` tool for applying changes (permissioned).

## 20. Anti-Patterns

- Vague `description` (skill never/wrongly triggers).
- Loading full skill bodies into every prompt (defeats progressive disclosure/budget).
- A skill executing scripts with ambient privilege (must go through tools/permission).
- Encoding executable behavior in a skill instead of a tool.
- Trusting plugin skill content as if first-party.

## 21. Things That Must Never Happen

1. A skill executes code without going through a permissioned tool.
2. Full skill bodies are force-loaded into context regardless of relevance (budget blowup).
3. A malformed/plugin skill crashes startup or gains privilege beyond the granting agent.
4. Skill loading causes network egress.
5. Which skill guided a run is hidden from the trace/user.

## 22. Relationship With Other Subsystems

Loaded by [15_REASONING_ENGINE](./15_REASONING_ENGINE.md); scoped by [18_AGENT_SYSTEM](./18_AGENT_SYSTEM.md); references [20_TOOL_SYSTEM](./20_TOOL_SYSTEM.md) under [24_PERMISSION_SYSTEM](./24_PERMISSION_SYSTEM.md); matched via [14_EMBEDDINGS](./14_EMBEDDINGS.md); distributed by [23_PLUGIN_SYSTEM](./23_PLUGIN_SYSTEM.md); authored per [SKILLS.md](./SKILLS.md); budgeted by [17_EFFORT_MODES](./17_EFFORT_MODES.md).

## 23. Migration Considerations

- `SKILL.md` frontmatter is versioned; new optional fields are additive (PR-18). Skill renames follow the terminology/registry update process. Changing the trigger-matching algorithm ([14](./14_EMBEDDINGS.md)) is transparent to skill content. Deprecated skills are marked, not silently deleted.
