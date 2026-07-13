# 35 — Testing Strategy (Test Stratejisi)

> Part of the **turkish.code Engineering Bible**. Canonical source of truth.
> **Status:** Canonical · **Version:** 1.0 · **Last updated:** 2026-07-12
> **Owner:** cross-cutting
> **Related:** [01_ARCHITECTURE](./01_ARCHITECTURE.md) · [10_IPC](./10_IPC.md) · [30_SECURITY](./30_SECURITY.md) · [32_OFFLINE_FIRST](./32_OFFLINE_FIRST.md) · [36_CODING_STANDARDS](./36_CODING_STANDARDS.md) · [41_IMPLEMENTATION_RULES](./41_IMPLEMENTATION_RULES.md)

---

## 1. Purpose

Defines **how turkish.code is tested**: the test pyramid across three tiers and two contract seams, the special **gates** that protect the pillars (security, offline, Turkish-locale, reversibility, crash-recovery, determinism), the CI matrix, and the standards for what "tested" means. Because the pillars are structural, the tests that *prove* the pillars are non-negotiable gates — a build that fails them cannot ship. Each subsystem doc has a "Testing Strategy" section; this doc is the umbrella that unifies them.

## 2. Scope

Test taxonomy/layers, per-tier tooling, contract/integration/e2e, the pillar gates, fixtures/fakes, CI matrix, coverage philosophy, and flakiness policy. Out of scope: subsystem-specific test cases (their docs), coding style ([36](./36_CODING_STANDARDS.md)).

## 3. Testing Philosophy

- **Test the guarantees, not just the code.** The most important tests assert the *invariants* (no ungated side effect, no secret leak, offline works, edits reversible) — see the gates (§6).
- **Fast feedback, layered.** Many cheap unit tests; fewer integration; fewest e2e — the classic pyramid, adapted to a 3-tier app.
- **Deterministic where the system is deterministic** (PR-15); isolate model non-determinism behind fakes so the *system* is testable even though the *model* varies.
- **Fakes at boundaries.** The DI container ([09](./09_PYTHON_BACKEND.md) §7) and codegen'd contracts ([10](./10_IPC.md)) make fakes easy: fake providers, fake broker, fake storage.
- **Turkish-first is a test dimension** (PR-12), not an afterthought.

## 4. Test Taxonomy (Pyramid)

```
        ▲ e2e (few): packaged app, real Kabuk+Çekirdek, driven UI, per-OS
        │ integration (some): cross-tier flows, real IPC, fake models/network
        │ contract (some): generated from ipc-schema + storage schemas
        ▼ unit (many): per-subsystem, against interfaces with fakes
```

### 4.1 Unit
- **Arayüz:** Vitest + Testing Library (components, stores, bridge client with a mock Bridge).
- **Kabuk:** `cargo test` (permission eval, framing/correlation, broker gating, secret vault, supervisor).
- **Çekirdek:** `pytest`/`pytest-asyncio` per subsystem against interfaces with fakes.
- **Design system:** Storybook + Vitest ([06](./06_COMPONENT_LIBRARY.md)).

### 4.2 Contract
- Generated from `packages/ipc-schema` ([10](./10_IPC.md)) and `depo/schema` ([29](./29_STORAGE.md)): round-trip every message/type across TS/Rust/Python; a **codegen-drift check** fails CI if generated bindings are stale ([37](./37_REPOSITORY_STRUCTURE.md) §7).

### 4.3 Integration
- Real Kabuk + real Çekirdek over the real Core Channel, with **fake providers** (deterministic model outputs) and **network disabled** — drive the canonical lifecycle ([01](./01_ARCHITECTURE.md) §8): send → reason → tool → snapshot → timeline → result. Includes fault injection ([28](./28_CRASH_RECOVERY.md)).

### 4.4 E2E
- The **packaged app** on each OS ([07](./07_DESKTOP_ARCHITECTURE.md)) driven via Playwright/Tauri driver: real UI, real flows, real local (small) model or a scripted provider. Fewest, slowest, highest-fidelity.

## 5. Fakes, Fixtures & Determinism

- **Fake Provider:** returns scripted/deterministic completions + tool-call sequences → lets us test reasoning/agents/council deterministically ([15](./15_REASONING_ENGINE.md)/[16](./16_COUNCIL_MODE.md)/[18](./18_AGENT_SYSTEM.md)).
- **Fake Broker:** records permission requests and simulates allow/deny/prompt → tests the tool/permission path ([20](./20_TOOL_SYSTEM.md)/[24](./24_PERMISSION_SYSTEM.md)) without touching the real FS.
- **In-memory/temp storage** fixtures ([29](./29_STORAGE.md)).
- **Golden fixtures** for retrieval quality, chunking, graph extraction, embeddings determinism, trace shape.
- **Determinism harness:** replay a journal → assert reconstructed state (PR-15, [26](./26_TIMELINE.md)/[28](./28_CRASH_RECOVERY.md)).

## 6. The Pillar Gates (Non-Negotiable, Block Release)

These suites *prove the pillars*. A failure blocks the build/release. Each aggregates the "Testing Strategy" of the relevant subsystem docs.

| Gate | Asserts | Sourced from |
|---|---|---|
| **Security Gate** | the 10 invariants ([30](./30_SECURITY.md) §12): no ungated side effect, no secret leak, no default port, fail-safe deny, sandbox holds, artifacts verified | [30](./30_SECURITY.md), [24](./24_PERMISSION_SYSTEM.md), [34](./34_API_KEYS.md), [20](./20_TOOL_SYSTEM.md), [23](./23_PLUGIN_SYSTEM.md) |
| **Offline-Fallback Gate** | with all cloud providers disabled, the router falls back to local Ollama and the core flow still works ([32](./32_OFFLINE_FIRST.md) §15) + no-CDN | [32](./32_OFFLINE_FIRST.md), [21](./21_PROVIDER_SYSTEM.md), [45](./45_ROUTING_ORCHESTRATION.md) |
| **Provider/Routing Gate** | model-first selection; smart failover/retry/timeout/cooldown; quota-preserving + **quality-under-exhaustion**; cost-mode reweighting; provider-independence (swap providers, no core change) | [45](./45_ROUTING_ORCHESTRATION.md), [47](./47_SCORING_ALGORITHMS.md), [48](./48_QUOTA_TIER_MANAGEMENT.md), [21](./21_PROVIDER_SYSTEM.md) |
| **Reversibility Gate** | every mutation snapshot-backed; round-trip undo byte-identical | [27](./27_SNAPSHOTS.md), [20](./20_TOOL_SYSTEM.md) |
| **Crash-Recovery Gate** | kill at every phase → consistent resume, no corruption | [28](./28_CRASH_RECOVERY.md), [26](./26_TIMELINE.md), [29](./29_STORAGE.md) |
| **Turkish-Locale Gate** | casing (İ/ı), collation, plurals, glyphs, no ASCII-folding | [03](./03_UI_SYSTEM.md), [04](./04_TURKISH_DESIGN_LANGUAGE.md), [14](./14_EMBEDDINGS.md), [09](./09_PYTHON_BACKEND.md) |
| **Budget Gate** | no unbounded loop/recursion/fan-out; effort caps honored | [17](./17_EFFORT_MODES.md), [15](./15_REASONING_ENGINE.md), [18](./18_AGENT_SYSTEM.md), [16](./16_COUNCIL_MODE.md) |
| **Contract Gate** | codegen not drifted; all message/type round-trips pass | [10](./10_IPC.md), [29](./29_STORAGE.md) |
| **A11y/Contrast Gate** | WCAG AA both themes; keyboard; reduced-motion | [04](./04_TURKISH_DESIGN_LANGUAGE.md), [03](./03_UI_SYSTEM.md), [05](./05_ANIMATION_SYSTEM.md), [06](./06_COMPONENT_LIBRARY.md) |
| **Performance Gate** | budget targets on baseline hardware; no regressions | [31](./31_PERFORMANCE.md) |

## 7. CI Matrix

- **OS:** Windows, macOS, Linux — build installers ([07](./07_DESKTOP_ARCHITECTURE.md)) + run e2e per OS WebView.
- **Hardware:** GPU-present and **GPU-absent (CPU-only)** paths ([22](./22_PROVIDER_INTEGRATIONS.md)/[31](./31_PERFORMANCE.md)) — CPU-only must pass all functional + offline gates.
- **Stages:** lint/format/typecheck → unit → contract (+ drift) → integration (+ fault injection) → gates (security/offline/locale/…) → e2e → performance → packaging.
- **Secret scanning** + **dependency audit** run on every build ([30](./30_SECURITY.md)).
- A failing pillar gate is **not** overridable.

## 8. Coverage Philosophy

- Coverage is a **signal, not a target**; we require coverage of the *invariants and error paths*, not a magic percentage. Every typed error ([38](./38_ERROR_HANDLING.md)) and every "must never happen" ([per subsystem]) has a test that provokes and asserts it.
- New side-effect paths, permission changes, and contract changes require accompanying gate-level tests (enforced in review, [41](./41_IMPLEMENTATION_RULES.md)).

## 9. Configuration / Tooling

- Vitest/Playwright (TS), `cargo test`/clippy (Rust), pytest/pytest-asyncio/mypy/ruff (Python), Storybook (design). Orchestrated by the repo task graph ([37](./37_REPOSITORY_STRUCTURE.md)). Deterministic seeds for any randomness. Time is injectable (freeze clocks) for deterministic snapshots/animation tests.

## 10. Dependencies

- The DI container ([09](./09_PYTHON_BACKEND.md)) and codegen'd contracts ([10](./10_IPC.md)/[29](./29_STORAGE.md)) enable fakes/contract tests; every subsystem provides its own suite feeding the gates (§6).

## 11. Edge Cases (Testing Them)

- **Non-determinism:** isolate behind fake providers; never assert exact model text — assert structure/behavior (tool called, grounded, bounded).
- **Flaky e2e:** quarantined + fixed, not muted; a flaky test is a bug. Zero-tolerance flakiness policy on gates.
- **Long/soak scenarios:** memory/disk growth bounded ([31](./31_PERFORMANCE.md)); run in a nightly job.
- **Adversarial inputs:** injection/malicious-plugin/path-traversal fixtures feed the Security Gate.
- **Locale corner cases:** İstanbul/ırmak/IĞDIR, mixed tr/en/code, ₺ — in the Locale Gate.

## 12. Failure Recovery (of the test suite)

- Deterministic + hermetic tests (no network, temp dirs) mean reruns are stable. Fault-injection tests are the *product's* recovery being tested; the suite itself is designed to be reproducible (seeds, frozen time, isolated storage).

## 13. Security (of testing)

- Tests never use real secrets/keys (fakes only); the secret scanner ensures no fixtures leak credentials. Adversarial security tests run in isolation. See [30_SECURITY](./30_SECURITY.md).

## 14. Performance (of testing)

- The pyramid keeps feedback fast; heavy e2e/perf/soak run in later CI stages/nightly. Unit + contract must be seconds-fast for local dev.

## 15. Future Extensions

- Property-based/fuzz testing for contracts + permission engine; mutation testing on safety-critical modules ([24](./24_PERMISSION_SYSTEM.md)/[27](./27_SNAPSHOTS.md)/[28](./28_CRASH_RECOVERY.md)); model-eval harness for reasoning quality regressions; record/replay of real sessions as regression fixtures; automated a11y audits expansion.

## 16. Examples

- A single integration test drives: `session.send` → fake provider emits a `fs.write` tool call → fake broker asserts permission was requested → snapshot recorded → timeline event appended → undo restores original — touching the Reversibility, Budget, and Contract gates at once.

## 17. Anti-Patterns

- Asserting exact model output (brittle; non-deterministic).
- Muting flaky tests instead of fixing them.
- Skipping a pillar gate "to unblock a release."
- Tests that hit the real network or use real secrets.
- Coverage-percentage chasing without testing invariants/error paths.
- New side-effect/permission/contract code without gate tests.

## 18. Things That Must Never Happen

1. A release ships with a failing pillar gate (§6).
2. Tests use real secrets or real network egress.
3. A new side-effect path merges without a permission/reversibility test.
4. A contract change merges with stale/undrifted-unchecked bindings.
5. Turkish-locale correctness is untested for a text-transforming change.

## 19. Relationship With Other Subsystems

Aggregates every subsystem's "Testing Strategy" into unified gates; validates the invariants of [30](./30_SECURITY.md)/[32](./32_OFFLINE_FIRST.md)/[24](./24_PERMISSION_SYSTEM.md)/[27](./27_SNAPSHOTS.md)/[28](./28_CRASH_RECOVERY.md)/[17](./17_EFFORT_MODES.md); relies on [10_IPC](./10_IPC.md)/[29_STORAGE](./29_STORAGE.md) contracts + [09_PYTHON_BACKEND](./09_PYTHON_BACKEND.md) DI for fakes; enforced operationally by [41_IMPLEMENTATION_RULES](./41_IMPLEMENTATION_RULES.md); coding-level testability from [36_CODING_STANDARDS](./36_CODING_STANDARDS.md).

## 20. Migration Considerations

- New pillar-relevant behavior adds a gate test in the same change (PR-18/[41](./41_IMPLEMENTATION_RULES.md)). Contract/schema changes regenerate + re-verify bindings. Removing a test requires justification; removing a *gate* requires a vision-level review ([00](./00_PROJECT_VISION.md)). Perf baselines are re-tuned per hardware-tier changes ([31](./31_PERFORMANCE.md)).
