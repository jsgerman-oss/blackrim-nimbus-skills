# cloud-railway

Railway development toolkit for Claude Code. Loads as a plugin from the parent `plugins/` marketplace.

<!-- BEGIN: what's inside -->
## What's inside

**Skills** — invoked automatically by description match, or with `/<skill-name>`:

| Skill | Description |
| --- | --- |
| `railway-data` | Design or audit Railway data management — Database Plugins (Postgres, MySQL, Redis, MongoDB), seeding strategies, connection strings via Reference Variables, backups and restore, scaling Plugins, and when to migrate off Plugins to external managed databases. Use when provisioning a Plugin, wiring a connection string, designing a seed/migration workflow, or assessing whether a Plugin is the right long-term choice. |
| `railway-networking` | Design or audit Railway networking — service-to-service communication via private domains (`<service>.railway.internal`), public domains with automatic TLS, custom domains, port detection from `$PORT`, TCP proxy for non-HTTP services, and sticky-session considerations. Use when connecting services internally, exposing a service to the internet, setting up a custom domain, or debugging connectivity. |
| `railway-observability-and-cost` | Set up or audit Railway observability and cost — built-in log streaming (live and historical), service Metrics (CPU / memory / network), the Observability dashboard (Pro plan), external log drains (Datadog, Better Stack, Logflare), Railway's per-second billing model, and a cadence for reviewing the Usage page. Use when adding telemetry to a service, wiring a log drain, diagnosing a cost spike, or setting up a regular billing review. |
| `railway-security-and-secrets` | Design or audit Railway security posture — Variables (per-service and shared), Reference Variables for cross-service secret injection, Service Tokens, project tokens, GitHub OAuth integration scope, secret rotation, deployment protection (Pro plan), and audit log access. Use when wiring secrets, scoping service access, rotating credentials, reviewing team permissions, or hardening a production project. |
| `railway-services` | Design, configure, or audit Railway Services — build source selection (Git repo / Dockerfile / pre-built image), Nixpacks auto-detect vs custom Dockerfile, build and start command overrides, restart policy, health checks, replicas (Pro plan), Volumes for persistent disk, and resource limits (vCPU + memory). Use when adding a new service, tuning build behavior, configuring persistent storage, or right-sizing resources. |
| `railway-templates-and-deployment` | Design or audit Railway deployment configuration — `railway.json` / `railway.toml` (build and deploy config), Railway CLI (≥ 3.x), Railway Templates (publishing and consuming), GitHub Actions integration with project tokens, environment promotion (dev → staging → production), preview environments (PR-based), and Volumes lifecycle in deploys. Use when configuring a deployment pipeline, publishing a Template, setting up preview environments, or promoting between environments. |

**Sub-agents** — call explicitly via `subagent_type`:

| Agent | Description |
| --- | --- |
| `railway-architect` | Railway architecture reviewer. Use when the user asks whether Railway is the right platform for a workload, wants an architecture review of an existing Railway project, needs a pre-launch reliability or cost audit, or wants findings across the five Railway architecture pillars (PaaS-fit, reliability, security, cost, portability). |
| `railway-security-reviewer` | Railway security reviewer. Use when the user wants a security audit of a Railway project, needs to review Variable scoping, Service Token hygiene, GitHub OAuth scope, public vs private domain exposure, Postgres connection-string handling, team MFA posture, or audit log review. |

**Slash commands:**

| Command | Description |
| --- | --- |
| `/railway-scaffold-project` | Scaffold a Railway project — railway.json, Dockerfile (or Nixpacks config), environment splits (development / staging / production), GitHub Actions deploy job with Service Token, Postgres Plugin wiring via Reference Variables, and PR preview environment setup. |
<!-- END: what's inside -->

## Install

This plugin ships inside the Blackrim.dev repo's `plugins/` marketplace. From a Claude Code session:

```text
/plugin marketplace add /Users/jayse/Code/blackrim/plugins
/plugin install cloud-railway@blackrim-cloud-toolkits
```

## Design principles

1. **Defaults are production-grade, not demo-grade.** Service Tokens scoped per environment, Reference Variables instead of hardcoded URLs, custom domain + TLS, health checks on every service.
2. **Be honest about Railway's positioning.** Railway is exceptional for early-stage products, internal tools, hobby projects, and small-to-medium team workloads. High-volume production traffic, sub-10ms SLA databases, and complex compliance regimes are where you hit the ceiling — this toolkit surfaces those inflection points explicitly.
3. **Railway-native patterns first.** Nixpacks auto-detection, Reference Variables, Preview Environments, and the Railway CLI are first-class. Raw environment variable strings and manual deploy scripts are red flags.
4. **Cost is per-second usage.** The billing model rewards right-sizing; idle resources still cost. Every skill flags the cost dimension at decision time.
5. **Stateless services, managed data.** Stateless services behind Railway are easy to scale and replace. Serious production databases belong in a dedicated managed provider (Neon, PlanetScale, Supabase, Aiven), not a Railway Plugin — the toolkit is clear about this inflection point.

## Conventions

- Skills assume the Railway CLI ≥ 3.x is installed (`railway --version`) and a project is linked (`railway link`).
- Config examples target `railway.json` (project-level) and `railway.toml` (service-level), current as of 2026-05.
- Environment names are explicit — no implicit `production` magic.
- Examples assume a single-project setup first; multi-project / multi-team patterns are noted where they change the answer.
