# 43 — Non-Goals (Hedef Olmayanlar)

> Part of the **turkish.code Engineering Bible**. Canonical source of truth.
> **Status:** Canonical · **Version:** 2.0 · **Last updated:** 2026-07-12
> **Changed in v2.0** (per [52_ADR_LOG](./52_ADR_LOG.md)): added the recovered **rejected provider/architecture ideas** (§4b). **NVIDIA NIM is NOT a non-goal** — it was rejected then *reintroduced* (ADR-0007) and is now a primary provider. Some prior "offline-first sovereign / heavy-privacy" non-goals are relaxed (ADR-0010).
> **Related:** [00_PROJECT_VISION](./00_PROJECT_VISION.md) · [52_ADR_LOG](./52_ADR_LOG.md) · [21_PROVIDER_SYSTEM](./21_PROVIDER_SYSTEM.md) · [42_ROADMAP](./42_ROADMAP.md)

---

## 1. Purpose

States, explicitly, what turkish.code **is not** and **will not** be. A focused product is defined as much by what it refuses as by what it builds. This document is the guardrail against scope creep ([00](./00_PROJECT_VISION.md) §10) and the reference an implementer/AI consults before adding something that "seems useful." If a proposal matches a non-goal, it is rejected by default; overturning a non-goal requires a deliberate vision revision ([00](./00_PROJECT_VISION.md)).

## 1b. Rejected Provider & Architecture Ideas (recovered — §4b detail)

From the engineering history ([52_ADR_LOG](./52_ADR_LOG.md) §4). These were **rejected** and are non-goals **unless** an ADR reverses them (as happened with NVIDIA NIM). **Read chronologically** ([52](./52_ADR_LOG.md) §0): the "Rejected Ideas" list is point-in-time.

| Rejected idea | Status | Note |
|---|---|---|
| **Cerebras** provider | Non-goal | No reversal. |
| **HuggingFace** provider | Non-goal | No reversal. |
| **NVIDIA NIM** | **NOT a non-goal** | **Reversed → primary provider** (ADR-0007). |
| **Provider-first routing** as primary abstraction | Non-goal | Superseded by model-first (ADR-0005). |
| **Simple static failover** as sufficient | Non-goal | Superseded by smart failover/cooldown (ADR-0009). |
| **Static MODEL_POOLS** as the final design | Non-goal | Superseded by dynamic/model-first (ADR-0004/0005). |
| **Heavy keyring dependency** | Non-goal | Light key handling instead (ADR-0010, [34](./34_API_KEYS.md)). |
| **Large privacy/key-management sections** | Non-goal | Slim security instead (ADR-0010, [30](./30_SECURITY.md)). |
| **Hybrid mode as a separate architecture** | Non-goal | Routing already spans cloud+local; no separate mode. |

## 2. Scope

The deliberate exclusions across product surface, architecture, and business model, each with rationale and the pillar it protects. Out of scope: the positive vision ([00](./00_PROJECT_VISION.md)) and future *extensions that are allowed* ([42](./42_ROADMAP.md) §14 — those are deferred goals, not non-goals).

## 3. How To Use This Document

Before adding a feature/dependency/capability, check it against these. A match = default reject. A "deferred goal" ([42](./42_ROADMAP.md)) is different from a "non-goal" (here): deferred = later; non-goal = not this product. When unsure, the priority order ([02](./02_DESIGN_PRINCIPLES.md) §4) and pillars ([00](./00_PROJECT_VISION.md)) decide.

## 4. Product Non-Goals

- **NG-1 — Not a cloud SaaS / web app.** turkish.code is a local desktop app ([07](./07_DESKTOP_ARCHITECTURE.md)). No hosted multi-tenant service, no accounts-in-the-cloud, no server-side processing of user code. *Protects:* P1 (sovereignty). *Rationale:* the whole point is data stays local.
- **NG-2 — Not a general chatbot / assistant for everything.** It is a **software-engineering** companion. It won't pretend to be a general life assistant, image generator, or search engine. *Protects:* focus. *Rationale:* every non-coding feature dilutes the pillars.
- **NG-3 — Not mobile or browser-based.** No iOS/Android/PWA. Desktop only ([07](./07_DESKTOP_ARCHITECTURE.md)). *Rationale:* the agentic, filesystem-editing, GPU-inference workflow is a desktop workflow.
- **NG-4 — Not English-first with Turkish bolted on.** The reverse of the market. Turkish is the substrate ([04](./04_TURKISH_DESIGN_LANGUAGE.md)); English is a supported secondary locale, never the primary design frame. *Protects:* P2.
- **NG-5 — Not a telemetry/data-collection product.** No behavioral analytics, no "anonymous usage" phoning home by default, no training on user data. Any opt-in diagnostic is explicit + categorized ([30](./30_SECURITY.md)/[39](./39_LOGGING.md)). *Protects:* P1. *Rationale:* trust is the product.
- **NG-6 — Not a VCS or a replacement for git.** It reads VCS ignore rules and can integrate, but snapshots ([27](./27_SNAPSHOTS.md)) are for agent-undo, not version control. *Rationale:* don't reinvent git.
- **NG-7 — Not a plugin free-for-all.** Extensibility is real but **sandboxed and capability-gated** ([23](./23_PLUGIN_SYSTEM.md)); we will not allow plugins that bypass permissions, egress, or the trusted-tier boundary for convenience. *Protects:* P1/P5.

## 5. Architectural Non-Goals

- **NG-8 — No mandatory network dependency for core features.** Cloud is always optional ([32](./32_OFFLINE_FIRST.md)). We will not implement a core capability that only works online. *Protects:* P1/PR-6.
- **NG-9 — No default-open network ports / listening services.** The Core Channel is stdio ([10](./10_IPC.md)); we won't expose local HTTP servers by default. *Protects:* P1/security ([30](./30_SECURITY.md)).
- **NG-10 — No secrets outside the OS keychain.** We will never add a "convenient" secret store in config/DB ([34](./34_API_KEYS.md)). *Protects:* P1.
- **NG-11 — No side-effect path outside the broker.** We won't add "just this once" direct fs/shell/net access ([08](./08_TAURI_ARCHITECTURE.md), PR-2). *Protects:* P5.
- **NG-12 — Not Electron / bundled-Chromium.** Tauri + native WebView ([08](./08_TAURI_ARCHITECTURE.md)) for size/perf/privilege separation. *Rationale:* [01](./01_ARCHITECTURE.md) §4.4.
- **NG-13 — No hard NVIDIA/GPU requirement.** GPU is first-class but never mandatory; CPU fallback always exists ([22](./22_PROVIDER_INTEGRATIONS.md), PR-7). *Protects:* reach + PR-6.
- **NG-14 — No unbounded autonomy.** No agents that loop/recurse/act without budgets, permissions, and oversight ([17](./17_EFFORT_MODES.md)/[18](./18_AGENT_SYSTEM.md)/[24](./24_PERMISSION_SYSTEM.md), PR-14). *Protects:* P5.

## 6. Behavioral / UX Non-Goals

- **NG-15 — No silent/irreversible agent actions.** Every mutation is snapshotted ([27](./27_SNAPSHOTS.md)); egress/destructive actions are gated ([24](./24_PERMISSION_SYSTEM.md)). *Protects:* P4/P5.
- **NG-16 — No hidden reasoning.** We won't ship "magic" that hides what the agent did ([15](./15_REASONING_ENGINE.md)/[26](./26_TIMELINE.md)). *Protects:* P4/P5.
- **NG-17 — No dark patterns for consent.** Egress/cloud/telemetry consent is honest, per-category, revocable ([24](./24_PERMISSION_SYSTEM.md) §9); no pre-checked "share data" boxes. *Protects:* P1.
- **NG-18 — No ASCII-folded / locale-broken Turkish.** Correct Turkish casing/glyphs are a correctness property (PR-12); we won't ship shortcuts that mangle it. *Protects:* P2.

## 7. Business / Distribution Non-Goals (Stance)

- **NG-19 — No lock-in via cloud-only features.** The local product is complete; we won't cripple it to upsell cloud ([32](./32_OFFLINE_FIRST.md)). *Protects:* trust.
- **NG-20 — No selling/monetizing user data.** Ever. *Protects:* P1 (the deepest non-goal).

## 8. "Deferred Goals" (NOT Non-Goals — Clarification)

To avoid confusion: the following are **allowed future work** ([42](./42_ROADMAP.md) §14), not non-goals — they may be built *if* they preserve the pillars:
- Headless/CLI mode; a remote Core on a trusted LAN GPU box (consent-gated) ([01](./01_ARCHITECTURE.md) §19).
- Plugin marketplace (curated/signed) ([23](./23_PLUGIN_SYSTEM.md)).
- Fine-tuned Turkish-code models ([14](./14_EMBEDDINGS.md)).
- Enterprise policy/compliance features ([24](./24_PERMISSION_SYSTEM.md)/[30](./30_SECURITY.md)).
The line: a deferred goal *preserves* the pillars; a non-goal would *violate* one.

## 9. Edge Cases (Applying Non-Goals)

- **"Add a quick cloud-only feature for speed":** violates NG-8; reject or add a local path first.
- **"Let plugins have direct fs for convenience":** violates NG-7/NG-11; reject.
- **"Collect anonymous usage to improve UX":** violates NG-5; only as explicit opt-in ([30](./30_SECURITY.md)).
- **"Support a web version":** violates NG-1/NG-3; out of scope.
- **"Store the API key in settings.json so it's easy":** violates NG-10; keychain only.
- **"Make GPU required for acceptable speed":** violates NG-13; keep CPU path.

## 10. Failure Recovery (of scope discipline)

- If a non-goal-violating feature slips in, it's a design defect: remove it or redesign to respect the pillar it violated. Non-goals are checked in review ([41](./41_IMPLEMENTATION_RULES.md) §4/§18).

## 11. Security / Privacy Relationship

- Most non-goals exist to protect **P1 (privacy/sovereignty)** and **P5 (trust)** — NG-1/5/8/9/10/11/17/19/20 are all privacy/trust guards. They are the negative-space expression of [30_SECURITY](./30_SECURITY.md).

## 12. Testing Strategy

- Some non-goals are *tested as invariants* (the pillar gates, [35](./35_TESTING.md) §6): no default port (NG-9), no secret outside keychain (NG-10), no side-effect outside broker (NG-11), no telemetry-by-default (NG-5), no unbounded loops (NG-14), offline core (NG-8). A violation is a failing gate → release blocker.

## 13. Anti-Patterns (Meta)

- Treating a non-goal as "just this once" flexible.
- Confusing a deferred goal with a non-goal (or vice versa).
- Adding scope that doesn't serve a pillar.
- Rationalizing a privacy/trust compromise as a UX win.

## 14. Things That Must Never Happen

1. A non-goal is silently violated to ship a feature.
2. User data is sold, or telemetry is collected without explicit opt-in.
3. A core feature becomes cloud-only.
4. A convenience path bypasses the broker/permission/keychain invariants.
5. A non-goal is overturned without a documented vision revision ([00](./00_PROJECT_VISION.md)).

## 15. Relationship With Other Subsystems

The negative-space of [00_PROJECT_VISION](./00_PROJECT_VISION.md); enforced as invariants by [30_SECURITY](./30_SECURITY.md)/[32_OFFLINE_FIRST](./32_OFFLINE_FIRST.md)/[24_PERMISSION_SYSTEM](./24_PERMISSION_SYSTEM.md)/[34_API_KEYS](./34_API_KEYS.md); guards the plan in [42_ROADMAP](./42_ROADMAP.md); checked by [41_IMPLEMENTATION_RULES](./41_IMPLEMENTATION_RULES.md); tested by [35_TESTING](./35_TESTING.md).

## 16. Migration Considerations

- Non-goals are among the most stable statements in the Bible. Converting a non-goal into a goal (or a deferred goal) requires an explicit, reasoned revision of [00_PROJECT_VISION](./00_PROJECT_VISION.md) and a reconciliation pass across affected docs ([40](./40_DOCUMENTATION_RULES.md)). Adding a new non-goal is additive and encouraged when scope pressure appears.
