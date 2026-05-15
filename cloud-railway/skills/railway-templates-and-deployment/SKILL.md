---
name: railway-templates-and-deployment
description: Design or audit Railway deployment configuration — `railway.json` / `railway.toml` (build and deploy config), Railway CLI (≥ 3.x), Railway Templates (publishing and consuming), GitHub Actions integration with project tokens, environment promotion (dev → staging → production), preview environments (PR-based), and Volumes lifecycle in deploys. Use when configuring a deployment pipeline, publishing a Template, setting up preview environments, or promoting between environments.
---

# Railway Templates and Deployment

## When to use

- Writing or reviewing `railway.json` or `railway.toml` for a service.
- Setting up a GitHub Actions workflow to deploy to Railway on push or merge.
- Creating or consuming a Railway Template.
- Designing an environment promotion workflow (dev → staging → production).
- Configuring PR-based preview environments.
- Understanding how Volumes behave across deploys, re-deploys, and environment promotions.

## `railway.json` and `railway.toml` — the config layer

Railway reads two config files:

| File | Scope | Committed to repo? |
| --- | --- | --- |
| `railway.json` | Project-wide defaults, single service config | Yes |
| `railway.toml` | Service-level overrides | Yes |

Both files support the same top-level sections:

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS",
    "buildCommand": "npm run build",
    "watchPatterns": ["src/**", "package.json"]
  },
  "deploy": {
    "startCommand": "node dist/server.js",
    "healthcheckPath": "/health",
    "healthcheckTimeout": 120,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10,
    "numReplicas": 1
  }
}
```

`railway.toml` (TOML equivalent, preferred for service-level config in monorepos):

```toml
[build]
builder = "nixpacks"
buildCommand = "npm run build"

[deploy]
startCommand = "node dist/server.js"
healthcheckPath = "/health"
healthcheckTimeout = 120
restartPolicyType = "ON_FAILURE"
```

**Precedence:** dashboard settings override `railway.json` / `railway.toml`. If you change a setting in the dashboard, it takes effect even if the file says otherwise. Prefer config files for reproducibility; audit dashboard overrides regularly.

## Railway CLI (≥ 3.x)

Install:

```bash
# macOS
brew install railway

# npm
npm install -g @railway/cli

# Shell installer
bash <(curl -fsSL cli.new)
```

Core workflow:

```bash
railway login                    # authenticate (browser-based OAuth)
railway link                     # link local dir to a Railway project + service
railway up                       # deploy current directory
railway up --detach              # deploy and return immediately (CI-friendly)
railway logs --service my-api    # stream logs
railway run -- npm run migrate   # run a command in Railway's environment locally
railway variables                # list service variables
railway open                     # open the project dashboard in a browser
railway environment              # switch active environment
railway status                   # show current project, environment, service
```

For CI/CD, authenticate with a Service Token:

```bash
export RAILWAY_TOKEN=<service-token>
railway up --service my-api --environment production --detach
```

## GitHub Actions deployment

The canonical GitHub Actions pattern for Railway (as of 2026-05 with CLI ≥ 3.x):

```yaml
name: Deploy to Railway

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install Railway CLI
        run: npm install -g @railway/cli

      - name: Deploy
        env:
          RAILWAY_TOKEN: ${{ secrets.RAILWAY_TOKEN }}
        run: railway up --service my-api --environment production --detach
```

Key points:

- `RAILWAY_TOKEN` is a Service Token stored in GitHub Actions Secrets (not a personal account token).
- `--detach` returns immediately after triggering the deploy; the Railway dashboard shows deploy status.
- Scope the token to the specific service and environment — do not use a project-wide token unless the workflow deploys multiple services.
- Pin the `actions/checkout` version; pin the Railway CLI version for reproducible builds.

For monorepos with multiple services, deploy them in parallel:

```yaml
jobs:
  deploy-api:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npm install -g @railway/cli
      - env:
          RAILWAY_TOKEN: ${{ secrets.RAILWAY_TOKEN_API }}
        run: railway up --service api --environment production --detach

  deploy-worker:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npm install -g @railway/cli
      - env:
          RAILWAY_TOKEN: ${{ secrets.RAILWAY_TOKEN_WORKER }}
        run: railway up --service worker --environment production --detach
```

## Railway Templates

Templates are shareable Railway project configurations that others can deploy with one click.

**Consuming a template:**

1. Browse `railway.app/templates` or use a direct template link.
2. Click "Deploy" — Railway provisions all services defined in the template into your project.
3. Review and set required Variables (the template declares which ones are required).
4. Review service settings and customize as needed before sending traffic.

**Publishing a template:**

1. Build a working Railway project with all services, Variables, and config files.
2. Navigate to Project Settings → "Create Template".
3. Mark Variables as `required` (user must set) or `optional` (has a default).
4. Write a clear `README.md` — it appears on the template page.
5. Publish. The template captures your project structure but NOT your secret variable values.

Template best practices:

- Include a health check on every service in the template — new deployers get a working project, not a silent failure.
- Document required Variables with descriptions in the Railway variable panel (Railway shows descriptions in the deploy UI).
- Pin image tags or Nixpacks versions in the template so deployers get a known-good state.
- Test the template in a clean Railway account before publishing.

## Environment promotion (dev → staging → production)

Railway environments are isolated — each has its own service instances, Plugins, and Variables.

**Environment structure:**

```text
Project
├── production   (main branch auto-deploys here)
├── staging      (staging branch or manual deploys)
└── development  (feature branches or manual deploys)
```

**Promotion workflow:**

1. Merge feature branch to `staging` branch → Railway auto-deploys to the `staging` environment.
2. Run smoke tests against staging.
3. Merge `staging` to `main` → Railway auto-deploys to `production`.

**Variables per environment:**

Each environment has its own copy of Variables. Set `DATABASE_URL` in production to point to the production Postgres Plugin; set it in staging to point to the staging Postgres Plugin. Never share credentials between environments.

**Promoting a specific deploy:**

Railway allows you to re-deploy any previous deployment from the service's deploy history. This is the rollback mechanism — if a production deploy is bad, find the previous good deploy in history and redeploy it.

## Preview environments (PR-based)

Railway can create a temporary environment per GitHub Pull Request:

1. Enable in Project Settings → "PR Environments".
2. When a PR is opened, Railway clones the closest environment (usually `staging` or `development`) and deploys the PR branch into it.
3. When the PR is merged or closed, Railway deletes the preview environment and all its resources.

Preview environment considerations:

- Preview environments create real Plugin instances (Postgres, Redis) that incur real costs until deleted.
- Set up automatic environment deletion on PR merge in GitHub Actions:

```yaml
on:
  pull_request:
    types: [closed]

jobs:
  cleanup:
    runs-on: ubuntu-latest
    if: github.event.pull_request.merged == true || github.event.pull_request.state == 'closed'
    steps:
      - name: Delete Railway PR environment
        env:
          RAILWAY_TOKEN: ${{ secrets.RAILWAY_TOKEN }}
        run: railway environment delete --name "pr-${{ github.event.number }}" --yes
```

- If preview environments use the same Plugin type as production, ensure migrations run safely on ephemeral data.
- Do not point preview environments at production data sources — each gets its own seeded or empty Plugin.

## Volumes lifecycle in deploys

Volumes persist data across deploys — the mount path survives a new deploy, rollback, or restart.

What happens in different scenarios:

| Scenario | Volume data |
| --- | --- |
| Redeploy (same service) | Volume is preserved and remounted |
| Rollback to a previous deploy | Volume is preserved; old code sees current Volume state |
| Service deletion | Volume is deleted (and data is gone unless you backed it up) |
| Preview environment deletion | Volume inside preview env is deleted |
| Service clone to a new environment | Volume is NOT cloned; new environment starts with an empty Volume |

Implications for migrations: if your migration writes a marker to the Volume (e.g., SQLite `migrations` table), rollback may see a newer schema. Design schema migrations to be backward-compatible (additive only) to make rollback safe.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Dashboard-only config with no `railway.json` | Config is invisible to code review; drift is silent and hard to audit. |
| Deploying production directly from a developer laptop | No audit trail; no review gate; accidental prod pushes. Use CI/CD. |
| Single Service Token for all environments | Token exposure = all environments at risk. One token per service per env. |
| Preview environments with no cleanup job | Accumulate indefinitely; Plugin costs add up; stale envs confuse the team. |
| Sharing Variables across environments | Staging accidentally uses prod keys; prod uses stale staging secrets. |
| Rollback without considering Volume state | Volume contains data written by the newer deploy; rollback code may misinterpret it. |
| Publishing a template with hardcoded secrets | Template captures Variable values at publish time; anyone deploying the template gets your secrets. Mark all secrets as `required` with no default. |

## Security defaults

- Service Tokens for CI/CD, scoped per service per environment.
- `railway.json` checked into version control so config changes go through code review.
- No personal account credentials in CI (use tokens).
- Preview environment tokens separate from production tokens.
- Template published with no secret defaults — all sensitive Variables marked `required`.

## Observability defaults

- Enable GitHub commit status updates in Railway project settings so deploy status appears on PRs.
- Wire a log drain before launch so deploy failures and errors appear in your observability tool, not just the Railway dashboard.
- Tag Railway services with `environment` and `service` labels (via Railway Variables injected into the app) so logs and metrics filter correctly in Datadog / Better Stack.

## Cost considerations

- Preview environments with Plugins: each PR environment spins up its own Plugin instances. Budget this explicitly or enforce cleanup.
- `railway up --detach` returns before billing starts accumulating for the build — build minutes are billed separately from runtime minutes.
- Staging environment is always-on by default; if it has Plugins, those run continuously. Consider pausing staging services on weekends or overnight if the usage pattern justifies it (Railway has a "pause" feature for services).

## Verification checklist

Before declaring a deployment configuration complete:

- [ ] `railway.json` or `railway.toml` committed to repo and covers build + deploy config.
- [ ] GitHub Actions workflow uses a scoped Service Token per environment (not a personal token).
- [ ] Production deploys go through CI/CD only (no `railway up` from laptops in prod).
- [ ] Preview environments are enabled only if a cleanup job is also in place.
- [ ] Each environment has its own Variables (including its own Plugin credentials).
- [ ] Template (if publishing) has all sensitive Variables marked `required` with no default.
- [ ] Rollback path tested: select a previous deploy in history, verify it serves correctly.
- [ ] Volume backup strategy documented and tested before the first production write.
- [ ] Deploy protection enabled on production environment (Pro plan).
