# 02 — Engineering Design Principles (Tasarım İlkeleri)

> Part of the **turkish.code Engineering Bible**. Canonical source of truth.
> **Status:** Canonical · **Version:** 1.0 · **Last updated:** 2026-07-12
> **Related:** [00_PROJECT_VISION](./00_PROJECT_VISION.md) · [01_ARCHITECTURE](./01_ARCHITECTURE.md) · [36_CODING_STANDARDS](./36_CODING_STANDARDS.md) · [41_IMPLEMENTATION_RULES](./41_IMPLEMENTATION_RULES.md)

---

## 1. Purpose

The vision ([00](./00_PROJECT_VISION.md)) says *what and why*. The architecture ([01](./01_ARCHITECTURE.md)) says *the shape*. This document says **how we make engineering decisions** — the principles that resolve trade-offs when the other documents are silent. When two valid implementations exist, these principles pick the winner. They are the "constitution" that individual coding rules ([36](./36_CODING_STANDARDS.md)) and implementation rules ([41](./41_IMPLEMENTATION_RULES.md)) derive from.

## 2. Scope

Cross-cutting engineering philosophy and heuristics that apply to every tier and subsystem. Not language-specific style (that is [36](./36_CODING_STANDARDS.md)); not product intent (that is [00](./00_PROJECT_VISION.md)).

## 3. The Principles

Each principle: a name, the rule, the rationale, and a concrete test you can apply.

### PR-1 — Pillars Are Structural, Not Aspirational
Enforce the five pillars ([00](./00_PROJECT_VISION.md) §5) with architecture and types, not with discipline. If privacy depends on developers "remembering not to," it will fail.
*Test:* Can a new contributor violate the pillar by writing ordinary-looking code? If yes, the design is wrong — add a structural gate (a single egress choke point, a type that can't be constructed without a permission token, etc.).

### PR-2 — One Path Per Side Effect
Every category of side effect (fs write, shell exec, egress, secret access) has exactly **one** code path, in exactly one tier. No shortcuts, no "just this once" direct calls.
*Rationale:* one path can be permission-gated, logged, snapshotted, and tested. Ten paths cannot.
*Test:* `grep` for the OS primitive (e.g., raw file-write API). It should appear in exactly one module. See [24_PERMISSION_SYSTEM](./24_PERMISSION_SYSTEM.md).

### PR-3 — Trust Decreases Outward
Kabuk > Çekirdek > Arayüz in trust. Never let a less-trusted tier gain the authority of a more-trusted one. Treat model output and rendered content as potentially adversarial (prompt injection is real).
*Test:* Could a malicious string in model output cause a side effect without passing a permission gate? If yes, fix the boundary.

### PR-4 — Reversible by Default
Prefer designs where any action can be undone. Snapshot before mutating files. Make destructive operations opt-in and gated.
*Test:* "If the model is wrong here, can the user recover in one click?" If no, add a snapshot/undo path. See [27_SNAPSHOTS](./27_SNAPSHOTS.md).

### PR-5 — Everything Important Is An Event
Perception and action are recorded as immutable events in the Timeline. State is derived from events where feasible (event-sourcing bias). This yields audit, replay, and crash recovery for free.
*Test:* "Could I reconstruct what happened from the Event Journal alone?" See [26_TIMELINE](./26_TIMELINE.md), [28_CRASH_RECOVERY](./28_CRASH_RECOVERY.md).

### PR-6 — Offline Is the Default Code Path, Not the Fallback
Write the local path first; make cloud an *optional enhancement* layered on top. Never write "call cloud, and if offline, degrade" — write "run locally, and if consent + connectivity, enhance."
*Test:* Disable all network. Does the feature work at full core function? See [32_OFFLINE_FIRST](./32_OFFLINE_FIRST.md).

### PR-7 — Degrade, Don't Die
Missing GPU, tiny model, no reranker, corrupt cache: shrink ambition and continue. Every capability declares a graceful-degradation ladder.
*Test:* Remove the optional dependency. Does the feature return a *worse but valid* result, or crash? See [31_PERFORMANCE](./31_PERFORMANCE.md).

### PR-8 — Contracts at Boundaries, Freedom Within
Cross-tier and cross-subsystem interactions go through **versioned, typed, codegen'd contracts** ([01](./01_ARCHITECTURE.md) §12). Inside a subsystem, refactor freely. The contract is the promise; the implementation is private.
*Test:* Can I rewrite a subsystem's internals without touching another subsystem's code? If not, a private detail has leaked into a contract.

### PR-9 — Explicit Over Implicit
No hidden globals, no ambient magic, no "spooky action at a distance." Dependencies are injected; effort budgets, permission contexts, and provider selections are passed explicitly.
*Test:* Reading a function signature, can you tell what it can touch and what it needs? See [36_CODING_STANDARDS](./36_CODING_STANDARDS.md).

### PR-10 — Typed Errors, Never Silent Failure
Failures are values with types and remediation, not swallowed exceptions or `null`. Every error names its category, whether it's retryable, and what the user/agent should do. See [38_ERROR_HANDLING](./38_ERROR_HANDLING.md).
*Test:* For any failure, can the caller programmatically decide to retry, degrade, or surface? If it's a bare string/None, fix it.

### PR-11 — Legible to Machines and Humans
Config, logs, IPC, and docs are structured for both human reading and machine parsing (another AI agent must be able to operate the system). Prefer declarative, introspectable definitions (tool schemas, skill manifests) over imperative hardcoding.
*Test:* Could an AI agent, given only the docs and schemas, invoke this correctly? See [40_DOCUMENTATION_RULES](./40_DOCUMENTATION_RULES.md), [AGENTS.md](./AGENTS.md).

### PR-12 — Turkish-First Is a Correctness Property
Turkish locale handling (dotless-i casing, glyphs, collation, pluralization) is not a "nice to have"; a casing bug is a *correctness bug*. All user-facing text flows through the i18n layer; no hardcoded strings. See [04_TURKISH_DESIGN_LANGUAGE](./04_TURKISH_DESIGN_LANGUAGE.md), [03_UI_SYSTEM](./03_UI_SYSTEM.md).
*Test:* Does `"İstanbul".lower()` and `"ı".upper()` behave correctly for the Turkish locale everywhere text is transformed?

### PR-13 — Small, Sharp, Single-Responsibility Modules
Each subsystem does one thing (mirrors the one-doc-one-responsibility rule of the Bible). Prefer composition of small units over large god-objects.
*Test:* Can you state the module's responsibility in one sentence without "and"?

### PR-14 — Budgeted Everything
Compute, tokens, tool-call depth, retrieval breadth, and time are **budgets**, set by the Effort Mode and passed explicitly. No unbounded loops, no unbounded recursion of agents. See [17_EFFORT_MODES](./17_EFFORT_MODES.md).
*Test:* Is there a hard numeric bound on every loop, recursion, and external call fan-out?

### PR-15 — Determinism Where It Matters
Storage, migrations, IDs, hashing, and event ordering are deterministic and reproducible. Model calls are inherently non-deterministic, so isolate that non-determinism behind the provider boundary and record inputs/outputs in the Timeline for replayability of the *system* even when the *model* varies.
*Test:* Given the same journal, does replay reconstruct the same state?

### PR-16 — Consent Is Sacred and Revocable
Any egress, cloud use, or telemetry requires explicit, per-category, revocable consent, and every such act is logged. Absence of a "no" is never a "yes." See [30_SECURITY](./30_SECURITY.md), [34_API_KEYS](./34_API_KEYS.md).

### PR-17 — Optimize the Second Time
Write the correct, clear, well-bounded version first; measure; then optimize the proven hot path. Premature micro-optimization that obscures the pillars is a defect. But *architectural* performance (planes, streaming, backpressure) is designed in from the start, not retrofitted. See [31_PERFORMANCE](./31_PERFORMANCE.md).

### PR-18 — Additive Evolution
Prefer additive, backward-compatible changes to contracts and storage. Breaking changes require a versioned migration and a deprecation window. See §"Migration" in each subsystem doc.

### PR-19 — Provider-Independent, Model-First
The system depends on **capabilities and models**, never on a specific vendor. Ask "what is the best *model* for this task?" and let the router pick the provider ([45_ROUTING_ORCHESTRATION](./45_ROUTING_ORCHESTRATION.md)) — never hardcode a provider or select provider-first ([52_ADR_LOG](./52_ADR_LOG.md) ADR-0005). Agents are **provider-agnostic** (ADR-0012).
*Test:* Can you swap the entire provider set without touching reasoning/agent code? If not, a vendor leaked into the core.

### PR-20 — SOLID, Single-Responsibility Adapters
Follow **SOLID + Dependency Injection**. Each provider (and each integration) is a **single-responsibility adapter** behind one interface, so **adding a future provider requires minimal changes** — implement the interface, register it, done ([52_ADR_LOG](./52_ADR_LOG.md) ADR-0014, [36_CODING_STANDARDS](./36_CODING_STANDARDS.md)).
*Test:* Does adding a provider touch any file outside its own adapter (+ registration)? If yes, responsibilities are tangled.

### PR-21 — Resilience by Default (Smart Failover)
External model calls are unreliable (rate limits, quotas, outages). Design for **smart failover, retry, timeout, and cooldown** and **quota-preserving, quality-under-exhaustion** routing ([48_QUOTA_TIER_MANAGEMENT](./48_QUOTA_TIER_MANAGEMENT.md), ADR-0006/0009) — never simple static failover, never a hard-fail while a viable model (incl. the Ollama fallback) remains.
*Test:* Kill the preferred provider mid-run — does the system fail over to the next-best model and preserve quality, or collapse?

## 4. Decision Heuristics (When Principles Conflict)

Principles can tension against each other. Resolve in this priority order:

```
1. Safety & Privacy (PR-1, PR-2, PR-3, PR-16)      ← never traded away
2. Reversibility & Auditability (PR-4, PR-5)
3. Offline & Degradation (PR-6, PR-7)
4. Correctness incl. Turkish locale (PR-10, PR-12, PR-15)
5. Clarity & Contracts (PR-8, PR-9, PR-11, PR-13)
6. Performance (PR-14, PR-17)
```

Higher wins. Example: if a caching optimization (perf, level 6) would create a second egress path (level 1), the optimization loses. This ordering is itself an application of the vision's constraint order ([00](./00_PROJECT_VISION.md) §9).

## 5. Applying These to a New Subsystem (Checklist)

When designing any new subsystem, walk this list before writing code:

1. Which pillar(s) does it serve? (If none, why does it exist? See [43_NON_GOALS](./43_NON_GOALS.md).)
2. What side effects does it have, and do they route through the single path (PR-2)?
3. What is reversible; where are the snapshots (PR-4)?
4. What events does it emit to the Timeline (PR-5)?
5. What is the fully-offline code path (PR-6)?
6. What is the degradation ladder (PR-7)?
7. What is the versioned contract at its boundary (PR-8)?
8. What are the budgets (PR-14)?
9. What are the typed errors (PR-10)?
10. What Turkish-locale concerns exist (PR-12)?

The subsystem's doc must answer all ten. This checklist is repeated operationally in [41_IMPLEMENTATION_RULES](./41_IMPLEMENTATION_RULES.md).

## 6. Anti-Patterns (Principle Violations)

- "I'll add the offline path later." (Violates PR-6; later never comes.)
- "It's just a small direct file write." (Violates PR-2.)
- "Catch, log, and continue" that hides a real error. (Violates PR-10.)
- Passing capability through a global singleton. (Violates PR-9.)
- Unbounded agent recursion / tool loops. (Violates PR-14.)
- ASCII-folding Turkish text to "simplify." (Violates PR-12; data-losing.)
- A perf hack that opens a second side-effect path. (Violates the priority order §4.)

## 7. Things That Must Never Happen

1. A design ships that makes a pillar depend on developer discipline rather than structure (PR-1).
2. A second, ungated path to a side effect is introduced (PR-2).
3. A less-trusted tier is granted more-trusted authority (PR-3).
4. An unbounded loop/recursion/fan-out reaches production (PR-14).
5. User-facing text is hardcoded, bypassing the i18n/locale layer (PR-12).

## 8. Relationship With Other Subsystems

These principles are cited throughout the Bible as the *why* behind specific rules. [36_CODING_STANDARDS](./36_CODING_STANDARDS.md) and [41_IMPLEMENTATION_RULES](./41_IMPLEMENTATION_RULES.md) are the operational, checkable enforcement of these principles. [30_SECURITY](./30_SECURITY.md), [32_OFFLINE_FIRST](./32_OFFLINE_FIRST.md), and [24_PERMISSION_SYSTEM](./24_PERMISSION_SYSTEM.md) are the deepest expressions of PR-1/2/3/16.

## 9. Migration Considerations

Principles evolve rarely and deliberately. A change here can invalidate design decisions across many subsystems, so any edit requires a review of every doc that cites the changed principle (tracked via the [ARCHITECTURE_INDEX](./ARCHITECTURE_INDEX.md) cross-reference map) and a note in [42_ROADMAP](./42_ROADMAP.md).
