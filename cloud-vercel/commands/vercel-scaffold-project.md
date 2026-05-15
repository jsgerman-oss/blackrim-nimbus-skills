---
description: Scaffold a Next.js-on-Vercel project (or SvelteKit / Astro alternative) with vercel.json, env-var scope split, monorepo-aware Turborepo config, GitHub Actions for preview and production deploys, and an optional Terraform skeleton using the vercel/vercel provider.
argument-hint: <project-description>
---

# Vercel Scaffold Project

Scaffold a new Vercel project for: **$ARGUMENTS**

## What to do

1. **Confirm the framework.** Ask the user which framework they want, with a one-line recommendation based on the project description:
   - Content site, blog, marketing, SaaS with mostly server-rendered pages → **Next.js 15 (App Router)**. Best Vercel integration, ISR, Edge Middleware, native Image Optimization.
   - Component-driven, form-heavy app with excellent DX → **SvelteKit** with `@sveltejs/adapter-vercel`.
   - Content-first static site with optional SSR islands → **Astro** with `@astrojs/vercel` adapter.
   - Don't prescribe — recommend, then defer to the user.

2. **Confirm scope** with up to three questions if not obvious:
   - Monorepo or single-app repo?
   - Primary data store (Vercel Postgres / KV / Blob, external DB, headless CMS)?
   - Compliance requirements (GDPR, SOC 2, PCI) that affect Deployment Protection and data handling?

3. **Generate the project skeleton** in the current working directory (or a subdirectory the user picks). Use the layout below for the chosen framework. Every scaffold must include:
   - `vercel.json` with security headers, function config, and crons placeholder.
   - `.env.example` documenting all required env vars with comments (no values).
   - `.gitignore` entry for `.env.local` and `.vercel/`.
   - `README.md` with setup, deploy, and env var rotation instructions.
   - GitHub Actions workflows for Preview deploy (on PR) and Production deploy (on push to release branch, with manual approval gate).
   - Spend Management note in the README reminding the team to set limits in the Vercel Dashboard.

4. **Wire safe defaults.** For every scaffold:
   - Deployment Protection: note in README to enable for Preview deployments (Vercel Auth recommended; Password Protection as alternative).
   - All credential env vars marked as Sensitive in the setup instructions.
   - Security headers block in `vercel.json` (HSTS, X-Content-Type-Options, X-Frame-Options, Referrer-Policy, Permissions-Policy).
   - `CRON_SECRET` placeholder and verification snippet if cron jobs are included.
   - Rate limiting on auth routes noted in the WAF setup section of the README.

5. **Print next steps** — the exact commands the user must run after scaffold generation, plus a pre-launch security checklist.

## Framework-specific layouts

### Next.js 15 (App Router) — single app

```
.
├── app/
│   ├── layout.tsx              # Root layout — Analytics + SpeedInsights here
│   ├── page.tsx
│   ├── api/
│   │   ├── health/route.ts     # GET /api/health — liveness check
│   │   └── cron/
│   │       └── daily/route.ts  # POST /api/cron/daily — verify CRON_SECRET
│   └── (marketing)/
│       └── page.tsx
├── middleware.ts               # Edge Middleware — auth + geo; tight matcher
├── lib/
│   ├── db.ts                   # Vercel Postgres / Drizzle / Prisma client
│   └── kv.ts                   # Vercel KV client (if used)
├── public/
├── .github/
│   └── workflows/
│       ├── preview.yml         # PR → Preview deploy + comment
│       └── production.yml      # push release → Production (with approval)
├── vercel.json                 # Headers, rewrites, function config, crons
├── next.config.ts              # Pinned Next.js config; no output: 'standalone'
├── .env.example
├── .gitignore
└── README.md
```

### Next.js 15 (App Router) — monorepo with Turborepo

```
.
├── apps/
│   ├── web/                    # Main Next.js app
│   │   ├── app/
│   │   ├── middleware.ts
│   │   ├── vercel.json
│   │   ├── next.config.ts
│   │   └── package.json
│   └── docs/                   # Optional docs site (Astro / Next.js)
│       └── package.json
├── packages/
│   ├── ui/                     # Shared component library
│   │   └── package.json
│   └── db/                     # Shared Drizzle schema + migrations
│       └── package.json
├── turbo.json                  # Task pipeline: build, lint, test
├── .github/
│   └── workflows/
│       ├── preview.yml
│       └── production.yml
├── package.json                # Root workspace config
├── .env.example
├── .gitignore
└── README.md
```

Vercel project settings for monorepo:
- **Root Directory:** `apps/web`
- **Build Command:** `cd ../.. && npx turbo run build --filter=web`
- **Install Command:** `npm install` (at root)
- **Ignored Build Step:** `npx turbo-ignore`

### SvelteKit

```
.
├── src/
│   ├── routes/
│   │   ├── +layout.svelte
│   │   ├── +page.svelte
│   │   └── api/
│   │       └── health/+server.ts
│   └── hooks.server.ts         # Auth / session middleware
├── static/
├── .github/
│   └── workflows/
│       ├── preview.yml
│       └── production.yml
├── vercel.json
├── svelte.config.js            # adapter: vercel(), pinned version
├── vite.config.ts
├── .env.example
├── .gitignore
└── README.md
```

`svelte.config.js` adapter pin:

```javascript
import adapter from '@sveltejs/adapter-vercel';

const config = {
  kit: {
    adapter: adapter({
      runtime: 'nodejs22.x',  // or 'edge' for edge-deployed routes
      regions: ['iad1'],       // pin to region closest to database
    }),
  },
};

export default config;
```

### Astro (SSR)

```
.
├── src/
│   ├── pages/
│   │   ├── index.astro
│   │   └── api/
│   │       └── health.ts
│   └── layouts/
│       └── Base.astro
├── public/
├── .github/
│   └── workflows/
│       ├── preview.yml
│       └── production.yml
├── vercel.json
├── astro.config.mjs            # output: 'server', adapter: vercel()
├── .env.example
├── .gitignore
└── README.md
```

`astro.config.mjs` for Vercel SSR:

```javascript
import { defineConfig } from 'astro/config';
import vercel from '@astrojs/vercel/serverless';

export default defineConfig({
  output: 'server',
  adapter: vercel({
    webAnalytics: { enabled: true },
    speedInsights: { enabled: true },
    imageService: true,         // use Vercel Image Optimization
    isr: {
      expiration: 60,           // ISR revalidation in seconds
    },
  }),
});
```

## Generated file contents

### `vercel.json` (Next.js baseline)

```json
{
  "framework": "nextjs",
  "functions": {
    "api/export.ts": { "maxDuration": 300 }
  },
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        { "key": "Strict-Transport-Security", "value": "max-age=63072000; includeSubDomains; preload" },
        { "key": "X-Content-Type-Options", "value": "nosniff" },
        { "key": "X-Frame-Options", "value": "DENY" },
        { "key": "Referrer-Policy", "value": "strict-origin-when-cross-origin" },
        { "key": "Permissions-Policy", "value": "camera=(), microphone=(), geolocation=()" }
      ]
    }
  ],
  "crons": [
    { "path": "/api/cron/daily", "schedule": "0 4 * * *" }
  ]
}
```

### `.env.example`

```bash
# Database (Vercel Postgres — injected automatically after linking)
# POSTGRES_URL=
# POSTGRES_URL_NON_POOLING=  # Use this for migrations only
# POSTGRES_USER=
# POSTGRES_HOST=
# POSTGRES_DATABASE=
# POSTGRES_PASSWORD=         # Mark SENSITIVE in Vercel Dashboard

# KV (Vercel KV — injected automatically after linking)
# KV_URL=
# KV_REST_API_URL=
# KV_REST_API_TOKEN=         # Mark SENSITIVE
# KV_REST_API_READ_ONLY_TOKEN=

# Blob (Vercel Blob — injected automatically after linking)
# BLOB_READ_WRITE_TOKEN=     # Mark SENSITIVE

# Auth
# AUTH_SECRET=               # Mark SENSITIVE — random 32-byte hex string
# AUTH_URL=                  # Public URL of this app (e.g., https://example.com)

# Cron security
# CRON_SECRET=               # Mark SENSITIVE — verify in /api/cron/* handlers

# ISR on-demand revalidation
# REVALIDATE_SECRET=         # Mark SENSITIVE — verify in /api/revalidate handler

# Third-party services (examples)
# STRIPE_SECRET_KEY=         # Mark SENSITIVE
# SENDGRID_API_KEY=          # Mark SENSITIVE
```

### GitHub Actions — Preview deploy (`preview.yml`)

```yaml
name: Preview Deploy

on:
  pull_request:
    types: [opened, synchronize, reopened]

jobs:
  preview:
    runs-on: ubuntu-latest
    permissions:
      pull-requests: write

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: '22'
          cache: 'npm'

      - run: npm ci

      - name: Run checks
        run: npm run lint && npm run typecheck

      - name: Deploy Preview
        id: deploy
        run: |
          npx vercel@39 pull --yes --environment=preview \
            --token=${{ secrets.VERCEL_TOKEN }}
          npx vercel@39 build --token=${{ secrets.VERCEL_TOKEN }}
          URL=$(npx vercel@39 deploy --prebuilt \
            --token=${{ secrets.VERCEL_TOKEN }})
          echo "url=$URL" >> $GITHUB_OUTPUT
        env:
          VERCEL_ORG_ID: ${{ secrets.VERCEL_ORG_ID }}
          VERCEL_PROJECT_ID: ${{ secrets.VERCEL_PROJECT_ID }}

      - name: Comment preview URL
        uses: actions/github-script@v7
        with:
          script: |
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: `Preview ready: ${{ steps.deploy.outputs.url }}`
            })
```

### GitHub Actions — Production deploy (`production.yml`)

```yaml
name: Production Deploy

on:
  push:
    branches: [release]

jobs:
  production:
    runs-on: ubuntu-latest
    environment: production    # GitHub Environment — configure required reviewers

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: '22'
          cache: 'npm'

      - run: npm ci

      - name: Run checks
        run: npm run lint && npm run typecheck && npm test

      - name: Deploy Production
        run: |
          npx vercel@39 pull --yes --environment=production \
            --token=${{ secrets.VERCEL_TOKEN }}
          npx vercel@39 build --prod --token=${{ secrets.VERCEL_TOKEN }}
          npx vercel@39 deploy --prebuilt --prod \
            --token=${{ secrets.VERCEL_TOKEN }}
        env:
          VERCEL_ORG_ID: ${{ secrets.VERCEL_ORG_ID }}
          VERCEL_PROJECT_ID: ${{ secrets.VERCEL_PROJECT_ID }}
```

### Optional Terraform skeleton

```hcl
# terraform/main.tf
terraform {
  required_providers {
    vercel = {
      source  = "vercel/vercel"
      version = "~> 1.0"
    }
  }

  backend "s3" {
    # Replace with your state bucket
    bucket = "my-org-terraform-state"
    key    = "vercel/<project-name>/terraform.tfstate"
    region = "us-east-1"
  }
}

provider "vercel" {
  # Set VERCEL_API_TOKEN env var — never hardcode
  team = var.vercel_team_id
}

resource "vercel_project" "app" {
  name      = var.project_name
  framework = "nextjs"

  git_repository = {
    type = "github"
    repo = var.github_repo   # format: "org/repo"
  }

  serverless_function_region = "iad1"
}

resource "vercel_project_environment_variable" "auth_secret" {
  project_id = vercel_project.app.id
  key        = "AUTH_SECRET"
  value      = var.auth_secret
  target     = ["production", "preview"]
  sensitive  = true
}

# Add additional env vars following the same pattern
```

## After scaffolding — next steps

1. **Run locally:**
   ```bash
   npm install
   vercel link         # links to Vercel project; creates .vercel/project.json (gitignored)
   vercel env pull     # writes .env.local with all env vars
   npm run dev
   ```

2. **Set up Vercel Dashboard:**
   - Enable Deployment Protection → Vercel Auth (or Password) for Preview.
   - Mark all credential env vars as Sensitive.
   - Set Spend Management: soft limit = 2× estimated monthly, hard limit = 5× estimated monthly.
   - Enable WAF managed rules in Log mode; review for 48 hours; switch to Block.

3. **Set up GitHub:**
   - Add repository secrets: `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`.
   - Create a `release` branch as the production target.
   - Configure a GitHub Environment named `production` with required reviewer(s).

4. **Pre-launch security checklist:**
   - [ ] All secrets marked Sensitive.
   - [ ] Deployment Protection on for Preview.
   - [ ] Security headers verified (use [securityheaders.com](https://securityheaders.com)).
   - [ ] WAF rate limiting on auth endpoints.
   - [ ] `CRON_SECRET` set and verified in cron handler.
   - [ ] `.env.local` in `.gitignore` and not committed.

5. **Hand off to `vercel-architect`** for a review of the scaffold before the first production deploy.
