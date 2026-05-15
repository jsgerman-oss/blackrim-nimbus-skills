# cloud-hetzner

Hetzner development toolkit for Claude Code. Covers both **Hetzner Cloud** (modern API, hcloud-cli, Terraform) and **Hetzner Robot** (dedicated servers, legacy API). Loads as a plugin from the parent `plugins/` marketplace.

<!-- BEGIN: what's inside -->
## What's inside

**Skills** — invoked automatically by description match, or with `/<skill-name>`:

| Skill | Description |
| --- | --- |
| `hetzner-compute` | Choose, design, or harden Hetzner compute — Cloud server types (CX / CPX / CCX / CAX ARM Ampere), placement groups, snapshots vs backups vs images, server rescue, Robot dedicated server families (AX / EX / SX / GEX GPU), Auctions, server reset. Use when picking a server type, sizing capacity, designing for HA, or managing server lifecycle. |
| `hetzner-iac-and-deployment` | Choose, scaffold, or review Hetzner Infrastructure-as-Code and deployment — hcloud CLI, Terraform hetznercloud/hcloud provider (≥ 1.48), Ansible hetzner.hcloud collection, Packer for image baking, cloud-init for bootstrap, snapshot-as-golden-image pattern, GitHub Actions deploy with token from secrets. Use when starting a new IaC project, picking a tool, or hardening a release path for Hetzner infrastructure. |
| `hetzner-identity-and-security` | Design or audit Hetzner identity and security posture — API tokens (read-only vs read+write, project isolation), project-level access boundary and its RBAC limitations, SSH key management, Cloud Firewall policies, server password vs key-only auth, MFA on the Cloud console, Robot vs Cloud account separation. Use when scoping access, creating API tokens, auditing security posture, or hardening a Hetzner deployment. |
| `hetzner-networking` | Design or audit Hetzner networking — Private Networks (Cloud), Load Balancers (LB11 / LB21 / LB31), Floating IPs, Cloud Firewalls, vSwitch for Robot dedicated, dual-stack IPv4/IPv6 and the IPv4 cost surcharge, Reverse DNS (PTR), location vs network zone semantics. Use when standing up inter-server networking, exposing a service, or hardening network posture. |
| `hetzner-observability-and-cost` | Wire up or audit Hetzner observability and cost — hcloud server metrics (CPU / network / disk via API), Cloud Status page, Robot server monitoring, pairing with external observability stacks (Grafana Cloud, Datadog, Better Stack, Prometheus), Hetzner billing model (hourly capped at monthly), egress traffic allowances and per-TB overage, IPv4 surcharge. Use when adding telemetry, tracking down a cost regression, or sizing a monthly bill. |
| `hetzner-storage-and-databases` | Design or audit Hetzner storage and database options — Cloud Volumes, Backups, Snapshots, Storage Box (SFTP / SMB / WebDAV / object), and how to pair with external managed databases. Use when picking a storage tier, sizing volumes, configuring retention, or selecting a managed database provider to run alongside Hetzner compute. |

**Sub-agents** — call explicitly via `subagent_type`:

| Agent | Description |
| --- | --- |
| `hetzner-architect` | Hetzner architecture reviewer. Use when the user asks for an architecture review, "is this design sound", a pre-launch audit, or wants findings against the six Hetzner-specific pillars (cost efficiency, reliability, security, performance, operational excellence, data sovereignty). Understands Hetzner's limitations — single-DC failure domains, no managed databases, no anycast LB, limited regions — and reviews designs honestly against that reality. |
| `hetzner-security-reviewer` | Hetzner security reviewer. Use when the user asks for a security audit, Cloud Firewall posture review, API token scope validation, pre-launch security check, Robot server hardening review, or wants to validate posture against general CIS-equivalent Linux and API security baselines on Hetzner infrastructure. |

**Slash commands:**

| Command | Description |
| --- | --- |
| `/hetzner-scaffold-iac` | Scaffold a Hetzner Infrastructure-as-Code project — Terraform hetznercloud/hcloud or Ansible hetzner.hcloud, with opinionated production-grade defaults for compute, networking, firewalls, and storage. |
<!-- END: what's inside -->

## Install

This plugin ships inside the Blackrim.dev repo's `plugins/` marketplace. From a Claude Code session:

```text
/plugin marketplace add /Users/jayse/Code/blackrim/plugins
/plugin install cloud-hetzner@blackrim-cloud-toolkits
```

## Managed database note

**Hetzner does not offer a native managed database service.** There is no Hetzner equivalent of RDS, Cloud SQL, or Managed Postgres. For production databases, pair Hetzner compute with an external managed provider:

| Provider | Best for |
| --- | --- |
| [Crunchy Bridge](https://crunchybridge.com/) | Postgres, EU data residency options |
| [Neon](https://neon.tech/) | Serverless Postgres, autoscaling |
| [Aiven](https://aiven.io/) | Postgres, MySQL, Redis, OpenSearch — multi-cloud |
| [PlanetScale](https://planetscale.com/) | MySQL-compatible, branching workflow |
| Self-hosted on Hetzner | Full control; you own backups, HA, patching |

Self-hosting on Hetzner with streaming replication + an automated backup-to-Storage-Box pipeline is a viable and cost-effective choice for teams that can manage it. Skills in this plugin call out where the tradeoff matters.

## Design principles

1. **Cost efficiency is the reason teams choose Hetzner.** Every skill flags choices that undermine the cost advantage — unnecessary public IPs, oversized server types, missing egress discipline.
2. **Production-grade defaults, not demo shortcuts.** SSH key-only auth (no password). Cloud Firewall default-deny. Private Networks for inter-server traffic. API tokens scoped to project and purpose.
3. **Honest about limitations.** Hetzner lacks managed databases, multi-region active-active (all locations are independent failure domains), anycast load balancing, and account-wide RBAC. Skills surface these plainly.
4. **IaC over panel.** Hetzner's Cloud panel and Robot panel are excellent but not auditable. Everything reproducible belongs in Terraform or Ansible.
5. **EU-first data sovereignty.** Hetzner's primary data centers (Nuremberg, Falkenstein, Helsinki) are EU-resident. The Ashburn (USA East) and Hillsboro (USA West) locations add US presence but break EU-only assumptions.

## Conventions

- Skills assume `hcloud` CLI ≥ 1.45 is installed and authenticated via `HCLOUD_TOKEN` or `hcloud context use`.
- Terraform examples target `hetznercloud/hcloud` provider ≥ 1.48.
- Robot API examples assume the Robot account credentials are set; no single-auth-token model exists for Robot.
- Location codes used throughout: `nbg1` (Nuremberg), `fsn1` (Falkenstein), `hel1` (Helsinki), `ash` (Ashburn, USA), `hil` (Hillsboro, USA), `sin` (Singapore).
- Network zone semantics: `eu-central` covers `nbg1` / `fsn1` / `hel1`; `us-east` covers `ash`; `us-west` covers `hil`; `ap-southeast` covers `sin`.
- IPv4 is now billed at €0.001/hr per address. Prefer IPv6-only where your stack allows, or Floating IPs shared across a LB tier.
