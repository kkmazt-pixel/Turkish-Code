# 36 — Coding Standards (Kodlama Standartları)

> Part of the **turkish.code Engineering Bible**. Canonical source of truth.
> **Status:** Canonical · **Version:** 1.0 · **Last updated:** 2026-07-12
> **Owner:** cross-cutting
> **Related:** [02_DESIGN_PRINCIPLES](./02_DESIGN_PRINCIPLES.md) · [37_REPOSITORY_STRUCTURE](./37_REPOSITORY_STRUCTURE.md) · [38_ERROR_HANDLING](./38_ERROR_HANDLING.md) · [41_IMPLEMENTATION_RULES](./41_IMPLEMENTATION_RULES.md) · [44_GLOSSARY](./44_GLOSSARY.md)

---

## 1. Purpose

The **language-level and code-level standards** for turkish.code across its three tiers: naming, formatting, typing, structure, comments, and the concrete rules that operationalize the design principles ([02](./02_DESIGN_PRINCIPLES.md)) in day-to-day code. Where [02](./02_DESIGN_PRINCIPLES.md) is the "constitution," this is the "statute": specific, checkable rules that lint/format/typecheck can enforce. Consistency here is what lets any developer or AI agent read and extend the codebase fluently.

## 2. Scope

Universal rules + per-language (TypeScript/Rust/Python) conventions, naming (including the Turkish-transliteration rule), typing discipline, comments/docstrings, imports/structure, and enforcement tooling. Out of scope: architecture ([01](./01_ARCHITECTURE.md)), where files go ([37](./37_REPOSITORY_STRUCTURE.md)), error/logging semantics ([38](./38_ERROR_HANDLING.md)/[39](./39_LOGGING.md)).

## 3. Universal Rules (All Tiers)

- **Match the surrounding code.** Comment density, naming, and idiom follow the file you're in; consistency beats personal preference.
- **Types are mandatory** at boundaries and public APIs; no untyped/`any`/`Any` in public surfaces (§6).
- **Explicit over implicit** (PR-9): inject dependencies; pass budgets/permission-contexts/providers explicitly; no import-time side effects or hidden globals.
- **Typed errors, never silent failure** (PR-10, [38](./38_ERROR_HANDLING.md)): no bare `catch`/`except: pass`, no `null`/`None` to signal an error.
- **Small, single-responsibility units** (PR-13): a function/module does one nameable thing.
- **Bounded everything** (PR-14): every loop/recursion/fan-out/external call has a limit.
- **No hardcoded user-facing strings** (PR-12): all through i18n ([03](./03_UI_SYSTEM.md)) / locale layer.
- **One path per side effect** (PR-2): the OS primitives for fs/shell/net appear only in the sanctioned module ([08](./08_TAURI_ARCHITECTURE.md) `broker/`) — a `grep` gate enforces this.
- **No secrets in code/logs** ([34](./34_API_KEYS.md)/[30](./30_SECURITY.md)).
- **Comments explain *why*, not *what*.** The code says what; comments justify non-obvious decisions and reference the governing doc (e.g., `// snapshot before write — doc 27`).

## 4. Naming & The Turkish Transliteration Rule

- **Canonical terms** come from [44_GLOSSARY](./44_GLOSSARY.md); use them verbatim (no synonyms — the forbidden-alias table applies).
- **Turkish subsystem names in identifiers are ASCII-transliterated** (no diacritics): directory/module `muhakeme`, `getirim`, `saglayicilar` — never `çekirdek`/`sağlayıcılar` in a path or identifier (cross-platform filename/identifier safety). This rule is defined once in [44](./44_GLOSSARY.md) §2 and enforced here.
- **User-facing text** uses correct Turkish orthography (İ ı ş ğ ç ö ü) via i18n — the transliteration rule is for *code identifiers only*.
- **No spaces in project paths** ([37](./37_REPOSITORY_STRUCTURE.md) §11); the repo *root* may (dev machine "Turkish Code") so scripts must quote paths.
- Casing conventions per language (§5).

## 5. Per-Language Conventions

### 5.1 TypeScript (Arayüz, design system)
- **Tooling:** ESLint + Prettier + `tsc --noEmit`; `strict: true`.
- **Naming:** `PascalCase` components/types, `camelCase` vars/functions, `UPPER_SNAKE` consts, files `PascalCase.tsx` for components else `camelCase.ts`.
- **Rules:** no `any` (use `unknown` + narrowing); prefer `type`/discriminated unions for data; no default exports for components (named exports); no direct `@tauri-apps/api`/`fetch` outside `bridge/` (lint rule, [03](./03_UI_SYSTEM.md)); token-only styling (no hardcoded color/space, [04](./04_TURKISH_DESIGN_LANGUAGE.md)); no `String.toUpperCase()` on Turkish text — use the locale helper ([03](./03_UI_SYSTEM.md) §11).
- **React:** function components + hooks; memoize deliberately; no business logic (pure view, [01](./01_ARCHITECTURE.md)).

### 5.2 Rust (Kabuk)
- **Tooling:** `rustfmt` + `clippy` (deny warnings in CI); stable toolchain.
- **Naming:** `snake_case` fns/modules, `CamelCase` types, `SCREAMING_SNAKE` consts.
- **Rules:** no `unwrap()`/`expect()` on fallible paths in production code (return typed errors, [38](./38_ERROR_HANDLING.md)); `unsafe` is forbidden unless justified with a comment + review; OS side-effect primitives only in `broker/` (PR-2); async via Tokio; no blocking calls on the async runtime (use the blocking pool); commands are thin ([08](./08_TAURI_ARCHITECTURE.md)).

### 5.3 Python (Çekirdek)
- **Tooling:** `ruff` (lint) + `black` (format) + `mypy` (strict-ish); Python 3.12+.
- **Naming:** `snake_case` modules/functions/vars, `PascalCase` classes, `UPPER_SNAKE` consts; package dirs use the transliteration rule (§4).
- **Rules:** **full type hints** on public functions; `async def` for I/O; **never block the event loop** (offload CPU/GPU, [09](./09_PYTHON_BACKEND.md) §6); no module-level side effects/singletons — construct via the DI container ([09](./09_PYTHON_BACKEND.md) §7); **nothing to stdout** except protocol ([09](./09_PYTHON_BACKEND.md) §16 — `print(` is lint-banned); pydantic models mirror `ipc-schema`/storage schemas; typed errors from `hata/` ([38](./38_ERROR_HANDLING.md)); Turkish locale ops via `ortak/` ([09](./09_PYTHON_BACKEND.md) §10).

## 6. Typing Discipline

- Public APIs, IPC params/results, and storage records are fully typed and validated against the schema ([10](./10_IPC.md)/[29](./29_STORAGE.md)). No `any`/`Any`/untyped dict at boundaries.
- Prefer making illegal states unrepresentable (discriminated unions, newtypes, exhaustive matches). Model the permission-context/effort-budget as explicit typed parameters (PR-9/PR-14).

## 7. Comments & Docstrings

- **Docstrings** on public functions/modules describe purpose, params, returns, errors, and cite the governing doc where relevant.
- **Inline comments** justify non-obvious decisions and reference invariants (`// PR-2: single side-effect path`, `// doc 27: snapshot before mutate`). This traceability from code → Bible is a project norm (aids AI + human maintainers).
- Keep comments truthful and current; a wrong comment is worse than none.

## 8. Structure & Imports

- Files stay focused and reasonably small; extract when a file grows multi-responsibility (PR-13).
- Import order: stdlib → third-party → internal, grouped; no deep reach-ins across subsystem boundaries (use the interface/contract). Downward-only dependencies ([03](./03_UI_SYSTEM.md)/[06](./06_COMPONENT_LIBRARY.md)/[09](./09_PYTHON_BACKEND.md)).
- No cyclic imports (lint-enforced where possible).

## 9. Enforcement (Tooling as the Standard)

- Standards are **machine-enforced** wherever possible: formatters (Prettier/rustfmt/black), linters (ESLint/clippy/ruff) with project rule-sets, type-checkers (tsc/mypy), plus custom lint rules for project-specific invariants (no `@tauri-apps/api` outside `bridge/`; no `print(` in Çekirdek; side-effect primitives only in `broker/`; token-only styling). CI blocks on all of them ([35](./35_TESTING.md) §7).
- Pre-commit hooks run format + fast lint locally.

## 10. Configuration

- Rule-sets/formatters config live per package ([37](./37_REPOSITORY_STRUCTURE.md)); the authoritative toolchain versions are in [33_CONFIGURATION](./33_CONFIGURATION.md) §5. `.editorconfig` at root for baseline whitespace.

## 11. Dependencies

- New dependencies are added deliberately: pinned, license-checked, security-audited ([30](./30_SECURITY.md)), and offline-compatible (no runtime CDN, PR-6). Prefer the standard library / existing deps over adding surface. Removing a dep is preferred to adding one when feasible.

## 12. Edge Cases

- **Generated code** (`ipc-schema/generated`) is never hand-edited or linted as source ([37](./37_REPOSITORY_STRUCTURE.md) §7).
- **Turkish identifiers in user code** (the *user's* project) are handled correctly by tools ([12](./12_KNOWLEDGE_GRAPH.md)) — our own identifiers use transliteration (§4).
- **Long agglutinative names:** allowed; readability over arbitrary length caps.
- **Perf-critical hot paths:** may deviate from a style rule *with a comment justifying it and a benchmark* ([31](./31_PERFORMANCE.md), PR-17) — never silently.

## 13. Failure Recovery

- A formatting/lint failure blocks merge but is trivially fixable (auto-format). There is always a documented `--clean` reset for a broken local toolchain ([37](./37_REPOSITORY_STRUCTURE.md) §12).

## 14. Security

- Coding rules encode security: no secrets in code/logs, side-effects only in the broker, no `unsafe`/`eval`, typed/validated inputs, no untrusted content executed. These are lint/review gates, not suggestions ([30](./30_SECURITY.md)).

## 15. Performance

- Standard rules (no loop-blocking, bounded loops, compositor-only animation) are also perf rules ([31](./31_PERFORMANCE.md)). Deviations require justification + measurement (§12).

## 16. Testing Strategy

- Style/type/lint are the first CI stage ([35](./35_TESTING.md)); custom-rule tests verify the project-specific lints actually fire (e.g., a `print(` in Çekirdek fails). New code follows the testability rules (DI, interfaces) so it *can* be unit-tested with fakes.

## 17. Future Extensions

- More custom lint rules encoding invariants as they solidify; auto-fixers for common project patterns; a shared codemod library for migrations ([37](./37_REPOSITORY_STRUCTURE.md)).

## 18. Examples

```python
# GOOD (Çekirdek): typed, DI'd, bounded, cites invariant
async def recall(self, query: str, *, budget: MemoryBudget) -> list[MemoryItem]:
    """Recall top-K memories for `query` within `budget` (doc 11 §8)."""
    hits = await self._getirim.search(query, k=budget.recall_k)  # bounded (PR-14)
    return self._rank(hits)[: budget.recall_k]
# BAD: print to stdout (breaks protocol, doc 09 §16), unbounded, untyped
def recall(q):
    print("recalling", q)          # forbidden
    return [m for m in ALL_MEMORY] # unbounded, global
```

## 19. Anti-Patterns

- `any`/`Any`/untyped boundaries.
- Bare `catch`/`except: pass`; `unwrap()` on fallible paths.
- Hardcoded user-facing strings or style values.
- Side-effect primitives outside `broker/`.
- `print(` in the Çekirdek; blocking the event loop.
- Import-time side effects / hidden globals.
- Editing generated code.
- Non-Turkish casing on Turkish text.

## 20. Things That Must Never Happen

1. Untyped/`any` at a public API or IPC/storage boundary.
2. A side-effect OS primitive outside the sanctioned broker module.
3. A silent-swallow error handler in production code.
4. A hardcoded user-facing string bypassing i18n.
5. `print`-to-stdout (or any non-protocol stdout write) in the Çekirdek.

## 21. Relationship With Other Subsystems

Operationalizes [02_DESIGN_PRINCIPLES](./02_DESIGN_PRINCIPLES.md) in code; uses names from [44_GLOSSARY](./44_GLOSSARY.md); places files per [37_REPOSITORY_STRUCTURE](./37_REPOSITORY_STRUCTURE.md); errors per [38_ERROR_HANDLING](./38_ERROR_HANDLING.md); logging per [39_LOGGING](./39_LOGGING.md); enforced/gated by [35_TESTING](./35_TESTING.md) and the process in [41_IMPLEMENTATION_RULES](./41_IMPLEMENTATION_RULES.md).

## 22. Migration Considerations

- Adding/tightening a lint rule ships with an auto-fix or a codemod and a grace period; the rule becomes CI-blocking once the codebase is clean. Toolchain upgrades ([33](./33_CONFIGURATION.md)) are validated by the full suite. Renames follow the glossary process ([44](./44_GLOSSARY.md)).
