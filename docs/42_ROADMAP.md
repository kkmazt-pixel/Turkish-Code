# 42 — Roadmap & Implementation Order (Yol Haritası)

> Part of the **turkish.code Engineering Bible**. Canonical source of truth (planning).
> **Status:** Canonical · **Version:** 1.0 · **Last updated:** 2026-07-12
> **Related:** [00_PROJECT_VISION](./00_PROJECT_VISION.md) · [01_ARCHITECTURE](./01_ARCHITECTURE.md) · [41_IMPLEMENTATION_RULES](./41_IMPLEMENTATION_RULES.md) · [ARCHITECTURE_INDEX](./ARCHITECTURE_INDEX.md) · [43_NON_GOALS](./43_NON_GOALS.md)

---

## 1. Purpose

Defines the **build sequence, priority, and milestones** for implementing turkish.code from this documentation. Phase 1 (this documentation) is complete when the Bible is done; this doc governs Phase 2+ (implementation). It exists so implementers (human or AI) build subsystems in an order where dependencies precede dependents and the pillar-guaranteeing substrate exists before features rely on it ([41](./41_IMPLEMENTATION_RULES.md) §7).

## 2. Scope

Phasing, the implementation order with rationale, priority tiers, milestones with acceptance criteria, and dependency-driven sequencing. Out of scope: the workflow per change ([41](./41_IMPLEMENTATION_RULES.md)), the dependency graph visualization ([ARCHITECTURE_INDEX](./ARCHITECTURE_INDEX.md)).

## 3. Phases

```
Phase 1 — DOCUMENTATION (this Bible)                    ← COMPLETE at Bible sign-off
Phase 2 — WALKING SKELETON (tiers + IPC + storage)      ← the substrate
Phase 3 — CORE INTELLIGENCE (reason/tools/RAG/memory)   ← the brain, offline
Phase 4 — SAFETY & STATE (permissions/snapshots/timeline/recovery)  ← woven in from P2, hardened here
Phase 5 — ADVANCED INTELLIGENCE (council/agents/effort/skills)
Phase 6 — EXTENSIBILITY & POLISH (providers+/plugins/design polish)
Phase 7 — HARDENING & GA (perf/security audit/offline/packaging/locale)
```
Note: Safety (Phase 4 items) is not literally "after" the brain — permission/snapshot/timeline hooks are built into the tool/broker path *as it is created* (PR-1); Phase 4 is where they're fully hardened and surfaced. Build the guarantee with the feature, never bolt it on ([41](./41_IMPLEMENTATION_RULES.md)).

## 4. Implementation Order (Dependency-Driven)

The canonical order (each depends on those before it). Numbers reference docs.

**Tier 0 — Foundations (must exist first):**
1. Repo/monorepo + toolchain + CI skeleton ([37](./37_REPOSITORY_STRUCTURE.md), [36](./36_CODING_STANDARDS.md), [35](./35_TESTING.md), [33](./33_CONFIGURATION.md)).
2. IPC contracts + codegen ([10](./10_IPC.md), `ipc-schema`).
3. Storage substrate: SQLite/WAL, blob CAS, event journal ([29](./29_STORAGE.md)).
4. Three-tier walking skeleton: Kabuk supervisor + Core Channel + a minimal Çekirdek + a minimal Arayüz that can round-trip a message ([08](./08_TAURI_ARCHITECTURE.md), [09](./09_PYTHON_BACKEND.md), [03](./03_UI_SYSTEM.md), [07](./07_DESKTOP_ARCHITECTURE.md)).

**Tier 1 — Safety substrate (woven into the skeleton):**
5. Permission engine + broker choke point ([24](./24_PERMISSION_SYSTEM.md), [08](./08_TAURI_ARCHITECTURE.md)).
6. Tool system with snapshot + timeline hooks ([20](./20_TOOL_SYSTEM.md), [27](./27_SNAPSHOTS.md), [26](./26_TIMELINE.md)).
7. Secret vault ([34](./34_API_KEYS.md)).
8. Crash recovery scaffolding (checkpoints) ([28](./28_CRASH_RECOVERY.md)).

**Tier 2 — Knowledge & providers (offline first):**
9. Provider system + a local provider (llama.cpp/Ollama/NIM) ([21](./21_PROVIDER_SYSTEM.md), [22](./22_PROVIDER_INTEGRATIONS.md)).
10. Embeddings (local) ([14](./14_EMBEDDINGS.md)).
11. Workspace + discovery/watch/ignore ([25](./25_WORKSPACE_SYSTEM.md)).
12. Knowledge graph extraction ([12](./12_KNOWLEDGE_GRAPH.md)) + RAG pipeline ([13](./13_RAG_SYSTEM.md)).
13. Memory ([11](./11_MEMORY_SYSTEM.md)).

**Tier 3 — Reasoning:**
14. Effort modes/budgets ([17](./17_EFFORT_MODES.md)).
15. Reasoning engine (plan→act→observe→reflect, tool-calling, trace) ([15](./15_REASONING_ENGINE.md)).

**Tier 4 — Advanced intelligence:**
16. Skills ([19](./19_SKILLS_SYSTEM.md)), Council ([16](./16_COUNCIL_MODE.md)), Agents ([18](./18_AGENT_SYSTEM.md)).

**Tier 5 — Extensibility & polish:**
17. More providers incl. cloud (consented) ([21](./21_PROVIDER_SYSTEM.md)/[22](./22_PROVIDER_INTEGRATIONS.md)), Plugins ([23](./23_PLUGIN_SYSTEM.md)).
18. Full design system realization ([04](./04_TURKISH_DESIGN_LANGUAGE.md), [05](./05_ANIMATION_SYSTEM.md), [06](./06_COMPONENT_LIBRARY.md)), all product components.

**Tier 6 — Hardening & GA:**
19. Performance passes ([31](./31_PERFORMANCE.md)), Security audit ([30](./30_SECURITY.md)), Offline gate hardening ([32](./32_OFFLINE_FIRST.md)), Locale gate, packaging/updates ([07](./07_DESKTOP_ARCHITECTURE.md)).

## 5. Priority Tiers (What Matters Most)

```
P0 (blocking, structural): tier boundaries, IPC, storage/journal, permission, snapshots,
     timeline, secret vault — the pillar substrate. Nothing safe ships without these.
P1 (core value): local provider, embeddings, RAG, graph, memory, effort, reasoning, basic UI.
P2 (differentiators): council, agents, skills, Turkish design polish, model-first multi-provider routing (scoring/quota/failover).
P3 (extensibility/reach): plugins, cloud providers, advanced UI, multi-workspace polish.
P4 (nice-to-have/future): headless/CLI, remote Core, marketplace, advanced analytics.
```
Priority follows the vision: privacy/offline/safety substrate (P0) is non-negotiable and first; Turkish-native identity + agentic reasoning (P1/P2) is the core value; extensibility (P3) broadens reach; futures (P4) come last ([00](./00_PROJECT_VISION.md), [41](./41_IMPLEMENTATION_RULES.md) §7).

## 6. Milestones (with Acceptance Criteria)

**M1 — Walking Skeleton.** Kabuk↔Çekirdek↔Arayüz round-trip a message over the real contracts; storage/journal live; CI + gates scaffolded. *Accept:* contract + a smoke integration test pass.

**M2 — Safe Tooling.** A permissioned, snapshotted, audited `fs.write` works end-to-end. *Accept:* Reversibility + Security + Contract gates pass on the tool path.

**M3 — Offline Reasoning.** Ask a question about a workspace, get a grounded, cited Turkish answer using a **local** model (RAG + graph + memory + reasoning). *Accept:* Offline gate passes for this flow; Locale gate passes.

**M4 — Agentic Editing.** The agent makes a reviewed, reversible multi-file change under effort modes, with a full trace. *Accept:* success criterion #1/#4 ([00](./00_PROJECT_VISION.md) §8) demonstrable; Crash-Recovery gate passes.

**M5 — Advanced Intelligence.** Council + multi-agent + skills operational, all bounded. *Accept:* Budget gate passes; council works offline (single-model multi-stance).

**M6 — Extensible & Beautiful.** Plugins (sandboxed), cloud providers (consented), full TTD/design polish. *Accept:* Plugin sandbox tests pass; A11y/Contrast gate passes; egress consent verified.

**M7 — GA.** Perf targets met on baseline hardware; security audit clean; offline/locale gates green on all OSes; signed installers/updates. *Accept:* all pillar gates green in the full CI matrix ([35](./35_TESTING.md) §7) on Win/mac/Linux, GPU + CPU-only.

## 7. Sequencing Rules

- **Contracts before implementations** ([41](./41_IMPLEMENTATION_RULES.md) §3).
- **Offline/local path before cloud** within each subsystem (PR-6).
- **Safety hooks with the feature**, never after (PR-1).
- **A dependent subsystem is not started before its dependencies pass their gate** (the [ARCHITECTURE_INDEX](./ARCHITECTURE_INDEX.md) dependency graph is the authority).

## 8. Configuration / Tracking

- Progress is tracked against milestones (§6); each subsystem's Definition of Done ([41](./41_IMPLEMENTATION_RULES.md) §6) gates its completion. The version matrix + feature flags ([33](./33_CONFIGURATION.md)) manage in-progress features behind flags until their gates pass.

## 9. Dependencies

- The order derives from the cross-subsystem dependency graph ([ARCHITECTURE_INDEX](./ARCHITECTURE_INDEX.md)); each item's doc is the spec; execution follows [41_IMPLEMENTATION_RULES](./41_IMPLEMENTATION_RULES.md).

## 10. Edge Cases / Risks

- **Model availability/quality for Turkish + code** (P1 risk): mitigate by supporting multiple local backends ([21](./21_PROVIDER_SYSTEM.md)) and a re-embed migration path ([14](./14_EMBEDDINGS.md)); pick the best available and stay swappable (PR-8).
- **GPU/runtime packaging complexity** ([22](./22_PROVIDER_INTEGRATIONS.md)/[07](./07_DESKTOP_ARCHITECTURE.md)): keep a CPU fallback path first (PR-7) so GA doesn't block on GPU packaging.
- **Scope creep** diluting pillars: [43_NON_GOALS](./43_NON_GOALS.md) is the guardrail; every feature must serve a pillar ([00](./00_PROJECT_VISION.md)).
- **Retrofitting a pillar** if built out of order: avoided by P0-first sequencing (§5).
- **AI-implementer drift** from the docs: mitigated by [41](./41_IMPLEMENTATION_RULES.md) §8 + gate tests.

## 11. Failure Recovery (of the plan)

- If a milestone's gate can't pass, the blocking subsystem is fixed before dependents proceed (no building on a broken foundation). Re-sequencing is allowed as long as dependency order + P0-first hold; changes are recorded here.

## 12. Security & Performance in the Plan

- Security ([30](./30_SECURITY.md)) and offline ([32](./32_OFFLINE_FIRST.md)) are P0 substrate + M7 audit — present from the start, verified at GA. Performance ([31](./31_PERFORMANCE.md)) is architecturally designed in (M1) and tuned at M7. Neither is deferred as an afterthought (PR-17).

## 13. Testing in the Plan

- Each milestone's acceptance is defined by its **pillar gates** ([35](./35_TESTING.md) §6). CI grows with the product; gates become blocking as their subsystems land.

## 14. Future (Post-GA) Extensions

- Headless/CLI + remote Core ([01](./01_ARCHITECTURE.md) §19), plugin marketplace ([23](./23_PLUGIN_SYSTEM.md)), fine-tuned Turkish-code models ([14](./14_EMBEDDINGS.md)), enterprise policy/compliance ([24](./24_PERMISSION_SYSTEM.md)/[30](./30_SECURITY.md)), richer graph/timeline UX. Each is a documented, gated addition — never a pillar compromise.

## 15. Anti-Patterns

- Building a feature before its dependencies/contract exist.
- Deferring safety/offline "until later."
- GA-blocking on GPU when a CPU path suffices.
- Letting non-pillar features jump the queue.
- Skipping a milestone's gate to hit a date.

## 16. Things That Must Never Happen

1. A dependent subsystem is built on an ungated/incomplete dependency.
2. A pillar-guaranteeing hook (permission/snapshot/timeline) is deferred rather than built with its feature.
3. GA is declared with a failing pillar gate on any supported OS/hardware.
4. Scope creep ships a feature that dilutes a pillar ([43](./43_NON_GOALS.md)).

## 17. Relationship With Other Subsystems

Sequences all subsystem docs; ordered by [ARCHITECTURE_INDEX](./ARCHITECTURE_INDEX.md) dependencies; executed per [41_IMPLEMENTATION_RULES](./41_IMPLEMENTATION_RULES.md); gated by [35_TESTING](./35_TESTING.md); bounded by [43_NON_GOALS](./43_NON_GOALS.md); serves [00_PROJECT_VISION](./00_PROJECT_VISION.md).

## 18. Migration Considerations

- The roadmap is a living plan; re-sequencing is allowed within the rules (§7) and recorded here with rationale. Milestone acceptance criteria only tighten. Post-GA additions follow [41](./41_IMPLEMENTATION_RULES.md) and never regress a shipped pillar guarantee.
