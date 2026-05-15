---
name: fly-iac-and-deployment
description: Design or audit Fly.io infrastructure-as-code and deployment — flyctl CLI, fly.toml configuration, deploy strategies (immediate/rolling/bluegreen/canary), GitHub Actions with superfly/flyctl-actions, machine pinning via the Machines API, Pulumi flyio/fly provider, multi-region deploys. Use when setting up a deployment pipeline, reviewing fly.toml structure, or choosing a deploy strategy.
---

# Fly IaC and Deployment

## When to use

- Designing a CI/CD pipeline for a Fly-hosted application.
- Writing or reviewing a `fly.toml` configuration.
- Choosing between deploy strategies for a service.
- Setting up GitHub Actions for automated deployment.
- Scripting multi-region machine configuration via the Machines API.
- Evaluating the Pulumi `flyio/fly` provider for infrastructure management.

## `flyctl` — the primary interface

`flyctl` (alias: `fly`) is the canonical CLI and the primary IaC surface for Fly. As of flyctl ≥ 0.3.x:

- `fly deploy` — build and deploy an app from source or a pre-built image.
- `fly machine run` — launch an ephemeral or long-running machine directly.
- `fly machine update` — update machine config (size, env, image) without a full deploy.
- `fly releases` — list and manage releases.
- `fly scale` — adjust machine count and size.
- `fly ssh` — interactive shell into a machine.
- `fly postgres`, `fly redis`, `fly storage` — manage attached services.

**Version-pin `flyctl` in CI.** Fly moves fast; pin a specific version in your GitHub Actions workflow to avoid surprise breakage.

## `fly.toml` — configuration-as-code

`fly.toml` is the app's configuration file. It is version-controlled alongside the application code. It defines services, environment variables, health checks, mount points, deploy strategy, and resource constraints.

**v2 format is required** as of flyctl 0.1.x. Use `fly config show` to validate the format.

### Annotated `fly.toml` example

```toml
# fly.toml — v2 format

app = "myapp"
primary_region = "iad"

[build]
  dockerfile = "Dockerfile"

[env]
  # Non-sensitive config only. Secrets go in fly secrets.
  PORT = "8080"
  LOG_LEVEL = "info"
  FLY_APP_NAME = "myapp"

[deploy]
  strategy = "rolling"    # or "bluegreen", "canary", "immediate"
  release_command = "python manage.py migrate"  # Run before new machines start

[[vm]]
  size = "shared-cpu-2x"
  memory = "512mb"

[http_service]
  internal_port = 8080
  force_https = true
  auto_stop_machines = "stop"
  auto_start_machines = true
  min_machines_running = 1

  [http_service.concurrency]
    type = "requests"
    hard_limit = 200
    soft_limit = 150

[[http_service.checks]]
  grace_period = "10s"
  interval = "15s"
  method = "GET"
  path = "/healthz"
  timeout = "5s"

[mounts]
  source = "myapp_data"
  destination = "/data"

[[metrics]]
  port = 9091
  path = "/metrics"    # Prometheus-compatible endpoint for Fly to scrape
```

### Key `fly.toml` fields explained

- **`primary_region`**: the region where Fly creates the first machine on `fly deploy`. For multi-region, this is your "home" region.
- **`[deploy] release_command`**: runs in a temporary machine before new machines start. Use for database migrations. If it exits non-zero, the deploy aborts.
- **`auto_stop_machines = "stop"`**: Fly Proxy stops machines with no active connections. `"suspend"` preserves memory. `false` disables.
- **`[http_service.concurrency]`**: tells Fly Proxy how many concurrent requests a machine handles before spinning up another. Tune to your app's measured capacity.
- **`[[metrics]]`**: Fly scrapes this endpoint and surfaces it in the built-in Grafana dashboard.

## Deploy strategies

### Choosing a strategy

| Strategy | `fly.toml` value | When to use |
| --- | --- | --- |
| `rolling` | `"rolling"` | Default. Stateless services. One machine at a time; minimizes downtime. |
| `bluegreen` | `"bluegreen"` | Zero-downtime for user-facing services. Spins up a full new set, then cuts traffic. Peak cost doubles during deploy. |
| `canary` | `"canary"` | Deploy to 1 machine first; watch health checks; roll out if healthy. Catches startup regressions. |
| `immediate` | `"immediate"` | Dev/staging only. Replace all machines at once. Brief unavailability if the image is slow to start. |

### Release command for migrations

Use `release_command` to run database migrations atomically with the deploy:

```toml
[deploy]
  release_command = "python manage.py migrate --noinput"
  strategy = "rolling"
```

Fly runs the release command in a new temporary machine. If it fails, the deploy aborts before touching running machines. This is the safe default for migration-bearing deploys.

**Gotcha:** the release machine has the new image but connects to the same database as the running machines. Write migrations that are backward-compatible with the previous image (add nullable columns, do not drop / rename columns in the same release as the app code that reads them).

## GitHub Actions — CI/CD pipeline

The canonical GitHub Actions setup uses `superfly/flyctl-actions`:

```yaml
# .github/workflows/deploy.yml

name: Deploy to Fly

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    concurrency:
      group: ${{ github.workflow }}-${{ github.ref }}
      cancel-in-progress: true

    steps:
      - uses: actions/checkout@v4

      - name: Setup flyctl
        uses: superfly/flyctl-actions/setup-flyctl@master
        with:
          version: "0.3.35"    # Pin the version

      - name: Deploy
        run: fly deploy --strategy bluegreen --remote-only
        env:
          FLY_API_TOKEN: ${{ secrets.FLY_API_TOKEN }}
```

**`FLY_API_TOKEN` must be a deploy token**, not an org token. Create it with:

```bash
fly tokens create deploy -a myapp --expiry 720h -n "github-actions-main"
```

Store it as a GitHub Actions secret (`FLY_API_TOKEN`). Rotate it when it expires or on any security event.

### `--remote-only` flag

`fly deploy --remote-only` builds the Docker image on Fly's remote builder instead of locally in the CI runner. This avoids transferring large layer caches in CI and leverages Fly's layer cache. Prefer this unless the build has a specific local dependency.

### Per-environment deploy strategy

```yaml
# Deploy to staging on PRs
- name: Deploy staging
  run: fly deploy -a myapp-staging --strategy rolling --remote-only

# Deploy to production on main merge
- name: Deploy production
  run: fly deploy -a myapp-prod --strategy bluegreen --remote-only
```

## Machines API — direct machine management

For advanced use cases (ephemeral machines, on-demand job runners, fine-grained multi-region control), use the Machines REST API directly:

```bash
# Create a machine in ams (Amsterdam)
curl -X POST \
  -H "Authorization: Bearer $FLY_API_TOKEN" \
  -H "Content-Type: application/json" \
  "https://api.machines.dev/v1/apps/myapp/machines" \
  -d '{
    "config": {
      "image": "registry.fly.io/myapp:sha-abc123",
      "size": "shared-cpu-2x",
      "env": {"REGION_ROLE": "worker"}
    },
    "region": "ams"
  }'
```

Use cases: batch job machines that start on a trigger and stop when done, A/B test machines with different configs, region-specific machine pinning.

## Multi-region deploys

`fly deploy` by default places machines in `primary_region`. For multi-region:

```bash
# Scale to 2 machines in iad, 1 in lhr, 1 in nrt
fly scale count 2 --region iad
fly scale count 1 --region lhr
fly scale count 1 --region nrt
```

Or use `fly.toml` with a `[[regions]]` block (experimental as of 2025 — check docs for GA status).

For write routing in multi-region stateful apps: configure `fly-replay` headers (see `fly-networking-and-edge`) to route writes to the primary region.

## Pulumi `flyio/fly` provider

The `flyio/fly` Pulumi provider (community, not official Fly) supports:

- Fly Apps, Machines, Volumes, IP allocation.
- Fly Postgres cluster creation.
- Limited support for secrets (Fly secrets require `fly` CLI for value injection).

As of May 2026, the provider lags behind Fly's API surface. For production IaC, prefer `fly.toml` + `flyctl` in CI, supplemented by Pulumi for resources the provider covers. Do not assume Pulumi coverage for newer Fly features without verifying the provider version.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Org token in GitHub Actions secrets | A repo-scoped deploy token is the correct scope. Org token gives full account access. |
| `fly deploy` from a developer laptop for production | No audit trail, no pipeline-enforced checks. Production deploys must go through CI. |
| Unpinned flyctl version in CI | Fly CLI updates can change `fly.toml` behavior or flag semantics. Pin and update deliberately. |
| Non-backward-compatible migrations in the same release | If old machines run alongside new ones during rolling deploy, the old code breaks on the new schema. |
| `strategy = "immediate"` in production | Brief total downtime on every deploy. Use `rolling` or `bluegreen` for user-facing services. |
| No `release_command` for migration-bearing deploys | Migrations run after machines start; old machines see new schema before the migration runs on all nodes. |
| Image tagged `:latest` | Rollback is guessing. Pin images by git SHA (`fly deploy --image registry.fly.io/myapp:sha-abc123`). |

## Defaults — release pipeline

- Trunk-based development. Feature branches merged to main; main deploys to production.
- PR deploys to a staging app via `fly deploy -a myapp-staging`.
- Production deploy on main merge via GitHub Actions with a deploy token.
- Images tagged with git SHA. `:latest` never used in production.
- `release_command` for any migration-bearing deploy.
- `--strategy bluegreen` for production. `--strategy rolling` for staging.
- `fly releases` checked after every deploy; confirm the new release is healthy before closing the deploy PR.
- Rollback: `fly releases rollback <version>` or `fly deploy --image <prev-sha>`. Test the rollback path quarterly.

## Cost considerations

- `bluegreen` deploys momentarily double machine count during cutover. Budget for the peak.
- Remote builds consume Fly builder machine time. Large images with slow builds may benefit from Docker layer optimization.
- Pulumi state is stored externally (Pulumi Cloud or S3 + DynamoDB for self-hosted); small cost.
- Ephemeral machines via the Machines API are billed for their runtime. Clean up promptly on job completion.

## IaC hints

- `fly.toml` is the source of truth. Never modify app config via the dashboard for production; use `fly.toml` + deploy.
- `fly config validate` checks `fly.toml` syntax before deploy.
- `fly config show --json` exports current live config for diff-ing against the expected `fly.toml`.
- For secrets in IaC bootstrap: write a `scripts/bootstrap-secrets.sh` that pulls from a secrets manager (1Password CLI, HashiCorp Vault, AWS Secrets Manager) and pushes to `fly secrets` on first deploy.

## Verification checklist

- [ ] `fly.toml` committed to source control; production deploys run from CI only.
- [ ] `FLY_API_TOKEN` is a deploy token with expiry; stored as a GitHub Actions secret.
- [ ] flyctl version pinned in GitHub Actions workflow.
- [ ] Deploy strategy matches downtime tolerance: `bluegreen` or `rolling` for production.
- [ ] `release_command` defined for migration-bearing deploys; backward-compatible migrations verified.
- [ ] Images tagged by git SHA; `:latest` is absent from production references.
- [ ] Rollback procedure documented and tested.
- [ ] Multi-region write routing configured (`fly-replay`) for stateful apps.
- [ ] Staging environment receives every deploy before production.
