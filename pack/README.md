# nimbus — cloud app-hosting enabler pack

`nimbus` is the city-side gascity pack that makes a gas city **app-hosting-capable**:
an agent can scaffold a new web app and deploy it end to end. It is the runnable
companion to this repo's 19 per-provider Claude Code plugins (`cloud-*/`) — those
teach Claude each cloud's well-architected defaults; this pack turns that into a
**golden path** plus **breadth** across all 19 clouds.

> **Status:** the CLI engine landed (`nim-rsa`) — `scaffold` / `readiness` /
> `providers` work. The golden-path skill (`nim-ulq`), the 19-provider curation
> (`nim-6y5`), and launch-quality docs/tests (`nim-114`) land in the follow-up
> beads. Read [`docs/DESIGN.md`](docs/DESIGN.md) before extending.

## What it provides

| Path | Role |
|------|------|
| `bin/nimbus` | the app-scaffold + deploy-readiness CLI (`nim-rsa`) |
| `nimbus/` | the pure-stdlib engine: `golden` + `scaffold` + `readiness` (`nim-rsa`) |
| `skills/golden-path-hosting/` | the golden-path deploy skill (placeholder; `nim-ulq`) |
| `docs/DESIGN.md` | the pack's design + scope (stub; `nim-114`) |

- **Golden path:** vite + voidzero + cloudflare + convex.
- **Breadth:** 19 providers — alibaba, aws, azure, cloudflare, digitalocean, fly,
  gcp, hetzner, ibm, linode, netlify, oci, railway, render, scaleway, supabase,
  tencent, vercel, vultr — curated as skills (`nim-6y5`).

Stdlib-only (`tomllib` ≥3.11 / `tomli` fallback). No overlay, no hooks, no prompt
fragments — mirrors `gascity-cockpit` / `provider-forge`'s minimal footprint.

## Quickstart

```bash
# (optional) build the engine venv; bin/nimbus also runs under any system python3
./setup.sh

# what is this pack, and what does it do?
./bin/nimbus info

# the golden path + the 19 curated clouds (the breadth escape hatch)
./bin/nimbus providers

# scaffold a new golden-path app into ./myapp/
./bin/nimbus scaffold myapp

# is a scaffolded app ready to deploy? (files + creds + toolchain)
./bin/nimbus readiness ./myapp
```

### Commands

| Command | What it does |
|---------|--------------|
| `nimbus version [--json]` | print the pack version |
| `nimbus info [--json]` | pack identity, the golden path, and the remaining roadmap |
| `nimbus scaffold NAME [--dir DIR] [--force] [--json]` | scaffold a golden-path app (vite + voidzero + cloudflare + convex) into `DIR/NAME` (default `DIR` = cwd; `--force` to write into a non-empty dir) |
| `nimbus readiness [DIR] [--json]` | check a scaffolded app's deploy readiness — required files present, deploy creds (`CLOUDFLARE_API_TOKEN`, `CONVEX_DEPLOY_KEY`) in the environment, and the `node`/`npm`/`npx` toolchain on PATH |
| `nimbus providers [--json]` | list the golden path + the 19 curated cloud providers |

`readiness` exits `0` when deploy-ready, `1` when something is missing, and `2`
when the directory does not exist — so it slots into a deploy script's gate.

A scaffolded app drops a `.nimbus.json` marker recording the stack and its
deploy-readiness requirements; `readiness` reads it back (and falls back to the
golden defaults for a dir without one).

## Install into a city

Vendor `pack/` into the target city as `packs/nimbus/`, then:

```bash
packs/nimbus/install.sh --town            # city-wide
packs/nimbus/install.sh --rig <name>      # one rig
packs/nimbus/install.sh --town --dry-run  # preview
```

This registers a direct `source = "packs/nimbus"` import (the gastown pattern),
`gc reload`s, and verifies (`gc lint`, import registered, `bin/nimbus version`
smoke). Reverse with `uninstall.sh` (same scope flags; `--purge` to drop the venv).

## Tests

```bash
python3 -m pytest -q          # full suite: cli + golden + scaffold + readiness (no network)
python3 tests/test_cli.py     # or the fixture-free CLI smoke subset, standalone
```

## License

MIT — see [LICENSE](LICENSE).
