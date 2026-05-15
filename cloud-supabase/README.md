# cloud-supabase

Supabase development toolkit for Claude Code. Loads as a plugin from the parent `plugins/` marketplace.

Supabase is a Postgres-backed Backend-as-a-Service providing Auth, Realtime, Storage, Edge Functions, and Vector search. It runs on hosted infrastructure (supabase.com) or self-hosted via Docker or Kubernetes. The skills here apply to both, calling out where behavior differs.

<!-- BEGIN: what's inside -->
## What's inside

**Skills** — invoked automatically by description match, or with `/<skill-name>`:

| Skill | Description |
| --- | --- |
| `supabase-auth` | Design or implement Supabase Auth — email/password, magic links, OAuth providers, phone/SMS, MFA (TOTP and WebAuthn/passkeys), JWT structure and custom claims, auth hooks, session management, server-side auth with cookies, and auth redirects. Use when choosing an auth method, designing a user flow, auditing JWT handling, or wiring auth hooks. |
| `supabase-deployment-and-iac` | Design or implement Supabase deployment workflows — CLI (init, link, db push, db diff, migrations), supabase/config.toml, GitHub Actions pipelines for migrations and Edge Functions, environment promotion (local → dev → staging → prod), database branching with PR previews, self-hosting via Docker or Kubernetes, and Terraform with the supabase/supabase provider. Use when setting up a new project, wiring CI/CD, or planning self-hosting. |
| `supabase-edge-functions-and-vector` | Build or audit Supabase Edge Functions (Deno runtime, secrets, regions, background tasks, WebSockets, scheduled functions via pg_cron) and Vector / pgvector (HNSW vs IVF indexes, embedding workflows, Supabase AI client, OpenAI / Anthropic / local model integration). Use when writing server-side logic at the edge, scheduling jobs, or implementing semantic search and retrieval-augmented generation. |
| `supabase-postgres-and-rls` | Design or audit Supabase Postgres schemas, Row Level Security (RLS) policies, roles, migrations, connection pooling (Supavisor), read replicas, database branching, and point-in-time recovery. Use when modeling data, writing policies, sizing a database, or reviewing the security posture of a schema. |
| `supabase-security-and-compliance` | Audit or harden the security posture of a Supabase project — RLS coverage on every table, service_role discipline, JWT verification, secret management, database password rotation, MFA enforcement, network restrictions (IP allowlists), SOC 2 Type II / HIPAA tier requirements, and audit logging. Use when reviewing a project before launch, running a security audit, or responding to a compliance requirement. |
| `supabase-storage-and-realtime` | Design or implement Supabase Storage (buckets, RLS for objects, image transformations, signed URLs, resumable uploads via TUS) and Realtime (Postgres changes via WAL, Broadcast, Presence, channel auth, scaling). Use when storing files, serving user-generated content, streaming database changes, or building collaborative features. |

**Sub-agents** — call explicitly via `subagent_type`:

| Agent | Description |
| --- | --- |
| `supabase-architect` | Supabase architecture reviewer. Use when the user asks for an architecture review, data model feedback, "is this design sound", a pre-launch audit, or wants findings across the four Supabase architecture pillars (data modeling, auth design, scalability, security, cost). |
| `supabase-security-reviewer` | Supabase security reviewer. Use when the user asks for a security audit, RLS coverage review, pre-launch security check, incident-readiness review, or wants to validate posture against Supabase security best practices. Anchors to RLS coverage as the primary control — every table reviewed, every policy tested. |

**Slash commands:**

| Command | Description |
| --- | --- |
| `/supabase-scaffold-project` | Scaffold a new Supabase project — supabase/ directory with migrations, Edge Functions, config.toml, local dev Docker setup, GitHub Actions CI for db diff / linting / migration apply, env splits (local / preview / staging / prod), and client library bootstrap. |
<!-- END: what's inside -->

## Hosted vs self-hosted

| Concern | Hosted (supabase.com) | Self-hosted |
| --- | --- | --- |
| Postgres version | Managed, currently 15 / 16 | You control — pin explicitly |
| Auth | Managed GoTrue | Self-hosted GoTrue (Docker) |
| Realtime | Managed, Elixir cluster | Self-hosted, tune replicas manually |
| Edge Functions | Managed Deno runtime | Self-hosted via `supabase/edge-runtime` |
| Connection pooling | Supavisor managed | Self-hosted Supavisor |
| Network restrictions | Dashboard IP allowlists | Firewall / SG at your infra layer |
| SOC 2 / HIPAA | Available on Enterprise plan | Your responsibility entirely |
| Point-in-time recovery | Available on Pro+ | Configure WAL archiving yourself |

## Install

This plugin ships inside the Blackrim.dev repo's `plugins/` marketplace. From a Claude Code session:

```text
/plugin marketplace add /Users/jayse/Code/blackrim/plugins
/plugin install cloud-supabase@blackrim-cloud-toolkits
```

## Design principles

1. **RLS is not optional.** Row Level Security is Supabase's primary data-access control mechanism. Every table in a Supabase database must have RLS enabled and at least one explicit policy. Unprotected tables are a security failure, not a to-do item.
2. **`service_role` stays on the server.** The service role key bypasses all RLS policies. Exposing it in a client bundle, a frontend env var, or a public repo is equivalent to disabling all your access controls.
3. **Postgres-first, BaaS-second.** Supabase exposes Postgres. Design your schema, constraints, indexes, and types in Postgres terms first; the REST / GraphQL / Realtime surfaces follow from the schema.
4. **Migrations are the source of truth.** Never alter production schema via the dashboard SQL editor or Studio without capturing the change in a migration file. `supabase db diff` is your net.
5. **Cost is a first-class concern.** Realtime concurrent connections, Storage egress, Edge Function invocations, and database compute all appear on the bill. Choices that affect these should surface cost implications at decision time.

## Conventions

- Skills assume the Supabase CLI (≥ 1.180) is installed and `supabase link` has been run for hosted projects.
- All examples target Postgres 15 / 16 and Deno 1.45+ for Edge Functions.
- RLS examples use the `auth.uid()` and `auth.role()` helpers from the Supabase `auth` schema.
- Self-hosting references the official `supabase/supabase` Docker Compose stack.
- Terraform references the `supabase/supabase` Terraform provider.
