# cloud-linode

Linode (Akamai Cloud Computing) development toolkit for Claude Code. Loads as a plugin from the parent `plugins/` marketplace.

<!-- BEGIN: what's inside -->
## What's inside

**Skills** — invoked automatically by description match, or with `/<skill-name>`:

| Skill | Description |
| --- | --- |
| `linode-compute` | Choose, design, or harden Linode compute — Compute Instances (Nanode / Shared / Dedicated / High Memory / Premium / GPU), Linode Kubernetes Engine (LKE), Bare Metal, Marketplace apps. Use when picking an instance plan, sizing a Kubernetes cluster, configuring autoscaling node pools, or reviewing a compute architecture for cost and availability. |
| `linode-iac-and-deployment` | Choose, scaffold, or review Linode Infrastructure-as-Code and deployment — linode-cli, Terraform linode/linode provider, Ansible Linode collection, StackScripts (legacy), cloud-init bootstrap, GitHub Actions CI/CD. Use when starting a new IaC project, picking a tool, or hardening a release path. |
| `linode-networking` | Design or audit Linode networking — VLAN (private L2), VPC (VPC + Subnets), NodeBalancer (L4/L7 load balancing), Cloud Firewall (stateful), Reserved IPs, IPv6. Use when standing up private networking, exposing a service, hardening edge, or auditing east-west connectivity. |
| `linode-observability-and-cost` | Wire up or audit Linode observability and cost — Longview agent, Cloud Manager metrics, external monitoring (Datadog / Better Stack / Grafana Cloud), alerts, billing model (per-hour with monthly cap), and the regional transfer pool. Use when adding telemetry, diagnosing a cost spike, or planning a billing review. |
| `linode-security` | Design or audit Linode security posture — Linode Manager users and roles, Personal Access Tokens (scopes and expiry), MFA and SSH key requirements, Cloud Firewall posture, root-user discipline, Akamai Shield DDoS, audit logs, OAuth applications. Use when hardening an account, scoping API access, reviewing access grants, or responding to a security event. |
| `linode-storage-and-databases` | Design or audit Linode storage and database tiers — Block Storage Volumes, Object Storage, Backups, Managed Databases (Postgres / MySQL), and custom Images. Use when choosing a data store, modeling lifecycle and access patterns, sizing capacity, securing data, or planning recovery. |

**Sub-agents** — call explicitly via `subagent_type`:

| Agent | Description |
| --- | --- |
| `linode-architect` | Linode architecture reviewer. Use when the user asks for an architecture review, "is this design sound on Linode", a pre-launch audit, or wants findings against the five architecture pillars (cost optimization, reliability, security, performance efficiency, operational excellence) applied to Linode's feature set and platform limits. |
| `linode-security-reviewer` | Linode security reviewer. Use when the user asks for a security audit, threat model, pre-launch security check, PAT scope review, Cloud Firewall posture review, or MFA enforcement audit. Anchors to Personal Access Token scopes and rotation, Cloud Firewall posture, MFA and SSH key requirements, public-IP discipline, Object Storage bucket policy, VPC isolation, and audit log review. |

**Slash commands:**

| Command | Description |
| --- | --- |
| `/linode-scaffold-iac` | Scaffold a Linode Infrastructure-as-Code project — primary tool is Terraform (linode/linode provider); alternative is Ansible Linode collection. Generates production-grade defaults for networking, compute, firewalls, and state management. |
<!-- END: what's inside -->

## Install

This plugin ships inside the Blackrim.dev repo's `plugins/` marketplace. From a Claude Code session:

```text
/plugin marketplace add /Users/jayse/Code/blackrim/plugins
/plugin install cloud-linode@blackrim-cloud-toolkits
```

## Design principles

1. **Defaults are production-grade, not demo-grade.** VPC private networking on by default. Cloud Firewall default-deny. SSH key-only authentication — no password login. Backups enabled on stateful instances. Object Storage buckets default-private.
2. **Cost is a first-class concern.** Linode bills hourly with a monthly cap. Transfer pools accumulate across instances in a region — every skill flags egress-heavy choices. Egress between regions and to the internet meters separately.
3. **Be honest about platform limits.** Linode has fewer regions than AWS (approximately 20 vs 30+), a simpler managed-DB offering (no equivalent of Aurora or DynamoDB), no anycast load balancer, and no global CDN of its own. Skills surface these limits where they affect design choices — consumers should plan around them.
4. **IaC over console.** All recurring configuration is expressed as Terraform or Ansible. Cloud Manager / console steps appear only for one-time account setup (MFA, token creation).
5. **Terraform-first.** The `linode/linode` provider (>= 2.20) is the primary IaC tool. `linode-cli` is the operational companion. StackScripts are a legacy callout — prefer cloud-init for bootstrap.

## Conventions

- Skills assume `linode-cli` >= 5.x is installed and configured (`linode-cli configure`), and/or Terraform >= 1.6 with `linode/linode` provider >= 2.20.
- Region is always explicit — no default assumed.
- Examples are single-account. Linode does not have multi-account organizations equivalent to AWS Organizations; team access is controlled via Linode Manager user grants.
- Kubernetes examples target LKE with the most recent stable Kubernetes release supported by Linode (verify at deploy time).
- Akamai Connected Cloud / CDN integration is called out separately — skills focus on the Linode compute and storage surface, not Akamai's broader CDN/WAF product.
