---
name: blackrim-nimbus
description: Marketing + docs site for blackrim-nimbus-skills — the cloud-toolkits marketplace and its GasCity hosting pack. Inherits blackrim's "Working Lab Notebook" system with nimbus's own vapor-cyan accent.
colors:
  vapor: "oklch(0.76 0.15 200)"
  vapor-lift: "oklch(0.83 0.13 200)"
  vapor-deep: "oklch(0.54 0.12 204)"
  bg-dark: "oklch(0.15 0.012 215)"
  surface-dark: "oklch(0.188 0.016 214)"
  lifted-dark: "oklch(0.236 0.02 213)"
  hairline-dark: "oklch(0.31 0.018 215)"
  hairline-strong-dark: "oklch(0.42 0.026 215)"
  ink-dark: "oklch(0.975 0.006 220)"
  mute-dark: "oklch(0.745 0.026 220)"
  caption-dark: "oklch(0.57 0.03 222)"
  bg-light: "oklch(0.976 0.005 95)"
  ink-light: "oklch(0.22 0.02 215)"
  accent-light: "oklch(0.55 0.15 206)"
  signal-amber: "oklch(0.82 0.14 76)"
  signal-red: "oklch(0.68 0.2 22)"
  signal-green: "oklch(0.88 0.18 158)"
typography:
  display:
    fontFamily: "'Inter Variable', Inter, sans-serif"
    fontSize: "clamp(2.75rem, 1.6rem + 5.4vw, 5.25rem)"
    fontWeight: 600
    letterSpacing: "-0.03em"
  headline:
    fontFamily: "'Inter Variable', Inter, sans-serif"
    fontSize: "clamp(2rem, 1.3rem + 3.2vw, 3.5rem)"
    fontWeight: 600
    letterSpacing: "-0.02em"
  mono:
    fontFamily: "'JetBrains Mono Variable', monospace"
    fontSize: "15px"
  label:
    fontFamily: "'JetBrains Mono Variable', monospace"
    fontSize: "13px"
    fontWeight: 500
    letterSpacing: "0.14em"
rounded:
  none: "0"
  code: "4px"
---

# Design System: blackrim-nimbus

The nimbus site inherits the **blackrim "Working Lab Notebook"** system wholesale —
operations-room calm, evidence-first, the surface is the proof. Read
`/Users/jayse/Code/blackrim/DESIGN.md` for the full rationale; everything there holds unless
overridden below. One deliberate departure: the accent.

## The one departure: vapor cyan

Where blackrim signs with **Armada Blue** (hue ~266) and the Cockpit signs with **ignition
azure** (hue ~228), nimbus signs with **vapor cyan** (`oklch(0.76 0.15 200)`, hue ~200) — a
luminous cloud-edge cyan that reads as atmosphere, edge compute, and the instant a deploy goes
live. It carries the same single-color-of-meaning role: links, eyebrows, the hero accent line,
focus rings, the grid texture, the hero halo. The neutral ramp is re-tinted toward 215 at very
low chroma (still a tinted near-black, never `#000`).

## Carried over unchanged

- **Inter + JetBrains Mono.** Sans for argument, mono for evidence.
- **Square corners.** Radius `0` everywhere; only `<pre>`/`<code>` get 4px.
- **Hairline-driven hierarchy.** 1px borders carry structure; flat by default; hover lifts via
  `translateY(-2px)`, never shadow.
- **The `/` eyebrow.** Mono uppercase, accent color, prefixed with a `/` glyph in caption-slate.
- **Two themes.** Dark primary, light full fidelity, same accent role in both.

## Signature artifact: the golden-path deploy terminal

Blackrim's hero is a faux-but-real terminal of `gt crew` / `bd ready`; the Cockpit's is a
faux-but-real VS Code window. Nimbus's is a faux-but-real **deploy terminal** running the golden
path end to end — `npm create vite@latest`, the voidzero build (vite / rolldown / oxc),
`wrangler deploy` to Cloudflare, `npx convex deploy` — with real token coloring (vapor for
prompts + URLs, ink for command text, signal-green for the live deploy URL + status, signal-amber
for cost/region notes, caption for dim output) and a blinking vapor caret. It is the only element
that gets the reserved halo. Nothing else on the page does.

## Signature component: the cloud matrix

The 19-provider breadth renders as a connected hairline grid — one cell per provider, mono
provider label, a one-line "best for", and the golden-path trio (Cloudflare + Convex + voidzero)
marked as the lit/selected channel while the others sit available-but-recessive. Hover lights one
cell and dims the rest (the instrument-panel hover, `:has()`), mirroring blackrim's crew-card
behavior. Shared 1px hairlines, no per-cell outlines — the connected-panel feel.

## Motion

Staged hero reveal (eyebrow, headline lines, lede, deploy terminal fading up), the terminal lines
settling in sequence, a blinking vapor caret, the live-deploy pulse on the status line. Section
reveals enhance already-visible content and have a `prefers-reduced-motion` fallback. Easing
`ease-out-expo`/`quart`; no bounce.

## Layout

Multi-page, prerendered static for GitHub Pages (vite + voidzero build; Cloudflare Pages later):
`/` (landing), `/providers` (the cloud matrix in full), `/pack` (the GasCity hosting pack + golden
path). Shared sticky nav (translucent + 12px backdrop blur, brand mark + wordmark, mute to ink
links with vapor active-underline, theme toggle + GitHub ghost button) and footer. Content shell
caps at 76rem; prose at 64ch, leads 52 to 64ch, headings 14 to 26ch.
