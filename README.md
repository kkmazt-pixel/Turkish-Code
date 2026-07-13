# turkish.code

Turkish-native, agentic AI software-engineering desktop application. The
product's intelligence is a **multi-provider, model-first LLM orchestration
core** — Gemini, Groq, OpenRouter, and NVIDIA NIM as primary providers, with a
local Ollama model as the offline fallback.

> **Status:** early engineering-foundation stage. The Python core (Çekirdek)
> foundation is implemented and tested; the desktop shell (Kabuk/Tauri) and
> frontend (Arayüz/React) have not been started yet. See
> [Repository Structure](#repository-structure) for what exists today.

## What It Is

turkish.code is an agent that reasons, uses tools, edits code, and retrieves
knowledge inside a permissioned, reversible, auditable workspace — not a
chat wrapper. It routes each task to the best available model rather than
committing to a single provider, and it keeps working offline via a local
model when the network or a provider is unavailable.

## Purpose

- **Turkish-native**, not translated: Turkish is the first-class language of
  the interface, the reasoning, and the documentation.
- **Agentic**: plans, calls tools, edits files, runs commands, and reflects
  toward a goal, under an explicit permission model.
- **Model-first, not provider-first**: the router picks the best model for a
  task by capability and tier; agents are provider-agnostic.
- **Resilient**: smart failover, retry, cooldown, and quota-preserving
  routing keep answer quality up as provider quotas exhaust.
- **Trustworthy by construction**: every side effect is permission-gated,
  snapshotted, and auditable; nothing is unbounded or silent.

## Core Features (Target Architecture)

| Area | What it provides |
|---|---|
| Reasoning & Agents | Plan → act → observe → reflect loop with tool use, sub-agents, and a full trace |
| Multi-Provider Routing | Capability + tier + quota-aware routing across Gemini/Groq/OpenRouter/NVIDIA NIM + Ollama fallback |
| Memory & Knowledge | Layered durable memory, a knowledge graph, and hybrid RAG retrieval over the workspace |
| Safety Substrate | Permission engine, content-addressed snapshots, append-only timeline, crash recovery |
| Turkish Design | A dedicated Turkish design language across the UI, not a localized template |
| Extensibility | Provider-agnostic agents, a skills system, and a sandboxed plugin system |

Each of these is specified in full in [`docs/`](./docs/) before being built —
see [Documentation Map](#documentation-map).

## Architecture Summary

Three isolated tiers, each the right tool for its job:

```
Arayüz  (React 19 + TypeScript, Tauri WebView)   — presentation only, no business logic
   │  Bridge (Tauri commands/events)
Kabuk   (Rust + Tauri 2.x)                        — trusted broker: permissions, snapshots, secrets
   │  Core Channel (JSON-RPC 2.0 over length-prefixed stdio)
Çekirdek (Python 3.12+ sidecar)                   — the AI brain: reasoning, providers, memory, RAG
```

The Arayüz never touches the filesystem, shell, or network directly; every
side effect is brokered by the Kabuk and is permission-gated, snapshotted,
and recorded to an append-only timeline. Full detail:
[`docs/01_ARCHITECTURE.md`](./docs/01_ARCHITECTURE.md).

## Repository Structure

```
core/                  # Çekirdek — Python AI-brain sidecar (implemented: foundation)
  turkish_code/
    hata/              # typed error taxonomy (doc 38)
    ortak/             # shared kernel: Clock, LogLevel (doc 09 §10)
    yapilandirma/      # layered configuration + paths (doc 33)
    gunluk/            # structured logger + redaction (doc 39)
    kanal/             # Core Channel message contract (doc 10)
    kompozisyon.py     # composition root / DI wiring (doc 09 §7)
  tests/               # pytest suite
  pyproject.toml       # ruff + black + mypy(strict) + pytest config

apps/desktop/          # Arayüz + Kabuk — not yet implemented
packages/              # design-system, ipc-schema — not yet implemented

docs/                  # the Engineering Bible — canonical spec for every subsystem
CLAUDE.md              # entry point + non-negotiables for AI agents working in this repo
PROJECT_ANALYSIS.md    # recovered ground-truth for the provider/LLM layer
```

See [`docs/37_REPOSITORY_STRUCTURE.md`](./docs/37_REPOSITORY_STRUCTURE.md) for
the full canonical layout and placement rules.

## Getting Started

Only the Çekirdek (Python core) is implemented today.

```bash
cd core
pip install -e ".[dev]"

pytest          # run the test suite
ruff check .    # lint
black --check . # format check
mypy            # strict type-check
```

See [`core/README.md`](./core/README.md) for details on what's implemented in
the core so far.

## Documentation Map

The `docs/` directory is the **Engineering Bible** — the canonical
specification every subsystem is built from. Start at
**[`docs/ARCHITECTURE_INDEX.md`](./docs/ARCHITECTURE_INDEX.md)**: it catalogs
every document, the dependency graph between subsystems, the implementation
order, and an AI/developer onboarding guide.

Authority order when documents disagree:
[`PROJECT_ANALYSIS.md`](./PROJECT_ANALYSIS.md) (recovered ground-truth for the
provider/LLM layer, read chronologically) → [`CLAUDE.md`](./CLAUDE.md) (agent
entry point and non-negotiables) → `docs/*` (the detailed spec). See
[`docs/52_ADR_LOG.md`](./docs/52_ADR_LOG.md) for the decision history behind
this ordering.

## License

Apache License 2.0 — see [`LICENSE`](./LICENSE).
