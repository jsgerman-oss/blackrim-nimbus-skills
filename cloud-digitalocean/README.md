# cloud-digitalocean

DigitalOcean development toolkit for Claude Code. Loads as a plugin from the parent `plugins/` marketplace.

<!-- BEGIN: what's inside -->
## What's inside

**Skills** — invoked automatically by description match, or with `/<skill-name>`:

| Skill | Description |
| --- | --- |
| `do-compute` | Choose, design, or harden DigitalOcean compute — Droplets (Basic, General Purpose, CPU-Optimized, Memory-Optimized, Storage-Optimized, GPU), App Platform, DOKS (DigitalOcean Kubernetes), Functions (Serverless), and Snapshots. Use when picking a runtime, sizing capacity, configuring autoscaling, or reviewing a compute architecture for cost, latency, or availability. |
| `do-iac-and-deployment` | Choose, scaffold, or review DigitalOcean Infrastructure-as-Code and deployment — doctl CLI, Terraform `digitalocean/digitalocean` provider, App Platform App Spec YAML, DOKS GitOps with Argo CD / Flux, GitHub Actions with PATs, and image build via doctl registry. Use when starting a new IaC project, picking a tool, or hardening a release path. |
| `do-identity-and-security` | Design or audit DigitalOcean identity and security posture — Teams (members, roles), Personal Access Tokens (PATs — scopes, rotation), OAuth applications, doctl authentication, Container Registry vulnerability scanning, Cloud Firewall posture, agent monitoring vs metrics agent, and project-based isolation. Use when writing access policies, rotating secrets, scoping tokens, or hardening a team account. |
| `do-networking-and-edge` | Design or audit DigitalOcean networking — VPC (per-region, multi-VPC patterns), Load Balancer (regional, global), Floating / Reserved IPs, DNS (PowerDNS-based), Cloud Firewall, Spaces CDN, and PTR records. Use when standing up a new VPC, exposing a service, hardening edge, or auditing east-west connectivity. |
| `do-observability-and-cost` | Wire up or audit DigitalOcean observability and cost — Monitoring (graphs, alert policies for CPU, disk, memory, bandwidth), Logs, Insights / metrics, project-level billing, Reserved capacity hooks, and snapshot lifecycle costs. Use when adding telemetry, tracking down a regression, or shrinking a bill. |
| `do-storage-and-databases` | Design or audit DigitalOcean storage and database tiers — Spaces (S3-compatible object storage), Volumes (block storage), Managed Databases (Postgres, MySQL, MongoDB, Redis, Kafka, OpenSearch), and Backups. Use when picking a data store, modeling access patterns, sizing, securing, or backing up data. |

**Sub-agents** — call explicitly via `subagent_type`:

| Agent | Description |
| --- | --- |
| `do-architect` | DigitalOcean architecture reviewer. Use when the user asks for an architecture review, "is this design sound", a pre-launch audit, or wants findings against the five adapted DigitalOcean pillars (operational excellence, security, reliability, performance, cost optimization). Honest about DigitalOcean's ceiling and when a different platform or self-hosted component would serve better. |
| `do-security-reviewer` | DigitalOcean security reviewer. Use when the user asks for a security audit, pre-launch security check, incident-readiness review, or wants to validate posture across Cloud Firewall rules, project / team RBAC, PAT scoping and rotation, VPC isolation, Container Registry scanning, Spaces public bucket exposure, and MFA enforcement. |

**Slash commands:**

| Command | Description |
| --- | --- |
| `/do-scaffold-iac` | Scaffold a DigitalOcean Infrastructure-as-Code project — Terraform `digitalocean/digitalocean` provider or App Platform App Spec YAML, with opinionated production-grade defaults. |
<!-- END: what's inside -->

## Install

This plugin ships inside the Blackrim.dev repo's `plugins/` marketplace. From a Claude Code session:

```text
/plugin marketplace add /Users/jayse/Code/blackrim/plugins
/plugin install cloud-digitalocean@blackrim-cloud-toolkits
```

## Design principles

1. **Defaults are production-grade, not demo-grade.** VPC private networking on by default. Cloud Firewall locked to known tags and sources. Managed Databases placed in private VPCs — no public connection strings.
2. **Cost is a first-class concern.** Every skill flags cost-amplifying choices (managed-DB markup, excess snapshots, idle Droplets) at decision time and offers the self-hosted tradeoff honestly.
3. **Observability before launch.** No workload ships without alert policies wired to a real notification target.
4. **IaC over the Control Panel.** Control Panel steps appear only for one-time bootstrap (team creation, billing setup). Everything else is `doctl` or Terraform.
5. **PATs are not passwords.** Scoped short-lived PATs stored in a secrets manager, rotated on a schedule — not pasted into `.env` files or hard-coded in scripts.

## Conventions

- Skills assume `doctl` >= 1.110 is installed and authenticated (`doctl auth init`).
- Terraform examples target `digitalocean/digitalocean` provider >= 2.40 and Terraform / OpenTofu >= 1.6.
- Region slugs are explicit throughout (e.g. `nyc3`, `sfo3`, `lon1`, `ams3`, `fra1`, `sgp1`, `blr1`, `syd1`).
- All examples assume a single team first; multi-team / multi-project patterns are called out where the answer changes.
