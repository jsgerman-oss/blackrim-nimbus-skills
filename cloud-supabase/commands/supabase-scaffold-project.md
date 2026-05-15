---
description: Scaffold a new Supabase project — supabase/ directory with migrations, Edge Functions, config.toml, local dev Docker setup, GitHub Actions CI for db diff / linting / migration apply, env splits (local / preview / staging / prod), and client library bootstrap.
argument-hint: <workload-description>
---

# Supabase Scaffold Project

Scaffold a new Supabase project for a workload described as: **$ARGUMENTS**

## What to do

1. **Confirm project details** with up to three questions if not obvious:
   - Is this a hosted Supabase project (supabase.com) or self-hosted (Docker / Kubernetes)?
   - What is the primary framework? (Next.js, SvelteKit, Remix, plain TypeScript, Python, etc.)
   - What authentication methods are needed? (email, OAuth — which providers, phone)
   
   Do not ask about things you can infer from the workload description. Proceed after confirming.

2. **Generate the project skeleton** in the current working directory (or a subdirectory the user picks). Every scaffold must include the structure below and the security, CI, and env-split defaults described in this command.

3. **Wire all security defaults** — RLS on every table from the start, `service_role` never in client bundles, email confirmation on, MFA available.

4. **Print next steps** — commands the user must run to link to a hosted project, apply initial migrations, and deploy.

---

## Project structure

```
.
├── supabase/
│   ├── config.toml                     # Project config (committed, no secrets)
│   ├── migrations/
│   │   └── 20240101000000_init.sql     # Initial schema with RLS enabled
│   ├── functions/
│   │   └── _shared/
│   │       └── cors.ts                 # Shared CORS headers helper
│   ├── seed.sql                        # Local dev seed data (non-sensitive)
│   └── .gitignore                      # Excludes .env files
├── src/
│   ├── lib/
│   │   ├── supabase-client.ts          # Browser client (anon key)
│   │   └── supabase-server.ts          # Server client (for SSR frameworks)
│   └── types/
│       └── supabase.ts                 # Generated — do not edit by hand
├── .env.local.example                  # Template for local dev secrets
├── .gitignore
└── .github/
    └── workflows/
        ├── supabase-pr-check.yml       # Migration diff + RLS lint on PR
        └── supabase-deploy.yml         # Deploy migrations + functions on merge to main
```

---

## Files to generate

### supabase/config.toml

```toml
[project]
project_id = "replace-with-your-project-ref"

[api]
enabled = true
port = 54321
schemas = ["public", "graphql_public"]
extra_search_path = ["public", "extensions"]
max_rows = 1000

[db]
port = 54322
shadow_port = 54320
major_version = 15

[studio]
enabled = true
port = 54323

[auth]
enabled = true
# Update site_url before going to production
site_url = "http://localhost:3000"
additional_redirect_urls = ["https://localhost:3000"]
jwt_expiry = 3600
enable_refresh_token_rotation = true
refresh_token_reuse_interval = 10

[auth.email]
enable_signup = true
enable_confirmations = true

# Uncomment to enable OAuth providers after adding credentials in the Dashboard
# [auth.external.google]
# enabled = true
# client_id = "env(GOOGLE_CLIENT_ID)"
# secret = "env(GOOGLE_CLIENT_SECRET)"

[realtime]
enabled = true

[storage]
enabled = true
file_size_limit = "50MiB"

[edge_runtime]
enabled = true
policy = "per_worker"
```

### supabase/migrations/20240101000000_init.sql

Generate the initial schema migration including:

1. Enable any required extensions (`vector`, `pg_cron`, `pg_net` if applicable to the workload).
2. Create the application tables inferred from the workload description.
3. **Enable RLS on every table immediately after creation** — never defer this.
4. Create basic policies for `authenticated` and `anon` roles appropriate to the use case.
5. Add indexes on foreign key columns and any column referenced in RLS `USING` clauses.

Example for a posts/comments app:

```sql
-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Posts table
CREATE TABLE public.posts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  title text NOT NULL CHECK (char_length(title) BETWEEN 1 AND 200),
  content text NOT NULL,
  published boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- RLS — immediately after table creation
ALTER TABLE public.posts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.posts FORCE ROW LEVEL SECURITY;

-- Policies
CREATE POLICY "users_select_published_or_own"
  ON public.posts FOR SELECT TO authenticated, anon
  USING (published = true OR user_id = auth.uid());

CREATE POLICY "users_insert_own"
  ON public.posts FOR INSERT TO authenticated
  WITH CHECK (user_id = auth.uid());

CREATE POLICY "users_update_own"
  ON public.posts FOR UPDATE TO authenticated
  USING (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

CREATE POLICY "users_delete_own"
  ON public.posts FOR DELETE TO authenticated
  USING (user_id = auth.uid());

-- Indexes
CREATE INDEX posts_user_id_idx ON public.posts (user_id);

-- updated_at trigger
CREATE OR REPLACE FUNCTION public.handle_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN NEW.updated_at = now(); RETURN NEW; END;
$$;

CREATE TRIGGER posts_updated_at
  BEFORE UPDATE ON public.posts
  FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();
```

### src/lib/supabase-client.ts (browser client)

```typescript
import { createBrowserClient } from "@supabase/ssr";
import type { Database } from "../types/supabase";

export function createClient() {
  return createBrowserClient<Database>(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  );
}
```

### src/lib/supabase-server.ts (server-side client — Next.js App Router example)

```typescript
import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import type { Database } from "../types/supabase";

export function createClient() {
  const cookieStore = cookies();
  return createServerClient<Database>(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll: () => cookieStore.getAll(),
        setAll: (cookiesToSet) => {
          cookiesToSet.forEach(({ name, value, options }) =>
            cookieStore.set(name, value, options)
          );
        },
      },
    }
  );
}

// For server actions or routes that need service role (admin operations only)
// NEVER export this to client components
export function createAdminClient() {
  return createServerClient<Database>(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_ROLE_KEY!, // Server only
    { cookies: { getAll: () => [], setAll: () => {} } }
  );
}
```

### .env.local.example

```bash
# Supabase — get these from your project's API settings
NEXT_PUBLIC_SUPABASE_URL=http://127.0.0.1:54321
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key-here

# Server-only — NEVER prefix with NEXT_PUBLIC_
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key-here

# Optional: external services
# OPENAI_API_KEY=sk-...
# STRIPE_SECRET_KEY=sk_test_...
# STRIPE_WEBHOOK_SECRET=whsec_...
```

### .gitignore additions

```
.env
.env.local
.env.*.local
supabase/.branches/
supabase/.temp/
```

### .github/workflows/supabase-pr-check.yml

```yaml
name: Supabase PR Check
on:
  pull_request:
    paths:
      - "supabase/migrations/**"
      - "supabase/config.toml"
      - "supabase/functions/**"

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

      - name: Validate all migrations apply cleanly
        run: supabase db reset

      - name: Check for RLS coverage gaps
        run: |
          UNCOVERED=$(supabase db query --local "
            SELECT tablename FROM pg_tables
            WHERE schemaname = 'public'
              AND tablename NOT IN (
                SELECT relname FROM pg_class
                WHERE relrowsecurity = true
                  AND relnamespace = 'public'::regnamespace
              );
          ")
          if [ -n "$UNCOVERED" ]; then
            echo "ERROR: Tables missing RLS:"
            echo "$UNCOVERED"
            exit 1
          fi
          echo "RLS coverage: all tables covered."

      - name: Diff against staging (detect uncommitted drift)
        env:
          SUPABASE_ACCESS_TOKEN: ${{ secrets.SUPABASE_ACCESS_TOKEN }}
        run: |
          supabase link --project-ref ${{ vars.SUPABASE_STAGING_REF }}
          DIFF=$(supabase db diff --linked --schema public)
          if [ -n "$DIFF" ]; then
            echo "ERROR: Schema drift detected between migrations and staging:"
            echo "$DIFF"
            exit 1
          fi

      - name: Stop local Supabase
        if: always()
        run: supabase stop
```

### .github/workflows/supabase-deploy.yml

```yaml
name: Deploy to Production
on:
  push:
    branches:
      - main

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: production  # Requires manual approval — configure in GitHub repository settings
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
        run: supabase functions deploy

      - name: Regenerate TypeScript types
        run: supabase gen types typescript --linked > src/types/supabase.ts

      - name: Commit updated types
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add src/types/supabase.ts
          git diff --cached --quiet || git commit -m "chore: regenerate supabase types [skip ci]"
          git push
```

---

## After scaffolding — next steps

Print these steps to the user:

### 1. Install dependencies

```bash
npm install @supabase/supabase-js @supabase/ssr
# If using Next.js:
npm install next
```

### 2. Start local development

```bash
# Install Supabase CLI if not present
brew install supabase/tap/supabase

# Start the local stack
supabase start

# Apply your initial migration
supabase db reset

# View Studio at http://localhost:54323
```

### 3. Link to a hosted project (when ready)

```bash
supabase link --project-ref <your-project-ref>
```

### 4. Configure GitHub Actions

Add these secrets to your GitHub repository (`Settings → Secrets and variables → Actions`):

- `SUPABASE_ACCESS_TOKEN`: your personal access token from supabase.com/account/tokens
- Repository variables: `SUPABASE_STAGING_REF`, `SUPABASE_PROD_REF`

Create a `production` environment in GitHub (`Settings → Environments`) with a required reviewer — this is the approval gate for production deploys.

### 5. Pre-launch security review

Before opening to real users, run `supabase-security-reviewer` on the generated schema to verify RLS coverage and auth configuration.

Hand off to `supabase-architect` for a review of the data model and auth design against the five architecture pillars.
