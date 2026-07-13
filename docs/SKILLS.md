# SKILLS.md — Skill Authoring Guide (Yetenek Rehberi)

> Part of the **turkish.code Engineering Bible**. Canonical source of truth.
> **Status:** Canonical · **Version:** 1.0 · **Last updated:** 2026-07-12
> **Related:** [19_SKILLS_SYSTEM](./19_SKILLS_SYSTEM.md) (the internals) · [20_TOOL_SYSTEM](./20_TOOL_SYSTEM.md) · [23_PLUGIN_SYSTEM](./23_PLUGIN_SYSTEM.md) · [24_PERMISSION_SYSTEM](./24_PERMISSION_SYSTEM.md)

---

## 1. Purpose

The practical guide to **authoring skills** ([Yetenekler](./19_SKILLS_SYSTEM.md)) for turkish.code — the modular know-how packages loaded via progressive disclosure. [19_SKILLS_SYSTEM](./19_SKILLS_SYSTEM.md) documents the *runtime/mechanism*; **this** doc teaches *how to write a good skill*: the `SKILL.md` format, the critical art of the trigger `description`, progressive-disclosure structure, safety, and Turkish authoring. A well-authored skill fires exactly when relevant and guides the agent precisely; a poorly-authored one never fires or misfires.

## 2. Scope

The `SKILL.md` format + frontmatter, writing effective triggers, structuring for progressive disclosure, referencing tools safely, Turkish-language authoring, validation, and testing your skill. Out of scope: the runtime/matching mechanics ([19](./19_SKILLS_SYSTEM.md)), tool execution ([20](./20_TOOL_SYSTEM.md)), plugin packaging ([23](./23_PLUGIN_SYSTEM.md)).

## 3. What a Skill Is (and Isn't)

- A **skill** is *knowledge*: instructions + optional inert assets that teach the agent *how and when* to do something ([19](./19_SKILLS_SYSTEM.md) §3). Loaded only when relevant (progressive disclosure).
- A skill is **not** a tool ([20](./20_TOOL_SYSTEM.md) — tools *do*; skills *describe*). A skill is **not** a plugin ([23](./23_PLUGIN_SYSTEM.md) — the distributable container that may *include* skills).
- **Rule:** if you need to *execute* something, that's a tool ([20](./20_TOOL_SYSTEM.md)) invoked (permissioned) *from within* the skill's guidance — never ambient execution ([19](./19_SKILLS_SYSTEM.md) §8).

## 4. Skill Package Layout

```
skills/<skill-name>/
  SKILL.md          # REQUIRED: frontmatter + the know-how
  assets/           # optional: templates/examples (inert)
  scripts/          # optional: helper scripts — run ONLY via a permissioned tool (19 §8)
  references/       # optional: deeper docs loaded on demand (Level 2, progressive)
```
First-party skills live in `skills/`; third-party skills ship inside plugins ([23](./23_PLUGIN_SYSTEM.md)).

## 5. `SKILL.md` Frontmatter

```yaml
---
name: tauri-komut-ekle
description: >-
  Yeni bir Tauri Bridge komutu (Arayüz↔Kabuk) eklemek gerektiğinde kullan:
  ipc-schema'ya tanım ekleme, Rust handler yazma ve TS binding üretimini kapsar.
version: 1.0.0
locale: tr
allowed-tools: [fs.read, fs.write]     # subset of tools this skill may reference (20/24)
scope: workspace                        # workspace | global
requires: []                            # optional skill deps (no cycles)
---
```

- **`name`** — kebab-case, matches the folder; add to [44_GLOSSARY](./44_GLOSSARY.md) if it introduces a term.
- **`description`** — the **trigger** (§6). The single most important field.
- **`allowed-tools`** — intersected with the granting agent's grants + runtime permissions ([19](./19_SKILLS_SYSTEM.md) §15, [24](./24_PERMISSION_SYSTEM.md)); keep it minimal (PR-3).
- **`locale`** — `tr` for Turkish skills (default); content Turkish-correct (PR-12).

## 6. Writing the Trigger `description` (The Art)

The runtime matches the current task against every skill's `description` (embedding + keyword, [19](./19_SKILLS_SYSTEM.md) §6). A great description is **specific about *when* to use the skill**:

- **Do:** name the concrete situation + what it covers. *"Türkçe yerelleştirme/çeviri işlerinde kullan: i18n anahtarları, İ/ı büyük-küçük harf kuralları ve çoğullaştırma."*
- **Don't:** be vague. *"Yerelleştirme yardımı."* (too broad → misfires or never fires).
- **Include trigger words** a task would naturally contain (e.g., "test", "migrasyon", "commit mesajı", "Tauri komut").
- **State boundaries** if needed ("... sadece frontend metinleri için").
- A weak `description` is the #1 reason a skill never fires ([19](./19_SKILLS_SYSTEM.md) §13).

## 7. Structuring for Progressive Disclosure

Three levels ([19](./19_SKILLS_SYSTEM.md) §5) — write with them in mind:
- **Level 0 (always loaded):** `name` + `description` only. Keep the description tight — it's always in context.
- **Level 1 (on trigger):** the `SKILL.md` body — the core steps/rules. Keep it focused; put the essentials here.
- **Level 2 (on demand):** heavy detail in `references/*.md`, linked from the body ("Ayrıntılı İ/ı kuralları için references/casing.md'ye bak"). The agent pulls these only if needed → keeps the base context lean (PR-14).

Structure the body so the agent gets the gist at Level 1 and dives to Level 2 only when the task demands it.

## 8. Writing the Body (Know-How)

- **Turkish, precise, actionable.** Numbered steps, gotchas, and *why*.
- **Reference project docs/tools** where relevant (`fs.write` ile uygula — doc 20; snapshot otomatik alınır — doc 27).
- **Cite invariants** the agent must respect (e.g., "kullanıcı metinlerini asla JS `toUpperCase` ile dönüştürme; locale yardımcısını kullan — [03](./03_UI_SYSTEM.md) §11").
- **Don't** duplicate a whole subsystem doc — link to it ([40](./40_DOCUMENTATION_RULES.md)).

## 9. Safety Rules for Skills

- **No ambient execution.** Scripts run only via a permissioned tool ([19](./19_SKILLS_SYSTEM.md) §8, [20](./20_TOOL_SYSTEM.md)/[24](./24_PERMISSION_SYSTEM.md)).
- **Least tools.** `allowed-tools` is the minimum; it's intersected with the agent's grants — a skill can't grant itself power ([19](./19_SKILLS_SYSTEM.md) §15).
- **Third-party skills are untrusted** ([23](./23_PLUGIN_SYSTEM.md)); their text can't trigger a side effect without a permissioned tool.
- **No secrets** in skill content/assets ([34](./34_API_KEYS.md)/[30](./30_SECURITY.md)).
- **No network assumption** — a skill must not require egress to be useful (PR-6); if it references an egress tool, that tool is off-by-default/consented ([32](./32_OFFLINE_FIRST.md)).

## 10. Turkish Authoring

- Correct casing/glyphs (İ ı ş ğ ç ö ü) throughout (PR-12); if the skill *teaches* casing, get the edge cases right (İstanbul→istanbul, IĞDIR→ığdır) and put the full table in `references/`.
- Natural, professional Turkish tone (matches the product voice, [04](./04_TURKISH_DESIGN_LANGUAGE.md) §12).

## 11. Validation

Skills are validated at registry load ([19](./19_SKILLS_SYSTEM.md) §7): required frontmatter present, `allowed-tools` ⊆ known tools, no `requires` cycles, parseable body. Invalid skills are rejected (fail-safe), excluded, with a clear error — they never crash startup.

## 12. Testing Your Skill

- **Trigger test:** given representative tasks, does your skill fire (and irrelevant tasks not trigger it)? ([19](./19_SKILLS_SYSTEM.md) §17)
- **Effectiveness:** when loaded, does it actually guide the agent to the right, safe outcome?
- **Progressive-disclosure:** Level-2 references load only when needed.
- **Turkish content:** casing/wording correct.
- Add these to the skill/plugin test suite ([35](./35_TESTING.md)).

## 13. Configuration

- Enable/disable skills, per-workspace skill sets, auto-trigger sensitivity, max skills per run are configurable ([33](./33_CONFIGURATION.md)/[17](./17_EFFORT_MODES.md)). Keep your skill useful under the default budget.

## 14. Dependencies

- Matched via [14_EMBEDDINGS](./14_EMBEDDINGS.md), loaded by [15_REASONING_ENGINE](./15_REASONING_ENGINE.md), may reference [20_TOOL_SYSTEM](./20_TOOL_SYSTEM.md) under [24_PERMISSION_SYSTEM](./24_PERMISSION_SYSTEM.md), distributed via [23_PLUGIN_SYSTEM](./23_PLUGIN_SYSTEM.md), governed by [19_SKILLS_SYSTEM](./19_SKILLS_SYSTEM.md).

## 15. Edge Cases

- **Overlapping skills:** multiple fire — the runtime loads top-K by relevance ([19](./19_SKILLS_SYSTEM.md) §13); make yours distinct so it's chosen for the right tasks.
- **Skill references a missing tool:** validation warns; at runtime the tool just isn't available — write the skill to degrade.
- **Skill too big:** move detail to `references/` (Level 2); keep Level 1 focused.
- **Conflicting guidance with another skill:** mark conflicts / narrow your `scope`/`description`.
- **Turkish edge cases in a casing skill:** cover İ/ı fully in `references/`.

## 16. Failure Recovery

- A skill that repeatedly causes failures can be auto-disabled ([19](./19_SKILLS_SYSTEM.md) §14); fix the trigger/body and re-enable. Skills are stateless knowledge — nothing to recover but re-indexing.

## 17. Security

- Skills are inert knowledge + optional inert assets; all *doing* is via permissioned tools ([19](./19_SKILLS_SYSTEM.md) §15, [20](./20_TOOL_SYSTEM.md)/[24](./24_PERMISSION_SYSTEM.md)). Loading a skill never egresses. Third-party skill content is untrusted; malicious *text* can't cause an effect without a gate. No secrets in skills. See [30_SECURITY](./30_SECURITY.md).

## 18. Performance

- Level-0 (description) is tiny and always loaded; keep it concise. Level-1/2 loads are budgeted ([17](./17_EFFORT_MODES.md)). Many skills are fine — only *loaded* skills cost tokens ([19](./19_SKILLS_SYSTEM.md) §16, [31](./31_PERFORMANCE.md)).

## 19. Future Extensions

- In-app skill authoring; skill marketplace via plugins ([23](./23_PLUGIN_SYSTEM.md)); trigger-rate analytics to refine descriptions; versioned skill deps; auto-suggested skills from repeated patterns ([19](./19_SKILLS_SYSTEM.md) §18).

## 20. Example Skill

`skills/turkce-commit/SKILL.md`:
```yaml
---
name: turkce-commit
description: >-
  Git commit mesajı yazarken kullan: mesajları Türkçe, kısa özet + gövde
  biçiminde ve doğru büyük-küçük harfle üretir.
version: 1.0.0
locale: tr
allowed-tools: [fs.read]
scope: global
---
```
Body: Turkish commit-message conventions (özet ≤ 50 karakter, gövde neden/nasıl), casing rules (link [03](./03_UI_SYSTEM.md) §11), examples; references the reasoning to *propose* the message (the actual commit runs via a permissioned tool, not the skill).

## 21. Anti-Patterns

- Vague `description` (never/wrongly fires).
- Encoding executable behavior in the skill instead of a tool.
- Force-loading big content (defeats progressive disclosure).
- Over-broad `allowed-tools`.
- Duplicating a subsystem doc instead of linking.
- Assuming network availability.
- Non-Turkish content / broken casing.

## 22. Things That Must Never Happen

1. A skill executes code without a permissioned tool ([19](./19_SKILLS_SYSTEM.md)/[20](./20_TOOL_SYSTEM.md)/[24](./24_PERMISSION_SYSTEM.md)).
2. A skill grants itself more tool power than the agent has.
3. A skill contains secrets or requires egress to be useful.
4. A malformed skill crashes startup (must be rejected/excluded).
5. Skill content mangles Turkish casing/glyphs.

## 23. Relationship With Other Subsystems

Authoring format for [19_SKILLS_SYSTEM](./19_SKILLS_SYSTEM.md); matched by [14_EMBEDDINGS](./14_EMBEDDINGS.md); loaded by [15_REASONING_ENGINE](./15_REASONING_ENGINE.md); references [20_TOOL_SYSTEM](./20_TOOL_SYSTEM.md) under [24_PERMISSION_SYSTEM](./24_PERMISSION_SYSTEM.md); scoped by [18_AGENT_SYSTEM](./18_AGENT_SYSTEM.md); distributed by [23_PLUGIN_SYSTEM](./23_PLUGIN_SYSTEM.md); tested per [35_TESTING](./35_TESTING.md); doc rules per [40_DOCUMENTATION_RULES](./40_DOCUMENTATION_RULES.md).

## 24. Migration Considerations

- `SKILL.md` frontmatter is versioned ([19](./19_SKILLS_SYSTEM.md) §23); new optional fields are additive (PR-18). Trigger-matching algorithm changes are transparent to skill content. Renames follow the glossary/registry process. Deprecated skills are marked, not silently deleted.
