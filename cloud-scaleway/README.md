# cloud-scaleway

Scaleway development toolkit for Claude Code. Loads as a plugin from the parent `plugins/` marketplace.

Scaleway is a French cloud provider with strong EU data residency credentials — Paris (PAR), Amsterdam (AMS), and Warsaw (WAW) regions — making it a natural choice for GDPR-scoped workloads and organizations that need data sovereignty guarantees. Global reach is narrower than hyperscalers; note this for non-EU latency requirements.

<!-- BEGIN: what's inside -->
## What's inside

**Skills** — invoked automatically by description match, or with `/<skill-name>`:

| Skill | Description |
| --- | --- |
| `scaleway-compute` | Choose, design, or harden Scaleway compute — Instances (Development / General Purpose / Compute Optimized / Enterprise / GPU / ARM), Elastic Metal (Bare Metal), Serverless Containers, Serverless Jobs, Serverless Functions, Kapsule (Kubernetes), Kosmos (multi-cloud Kubernetes), Apple Silicon (Mac mini M1). Use when picking a runtime, sizing capacity, configuring autoscaling, or reviewing a compute architecture for cost / latency / availability. |
| `scaleway-iac-and-deployment` | Choose, scaffold, or review Scaleway Infrastructure-as-Code and deployment — scw CLI, Terraform scaleway/scaleway provider, Pulumi pulumiverse/scaleway (community), Crossplane, GitOps with Kapsule, GitHub Actions OIDC patterns. Use when starting a new IaC project, picking a tool, or hardening a release path. |
| `scaleway-identity-and-security` | Design or audit Scaleway identity, access, and security posture — IAM (Organizations, Projects, Applications, Groups, Policies), Secret Manager, Key Manager (KMS), Audit Trail, OAuth tokens, MFA, SOC 2 / ISO 27001 / HDS certifications. Use when writing policies, rotating secrets, scoping application access, or hardening an Organization. |
| `scaleway-networking` | Design or audit Scaleway networking — VPC (with Private Networks per region), Public Gateways (egress + NAT), Load Balancers, Edge Services (CDN), Domains / DNS, IPv4 / IPv6 pools, Reserved IPs. Use when standing up a new VPC, exposing a service, hardening edge, or tracking down NAT / egress data costs. |
| `scaleway-observability-and-cost` | Wire up or audit Scaleway observability and cost — Cockpit (managed Grafana + metrics + logs), Cost Manager, Organization-level billing, Resource Tag filters, log retention tiers, alerting through Cockpit. Use when adding telemetry, tracking down a regression, building dashboards, or shrinking a bill. |
| `scaleway-storage-and-databases` | Design or audit Scaleway storage and database tiers — Object Storage (S3-compatible, Standard / Glacier), Block Storage (SBS 5K / 15K IOPS), Managed Databases (Postgres, MySQL), Serverless SQL (scale-to-zero Postgres), Managed Document Database (MongoDB-compat), Redis Cluster, IoT Hub. Use when picking a data store, modeling access patterns, sizing, securing, or backing up data. |

**Sub-agents** — call explicitly via `subagent_type`:

| Agent | Description |
| --- | --- |
| `scaleway-architect` | Scaleway architecture reviewer. Use when the user asks for an architecture review, "is this design sound", a pre-launch audit, or wants findings against Scaleway's six architecture pillars — data sovereignty, cost efficiency, reliability, security, performance, and operational excellence. |
| `scaleway-security-reviewer` | Scaleway security reviewer. Use when the user asks for a security audit, IAM least-privilege review, secret handling review, Audit Trail assessment, network exposure check, pre-launch security check, or wants to validate posture against GDPR / HDS / ISO 27001 / SOC 2 requirements on Scaleway. |

**Slash commands:**

| Command | Description |
| --- | --- |
| `/scaleway-scaffold-iac` | Scaffold a Scaleway Infrastructure-as-Code project — primary Terraform scaleway/scaleway provider, with opinionated production defaults. Alt path: scw CLI bootstrap for Kapsule clusters. |
<!-- END: what's inside -->

## Install

This plugin ships inside the Blackrim.dev repo's `plugins/` marketplace. From a Claude Code session:

```text
/plugin marketplace add /Users/jayse/Code/blackrim/plugins
/plugin install cloud-scaleway@blackrim-cloud-toolkits
```

## Design principles

1. **EU data residency first.** Region selection defaults to PAR, AMS, or WAW. Global workloads that need low-latency outside the EU require an explicit architecture decision.
2. **Defaults are production-grade, not demo-grade.** KMS CMEK on all data stores. Private Networks before Public Gateways. IAM Applications scoped to specific Projects with least-privilege Policies.
3. **Cost is a first-class concern.** Serverless scale-to-zero reduces idle spend. Every skill flags cost-amplifying choices (Public Gateway bandwidth, Elastic Metal commitments, Cockpit retention tiers) at decision time.
4. **Observability before launch.** No workload ships without Cockpit metrics, logs, and at least one alert wired to a real channel.
5. **IaC over console.** The `scw` CLI and Terraform `scaleway/scaleway` provider cover the full Scaleway surface. Console steps appear only for initial Organization setup.
6. **Be honest about regional fit.** Scaleway's EU presence is excellent; outside EU, options narrow quickly. Note this explicitly for global or latency-sensitive workloads that need more than three regions.

## Conventions

- Skills assume the Scaleway CLI (`scw`) ≥ 2.30 is installed and a profile is configured (`scw config list`).
- IaC examples target: Terraform `scaleway/scaleway` provider ≥ 2.45, Pulumi `pulumiverse/scaleway` ≥ 0.10.
- Region defaults are explicit — no implicit region magic. Examples use `fr-par` (Paris) as the first choice but prompt for the right region when sovereignty or latency differs.
- All examples assume single-Project first; multi-Project / Organization-level IAM is called out where it changes the answer.
- HDS (health-data hosting) certification is noted where it matters for regulated healthcare workloads.
