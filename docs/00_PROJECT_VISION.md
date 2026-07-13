# 00 — Project Vision (Proje Vizyonu)

> Part of the **turkish.code Engineering Bible**. Canonical source of truth.
> **Status:** Canonical · **Version:** 2.0 · **Last updated:** 2026-07-12
> **Audience:** Every future developer and every future AI agent working on turkish.code.
> **Changed in v2.0** (per [52_ADR_LOG](./52_ADR_LOG.md) ADR-0010): the product is **cloud-primary with a local (Ollama) offline *fallback*** — not "offline-first sovereign." Turkish-native + agentic + memory/audit identity is retained; privacy/key handling is light.
> **Related:** [01_ARCHITECTURE](./01_ARCHITECTURE.md) · [02_DESIGN_PRINCIPLES](./02_DESIGN_PRINCIPLES.md) · [21_PROVIDER_SYSTEM](./21_PROVIDER_SYSTEM.md) · [45_ROUTING_ORCHESTRATION](./45_ROUTING_ORCHESTRATION.md) · [52_ADR_LOG](./52_ADR_LOG.md) · [43_NON_GOALS](./43_NON_GOALS.md) · [44_GLOSSARY](./44_GLOSSARY.md)

---

## 1. Purpose

This document defines **what turkish.code is, who it is for, why it exists, and what success looks like**. It is the north star. Every architectural decision documented elsewhere must be traceable back to a principle or goal stated here. If a later design decision contradicts this document, this document wins until it is formally revised.

turkish.code (styled lowercase; internal product id `turkish.code`; Turkish concept name **Türk Kod**) is a **Turkish-native, agentic AI software-engineering companion** — a cross-platform desktop application whose intelligence is a **multi-provider, model-first LLM orchestration core** (Gemini · Groq · OpenRouter · NVIDIA NIM) with a **local Ollama offline fallback** for resilience.

In one sentence: *turkish.code is to Türkiye's developers what a Turkish-speaking senior engineer sitting next to you would be — one that reads your whole codebase, remembers everything, reasons carefully, uses tools, always picks the **best model for the task** across many providers, and keeps working (on a local model) when the network is down.*

---

## 2. Scope

This document covers:

- The problem space and motivation.
- The target users (personas).
- The product pillars (the non-negotiable properties).
- The high-level capability surface (what the product does).
- The philosophy that constrains *how* it does it.
- The definition of done / success metrics for the project as a whole.

This document does **not** cover implementation, tech stack rationale, or subsystem design. Those live in [01_ARCHITECTURE](./01_ARCHITECTURE.md) and the numbered subsystem documents. It also does not enumerate what we are deliberately **not** building — that is [43_NON_GOALS](./43_NON_GOALS.md).

---

## 3. The Problem

Modern AI coding assistants are extraordinarily capable but carry four structural problems that turkish.code exists to solve:

1. **Provider lock-in & fragility.** Mainstream assistants bind you to a single model provider. When that provider is slow, rate-limited, quota-exhausted, or simply not the best for the task at hand, quality and reliability suffer. turkish.code is **model-first and provider-independent**: it routes to the best available model across many providers and fails over gracefully ([45_ROUTING_ORCHESTRATION](./45_ROUTING_ORCHESTRATION.md)). *(Privacy remains a value we respect — keys stay out of source, egress is deliberate — but it is handled lightly, not as heavyweight sovereignty; see [52_ADR_LOG](./52_ADR_LOG.md) ADR-0010.)*

2. **Connectivity as a single point of failure.** Most assistants are useless without the network. turkish.code keeps working through a **local Ollama fallback** when the network or all cloud providers are unavailable — offline capability as *resilience*, not as the product's defining constraint. See [32_OFFLINE_FIRST](./32_OFFLINE_FIRST.md).

3. **Language & cultural alienation.** The entire AI-tooling ecosystem is English-first. Turkish developers reason, comment, name, and communicate in Turkish, but their tools force English framing, mangle Turkish casing (the dotted/dotless `İ/ı` problem), and offer no cultural design identity. A tool built *for* Turkish developers should feel native — in language, in typography, in aesthetic, and in idiom.

4. **Opacity & amnesia.** Assistants forget everything between sessions, hide their reasoning, and give no durable, inspectable record of what they did to your project. Professional engineering needs memory, an audit trail, undo, and explainability.

turkish.code is the answer to all four simultaneously. Dropping any one of them produces a different, lesser product.

---

## 4. Target Users (Personas)

The product is designed against these personas. All are Turkish-speaking; all value privacy.

- **Aylin — Senior backend engineer at a fintech.** Cannot legally send code to foreign clouds. Wants an agent that understands a large existing codebase, runs on her workstation's GPU, and produces an auditable trail she can show compliance.
- **Mert — Freelance full-stack developer.** Works from cafés and while traveling; connectivity is unreliable. Wants a capable assistant that keeps working offline on his laptop with a modest local model, and can *optionally* burst to a cloud provider when he chooses.
- **Deniz — CS student / hobbyist.** Learning to code, more comfortable reading explanations in Turkish. Wants clear, patient, Turkish-language reasoning and a beautiful, encouraging environment.
- **Kerem — Platform engineer in a regulated / air-gapped environment.** No internet at all. Everything must run from local models and local indexes. Auditability and reproducibility are mandatory.
- **An AI agent (yes, really).** Future automated agents will operate turkish.code programmatically. The product and its documentation must be legible and controllable by non-human operators. See [18_AGENT_SYSTEM](./18_AGENT_SYSTEM.md) and [AGENTS.md](./AGENTS.md).

**Explicit non-persona:** the casual consumer who wants a cloud chatbot with no privacy concerns. That user is well served elsewhere; designing for them would dilute every pillar below.

---

## 5. Product Pillars (Non-Negotiable)

These five pillars are inviolable. Any feature, dependency, or design that breaks a pillar must be rejected or redesigned. Each pillar has a dedicated deep-dive document; here we state the commitment.

### P1 — Multi-Provider Intelligence, Best-Model-for-Task (with Offline Fallback)
The core is a **model-first, provider-independent** LLM orchestration system: it routes each task to the **best available model** across **Gemini, Groq, OpenRouter, and NVIDIA NIM**, with **smart failover, retry, cooldown, and tier-aware, quota-preserving routing** — preserving answer quality even as provider quotas exhaust. Cloud providers are the **primary** path; a local **Ollama** model is the **offline/last-resort fallback** so the product keeps working when the network is unavailable. Agents are **provider-agnostic** — they request capabilities, the router picks the model. See [21_PROVIDER_SYSTEM](./21_PROVIDER_SYSTEM.md), [45_ROUTING_ORCHESTRATION](./45_ROUTING_ORCHESTRATION.md), [48_QUOTA_TIER_MANAGEMENT](./48_QUOTA_TIER_MANAGEMENT.md), [32_OFFLINE_FIRST](./32_OFFLINE_FIRST.md), [52_ADR_LOG](./52_ADR_LOG.md).

### P2 — Turkish-Native
Turkish is the first-class language of the interface, the reasoning, the documentation surface, and the aesthetic. This includes locale-correct casing (dotless-i), full glyph support, a bespoke Turkish design language, and Turkish-idiomatic naming throughout. English is supported as a secondary locale but never at the cost of Turkish quality. See [04_TURKISH_DESIGN_LANGUAGE](./04_TURKISH_DESIGN_LANGUAGE.md), [03_UI_SYSTEM](./03_UI_SYSTEM.md).

### P3 — Agentic & Tool-Using
turkish.code is not a chatbot; it is an **agent** that plans, uses tools, edits files, runs commands, retrieves knowledge, reflects, and iterates toward a goal — under a strict permission model. See [15_REASONING_ENGINE](./15_REASONING_ENGINE.md), [18_AGENT_SYSTEM](./18_AGENT_SYSTEM.md), [20_TOOL_SYSTEM](./20_TOOL_SYSTEM.md), [24_PERMISSION_SYSTEM](./24_PERMISSION_SYSTEM.md).

### P4 — Memory & Auditability
Everything the agent perceives and does is recorded in an append-only timeline, with content-addressed snapshots enabling perfect undo, and a durable, layered memory that persists across sessions. The user can always answer "what did it do, and why, and can I undo it?" See [11_MEMORY_SYSTEM](./11_MEMORY_SYSTEM.md), [26_TIMELINE](./26_TIMELINE.md), [27_SNAPSHOTS](./27_SNAPSHOTS.md).

### P5 — Trustworthy by Construction
The user is always in control. Destructive actions are gated. Reasoning is inspectable. Failures are recoverable. The design assumes the model can be wrong and builds guardrails, not blind trust. See [24_PERMISSION_SYSTEM](./24_PERMISSION_SYSTEM.md), [28_CRASH_RECOVERY](./28_CRASH_RECOVERY.md), [38_ERROR_HANDLING](./38_ERROR_HANDLING.md).

---

## 6. Capability Surface (What It Does)

At maturity, turkish.code can:

- **Understand a codebase.** Index a workspace into a knowledge graph + vector store; answer questions about it in Turkish. ([12_KNOWLEDGE_GRAPH](./12_KNOWLEDGE_GRAPH.md), [13_RAG_SYSTEM](./13_RAG_SYSTEM.md))
- **Converse & reason.** Multi-turn Turkish conversation with visible, structured reasoning traces. ([15_REASONING_ENGINE](./15_REASONING_ENGINE.md))
- **Edit code agentically.** Make multi-file changes via tools, with snapshots and one-click rollback. ([20_TOOL_SYSTEM](./20_TOOL_SYSTEM.md), [27_SNAPSHOTS](./27_SNAPSHOTS.md))
- **Run commands & tests** under permission gating in a controlled workspace. ([20_TOOL_SYSTEM](./20_TOOL_SYSTEM.md), [24_PERMISSION_SYSTEM](./24_PERMISSION_SYSTEM.md))
- **Deliberate as a council.** Convene multiple model personas (Divan) to debate hard problems and synthesize a superior answer. ([16_COUNCIL_MODE](./16_COUNCIL_MODE.md))
- **Scale effort deliberately.** The user (or the agent) picks an effort mode trading latency for depth. ([17_EFFORT_MODES](./17_EFFORT_MODES.md))
- **Remember.** Durable memory of the user, the project, and prior feedback, retrieved automatically when relevant. ([11_MEMORY_SYSTEM](./11_MEMORY_SYSTEM.md))
- **Extend itself.** Load skills and plugins that add tools, providers, agents, and UI. ([19_SKILLS_SYSTEM](./19_SKILLS_SYSTEM.md), [23_PLUGIN_SYSTEM](./23_PLUGIN_SYSTEM.md))
- **Route to the best model across providers** (Gemini/Groq/OpenRouter/NVIDIA NIM) via a provider-independent, model-first abstraction, with a local **Ollama** offline fallback. ([21_PROVIDER_SYSTEM](./21_PROVIDER_SYSTEM.md), [22_PROVIDER_INTEGRATIONS](./22_PROVIDER_INTEGRATIONS.md), [45_ROUTING_ORCHESTRATION](./45_ROUTING_ORCHESTRATION.md))
- **Survive crashes** and resume in-flight work exactly where it left off. ([28_CRASH_RECOVERY](./28_CRASH_RECOVERY.md))

---

## 7. Philosophy (How It Behaves)

These are behavioral commitments that shape UX and engineering equally.

- **Local by default, cloud by consent.** The default state is fully local. Reaching the network is a deliberate, visible, opt-in act.
- **Show the work.** Reasoning, retrieval, and tool calls are inspectable, not hidden magic. Trust is earned through transparency.
- **Reversible over fast.** When in doubt, prefer an action that can be undone. Snapshots before edits, always.
- **Ask, don't assume, for irreversible or outward-facing actions.** The permission system is a feature, not friction.
- **Beautiful is functional.** The Turkish design language is not decoration; a calm, legible, culturally resonant environment reduces cognitive load and builds trust.
- **Degrade gracefully.** Missing GPU, small model, no internet, corrupt index — the product should shrink its ambitions, not fall over.
- **Legible to machines.** Documentation, config, and IPC are structured so that other AI agents can operate and extend the system.

---

## 8. Success Definition

The project is successful when **all** of the following hold:

1. A developer with **no internet connection** can open a real-world Turkish codebase, ask questions in Turkish, and have the agent make a correct, reviewed, reversible multi-file change — entirely on local models.
2. **No source code, secret, or telemetry** ever leaves the machine except through an action the user explicitly and knowingly authorized.
3. The interface is indistinguishable in polish from a top-tier commercial IDE, and unmistakably **Turkish** in language and identity.
4. Any action the agent took can be **explained** (reasoning trace) and **undone** (snapshot rollback) after the fact.
5. A **new AI agent**, given only the `docs/` tree, can implement or extend any subsystem without needing additional design decisions. (This is the meta-goal of the documentation effort described in [40_DOCUMENTATION_RULES](./40_DOCUMENTATION_RULES.md).)

---

## 9. Guiding Constraints (Summary)

| Constraint | Commitment | Governing Doc |
|---|---|---|
| Privacy | No data egress without explicit consent | [30_SECURITY](./30_SECURITY.md) |
| Offline | Full function with zero network | [32_OFFLINE_FIRST](./32_OFFLINE_FIRST.md) |
| Language | Turkish-first, locale-correct | [04_TURKISH_DESIGN_LANGUAGE](./04_TURKISH_DESIGN_LANGUAGE.md) |
| Safety | Permission-gated, reversible | [24_PERMISSION_SYSTEM](./24_PERMISSION_SYSTEM.md) |
| Portability | Windows, macOS, Linux | [07_DESKTOP_ARCHITECTURE](./07_DESKTOP_ARCHITECTURE.md) |
| Hardware | Runs on a laptop; scales to a GPU workstation | [31_PERFORMANCE](./31_PERFORMANCE.md), [22_PROVIDER_INTEGRATIONS](./22_PROVIDER_INTEGRATIONS.md) |

---

## 10. Anti-Patterns (Vision-Level)

These represent *failures of vision* — mistakes that betray what the product is:

- **Cloud-only fallback for a core feature.** If any core capability silently requires the network, P1 is broken.
- **English leaking into the primary UX.** Turkish is not a translation layer bolted on; it is the substrate.
- **Hidden reasoning / unexplained edits.** Opaque behavior betrays P4/P5.
- **Irreversible agent actions with no snapshot.** Betrays P4.
- **Design as afterthought.** Shipping a generic Electron-looking shell betrays P2.
- **Feature bloat that dilutes the pillars.** Every feature must strengthen a pillar or it does not belong.

---

## 11. Things That Must Never Happen

1. Source code, embeddings, secrets, or telemetry are transmitted off-device without an explicit, logged, revocable user authorization.
2. A core capability becomes unavailable purely because the machine is offline.
3. The primary UI ships without full, correct Turkish locale support (casing, glyphs, pluralization).
4. An agent performs a destructive or irreversible action without either a snapshot or an explicit permission grant.
5. The project ships a subsystem whose behavior contradicts these pillars without this document first being revised and the contradiction reconciled.

---

## 12. Relationship With Other Documents

This document is the **root of the dependency tree of intent**. [01_ARCHITECTURE](./01_ARCHITECTURE.md) translates these pillars into a technical structure. [02_DESIGN_PRINCIPLES](./02_DESIGN_PRINCIPLES.md) translates them into engineering rules. [43_NON_GOALS](./43_NON_GOALS.md) states the deliberate exclusions that keep the vision focused. [42_ROADMAP](./42_ROADMAP.md) sequences delivery of the capability surface. Every other document implements some slice of the capability surface under these constraints.
