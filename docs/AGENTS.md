# AGENTS.md — Agent Authoring & AI Operator Guide (Ajan Rehberi)

> Part of the **turkish.code Engineering Bible**. Canonical source of truth.
> **Status:** Canonical · **Version:** 1.0 · **Last updated:** 2026-07-12
> **Related:** [18_AGENT_SYSTEM](./18_AGENT_SYSTEM.md) (the internals) · [19_SKILLS_SYSTEM](./19_SKILLS_SYSTEM.md) · [20_TOOL_SYSTEM](./20_TOOL_SYSTEM.md) · [24_PERMISSION_SYSTEM](./24_PERMISSION_SYSTEM.md) · [41_IMPLEMENTATION_RULES](./41_IMPLEMENTATION_RULES.md)

---

## 1. Purpose

Two audiences, one document:
1. **Agent authors** — how to define a new agent (`AgentDef`) for turkish.code's multi-agent system.
2. **AI operators** — an AI agent (like the one that may build/extend this project) working *in* the repository: what to read, how to behave, and the rules to honor.

[18_AGENT_SYSTEM](./18_AGENT_SYSTEM.md) documents the *internal machinery*; **this** doc is the *authoring format + operating contract*. (Analogous to how a repo's `AGENTS.md`/`CLAUDE.md` guides an AI working in it.) This is the file `CLAUDE.md` at the repo root points to.

## 2. Scope

The `AgentDef` authoring format + examples, agent design guidelines (roles, least privilege, budgets), and the AI-operator rules (what to read, how to change code, what never to do). Out of scope: the agent runtime/orchestration internals ([18](./18_AGENT_SYSTEM.md)), tool/permission mechanics ([20](./20_TOOL_SYSTEM.md)/[24](./24_PERMISSION_SYSTEM.md)).

---

# Part A — Authoring an Agent

## 3. What an Agent Is

An **Ajan** is a declarative unit ([18](./18_AGENT_SYSTEM.md) §4): a role + instructions + a **least-privilege** tool grant + memory scope + context policy + budget caps. Each agent is a scoped [Muhakeme](./15_REASONING_ENGINE.md) run. Agents compose into a hierarchy: an orchestrator decomposes and delegates.

## 4. `AgentDef` Format

Built-in agents live in `core/turkish_code/ajan/definitions/`; plugin agents are contributed via [23_PLUGIN_SYSTEM](./23_PLUGIN_SYSTEM.md). A definition (validated at load):

```toml
[agent]
id = "kodlayici"
name = "Kodlayıcı"                      # Turkish, user-facing
role = "implementer"

instructions = """
Sen bir uygulama ajanısın. Görevleri, verilen dosyalar ve testler kapsamında,
tersine alınabilir (snapshot destekli) düzenlemelerle uygularsın. Türkçe düşün ve açıkla.
"""                                     # tr, cites the task framing

tool_grants = ["fs.read", "fs.write", "code.search", "run.tests"]   # LEAST PRIVILEGE (24)
memory_scope = "workspace"              # session | workspace | isolated (11)
context_policy = { retrieval = "focused", graph = "on", memory = "on" }  # 13/12/11
model_preference = "code"              # hint to provider selection (21)
max_sub_agents = 2                      # bounded (17/18) — ≤ parent remaining
max_depth = 1
skills = ["turkce-yerellestirme"]      # optional, scoped skills (19)
```

**Field rules:**
- `tool_grants` — the smallest set that does the job (PR-3). A reviewer agent gets **read-only** tools; only an implementer gets `fs.write`. Grants are still permission-gated at runtime ([24](./24_PERMISSION_SYSTEM.md)).
- `memory_scope` — `isolated` sub-agents don't pollute shared memory ([11](./11_MEMORY_SYSTEM.md)).
- `max_sub_agents`/`max_depth` — bounded; never exceed the parent's remaining budget ([17](./17_EFFORT_MODES.md)/[18](./18_AGENT_SYSTEM.md), PR-14).
- `instructions` — Turkish, precise, cite constraints; never instruct the agent to bypass permissions/snapshots (it can't anyway, but don't try).

## 5. Built-in Agents (Reference)

| id | role | typical grants |
|---|---|---|
| `yonetici` | orchestrator | delegation only (no direct mutation) |
| `arastirmaci` | researcher | read-only: `code.search`, `retrieve`, `graph.query` |
| `kodlayici` | implementer | `fs.read/write`, `run.tests` |
| `test_yazari` | test author | `fs.read/write`, `run.tests` |
| `gozden_geciren` | reviewer | **read-only** |

## 6. Agent Design Guidelines

- **Single responsibility** per agent (PR-13). Don't build a god-agent; compose.
- **Least privilege** (PR-3): grant the minimum tools; prefer read-only.
- **Bounded** (PR-14): set sane `max_sub_agents`/`max_depth`; the orchestrator prefers *fewer, well-scoped* sub-tasks (orchestration overhead is real, [18](./18_AGENT_SYSTEM.md) §17).
- **Turkish-native** instructions/output (PR-12).
- **Reviewable output:** implementer agents produce snapshot-backed, diff-reviewable changes ([27](./27_SNAPSHOTS.md)/[06](./06_COMPONENT_LIBRARY.md) §6.4).
- **No autonomy without oversight:** agents run in a user-initiated, permissioned session ([18](./18_AGENT_SYSTEM.md) §3, [43](./43_NON_GOALS.md) NG-14).

## 7. Validation

`AgentDef`s are validated at registry load ([18](./18_AGENT_SYSTEM.md) §10): schema-correct, grants ⊆ known capabilities, budgets present, no delegation cycles. Invalid defs are rejected (fail-safe), never crashing startup.

---

# Part B — Rules for AI Operators (Working in This Repo)

## 8. Read Before You Build

An AI operating in this repository **must**, before implementing/extending a subsystem, read:
1. [00_PROJECT_VISION](./00_PROJECT_VISION.md) (pillars) + [02_DESIGN_PRINCIPLES](./02_DESIGN_PRINCIPLES.md) (rules) + [44_GLOSSARY](./44_GLOSSARY.md) (terms).
2. [01_ARCHITECTURE](./01_ARCHITECTURE.md) (the three tiers + invariants).
3. The **owning doc** for the subsystem you're touching (its number).
4. [41_IMPLEMENTATION_RULES](./41_IMPLEMENTATION_RULES.md) (the workflow + Definition of Done) and [ARCHITECTURE_INDEX](./ARCHITECTURE_INDEX.md) (dependencies/order).

Do not infer architecture from partial context; the docs are the spec ([41](./41_IMPLEMENTATION_RULES.md) §3).

## 9. The Operating Contract (Non-Negotiable)

When changing code, an AI operator honors the same gates as any implementer ([41](./41_IMPLEMENTATION_RULES.md)):
- **Contracts before code** — define in `ipc-schema`/storage schema, codegen, then implement ([10](./10_IPC.md)/[29](./29_STORAGE.md)).
- **Every side effect is a permissioned, snapshotted, audited tool** ([20](./20_TOOL_SYSTEM.md)/[24](./24_PERMISSION_SYSTEM.md)/[27](./27_SNAPSHOTS.md)/[26](./26_TIMELINE.md)) — never a direct fs/shell/net call outside the broker (PR-2).
- **Offline/local path first**, cloud optional ([32](./32_OFFLINE_FIRST.md), PR-6).
- **Bounded** everything (PR-14); **typed errors** ([38](./38_ERROR_HANDLING.md)); **Turkish-locale correct** (PR-12).
- **Docs + tests ship with the code** ([40](./40_DOCUMENTATION_RULES.md)/[35](./35_TESTING.md)); **pillar gates must pass** ([35](./35_TESTING.md) §6).
- **Never bypass a gate** to make something pass — a failing gate is a design signal ([41](./41_IMPLEMENTATION_RULES.md) §8).

## 10. Behavioral Norms for AI Operators

- **Prefer the safe/reversible/offline choice** when uncertain (priority order, [02](./02_DESIGN_PRINCIPLES.md) §4).
- **Scoped, reviewable changes** (PR-13); decompose big features per [42_ROADMAP](./42_ROADMAP.md).
- **Cite the governing invariant** in code/comments ([36](./36_CODING_STANDARDS.md) §7) so the next agent can trace intent.
- **Update the docs** when you change a contract/behavior — don't let docs drift ([40](./40_DOCUMENTATION_RULES.md) §8).
- **Use canonical terms** ([44](./44_GLOSSARY.md)); don't invent synonyms.
- **Ask/confirm for irreversible or outward-facing actions** (mirrors the product's own permission ethos).

## 11. Programmatic Operation (Future / Headless)

turkish.code is designed to be operable by AI agents programmatically ([01](./01_ARCHITECTURE.md) §19, [09](./09_PYTHON_BACKEND.md) §21): a headless/CLI mode can drive the Çekirdek over the Core Channel ([10](./10_IPC.md)) without the Arayüz. The same guarantees apply — permissions ([24](./24_PERMISSION_SYSTEM.md)), snapshots ([27](./27_SNAPSHOTS.md)), timeline ([26](./26_TIMELINE.md)), budgets ([17](./17_EFFORT_MODES.md)) — a headless operator is not privileged past a human one.

## 12. Configuration

- Built-in agent defs + orchestration policy + per-effort caps are configurable ([33](./33_CONFIGURATION.md)/[17](./17_EFFORT_MODES.md)). Plugin agents follow [23](./23_PLUGIN_SYSTEM.md).

## 13. Edge Cases

- **Over-decomposition / runaway delegation:** capped ([18](./18_AGENT_SYSTEM.md) §14, PR-14).
- **Sub-agent needs a tool it wasn't granted:** it can't use it — re-scope the `AgentDef`, don't widen at runtime.
- **AI operator tempted to skip a gate:** forbidden ([41](./41_IMPLEMENTATION_RULES.md) §19); fix the design.
- **Ambiguous docs:** resolve in the docs first ([40](./40_DOCUMENTATION_RULES.md)), then implement.

## 14. Security

- Agents (and AI operators) get **least privilege** and **no self-authorization** ([18](./18_AGENT_SYSTEM.md) §16, [24](./24_PERMISSION_SYSTEM.md)); everything they do is permissioned + audited. Prompt-injected agent output can only *request* effects. See [30_SECURITY](./30_SECURITY.md).

## 15. Testing Strategy

- New/changed `AgentDef`s: scoping tests (can't exceed grants), bound tests (caps honored), delegation-cycle tests ([18](./18_AGENT_SYSTEM.md) §18, [35](./35_TESTING.md)). AI-operator changes are held to the full pillar gates ([35](./35_TESTING.md) §6).

## 16. Future Extensions

- User-authored agents from within the app; agent "teams" as presets; learned decomposition; a conformance check that verifies an AI operator read the required docs before large changes ([41](./41_IMPLEMENTATION_RULES.md) §16).

## 17. Examples

- **Authoring:** a `guvenlik_gozden_geciren` (security reviewer) agent = read-only grants + instructions to check for the security invariants ([30](./30_SECURITY.md) §12) in a diff; the orchestrator routes edits to it before finalizing.
- **Operating:** an AI adds a tool → reads [20](./20_TOOL_SYSTEM.md)/[24](./24_PERMISSION_SYSTEM.md)/[30](./30_SECURITY.md) → defines the `ToolDef`+capability in schema → implements it brokered/permissioned/snapshotted → adds Security+Reversibility gate tests → updates [20](./20_TOOL_SYSTEM.md) doc → verifies gates. (Full example: [41](./41_IMPLEMENTATION_RULES.md) §17.)

## 18. Anti-Patterns

- God-agents / all-tools grants.
- Unbounded delegation.
- AI operator inventing undocumented cross-tier behavior.
- Bypassing gates; letting docs drift.
- Non-Turkish agent instructions/output.
- Runtime privilege widening.

## 19. Things That Must Never Happen

1. An agent is granted more than least privilege or self-authorizes.
2. An AI operator introduces an ungated side-effect/egress/secret path.
3. A change ships without its doc/tests/gates.
4. Agent hierarchy exceeds budget/depth caps.
5. An operator bypasses a pillar gate to "make it work."

## 20. Relationship With Other Subsystems

Authoring format for [18_AGENT_SYSTEM](./18_AGENT_SYSTEM.md); agents use [20_TOOL_SYSTEM](./20_TOOL_SYSTEM.md) under [24_PERMISSION_SYSTEM](./24_PERMISSION_SYSTEM.md), load [19_SKILLS_SYSTEM](./19_SKILLS_SYSTEM.md), run [15_REASONING_ENGINE](./15_REASONING_ENGINE.md), bounded by [17_EFFORT_MODES](./17_EFFORT_MODES.md); the operator contract enforces [41_IMPLEMENTATION_RULES](./41_IMPLEMENTATION_RULES.md)/[40_DOCUMENTATION_RULES](./40_DOCUMENTATION_RULES.md)/[35_TESTING](./35_TESTING.md); extensible via [23_PLUGIN_SYSTEM](./23_PLUGIN_SYSTEM.md).

## 21. Migration Considerations

- `AgentDef` schema is versioned ([18](./18_AGENT_SYSTEM.md) §24); additive fields preferred (PR-18). The operator contract tightens as the Bible evolves; a change to it applies to all future AI work. Plugin agents validate against the current schema at load.
