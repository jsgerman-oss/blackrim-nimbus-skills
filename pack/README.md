# nimbus — cloud app-hosting enabler pack

`nimbus` is the city-side gascity pack that makes a gas city **app-hosting-capable**:
an agent can scaffold a new web app and deploy it end to end. It is the runnable
companion to this repo's 19 per-provider Claude Code plugins (`cloud-*/`) — those
teach Claude each cloud's well-architected defaults; this pack turns that into a
**golden path** plus **breadth** across all 19 clouds.

> **Status: v1 SCAFFOLD (`nim-bam`).** Only the structure + manifests live here.
> The CLI engine (`nim-rsa`), the golden-path skill (`nim-ulq`), the 19-provider
> curation (`nim-6y5`), and launch-quality docs/tests (`nim-114`) land in the
> follow-up beads. Read [`docs/DESIGN.md`](docs/DESIGN.md) before extending.

## What it provides

| Path | Role |
|------|------|
| `bin/nimbus` | the app-scaffold + deploy CLI (stub today; `nim-rsa`) |
| `nimbus/` | the engine (pure-stdlib; stub today; `nim-rsa`) |
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

# what is this pack, and what lands where?
./bin/nimbus info

# version (text or JSON)
./bin/nimbus version --json
```

The scaffold CLI ships only `version` and `info`. The real surface — scaffold a
new app on the golden path and deploy it to one of 19 clouds — lands in `nim-rsa`.

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
python3 -m pytest -q          # pure stdlib + pytest, no network
python3 tests/test_cli.py     # or run the smoke test standalone, without pytest
```

## License

MIT — see [LICENSE](LICENSE).
