# 41 — Implementation Rules (Uygulama Kuralları)

> Part of the **turkish.code Engineering Bible**. Canonical source of truth (meta/process).
> **Status:** Canonical · **Version:** 1.0 · **Last updated:** 2026-07-12
> **Related:** [02_DESIGN_PRINCIPLES](./02_DESIGN_PRINCIPLES.md) · [36_CODING_STANDARDS](./36_CODING_STANDARDS.md) · [35_TESTING](./35_TESTING.md) · [40_DOCUMENTATION_RULES](./40_DOCUMENTATION_RULES.md) · [AGENTS.md](./AGENTS.md)

---

## 1. Purpose

The **process rules for turning this documentation into code** — the workflow, gates, and order that any implementer (human or AI) must follow when building or extending turkish.code. Where [02](./02_DESIGN_PRINCIPLES.md) is *how we decide*, [36](./36_CODING_STANDARDS.md) is *how we write code*, and [35](./35_TESTING.md) is *how we test*, this doc is *how we execute a change end-to-end* so the pillars survive contact with implementation. It is the operational checklist that binds the Bible to reality.

## 2. Scope

The change workflow (design→contract→implement→test→doc→review), the pre-implementation checklist, the definition of done, the implementation order/priority (referencing the roadmap), and the rules specific to AI-agent implementers. Out of scope: architecture ([01](./01_ARCHITECTURE.md)), coding style ([36](./36_CODING_STANDARDS.md)), test taxonomy ([35](./35_TESTING.md)), the actual sequence/milestones ([42_ROADMAP](./42_ROADMAP.md)).

## 3. Golden Rules (Always)

1. **The docs are the spec.** Implement to the Bible; if the Bible is silent/ambiguous, resolve it *in the docs first* ([40](./40_DOCUMENTATION_RULES.md)), then code. Don't invent undocumented behavior for a load-bearing decision.
2. **Contracts before code.** Any cross-tier/cross-subsystem interaction is defined in `ipc-schema`/storage schema first, codegen'd, then implemented ([10](./10_IPC.md)/[29](./29_STORAGE.md), PR-8).
3. **Pillars are gates, not goals.** No change merges that breaks a pillar gate ([35](./35_TESTING.md) §6): security, offline, reversibility, crash-recovery, Turkish-locale, budgets, contracts, a11y, performance.
4. **Every side effect is a permissioned, snapshotted, audited tool** ([20](./20_TOOL_SYSTEM.md)/[24](./24_PERMISSION_SYSTEM.md)/[27](./27_SNAPSHOTS.md)/[26](./26_TIMELINE.md)) — no exceptions (PR-1/PR-2).
5. **Docs + tests ship with the code**, in the same change ([40](./40_DOCUMENTATION_RULES.md)/[35](./35_TESTING.md)).

## 4. Pre-Implementation Checklist (Per Subsystem/Feature)

Before writing code, answer (the [02](./02_DESIGN_PRINCIPLES.md) §5 checklist, operationalized):

1. **Which pillar(s)** does this serve? (None ⇒ reconsider, [43](./43_NON_GOALS.md).)
2. **Side effects?** Do they route through the single broker path (PR-2, [08](./08_TAURI_ARCHITECTURE.md))?
3. **Reversible?** Where are the snapshots ([27](./27_SNAPSHOTS.md))?
4. **Events?** What does it record to the Timeline ([26](./26_TIMELINE.md))?
5. **Offline path?** Fully local ([32](./32_OFFLINE_FIRST.md))?
6. **Degradation ladder?** ([31](./31_PERFORMANCE.md)/PR-7).
7. **Contract?** Versioned interface at its boundary ([10](./10_IPC.md), PR-8)?
8. **Budgets?** ([17](./17_EFFORT_MODES.md)/PR-14).
9. **Typed errors?** ([38](./38_ERROR_HANDLING.md)).
10. **Turkish-locale concerns?** ([03](./03_UI_SYSTEM.md)/[04](./04_TURKISH_DESIGN_LANGUAGE.md), PR-12).
11. **Security review?** Any new capability/egress/secret path ([30](./30_SECURITY.md)/[24](./24_PERMISSION_SYSTEM.md)/[34](./34_API_KEYS.md))?
12. **Which docs must update?** ([40](./40_DOCUMENTATION_RULES.md)).

If any answer is unknown, the design isn't ready — fix the doc first.

## 5. The Change Workflow

```
1. DESIGN: read the owning doc(s); resolve gaps in the docs first (40).
2. CONTRACT: define/extend schema (ipc-schema / depo/schema); codegen; commit generated (37 §7).
3. IMPLEMENT: code per 36; DI-wired (09 §7); side effects via broker (08); bounded (17).
4. TEST: unit + contract + integration; add/extend the relevant PILLAR GATE tests (35 §6).
5. DOC: update the subsystem doc + glossary + index in the SAME change (40).
6. VERIFY: run gates locally (security/offline/locale/reversibility/recovery/budget where relevant).
7. REVIEW: self-review against this checklist; peer/agent review for safety-critical paths.
8. MERGE: only if all gates + lint/type/contract-drift pass (35 §7).
```

## 6. Definition of Done

A change is **done** only when **all** hold:
- Behavior matches its doc; the doc is updated ([40](./40_DOCUMENTATION_RULES.md)).
- Contracts codegen'd + committed, no drift ([10](./10_IPC.md)/[37](./37_REPOSITORY_STRUCTURE.md)).
- Unit + contract + integration tests pass; new invariants have gate tests ([35](./35_TESTING.md)).
- All **pillar gates** pass ([35](./35_TESTING.md) §6).
- Lint/format/typecheck clean ([36](./36_CODING_STANDARDS.md)).
- No new ungated side-effect path, no secret leak, offline still works (spot-checked).
- Errors are typed + localized ([38](./38_ERROR_HANDLING.md)); logs are clean/redacted ([39](./39_LOGGING.md)).
- Migration provided if a contract/schema/config changed ([29](./29_STORAGE.md)/[33](./33_CONFIGURATION.md)).

"It works on my machine" is not done; "the gates pass and the doc matches" is.

## 7. Implementation Order & Priority

- The **build sequence** (which subsystems first, dependencies, milestones) is [42_ROADMAP](./42_ROADMAP.md); the **dependency map** is [ARCHITECTURE_INDEX](./ARCHITECTURE_INDEX.md). Implementers follow that order so foundations exist before dependents.
- **Priority rule:** build the **structural safety substrate early** (tier boundaries [01], IPC [10], storage/journal [29]/[26], permission [24], snapshots [27]) — because retrofitting a pillar guarantee is far harder than building on it (PR-1/PR-17). Intelligence features layer on top.
- Within a subsystem, build the **offline/local path first** (PR-6), then optional cloud enhancements.

## 8. Rules for AI-Agent Implementers (Important)

turkish.code will often be implemented/extended by AI agents ([18](./18_AGENT_SYSTEM.md)/[AGENTS.md](./AGENTS.md)). Additional rules:
- **Read the owning doc + [44_GLOSSARY](./44_GLOSSARY.md) + [02_DESIGN_PRINCIPLES](./02_DESIGN_PRINCIPLES.md) before coding a subsystem.** Don't infer architecture from partial context.
- **Never bypass a gate to "make it pass."** A failing pillar gate is a design signal, not an obstacle.
- **Don't invent undocumented cross-tier behavior.** If a contract is needed, define it in `ipc-schema` and document it.
- **Keep changes reviewable and scoped** (PR-13): one responsibility per change; large features decompose into ordered steps ([42](./42_ROADMAP.md)).
- **Cite the governing invariant in code/comments** ([36](./36_CODING_STANDARDS.md) §7) so the next agent can trace intent.
- **When uncertain, prefer the safe/reversible/offline choice** (priority order, [02](./02_DESIGN_PRINCIPLES.md) §4).

## 9. Configuration

- CI encodes these rules as gates ([35](./35_TESTING.md) §7); pre-commit hooks run fast checks ([36](./36_CODING_STANDARDS.md)). The Definition of Done (§6) is the merge policy.

## 10. Dependencies

- Draws together [02](./02_DESIGN_PRINCIPLES.md), [36](./36_CODING_STANDARDS.md), [35](./35_TESTING.md), [40](./40_DOCUMENTATION_RULES.md), [42_ROADMAP](./42_ROADMAP.md), [ARCHITECTURE_INDEX](./ARCHITECTURE_INDEX.md); enforced via [10_IPC](./10_IPC.md)/[29_STORAGE](./29_STORAGE.md) contracts.

## 11. Edge Cases

- **Doc is wrong/insufficient:** update the doc (with reasoning) *before/with* the code; never silently diverge ([40](./40_DOCUMENTATION_RULES.md) §8).
- **Gate seems overly strict for a legit change:** the gate is (almost always) right; if genuinely wrong, changing a gate requires a vision-level review ([00](./00_PROJECT_VISION.md)/[35](./35_TESTING.md)), not a bypass.
- **Urgent fix vs process:** hotfixes still pass security/reversibility gates (those protect users most); non-safety gates may be fast-tracked with follow-up, documented.
- **Large multi-subsystem feature:** decompose per [42](./42_ROADMAP.md), land in dependency order, keep each step green.

## 12. Failure Recovery (of the process)

- A merged change that later breaks a gate (a regression the suite missed) triggers: revert-or-fix-forward, add the missing test, and update the doc if the invariant was under-specified. The gates are strengthened, not weakened.

## 13. Security

- Any change touching capabilities/egress/secrets/sandbox ([24](./24_PERMISSION_SYSTEM.md)/[30](./30_SECURITY.md)/[34](./34_API_KEYS.md)/[23](./23_PLUGIN_SYSTEM.md)) requires an explicit security review step (§5.7) and its Security-Gate tests. Default-deny for new capabilities ([24](./24_PERMISSION_SYSTEM.md)).

## 14. Performance

- Architectural performance (planes/streaming/backpressure/budgets) is designed in from step 1 ([31](./31_PERFORMANCE.md)/PR-17); micro-optimization comes after correctness, justified by measurement (§ [36](./36_CODING_STANDARDS.md) §12).

## 15. Testing Strategy

- This doc *is* the process that guarantees tests exist; §5 step 4 + §6 make gate tests non-optional. The suite/gates themselves are [35_TESTING](./35_TESTING.md).

## 16. Future Extensions

- A machine-checkable "Definition of Done" bot; PR templates encoding §4/§6; an AI-onboarding conformance check that verifies an agent read the required docs before large changes.

## 17. Examples

- Adding a `web.search` tool: (1) design against [20](./20_TOOL_SYSTEM.md)/[24](./24_PERMISSION_SYSTEM.md)/[30](./30_SECURITY.md); (2) add its `ToolDef` + `net.egress` capability in schema; (3) implement as a brokered, default-off, consent-gated tool ([08](./08_TAURI_ARCHITECTURE.md)); (4) add Security + Offline gate tests (off by default; egress consented); (5) update [20](./20_TOOL_SYSTEM.md) doc + glossary; (6) verify gates; (7) review. Done only when all pass.

## 18. Anti-Patterns

- Coding before the contract/doc exists.
- Bypassing a pillar gate to merge.
- Adding an ungated side-effect/egress/secret path.
- Shipping code without updating its doc or tests.
- Inventing undocumented cross-tier behavior.
- Micro-optimizing before correctness.
- Landing a giant unreviewable multi-subsystem change at once.

## 19. Things That Must Never Happen

1. A change merges that fails a pillar gate ([35](./35_TESTING.md) §6).
2. A subsystem's behavior changes without its doc + tests updating in the same change.
3. A new side-effect/egress/secret path ships without security review + gate tests.
4. A contract/schema change lands without codegen + migration.
5. An implementer invents undocumented load-bearing behavior instead of documenting it first.

## 20. Relationship With Other Subsystems

Operationalizes [02_DESIGN_PRINCIPLES](./02_DESIGN_PRINCIPLES.md); enforces [36_CODING_STANDARDS](./36_CODING_STANDARDS.md)/[35_TESTING](./35_TESTING.md)/[40_DOCUMENTATION_RULES](./40_DOCUMENTATION_RULES.md); sequenced by [42_ROADMAP](./42_ROADMAP.md) + [ARCHITECTURE_INDEX](./ARCHITECTURE_INDEX.md); the process an AI implementer follows per [AGENTS.md](./AGENTS.md); protects the pillars of [00_PROJECT_VISION](./00_PROJECT_VISION.md).

## 21. Migration Considerations

- The workflow/gates evolve deliberately; strengthening them is additive. Weakening a safety gate requires vision-level sign-off ([00](./00_PROJECT_VISION.md)). New required checklist items apply to new changes and are back-filled as tech-debt tasks ([42](./42_ROADMAP.md)).
