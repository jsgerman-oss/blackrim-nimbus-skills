# nimbus pack — design & scope

> The city-side **cloud app-hosting enabler** for a gas city. This document is the
> canonical scope: what the pack is, where the golden path ends and breadth begins,
> how the engine works end to end, and what nimbus deliberately does **not** do.
> Read §4 ("Scope boundaries") before extending it.

## 1. What this pack is

`nimbus` makes a gas city **app-hosting-capable**: an agent in that city can
scaffold a new web app and take it to a live URL without re-deriving each cloud's
defaults from scratch. It is the runnable, city-side companion to this repo's 19
per-provider Claude Code plugins (`cloud-*/`). Those plugins teach Claude each
cloud's well-architected defaults (compute, storage, IaC, networking,
observability, security); this pack turns that knowledge into a **runnable scaffold
+ a deploy-readiness gate**, behind one opinionated golden path with breadth across
all 19 clouds as the escape hatch.

It does three things:

1. **Scaffolds a golden-path app** — `nimbus scaffold NAME` writes a complete
   `vite + voidzero + cloudflare + convex` project tree (React/TypeScript SPA,
   Convex reactive backend, Cloudflare Workers static-asset hosting) with
   production-grade defaults already wired.
2. **Gates the deploy** — `nimbus readiness DIR` asserts a project is ready to ship
   (required files present, deploy credentials in the environment, build/deploy
   toolchain on `PATH`) and returns a CI-usable exit code.
3. **Surfaces the breadth** — `nimbus providers` lists the golden path plus the 19
   curated clouds, for when the golden path doesn't fit the target.

Like `gascity-cockpit` and `provider-forge`, it is **pure-stdlib python** with a
**convention-discovered** layout and **no third-party runtime deps**: a CLI
(`bin/nimbus`), an engine package (`nimbus/`), and skills (`skills/`). No overlay,
no hooks, no prompt fragments.

## 2. Golden path vs. breadth

The pack's defining decision is the split between one opinionated default and a wide
escape hatch.

- **Golden path (the opinionated default):** `vite + voidzero + cloudflare +
  convex`. A new app on this stack goes from zero to a live URL with the fewest
  decisions and sane production defaults. The clean boundary that makes it work:
  **Cloudflare owns the edge** (static assets, CDN, custom domain, WAF), **Convex
  owns data + server logic + reactivity**, and **VoidZero** (Vite + Vitest +
  Rolldown + Oxc/oxlint) **owns the build** — one Rust-fast toolchain from one team,
  no toolchain drift. This is what `bin/nimbus scaffold`/`readiness` (nim-rsa) and
  the `golden-path-hosting` skill (nim-ulq) optimize for.
- **Breadth (the escape hatch):** the 19 providers curated in this marketplace —
  alibaba, aws, azure, cloudflare, digitalocean, fly, gcp, hetzner, ibm, linode,
  netlify, oci, railway, render, scaleway, supabase, tencent, vercel, vultr —
  surfaced as curated skills (nim-6y5) for when the golden path doesn't fit the
  target cloud. The engine optimizes the golden path; breadth is documentation +
  skills, not scaffold templates.

`golden.PROVIDERS` is the single source of truth for that list and is kept in sync
with the `cloud-*` plugins and the site's provider matrix.

## 3. The engine: golden → scaffold → readiness

The engine is three pure-stdlib modules with one clean data-flow. `golden.py` is to
nimbus what `contract.py` is to cockpit — the single source of truth the operation
modules build on:

| Module | Role | Cockpit analogue |
|--------|------|------------------|
| `golden.py` | the knowledge: the stack, the 19 providers, the file templates a scaffolded app gets, the deploy-readiness requirements. Pure data + render helpers — no filesystem, no network. | `contract.py` (the declared contract) |
| `scaffold.py` | the **write** side: render `golden.py` into a new project tree on disk + drop a `.nimbus.json` marker. | `discovery.write_descriptor` |
| `readiness.py` | the **read + assess** side: inspect a project dir + the environment and return a deploy-readiness verdict. | `discovery.probe_api` + `assess_readiness` |
| `cli.py` | argparse surface over the three modules; `bin/nimbus` resolves the pack venv (or system `python3`) and execs `python -m nimbus.cli`. | `cli.py` + `bin/cockpit` |

### The `.nimbus.json` marker (the data-driven seam)

`scaffold` writes a `.nimbus.json` marker into every app it generates, recording the
stack and the deploy-readiness requirements (`files` / `env` / `tools`):

```json
{
  "schema": "nimbus.v0",
  "kind": "nimbus-golden-path-app",
  "name": "myapp",
  "stack": { "build": "vite", "toolchain": "voidzero",
             "hosting": "cloudflare", "backend": "convex" },
  "provider": "cloudflare",
  "requirements": {
    "files": ["package.json", "tsconfig.json", "vite.config.ts", "index.html",
              "wrangler.toml", "convex/schema.ts"],
    "env":   ["CLOUDFLARE_API_TOKEN", "CONVEX_DEPLOY_KEY"],
    "tools": ["node", "npm", "npx"]
  }
}
```

`readiness` reads those requirements **back from the marker** (data-driven) rather
than re-deriving them, and falls back to the `golden.py` defaults for a directory
without a marker. This keeps the scaffold and the checker in lock-step: the app
itself carries what "ready" means for it.

### A worked walk-through

```bash
# 1. scaffold a golden-path app into ./myapp/
nimbus scaffold myapp
#    -> writes package.json, tsconfig.json, vite.config.ts, index.html,
#       src/{main,App}.tsx, convex/{schema,tasks}.ts, wrangler.toml,
#       .env.example, .gitignore, README.md, + the .nimbus.json marker

# 2. wire it up (the skill drives the deploy; nimbus does not run it)
cd myapp && npm install && npx convex dev    # creates the dev deployment

# 3. gate the deploy — files? creds in env? toolchain on PATH?
nimbus readiness .
#    DEPLOY-READY            -> exit 0  (ship it)
#    NOT deploy-ready (...)  -> exit 1  (something is missing; it says what)
#    NO SUCH DIRECTORY       -> exit 2  (bad path)
```

`readiness`'s exit code is the contract that lets it slot into a deploy script as a
gate (`nimbus readiness . && npm run deploy`). The credential check reads the
**environment** — secrets are never read from disk and never committed.

## 4. Scope boundaries

nimbus ships the honest groundwork for app hosting and stops at three deliberate
edges. Each is a non-goal by design, not a gap.

### 4.1 — nimbus scaffolds and gates; it does **not** run the deploy

The pack writes the project and asserts readiness. It does **not** shell out to
`npm`, `wrangler`, or `convex` — running the deploy is the agent's/operator's job,
guided by the `golden-path-hosting` skill (nim-ulq). This keeps the engine pure
(hermetic, no network, fully testable without a cloud account) and keeps the
side-effecting, credentialed steps where a human or a skilled agent can see them.
`readiness` is the seam between the two: scaffold on one side, the real deploy on the
other, with a CI-usable gate in between.

### 4.2 — readiness is a static check, not a live cloud probe

`readiness` asserts that the deploy **credentials are present and non-empty in the
environment** and that the **toolchain is on `PATH`** — it does **not** call
Cloudflare or Convex to validate that a token is live or correctly scoped. That is
deliberate: the check stays hermetic, offline, and instant, so it is safe in CI and
in tests. Validating a token against the live API is the deploy step's failure mode
to surface, not the gate's.

### 4.3 — breadth is curated skills, not 19 scaffolds

The engine optimizes exactly one stack. The other 18 providers are surfaced as
**documentation + curated skills** (nim-6y5), not as alternative scaffold templates.
`nimbus providers` lists them and marks the golden provider; choosing a non-golden
cloud means dropping into that cloud's `cloud-*` skill, not `nimbus scaffold
--provider=aws`. Adding a second first-class scaffold stack would be a new bead with
its own golden-path rationale — not a flag on this one.

### 4.4 — pinned versions, advanced deliberately

`golden.py` pins the dependency version ranges and the wrangler `compatibility_date`
stamped into generated apps. They are pinned (not floated) so a scaffold is
reproducible and there is exactly one place to bump them; advancing them is a
deliberate edit kept in step with the `golden-path-hosting` skill, not an automatic
follow-the-latest.

## 5. Relationship to sibling beads

This pack was built across a small epic. Current status:

- `nim-bam` *(closed)* — scaffold the pack structure + manifests, mirroring
  `gascity-cockpit/pack`.
- `nim-rsa` *(closed)* — the `bin/nimbus` engine: `golden` + `scaffold` +
  `readiness` and the `version`/`info`/`scaffold`/`readiness`/`providers` CLI.
- `nim-ulq` *(closed)* — the `golden-path-hosting` skill: the full deploy process,
  worked example, and anti-patterns (vite + voidzero + cloudflare + convex).
- `nim-6y5` *(open)* — curate the 19 provider skills into the pack + wire the
  validator/regen. The breadth half of §2; the `providers` list already names them.
- `nim-114` *(this bead)* — bring `docs/DESIGN.md` + tests + `README.md` to launch
  quality, aligned with the repo brand.

## 6. Deployment

This pack lives in the `blackrim-nimbus-skills` repo under `pack/`. To deploy it into
a city, **vendor `pack/` into the target city as `packs/nimbus/`** (copy or clone)
and run the installer:

```bash
packs/nimbus/install.sh --town            # city-wide
packs/nimbus/install.sh --rig <name>      # one rig
packs/nimbus/install.sh --town --dry-run  # preview
```

`install.sh` records a direct `source = "packs/nimbus"` import (the gastown pattern),
`gc reload`s, and verifies the install (`gc lint`, the import is registered, and a
`bin/nimbus version` smoke). Reverse it with `uninstall.sh` (same scope flags;
`--purge` also drops the engine venv). `setup.sh` builds the optional self-contained
venv; because the engine is pure-stdlib, `bin/nimbus` also runs under any system
`python3` with no venv at all.

## 7. Testing

Tests live under `tests/` (pytest, pure stdlib, **no network**). The testable seam is
the **engine/CLI contract**, not any external glue — every test runs offline against
injected inputs. The suite covers all four modules:

- **golden** (`test_golden.py`) — the name validator (incl. path-traversal
  rejection), the 19-provider breadth, that rendered files parse, that
  `REQUIRED_FILES` is a subset of what `scaffold` writes (so a fresh scaffold can
  never report a "missing" required file), that `STACK_ORDER` covers the stack, and
  that the marker payload is internally consistent.
- **scaffold** (`test_scaffold.py`) — a fresh scaffold lays down the full tree + the
  marker; an invalid name raises before touching disk; a non-empty target is refused
  unless `force=True`; `force` overlays without clobbering unrelated files.
- **readiness** (`test_readiness.py`) — a complete scaffold with creds + toolchain is
  ready; each missing dimension (file / env / tool) flips it not-ready and is
  reported; a malformed marker is ignored; requirements are read data-driven from the
  marker when present, else from the golden defaults. `env` and `which` are injected
  so the suite is fully hermetic.
- **cli** (`test_cli.py`) — the exit-code state machine (`readiness` 0/1/2,
  `scaffold` 1 on bad name / clobber), text **and** JSON rendering of every command,
  and a bare invocation that prints help instead of erroring. The fixture-free subset
  also runs standalone via `python3 tests/test_cli.py`.
- **wrapper** (`test_bin.py`) — a subprocess smoke of the real `bin/nimbus`
  executable: it resolves an interpreter, sets `PYTHONPATH`, and `version`/`info`
  answer — the one seam the in-process tests can't reach.

Run the full suite with `python3 -m pytest -q`. The `bin/nimbus version` smoke that
`install.sh` runs is the live-install analogue: if the wrapper-to-engine wiring
drifts, the install fails loudly.
