---
name: render-blueprints-and-deployment
description: Design or audit Render Blueprints and deployment — render.yaml Blueprint IaC (the recommended path), PR Preview environments, build / start commands, build caching, secret env var management, render-cli, Terraform render-oss/render provider, GitHub / GitLab integration. Use when setting up a new Blueprint, configuring preview environments, or reviewing a deployment pipeline.
---

# Render Blueprints and Deployment

## When to use

- Creating a `render.yaml` Blueprint for a new project.
- Adding PR Preview environments to an existing Blueprint.
- Reviewing a Blueprint for security and correctness before launch.
- Setting up a GitHub Actions CI pipeline that integrates with Render deploys.
- Deciding between Render's GitHub integration and image-based deploys for a CI pipeline.
- Using the `render` CLI for local development or scripted operations.

## Blueprints — `render.yaml`

A `render.yaml` file at the root of your repository (or a path you specify) declares your entire Render infrastructure: services, databases, environment variable groups, and preview configuration. It is the recommended path for any team that wants reproducible, auditable deployments.

### File structure

```yaml
# render.yaml — annotated template

services:
  - type: web          # web | pserv | worker | cron | static
    name: my-api
    runtime: node      # node | python | ruby | go | rust | docker
    plan: standard
    region: oregon
    branch: main
    buildCommand: npm ci
    startCommand: node server.js
    healthCheckPath: /health
    autoscaling:
      minInstances: 1
      maxInstances: 5
      criteria:
        cpu:
          enabled: true
          percentage: 70
        memory:
          enabled: true
          percentage: 80
    envVars:
      - fromGroup: prod-secrets
      - key: NODE_ENV
        value: production
    domains:
      - my-api.example.com

  - type: worker
    name: my-worker
    runtime: node
    plan: starter
    region: oregon
    branch: main
    buildCommand: npm ci
    startCommand: node worker.js
    envVars:
      - fromGroup: prod-secrets

  - type: cron
    name: nightly-report
    runtime: node
    plan: starter
    region: oregon
    schedule: "0 2 * * *"   # Cron expression (UTC)
    buildCommand: npm ci
    startCommand: node scripts/report.js
    envVars:
      - fromGroup: prod-secrets

databases:
  - name: my-postgres
    databaseName: myapp
    plan: standard
    region: oregon
    ipAllowList: []   # Empty = allow all; restrict to private network in prod if possible

  - name: my-redis
    plan: starter
    region: oregon

previews:
  generation: automatic        # automatic | manual
  previewPlan: starter
  previewsExpireAfterDays: 7   # Delete preview environments after 7 days
```

### Key rules

1. **Region consistency**: set the same `region:` on all services and databases. Cross-region service-to-service calls work, but Private Service discovery (`http://<name>:<port>`) is region-scoped.
2. **No plaintext secrets**: use `fromGroup:` to reference Environment Groups. Never use `value: "secret"` for any credential.
3. **Plan in code**: setting `plan:` in `render.yaml` means the plan is not accidentally changed via the dashboard. Dashboard changes to managed Blueprint fields are overwritten on the next deploy.
4. **Autoscaling bounds**: always set `minInstances` and `maxInstances` explicitly. Without `maxInstances`, a traffic spike can create unbounded replicas and an unexpected bill.
5. **Health check path**: required for zero-downtime deploys. Set a path that reflects real readiness (e.g. confirms database connectivity), not just process liveness.

## PR Preview environments

The `previews:` block enables automatic ephemeral environments for every pull request. Each preview gets its own set of services (web, worker, cron) and databases, isolated from production and staging.

```yaml
previews:
  generation: automatic
  previewPlan: starter      # Cheaper plan for ephemeral previews
  previewsExpireAfterDays: 7
```

**How it works:**

1. A PR is opened against the branch configured in `branch:`.
2. Render automatically provisions a new environment from the Blueprint using `previewPlan`.
3. The PR gets a preview URL (e.g. `my-api-pr-42.onrender.com`).
4. When the PR is closed or `previewsExpireAfterDays` is reached, the environment is deleted.

**Database isolation in previews**: by default, preview databases are separate instances. Never let preview environments point at production databases — verify this in the Blueprint.

**Cost control**: set `previewsExpireAfterDays` to a finite value. Without it, preview environments persist until manually deleted and accumulate charges at `previewPlan` rate per service.

## Build and start commands

Render runs `buildCommand` once (at deploy time), then `startCommand` for the running process.

**Build caching:**

Render supports build caching for:
- Node.js: `node_modules` directory is cached between builds if `package.json` has not changed.
- Python: pip packages cached if `requirements.txt` has not changed.
- Docker: layer cache (Docker layer caching) is available and on by default.
- Go module cache.

Enable caching aggressively — build time directly affects deploy frequency and build minute consumption.

**Dockerfile-based builds:**

When `runtime: docker` is set, Render builds your `Dockerfile`. Best practices:
- Use multi-stage builds to keep the final image small.
- Copy `package.json` (or equivalent) and install dependencies before copying application code — this maximizes Docker layer cache hits.
- Set `dockerfilePath:` if the Dockerfile is not at the repo root.
- Set `dockerContext:` if the build context should be a subdirectory.

## Secret environment variable management

In `render.yaml`, there are two safe ways to inject secrets:

1. **Environment Group reference (`fromGroup:`)**: the group's variables are resolved at runtime; values are not stored in the Blueprint.
2. **`generateValue: true`**: Render generates a random value for the variable (useful for `SECRET_KEY_BASE`, session keys, etc.) on first deploy and reuses it thereafter.

Unsafe pattern to avoid:

```yaml
# BAD — never do this
envVars:
  - key: DATABASE_URL
    value: postgres://user:password@host/db
```

For non-secret configuration (e.g. `NODE_ENV=production`, `PORT=3000`), using `value:` is fine — the key is not a credential.

## render-cli

The `render` CLI (≥ 1.x) provides local access to Render's API:

```bash
# Install
brew install render

# Authenticate
render login

# Deploy a service
render deploy <service-id>

# Tail logs
render logs <service-id>

# List services
render services list

# Run a one-off command in a running service's environment
render ssh <service-id>   # opens a shell
```

**CI/CD usage:**

Use the Render API or CLI in GitHub Actions to trigger a deploy after an external CI build completes (e.g. after building and pushing an image to GHCR):

```yaml
# .github/workflows/deploy.yml
- name: Trigger Render deploy
  env:
    RENDER_API_KEY: ${{ secrets.RENDER_API_KEY }}
  run: |
    curl -X POST "https://api.render.com/v1/services/$SERVICE_ID/deploys" \
      -H "Authorization: Bearer $RENDER_API_KEY" \
      -H "Content-Type: application/json" \
      -d '{"clearCache": false}'
```

## Terraform provider

The community-maintained `render-oss/render` Terraform provider supports creating and managing Render services and databases as IaC:

```hcl
terraform {
  required_providers {
    render = {
      source  = "render-oss/render"
      version = "~> 1.0"
    }
  }
}

resource "render_web_service" "api" {
  name    = "my-api"
  plan    = "standard"
  region  = "oregon"
  # ... other fields
}
```

**Limitations as of 2026-05:**

- Coverage is less complete than `render.yaml` — some Blueprint features (autoscaling, `previews:` block) may not be available in the Terraform provider.
- The community provider is not maintained by Render Inc.; check the provider changelog before adopting for production.
- For most teams, `render.yaml` (Blueprint) + GitHub integration is the better IaC path. Use Terraform only if you need to manage Render resources alongside other cloud providers in a single Terraform workspace.

## GitHub / GitLab integration

Render connects to GitHub or GitLab to:

- Auto-deploy on push to the configured `branch:`.
- Build PR Previews from pull requests.
- Receive commit status feedback (pass/fail) on deploys.

**Integration nuances:**

- Render deploys trigger on **every push** to the configured branch, including `git push --force` and rebases. Use branch protection rules in GitHub to prevent force-pushes to your deploy branch.
- Deploy order is not guaranteed within a single push containing multiple commits — the latest commit SHA is what gets deployed.
- If you need to gate Render deploys on external CI (e.g. pass test suite before deploy), use the Render API trigger approach (CI calls Render API after passing) rather than relying on the GitHub integration auto-deploy.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| No `render.yaml` (console-only setup) | Config drift between environments; no code review for infrastructure changes; reprovisioning is manual. |
| Plaintext `value:` for credentials in `render.yaml` | Credential committed to source control; anyone with repo access has the secret. Use `fromGroup:`. |
| No `previewsExpireAfterDays` set | Preview environments accumulate indefinitely; unexpected billing. |
| `maxInstances` not set on autoscaled services | Uncapped scale-out; runaway bill during traffic spikes or DDoS. |
| Relying on auto-deploy for production without a CI gate | A broken commit deploys immediately to production. Add a CI workflow that tests before triggering the Render deploy. |
| Different regions across services and their databases | Cross-region database calls add latency; Private Service discovery breaks. Use the same `region:` for all resources in an environment. |
| Building secrets into Docker image as build args | Secrets appear in `docker history` and image layers. Pass secrets at runtime via Environment Groups. |
| Terraform provider for Render without verifying coverage | Missing features cause `terraform apply` to produce incomplete infrastructure. Verify provider support for each feature before adopting. |

## Defaults

- `render.yaml` at repo root; all environments use the same Blueprint with `branch:` per environment.
- `previewsExpireAfterDays: 7` — preview environments expire automatically.
- `healthCheckPath: /health` on every Web Service.
- `autoscaling.minInstances: 1` and explicit `maxInstances` on Standard+ services.
- `fromGroup:` for all credentials; `generateValue: true` for generated secrets.
- Docker layer caching on by default — structure Dockerfiles to maximize cache hits.

## IaC hints

- Run `render validate` (if the CLI supports it) or use the Render API to validate a Blueprint before deploying.
- Use per-branch `branch:` to separate prod (`main`) and staging (`staging`) environments from the same Blueprint.
- Use `sync: false` on environment variables that should be set once and not overwritten by Blueprint syncs (e.g. a generated secret that should not be regenerated on every deploy).

## Verification checklist

- [ ] `render.yaml` exists at repo root and declares all services, databases, and preview configuration.
- [ ] No plaintext credentials in `render.yaml`; all secrets use `fromGroup:` or `generateValue: true`.
- [ ] `previews:` block includes `previewsExpireAfterDays:` set to a finite value.
- [ ] `maxInstances` set explicitly on all autoscaled services.
- [ ] `healthCheckPath` set on all Web Services and Private Services.
- [ ] Same `region:` used for all services and databases in an environment.
- [ ] CI pipeline tests pass before Render deploy is triggered (API-trigger pattern for production).
- [ ] Dockerfile structured for layer cache efficiency (dependencies before source code).
- [ ] Branch protection rules prevent force-push to the deploy branch in GitHub / GitLab.
- [ ] Preview environments tested at least once per PR before merge to staging / main.
