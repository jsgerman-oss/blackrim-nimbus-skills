---
name: supabase-deployment-and-iac
description: Design or implement Supabase deployment workflows — CLI (init, link, db push, db diff, migrations), supabase/config.toml, GitHub Actions pipelines for migrations and Edge Functions, environment promotion (local → dev → staging → prod), database branching with PR previews, self-hosting via Docker or Kubernetes, and Terraform with the supabase/supabase provider. Use when setting up a new project, wiring CI/CD, or planning self-hosting.
---

# Supabase Deployment and Infrastructure-as-Code

## When to use

- Setting up a new Supabase project from scratch with a proper local dev workflow.
- Wiring CI/CD for automated migration diffing, linting, and deployment.
- Designing an environment promotion strategy (local → preview → staging → prod).
- Planning or implementing Supabase self-hosting via Docker or Kubernetes.
- Using Terraform to manage Supabase project settings, secrets, and resource configuration.
- Setting up preview branches for pull requests.

## The Supabase CLI — core commands

Install: `brew install supabase/tap/supabase` or via `npm install supabase --save-dev`.

Version: pin ≥ 1.180 in CI to avoid silent behavior changes.

```bash
# Initialize a new project (creates supabase/ directory)
supabase init

# Link to a hosted project
supabase link --project-ref <project-ref>

# Start local development stack (Postgres, Auth, Storage, Realtime, Studio)
supabase start

# Stop local stack
supabase stop

# Create a new migration
supabase migration new <name>

# Apply migrations locally (reset and replay all)
supabase db reset

# Diff local schema against linked remote (detect drift)
supabase db diff --linked --schema public

# Push local migrations to linked remote
supabase db push

# Pull remote schema to generate a migration capturing current state
supabase db pull

# Deploy Edge Functions
supabase functions deploy <function-name>

# Manage secrets
supabase secrets set KEY=value
supabase secrets list

# Generate TypeScript types from the database schema
supabase gen types typescript --linked > src/types/supabase.ts
```

## supabase/config.toml

`supabase/config.toml` is the project configuration file, committed to version control. It drives both the local development stack and (when deployed) the hosted project configuration.

```toml
# supabase/config.toml
[project]
project_id = "your-project-ref"

[api]
enabled = true
port = 54321
schemas = ["public", "graphql_public"]
extra_search_path = ["public", "extensions"]
max_rows = 1000  # prevents unbounded SELECT without LIMIT

[db]
port = 54322
shadow_port = 54320
major_version = 15  # pin the Postgres version

[studio]
enabled = true
port = 54323

[auth]
enabled = true
site_url = "http://localhost:3000"
additional_redirect_urls = ["https://localhost:3000"]
jwt_expiry = 3600
enable_refresh_token_rotation = true
refresh_token_reuse_interval = 10

[auth.email]
enable_signup = true
enable_confirmations = true  # ALWAYS true in prod

[auth.hook.custom_access_token]
enabled = true
uri = "pg-functions://postgres/public/custom_access_token"

[functions.my-function]
verify_jwt = true

[realtime]
enabled = true
ip_version = "IPv6"

[storage]
enabled = true
file_size_limit = "50MiB"  # global default; override per bucket

[edge_runtime]
enabled = true
policy = "per_worker"
```

Commit `config.toml`. It must not contain secrets — use `supabase secrets set` for those.

## Project layout

```
.
├── supabase/
│   ├── config.toml               # Project configuration
│   ├── migrations/               # Ordered SQL migration files
│   │   ├── 20240101000000_init.sql
│   │   ├── 20240115120000_add_posts.sql
│   │   └── 20240201090000_add_rls_policies.sql
│   ├── functions/                # Edge Functions
│   │   ├── send-email/
│   │   │   └── index.ts
│   │   └── process-webhook/
│   │       └── index.ts
│   ├── seed.sql                  # Optional: seed data for local dev
│   └── .gitignore               # Exclude .env files
├── src/
│   ├── types/
│   │   └── supabase.ts          # Generated TypeScript types
│   └── lib/
│       └── supabase.ts          # Client initialization
├── .env.local                   # Local dev secrets (never commit)
└── .github/
    └── workflows/
        ├── supabase-migrate.yml
        └── supabase-deploy.yml
```

## Environment strategy

| Environment | Supabase project | Purpose |
| --- | --- | --- |
| Local | `supabase start` (Docker) | Developer-local, rapid iteration |
| Preview | Supabase database branch per PR | PR-scoped testing, auto-provisioned |
| Staging | Dedicated hosted project | Pre-production integration tests |
| Production | Dedicated hosted project | Live traffic |

Use separate Supabase projects for staging and production — never share a single project between environments. Environment-specific credentials are injected via CI/CD secrets; never committed.

## GitHub Actions — migration and deployment

### Migration diff and lint on PR

```yaml
# .github/workflows/supabase-migrate.yml
name: Supabase Migration Check
on:
  pull_request:
    paths:
      - "supabase/migrations/**"
      - "supabase/config.toml"

jobs:
  migration-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: supabase/setup-cli@v1
        with:
          version: latest

      - name: Start local Supabase
        run: supabase start

      - name: Validate migrations
        run: supabase db reset --debug

      - name: Diff against staging (detect drift)
        env:
          SUPABASE_ACCESS_TOKEN: ${{ secrets.SUPABASE_ACCESS_TOKEN }}
        run: |
          supabase link --project-ref ${{ vars.SUPABASE_STAGING_REF }}
          supabase db diff --linked --schema public

      - name: Check RLS coverage
        run: |
          supabase db query "
            SELECT tablename FROM pg_tables
            WHERE schemaname = 'public'
              AND tablename NOT IN (
                SELECT relname FROM pg_class
                WHERE relrowsecurity = true
                  AND relnamespace = 'public'::regnamespace
              );
          " | grep -q "0 rows" || (echo "Tables missing RLS!" && exit 1)
```

### Deploy migrations and functions to production

```yaml
# .github/workflows/supabase-deploy.yml
name: Deploy to Production
on:
  push:
    branches:
      - main

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: production  # requires manual approval in GitHub
    steps:
      - uses: actions/checkout@v4
      - uses: supabase/setup-cli@v1
        with:
          version: latest

      - name: Link to production project
        env:
          SUPABASE_ACCESS_TOKEN: ${{ secrets.SUPABASE_ACCESS_TOKEN }}
        run: supabase link --project-ref ${{ vars.SUPABASE_PROD_REF }}

      - name: Deploy migrations
        env:
          SUPABASE_ACCESS_TOKEN: ${{ secrets.SUPABASE_ACCESS_TOKEN }}
        run: supabase db push --linked

      - name: Deploy Edge Functions
        env:
          SUPABASE_ACCESS_TOKEN: ${{ secrets.SUPABASE_ACCESS_TOKEN }}
        run: supabase functions deploy --project-ref ${{ vars.SUPABASE_PROD_REF }}

      - name: Regenerate TypeScript types
        run: |
          supabase gen types typescript --linked > src/types/supabase.ts
          git add src/types/supabase.ts
          git diff --cached --quiet || git commit -m "chore: regenerate supabase types"
```

## Preview branches (PR previews)

With the Supabase GitHub integration enabled, each PR automatically provisions a database branch with migrations applied. Configure via Dashboard → Project Settings → Integrations → GitHub.

The branch connection string is available as a GitHub Actions environment variable (`SUPABASE_DB_URL`) for your PR preview deployments (Vercel, Netlify, etc.).

Branches are torn down automatically on PR close.

## Self-hosting — Docker Compose

Supabase publishes an official Docker Compose stack at `github.com/supabase/supabase`.

```bash
git clone --depth 1 https://github.com/supabase/supabase
cd supabase/docker
cp .env.example .env
# Edit .env: generate secrets for POSTGRES_PASSWORD, JWT_SECRET, ANON_KEY, SERVICE_ROLE_KEY
docker compose up -d
```

Key self-hosting considerations:

- **Secrets:** generate strong random values for `JWT_SECRET`, `POSTGRES_PASSWORD`, `ANON_KEY`, and `SERVICE_ROLE_KEY`. Use `openssl rand -base64 32` for each.
- **TLS:** terminate TLS at an upstream reverse proxy (nginx, Caddy, or a load balancer). Supabase Docker Compose does not handle TLS natively.
- **Email:** configure SMTP in the environment — the default Supabase inbucket is for local dev only.
- **Realtime:** runs as a separate container; scale horizontally by running multiple instances behind the load balancer.
- **Backups:** configure `pg_basebackup` or WAL archiving to an external store. There is no managed PITR in self-hosted — you own it entirely.
- **Updates:** pin specific image tags in Docker Compose; don't use `latest` in production. Update on a cadence after reviewing release notes.

### Self-hosting on Kubernetes

Use the Supabase Helm chart (`helm.supabase.com`) or the self-maintained community chart:

```bash
helm repo add supabase https://helm.supabase.com
helm install supabase supabase/supabase --values values.yaml
```

Run Postgres separately (Postgres operator like `cloudnative-pg`, or a managed Postgres like RDS / CloudSQL) and point the Supabase services at it. This is more maintainable than running Postgres inside Kubernetes for production workloads.

## Terraform — supabase/supabase provider

The Terraform provider manages project-level Supabase resources (settings, secrets, users, but not schema migrations).

```hcl
terraform {
  required_providers {
    supabase = {
      source  = "supabase/supabase"
      version = "~> 1.0"
    }
  }
}

provider "supabase" {
  access_token = var.supabase_access_token
}

resource "supabase_project" "prod" {
  organization_id = var.supabase_org_id
  name            = "my-app-prod"
  database_password = var.db_password  # sensitive
  region          = "us-east-1"
}

resource "supabase_settings" "prod" {
  project_ref = supabase_project.prod.id

  api = jsonencode({
    db_schema = "public,graphql_public"
    db_extra_search_path = "public,extensions"
    max_rows = 1000
  })

  auth = jsonencode({
    site_url = "https://myapp.com"
    disable_signup = false
    jwt_exp = 3600
  })
}
```

Note: Terraform manages project settings but **not** schema migrations. Always use the Supabase CLI for migrations; do not attempt to manage schema via Terraform data sources.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Editing migrations after they've been applied anywhere | Checksums diverge; `db push` will fail or skip changes silently. |
| Using the Dashboard SQL editor for production schema changes | No migration file created; drift accumulates between environments. |
| Sharing a single Supabase project across staging and prod | A bad migration in staging runs against prod data. Always separate projects. |
| Committing `.env` or secrets in config files | Supabase keys exposed in git history. Use `.gitignore` and CI/CD secrets. |
| `supabase db push` without a `db diff` review in CI | Blind push; a migration with a destructive operation (DROP COLUMN) ships without review. |
| Self-hosting without external Postgres backups | Supabase Docker Compose has no built-in backup. A volume failure = data loss. |
| Using `latest` Docker image tags in self-hosted production | Uncontrolled updates; a breaking change ships without notice. Pin versions. |

## Security defaults

- Each environment uses a separate Supabase project with isolated credentials.
- Staging uses different `ANON_KEY` and `SERVICE_ROLE_KEY` from production — a staging key leak does not affect production.
- Production deployment requires a manual approval gate in GitHub Actions (environment protection rule).
- `db push` is preceded by `db diff` review in CI — no surprise destructive migrations.
- TypeScript types regenerated and committed as part of the deploy job to keep client code in sync with schema.
- Self-hosted: TLS terminated at the load balancer; Postgres not exposed outside the private network; secrets generated with `openssl rand`.

## Observability defaults

- Migration timestamps: each migration filename starts with a UTC timestamp — you can correlate a schema change to a time window in logs.
- GitHub Actions workflow history provides an audit trail of who deployed what and when.
- Supabase Dashboard → Logs → Postgres Logs for query-level visibility post-migration.
- Self-hosted: ship Postgres logs to a centralized log aggregator (Loki, Elastic, etc.); pg_stat_statements for slow-query tracking.

## Cost considerations

- Hosted: each Supabase project is billed independently. A staging project at the free or Pro tier adds ~$25/mo; fold staging and prod into separate projects from day one.
- Preview branches: provisioned and torn down automatically; billed only for active branch time (Pro+).
- Self-hosted: infrastructure cost is yours to optimize. Supabase itself is MIT-licensed with no per-request fee. Primary costs: compute, managed Postgres, network egress.
- Terraform Cloud: not required; a local backend (S3 + DynamoDB lock) works fine for Supabase Terraform state.

## IaC hints

- Supabase CLI + migrations: the primary IaC path for schema. No alternatives.
- Terraform: project and settings management only; not a migration tool.
- `config.toml`: commit it; keep secrets out of it.
- GitHub Actions: use `environment: production` with required reviewers for prod deploys.
- Self-hosting Helm chart: use Helm's `--set-string` for secrets or an external secrets operator (External Secrets Operator → AWS Secrets Manager / Vault).

## Verification checklist

- [ ] `supabase/migrations/` contains all schema changes; no schema was applied via the Dashboard SQL editor.
- [ ] `supabase db diff --linked` shows no unexpected drift between migration history and remote schema.
- [ ] CI runs `supabase db reset` to validate the full migration stack applies cleanly from zero.
- [ ] CI runs an RLS coverage query and fails the build if any table is missing RLS.
- [ ] Production deploy has a manual approval gate.
- [ ] Separate Supabase projects for staging and production with independent credentials.
- [ ] TypeScript types are regenerated and committed on each schema change.
- [ ] Self-hosted: TLS on all external endpoints; Postgres not publicly exposed; backups tested.
- [ ] Docker image tags pinned in self-hosted production; update cadence documented.
- [ ] `.env` and secrets files are in `.gitignore`; no secrets in `config.toml`.
