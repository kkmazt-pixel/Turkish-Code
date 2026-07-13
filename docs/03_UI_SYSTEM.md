# 03 — UI System (Arayüz Sistemi)

> Part of the **turkish.code Engineering Bible**. Canonical source of truth.
> **Status:** Canonical · **Version:** 1.0 · **Last updated:** 2026-07-12
> **Owner tier:** Arayüz (Frontend)
> **Related:** [04_TURKISH_DESIGN_LANGUAGE](./04_TURKISH_DESIGN_LANGUAGE.md) · [05_ANIMATION_SYSTEM](./05_ANIMATION_SYSTEM.md) · [06_COMPONENT_LIBRARY](./06_COMPONENT_LIBRARY.md) · [08_TAURI_ARCHITECTURE](./08_TAURI_ARCHITECTURE.md) · [10_IPC](./10_IPC.md) · [26_TIMELINE](./26_TIMELINE.md)

---

## 1. Purpose

Defines the **architecture of the frontend tier (Arayüz)**: the framework, the state model, how it talks to the Kabuk, how it renders streaming AI output, its rendering/layout system, internationalization, accessibility, and the strict boundary that keeps it a pure presentation layer. The *visual identity* (colors, motifs, typography) is [04](./04_TURKISH_DESIGN_LANGUAGE.md); the *motion* is [05](./05_ANIMATION_SYSTEM.md); the *component catalog* is [06](./06_COMPONENT_LIBRARY.md). This document is the *engine* those three feed into.

## 2. Scope

Frontend framework and structure, state management, the Bridge client, streaming rendering, layout/windowing, theming mechanics, i18n/locale, accessibility, error/empty/loading states, and testing. Out of scope: any business logic (that is Çekirdek), OS access (that is Kabuk).

## 3. Goals

1. A **pure presentation tier** — zero business logic, zero secrets, zero direct OS/network ([01](./01_ARCHITECTURE.md) §4.1, PR-3).
2. Native-feeling, 60fps-smooth, beautiful per the TTD.
3. First-class streaming: reasoning traces, token deltas, and tool activity render live and interruptibly.
4. Fully rehydratable: a WebView reload never loses authoritative state.
5. Turkish-first correctness (PR-12): locale casing, glyphs, pluralization.
6. Accessible (keyboard-first, screen-reader-capable, high-contrast).

### Non-Goals
- No client-side persistence of authoritative data (only trivial view prefs, via Kabuk).
- No SSR/routing-server concerns (this is a desktop WebView, not a website).

## 4. Technology Choices (and Rationale)

| Concern | Choice | Rationale / Rejected alternatives |
|---|---|---|
| Framework | **React 19 + TypeScript** | Largest ecosystem + AI-agent familiarity (serves the "AI can implement this" meta-goal), concurrent rendering for streaming. Rejected: Svelte/Solid (smaller ecosystem/training-data), plain web components (slower to build the rich surface). |
| Build | **Vite 6** | Fast HMR, first-class Tauri integration. |
| View state | **Zustand** | Minimal, explicit stores (PR-9). Rejected: Redux (boilerplate), global context soup. |
| Server/Core state | **TanStack Query** over the Bridge | Caching, invalidation, request dedupe for control-plane calls. |
| Styling | **TTD tokens via CSS custom properties** + a thin utility layer | Bespoke identity ([04](./04_TURKISH_DESIGN_LANGUAGE.md)); tokens not hardcoded values. |
| Animation | **Motion** (Framer-Motion successor) | See [05](./05_ANIMATION_SYSTEM.md). |
| Code/diff view | **CodeMirror 6** | Lightweight, extensible, good perf on large files; Turkish comment rendering. Rejected: Monaco (heavier, VS-Code-coupled). |
| Icons | Inline SVG icon set (part of design system) | Offline, themeable, no CDN (PR-6). |

All dependencies must be **bundled** (no CDN/runtime fetch) to honor offline-first (PR-6) and the CSP (§11).

## 5. Architecture

```
apps/desktop/src/
  app/           # AppShell, theme + locale providers, top-level layout, error boundary
  features/      # feature modules, each self-contained:
    sohbet/        (chat/conversation surface)
    calisma/       (workspace/file explorer + editor)
    zaman/         (Timeline viewer, doc 26)
    muhakeme/      (reasoning trace viewer, doc 15)
    divan/         (council view, doc 16)
    ayarlar/       (settings: providers, permissions, effort, doc 33/34)
    kurtarma/      (crash recovery UI, doc 28)
  bridge/        # typed client over Tauri commands + event subscriptions (doc 10)
  stores/        # Zustand view-state stores
  i18n/          # locale resources + the locale engine
  styles/        # TTD token imports, resets, globals
```

- **Feature module rule:** each feature owns its components, its store slice, its Bridge calls, and its strings. Features do not import each other's internals; they communicate through shared stores or the Bridge. (PR-13.)
- **AppShell** composes the window chrome (title bar, side rail, panels), mounts providers (Theme, Locale, QueryClient, ErrorBoundary), and hosts the active feature.

### 4-Layer frontend model

```
┌───────────────────────────────────────────────┐
│  View Layer (React components, TTD-styled)     │  what the user sees
├───────────────────────────────────────────────┤
│  State Layer (Zustand view stores + TanStack)  │  ephemeral view state + Core caches
├───────────────────────────────────────────────┤
│  Bridge Layer (typed command/event client)     │  the ONLY way out (doc 10)
├───────────────────────────────────────────────┤
│  Kabuk (Rust) via Tauri invoke/events          │  trust boundary
└───────────────────────────────────────────────┘
```

Nothing in the View or State layer may reach past the Bridge layer. This is enforced by lint rules (no `@tauri-apps/api` imports outside `bridge/`, no `fetch`/`XMLHttpRequest` anywhere).

## 6. Data Flow

### 6.1 Control (request/response)
`View → dispatch → Bridge.invoke("method", params) → Kabuk → (maybe Çekirdek) → result → TanStack cache → View`. Used for discrete actions (open workspace, list providers, send message).

### 6.2 Stream (live updates)
`Kabuk emits Tauri events (reasoning.step, token.delta, tool.activity, log.line) → Bridge subscription → reducer → store → View`. Streaming is append-first: the reasoning/chat view maintains an ordered event buffer keyed by a run id and appends deltas. See [10_IPC](./10_IPC.md) §streaming and [15_REASONING_ENGINE](./15_REASONING_ENGINE.md) for event shapes.

### 6.3 Rehydration
On mount/reload, the Arayüz calls `app.bootstrap` then `session.resume` to fetch the current session's event log tail and rebuild the view from authoritative state ([01](./01_ARCHITECTURE.md) §7). It never assumes local memory survived the reload.

## 7. Lifecycle

```
mount AppShell
  → providers init (theme from Kabuk pref, locale = tr default)
  → app.bootstrap (locale, theme, last workspace, provider/health status)
  → if recoverable session → route to kurtarma feature (doc 28)
  → else → route to last feature / home
  → subscribe to global event streams (health, log, notifications)
runtime
  → user interactions dispatch control calls; streams update views
unmount / reload
  → unsubscribe; no flush needed (no authoritative state held)
```

## 8. State Machine (Streaming Run View)

The chat/reasoning surface for a single run:

```
[Idle] --send--> [Submitting] --ack--> [Streaming]
   ▲                  │ error              │  token.delta / reasoning.step (loop)
   │                  ▼                    │  tool.activity (permission prompts may interleave)
   │              [Error]                  ├--complete--> [Done]
   │                                       ├--cancel----> [Cancelled]
   └───────────────── reset ───────────────┘
```

- **[Streaming]** is interruptible: a Stop control sends `$/cancel` (doc 10). The view remains responsive throughout (streaming never blocks the main thread; heavy tokenization runs in a Web Worker).
- Permission prompts (doc 24) surface as modal-but-non-blocking overlays during [Streaming] without tearing down the stream.

## 9. Rendering Concerns

- **Streaming markdown/code:** partial markdown is rendered incrementally; code blocks stream into CodeMirror read-only views with Turkish-aware syntax and comment rendering. A tokenizer Web Worker keeps the main thread free.
- **Virtualization:** long timelines, chat histories, and file trees are virtualized (windowed lists) to stay at 60fps regardless of length (PR-14, [31_PERFORMANCE](./31_PERFORMANCE.md)).
- **Diff rendering:** file edits from tools render as reviewable diffs with snapshot-backed accept/undo affordances (doc 27).
- **Backpressure:** if event volume exceeds render budget, the store coalesces deltas (e.g., batch token appends per animation frame) rather than dropping data. See [10_IPC](./10_IPC.md) §backpressure.

## 10. Theming Mechanics

- TTD tokens are exposed as CSS custom properties on `:root`, switched by a `data-theme` attribute (`gece`/night dark default, `gunduz`/day light). See [04](./04_TURKISH_DESIGN_LANGUAGE.md).
- The theme provider reads the user's preference from the Kabuk (persisted trivial pref) and also honors OS `prefers-color-scheme`.
- No component hardcodes a color/space/radius; all consume tokens (lint-enforced). Rationale: [04](./04_TURKISH_DESIGN_LANGUAGE.md) is the single source of visual truth.

## 11. Internationalization & Turkish Locale (Critical)

- **Default locale is `tr` (Turkish).** `en` is a full secondary locale. All user-facing strings come from `i18n/` resource bundles; **no hardcoded strings** (PR-12; lint-enforced).
- **Casing:** all case transforms use a locale-aware helper that implements Turkish rules — `İ↔i` (dotted) and `I↔ı` (dotless). Never use JS default `toUpperCase/toLowerCase` on user or UI text; use `toLocaleUpperCase('tr')`/`toLocaleLowerCase('tr')` via the i18n helper. A single utility (`i18n/case.ts`) owns this (PR-2, one path).
- **Pluralization & formatting:** use `Intl` with the `tr` locale for numbers, dates, plurals, and lists.
- **Collation:** sorting user-visible lists uses `Intl.Collator('tr')` (correct Turkish alphabetical order).
- **Glyph coverage:** the type stack must fully cover İ ı ş ğ ç ö ü and Turkish Lira ₺ (see [04](./04_TURKISH_DESIGN_LANGUAGE.md) typography).
- The locale engine also feeds the Çekirdek: the active locale is passed on each `session.send` so reasoning output is Turkish by default (see [15_REASONING_ENGINE](./15_REASONING_ENGINE.md)).

## 12. Accessibility

- Keyboard-first: every action reachable without a mouse; a command palette (`Ctrl/Cmd-K`) exposes all commands.
- ARIA roles on all interactive components; focus management on modals/overlays; visible focus rings from TTD tokens.
- Screen-reader announcements for streaming milestones (run started, tool ran, done) — not per-token spam.
- Respects `prefers-reduced-motion` (coordinated with [05](./05_ANIMATION_SYSTEM.md)).
- Minimum contrast ratios enforced by the TTD palette ([04](./04_TURKISH_DESIGN_LANGUAGE.md) §contrast).

## 13. Security (Frontend-Specific)

- **Strict CSP:** no remote origins; `connect-src` limited to the Tauri IPC scheme; no inline scripts except the bundled app; no `eval`. This makes prompt-injected content in rendered model output unable to phone home (defense in depth behind the Kabuk egress choke point).
- **Rendered model output is untrusted:** markdown/HTML from the model is sanitized; links are not auto-followed; any action a rendered artifact suggests must go through the Bridge + permission engine, never a direct capability.
- The Arayüz holds **no secrets** and cannot read the keychain (PR-3, [30_SECURITY](./30_SECURITY.md)).
- See [08_TAURI_ARCHITECTURE](./08_TAURI_ARCHITECTURE.md) for capability allowlisting of the Bridge.

## 14. Configuration

- Trivial view prefs (theme, panel layout, last route) persist via a Kabuk-backed key-value pref store (not the App DB directly; the Arayüz has no DB access). See [33_CONFIGURATION](./33_CONFIGURATION.md).
- Feature flags for in-development UI are read at bootstrap from config.

## 15. Dependencies

- Internal: `packages/design-system` ([04](./04_TURKISH_DESIGN_LANGUAGE.md)/[06](./06_COMPONENT_LIBRARY.md)), `packages/ipc-schema` (Bridge types, [10](./10_IPC.md)).
- External (bundled): React, Vite, Zustand, TanStack Query, Motion, CodeMirror 6, an Intl polyfill only if a target WebView lacks `tr` locale data (see edge cases).

## 16. Edge Cases

- **WebView lacks full `tr` `Intl` data** (older WebKitGTK): bundle ICU/locale data or a `tr` pluralization/collation fallback; never silently use `en` rules on Turkish text.
- **Very large file / diff** (100k+ lines): virtualize and lazy-tokenize; offer "open externally" affordance via a brokered command.
- **Event stream faster than render**: coalesce per frame (§9 backpressure).
- **Reload mid-run**: rehydrate and resume streaming from last event id (§6.3).
- **Çekirdek not ready at bootstrap**: render a "starting brain" state; keep settings/diagnostics usable ([01](./01_ARCHITECTURE.md) §14).
- **RTL/mixed content**: Turkish is LTR, but code/paths and occasional Arabic-script content must render correctly with proper bidi isolation.

## 17. Failure Recovery

- A React render error is caught by a top-level Error Boundary that offers "reload view" (safe, since no authoritative state is lost) and reports the error to the Kabuk log (doc 39).
- Loss of the event stream (Çekirdek restart) shows a reconnecting state and resumes from last event id after the supervisor recovers ([28_CRASH_RECOVERY](./28_CRASH_RECOVERY.md)).

## 18. Performance

- Budgets: first paint < 1s independent of Çekirdek readiness; interaction latency < 100ms; sustained 60fps during streaming. See [31_PERFORMANCE](./31_PERFORMANCE.md) for measurement.
- Techniques: virtualization, per-frame delta coalescing, Web Workers for tokenization, code-splitting per feature, memoization discipline.

## 19. Testing Strategy

- Component/unit: Vitest + Testing Library.
- Visual/interaction: Storybook for the design system ([06](./06_COMPONENT_LIBRARY.md)).
- E2E: Playwright driving the packaged app (or a Tauri mock of the Bridge). Includes a **Turkish-locale test suite** (casing, collation, plurals, glyph rendering) as a first-class gate (PR-12). See [35_TESTING](./35_TESTING.md).
- Contract: Bridge types generated from `ipc-schema`; a mock Bridge validates the Arayüz against the contract without a live Çekirdek.

## 20. Future Extensions

- Split-view / multi-pane sessions; themeable "skins" within the TTD; plugin-provided UI panels (sandboxed, doc 23); an accessibility high-contrast Turkish theme variant.

## 21. Examples

**Locale-correct casing (the one allowed path):**
```ts
// i18n/case.ts — the ONLY place case transforms live (PR-2, PR-12)
export const trUpper = (s: string) => s.toLocaleUpperCase('tr');
export const trLower = (s: string) => s.toLocaleLowerCase('tr');
// "istanbul" -> trUpper -> "İSTANBUL"; "IĞDIR" -> trLower -> "ığdır"
```

**Bridge call (the only way out):**
```ts
// bridge/session.ts
export const sendMessage = (p: SendParams) =>
  invoke<SendAck>('session.send', p);      // types from packages/ipc-schema
```

## 22. Anti-Patterns

- Importing `@tauri-apps/api` or calling `fetch` outside `bridge/`.
- Hardcoding a color/space or a user-facing string.
- Using `String.toUpperCase()` on Turkish text.
- Holding authoritative session/memory state in a Zustand store.
- Blocking the main thread on tokenization or diffing.
- Rendering model-provided HTML without sanitization.

## 23. Things That Must Never Happen

1. The Arayüz reaches the network or filesystem directly (only via Bridge → Kabuk).
2. A secret is present in frontend memory or storage.
3. User-facing text bypasses i18n or uses non-Turkish casing rules on Turkish text.
4. Authoritative AI state is treated as owned by the frontend.
5. Model-generated content triggers a capability without passing the permission engine.

## 24. Relationship With Other Subsystems

Consumes visual truth from [04](./04_TURKISH_DESIGN_LANGUAGE.md), motion from [05](./05_ANIMATION_SYSTEM.md), components from [06](./06_COMPONENT_LIBRARY.md). Talks only to [08_TAURI_ARCHITECTURE](./08_TAURI_ARCHITECTURE.md) via [10_IPC](./10_IPC.md). Renders data produced by the reasoning ([15](./15_REASONING_ENGINE.md)), timeline ([26](./26_TIMELINE.md)), council ([16](./16_COUNCIL_MODE.md)), and permission ([24](./24_PERMISSION_SYSTEM.md)) subsystems. Bound by [30_SECURITY](./30_SECURITY.md) and [31_PERFORMANCE](./31_PERFORMANCE.md).

## 25. Migration Considerations

- The Bridge contract is versioned; a frontend built against an older contract must be detected at handshake and refuse to run against an incompatible Kabuk ([01](./01_ARCHITECTURE.md) §14, [10](./10_IPC.md)).
- Swapping the UI framework (e.g., React→X) must not change the Bridge contract — the boundary makes this a contained migration (PR-8).
