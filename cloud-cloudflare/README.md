# cloud-cloudflare

Cloudflare development toolkit for Claude Code. Loads as a plugin from the parent `plugins/` marketplace.

<!-- BEGIN: what's inside -->
## What's inside

**Skills** — invoked automatically by description match, or with `/<skill-name>`:

| Skill | Description |
| --- | --- |
| `cf-iac-and-deployment` | Configure or audit Cloudflare Infrastructure-as-Code and deployment — Wrangler (wrangler.toml / wrangler.jsonc), Terraform cloudflare/cloudflare ≥ 5.x, Pages CI, Workers Builds, GitHub Actions deploy with scoped API tokens, and secret management. Use when scaffolding a new project, wiring CI/CD, migrating from v4 Terraform provider, or hardening a release pipeline. |
| `cf-networking-and-edge` | Design or audit Cloudflare networking — DNS (authoritative), CDN cache rules, Load Balancing, Argo Smart Routing, Spectrum, Cloudflare Tunnel, Magic WAN / Magic Transit. Use when configuring DNS, tuning cache behaviour, exposing services, or connecting private infrastructure to Cloudflare's network. |
| `cf-observability-and-cost` | Wire up or audit Cloudflare observability and cost — Workers Analytics Engine, Logpush, Trace Workers, Web Analytics, GraphQL Analytics API, dashboard alerts, and billing tiers. Use when adding telemetry to Workers, debugging a production issue, reviewing billing, or deciding when to upgrade plans. |
| `cf-storage-and-databases` | Design or audit Cloudflare storage and databases — R2, D1, Workers KV, Queues, Hyperdrive, Vectorize. Use when picking an edge-native data store, modeling access patterns, securing data, or integrating Cloudflare storage with existing origin databases. |
| `cf-workers-and-compute` | Design or configure Cloudflare compute — Workers (modules, bindings), Workers AI, Durable Objects, Pages Functions, Workflows, Containers, Smart Placement. Use when choosing a runtime model, wiring bindings, sizing Durable Object state, or debugging CPU / wall-clock limits. |
| `cf-zero-trust-and-security` | Design or audit Cloudflare Zero Trust and security posture — Access (ZTNA / identity-aware proxy), Gateway (SWG / DNS filtering), WAF, Bot Management, DDoS posture, Page Shield, Magic Firewall, API Shield. Use when securing an application, filtering egress, building a Zero Trust network, or reviewing WAF coverage. |

**Sub-agents** — call explicitly via `subagent_type`:

| Agent | Description |
| --- | --- |
| `cf-architect` | Cloudflare edge architecture reviewer. Use when the user asks for an architecture review, "is this design sound for Cloudflare?", a pre-launch audit, or wants findings against the six edge pillars (edge-first design, data locality, cache effectiveness, security posture, cost, reliability). |
| `cf-security-reviewer` | Cloudflare security reviewer. Use when the user asks for a security audit, Zero Trust posture review, WAF coverage check, API token hygiene review, pre-launch security check, or wants to validate posture against Cloudflare's recommended security baseline. |

**Slash commands:**

| Command | Description |
| --- | --- |
| `/cf-scaffold-project` | Scaffold a Cloudflare project — Worker, Pages, or Worker+D1+R2 starter — with Wrangler config, Terraform skeleton, and GitHub Actions deploy using scoped API tokens. |
<!-- END: what's inside -->

## Install

This plugin ships inside the Blackrim.dev repo's `plugins/` marketplace. From a Claude Code session:

```text
/plugin marketplace add /Users/jayse/Code/blackrim/plugins
/plugin install cloud-cloudflare@blackrim-cloud-toolkits
```

## Design principles

1. **Edge-first, not cloud-first adapted.** Cloudflare's primitives (isolates, anycast, Durable Objects) differ meaningfully from IaaS VMs and containers. Defaults here reflect the edge runtime model, not a warmed-over EC2 analogy.
2. **Zero Trust over public exposure.** Cloudflare Access in front of any internal tool or admin interface; WAF and Bot Management on every public origin; Gateway filtering egress by default.
3. **Scoped API tokens, never global.** Every deployment credential is narrowed to the minimum permissions (zone, account resource) and the specific environment it serves.
4. **No egress fees on R2.** Data architecture exploits R2's zero-egress model for reads; recommendations always flag R2 vs origin-pull cost tradeoffs explicitly.
5. **Observability at the edge is different.** Traditional APM agents don't run in isolates. Analytics Engine, Logpush, and Trace Workers are the real telemetry stack — every skill wires them from day one.

## Conventions

- Skills assume Wrangler ≥ 4.x (`wrangler.toml` or `wrangler.jsonc`) is installed and `wrangler login` has been run, or a scoped API token is set via `CLOUDFLARE_API_TOKEN`.
- Terraform examples target `cloudflare/cloudflare` provider ≥ 5.x; v5 introduced breaking changes from v4 (resource renames, zone ID handling, removed account-scoped DNS resources) — the skills call these out explicitly.
- Account IDs and zone IDs are always explicit in IaC — no implicit environment detection.
- All examples assume a single Cloudflare account first; multi-account / enterprise organization structures are called out where they change the answer.
