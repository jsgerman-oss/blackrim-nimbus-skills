---
name: vercel-iac-and-deployment
description: Configure or audit Vercel deployment infrastructure — vercel.json (rewrites, redirects, headers, function config), Vercel CLI, Git integration vs vercel deploy, GitHub Actions for PR previews and production deploys, Turborepo for monorepos, environment variable promotion (Dev → Preview → Production), and the community Terraform vercel/vercel provider. Use when setting up a new project's deployment pipeline, debugging routing, or codifying Vercel config in IaC.
---

# Vercel IaC and Deployment

## When to use

- Configuring `vercel.json` for rewrites, redirects, headers, or function overrides.
- Setting up a GitHub Actions workflow for preview deploy comments or production gating.
- Migrating from `vercel deploy` (manual) to Git-integrated automated deploys.
- Onboarding a monorepo to Turborepo for build optimization.
- Promoting environment variables from Preview to Production safely.
- Codifying a Vercel project in Terraform for repeatable provisioning.

## `vercel.json`

`vercel.json` is the primary configuration file for Vercel routing and function settings. It lives at the project root (or the configured Root Directory for monorepos).

### Rewrites

Rewrites proxy a request to a different path or URL without changing the browser's URL:

```json
{
  "rewrites": [
    { "source": "/api/:path*", "destination": "https://api.internal.example.com/:path*" },
    { "source": "/old-docs/:slug", "destination": "/docs/:slug" }
  ]
}
```

**Order matters:** rewrites are matched top-to-bottom. More specific patterns go first.

**Rewrite vs redirect:** use a rewrite to proxy (origin changes, URL stays); use a redirect to move a URL permanently or temporarily.

### Redirects

```json
{
  "redirects": [
    { "source": "/blog", "destination": "/posts", "permanent": true },
    { "source": "/promo", "destination": "https://partner.example.com/promo", "permanent": false }
  ]
}
```

`permanent: true` sends HTTP 308 (permanent redirect); `permanent: false` sends 307 (temporary). Both are cacheable at the CDN level — use 307 for anything that may change.

### Headers

```json
{
  "headers": [
    {
      "source": "/api/(.*)",
      "headers": [
        { "key": "Access-Control-Allow-Origin", "value": "https://app.example.com" },
        { "key": "Access-Control-Allow-Methods", "value": "GET,POST,OPTIONS" }
      ]
    },
    {
      "source": "/(.*)",
      "headers": [
        { "key": "Strict-Transport-Security", "value": "max-age=63072000; includeSubDomains; preload" },
        { "key": "X-Content-Type-Options", "value": "nosniff" }
      ]
    }
  ]
}
```

### Function configuration

Override memory, max duration, and region for specific function paths:

```json
{
  "functions": {
    "api/heavy-task.ts": {
      "memory": 1024,
      "maxDuration": 300
    },
    "api/edge-handler.ts": {
      "runtime": "edge"
    }
  }
}
```

### Clean URL and trailing slash

```json
{
  "cleanUrls": true,
  "trailingSlash": false
}
```

These settings interact with Next.js's own `trailingSlash` config — set them consistently in both places to avoid redirect loops.

### Full `vercel.json` for a production Next.js project

```json
{
  "framework": "nextjs",
  "functions": {
    "api/export.ts": { "maxDuration": 300, "memory": 1024 }
  },
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        { "key": "Strict-Transport-Security", "value": "max-age=63072000; includeSubDomains; preload" },
        { "key": "X-Content-Type-Options", "value": "nosniff" },
        { "key": "X-Frame-Options", "value": "DENY" },
        { "key": "Referrer-Policy", "value": "strict-origin-when-cross-origin" }
      ]
    }
  ],
  "redirects": [
    { "source": "/old-product", "destination": "/products/new", "permanent": true }
  ],
  "crons": [
    { "path": "/api/cron/daily-sync", "schedule": "0 4 * * *" }
  ]
}
```

## Vercel CLI

```bash
# Install and authenticate
npm i -g vercel@latest  # ≥ 39.x
vercel login            # opens browser OAuth

# Link a project
vercel link             # creates .vercel/project.json (do NOT commit)

# Pull env vars to .env.local (gitignored)
vercel env pull

# Deploy to preview
vercel

# Deploy to production
vercel --prod

# Force a fresh build (busts cache)
vercel --prod --force

# Stream logs
vercel logs https://my-project.vercel.app --follow
```

**`.vercel/project.json`** contains project and team IDs — do not commit to source control (add to `.gitignore`). CI workflows use `VERCEL_TOKEN`, `VERCEL_ORG_ID`, and `VERCEL_PROJECT_ID` env vars instead.

## Git integration vs `vercel deploy`

| Approach | When to use |
| --- | --- |
| Git integration (automatic) | Standard projects — every push triggers a deploy automatically |
| `vercel --prod` (CLI) | One-off production deploys without a CI system; local hotfix |
| `vercel deploy --prebuilt` | Separation of build and deploy stages (build in CI, deploy artifact to Vercel) |
| Deploy hook (webhook) | CMS-triggered ISR rebuilds, non-Git automation |

**Prefer Git integration** for all standard workflows — it provides commit attribution, PR comments, and branch-based environment targeting automatically.

**`vercel deploy --prebuilt`** is the pattern for large CI pipelines where you want to run the build on self-hosted runners (more CPU/memory, custom tooling) and only upload the output artifact to Vercel:

```bash
# In CI
npm run build        # builds the project locally
vercel deploy --prebuilt --token $VERCEL_TOKEN
```

## GitHub Actions

### PR preview deploy with comment

```yaml
# .github/workflows/preview.yml
name: Preview Deploy

on:
  pull_request:
    types: [opened, synchronize, reopened]

jobs:
  deploy-preview:
    runs-on: ubuntu-latest
    permissions:
      pull-requests: write
    steps:
      - uses: actions/checkout@v4

      - name: Install Vercel CLI
        run: npm install -g vercel@39

      - name: Deploy Preview
        id: deploy
        run: |
          URL=$(vercel --token ${{ secrets.VERCEL_TOKEN }} \
            --env VERCEL_ORG_ID=${{ secrets.VERCEL_ORG_ID }} \
            --env VERCEL_PROJECT_ID=${{ secrets.VERCEL_PROJECT_ID }} \
            2>/dev/null)
          echo "url=$URL" >> $GITHUB_OUTPUT
        env:
          VERCEL_TOKEN: ${{ secrets.VERCEL_TOKEN }}
          VERCEL_ORG_ID: ${{ secrets.VERCEL_ORG_ID }}
          VERCEL_PROJECT_ID: ${{ secrets.VERCEL_PROJECT_ID }}

      - name: Comment Preview URL
        uses: actions/github-script@v7
        with:
          script: |
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: `Preview: ${{ steps.deploy.outputs.url }}`
            })
```

### Production deploy with manual approval

```yaml
# .github/workflows/production.yml
name: Production Deploy

on:
  push:
    branches: [release]

jobs:
  deploy-production:
    runs-on: ubuntu-latest
    environment: production   # GitHub environment with required reviewers
    steps:
      - uses: actions/checkout@v4
      - run: npm install -g vercel@39
      - run: vercel --prod --token ${{ secrets.VERCEL_TOKEN }}
        env:
          VERCEL_TOKEN: ${{ secrets.VERCEL_TOKEN }}
          VERCEL_ORG_ID: ${{ secrets.VERCEL_ORG_ID }}
          VERCEL_PROJECT_ID: ${{ secrets.VERCEL_PROJECT_ID }}
```

Using a GitHub Environment with required reviewers gates production deploys behind a manual approval step.

## Turborepo for monorepos

Turborepo is a monorepo build orchestrator that integrates deeply with Vercel. Use it when a monorepo has ≥ 2 apps or ≥ 3 shared packages.

```json
// turbo.json at the monorepo root
{
  "$schema": "https://turbo.build/schema.json",
  "tasks": {
    "build": {
      "dependsOn": ["^build"],
      "outputs": [".next/**", "dist/**", ".svelte-kit/**"]
    },
    "lint": { "dependsOn": [] },
    "test": { "dependsOn": ["^build"] }
  }
}
```

**Vercel project configuration for a monorepo:**

- Set **Root Directory** in Project Settings to the app's directory (e.g., `apps/web`).
- Set **Build Command** to `cd ../.. && npx turbo run build --filter=web` (run turbo from root).
- Set **Install Command** to `npm install` at the root.
- Enable **Ignored Build Step** with `npx turbo-ignore` to skip builds when the app and its deps are unchanged.

**Vercel Remote Cache** accelerates Turborepo builds across CI runs. Enable it via:

```bash
vercel link   # links the repo; injects TURBO_TOKEN and TURBO_TEAM automatically on Vercel builds
npx turbo run build --remote-only  # for CI that also uses remote cache
```

## Environment variable promotion

Vercel supports three env var scopes: **Development** (local), **Preview** (non-production branches), and **Production**.

**Promotion workflow:**

1. Add a new secret to Preview scope first.
2. Verify behavior in a Preview deployment.
3. Promote to Production scope in Project Settings → Environment Variables.

There is no one-click "promote from Preview to Production" in the UI — you add the same key to Production scope separately. This is intentional: Preview and Production often have different values (sandbox vs live credentials).

**Branch-specific env vars (Pro+):** override values for a specific branch:

```bash
vercel env add STRIPE_KEY preview --git-branch staging
```

This sets `STRIPE_KEY` specifically for the `staging` branch's preview deployments without affecting other branches.

## Terraform — `vercel/vercel` provider

The community `vercel/vercel` Terraform provider (≥ 1.x) manages Vercel resources in code.

```hcl
terraform {
  required_providers {
    vercel = {
      source  = "vercel/vercel"
      version = "~> 1.0"
    }
  }
}

provider "vercel" {
  api_token = var.vercel_api_token   # never hardcode; use env var VERCEL_API_TOKEN
  team      = var.vercel_team_id
}

resource "vercel_project" "web" {
  name      = "my-web-app"
  framework = "nextjs"

  git_repository = {
    type = "github"
    repo = "my-org/my-repo"
  }
}

resource "vercel_project_environment_variable" "database_url" {
  project_id = vercel_project.web.id
  key        = "DATABASE_URL"
  value      = var.database_url
  target     = ["production", "preview"]
  sensitive  = true
}
```

**Provider caveats:**

- The provider is community-maintained — validate capabilities against the latest release before using in critical workflows.
- WAF rules, Logs Drains, and Spend Management limits are not yet fully exposed in the provider (as of v1.x). Use the Vercel API for those.
- Store state in a remote backend (Terraform Cloud, S3 + DynamoDB) — not locally, since multiple team members may need to apply.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Committing `.vercel/project.json` | Exposes project and org IDs; anyone with a token can deploy to your project. |
| `vercel --prod` from a developer laptop | No audit trail, bypasses CI gates, no PR review. Use Git integration. |
| `vercel.json` rewrites proxying internal endpoints without auth | Any internet client can reach your internal API. Add authentication in the rewrite target or Middleware. |
| Duplicate framework config in `vercel.json` and `next.config.js` | Conflicting `trailingSlash` or `redirects` causes redirect loops. Pick one source of truth. |
| Turborepo without `turbo-ignore` | Every push to any branch rebuilds all apps in the monorepo, burning build minutes. |
| Plain `VERCEL_TOKEN` in GitHub Actions without OIDC | Token scoped to your whole team is a blast-radius problem if the secret leaks. Rotate quarterly. |
| Terraform `vercel_project` without `git_repository` | Creates a project that is not connected to Git; requires manual deploys forever. |

## Defaults — release pipeline

- Production branch is a deliberate branch (`release`, `production`, or a protected `main`) with branch protection rules.
- Every PR triggers a Preview deploy with the URL posted as a PR comment.
- Production deploys require a passing CI check and (for regulated projects) a GitHub Environment manual approval.
- `vercel.json` is version-controlled; changes go through PR review.
- Security headers set in `vercel.json` headers block.
- Cron secrets and deploy hook URLs stored as GitHub secrets, never in `vercel.json`.

## Verification checklist

- [ ] `.vercel/project.json` in `.gitignore`.
- [ ] Git integration connected — no manual `vercel --prod` from laptops as standard practice.
- [ ] `vercel.json` committed to source control and reviewed in PRs.
- [ ] Security headers (HSTS, X-Content-Type-Options, X-Frame-Options) present in `vercel.json` headers block.
- [ ] Monorepo: Turborepo configured with remote cache; `turbo-ignore` as Ignored Build Step.
- [ ] GitHub Actions: `VERCEL_TOKEN` stored as GitHub secret; not logged or echoed.
- [ ] Env var promotion: Preview and Production scopes have different values for credentials (sandbox vs live).
- [ ] Terraform state in a remote backend if the `vercel/vercel` provider is used.
- [ ] Cron job paths verified with `CRON_SECRET` header check in the handler.
