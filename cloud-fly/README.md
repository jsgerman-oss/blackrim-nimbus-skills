# cloud-fly

Fly.io development toolkit for Claude Code. Loads as a plugin from the parent `plugins/` marketplace.

<!-- BEGIN: what's inside -->
## What's inside

**Skills** — invoked automatically by description match, or with `/<skill-name>`:

| Skill | Description |
| --- | --- |
| `fly-iac-and-deployment` | Design or audit Fly.io infrastructure-as-code and deployment — flyctl CLI, fly.toml configuration, deploy strategies (immediate/rolling/bluegreen/canary), GitHub Actions with superfly/flyctl-actions, machine pinning via the Machines API, Pulumi flyio/fly provider, multi-region deploys. Use when setting up a deployment pipeline, reviewing fly.toml structure, or choosing a deploy strategy. |
| `fly-machines-and-apps` | Design, size, or operate Fly Machines and Apps — Firecracker VMs, auto-start/stop, scale-to-zero, machine sizes, placement across regions, rolling vs immediate deploys, releases, fly-replay routing. Use when picking a machine size, configuring multi-region, reviewing a deployment strategy, or auditing scale-to-zero correctness. |
| `fly-networking-and-edge` | Design or audit Fly.io networking — anycast IPv4/IPv6, the 6PN WireGuard private network, Flycast for private anycast routing, fly.toml services, TCP/HTTP/TLS handlers, dedicated IPs, WireGuard peer tunnels. Use when exposing a service, designing service-to-service communication, configuring TLS termination, or auditing network exposure. |
| `fly-observability-and-cost` | Wire up or audit observability and cost on Fly.io — built-in Grafana metrics, fly logs (NATS-backed), shipping to external observability stacks, OpenTelemetry support, Fly pricing model (machine-seconds, volumes, egress). Use when adding telemetry to a Fly app, diagnosing a regression, or sizing a cost review. |
| `fly-security-and-secrets` | Design or audit Fly.io security posture — Fly tokens (org/app/deploy scope), fly secrets management, SSO and org membership, private apps via Flycast, least-privilege token handling, secret rotation, image hardening. Use when scoping credentials, rotating secrets, designing a private app, or reviewing the security posture of a Fly-hosted service. |
| `fly-storage-and-databases` | Design or audit storage and databases on Fly.io — Fly Volumes (AZ-local block storage), Fly Postgres (self-managed on Machines), Fly Redis (Upstash-backed), Tigris (S3-compatible object storage), LiteFS (SQLite replication). Use when choosing a data store, modeling replication, configuring backups, or planning a restore drill. |

**Sub-agents** — call explicitly via `subagent_type`:

| Agent | Description |
| --- | --- |
| `fly-architect` | Fly.io architecture reviewer. Use when the user asks for an architecture review, "is this design sound", a pre-launch audit, or wants findings against five Fly-specific pillars (edge-first design, data placement, scale-to-zero correctness, security posture, cost). |
| `fly-security-reviewer` | Fly.io security reviewer. Use when the user asks for a security audit, pre-launch security check, token scope review, secrets handling review, or wants to validate posture against Fly-specific security baselines (token scoping, private apps, Postgres rotation, WireGuard hygiene, image signing). |

**Slash commands:**

| Command | Description |
| --- | --- |
| `/fly-scaffold-app` | Scaffold a Fly.io application — fly.toml, Dockerfile, GitHub Actions deploy pipeline, multi-region machine config, optional Fly Postgres and Tigris bucket, secrets bootstrap script. |
<!-- END: what's inside -->

## Install

This plugin ships inside the Blackrim.dev repo's `plugins/` marketplace. From a Claude Code session:

```text
/plugin marketplace add /Users/jayse/Code/blackrim/plugins
/plugin install cloud-fly@blackrim-cloud-toolkits
```

## Design principles

1. **Edge-first defaults, not cloud-region-first.** Fly places machines across 30+ global regions with anycast routing. Latency is a design variable, not an afterthought.
2. **Scale-to-zero is the default, not a feature flag.** `auto_stop_machines` and `auto_start_machines` are on by default. Design for cold-start budgets, not always-warm assumptions.
3. **Cost is machine-seconds.** Fly bills by actual machine runtime, not reservation. An idle machine at `auto_stop` costs nothing. Understand the difference between `stopped` (no charge) and `suspended` (memory preserved, small charge).
4. **Volumes are AZ-local — redundancy is your job.** Fly Volumes are attached to a single machine in a single region. Replication (LiteFS, Postgres streaming replication, application-level) is not automatic. Build with this constraint, not around it.
5. **Fly Postgres is managed-by-you.** It is not a fully-managed service like RDS. You own upgrades, failover configuration, and backups. Name this clearly to stakeholders.
6. **Private by default, public only when required.** Internal services belong on the 6PN WireGuard mesh reached via Flycast, not a public anycast address. Reserve public IPs for edge-facing services.

## Conventions

- Skills assume `flyctl` ≥ 0.3.x is installed and `fly auth login` has been run.
- Examples target the Machines API v1, LiteFS current stable, and Tigris (GA as of 2025).
- Region codes are explicit (`iad`, `lhr`, `nrt`) — no implicit defaults.
- All examples assume a single Fly organization first; multi-org is noted where it changes the answer.
- `fly.toml` examples use the v2 format (required as of flyctl 0.1.x).
