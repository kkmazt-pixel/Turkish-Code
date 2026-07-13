# 37 — Repository Structure (Depo Yapısı)

> Part of the **turkish.code Engineering Bible**. Canonical source of truth.
> **Status:** Canonical · **Version:** 1.0 · **Last updated:** 2026-07-12
> **Related:** [01_ARCHITECTURE](./01_ARCHITECTURE.md) · [08_TAURI_ARCHITECTURE](./08_TAURI_ARCHITECTURE.md) · [09_PYTHON_BACKEND](./09_PYTHON_BACKEND.md) · [33_CONFIGURATION](./33_CONFIGURATION.md) · [35_TESTING](./35_TESTING.md) · [36_CODING_STANDARDS](./36_CODING_STANDARDS.md)

---

## 1. Purpose

Defines the **canonical monorepo layout**, the tooling per tier, the build/dev orchestration, and the rules for where any given file belongs. A new contributor or AI agent must be able to place a new file correctly using only this document.

## 2. Scope

The directory tree, per-package tooling, workspace management, naming, and build/dev scripts. Not the internal module layout of a subsystem (that lives in each subsystem doc's "Directory Structure" section) and not coding style ([36](./36_CODING_STANDARDS.md)).

## 3. Why a Monorepo

- The three tiers share versioned contracts ([01](./01_ARCHITECTURE.md) §12) that must evolve atomically; a monorepo makes a cross-tier contract change a single reviewable commit.
- Unified CI, versioning, and release. One `docs/` tree is the source of truth for all.
- Rejected alternative: polyrepo — rejected because contract drift across repos is exactly the failure mode we most want to prevent (PR-8 in [02](./02_DESIGN_PRINCIPLES.md)).

## 4. Top-Level Tree

```
turkish.code/
├── apps/
│   └── desktop/                  # The desktop application (Arayüz + Kabuk)
│       ├── src/                  # ARAYÜZ — React 19 + TypeScript frontend
│       │   ├── main.tsx
│       │   ├── app/              # app shell, routing, providers
│       │   ├── features/         # feature modules (chat, workspace, timeline…)
│       │   ├── bridge/           # typed wrappers over Tauri commands/events
│       │   ├── stores/           # Zustand stores (view state only)
│       │   ├── i18n/             # locale bundles (tr default, en)
│       │   └── styles/           # TTD token consumption, globals
│       ├── src-tauri/            # KABUK — Rust / Tauri 2.x shell
│       │   ├── src/
│       │   │   ├── main.rs
│       │   │   ├── commands/     # allowlisted Tauri commands (Bridge API)
│       │   │   ├── supervisor/   # Çekirdek process lifecycle
│       │   │   ├── channel/      # Core Channel (JSON-RPC over stdio)
│       │   │   ├── permission/   # permission engine (enforcement locus)
│       │   │   ├── secrets/      # OS keychain vault
│       │   │   ├── broker/       # brokered side effects (fs, shell, net)
│       │   │   └── events/       # event re-emission to Arayüz
│       │   ├── capabilities/     # Tauri capability/permission manifests
│       │   ├── tauri.conf.json
│       │   └── Cargo.toml
│       ├── index.html
│       ├── vite.config.ts
│       ├── package.json
│       └── tsconfig.json
│
├── core/                         # ÇEKİRDEK — Python 3.12+ AI brain (sidecar)
│   ├── turkish_code/             # the installable package
│   │   ├── __init__.py
│   │   ├── __main__.py           # sidecar entrypoint (stdio JSON-RPC loop)
│   │   ├── kanal/                # Core Channel server (framing, dispatch)
│   │   ├── muhakeme/             # Reasoning Engine        (doc 15)
│   │   ├── divan/                # Council Mode            (doc 16)
│   │   ├── caba/                 # Effort Modes            (doc 17)
│   │   ├── ajan/                 # Agent System            (doc 18)
│   │   ├── yetenek/              # Skills runtime          (doc 19)
│   │   ├── araclar/              # Tools                   (doc 20)
│   │   ├── saglayicilar/         # Providers               (doc 21) incl. nvidia/
│   │   ├── bellek/               # Memory                  (doc 11)
│   │   ├── graf/                 # Knowledge Graph         (doc 12)
│   │   ├── getirim/              # RAG                     (doc 13)
│   │   ├── gomme/                # Embeddings              (doc 14)
│   │   ├── depo/                 # Storage adapters        (doc 29)
│   │   ├── zaman/                # Timeline                (doc 26)
│   │   ├── anlik/                # Snapshots               (doc 27)
│   │   ├── kurtarma/             # Crash Recovery          (doc 28)
│   │   ├── calisma_alani/        # Workspace               (doc 25)
│   │   ├── izin/                 # permission client (talks to Kabuk) (doc 24)
│   │   ├── yapilandirma/         # config loader           (doc 33)
│   │   ├── gunluk/               # logging                 (doc 39)
│   │   ├── hata/                 # typed errors            (doc 38)
│   │   └── ortak/                # shared utils, locale (Turkish casing)
│   ├── pyproject.toml
│   └── README.md
│
├── packages/
│   ├── design-system/            # TTD tokens + React components (doc 04, 06)
│   │   ├── tokens/               # source-of-truth design tokens (JSON/TS)
│   │   ├── components/
│   │   ├── motion/               # animation presets (doc 05)
│   │   └── package.json
│   └── ipc-schema/               # SHARED CONTRACTS — source of truth (doc 10)
│       ├── schema/               # method/event/type definitions (e.g. JSON Schema)
│       ├── generated/            # codegen outputs (TS + Rust + Python)
│       └── package.json
│
├── skills/                       # first-party Yetenekler (doc 19, SKILLS.md)
│   └── <skill-name>/
│       ├── SKILL.md
│       └── ...
│
├── plugins/                      # sample/first-party Eklentiler (doc 23)
│   └── <plugin-name>/
│       ├── plugin.toml
│       └── ...
│
├── docs/                         # THIS ENGINEERING BIBLE (00–44, AGENTS, SKILLS,
│                                 #  ARCHITECTURE_INDEX)
│
├── scripts/                      # dev/build/package/release orchestration
│   ├── dev.sh                    # run Kabuk+Arayüz+Çekirdek in dev
│   ├── build.sh
│   ├── package.sh                # bundle Çekirdek + Tauri installers
│   ├── codegen.sh                # generate contracts from ipc-schema
│   └── bootstrap-models.sh       # fetch/verify default local models
│
├── tests/                        # cross-tier integration & e2e (doc 35)
│   ├── integration/
│   └── e2e/
│
├── .github/ or .ci/              # CI pipelines
├── Cargo.toml                    # Rust workspace root
├── package.json                  # JS workspace root (pnpm)
├── pnpm-workspace.yaml
├── turbo.json (or nx.json)       # JS task orchestration
├── uv.lock / poetry.lock         # Python lock
├── .editorconfig
├── CLAUDE.md                     # AI-agent entry pointer → docs/AGENTS.md
├── LICENSE
└── README.md
```

## 5. Placement Rules (Where Does X Go?)

A decision table so any file lands correctly:

| You are adding… | It goes in… |
|---|---|
| A React component or view | `apps/desktop/src/features/*` or `packages/design-system/components` if reusable |
| A design token, color, motion preset | `packages/design-system/tokens` / `motion` |
| A new Tauri command (Bridge API) | `apps/desktop/src-tauri/src/commands` **and** declare it in `packages/ipc-schema` |
| A brokered side effect (fs/shell/net) | `apps/desktop/src-tauri/src/broker` (never elsewhere; PR-2) |
| A new Core Channel method | define in `packages/ipc-schema/schema`, implement in `core/turkish_code/kanal` + owning subsystem |
| A new tool | `core/turkish_code/araclar/<tool>` |
| A new provider | `core/turkish_code/saglayicilar/<provider>` |
| A new skill | `skills/<name>/` |
| A distributable plugin | `plugins/<name>/` |
| A shared Turkish-locale helper | `core/turkish_code/ortak` (Python) / `apps/desktop/src/i18n` (TS) |
| A doc | `docs/` (and register in `ARCHITECTURE_INDEX.md`) |
| A cross-tier test | `tests/integration` or `tests/e2e` |
| A subsystem-internal unit test | co-located with the subsystem |

**Rule:** if the table is ambiguous, the module owns its own directory and the answer is documented in that subsystem's doc; then update this table.

## 6. Tooling Per Tier

| Tier | Language | Package/Build | Test | Lint/Format |
|---|---|---|---|---|
| Arayüz | TypeScript 5.x, React 19 | Vite 6, pnpm | Vitest + Playwright | ESLint, Prettier, `tsc --noEmit` |
| Kabuk | Rust (stable) | Cargo, Tauri 2.x | `cargo test` | `clippy`, `rustfmt` |
| Çekirdek | Python 3.12+ | `uv` (or Poetry), pyproject | `pytest`, `pytest-asyncio` | `ruff`, `mypy`, `black` |
| Design system | TypeScript | Vite/tsup, pnpm | Vitest + Storybook | ESLint, Prettier |
| Contracts | JSON Schema → codegen | `scripts/codegen.sh` | schema round-trip tests | schema lint |

Versions are pinned in the respective lockfiles; the authoritative version matrix lives in [33_CONFIGURATION](./33_CONFIGURATION.md) §toolchain.

## 7. Workspace Management

- **JS:** pnpm workspaces (`pnpm-workspace.yaml`) covering `apps/*`, `packages/*`. Task graph via Turborepo (or Nx).
- **Rust:** a Cargo workspace with `src-tauri` (and any future crates) as members.
- **Python:** a single `core` project managed by `uv`; sidecar packaged for distribution (see [09_PYTHON_BACKEND](./09_PYTHON_BACKEND.md) §packaging).
- **Contracts:** `packages/ipc-schema` is the source of truth; `scripts/codegen.sh` regenerates TS/Rust/Python bindings. **Generated files are committed** and CI verifies they are up to date (a drift check).

## 8. Dev & Build Orchestration

- `scripts/dev.sh` starts: contract codegen (watch) → Çekirdek in dev mode → Tauri dev (which starts Vite for the Arayüz and the Kabuk with the sidecar wired). Hot reload on all three where possible.
- `scripts/build.sh` produces release artifacts per tier.
- `scripts/package.sh` bundles the Çekirdek (frozen Python runtime + deps, see [09](./09_PYTHON_BACKEND.md)) into the Tauri resource dir and produces platform installers (.msi/.dmg/.AppImage/.deb).
- `scripts/bootstrap-models.sh` fetches and checksum-verifies the default offline models into the model cache (see [22_PROVIDER_INTEGRATIONS](./22_PROVIDER_INTEGRATIONS.md), [32_OFFLINE_FIRST](./32_OFFLINE_FIRST.md)).

## 9. Naming Conventions (Directory/File Level)

- Directory names for Çekirdek subsystems use the **Turkish canonical name, ASCII-transliterated** (no diacritics): `muhakeme`, `getirim`, `bellek`, `saglayicilar`. (Rationale and the transliteration rule: [44_GLOSSARY](./44_GLOSSARY.md) §2.)
- TS files: `PascalCase` for components, `camelCase` for modules. Rust: `snake_case` modules. Python: `snake_case` modules/packages.
- No spaces in any path (note: the *repo root* on this machine currently has a space — "Turkish Code" — but the project's own paths must never introduce spaces; tooling must quote the root).
- Full rules in [36_CODING_STANDARDS](./36_CODING_STANDARDS.md).

## 10. Configuration Files (Where They Live)

- Build/tool config at repo root and per package (§4).
- Runtime app config is **not** in the repo; it lives in the OS app-data dir at runtime. See [33_CONFIGURATION](./33_CONFIGURATION.md) for the resolution order and paths.
- Default/seed config templates ship under `apps/desktop/src-tauri/resources/defaults`.

## 11. Edge Cases

- **The repo root path contains a space** ("Turkish Code"). All scripts must quote paths; CI runs a check that fails on unquoted `$PWD` usage. Generated artifacts and installers must handle spaced install paths on all OSes.
- **Generated bindings drift**: CI's codegen-drift check fails the build if `generated/` is stale. Never hand-edit generated files.
- **Large model files** must never be committed; they live in the model cache and are fetched by `bootstrap-models.sh`. `.gitignore` (or repo hygiene) enforces this.

## 12. Failure Recovery

- A broken lockfile or partial `node_modules`/venv is recovered by `scripts/dev.sh --clean` (documented reset path). No hidden global state; deleting build caches and re-bootstrapping always yields a working tree.

## 13. Security

- Secrets and API keys are **never** committed (they live in the OS keychain at runtime; [34_API_KEYS](./34_API_KEYS.md)). CI runs a secret scanner.
- Plugin/skill directories are treated as untrusted content when third-party; see [23_PLUGIN_SYSTEM](./23_PLUGIN_SYSTEM.md).

## 14. Performance

- The task graph (Turbo/Nx + Cargo + uv) caches builds; contract codegen is incremental. First-paint of the dev app must not wait on Çekirdek build (parallelized).

## 15. Testing Strategy

- Each package tests locally; `tests/` holds cross-tier suites. See [35_TESTING](./35_TESTING.md) for the pyramid and the CI matrix.

## 16. Future Extensions

- Additional apps (e.g., `apps/cli` headless mode) slot under `apps/`.
- Additional Rust crates (e.g., a shared `kabuk-core`) slot into the Cargo workspace.

## 17. Anti-Patterns

- Putting business logic under `apps/desktop/src` (Arayüz must stay a pure view).
- A side-effect primitive outside `src-tauri/src/broker`.
- Hand-editing `packages/ipc-schema/generated`.
- Committing model weights, secrets, or runtime config.
- Introducing spaces into project paths.

## 18. Things That Must Never Happen

1. Generated contract bindings are edited by hand or allowed to drift silently.
2. A secret or model weight is committed to the repo.
3. A new side-effect path is created outside the broker module.
4. Two packages define the same contract independently (contracts live only in `ipc-schema`).

## 19. Relationship With Other Subsystems

This document is the physical embodiment of the architecture in [01](./01_ARCHITECTURE.md). Each subsystem doc's "Directory Structure" section refines the module layout *inside* its top-level folder shown here. Build/tooling versions are governed by [33_CONFIGURATION](./33_CONFIGURATION.md); CI by [35_TESTING](./35_TESTING.md).

## 20. Migration Considerations

- Moving a subsystem folder is a mechanical but tracked migration: update this tree, the subsystem doc, the [ARCHITECTURE_INDEX](./ARCHITECTURE_INDEX.md), and any import paths in one commit.
- Renaming a canonical Turkish folder requires a glossary update first ([44](./44_GLOSSARY.md)).
