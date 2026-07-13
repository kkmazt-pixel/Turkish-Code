# 04 — Turkish Design Language (Türk Tasarım Dili — TTD)

> Part of the **turkish.code Engineering Bible**. Canonical source of truth for visual identity.
> **Status:** Canonical · **Version:** 1.0 · **Last updated:** 2026-07-12
> **Owner:** `packages/design-system`
> **Related:** [00_PROJECT_VISION](./00_PROJECT_VISION.md) (Pillar P2) · [03_UI_SYSTEM](./03_UI_SYSTEM.md) · [05_ANIMATION_SYSTEM](./05_ANIMATION_SYSTEM.md) · [06_COMPONENT_LIBRARY](./06_COMPONENT_LIBRARY.md)

---

## 1. Purpose

The **Türk Tasarım Dili (TTD)** is the bespoke visual identity that makes turkish.code unmistakably Turkish and unmistakably premium. It is the single source of truth for **color, typography, spacing, radius, elevation, motifs, iconography, imagery, and voice**. It exists to satisfy Pillar P2 ([00](./00_PROJECT_VISION.md) §5): Turkish is the substrate, not a translation. This document defines the *tokens and rules*; components ([06](./06_COMPONENT_LIBRARY.md)) consume them and motion ([05](./05_ANIMATION_SYSTEM.md)) animates them.

## 2. Scope

The design token system and its semantic layer, palette, typography, spacing/grid, radius/elevation, the motif system, iconography, imagery, dark/light themes, contrast/accessibility, and Turkish-language voice & tone. Out of scope: motion timing curves ([05](./05_ANIMATION_SYSTEM.md)), component anatomy ([06](./06_COMPONENT_LIBRARY.md)), frontend mechanics ([03](./03_UI_SYSTEM.md)).

## 3. Design Philosophy

The TTD abstracts the **geometric heritage of Anatolia** — Seljuk (Selçuklu) star-and-polygon lattices, İznik tile palettes, kilim geometry, and the disciplined negative space of Ottoman illumination (tezhip) — into a **modern, calm, high-contrast, dark-first** interface. Principles:

- **Abstracted, never literal.** Motifs appear as subtle texture, dividers, focus states, and accents — never as kitschy skeuomorphic ornament. Restraint is the aesthetic.
- **Calm and legible.** A coding companion is used for hours; the surface must reduce cognitive load. Generous space, quiet backgrounds, one confident accent at a time.
- **Craft in the details.** The identity lives in micro-decisions: a hairline in İznik cobalt, a focus ring echoing a Seljuk star, a gold accent used sparingly like tezhip gilding.
- **Dark-first.** `gece` (night) is the default theme — kinder to long sessions and to the palette's jewel tones. `gündüz` (day) is a fully-supported equal.
- **Sovereign confidence.** The identity communicates trust, privacy, and craftsmanship — the emotional core of the product.

## 4. Token System Architecture

Three token layers (source of truth: `packages/design-system/tokens`, emitted to CSS custom properties consumed by [03](./03_UI_SYSTEM.md)):

```
Layer 1 — PRIMITIVE tokens   (raw values; never used directly in components)
   turkuaz-500 = #1BA3A3, uzay-2 = 8px, yaricap-2 = 8px, ...
Layer 2 — SEMANTIC tokens    (meaning; components use ONLY these)
   renk.arka         = gece-900        (background)
   renk.vurgu        = turkuaz-500     (primary accent)
   renk.metin        = kar-50          (text)
   bosluk.govde      = uzay-4          (body spacing)
Layer 3 — COMPONENT tokens   (optional per-component overrides)
   dugme.dolgu.vurgu = renk.vurgu
```

**Rule:** components consume **Layer 2 only** (or Layer 3). Primitives are never referenced in a component (PR-2/PR-8: one source of truth). Theme switching swaps Layer-1→Layer-2 mappings, so components need no theme awareness.

## 5. Color Palette (İznik & Seljuk)

Primitive palette (names in Turkish; identifiers ASCII-transliterated per [44](./44_GLOSSARY.md) §2). Hex values are the canonical reference (tune only with contrast re-validation, §11).

| Token | Hex | Origin / meaning |
|---|---|---|
| `turkuaz-500` | `#1BA3A3` | İznik turquoise — **primary accent** |
| `turkuaz-300 / 700` | `#5FD3D0` / `#0E6E6E` | accent tints/shades |
| `cini-mavi-500` | `#1E5FA8` | İznik cobalt — secondary/info |
| `mercan-500` | `#E2533B` | İznik coral-red (bole) — **danger/destructive**, alerts |
| `zumrut-500` | `#1F9D6B` | emerald — **success**, positive |
| `altin-500` | `#C9A24B` | tezhip gold — rare highlight, premium accents (use sparingly) |
| `patlican-500` | `#6C3A6E` | aubergine — special/plugin accents |
| `gece-950…700` | `#0B0F14 … #1B242E` | night backgrounds (dark theme surfaces) |
| `kar-50…200` | `#F7FAFB … #D8E0E4` | snow — text/surfaces on dark; backgrounds on light |
| `kum-100…300` | `#EFE9DE … #CFC4AE` | sand — warm neutral (light theme surfaces) |
| `uyari-500` | `#D98A1F` | amber — warnings (distinct from danger) |

### Semantic mapping (both themes)

| Semantic | `gece` (dark, default) | `gündüz` (light) |
|---|---|---|
| `renk.arka` (bg) | `gece-950` | `kar-50` |
| `renk.yüzey` (surface/card) | `gece-900` | `kum-100` |
| `renk.yüzey-2` (raised) | `gece-800` | `#FFFFFF` |
| `renk.metin` | `kar-50` | `gece-900` |
| `renk.metin-ikincil` | `kar-200` | `gece-700` |
| `renk.kenar` (border/hairline) | `gece-700` | `kum-300` |
| `renk.vurgu` (primary) | `turkuaz-500` | `turkuaz-700` |
| `renk.bilgi` (info) | `cini-mavi-500` | `cini-mavi-500` |
| `renk.başarı` (success) | `zumrut-500` | `zumrut-500` |
| `renk.tehlike` (danger) | `mercan-500` | `mercan-500` |
| `renk.uyarı` (warning) | `uyari-500` | `uyari-500` |
| `renk.altın` (rare highlight) | `altin-500` | `altin-500` |
| `renk.odak` (focus ring) | `turkuaz-300` | `turkuaz-500` |

**Usage discipline:** one dominant accent per view (`turkuaz`). Gold (`altin`) is reserved for genuinely special moments (e.g., a completed council synthesis, a premium state) — like gilding, its power is in scarcity. Danger (`mercan`) only for destructive/irreversible affordances, reinforcing the reversibility ethos (PR-4).

## 6. Typography

- **UI / body typeface:** a humanist variable sans with **complete Turkish coverage** (İ ı ş ğ ç ö ü) and proper `locl` Turkish features. Recommended baseline: **Inter** (variable) as a safe, fully-covering default, optionally paired with a distinctive Turkish display face for headings. The chosen face must be **bundled** (offline, PR-6); no web-font CDN.
- **Monospace (code):** a coding font with clear Turkish glyphs, a dotted/dotless-i distinction, ligature control, and good `ı`/`i`/`l`/`1` differentiation. Baseline: **JetBrains Mono** or **IBM Plex Mono**, bundled.
- **₺ (Turkish Lira):** the type stack must render ₺ correctly.
- **Type scale** (rem, 16px base) — semantic tokens:

| Token | Size / line-height / weight | Use |
|---|---|---|
| `yazi.ekran` | 2.25 / 1.2 / 700 | hero/display |
| `yazi.baslik-1` | 1.75 / 1.25 / 650 | page titles |
| `yazi.baslik-2` | 1.375 / 1.3 / 600 | section titles |
| `yazi.govde` | 1.0 / 1.55 / 400 | body |
| `yazi.govde-vurgu` | 1.0 / 1.55 / 600 | emphasized body |
| `yazi.kucuk` | 0.875 / 1.5 / 400 | secondary/meta |
| `yazi.mono` | 0.9375 / 1.6 / 400 | code |

- **Casing in the type system:** display styles must **never** apply CSS `text-transform: uppercase` blindly — that breaks Turkish `i→I`. If uppercase styling is desired, the string is transformed through the locale helper ([03](./03_UI_SYSTEM.md) §11) *before* rendering, or `text-transform` is paired with `lang="tr"` so the engine applies Turkish casing. Prefer pre-transformed strings. (PR-12.)
- Line length capped ~72ch for readable Turkish prose.

## 7. Spacing, Grid & Layout

- **Base unit:** 4px. Spacing tokens `uzay-1..-10` = 4,8,12,16,24,32,48,64,96,128 px.
- **Grid:** an 8px soft grid; components align to it. Dense areas (code, timeline) may use 4px.
- **Layout regions:** left **rail** (navigation/features), central **workspace**, right **inspector/context** (reasoning trace, memory, permissions). Panels are resizable and collapsible; layout persists as a trivial pref ([03](./03_UI_SYSTEM.md) §14).
- **Density modes:** `rahat` (comfortable, default) and `sıkı` (compact) as a spacing multiplier token — respects long-session comfort vs. information density.

## 8. Radius & Elevation

- **Radius tokens:** `yaricap-1..4` = 4,8,12,16px; `yaricap-tam` = pill/round. Cards use `yaricap-2/3`; inputs `yaricap-2`; the geometry stays crisp (not overly rounded) to echo the disciplined Seljuk line.
- **Elevation:** dark-first, so elevation is expressed with **surface lightening + hairline + soft shadow** rather than heavy drop shadows. Tokens `kat-0..3` (kat = layer): background → surface → raised → overlay. Overlays add a subtle `gece` scrim with a motif watermark (§9) at very low opacity.

## 9. Motif System (Selçuklu / İznik geometry)

Motifs are the identity's soul, applied with restraint:

- **`motif.yildiz`** — the Seljuk 8/10/12-point star lattice. Uses: empty-state backgrounds (very low opacity), the app splash, section dividers, and the **focus ring** micro-shape. Delivered as inline SVG in the design system (offline; themeable via `currentColor`).
- **`motif.kilim`** — angular kilim bands. Uses: progress/loading indicators, selection edges, the timeline "spine."
- **`motif.tezhip`** — gilded illumination flourish. Uses: rare celebratory moments (`altin`), premium badges. Never on routine surfaces.
- **`motif.cini`** — İznik floral abstraction reduced to geometry. Uses: onboarding illustrations, decorative headers.

**Rules:** motifs never reduce text contrast below thresholds (§11); they never animate distractingly (see [05](./05_ANIMATION_SYSTEM.md) reduced-motion); they are always SVG (crisp at any DPI, themeable, offline). No raster texture files that can't retint per theme.

## 10. Iconography & Imagery

- **Icons:** a single bundled, geometrically-consistent inline-SVG set; 1.5px stroke on a 24px grid, aligned to the Seljuk crispness. Icons are monochrome (`currentColor`) and theme via tokens.
- **Illustrations:** abstract-geometric, palette-limited, always vector. Cultural motifs are stylized, not photographic. No stock imagery.
- **Loading & empty states:** use `motif.kilim`/`motif.yildiz` animated subtly rather than generic spinners where possible.

## 11. Contrast & Accessibility (Binding)

- **All text meets WCAG AA** (≥4.5:1 for body, ≥3:1 for large text) against its surface, in **both** themes. This is a gate, not a guideline: the palette ships with a contrast validation table, and CI checks token pairs.
- **Non-text UI** (focus rings, borders on interactive elements) meets ≥3:1.
- **Never rely on color alone**: danger/success/warning always pair color with an icon and/or label (colorblind-safe). Coral-red vs. emerald are distinguishable but must not be the *only* signal.
- **Focus is always visible** (`renk.odak`), using the `motif.yildiz`-inspired ring.
- Reduced-motion handling is defined in [05](./05_ANIMATION_SYSTEM.md); the TTD guarantees a fully static, still-beautiful fallback.

## 12. Voice & Tone (Turkish)

The product *speaks*, and its voice is part of the design:

- **Language:** Turkish by default, warm but professional — like a respected senior colleague (`abi/abla` warmth without slang). Clear, encouraging, never condescending.
- **Address:** default polite-neutral second person; configurable formality. Error messages are calm, blame-free, and actionable (coordinate with [38_ERROR_HANDLING](./38_ERROR_HANDLING.md) message guidelines).
- **Terminology:** use the canonical Turkish subsystem names ([44](./44_GLOSSARY.md)) in the UI (e.g., "Divan", "Muhakeme", "Anlık Görüntü") — this reinforces identity and teaches the vocabulary.
- **Casing correctness** in all copy (PR-12).
- **English locale** mirrors tone but in natural English; never a literal, awkward translation.

## 13. Configuration

- Theme (`gece`/`gündüz`/system), density (`rahat`/`sıkı`), and reduced-motion are user prefs ([03](./03_UI_SYSTEM.md) §14, [33_CONFIGURATION](./33_CONFIGURATION.md)).
- The token set is versioned; a theme is a mapping file, enabling future first-party and plugin themes ([23_PLUGIN_SYSTEM](./23_PLUGIN_SYSTEM.md)) — all of which must pass the contrast gate.

## 14. Dependencies

- Bundled fonts, inline SVG motifs/icons — **zero external design assets at runtime** (PR-6, CSP in [03](./03_UI_SYSTEM.md) §13).
- Token build tooling emits CSS custom properties + typed TS token accessors.

## 15. Edge Cases

- **Missing glyph**: if a bundled face lacks a rare glyph, a defined fallback stack covers it; CI verifies Turkish glyph coverage.
- **Ultra-wide / tiny windows**: layout regions collapse gracefully (rail → icons; inspector → drawer).
- **High-DPI & fractional scaling** (common on Linux): SVG motifs and the grid stay crisp; no raster blur.
- **Forced-colors / OS high-contrast mode**: honor it; map tokens to system colors while preserving danger/success semantics.
- **Colorblind users**: enforced by the "never color alone" rule (§11).

## 16. Failure Recovery

- If a custom/plugin theme fails the contrast gate at load, fall back to the built-in `gece` theme and surface a non-blocking notice (never render an inaccessible UI).

## 17. Security

- No remote assets ⇒ no tracking pixels / CDN leakage (aligns with [30_SECURITY](./30_SECURITY.md)). Plugin themes are validated and sandboxed to token values only (no arbitrary CSS that could exfiltrate via `background: url()`), per [23_PLUGIN_SYSTEM](./23_PLUGIN_SYSTEM.md).

## 18. Performance

- Tokens as CSS variables → theme switch is a single attribute change, no re-render storm. SVG motifs are lightweight and cached. Fonts subset to needed glyph ranges to reduce bundle size while keeping full Turkish coverage. See [31_PERFORMANCE](./31_PERFORMANCE.md).

## 19. Testing Strategy

- **Contrast tests** on every semantic pair, both themes (CI gate).
- **Glyph coverage test** for the Turkish set + ₺.
- **Visual regression** via Storybook snapshots ([06](./06_COMPONENT_LIBRARY.md)).
- **Casing test**: any component that offers uppercase styling is verified against İstanbul/ırmak cases.

## 20. Future Extensions

- Seasonal/regional motif packs; a high-contrast Turkish theme; user-tunable accent within the İznik family (still contrast-gated); optional bundled premium Turkish display typeface.

## 21. Examples

**Semantic token usage (correct):**
```css
.kart { background: var(--renk-yuzey); color: var(--renk-metin);
        border: 1px solid var(--renk-kenar); border-radius: var(--yaricap-3);
        padding: var(--uzay-4); }
.dugme-tehlike { background: var(--renk-tehlike); } /* mercan — destructive only */
```

**Theme switch:** set `document.documentElement.dataset.theme = 'gunduz'` — all tokens remap; no component code changes.

## 22. Anti-Patterns

- Hardcoding a hex value or px in a component instead of a token.
- Using `altin` (gold) routinely, cheapening the accent.
- Literal, heavy cultural ornamentation that harms legibility.
- `text-transform: uppercase` on Turkish text without locale-correct handling.
- Color as the only signal for state.
- Any runtime-fetched font/asset.

## 23. Things That Must Never Happen

1. Text fails WCAG AA contrast in either theme.
2. Turkish glyphs (İ ı ş ğ ç ö ü) or ₺ fail to render.
3. A design asset is fetched from the network at runtime.
4. Uppercase display corrupts Turkish casing.
5. A component reads a primitive token or a raw value instead of a semantic token.

## 24. Relationship With Other Subsystems

The TTD is consumed by [03_UI_SYSTEM](./03_UI_SYSTEM.md) (mechanics), realized by [06_COMPONENT_LIBRARY](./06_COMPONENT_LIBRARY.md) (components), and animated by [05_ANIMATION_SYSTEM](./05_ANIMATION_SYSTEM.md). Its voice coordinates with [38_ERROR_HANDLING](./38_ERROR_HANDLING.md). It directly satisfies Pillar P2 ([00](./00_PROJECT_VISION.md)).

## 25. Migration Considerations

- The token set is versioned; renaming/removing a semantic token is a migration that updates all consumers in one change (semantic tokens are the stable contract; primitives may change freely if semantics hold — PR-8).
- Palette tuning requires re-running the contrast gate before merge.
