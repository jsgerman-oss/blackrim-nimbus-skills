---
name: golden-path-hosting
description: PLACEHOLDER (nim-ulq) — reserves the convention-discovered skill slot. Will deploy a new web app on the nimbus golden path (vite + voidzero + cloudflare + convex) from zero to a live URL, with the 19 curated provider skills (cloud-*) as the escape hatch when the golden path doesn't fit. The full skill — process, worked example, verification gate — lands in nim-ulq; this file only keeps the pack's skills/ layout in place so the scaffold mirrors gascity-cockpit/pack.
---

# Golden-Path Hosting (placeholder)

> **STATUS: PLACEHOLDER (nim-bam scaffold).** The full golden-path hosting skill
> lands in **nim-ulq**. This file exists only to reserve the
> convention-discovered `skills/<name>/SKILL.md` slot so the pack's skeleton
> mirrors `gascity-cockpit/pack`. Do not rely on its contents yet.

## What this will be

The opinionated, end-to-end path for standing up and deploying a new web app on a
gas city:

- **Golden path** — vite + voidzero + cloudflare + convex: the default stack,
  scaffolded and deployed with production-grade defaults.
- **Breadth** — the 19 curated provider skills (`cloud-*`) as the escape hatch
  when the golden path doesn't fit the target cloud (curated in via nim-6y5).

## Roadmap

| Piece | Bead |
|-------|------|
| `bin/nimbus` app scaffold + deploy helpers (stdlib-only) | nim-rsa |
| This skill's full process + worked example + verification gate | nim-ulq |
| 19 provider skills curated into the pack + validator/regen wiring | nim-6y5 |
| docs/DESIGN.md + tests + README to launch quality | nim-114 |

<!-- registration -->
**Registration.** gc discovers pack skills by directory convention: a pack
contributes a skill by placing `skills/<name>/SKILL.md` under the pack root, with
YAML frontmatter carrying at minimum `name` and `description`. This file lives at
`pack/skills/golden-path-hosting/SKILL.md`, so it is picked up automatically —
`pack.toml` does not enumerate skills. Once the `nimbus` pack is imported into a
city (vendored under `packs/nimbus` and registered via a direct
`source = "packs/nimbus"` import), the skill surfaces in `gc skill list`
binding-qualified as `nimbus.golden-path-hosting`. Verify with `gc skill list`
(and `gc lint .` / `gc doctor`).
