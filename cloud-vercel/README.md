# cloud-vercel

Vercel development toolkit for Claude Code. Loads as a plugin from the parent `plugins/` marketplace.

<!-- BEGIN: what's inside -->
## What's inside

**Skills** — invoked automatically by description match, or with `/<skill-name>`:

| Skill | Description |
| --- | --- |
| `vercel-data` | Choose and configure Vercel-native data stores — Vercel KV (Upstash Redis), Vercel Postgres (Neon-backed), Vercel Blob (object storage), Edge Config (low-latency read-only), and marketplace integrations (Neon, Upstash, MongoDB Atlas, Supabase). Use when picking a data layer for a Vercel project, sizing storage, or evaluating portability tradeoffs. |
| `vercel-deployments` | Design, configure, or debug Vercel deployments — Production / Preview / Branch deploys, Git integrations (GitHub / GitLab / Bitbucket), monorepo configuration, build caching, build environment variables, framework presets (Next.js / SvelteKit / Astro / Remix / Nuxt / Vite), build skipping, and immutable deployments. Use when setting up a new project, tuning build performance, diagnosing a failed deploy, or choosing framework preset settings. |
| `vercel-functions-and-edge` | Design or configure Vercel compute — Edge Functions (V8 isolates), Edge Middleware, Serverless Functions (Node.js / Python), Streaming responses, ISR and on-demand revalidation, Image Optimization, Cron Jobs, Edge Config, and function memory / duration limits per plan. Use when choosing where to run code, tuning cold start, implementing middleware, or wiring ISR revalidation. |
| `vercel-iac-and-deployment` | Configure or audit Vercel deployment infrastructure — vercel.json (rewrites, redirects, headers, function config), Vercel CLI, Git integration vs vercel deploy, GitHub Actions for PR previews and production deploys, Turborepo for monorepos, environment variable promotion (Dev → Preview → Production), and the community Terraform vercel/vercel provider. Use when setting up a new project's deployment pipeline, debugging routing, or codifying Vercel config in IaC. |
| `vercel-identity-and-security` | Design or audit Vercel identity and security posture — team membership and roles, Project / Team access controls, Vercel Authentication (SSO), Deployment Protection (Vercel Auth, Password, Trusted IPs, Bypass tokens), WAF (custom + managed rules), DDoS mitigation, Attack Challenge Mode, environment variable encryption, and Sensitive flag usage. Use when hardening a project before launch, onboarding a new team, or auditing access controls. |
| `vercel-observability-and-cost` | Wire up or audit Vercel observability and cost — Web Analytics (privacy-first, no cookies), Speed Insights (Core Web Vitals), Logs (real-time + Logs Drains to Datadog / Logflare / etc.), OpenTelemetry traces, Spend Management (budgets, hard limits), and tracking edge / function / bandwidth / image-optimization consumption. Use when adding telemetry, investigating a performance regression, or controlling a growing bill. |

**Sub-agents** — call explicitly via `subagent_type`:

| Agent | Description |
| --- | --- |
| `vercel-architect` | Vercel architecture reviewer. Use when the user asks for an architecture review, "is this design sound for Vercel", a pre-launch audit, or wants findings across five pillars — edge/framework alignment, data locality, security posture, cost profile, and developer experience. Also use for evaluating portability tradeoffs and platform lock-in exposure. |
| `vercel-security-reviewer` | Vercel security reviewer. Use when the user asks for a security audit, pre-launch security check, Deployment Protection review, env var sensitivity audit, or wants to validate WAF posture, security headers, secrets rotation, and third-party data boundaries for a Vercel project. |

**Slash commands:**

| Command | Description |
| --- | --- |
| `/vercel-scaffold-project` | Scaffold a Next.js-on-Vercel project (or SvelteKit / Astro alternative) with vercel.json, env-var scope split, monorepo-aware Turborepo config, GitHub Actions for preview and production deploys, and an optional Terraform skeleton using the vercel/vercel provider. |
<!-- END: what's inside -->

## Install

This plugin ships inside the Blackrim.dev repo's `plugins/` marketplace. From a Claude Code session:

```text
/plugin marketplace add /Users/jayse/Code/blackrim/plugins
/plugin install cloud-vercel@blackrim-cloud-toolkits
```

## Design principles

1. **Edge-first by default, not edge-always.** Push latency-sensitive reads to the edge; keep compute-heavy or stateful work in regional Serverless Functions. Don't route everything through Edge Functions because they're new and shiny.
2. **Deployment Protection on for every preview.** Unauthenticated preview URLs are a data-leak vector. Vercel Auth or Password Protection is mandatory unless explicitly opted out.
3. **Secure env vars for secrets, never plain.** The "Sensitive" flag prevents values from being logged or returned via API — use it for any credential, token, or key.
4. **Cost and usage are visible before they surprise you.** Spend Management limits are set at project creation, not after the first overrun invoice.
5. **Framework preset is a convention, not a contract.** Know which build command and output directory the preset maps to so you can override when needed.
6. **Lock-in is real and worth naming.** Edge Middleware, ISR on-demand revalidation, and Image Optimization are Vercel-specific. This toolkit documents portability tradeoffs honestly.

## Conventions

- Skills assume Vercel CLI ≥ 39.x is installed (`vercel --version`) and the project is linked (`vercel link`).
- Next.js examples target ≥ 15.x (App Router primary; Pages Router called out where behavior differs).
- The `vercel/vercel` Terraform provider is community-maintained (≥ 1.x); Vercel does not publish an official provider.
- All examples assume a single team and project unless monorepo is explicitly the context.
- Framework versions are pinned in examples — no implicit latest-minor upgrade surprises.
