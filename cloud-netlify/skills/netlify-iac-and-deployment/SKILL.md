---
name: netlify-iac-and-deployment
description: Manage Netlify infrastructure-as-code and deployment — `netlify.toml` as the primary IaC surface, Netlify CLI (v17+), Build Plugins (`@netlify/plugin-*`), GitHub / GitLab / Bitbucket Git provider integration, deploy hooks, `netlify deploy --prod`, and the community Terraform `netlify/netlify` provider. Use when setting up a new site from code, scripting deployments in CI, wiring Git provider webhooks, or auditing the deployment pipeline.
---

# Netlify IaC and Deployment

## When to use

- Setting up a new Netlify site with everything in code, not the dashboard.
- Migrating dashboard-configured settings into `netlify.toml`.
- Writing a CI pipeline for preview and production deploys.
- Scripting site creation and management via the Netlify CLI.
- Evaluating the Terraform `netlify/netlify` provider for infrastructure automation.
- Auditing deploy hooks, deploy keys, and Git provider integration for security.
- Adding a Build Plugin to the deploy pipeline.

## `netlify.toml` — the primary IaC surface

`netlify.toml` is the single source of truth for a Netlify site's build, redirect, header, function, and edge function configuration. It lives at the repository root and is parsed on every build.

Reference structure covering all major sections:

```toml
# ── Build ──────────────────────────────────────────────────────────────────
[build]
  command   = "npm run build"
  publish   = "dist"
  functions = "netlify/functions"
  edge_functions = "netlify/edge-functions"
  ignore    = "git diff --quiet HEAD^ HEAD -- src/"  # skip build if only non-src changed

[build.environment]
  NODE_VERSION = "20"
  PNPM_VERSION = "9"

# ── Context overrides ──────────────────────────────────────────────────────
[context.production]
  command = "npm run build:prod"

[context.deploy-preview]
  command = "npm run build:preview"

[context."staging"]              # named branch context
  command = "npm run build:staging"

# ── Security headers ────────────────────────────────────────────────────────
[[headers]]
  for = "/*"
  [headers.values]
    Strict-Transport-Security = "max-age=63072000; includeSubDomains; preload"
    X-Frame-Options           = "DENY"
    X-Content-Type-Options    = "nosniff"
    Referrer-Policy           = "strict-origin-when-cross-origin"
    Permissions-Policy        = "camera=(), microphone=(), geolocation=()"
    Content-Security-Policy   = "default-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none';"

[[headers]]
  for = "/api/*"
  [headers.values]
    Cache-Control = "no-store"

# ── Redirects ───────────────────────────────────────────────────────────────
[[redirects]]
  from   = "/api/*"
  to     = "/.netlify/functions/:splat"
  status = 200

[[redirects]]
  from   = "/*"
  to     = "/index.html"
  status = 200
  conditions = { Language = ["en"] }

# ── Build Plugins ───────────────────────────────────────────────────────────
[[plugins]]
  package = "@netlify/plugin-lighthouse"
  [plugins.inputs]
    fail_deploy_on_score_regression = "true"

[[plugins]]
  package = "netlify-plugin-a11y"

# ── Edge Functions ──────────────────────────────────────────────────────────
[[edge_functions]]
  function = "geolocation"
  path     = "/personalized/*"

[[edge_functions]]
  function = "ab-test"
  path     = "/"

# ── Per-function config ──────────────────────────────────────────────────────
[functions]
  node_bundler = "esbuild"

[functions.process-webhook]
  schedule = "@hourly"
```

## `_headers` and `_redirects` files

These flat files in the `publish` directory are an alternative (and complement) to `netlify.toml`. They are processed before `netlify.toml` directives for the same paths; when both exist, the file takes precedence on conflicting rules.

`_headers` example:

```
/*
  X-Frame-Options: DENY
  X-Content-Type-Options: nosniff

/static/*
  Cache-Control: public, max-age=31536000, immutable
```

`_redirects` example:

```
# SPA fallback
/*    /index.html   200

# API proxy
/api/*  /.netlify/functions/:splat  200

# Country redirect (Geo)
/     /us/     302   Country=us
/     /gb/     302   Country=gb
```

Prefer `netlify.toml` for version-controlled teams — it's reviewed in PRs. Use `_headers` / `_redirects` when the build framework generates them programmatically (some SSG frameworks emit these from their config).

## Netlify CLI (v17+)

The Netlify CLI is the primary tool for local development and scripted deployments. Install: `npm install -g netlify-cli`.

### Essential commands

```bash
# Link local dir to a Netlify site
netlify link

# Start local dev server (Functions, Edge Functions, redirects all active)
netlify dev

# Build the site locally (same environment as CI)
netlify build

# Deploy to a draft URL (staging, not production)
netlify deploy --dir=dist

# Deploy to production
netlify deploy --dir=dist --prod

# Deploy with a message tag
netlify deploy --dir=dist --prod --message="release v1.2.3"

# Run a function locally
netlify functions:invoke my-function --payload '{"key":"value"}'

# Open the Netlify dashboard for the linked site
netlify open

# List environment variables
netlify env:list

# Set an env var for a specific context and scope
netlify env:set DB_URL "postgres://..." --context production --scope functions

# Import env vars from a .env file
netlify env:import .env.production

# Trigger a deploy hook manually
netlify deploy:trigger
```

### Netlify Dev — local environment

`netlify dev` starts a local server that emulates the full Netlify environment:

- Proxies all requests through the Netlify routing rules (redirects, headers).
- Serves Serverless Functions at `/.netlify/functions/*`.
- Executes Edge Functions via a local Deno runtime.
- Injects environment variables from the Netlify site's settings.

This means you can develop and test Functions, Edge Functions, redirects, and headers locally without deploying.

## Git provider integration

Netlify integrates natively with GitHub, GitLab, and Bitbucket via OAuth. When connected:

- Every push to the default branch triggers a production deploy.
- Every pull request triggers a Deploy Preview.
- Deploy status checks appear on the PR.

Configuration options (dashboard → Site configuration → Build & deploy → Continuous deployment):

- **Auto-publishing**: on / off per context.
- **Deploy Previews**: all pull requests, or pull requests from team members only (recommended for public repos with forks).
- **Branch deploys**: all branches, or allowlisted branches.
- **Deploy notifications**: GitHub commit status checks, email, Slack.

### Deploy keys

Netlify registers a read-only deploy key on your Git repository to clone it at build time. Rotate this key if a team member with repository access leaves:

1. **Site configuration → Build & deploy → Continuous deployment → Deploy key**.
2. Generate a new key. Netlify updates the key on the Git provider automatically.

## Deploy hooks

Deploy hooks are incoming webhook URLs that trigger a new build when POSTed to. Use them for:

- CMS-triggered rebuilds (content published → POST to Netlify → rebuild site).
- External event-driven deploys (cron jobs, IoT, third-party services).
- Manual trigger without the CLI.

Create a hook: **Site configuration → Build & deploy → Continuous deployment → Build hooks → Add build hook**.

```bash
# Trigger a build hook
curl -X POST -d '{}' https://api.netlify.com/build_hooks/<hook-id>
```

Treat hook URLs as secrets — they trigger builds and consume build minutes. Rotate if leaked.

## GitHub Actions CI pipeline

For teams that want GitOps-style CI with Netlify deploy as the CD step:

```yaml
# .github/workflows/deploy.yml
name: Deploy to Netlify

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: "npm"

      - run: npm ci

      - run: npm run build

      - name: Deploy preview
        if: github.event_name == 'pull_request'
        uses: netlify/actions/cli@master
        with:
          args: deploy --dir=dist --alias=preview-${{ github.event.number }}
        env:
          NETLIFY_SITE_ID: ${{ secrets.NETLIFY_SITE_ID }}
          NETLIFY_AUTH_TOKEN: ${{ secrets.NETLIFY_AUTH_TOKEN }}

      - name: Deploy production
        if: github.ref == 'refs/heads/main'
        uses: netlify/actions/cli@master
        with:
          args: deploy --dir=dist --prod
        env:
          NETLIFY_SITE_ID: ${{ secrets.NETLIFY_SITE_ID }}
          NETLIFY_AUTH_TOKEN: ${{ secrets.NETLIFY_AUTH_TOKEN }}
```

`NETLIFY_AUTH_TOKEN`: generate a **personal access token** from your Netlify user settings (not a site-level token). Store as a GitHub Actions secret. Scope it to the minimum needed — deploy-only patterns can be achieved with a deploy hook instead of a full auth token.

## Terraform `netlify/netlify` provider

The community `netlify/netlify` Terraform provider manages Netlify site configuration as code. It is **community-maintained and lags the Netlify API** — treat it as best-effort for non-critical settings.

```hcl
terraform {
  required_providers {
    netlify = {
      source  = "netlify/netlify"
      version = "~> 0.3"
    }
  }
}

provider "netlify" {
  token = var.netlify_token    # Netlify personal access token
}

resource "netlify_site" "my_site" {
  name         = "my-site-name"
  custom_domain = "www.example.com"

  repo {
    command     = "npm run build"
    deploy_key_id = netlify_deploy_key.this.id
    dir         = "dist"
    provider    = "github"
    repo_path   = "org/repo"
    repo_branch = "main"
  }
}

resource "netlify_deploy_key" "this" {}

resource "netlify_environment_variable" "stripe_key" {
  site_id = netlify_site.my_site.id
  key     = "STRIPE_SECRET_KEY"
  values = [{
    value   = var.stripe_secret_key
    context = "production"
  }]
  scopes = ["functions"]
}
```

**Terraform limitations for Netlify:**
- No support for Logs Drain, Analytics, Identity configuration, or Build Plugin installation.
- Drift between the provider version and the Netlify API can cause plan errors.
- For most Netlify teams, `netlify.toml` + Netlify CLI + GitHub Actions covers 95% of IaC needs without Terraform.

Use the Terraform provider if your organization manages infrastructure across multiple providers in a single Terraform root module (e.g., Cloudflare DNS + Netlify sites + GitHub repos together).

## Build Plugins reference

Build Plugins are npm packages that hook into the Netlify build lifecycle. Install via `devDependencies`:

```bash
npm install --save-dev @netlify/plugin-lighthouse netlify-plugin-a11y
```

Declare in `netlify.toml`:

```toml
[[plugins]]
  package = "@netlify/plugin-lighthouse"
  [plugins.inputs]
    fail_deploy_on_score_regression = "true"
    thresholds_performance          = 0.9
    thresholds_accessibility        = 0.95
```

Recommended plugins for production sites:

| Plugin | Purpose | Fail on? |
| --- | --- | --- |
| `@netlify/plugin-lighthouse` | Lighthouse gate | Score regression |
| `netlify-plugin-a11y` | Accessibility audit | Violations |
| `netlify-plugin-checklinks` | Broken links | 404s on site links |
| `netlify-plugin-csp-nonce-gatsby` | CSP nonce injection | N/A |
| `@netlify/plugin-nextjs` | Next.js SSR/ISR support | Required for Next.js App Router |

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Dashboard-only configuration | Unreviewed, unversioned, invisible to new team members, drifts from code. |
| `NETLIFY_AUTH_TOKEN` in build env var | Token visible in build logs and to all team members. Store as a CI secret, not an env var. |
| Deploy hooks not rotated after leak | A leaked hook URL means anyone on the internet can burn your build minutes. |
| Auto-publish Deploy Previews for fork PRs | External contributors' PRs get access to your `deploy-preview` env vars. Restrict to team members. |
| Terraform managing `netlify.toml`-configurable settings | Two sources of truth; `netlify.toml` wins on most build settings and creates silent drift. |
| Using `netlify deploy --prod` from developer laptops without CI | No audit trail, no gate on tests, no consistent environment. Pipeline-only production deploys. |

## Security defaults

- `NETLIFY_AUTH_TOKEN` stored as a CI secret, never as a Netlify environment variable.
- Deploy hook URLs treated as secrets; stored in a secrets manager, not in `netlify.toml`.
- Deploy Previews restricted to team members (not all fork contributors) to prevent env var exposure.
- `netlify.toml` reviewed in every PR — build config changes are code changes.
- Build Plugin inputs reviewed before enabling; plugins run arbitrary code at build time.
- `netlify env:set --scope functions` applied to every secret that should not reach the browser.

## Observability defaults

- Deploy status checks on every PR via GitHub / GitLab integration.
- Deploy notifications (email + Slack) for production deploy success and failure.
- `netlify build` exit code in CI gates the PR — a failed build blocks merge.
- Build minutes usage visible in Team overview; set a billing alert threshold.

## Cost considerations

- Netlify CLI-triggered deploys (`netlify deploy --prod`) consume build minutes if using `--build` flag; skip with `--dir=<pre-built-dir>` in CI where the build runs separately.
- Terraform apply runs via GitHub Actions: runner cost is separate from Netlify build minutes — CLI calls against the Netlify API don't consume build minutes.
- Build Plugins add to build time; each plugin is an additional process. Measure contribution with build logs before adding more.
- Deploy hooks triggered by a chatty CMS (many saves, few publishes) burn minutes rapidly — batch rebuilds or use Netlify's ISR/DPR for content-driven sites.

## Verification checklist

- [ ] All build, redirect, header, and function configuration in `netlify.toml` (no dashboard-only settings).
- [ ] `netlify.toml` reviewed in every PR as code.
- [ ] `NETLIFY_AUTH_TOKEN` stored as a CI repository secret, not as a Netlify env var.
- [ ] Deploy hook URLs stored in a secrets manager; rotated if exposed.
- [ ] Deploy Previews scoped to team members (not all fork contributors).
- [ ] Build Plugins installed as `devDependencies` and pinned to a version range.
- [ ] Production deploys gated on a passing CI pipeline; no direct `netlify deploy --prod` from developer machines.
- [ ] Terraform provider version pinned; plan reviewed before apply.
- [ ] Security headers present in `netlify.toml` `[[headers]]` for `/*`.
