# 06 — Component Library (Bileşen Kütüphanesi)

> Part of the **turkish.code Engineering Bible**. Canonical source of truth for UI components.
> **Status:** Canonical · **Version:** 1.0 · **Last updated:** 2026-07-12
> **Owner:** `packages/design-system/components`
> **Related:** [03_UI_SYSTEM](./03_UI_SYSTEM.md) · [04_TURKISH_DESIGN_LANGUAGE](./04_TURKISH_DESIGN_LANGUAGE.md) · [05_ANIMATION_SYSTEM](./05_ANIMATION_SYSTEM.md)

---

## 1. Purpose

Defines the **catalog, anatomy, contracts, and rules** of reusable UI components. It is the bridge between the abstract TTD tokens ([04](./04_TURKISH_DESIGN_LANGUAGE.md)) and concrete, accessible, Turkish-correct building blocks that features ([03](./03_UI_SYSTEM.md)) compose. A component defined here can be built identically by any developer or AI agent.

## 2. Scope

Component taxonomy, per-component contract (props/states/a11y), the product-specific "intelligence" components (chat, reasoning trace, diff, permission prompt, council, timeline), composition rules, and testing. Out of scope: tokens ([04](./04_TURKISH_DESIGN_LANGUAGE.md)), motion presets ([05](./05_ANIMATION_SYSTEM.md)), app wiring ([03](./03_UI_SYSTEM.md)).

## 3. Principles

- **Token-only styling.** Components read semantic tokens ([04](./04_TURKISH_DESIGN_LANGUAGE.md) §4), never raw values. No hardcoded color/space/radius/duration.
- **Headless where it helps.** Complex interactive components (menus, dialogs, comboboxes) build on a headless a11y primitive layer (e.g., Radix-style) skinned with TTD; simple components are hand-built.
- **Accessible by construction.** Keyboard, ARIA, focus management are part of the component contract, not optional ([03](./03_UI_SYSTEM.md) §12).
- **Turkish-correct.** Any label/casing goes through i18n + locale casing ([03](./03_UI_SYSTEM.md) §11). Components accept text via i18n keys or already-localized strings, never invent copy.
- **Composable & single-purpose** (PR-13). Small primitives compose into product components.
- **Controlled + uncontrolled** variants where stateful.
- **No business logic.** Components render and emit events; they never call the Bridge directly (features do). (PR-3, [03](./03_UI_SYSTEM.md).)

## 4. Component Taxonomy

Four tiers:

```
1. PRIMITIVES     — Text, Icon, Box/Stack/Grid, Divider, VisuallyHidden, Motif
2. CONTROLS       — Button, IconButton, Input, Textarea, Select, Combobox, Switch,
                    Checkbox, Radio, Slider, SegmentedControl, Menu, Tooltip, Tabs
3. SURFACES       — Card, Panel, Drawer, Dialog/Modal, Sheet, Toast, Popover,
                    Banner/Alert, Skeleton, EmptyState, Rail, Inspector
4. PRODUCT ("zeki"/intelligent) — see §6
```

## 5. Component Contract (Every Component Documents)

Each component in the library ships with:
- **Anatomy** (named parts).
- **Props** (typed; controlled/uncontrolled; token-driven variants — no free-form style).
- **States** (default, hover, focus, active, disabled, loading, error, selected).
- **Variants** (e.g., Button: `vurgu`/primary, `sessiz`/ghost, `tehlike`/danger, `ana-hat`/outline).
- **Sizes** (`kucuk`/`orta`/`buyuk`).
- **A11y** (role, keyboard map, ARIA, focus behavior).
- **Motion** (which [05](./05_ANIMATION_SYSTEM.md) preset).
- **Do/Don't**.
- **Storybook stories** (all states × both themes × reduced-motion).

**Example — Button (`Dugme`):**
- Variants: `vurgu`, `ana-hat`, `sessiz`, `tehlike` (mercan; destructive only, pairs icon+label). Sizes: kucuk/orta/buyuk.
- States: includes `loading` (kilim shimmer, disables press) and `disabled` (reduced opacity, non-focusable-in-tab? — remains focusable with `aria-disabled` for discoverability).
- A11y: `role=button`, Enter/Space activate, visible `renk.odak` ring.
- Motion: Press preset ([05](./05_ANIMATION_SYSTEM.md) §5).
- Don't: use `tehlike` for non-destructive actions; use color alone to signal danger.

## 6. Product ("Zeki") Components — the Heart of the Product

These are turkish.code-specific and where the design system earns its keep. Each is specified enough to build.

### 6.1 `SohbetGovdesi` — Conversation Surface
Renders the message stream (user + agent), streaming markdown/code, tool activity inline. Virtualized ([03](./03_UI_SYSTEM.md) §9). Composes `MesajBalonu`, `AracEtkinligi`, `MuhakemeIzi`. Streaming motion per [05](./05_ANIMATION_SYSTEM.md) §6. Emits: send, stop, retry, edit.

### 6.2 `MuhakemeIzi` — Reasoning Trace Viewer
Renders the structured reasoning steps from [15_REASONING_ENGINE](./15_REASONING_ENGINE.md) (plan, act, observe, reflect) as an expandable, kilim-spined timeline. Collapsible; deep-links to related tool calls/snapshots. Shows effort mode ([17](./17_EFFORT_MODES.md)) and, in Divan mode, links to `DivanGorunumu`.

### 6.3 `DivanGorunumu` — Council View
Visualizes multiple personas ([16_COUNCIL_MODE](./16_COUNCIL_MODE.md)): each üye's stance/proposal, the critique round, and the synthesis (highlighted with an `altin` pulse, [04](./04_TURKISH_DESIGN_LANGUAGE.md)/[05](./05_ANIMATION_SYSTEM.md)). Read-only inspector of a deliberation.

### 6.4 `KodFarki` — Diff / Edit Review
Renders a file edit as a reviewable diff (CodeMirror-based, [03](./03_UI_SYSTEM.md)). Every diff is backed by a Snapshot ([27_SNAPSHOTS](./27_SNAPSHOTS.md)) and exposes **Accept / Undo** affordances. Danger/irreversible framing uses `mercan`. This component is the visible face of Pillar P4.

### 6.5 `IzinIstemi` — Permission Prompt
The modal-but-non-blocking prompt raised when the agent requests a gated capability ([24_PERMISSION_SYSTEM](./24_PERMISSION_SYSTEM.md)). Shows: capability, exact target (path/command/host), why, and the choices (Bir kez izin ver / Her zaman / Reddet / Planla). Destructive scopes use `mercan` and require deliberate confirmation. Must be unmistakable and never auto-dismiss.

### 6.6 `ZamanCizelgesi` — Timeline Viewer
Renders the append-only event log ([26_TIMELINE](./26_TIMELINE.md)) with filtering (edits, tool calls, messages, reasoning), scrubbing, and jump-to-snapshot. The kilim "spine" motif ([04](./04_TURKISH_DESIGN_LANGUAGE.md) §9) is literal here.

### 6.7 `CabaSecici` — Effort Mode Selector
Segmented control for `Hızlı / Dengeli / Derin / Maksimum` ([17_EFFORT_MODES](./17_EFFORT_MODES.md)) with a plain-Turkish explanation of the latency/quality trade for each. Also surfaces council toggle.

### 6.8 `SaglayiciDurum` — Provider & Model Panel
The provider/model control surface (recovered from the UI evolution, [52_ADR_LOG](./52_ADR_LOG.md); `PROJECT_ANALYSIS.md` L47–54). Shows and controls:
- **Provider status:** active providers (Gemini/Groq/OpenRouter/NVIDIA NIM + Ollama), **health**, quota **headroom**, and the currently-selected model per role ([21_PROVIDER_SYSTEM](./21_PROVIDER_SYSTEM.md)/[48_QUOTA_TIER_MANAGEMENT](./48_QUOTA_TIER_MANAGEMENT.md)/[51_METRICS](./51_METRICS.md)).
- **Auto/Manual model selection:** trust the model-first router ([45_ROUTING_ORCHESTRATION](./45_ROUTING_ORCHESTRATION.md)) or pin a model/provider per role.
- **Cost/Quota mode:** the Performance/Balanced/Economy selector ([17_EFFORT_MODES](./17_EFFORT_MODES.md) §4b).
- **API key management:** enter/rotate/remove per-provider keys (light handling, [34_API_KEYS](./34_API_KEYS.md)).
- **Speed Test:** run latency probes across providers/models and compare ([50_BENCHMARK_SPEEDTEST](./50_BENCHMARK_SPEEDTEST.md)).
- **Online/offline indicator:** clearly shows when the local Ollama fallback is in use ([32_OFFLINE_FIRST](./32_OFFLINE_FIRST.md)).

### 6.9 `BellekPaneli` — Memory Inspector
Browse/search/edit durable memory ([11_MEMORY_SYSTEM](./11_MEMORY_SYSTEM.md)); shows what was recalled for the current run and lets the user pin/forget items (control is a P4/P5 requirement).

### 6.10 `KurtarmaEkrani` — Recovery Screen
Presents a recoverable session after a crash ([28_CRASH_RECOVERY](./28_CRASH_RECOVERY.md)): what was in flight, what will be resumed, and resume/discard choices.

### 6.11 `KomutPaleti` — Command Palette
`Ctrl/Cmd-K` palette exposing every action (a11y + power-user path, [03](./03_UI_SYSTEM.md) §12). Turkish-collated search ([03](./03_UI_SYSTEM.md) §11).

## 7. Composition Rules

- Features compose product components; product components compose surfaces/controls/primitives. **Downward-only** dependency (a primitive never imports a product component).
- Layout is done with `Stack`/`Grid`/`Box` primitives on the TTD grid ([04](./04_TURKISH_DESIGN_LANGUAGE.md) §7); no raw flexbox with magic numbers in features.
- Overlays (Dialog, Drawer, Toast, Popover) render through a single portal/overlay manager to guarantee focus trapping, stacking order, and scrim consistency.

## 8. State & Feedback Conventions

- **Loading:** skeletons for content-shaped areas; kilim shimmer for actions ([05](./05_ANIMATION_SYSTEM.md) §8).
- **Empty:** `EmptyState` with a motif illustration + a clear Turkish next action.
- **Error:** `Banner`/inline error with calm, actionable Turkish copy ([38_ERROR_HANDLING](./38_ERROR_HANDLING.md)); never a raw stack trace to the user (that goes to logs, [39](./39_LOGGING.md)).
- **Success/danger:** color + icon + label (never color alone, [04](./04_TURKISH_DESIGN_LANGUAGE.md) §11).

## 9. Configuration

- Density (`rahat`/`sıkı`) and theme are read from context providers ([03](./03_UI_SYSTEM.md), [04](./04_TURKISH_DESIGN_LANGUAGE.md)); components adapt via tokens automatically.

## 10. Dependencies

- Internal: TTD tokens ([04](./04_TURKISH_DESIGN_LANGUAGE.md)), motion presets ([05](./05_ANIMATION_SYSTEM.md)), i18n ([03](./03_UI_SYSTEM.md)).
- External (bundled): a headless a11y primitive lib, CodeMirror 6 (for `KodFarki`/code views), Motion. All offline (PR-6).

## 11. Edge Cases

- **Long Turkish labels** (agglutinative words get long): components truncate with accessible tooltips, never clip silently.
- **Overlay over streaming:** `IzinIstemi` must appear over an active stream without stopping it ([03](./03_UI_SYSTEM.md) §8).
- **Nested overlays** (permission prompt during a dialog): overlay manager stacks and traps focus correctly.
- **Reduced-motion / forced-colors:** every component has a verified static, high-contrast rendering.
- **Very large diffs:** `KodFarki` virtualizes.

## 12. Failure Recovery

- A component that receives malformed data (e.g., an unknown event type) renders a safe fallback (`EmptyState`/unknown-item chip) and reports to logs rather than crashing the tree ([03](./03_UI_SYSTEM.md) §17 error boundary).

## 13. Security

- Any component that renders model/tool/plugin-provided content sanitizes it ([03](./03_UI_SYSTEM.md) §13). `KodFarki` and markdown renderers never execute embedded content. Links surfaced by the agent are inert until a brokered, permissioned action opens them.

## 14. Performance

- Product components virtualize long lists, memoize, and animate only compositor-friendly properties ([05](./05_ANIMATION_SYSTEM.md), [31](./31_PERFORMANCE.md)). `SohbetGovdesi`/`ZamanCizelgesi` must stay 60fps at large sizes.

## 15. Testing Strategy

- **Storybook** is the component workbench: every component × states × both themes × reduced-motion.
- **Unit/interaction:** Vitest + Testing Library (keyboard nav, ARIA, controlled/uncontrolled).
- **Visual regression:** deterministic Storybook snapshots (contrast + layout).
- **A11y:** automated axe checks on stories + manual screen-reader passes for product components.
- **Turkish-locale:** casing/collation/truncation cases in labels. See [35_TESTING](./35_TESTING.md).

## 16. Future Extensions

- Plugin-contributed components mount only inside sandboxed panels ([23_PLUGIN_SYSTEM](./23_PLUGIN_SYSTEM.md)) and must pass the same token/a11y/contrast gates. New product components (e.g., a graph explorer for [12_KNOWLEDGE_GRAPH](./12_KNOWLEDGE_GRAPH.md)) are added to §6 with a full contract.

## 17. Examples

```tsx
// Feature composing product + control components (no Bridge calls inside components)
<Panel baslik={t('sohbet.baslik')}>
  <SohbetGovdesi runId={run.id} onDur={() => feature.stop()} />
  <CabaSecici value={effort} onChange={feature.setEffort} />
</Panel>
```

## 18. Anti-Patterns

- Hardcoding style values instead of tokens.
- Putting Bridge/business calls inside a component.
- Inventing copy in a component instead of i18n keys.
- Using `tehlike`/`mercan` for non-destructive actions.
- Bypassing the overlay manager (breaks focus/stacking).
- A product component importing a feature (dependency must point downward).

## 19. Things That Must Never Happen

1. A component renders raw/unsanitized model/plugin HTML.
2. A destructive action lacks the danger treatment + confirmation.
3. `IzinIstemi` auto-dismisses or is visually ambiguous.
4. A `KodFarki` edit lacks a backing Snapshot/undo affordance.
5. A component ships without keyboard access and a reduced-motion/contrast-verified state.

## 20. Relationship With Other Subsystems

Turns TTD tokens ([04](./04_TURKISH_DESIGN_LANGUAGE.md)) + motion ([05](./05_ANIMATION_SYSTEM.md)) into concrete building blocks for features ([03](./03_UI_SYSTEM.md)). The product components are the visible surface of the reasoning ([15](./15_REASONING_ENGINE.md)), council ([16](./16_COUNCIL_MODE.md)), permission ([24](./24_PERMISSION_SYSTEM.md)), snapshot ([27](./27_SNAPSHOTS.md)), timeline ([26](./26_TIMELINE.md)), memory ([11](./11_MEMORY_SYSTEM.md)), and provider ([21](./21_PROVIDER_SYSTEM.md)) subsystems.

## 21. Migration Considerations

- Component APIs are semver'd within the design system; a breaking prop change is a tracked migration across features. Renaming a component follows the glossary/terminology process ([44](./44_GLOSSARY.md)). Token changes flow in automatically (PR-8).
