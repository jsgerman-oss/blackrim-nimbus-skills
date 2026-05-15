# cloud-netlify

Netlify development toolkit for Claude Code. Loads as a plugin from the parent `plugins/` marketplace.

<!-- BEGIN: what's inside -->
## What's inside

**Skills** — invoked automatically by description match, or with `/<skill-name>`:

| Skill | Description |
| --- | --- |
| `netlify-builds-and-deploys` | Configure or debug Netlify builds and deployments — netlify.toml, build environment, Deploy Previews, Branch Deploys, Atomic Deploys, Instant Rollback, Build Plugins, framework presets, Skip CI, and build minutes budgeting. Use when setting up a new site, tuning build performance, debugging a broken deploy, or reviewing CI/CD posture. |
| `netlify-data` | Design or implement Netlify's data layer — Netlify Blobs (persistent key-value storage, deploy-scoped vs site-wide), Forms (spam mitigation, reCAPTCHA, Akismet), Netlify Connect (Enterprise data caching layer), and third-party integrations (Supabase, Auth0, Stripe). Use when adding persistent state to a JAMstack site, wiring up a contact form, or choosing between Netlify-native data and an external database. |
| `netlify-functions-and-edge` | Design, implement, or audit Netlify serverless compute — Serverless Functions (Node.js / Go), Edge Functions (Deno runtime), Background Functions (async long-running), Scheduled Functions (cron), Blobs reads from functions, and geographic routing at the edge. Use when adding an API endpoint, customizing request handling, running cron jobs, or deciding between Functions and Edge Functions. |
| `netlify-iac-and-deployment` | Manage Netlify infrastructure-as-code and deployment — `netlify.toml` as the primary IaC surface, Netlify CLI (v17+), Build Plugins (`@netlify/plugin-*`), GitHub / GitLab / Bitbucket Git provider integration, deploy hooks, `netlify deploy --prod`, and the community Terraform `netlify/netlify` provider. Use when setting up a new site from code, scripting deployments in CI, wiring Git provider webhooks, or auditing the deployment pipeline. |
| `netlify-identity-and-security` | Design or audit Netlify identity and security posture — Netlify Identity (Gotrue), Visitor Access (basic auth / role-based at edge), site password protection, Single Sign-On, JWT secrets, environment variable scoping (Functions vs Build vs Runtime), DDoS / WAF (Pro+ and Enterprise), and security headers via `_headers` / `netlify.toml`. Use when locking down a site, implementing authentication, rotating secrets, or reviewing a security posture before launch. |
| `netlify-observability-and-cost` | Set up or audit Netlify observability and cost management — server-side Analytics, Function / Edge Function / Build logs, Logs Drain (Datadog / Logflare), Real User Monitoring, bandwidth and build minutes dashboards, billing tiers (Starter / Pro / Enterprise), and spend cap configuration. Use when adding telemetry to a Netlify site, diagnosing a cost spike, or planning a billing tier decision. |

**Sub-agents** — call explicitly via `subagent_type`:

| Agent | Description |
| --- | --- |
| `netlify-architect` | Netlify architecture reviewer. Use when the user asks for an architecture review, "is this design appropriate for Netlify", a pre-launch audit, or wants a structured assessment of JAMstack fit, edge-vs-function placement, data tier choice, security posture, and cost across build minutes / bandwidth / function invocations. |
| `netlify-security-reviewer` | Netlify security reviewer. Use when the user asks for a security audit, Deploy Preview access review, env var scope check, security headers audit, JWT secret rotation guidance, Forms spam posture, SSO / RBAC review, or wants to validate posture before a public launch. |

**Slash commands:**

| Command | Description |
| --- | --- |
| `/netlify-scaffold-project` | Scaffold a Netlify site configuration — netlify.toml, _headers, _redirects, Functions and Edge Functions starters, environment variable split, Build Plugin example, and a GitHub Actions CI pipeline for preview and production deploys. |
<!-- END: what's inside -->

## Install

This plugin ships inside the Blackrim.dev repo's `plugins/` marketplace. From a Claude Code session:

```text
/plugin marketplace add /Users/jayse/Code/blackrim/plugins
/plugin install cloud-netlify@blackrim-cloud-toolkits
```

## Design principles

1. **Defaults are production-grade, not demo-grade.** Security headers shipped via `_headers`. Deploy Previews behind Visitor Access for private codebases. Env vars scoped explicitly to the surface that needs them.
2. **JAMstack-first, honest about limits.** Netlify excels at statically-rendered and incrementally-generated sites with lightweight function backends. Full-stack Node applications with persistent connections, stateful long-running processes, or complex queue workers may fit better on Fly.io, Render, or Railway — this skill surfaces those tradeoffs explicitly.
3. **Cost is tracked at every layer.** Build minutes, bandwidth, function invocations, and add-on charges each have their own line on the bill. This toolkit flags them at decision time.
4. **Observability before launch.** No site ships without structured function logs, at least one alertable condition, and a spend cap configured.
5. **`netlify.toml` over dashboard.** Dashboard clicks are fine for exploration. Everything reviewable, diffable, and repeatable belongs in `netlify.toml` or `_headers` / `_redirects` committed to the repo.

## Conventions

- Skills assume the Netlify CLI v17+ is installed (`netlify --version`) and the site is linked (`netlify link`).
- Build image defaults to Ubuntu 22.04 (Jammy). Node.js version is pinned via `[build.environment] NODE_VERSION`.
- Framework presets (Next.js, Astro, SvelteKit, Nuxt, Vite) are called out where they diverge from the generic flow.
- All examples assume a single Netlify team / site first; Enterprise org-level policies are called out where they change the answer.
- Terraform examples use the community `netlify/netlify` provider; treat it as best-effort since it lags the Netlify API.
