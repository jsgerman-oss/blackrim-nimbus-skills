# nimbus pack — design & scope (stub)

> **STATUS: v1 SCAFFOLD (nim-bam).** This is a *stub*. It records enough design
> intent to make the scaffold coherent and to scope the follow-up beads. It is
> brought to launch quality — sharpened scope, scope forks (if any), worked
> deployment walk-through — in **nim-114**. Read it before extending the pack,
> but expect it to grow.

## 1. What this pack is

`nimbus` is the **cloud app-hosting enabler** for a gas city. It makes a city
*app-hosting-capable*: an agent in that city can scaffold a new web app and deploy
it, end to end, without re-deriving each cloud's defaults from scratch.

It is the city-side companion to this repo's per-provider Claude Code plugins
(`cloud-*/`). Those plugins teach Claude each cloud's well-architected defaults
(compute, storage, IaC, networking, observability, security). This pack turns that
knowledge into a **runnable scaffold + deploy workflow**: one opinionated golden
path, plus breadth across all 19 providers as an escape hatch.

Like `gascity-cockpit` and `provider-forge`, it is **pure-stdlib python**, with a
**convention-discovered** layout and **no third-party runtime deps**: a CLI
(`bin/nimbus`), an engine module (`nimbus/`), and skills (`skills/`). No overlay,
no hooks, no prompt fragments.

## 2. Golden path vs. breadth

- **Golden path (the opinionated default):** `vite + voidzero + cloudflare +
  convex`. A new app on this stack should go from zero to a live URL with sane
  production defaults and the fewest decisions. This is what the
  `golden-path-hosting` skill (nim-ulq) and the `bin/nimbus` scaffold/deploy
  helpers (nim-rsa) optimize for.
- **Breadth (the escape hatch):** the 19 providers curated in this marketplace —
  alibaba, aws, azure, cloudflare, digitalocean, fly, gcp, hetzner, ibm, linode,
  netlify, oci, railway, render, scaleway, supabase, tencent, vercel, vultr —
  surfaced as curated skills (nim-6y5) for when the golden path doesn't fit the
  target cloud.

## 3. Layout

```
pack/
  pack.toml                     pack manifest ([pack] name/schema/version)
  bin/nimbus                    venv-resolving CLI wrapper -> python -m nimbus.cli
  nimbus/                       pure-stdlib engine (__init__.py + cli.py)
  skills/golden-path-hosting/   golden-path deploy skill (placeholder; nim-ulq)
  docs/DESIGN.md                this document
  tests/                        pytest smoke tests (pure stdlib, no network)
  setup.sh                      build the engine venv (idempotent)
  install.sh / uninstall.sh     reversible, idempotent import lifecycle
  requirements.txt              minimal (stdlib-only; guarded tomli fallback)
  README.md / LICENSE
```

This mirrors `gascity-cockpit/pack`. The nimbus pack deliberately does **not**
ship a `contract/` directory or `contract.py`/`discovery.py` — those are
cockpit-specific (the `/v0` API compatibility gate). nimbus's own engine modules
(app scaffold + deploy helpers) land in nim-rsa.

## 4. Deployment

This pack lives in the `blackrim-nimbus-skills` repo under `pack/`. To deploy it
into a city, **vendor `pack/` into the target city as `packs/nimbus/`** (copy or
clone) and run `packs/nimbus/install.sh --town` (or `--rig <name>`). `install.sh`
records a direct `source = "packs/nimbus"` import (the gastown pattern), `gc
reload`s, and verifies (`gc lint`, import registered, `bin/nimbus version` smoke).
Reverse with `uninstall.sh` (same scope flags; `--purge` to drop the venv).

## 5. Relationship to sibling beads

- `nim-bam` — this scaffold (structure + manifests only).
- `nim-rsa` — `bin/nimbus` app scaffold + deploy helpers (stdlib-only): the
  engine that turns this skeleton into a working CLI.
- `nim-ulq` — the golden-path hosting skill (vite + voidzero + cloudflare +
  convex): the full process, worked example, and verification gate.
- `nim-6y5` — curate the 19 provider skills into the pack + wire validator/regen.
- `nim-114` — bring `docs/DESIGN.md` + tests + README to launch quality.

## 6. Testing

Tests live under `tests/` (pytest, pure stdlib, no network), mirroring the
cockpit pack's testable-seam approach: the engine/CLI contract is the seam, not
any external glue. The scaffold ships a CLI smoke test (`test_cli.py`); the
deploy-engine and golden-path tests grow alongside nim-rsa / nim-ulq, and nim-114
brings the suite to launch quality.
