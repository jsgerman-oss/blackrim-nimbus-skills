---
description: Scaffold a Cloudflare project — Worker, Pages, or Worker+D1+R2 starter — with Wrangler config, Terraform skeleton, and GitHub Actions deploy using scoped API tokens.
argument-hint: <workload-description>
---

# Cloudflare Scaffold Project

Scaffold a new Cloudflare project for a workload described as: **$ARGUMENTS**

## What to do

1. **Confirm the project type.** Ask the user which template they want, with a one-line recommendation based on the workload description:
   - Static site with optional edge logic → **Pages** (connect a GitHub repo; optional Pages Functions for API routes).
   - API handler, proxy, or lightweight service → **Worker** (module syntax, `wrangler.toml`, deployed via Wrangler).
   - Full-stack app with structured data and blob storage → **Worker + D1 + R2** (Worker handles routing, D1 stores relational data, R2 stores user uploads or assets).
   - Long-running or multi-step processes → **Worker + Queues + Durable Objects** (add Queues for background tasks and Durable Objects for coordination state).

   Do not prescribe — recommend, then defer to the user.

2. **Confirm scope** with up to three questions if not obvious:
   - Target Cloudflare account and zone (or `workers.dev` subdomain only)?
   - Multi-environment (staging + production) or single environment?
   - Greenfield, or migrating an existing app (import existing data, bind to existing resources)?

3. **Generate the project skeleton** in the current working directory (or a subdirectory the user picks). Every scaffold must include:
   - `wrangler.toml` (or `wrangler.jsonc`) with per-environment stanzas.
   - `package.json` with `wrangler` pinned in devDependencies; `npm run dev`, `npm run deploy`, and `npm test` scripts.
   - TypeScript configuration (`tsconfig.json`) with `@cloudflare/workers-types` for type safety.
   - `.gitignore` covering `node_modules/`, `.dev.vars`, `dist/`, `.wrangler/`.
   - `.dev.vars` (local secrets file) — empty template with a comment; confirm it is already in `.gitignore`.
   - A `README.md` with setup, local dev, deploy, and environment variable instructions.
   - Terraform skeleton in `infra/` for Cloudflare resources managed outside Wrangler.
   - GitHub Actions workflow(s) in `.github/workflows/`.
   - At least one unit test (`vitest` with `@cloudflare/vitest-pool-workers`) confirming the scaffold is testable.

4. **Wire production-grade defaults.** For each scaffold:
   - TLS Mode = Full (Strict) via Terraform (`cloudflare_zone_settings_override` or equivalent).
   - Always Use HTTPS and minimum TLS 1.2 enforced.
   - DNSSEC resource in Terraform (DS record reminder included in README).
   - WAF managed rulesets enabled via Terraform `cloudflare_ruleset`.
   - Secrets via `wrangler secret put` — documented in README with the exact command per secret.
   - No plaintext credentials in `wrangler.toml`.
   - Logpush job for HTTP request logs to R2 — Terraform resource included in skeleton.
   - Analytics Engine binding wired in `wrangler.toml`; `writeDataPoint` called in the Worker request handler.

5. **Print next steps** — the exact commands to run after the scaffold is generated:
   - `npm install` to install dependencies.
   - `wrangler login` (or set `CLOUDFLARE_API_TOKEN` in shell).
   - `wrangler dev` to start local development.
   - `wrangler secret put <SECRET_NAME> --env staging` for each secret.
   - `terraform init && terraform plan` in `infra/` to preview infrastructure.
   - `terraform apply` in `infra/` (with a reminder to review the plan first).
   - `wrangler deploy --env staging` to deploy to staging.
   - A reminder: staging deploy before production, always.

---

## Scaffold layouts

### Worker (standalone API or proxy)

```
.
├── src/
│   ├── index.ts             # Worker entry point (ES module syntax)
│   └── index.test.ts        # Unit tests (vitest + workers pool)
├── infra/
│   ├── main.tf              # Cloudflare provider + Worker domain/route
│   ├── variables.tf
│   ├── outputs.tf
│   └── terraform.tfvars.example
├── .github/
│   └── workflows/
│       ├── test.yml         # Run tests on every PR
│       └── deploy.yml       # Deploy to staging on main; production on tag
├── wrangler.toml            # Main config + env stanzas
├── package.json
├── tsconfig.json
├── .gitignore
├── .dev.vars                # Local secrets template (gitignored)
└── README.md
```

**`wrangler.toml` starter:**

```toml
name = "my-worker"
main = "src/index.ts"
compatibility_date = "2025-01-01"

[observability]
enabled = true              # Enable Workers Logs (dashboard tail).

[[analytics_engine_datasets]]
binding = "AE"
dataset = "my_worker_events"

[env.staging]
name = "my-worker-staging"
[[env.staging.analytics_engine_datasets]]
binding = "AE"
dataset = "my_worker_events_staging"

[env.production]
name = "my-worker-production"
[env.production.placement]
mode = "smart"
[[env.production.analytics_engine_datasets]]
binding = "AE"
dataset = "my_worker_events_production"
```

---

### Pages (static site + optional edge functions)

```
.
├── public/                  # Static assets (HTML, CSS, JS)
├── functions/
│   └── api/
│       └── [[route]].ts     # Catch-all Pages Function
├── infra/
│   ├── main.tf              # Cloudflare Pages project, DNS record
│   ├── variables.tf
│   └── terraform.tfvars.example
├── .github/
│   └── workflows/
│       └── pages-deploy.yml # Uses Wrangler for Pages deployment
├── wrangler.toml            # pages_build_output_dir + bindings
├── package.json
├── .gitignore
└── README.md
```

**Key `wrangler.toml` field for Pages:**

```toml
pages_build_output_dir = "public"
compatibility_date = "2025-01-01"

[[kv_namespaces]]
binding = "CACHE"
id = "<staging-kv-id>"
```

---

### Worker + D1 + R2 (full-stack with structured data and storage)

```
.
├── src/
│   ├── index.ts             # Worker router
│   ├── handlers/
│   │   ├── api.ts           # API route handlers
│   │   └── assets.ts        # R2 asset serving
│   └── index.test.ts
├── migrations/
│   └── 0001_init.sql        # D1 schema migration
├── infra/
│   ├── main.tf              # R2 bucket, D1 database, Logpush, WAF, DNS
│   ├── variables.tf
│   ├── outputs.tf
│   └── terraform.tfvars.example
├── .github/
│   └── workflows/
│       ├── test.yml
│       └── deploy.yml
├── wrangler.toml
├── package.json
├── tsconfig.json
├── .gitignore
├── .dev.vars
└── README.md
```

**`wrangler.toml` starter for Worker + D1 + R2:**

```toml
name = "my-app"
main = "src/index.ts"
compatibility_date = "2025-01-01"

[[d1_databases]]
binding = "DB"
database_name = "my-app-dev"
database_id = "<dev-database-id>"

[[r2_buckets]]
binding = "UPLOADS"
bucket_name = "my-app-uploads-dev"

[[analytics_engine_datasets]]
binding = "AE"
dataset = "my_app_events_dev"

[env.production]
name = "my-app-production"
[[env.production.d1_databases]]
binding = "DB"
database_name = "my-app-prod"
database_id = "<prod-database-id>"
[[env.production.r2_buckets]]
binding = "UPLOADS"
bucket_name = "my-app-uploads-prod"
[[env.production.analytics_engine_datasets]]
binding = "AE"
dataset = "my_app_events_production"
[env.production.placement]
mode = "smart"
```

---

## GitHub Actions — deploy workflow template

```yaml
name: Deploy

on:
  push:
    branches: [main]
  release:
    types: [published]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - run: npm ci
      - run: npm test

  deploy-staging:
    needs: test
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    environment: staging
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - run: npm ci
      - run: npx wrangler deploy --env staging
        env:
          CLOUDFLARE_API_TOKEN: ${{ secrets.CLOUDFLARE_API_TOKEN_STAGING }}

  deploy-production:
    needs: test
    if: github.event_name == 'release'
    runs-on: ubuntu-latest
    environment: production   # GitHub environment with required reviewers.
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - run: npm ci
      - run: npx wrangler deploy --env production
        env:
          CLOUDFLARE_API_TOKEN: ${{ secrets.CLOUDFLARE_API_TOKEN_PROD }}
```

**Required GitHub repository secrets:**
- `CLOUDFLARE_API_TOKEN_STAGING` — scoped to staging Worker/Pages deploy permissions only.
- `CLOUDFLARE_API_TOKEN_PROD` — scoped to production Worker/Pages deploy permissions only.

**Creating a scoped API token** (remind the user):
> Cloudflare dashboard → My Profile → API Tokens → Create Token → Use the "Edit Cloudflare Workers" template → Scope to the specific account and zone → Set an expiry date.

---

## After scaffolding

- Hand off the generated Wrangler config and Terraform skeleton to the `cf-architect` sub-agent for a same-day review before the first `wrangler deploy --env production`.
- Run `cf-security-reviewer` once the first staging environment is deployed and serving real traffic, before opening production.
- Remind the user: D1 schema migrations (`wrangler d1 migrations apply --env production`) must be run separately from Worker deploys. Plan the order: migrate schema first, then deploy the Worker that depends on it.
- For the Terraform skeleton: run `terraform init`, review the plan with `terraform plan`, and apply to staging before production.
