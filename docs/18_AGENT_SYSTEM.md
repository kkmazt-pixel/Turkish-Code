# 18 — Agent System (Ajan Sistemi)

> Part of the **turkish.code Engineering Bible**. Canonical source of truth.
> **Status:** Canonical · **Version:** 1.0 · **Last updated:** 2026-07-12
> **Owner:** Çekirdek `ajan/`
> **Related:** [15_REASONING_ENGINE](./15_REASONING_ENGINE.md) · [16_COUNCIL_MODE](./16_COUNCIL_MODE.md) · [17_EFFORT_MODES](./17_EFFORT_MODES.md) · [19_SKILLS_SYSTEM](./19_SKILLS_SYSTEM.md) · [20_TOOL_SYSTEM](./20_TOOL_SYSTEM.md) · [24_PERMISSION_SYSTEM](./24_PERMISSION_SYSTEM.md) · [AGENTS.md](./AGENTS.md)

---

## 1. Purpose

Defines the **Ajan** system: how turkish.code composes multiple reasoning runs into a hierarchy of specialized agents that **decompose goals and delegate**. Where [15](./15_REASONING_ENGINE.md) is a single reasoning *unit* and [16](./16_COUNCIL_MODE.md) is *deliberation*, the Ajan system is *delegation* — an orchestrator agent breaks a large task into sub-tasks, hands each to a scoped sub-agent, and integrates results. This enables large, multi-step work (multi-file refactors, "build feature X") while keeping each unit bounded, permissioned, and auditable.

## 2. Scope

Agent definitions, the orchestrator/sub-agent model, delegation protocol, context/memory/tool scoping per agent, budget allocation, lifecycle, and the agent registry. Out of scope: the reasoning loop itself ([15](./15_REASONING_ENGINE.md)), council ([16](./16_COUNCIL_MODE.md)), tool/permission mechanics ([20](./20_TOOL_SYSTEM.md)/[24](./24_PERMISSION_SYSTEM.md)), and the external-facing agent-operator guide ([AGENTS.md](./AGENTS.md)).

## 3. Goals

1. **Decompose & delegate** large goals into bounded sub-tasks executed by specialized agents.
2. **Scope everything** per agent: context, memory, tools, and budget — least privilege ([24](./24_PERMISSION_SYSTEM.md), PR-3).
3. **Bounded hierarchy** (PR-14): capped agent count and recursion depth from the effort budget ([17](./17_EFFORT_MODES.md)) — no runaway agent spawning.
4. **Composable & declarative**: agents are defined by data (role, instructions, tool grants), so they're legible to humans and AI operators (PR-11, [AGENTS.md](./AGENTS.md)).
5. **Auditable**: every agent's work is in the Timeline ([26](./26_TIMELINE.md)); delegation is visible.

### Non-Goals
- Not autonomous background daemons acting without user oversight (agents run within a user-initiated, permissioned session). Not a replacement for council (delegation ≠ deliberation).

## 4. Agent Definition (Ajan)

An agent is a declarative record ([AGENTS.md](./AGENTS.md) documents the authoring format):

```
AgentDef {
  id, name (Turkish),
  role: string                 // "yönetici/orchestrator", "kodlayıcı", "gözden geçiren", "test yazarı"...
  instructions: string         // system persona/goal framing (tr)
  toolGrants: [capability]     // subset of tools it may use (20/24) — least privilege
  memoryScope: session|workspace|isolated
  contextPolicy: {...}         // what retrieval/graph/memory it receives (11/12/13)
  modelPreference?: tier       // hint (21)
  maxSubAgents, maxDepth       // its own delegation caps (bounded by parent + effort 17)
  skills?: [skillId]           // skills it may load (19)
}
```

- **First-party agents** (built-in): `Yönetici` (orchestrator), `Kodlayıcı` (implementer), `Gözden Geçiren` (reviewer), `Test Yazarı` (test author), `Araştırmacı` (researcher/retrieval-heavy). More can be added; plugins may contribute agents ([23](./23_PLUGIN_SYSTEM.md)).
- Each agent = a configured Muhakeme run ([15](./15_REASONING_ENGINE.md)) with its role/instructions/tool grants/scope.

## 5. Orchestration Model

```
                 ┌──────────── Yönetici (orchestrator) ────────────┐
   user goal ───▶│ decompose goal → sub-tasks (a plan)             │
                 │ delegate each sub-task with a scoped budget      │
                 └───────┬───────────────┬───────────────┬─────────┘
                         ▼               ▼               ▼
                    Araştırmacı      Kodlayıcı       Test Yazarı
                    (retrieve/       (edit files     (write/run
                     analyze)         via tools)      tests)
                         │               │               │
                         └──── results ──┴──── integrated by Yönetici ───▶ Gözden Geçiren
                                                                            (review) → final
```

- The **orchestrator** owns the plan and integration; **sub-agents** execute bounded sub-tasks and return structured results.
- Delegation is **explicit** (a `delegate(subTask, agentRole, subBudget, scopedContext)` call), recorded in the Timeline. Sub-agents cannot exceed their granted tools/budget/scope.
- **Depth & breadth are capped** ([17](./17_EFFORT_MODES.md): `agents.maxSubAgents`, `agents.maxDepth`) — a sub-agent may itself delegate only within the remaining budget and depth (prevents fan-out explosions, PR-14).

## 6. Delegation Protocol

1. **Decompose:** orchestrator (a Muhakeme run) produces sub-tasks with clear acceptance criteria.
2. **Scope:** for each sub-task, allocate a **sub-budget** (a slice of remaining, [17](./17_EFFORT_MODES.md) §6), a **tool grant** (subset, least privilege), a **memory scope**, and a **context policy** (what it can retrieve/see).
3. **Execute:** each sub-agent runs its own bounded reasoning loop ([15](./15_REASONING_ENGINE.md)); sub-agents may run in parallel when independent (bounded concurrency, [09](./09_PYTHON_BACKEND.md)).
4. **Return:** structured result (artifacts, edits-as-snapshots [27], findings) + its own trace.
5. **Integrate:** orchestrator merges results, resolves conflicts, and (optionally) routes to a reviewer agent before finalizing.

## 7. Scoping & Least Privilege

- **Tools:** an agent may only use tools in its `toolGrants` (a subset of what permissions [24](./24_PERMISSION_SYSTEM.md) would allow). A reviewer agent, e.g., gets read-only tools; the implementer gets `fs.write` (still permission-gated at execution).
- **Memory:** `isolated` sub-agents don't pollute shared memory; `workspace` agents can read shared memory ([11](./11_MEMORY_SYSTEM.md)). Writes back to durable memory go through the orchestrator's curation.
- **Context:** each agent receives only the context its `contextPolicy` allows — a research agent gets broad retrieval; a focused implementer gets the specific files. Least context = less injection surface + better focus.
- This scoping is a defense-in-depth application of PR-3 (least privilege) *within* the Çekirdek.

## 8. Budget Allocation

- The orchestrator's `EffortBudget` ([17](./17_EFFORT_MODES.md)) is the ceiling. Each delegation consumes from a shared remaining pool; the sum of sub-agent budgets never exceeds the parent's remaining (§6). Depth is capped. Exhaustion → orchestrator finalizes with partial results (PR-7).

## 9. Lifecycle & State Machine

```
[Spawned] → [Planning] → [Delegating] ⇄ [AwaitingSubAgents]
                             │                    │ (parallel sub-runs)
                             ▼                    ▼
                        [Integrating] ────▶ [Reviewing]? ────▶ [Done]
Any → [Cancelled] ($/cancel propagates to the whole tree) | [Failed] (typed)
Every transition → Timeline event (26) + checkpoint (28)
```

- **Cancellation** propagates through the entire agent tree ([10](./10_IPC.md), [15](./15_REASONING_ENGINE.md)).
- **Crash recovery:** the agent tree state is checkpointed; a resumed session rebuilds the tree and continues incomplete sub-tasks ([28](./28_CRASH_RECOVERY.md)).

## 10. Agent Registry

- A registry ([09](./09_PYTHON_BACKEND.md) DI) holds available `AgentDef`s (built-in + plugin-contributed [23]). The orchestrator selects agents by role for each sub-task. Registry entries are declarative and inspectable ([AGENTS.md](./AGENTS.md)).

## 11. Directory Structure

```
ajan/
  registry.py     # AgentDef registry (built-in + plugin)
  orchestrator.py # decompose/delegate/integrate
  agent.py        # a single agent = scoped Muhakeme run (15)
  delegate.py     # delegation protocol + sub-budget allocation (17)
  scope.py        # tool/memory/context scoping (least privilege)
  definitions/    # built-in AgentDefs (yönetici, kodlayıcı, ...)
```

## 12. Configuration

- Built-in agent definitions, default orchestration policy, and per-effort agent caps are configurable ([33](./33_CONFIGURATION.md)/[17](./17_EFFORT_MODES.md)). Users/plugins can add agents ([23](./23_PLUGIN_SYSTEM.md), [AGENTS.md](./AGENTS.md)).

## 13. Dependencies

- [15_REASONING_ENGINE](./15_REASONING_ENGINE.md) (each agent is a run), [17_EFFORT_MODES](./17_EFFORT_MODES.md) (budgets), [20_TOOL_SYSTEM](./20_TOOL_SYSTEM.md)/[24_PERMISSION_SYSTEM](./24_PERMISSION_SYSTEM.md) (grants/enforcement), [11_MEMORY_SYSTEM](./11_MEMORY_SYSTEM.md) (scoped memory), [19_SKILLS_SYSTEM](./19_SKILLS_SYSTEM.md) (per-agent skills), [26_TIMELINE](./26_TIMELINE.md)/[28_CRASH_RECOVERY](./28_CRASH_RECOVERY.md) (audit/resume), [16_COUNCIL_MODE](./16_COUNCIL_MODE.md) (an agent may convene a council for a decision).

## 14. Edge Cases

- **Over-decomposition:** the orchestrator is capped (`maxSubAgents`); it must prefer fewer, well-scoped sub-tasks. A cap breach forces sequential/merged handling.
- **Sub-agent conflict** (two agents edit the same file): edits are snapshot-backed ([27](./27_SNAPSHOTS.md)); the orchestrator serializes conflicting writes or reconciles via a merge step; last-writer conflicts are surfaced, not silently overwritten.
- **Sub-agent failure:** orchestrator retries (bounded), reassigns, or reports partial completion (PR-7/PR-10) — one failed sub-task doesn't crash the whole run.
- **Runaway delegation:** depth/breadth caps + budget pool prevent it (PR-14).
- **Deadlock/cyclic delegation:** the registry/protocol forbids an agent delegating back up its own ancestry; depth cap is the backstop.
- **Cancellation mid-tree:** propagates; partial edits reversible via snapshots.

## 15. Failure Recovery

- Agent-tree checkpoints ([28](./28_CRASH_RECOVERY.md)) enable resume. Failed sub-agents are typed and retriable; the orchestrator decides continue/abort. All agent edits are reversible via snapshots ([27](./27_SNAPSHOTS.md)).

## 16. Security

- **Least privilege is structural** (§7): a sub-agent literally cannot call a tool outside its grant, and every tool call still passes the Kabuk permission engine ([24](./24_PERMISSION_SYSTEM.md)) regardless of agent. Compromised/prompt-injected sub-agent output can only act within its narrow grant. Delegation and grants are fully audited ([26](./26_TIMELINE.md)). See [30_SECURITY](./30_SECURITY.md).

## 17. Performance

- Parallelize independent sub-agents (bounded concurrency, [09](./09_PYTHON_BACKEND.md)); share the assembled base context to avoid re-retrieval; effort-scale the hierarchy. More agents ≠ always better — orchestration overhead is real; prefer the smallest hierarchy that fits the task ([31](./31_PERFORMANCE.md)).

## 18. Testing Strategy

- **Bound tests:** agent count/depth caps enforced; no runaway spawning; nested budgets respected.
- **Scoping tests:** a sub-agent cannot use a non-granted tool or read out-of-scope memory.
- **Conflict tests:** concurrent edits to one file are serialized/reconciled, snapshot-backed.
- **Cancellation/resume tests** across the tree.
- **Delegation-cycle prevention.** See [35_TESTING](./35_TESTING.md).

## 19. Future Extensions

- Headless/CLI agent operation ([01](./01_ARCHITECTURE.md) §19, [AGENTS.md](./AGENTS.md)); user-authored custom agents; learned decomposition strategies; agent "teams" as saved presets; long-running (checkpointed) background agents with explicit user oversight and permission ceilings.

## 20. Examples

- "Kullanıcı profili özelliğini ekle" under `Derin`: Yönetici plans → Araştırmacı maps affected code ([12](./12_KNOWLEDGE_GRAPH.md)) → Kodlayıcı implements (snapshot-backed edits) → Test Yazarı adds/runs tests → Gözden Geçiren reviews → Yönetici integrates and presents a reviewable, reversible change set with a full audit trail.

## 21. Anti-Patterns

- Unbounded/recursive agent spawning (PR-14).
- Granting every agent all tools (violates least privilege).
- Sub-agents silently overwriting each other's edits.
- Hidden delegation (must be in the Timeline).
- Over-decomposing trivial tasks (orchestration overhead > benefit).
- Background agents acting without user oversight/permission ceilings.

## 22. Things That Must Never Happen

1. Agent hierarchy exceeds depth/breadth/budget caps.
2. A sub-agent uses a tool outside its grant or bypasses permissions.
3. Concurrent agent edits corrupt a file without snapshot/conflict handling.
4. Delegation is not recorded/auditable.
5. An agent delegates cyclically up its own ancestry.

## 23. Relationship With Other Subsystems

Composes [15_REASONING_ENGINE](./15_REASONING_ENGINE.md) runs; bounded by [17_EFFORT_MODES](./17_EFFORT_MODES.md); scoped by [20](./20_TOOL_SYSTEM.md)/[24](./24_PERMISSION_SYSTEM.md); scoped memory via [11](./11_MEMORY_SYSTEM.md); may use [16_COUNCIL_MODE](./16_COUNCIL_MODE.md) and [19_SKILLS_SYSTEM](./19_SKILLS_SYSTEM.md); audited in [26_TIMELINE](./26_TIMELINE.md), resumable via [28_CRASH_RECOVERY](./28_CRASH_RECOVERY.md); externally documented for operators in [AGENTS.md](./AGENTS.md); extensible via [23_PLUGIN_SYSTEM](./23_PLUGIN_SYSTEM.md).

## 24. Migration Considerations

- `AgentDef` schema is versioned; adding agent roles/fields is additive (PR-18). Changing default orchestration policy is announced in [42_ROADMAP](./42_ROADMAP.md). Plugin-contributed agents are validated against the current schema at load ([23](./23_PLUGIN_SYSTEM.md)).
