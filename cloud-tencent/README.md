# cloud-tencent

Tencent Cloud development toolkit for Claude Code. Loads as a plugin from the parent `plugins/` marketplace.

## China vs International — read this first

Tencent Cloud operates two distinct account realms that are **not interoperable**:

- **China regions** (`ap-beijing`, `ap-shanghai`, `ap-guangzhou`, `ap-chengdu`, `ap-nanjing`, `ap-chongqing`): require a Tencent Cloud China account linked to a mainland-China registered entity, MIIT ICP filing for internet-facing services, and MLPS (Multi-Level Protection Scheme) classification for regulated systems. API endpoints, SDKs, and the console (`console.cloud.tencent.com`) differ from the International side.
- **International regions** (Hong Kong, Singapore, Tokyo, Seoul, Mumbai, Frankfurt, Virginia, São Paulo, Bangkok, Jakarta, Toronto): use a Tencent Cloud International account (`intl.cloud.tencent.com`). No ICP requirement for services hosted only in these regions, but data flowing to or from China mainland may still trigger CAC cross-border data transfer review.

When this guide says "China account" it means a credential set for the China realm; "International account" means the non-China realm. Keep them in separate `tccli` profiles and separate Terraform provider blocks.

<!-- BEGIN: what's inside -->
## What's inside

**Skills** — invoked automatically by description match, or with `/<skill-name>`:

| Skill | Description |
| --- | --- |
| `tencent-compute` | Choose, design, or harden Tencent Cloud compute — CVM (Standard / High IO / Memory Optimized / Compute Optimized / GPU), Lighthouse VPS, TKE Kubernetes (Standard / Serverless / Edge), EKS serverless k8s, SCF serverless functions, BatchCompute, CFS Container Service. Use when picking a runtime, sizing capacity, configuring autoscaling, or reviewing a compute architecture for cost / latency / availability. |
| `tencent-iac-and-deployment` | Choose, scaffold, or review Tencent Cloud Infrastructure-as-Code and deployment — Tencent Cloud CLI (tccli), Terraform tencentcloudstack/tencentcloud provider, TIC (Tencent Infrastructure-as-Code managed Terraform runner), Coding DevOps CI/CD, GitOps for TKE, GitHub Actions and Jenkins integrations. Use when starting a new IaC project, picking a tool, or hardening a release pipeline. |
| `tencent-identity-and-security` | Design or audit Tencent Cloud identity, access, and security posture — CAM (users, groups, roles, policies), SSO and federated identity, SSM Secrets Manager, KMS (Standard + HSM), Cloud Firewall, CWP (Cloud Workload Protection), CSI (Cloud Security Inspection), CloudAudit. Use when writing policies, scoping roles, rotating secrets, standing up SSO, or hardening an account. |
| `tencent-networking-and-edge` | Design or audit Tencent Cloud networking and edge — VPC, subnets, route tables, CLB (Classic + Application L4/L7), NAT Gateway, EIP, DNSPod, CDN, EdgeOne (CDN + WAF + DDoS + Workers), Anti-DDoS (Basic / Advanced / Pro), WAF, VPN Connections, Direct Connect, Cloud Connect Network (CCN). Use when standing up a new VPC, exposing a service publicly, or hardening edge posture. |
| `tencent-observability-and-cost` | Wire up or audit Tencent Cloud observability and cost — Cloud Monitor (metrics, alarms, dashboards), CLS (Cloud Log Service — collection, search, dashboards), APM, COC (Cloud Operations Center), Cost Manager (bills, budget, cost allocation tags), reservation and savings models. Use when adding telemetry, tracking a performance regression, or optimizing a bill. |
| `tencent-storage-and-databases` | Design or audit Tencent Cloud storage and database tiers — COS object storage, CBS block storage, CFS file storage, CDB MySQL, TDSQL (distributed SQL), MariaDB, DocumentDB (MongoDB-compatible), Redis, ClickHouse, Tendis, HBase, SQL Server. Use when picking a data store, modeling access patterns, sizing, securing, or designing backup and replication. |

**Sub-agents** — call explicitly via `subagent_type`:

| Agent | Description |
| --- | --- |
| `tencent-architect` | Tencent Cloud architecture reviewer. Use when the user asks for an architecture review, "is this design sound", a pre-launch audit, or wants findings against the six architecture pillars adapted for Tencent Cloud (regional fit, reliability, security, performance, cost optimization, compliance). |
| `tencent-security-reviewer` | Tencent Cloud security reviewer. Use when the user asks for a security audit, CAM least-privilege review, pre-launch security check, incident-readiness review, or wants to validate posture against MLPS Level 2 baseline, Tencent Cloud security best practices, or CIS Tencent Cloud Foundations equivalent controls. |

**Slash commands:**

| Command | Description |
| --- | --- |
| `/tencent-scaffold-iac` | Scaffold a Tencent Cloud Infrastructure-as-Code project — Terraform tencentcloudstack/tencentcloud or TIC, with opinionated production-grade defaults for China or International accounts. |
<!-- END: what's inside -->

## Install

This plugin ships inside the Blackrim.dev repo's `plugins/` marketplace. From a Claude Code session:

```text
/plugin marketplace add /Users/jayse/Code/blackrim/plugins
/plugin install cloud-tencent@blackrim-cloud-toolkits
```

## Design principles

1. **Defaults are production-grade, not demo-grade.** KMS CMK encryption on COS and CDB by default. Private subnets for all workloads. CAM roles only — no long-lived SecretId/SecretKey baked into workloads.
2. **China-first caveats are explicit.** ICP filing, MLPS Level 2 classification for production, and CAC cross-border data rules appear at the decision point, not buried in an appendix.
3. **Cost is a first-class concern.** Every skill flags cost-amplifying choices (NAT gateway data, CDN origin pull, underutilized reserved instances) at decision time.
4. **Observability before launch.** No workload ships without Cloud Monitor metrics, CLS log collection, and at least one alarm.
5. **IaC over console.** Console steps appear only for bootstrapping the root account. Everything else is Terraform or TIC.

## Conventions

- Skills assume `tccli` ≥ 3.0 is installed and a profile is configured (`tccli configure list`).
- Terraform examples target `tencentcloudstack/tencentcloud` provider ≥ 1.81.
- Region defaults are explicit — no implicit `ap-guangzhou` magic. For China workloads, specify the region; for International, choose the region closest to your users.
- All examples assume a single Tencent Cloud account first; multi-account CCN and landing-zone patterns are called out where they change the answer.
- For China accounts, every internet-facing service is assumed to require ICP filing; skills will remind you at the relevant decision points.
