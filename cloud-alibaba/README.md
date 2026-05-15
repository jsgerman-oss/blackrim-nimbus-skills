# cloud-alibaba

Alibaba Cloud (Aliyun) development toolkit for Claude Code. Loads as a plugin from the parent `plugins/` marketplace.

## Account model — read this first

Alibaba Cloud operates two entirely separate account spaces:

- **China regions** (`cn-*`): governed by MIIT regulations. Web-hosting workloads require an ICP filing (ICP Bei'an or ICP License depending on type). Data leaving China mainland requires a cross-border data-transfer security assessment (CAC review under the PIPL and DSL) or an SCC (Standard Contract Clause) filing. RAM, KMS, and most service endpoints are China-specific and do not interoperate with International accounts.
- **International regions** (`ap-*`, `eu-*`, `us-*`, etc.): standard global account. Governed by Alibaba Cloud International terms; no ICP required unless you are deliberately serving ICP-regulated mainland audiences.

A single organization typically maintains **two separate Alibaba Cloud accounts** — one China, one International — with no direct resource or IAM bridging between them. Plan your architecture around this boundary before picking a region.

<!-- BEGIN: what's inside -->
## What's inside

**Skills** — invoked automatically by description match, or with `/<skill-name>`:

| Skill | Description |
| --- | --- |
| `alibaba-compute` | Choose, design, or harden Alibaba Cloud compute — ECS (g7/c7/r7/ARM g8y, Spot), ACK Kubernetes (Standard/Pro/Serverless), Function Compute (FC), E-HPC, ECI, Serverless App Engine (SAE). Use when picking a runtime, sizing capacity, configuring autoscaling, or reviewing a compute architecture for cost, latency, or availability. |
| `alibaba-iac-and-deployment` | Choose, scaffold, or review Alibaba Cloud Infrastructure-as-Code and deployment — Alibaba Cloud CLI (aliyun ≥ 3.0.230), Terraform aliyun/alicloud provider (≥ 1.220), Resource Orchestration Service (ROS), Cloud Assistant, GitOps for ACK, GitHub Actions / Jenkins with RAM Role OIDC. Use when starting an IaC project, picking a tool, or hardening a release path. |
| `alibaba-identity-and-security` | Design or audit Alibaba Cloud identity, access, and security posture — RAM (users/groups/roles/policies), STS temporary credentials, KMS (Standard/Dedicated HSM), Secrets Manager, Cloud Config, Cloud Firewall, Security Center (Threat Detection), Anti-DDoS, ActionTrail, SDDP. Use when writing RAM policies, rotating secrets, scoping roles, or hardening an account. |
| `alibaba-networking-and-edge` | Design or audit Alibaba Cloud networking — VPC, VSwitch, route tables, Security Groups, ENI, SLB/ALB/NLB, NAT Gateway, EIP, CEN (cross-region), CDN, DCDN, Anti-DDoS Pro/Premium, WAF, IPv6 Gateway. Use when standing up a new VPC, exposing a service, connecting regions, or hardening edge. |
| `alibaba-observability-and-cost` | Wire up or audit Alibaba Cloud observability and cost — CloudMonitor (metrics/alarms), Simple Log Service (SLS logs/metrics/query), ARMS (APM traces), Cost Manager (bills/budgets/anomaly), Resource Management (groups/tags), reservation and savings models. Use when adding telemetry, tracking a regression, or shrinking the bill. |
| `alibaba-storage-and-databases` | Design or audit Alibaba Cloud storage and database tiers — OSS, EBS cloud disks, NAS, RDS (MySQL/Postgres/SQL Server/MariaDB), PolarDB, ApsaraDB for MongoDB / Redis, Lindorm, AnalyticDB. Use when picking a data store, modeling access patterns, sizing, securing, or configuring lifecycle and backup. |

**Sub-agents** — call explicitly via `subagent_type`:

| Agent | Description |
| --- | --- |
| `alibaba-architect` | Alibaba Cloud architecture reviewer. Use when the user asks for an architecture review, "is this design sound", a pre-launch audit, or wants findings against the six Alibaba-adapted pillars — regional fit (China vs International), reliability (multi-AZ + cross-region with CEN), security (RAM scope / ActionTrail / Cloud Firewall), performance efficiency, cost optimization, and compliance (China data residency / MIIT ICP / MLPS). |
| `alibaba-security-reviewer` | Alibaba Cloud security reviewer. Use when the user asks for a security audit, IAM/RAM least-privilege review, pre-launch security check, MLPS alignment review, or wants to validate posture against CIS Alibaba Cloud Foundations Benchmark, Cloud Firewall / WAF / Anti-DDoS posture, OSS public-bucket discipline, KMS CMK coverage, or ActionTrail completeness. |

**Slash commands:**

| Command | Description |
| --- | --- |
| `/alibaba-scaffold-iac` | Scaffold an Alibaba Cloud Infrastructure-as-Code project — Terraform aliyun/alicloud or ROS, with opinionated production-grade defaults. Handles China vs International region specifics. |
<!-- END: what's inside -->

## Install

This plugin ships inside the Blackrim.dev repo's `plugins/` marketplace. From a Claude Code session:

```text
/plugin marketplace add /Users/jayse/Code/blackrim/plugins
/plugin install cloud-alibaba@blackrim-cloud-toolkits
```

## Design principles

1. **Defaults are production-grade, not demo-grade.** VPC private placement, Cloud Firewall + Security Group default-deny, KMS CMK on every data store. OSS Block Public Access on by default.
2. **No long-lived AK/SK in workloads.** RAM Role + STS everywhere. AccessKey pairs belong only in bootstrap-human tooling, not in applications.
3. **China/International boundary is explicit.** Every architectural decision that changes at this boundary is flagged. Never assume a service, endpoint, or compliance requirement applies to both.
4. **Cost is a first-class concern.** Savings plans, resource groups, and tag-based billing reports are wired from day one.
5. **Observability before launch.** CloudMonitor metrics, SLS log pipelines, and ARMS traces are configured before a workload reaches production.
6. **IaC over console.** Console steps appear only for account root hardening. Everything else is Terraform or ROS.

## Conventions

- Skills assume the `aliyun` CLI ≥ 3.0.230 is installed and a profile is configured (`aliyun configure list`).
- Terraform examples target `aliyun/alicloud` provider ≥ 1.220.
- Region defaults are always explicit — no implicit `cn-hangzhou` magic.
- All examples note when behavior differs between China and International regions.
- RAM Role + STS assumed credential chains are the default everywhere application code touches the API.
