# cloud-render

Render development toolkit for Claude Code. Loads as a plugin from the parent `plugins/` marketplace.

<!-- BEGIN: what's inside -->
## What's inside

**Skills** — invoked automatically by description match, or with `/<skill-name>`:

| Skill | Description |
| --- | --- |
| `render-blueprints-and-deployment` | Design or audit Render Blueprints and deployment — render.yaml Blueprint IaC (the recommended path), PR Preview environments, build / start commands, build caching, secret env var management, render-cli, Terraform render-oss/render provider, GitHub / GitLab integration. Use when setting up a new Blueprint, configuring preview environments, or reviewing a deployment pipeline. |
| `render-identity-and-security` | Design or audit Render identity and security posture — Teams and member roles, Personal API tokens, Environment Groups, Secret Files, IP Access Control, SSO, SOC 2 posture, audit logs, GitHub/GitLab OAuth scopes. Use when configuring team access, managing secrets, reviewing credential hygiene, or hardening a Render account. |
| `render-networking-and-edge` | Design or audit Render networking and edge — custom domains with automatic TLS, Private Services mesh, HTTP/2, IP allowlists, DDoS posture, regional placement, and HTTPS enforcement. Use when exposing a service, connecting services internally, restricting access, or reviewing edge security. |
| `render-observability-and-cost` | Wire up or audit Render observability and cost — built-in metrics (CPU, memory, request rate, response time), log streams and retention, Datadog / New Relic / Logtail integrations, alerts, billing by service plan and hours, free tier limits, and plan upgrade decisions. Use when adding telemetry, diagnosing a regression, or sizing a cost review. |
| `render-services` | Choose, design, or harden Render compute — Web Services (autoscale, zero-downtime deploys, custom domains, health checks), Private Services (internal-only), Background Workers, Cron Jobs, Static Sites, image-based vs runtime builds, service plans. Use when picking a service type, sizing a plan, configuring autoscaling, or reviewing a service architecture for cost and availability. |
| `render-storage-and-databases` | Design or audit Render storage and database tiers — Managed Postgres (HA + replicas + PITR), Managed Redis (Valkey), Persistent Disks (single-AZ). Use when choosing a data store, sizing a database, configuring backups, planning recovery drills, or understanding the single-AZ limitation of Persistent Disks. |

**Sub-agents** — call explicitly via `subagent_type`:

| Agent | Description |
| --- | --- |
| `render-architect` | Render architecture reviewer. Use when the user asks for an architecture review, "is this design sound on Render", a pre-launch audit, or wants findings against Render's five design pillars (simplicity, data persistence, security, regional constraints, and cost). |
| `render-security-reviewer` | Render security reviewer. Use when the user asks for a security audit, pre-launch security check, credential hygiene review, or wants to validate posture for a Render-hosted workload against practical security baselines. |

**Slash commands:**

| Command | Description |
| --- | --- |
| `/render-scaffold-blueprint` | Scaffold a Render Blueprint (render.yaml) with a web service, background worker, Postgres, Redis, Cron Job, PR preview environments, Environment Group, and GitHub Actions CI. |
<!-- END: what's inside -->

## Install

This plugin ships inside the Blackrim.dev repo's `plugins/` marketplace. From a Claude Code session:

```text
/plugin marketplace add /Users/jayse/Code/blackrim/plugins
/plugin install cloud-render@blackrim-cloud-toolkits
```

## Design principles

1. **Blueprint-first.** Everything is declared in `render.yaml`. Console-only changes drift immediately — treat them as temporary investigation tools.
2. **Private Services for internal traffic.** Services that don't serve end-user HTTP requests should be Private Services, not public Web Services with an obscure path.
3. **Secrets live in Environment Groups and Secret Files — never inline.** Inlined env var values in `render.yaml` are a credential-leak waiting to happen.
4. **PR Previews are the development loop.** Enable the `previews:` block so every PR gets an isolated environment; catch issues before merge, not after.
5. **Be honest about PaaS limits.** Render's Persistent Disks are single-AZ. Managed Postgres has regional (not global) reach. High-throughput workloads can outgrow a PaaS. This toolkit calls that out.

## Conventions

- Skills assume the `render` CLI (≥ 1.x) is installed: `brew install render`.
- Blueprint examples target the current Blueprint spec; `previews:` block, `envVars` with `fromGroup:`, and `secretFiles:` are all included by default.
- Region defaults are explicit — `oregon` is the most feature-complete region as of 2026-05, but Ohio and Frankfurt are available.
- All examples assume a single Render team; multi-team coordination is called out where it changes the answer.
