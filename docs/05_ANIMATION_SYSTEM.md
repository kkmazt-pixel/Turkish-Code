# 05 — Animation System (Hareket Sistemi)

> Part of the **turkish.code Engineering Bible**. Canonical source of truth for motion.
> **Status:** Canonical · **Version:** 1.0 · **Last updated:** 2026-07-12
> **Owner:** `packages/design-system/motion`
> **Related:** [03_UI_SYSTEM](./03_UI_SYSTEM.md) · [04_TURKISH_DESIGN_LANGUAGE](./04_TURKISH_DESIGN_LANGUAGE.md) · [06_COMPONENT_LIBRARY](./06_COMPONENT_LIBRARY.md) · [31_PERFORMANCE](./31_PERFORMANCE.md)

---

## 1. Purpose

Defines **how turkish.code moves**: the motion tokens (durations, easings), the standard transition patterns, streaming-specific motion, motif-based loaders, orchestration rules, and the accessibility contract for reduced motion. Motion is part of the identity (calm, crafted — [04](./04_TURKISH_DESIGN_LANGUAGE.md)) and part of usability (feedback, continuity), but it is **never** decoration that costs comprehension or frames.

## 2. Scope

Motion tokens, transition catalog, streaming motion, loaders/skeletons, orchestration/choreography, gesture feedback, and reduced-motion. Out of scope: static visual tokens ([04](./04_TURKISH_DESIGN_LANGUAGE.md)), component structure ([06](./06_COMPONENT_LIBRARY.md)).

## 3. Motion Philosophy

- **Purposeful, not performative.** Every animation communicates: state change, spatial continuity, causality, or progress. If it says nothing, it doesn't ship.
- **Calm and quick.** Durations are short; nothing makes the user wait on decoration. The feel is confident and unhurried, echoing the disciplined TTD.
- **Continuity over cuts.** Elements move/transform between states rather than popping, so the user's mental model stays intact.
- **Motif-aware.** Loaders and progress express the Seljuk/kilim geometry ([04](./04_TURKISH_DESIGN_LANGUAGE.md) §9) — identity even in waiting.
- **Respectful.** Reduced-motion is a first-class, fully-supported mode, not an afterthought (§10).

## 4. Motion Tokens

Source of truth: `packages/design-system/motion`. Components/animations use **only** these tokens (PR-2/PR-8 — no ad-hoc durations/easings).

### Durations (`sure.*`)
| Token | ms | Use |
|---|---|---|
| `sure.aninda` | 0 | reduced-motion / instant |
| `sure.hizli` | 120 | hovers, small state toggles |
| `sure.temel` | 200 | default transitions (most UI) |
| `sure.orta` | 320 | panel/drawer, modal enter |
| `sure.yavas` | 480 | large surface transitions, onboarding |

### Easings (`egri.*`)
| Token | curve | Use |
|---|---|---|
| `egri.standart` | cubic-bezier(0.2, 0, 0, 1) | most enter/move |
| `egri.giris` | cubic-bezier(0, 0, 0, 1) (decelerate) | elements entering |
| `egri.cikis` | cubic-bezier(0.4, 0, 1, 1) (accelerate) | elements leaving |
| `egri.yay` | spring(stiffness 320, damping 30) | playful/tactile (drag, reorder) |

### Distances / choreography
- `hareket.kayma` = 8–16px default translate distance for enter/leave.
- `sira.gecikme` = 24ms stagger step for list orchestration (capped list length before stagger disables, §7).

## 5. Transition Catalog (Standard Patterns)

Each pattern is a named, reusable Motion preset:

| Pattern | Tokens | Where |
|---|---|---|
| **Fade+Rise** (enter) | `sure.temel` + `egri.giris`, rise `hareket.kayma` | new messages, cards, list items |
| **Fade+Sink** (leave) | `sure.hizli` + `egri.cikis` | removals, dismissals |
| **Panel Slide** | `sure.orta` + `egri.standart` | rail/inspector/drawer open/close |
| **Modal/Overlay** | scrim fade `sure.temel` + content Fade+Rise; motif scrim ([04](./04_TURKISH_DESIGN_LANGUAGE.md) §8) | dialogs, permission prompts |
| **Shared-element / layout** | Motion layout animation `sure.orta` `egri.standart` | item moving between lists, expanding a card to a view |
| **Press** | scale 0.98 `sure.hizli` `egri.yay` | buttons, tappable rows |
| **Highlight pulse** | one gentle `renk.vurgu`/`altin` glow, `sure.orta` | success, council synthesis moment ([16](./16_COUNCIL_MODE.md)) |

## 6. Streaming Motion (Critical to This Product)

turkish.code streams tokens and reasoning constantly; motion here must aid reading without jitter:

- **Token stream:** appended text uses a subtle **fade-in of new glyph runs** (batched per animation frame, coordinated with the delta-coalescing in [03](./03_UI_SYSTEM.md) §9). Never animate each character individually at high volume (perf + readability). No layout shift as text grows (reserve/stabilize width).
- **Reasoning steps:** each new step in the Muhakeme trace ([15](./15_REASONING_ENGINE.md)) enters with **Fade+Rise**; a thin `motif.kilim` "spine" animates along the trace to show progress.
- **Tool activity:** a tool invocation ([20](./20_TOOL_SYSTEM.md)) shows a compact running indicator (kilim shimmer) that resolves to success/fail with a color+icon state change (never color alone, [04](./04_TURKISH_DESIGN_LANGUAGE.md) §11).
- **Cursor/typing affordance:** a calm caret pulse indicates active generation; it stops instantly on complete/cancel.
- **Interrupt:** hitting Stop animates the stream to a settled state (no abrupt disappearance) while `$/cancel` propagates ([10](./10_IPC.md)).

## 7. Orchestration & Choreography

- **Stagger** list entrances with `sira.gecikme`, but **cap** it: lists longer than N (e.g., 12) disable stagger and just fade the viewport batch (virtualized lists never stagger off-screen items — [03](./03_UI_SYSTEM.md) §9, PR-14).
- **One focal motion at a time.** Avoid competing simultaneous large animations; the eye should have one thing to follow.
- **Origin-aware:** overlays/menus animate from their trigger's position for spatial continuity.
- **Interruptibility:** all animations are interruptible and reversible; a state change mid-animation re-targets rather than queuing (Motion's velocity-preserving transitions).

## 8. Loaders, Skeletons & Progress

- **Indeterminate:** `motif.kilim` shimmer band or a slow-rotating `motif.yildiz` — identity-forward, calm.
- **Determinate:** a kilim-segmented progress bar filling in `renk.vurgu`.
- **Skeletons:** token-colored placeholder blocks with a low-amplitude shimmer for content that will stream in.
- **Long operations** (indexing a workspace, [13](./13_RAG_SYSTEM.md)) show real progress from backend events, never a fake spinner — honesty (PR-11).

## 9. Configuration

- Reduced-motion follows OS `prefers-reduced-motion` and an in-app override ([33](./33_CONFIGURATION.md)).
- A global "motion intensity" pref (`tam`/full, `hafif`/subtle, `kapalı`/off) maps to token overrides.

## 10. Reduced Motion (Binding Accessibility Contract)

When reduced-motion is active (OS or in-app):
- All non-essential motion is replaced by **instant** state changes (`sure.aninda`) or a simple opacity crossfade ≤ `sure.hizli`.
- **No** translate/scale/spring/parallax; **no** looping decorative motion (spinners become a static motif + text).
- Streaming still updates content (that's information, not decoration) but without per-run fade choreography — text simply appears.
- The UI remains **fully functional and still beautiful** in this mode ([04](./04_TURKISH_DESIGN_LANGUAGE.md) §11 guarantees a static fallback). This is verified in tests (§14).

## 11. Dependencies

- **Motion** (Framer-Motion successor) bundled; CSS transitions/`@keyframes` for the simplest cases to avoid JS overhead. No runtime-fetched animation assets (Lottie JSON is allowed only if bundled and static).

## 12. Edge Cases

- **Low-end GPU / software rendering** (Linux WebKitGTK without accel): motion auto-simplifies (drop springs/blur, prefer opacity/transform only) — a degradation ladder (PR-7, [31](./31_PERFORMANCE.md)).
- **High token throughput:** batching prevents animation thrash; if frames still drop, the system reduces to no-fade appends automatically.
- **Fractional DPI scaling (Linux):** use transform-based motion (GPU-composited) to avoid sub-pixel jitter.
- **Background tab/window:** pause decorative loops when the window is not visible.

## 13. Performance

- Animate **only** compositor-friendly properties (`transform`, `opacity`); never animate layout-triggering properties (`width`, `top`, `height`) on hot paths.
- Respect a frame budget; coalesce with the render loop; cap concurrent animations. Metrics/budgets in [31](./31_PERFORMANCE.md).
- Streaming fade batching is the single biggest perf lever — it is mandatory, not optional.

## 14. Testing Strategy

- **Reduced-motion test:** assert that with the flag set, no transform/scale animations run and the UI is fully operable (a first-class gate, PR-11/PR-12 spirit of accessibility).
- **Performance test:** streaming at high token rate stays ≥ 55fps (see [31](./31_PERFORMANCE.md), [35](./35_TESTING.md)).
- **Visual regression** of key transitions via deterministic (time-frozen) snapshots.

## 15. Future Extensions

- Richer motif-based celebratory sequences (tezhip gilding animation) for milestones; optional "focus mode" that quiets all motion; plugin-provided motion presets (must obey tokens + reduced-motion).

## 16. Examples

```ts
// motion/presets.ts — the ONLY source of animation values
export const fadeRise = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.2, ease: EGRI.giris } },
  exit:    { opacity: 0, y: 8,  transition: { duration: 0.12, ease: EGRI.cikis } },
};
// Components import presets; they never inline durations/easings.
```

## 17. Anti-Patterns

- Inlining durations/easings instead of tokens.
- Animating `width`/`height`/`top` on hot paths.
- Per-character animation of streamed text at volume.
- Decorative infinite loops that ignore reduced-motion or run off-screen.
- Motion that delays the user's ability to act.

## 18. Things That Must Never Happen

1. Reduced-motion is set but decorative transform/spring animations still run.
2. Streaming animation drops frames due to per-token animation (must batch).
3. An animation blocks interaction or input.
4. Animation values are hardcoded outside the motion token set.

## 19. Relationship With Other Subsystems

Realizes the calm/crafted feel of [04_TURKISH_DESIGN_LANGUAGE](./04_TURKISH_DESIGN_LANGUAGE.md); is consumed by [06_COMPONENT_LIBRARY](./06_COMPONENT_LIBRARY.md); is constrained by [03_UI_SYSTEM](./03_UI_SYSTEM.md) rendering rules and [31_PERFORMANCE](./31_PERFORMANCE.md) budgets; animates streaming from [15_REASONING_ENGINE](./15_REASONING_ENGINE.md) and [20_TOOL_SYSTEM](./20_TOOL_SYSTEM.md).

## 20. Migration Considerations

- Motion tokens are versioned with the design system; changing a token updates all presets centrally (PR-8). New presets are added to the catalog (§5), never invented ad-hoc in features.
