---
name: cf-iac-and-deployment
description: Configure or audit Cloudflare Infrastructure-as-Code and deployment — Wrangler (wrangler.toml / wrangler.jsonc), Terraform cloudflare/cloudflare ≥ 5.x, Pages CI, Workers Builds, GitHub Actions deploy with scoped API tokens, and secret management. Use when scaffolding a new project, wiring CI/CD, migrating from v4 Terraform provider, or hardening a release pipeline.
---

# Cloudflare IaC and Deployment

## When to use

- Setting up a new Worker, Pages, or D1 project with production-grade defaults.
- Writing or reviewing `wrangler.toml` / `wrangler.jsonc` for multi-environment deploys.
- Authoring or migrating Terraform for Cloudflare resources (especially v4 → v5 provider migration).
- Designing a CI/CD pipeline with GitHub Actions that deploys to Cloudflare using scoped API tokens.
- Managing Workers secrets safely across environments.
- Reviewing an existing IaC repo for drift, secret hygiene, or missing resources.

## Wrangler (the Cloudflare CLI)

Wrangler is the canonical tool for developing, testing, and deploying Workers and Pages projects. Wrangler ≥ 4.x (`npm install -D wrangler@latest`) is required for current features.

### `wrangler.toml` vs `wrangler.jsonc`

- Use `wrangler.toml` (TOML format) unless your project has an existing `wrangler.jsonc` (JSON5 with comments) convention.
- `wrangler.jsonc` supports comments and is friendlier for complex configs with inline documentation.
- Do not mix formats in the same project.

### Configuration structure

```toml
name = "my-worker"
main = "src/index.ts"
compatibility_date = "2025-01-01"   # Pin; advance deliberately.
compatibility_flags = []

# Shared bindings (available in all environments)
[[kv_namespaces]]
binding = "SESSIONS"
id = "abc123..."

[env.production]
name = "my-worker-production"
[[env.production.kv_namespaces]]
binding = "SESSIONS"
id = "xyz789..."          # Different namespace ID per environment.

[[env.production.d1_databases]]
binding = "DB"
database_name = "my-db-prod"
database_id = "..."

[env.production.placement]
mode = "smart"            # Smart Placement for production if origin-latency matters.
```

Key rules:
- `compatibility_date`: pin to a specific date; check Cloudflare's compatibility changelog before advancing.
- Separate resource IDs per environment — never share a KV namespace or D1 database between production and development.
- `main`: always explicit; never rely on convention defaults in production configs.
- Secrets are NOT declared in `wrangler.toml` — they are pushed via `wrangler secret put`.

### Multi-environment pattern

Two approaches; pick one per project:

1. **Environment stanzas in one file**: `[env.production]`, `[env.staging]`, `[env.development]` in a single `wrangler.toml`. Simpler for small teams; harder to audit environment differences.
2. **Separate files per environment**: `wrangler.staging.toml`, `wrangler.production.toml`. Deploy with `wrangler deploy --config wrangler.production.toml`. Easier to audit; harder to keep in sync.

For production systems with strict environment separation, prefer separate files.

### Local development

- `wrangler dev` runs a local development server. Bindings are simulated locally or can connect to remote resources (KV, D1, R2) with `--remote`.
- `wrangler dev --remote` uses your real account resources — use it with caution; writes are real.
- Use `.dev.vars` for local secrets (same format as `.env`). This file must be in `.gitignore`.

## Terraform `cloudflare/cloudflare` ≥ 5.x

### v5 breaking changes from v4

v5 of the Cloudflare Terraform provider introduced significant breaking changes. Do not copy v4 HCL into a v5 project without reviewing the migration guide.

Key changes:
- **Resource renames**: `cloudflare_page_rule` removed — use `cloudflare_ruleset` (Cache Rules, Transform Rules). `cloudflare_access_*` → `cloudflare_zero_trust_access_*`.
- **Zone ID handling**: some resources that previously accepted `zone_name` now require `zone_id` exclusively.
- **DNS records**: account-scoped DNS moved; ensure zone IDs are explicit on all `cloudflare_record` resources.
- **WAF managed rules**: `cloudflare_waf_rule` removed; configure via `cloudflare_ruleset` with `phase = "http_request_firewall_managed"`.
- Consult the [official v5 migration guide](https://registry.terraform.io/providers/cloudflare/cloudflare/latest/docs/guides/version-5-upgrade-guide) before any migration.

### Provider and version pinning

```hcl
terraform {
  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 5.0"   # Pin to major.minor; allow patch updates.
    }
  }
  required_version = ">= 1.6"
}
```

Always check in `.terraform.lock.hcl`.

### State management

- Remote state in S3 (or Terraform Cloud / Spacelift). For a pure Cloudflare project, R2 with S3-compatible state is a natural fit (zero egress for Terraform plan/apply runs from CI).
- Separate state files per environment — never run one `terraform apply` that covers both staging and production.
- Mark sensitive outputs with `sensitive = true` so they do not appear in CI logs.

### Key resources (v5)

```hcl
# Worker deployment
resource "cloudflare_worker_script" "api" {
  account_id = var.account_id
  script_name = "my-api"
  content    = file("dist/worker.js")

  kv_namespace_binding {
    name         = "SESSIONS"
    namespace_id = cloudflare_workers_kv_namespace.sessions.id
  }
}

# DNS record
resource "cloudflare_record" "api" {
  zone_id = var.zone_id
  name    = "api"
  content = "workers.dev"  # or actual origin IP for non-Workers
  type    = "CNAME"
  proxied = true
}

# Zero Trust Access application (v5 name)
resource "cloudflare_zero_trust_access_application" "internal_tool" {
  account_id = var.account_id
  name       = "Internal Tool"
  domain     = "tool.example.com"
  type       = "self_hosted"
}
```

### IaC-managed vs Wrangler-managed

Draw a clean boundary:
- **Wrangler manages**: Worker code, bindings, routes, Cron Triggers, `wrangler secret put` for secrets.
- **Terraform manages**: DNS records, WAF rulesets, Access applications and policies, Load Balancers, R2 buckets, D1 databases, Zero Trust policies, Logpush jobs.
- **Never both**: don't manage the same resource in Wrangler AND Terraform — they will drift against each other.

## GitHub Actions CI/CD

### API token scoping (critical)

Never use a global Cloudflare API key in CI. Create scoped API tokens per environment with the minimum required permissions:

- Workers deploy: `Account > Workers Scripts: Edit` + `Zone > Workers Routes: Edit` for the specific zone.
- Pages deploy: `Account > Cloudflare Pages: Edit`.
- DNS-only: `Zone > DNS: Edit` for the specific zone.
- Terraform apply (full): `Account > Account Settings: Read` + zone/account permissions matching resources managed.

Store tokens in GitHub Actions secrets (`CLOUDFLARE_API_TOKEN_PROD`, `CLOUDFLARE_API_TOKEN_STAGING`). Use separate tokens per environment.

### Workers deploy workflow

```yaml
name: Deploy Worker

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    permissions:
      contents: read

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: '20'

      - run: npm ci

      - run: npm test       # Run unit tests before deploy.

      - name: Deploy to production
        run: npx wrangler deploy --env production
        env:
          CLOUDFLARE_API_TOKEN: ${{ secrets.CLOUDFLARE_API_TOKEN_PROD }}
```

### Terraform workflow

```yaml
name: Terraform

on:
  pull_request:
    paths: ['infra/**']
  push:
    branches: [main]
    paths: ['infra/**']

jobs:
  plan:
    if: github.event_name == 'pull_request'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: "~1.8"
      - run: terraform init
        working-directory: infra/
        env:
          CLOUDFLARE_API_TOKEN: ${{ secrets.CLOUDFLARE_API_TOKEN_TF }}
      - run: terraform plan -out=tfplan
        working-directory: infra/
        env:
          CLOUDFLARE_API_TOKEN: ${{ secrets.CLOUDFLARE_API_TOKEN_TF }}
      # Post plan output as PR comment (use a helper action).

  apply:
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    runs-on: ubuntu-latest
    environment: production    # Require manual approval via GitHub environment protection.
    steps:
      - uses: actions/checkout@v4
      - uses: hashicorp/setup-terraform@v3
      - run: terraform init && terraform apply -auto-approve
        working-directory: infra/
        env:
          CLOUDFLARE_API_TOKEN: ${{ secrets.CLOUDFLARE_API_TOKEN_TF }}
```

### Workers Builds (Cloudflare-native CI)

Cloudflare Workers Builds runs builds directly on Cloudflare's infrastructure — no external CI runner needed for simple Workers projects.

- Connect the GitHub repository in the Workers dashboard; configure the build command and deploy command.
- Secrets injected at build time via the Workers Builds dashboard (separate from runtime secrets).
- Best fit for: simple Workers with no complex test suite or multi-environment Terraform. For complex pipelines, GitHub Actions gives more control.

### Pages CI

- For Pages projects, connect the GitHub repository in the Pages dashboard.
- Set build command (`npm run build`), build output directory (`dist/`), and environment variables per branch (preview vs production).
- Pages automatically creates a preview deployment for every pull request on its own `.pages.dev` subdomain — useful for PR review.
- For Pages Functions (edge logic attached to a Pages site), declare bindings in the Pages project settings or in `wrangler.toml` with `pages_build_output_dir`.

## Secret management

### Workers secrets

- Push secrets with: `wrangler secret put SECRET_NAME --env production`
- Secrets are encrypted at rest, scoped to the Worker and environment, and accessible as `env.SECRET_NAME` at runtime.
- Secrets are NOT visible in `wrangler.toml`, `wrangler secret list` (only names are shown), or in the dashboard.
- Rotation: `wrangler secret put SECRET_NAME --env production` overwrites the existing value with zero downtime.
- For CI/CD: use `echo "$SECRET_VALUE" | wrangler secret put SECRET_NAME --env production` — pipe from a masked CI secret to avoid the interactive prompt.
- Never store secrets in `wrangler.toml` or `.dev.vars` (except `.dev.vars` for local dev — which must be `.gitignore`d).

### Terraform-managed secrets

- For secrets managed alongside Terraform resources (e.g., D1 passwords, API keys for other services): use a secrets store (AWS Secrets Manager, HashiCorp Vault, or 1Password Secrets Automation) and inject at apply time.
- Do not store plaintext secrets in `terraform.tfvars` or `variables.tf` defaults.
- Mark sensitive variables and outputs with `sensitive = true`.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Global Cloudflare API key in CI | Key compromise = full account access. Use scoped tokens. |
| Hardcoding `account_id` or `zone_id` in Worker code | IDs differ between accounts; use `wrangler.toml` bindings and environment stanzas. |
| Copying v4 Terraform resource names to a v5 provider config | v5 renamed/removed several resources; the apply will fail or produce incorrect infrastructure. Read the migration guide. |
| Sharing a KV namespace or D1 database between staging and production | A migration or bulk write in staging corrupts production data. Separate resource IDs per environment. |
| `wrangler deploy` from a developer laptop to production | No audit trail, no test gate, no approval. Production deploys from CI only. |
| Secrets in `.dev.vars` committed to the repo | `.dev.vars` is for local dev only. Add it to `.gitignore` before the first commit. |
| `wrangler deploy` without running tests | A deploy that bypasses tests will eventually ship a regression. Test first, always. |
| Mixing Wrangler and Terraform management of the same resource | The two will drift and fight each other. Draw a clean boundary. |

## Security defaults

- Scoped API tokens per environment, per CI pipeline, per person. No global API keys.
- CI workflows use `permissions: contents: read` (minimum GitHub Actions permissions) and environment protection rules for production.
- `wrangler secret put` for all runtime secrets; never `wrangler.toml` plaintext.
- `.dev.vars` in `.gitignore`; `.gitignore` checked in before first commit.
- Terraform state in R2 or S3 with encryption at rest; state access restricted to CI service account.
- Wrangler version pinned in `devDependencies`; `npm ci` in CI (not `npm install`).

## Observability hints

- Every deployment should emit a marker (e.g., write a KV key `last_deploy_at = <timestamp, git SHA>`) so you can correlate a production issue to a deployment time.
- Use `wrangler tail` immediately after a production deploy to verify live traffic is behaving as expected.
- Terraform: use `terraform plan` output as a PR comment (with a helper action) so reviewers understand what will change before approving the apply.

## Cost considerations

- Wrangler CLI: free. Workers Builds: free tier (500 builds/month); paid beyond that.
- Terraform runs: free if self-hosted on GitHub Actions; pay for compute only. Terraform Cloud costs scale with team size.
- Pages: free tier includes 500 builds/month; unlimited Pages deployments on free (within limits). No per-request cost for Pages static assets served from Cloudflare's CDN.
- API tokens: free to create; no charge per token.
- Test environments: use Workers `wrangler dev` (local) to avoid consuming paid plan quotas during development.

## Verification checklist

- [ ] `compatibility_date` pinned; changelog reviewed before advancing.
- [ ] Separate resource IDs (KV, D1, R2, etc.) per environment — no sharing between staging and production.
- [ ] All secrets managed via `wrangler secret put`; `.dev.vars` in `.gitignore`.
- [ ] Scoped API tokens in CI; no global API key; separate tokens per environment.
- [ ] Tests run in CI before `wrangler deploy`; production deploys gate on test pass.
- [ ] Terraform provider pinned to `~> 5.0`; `.terraform.lock.hcl` checked in.
- [ ] Wrangler and Terraform manage distinct resource types — no overlap.
- [ ] Terraform state in remote backend with encryption; access restricted to CI.
- [ ] Production Terraform apply requires manual approval (GitHub environment protection or equivalent).
- [ ] v4 → v5 migration guide consulted if any existing v4 Terraform is being adopted.
