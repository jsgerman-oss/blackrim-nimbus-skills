# cloud-vultr

Vultr development toolkit for Claude Code. Loads as a plugin from the parent `plugins/` marketplace.

<!-- BEGIN: what's inside -->
## What's inside

**Skills** — invoked automatically by description match, or with `/<skill-name>`:

| Skill | Description |
| --- | --- |
| `vultr-compute` | Choose, design, or harden Vultr compute — Cloud Compute (Regular, High Performance, High Frequency, High Optimized AMD/Intel), Cloud GPU (NVIDIA fractional and dedicated), Bare Metal, Vultr Kubernetes Engine (VKE), Marketplace apps, ISO uploads, snapshots, startup scripts. Use when picking an instance plan, sizing capacity, designing a Kubernetes cluster, or auditing compute configuration. |
| `vultr-iac-and-deployment` | Choose, scaffold, or review Vultr Infrastructure-as-Code and deployment — vultr-cli (vultr CLI), Terraform vultr/vultr provider, Packer Vultr plugin, Ansible inventory plugin, cloud-init, GitHub Actions deploy, snapshot lifecycle. Use when starting a new IaC project for Vultr, designing a deployment pipeline, or auditing an existing IaC repo for drift and security posture. |
| `vultr-networking` | Design or audit Vultr networking — VPC 2.0 (modern regional software-defined network), Load Balancers (regional), Reserved IPs, Firewall Groups (account-wide policy sets), DDoS Protection (paid add-on per region), DNS, IPv6. Use when designing network topology, exposing a service publicly, hardening edge, or auditing connectivity between instances. |
| `vultr-observability-and-cost` | Wire up or audit Vultr observability and cost — built-in metrics (CPU / memory / network / disk), Alerts, third-party observability via standard agents (Prometheus node exporter, Datadog agent, Grafana Alloy), billing model (hourly with monthly cap), bandwidth pool model and per-TB overage, and free-transfer differences across regions. Use when adding telemetry, wiring alerts, diagnosing a performance regression, or reviewing a Vultr bill. |
| `vultr-security` | Design or audit Vultr security posture — Firewall Groups and per-instance application, SSH key management, API Access keys (account level, scope carefully), 2FA enforcement, sub-accounts (limited RBAC), audit log access, and public IP discipline. Use when hardening an account, reviewing access controls, rotating credentials, or designing a least-privilege posture. |
| `vultr-storage-and-databases` | Design or audit Vultr storage and database tiers — Block Storage (HDD vs NVMe), Object Storage (S3-compatible), Backups, Managed Databases (Postgres, MySQL, Redis/Valkey, Kafka) with HA tiers and replicas, and restore drills. Use when picking a data store, sizing, securing, setting up replication, or running a backup restore drill. |

**Sub-agents** — call explicitly via `subagent_type`:

| Agent | Description |
| --- | --- |
| `vultr-architect` | Vultr architecture reviewer. Use when the user asks for an architecture review, "is this design sound", a pre-launch audit, or wants findings against five pillars — cost (compute + bandwidth + GPU spot vs reserved), reliability (region + VPC + LB single-AZ realities), security (firewall groups + 2FA), performance (instance family selection), operational excellence. Vultr-specific realities and limitations surface throughout. |
| `vultr-security-reviewer` | Vultr security reviewer. Use when the user asks for a security audit, pre-launch security check, Firewall Group posture review, API key rotation, 2FA enforcement check, SSH key discipline review, Object Storage bucket policy audit, VPC 2.0 isolation review, sub-account discipline check, or DDoS Protection verification. |

**Slash commands:**

| Command | Description |
| --- | --- |
| `/vultr-scaffold-iac` | Scaffold a Vultr Infrastructure-as-Code project — primary IaC is Terraform with the vultr/vultr provider; alt is Ansible for OS configuration management. Opinionated production-grade defaults throughout. |
<!-- END: what's inside -->

## Install

This plugin ships inside the Blackrim.dev repo's `plugins/` marketplace. From a Claude Code session:

```text
/plugin marketplace add /Users/jayse/Code/blackrim/plugins
/plugin install cloud-vultr@blackrim-cloud-toolkits
```

## Design principles

1. **Defaults are production-grade, not demo-grade.** VPC 2.0 private networking by default. Firewall Groups default-deny with explicit allow rules. SSH key-only auth; password auth disabled. DDoS Protection on for every public-facing service.
2. **Cost is a first-class concern.** Bandwidth pool model, per-TB overage charges, GPU pricing, and regional differences all flagged at decision time.
3. **Observability before launch.** No instance ships without metrics enabled and at least one alert wired to a real notification channel.
4. **IaC over control panel.** Control panel steps appear only for one-time account bootstrap (2FA, SSH key upload). Everything repeatable is Terraform or `vultr-cli`.
5. **Honest about limits.** Vultr has narrower managed-service breadth than AWS or GCP. Cloud GPU and Bare Metal are unavailable in some regions. Sub-accounts provide limited RBAC — not comparable to hyperscaler IAM. These realities appear where they matter.

## Conventions

- Skills assume `vultr-cli` ≥ 3.x is installed and `VULTR_API_KEY` is set, or the Terraform `vultr/vultr` provider ≥ 2.21 is configured.
- IaC examples target Terraform ≥ 1.6 with `vultr/vultr` provider ≥ 2.21, or Ansible with the Vultr inventory plugin.
- Region slugs are explicit — no implicit defaults.
- Examples assume a single Vultr account; sub-account and multi-region considerations are called out where they change the answer.
