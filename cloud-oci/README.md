# cloud-oci

Oracle Cloud Infrastructure development toolkit for Claude Code. Loads as a plugin from the parent `plugins/` marketplace.

<!-- BEGIN: what's inside -->
## What's inside

**Skills** — invoked automatically by description match, or with `/<skill-name>`:

| Skill | Description |
| --- | --- |
| `oci-compute` | Choose, design, or harden OCI compute — Compute VMs and Bare Metal, GPU and A1 Ampere ARM shapes, Flex shapes, Container Engine for Kubernetes (OKE), Functions (Fn Project), Container Instances. Use when picking a runtime, sizing capacity, configuring autoscaling, or reviewing a compute architecture for cost, latency, or availability. |
| `oci-iac-and-deployment` | Choose, scaffold, or review OCI Infrastructure-as-Code and deployment — Terraform with the oracle/oci provider, Resource Manager (managed Terraform), OCI DevOps service (build and deploy pipelines), GitOps with OKE, OCI CLI. Use when starting a new IaC project, designing a CI/CD pipeline, or hardening a release path. |
| `oci-identity-and-security` | Design or audit OCI identity, access, and security posture — OCI IAM (compartments, groups, dynamic groups, identity domains), Resource Principal authentication, Vault (KMS + Secrets), Cloud Guard, Security Zones, Bastion service, Data Safe, Vulnerability Scanning. Use when writing policies, structuring compartments, scoping roles, or hardening a tenancy. |
| `oci-networking-and-edge` | Design or audit OCI networking — VCN, subnets, route tables, security lists, Network Security Groups (NSGs), Load Balancer (LBaaS L7 vs Network LB), WAF, DNS Traffic Steering, FastConnect, Site-to-Site VPN, Service Gateway, IPv6. Use when standing up a new VCN, exposing a service, controlling east-west traffic, or hardening edge access. |
| `oci-observability-and-cost` | Wire up or audit OCI observability and cost — Monitoring (metrics, alarms), Logging (custom, service, audit), Logging Analytics, APM, Stack Monitoring, Cost Analysis, Budgets, Tag Defaults, Cost-Tracking Tags. Use when adding telemetry, tracing a regression, building dashboards, or analyzing a bill. |
| `oci-storage-and-databases` | Design or audit OCI storage and database tiers — Object Storage (Standard, Infrequent Access, Archive), Block Volumes, Autonomous Database (ATP, ADW, AJD), MySQL HeatWave, NoSQL Database, File Storage Service, Exadata Cloud Service. Use when picking a data store, modeling access patterns, sizing, securing, or configuring lifecycle and backup policies. |

**Sub-agents** — call explicitly via `subagent_type`:

| Agent | Description |
| --- | --- |
| `oci-architect` | OCI Well-Architected and Cloud Adoption Framework reviewer. Use when the user asks for an architecture review, wants a pre-launch audit, or wants findings mapped to OCI's five well-architected pillars (operational excellence, security, reliability, performance efficiency, cost optimization). |
| `oci-security-reviewer` | OCI security reviewer. Use when the user asks for a security audit, IAM least-privilege review, compartment posture review, pre-launch security check, or wants to validate against the CIS Oracle Cloud Foundations Benchmark, OCI Cloud Guard recipes, or Security Zones policies. |

**Slash commands:**

| Command | Description |
| --- | --- |
| `/oci-scaffold-iac` | Scaffold an OCI Infrastructure-as-Code project — pick Terraform with the oracle/oci provider or Resource Manager, with opinionated production-grade defaults. |
<!-- END: what's inside -->

## Install

This plugin ships inside the Blackrim.dev repo's `plugins/` marketplace. From a Claude Code session:

```text
/plugin marketplace add /Users/jayse/Code/blackrim/plugins
/plugin install cloud-oci@blackrim-cloud-toolkits
```

## Design principles

1. **Defaults are production-grade, not demo-grade.** Customer-managed Vault keys for encryption at rest. Private subnets unless public access is explicitly justified. Resource Principal authentication for workloads — no user credentials in running services.
2. **Compartments are your first blast-radius control.** Every environment and every team gets its own compartment. IAM policies are attached at the compartment boundary, not the tenancy root.
3. **Cost is a first-class concern.** Every skill surfaces cost-amplifying choices (oversized flex shapes, idle Autonomous Database instances, cross-region data transfer) at decision time.
4. **Observability before launch.** No workload ships without Monitoring alarms, Logging enabled, and at least one notification channel wired to a real recipient.
5. **IaC over console.** Console steps appear only for initial tenancy and administrator setup. Everything else ships as Terraform or Resource Manager stacks.
6. **OCI Well-Architected as a checklist, not a vibe.** The `oci-architect` agent maps findings to the five pillar best practices from Oracle's Cloud Adoption Framework.

## Conventions

- Skills assume the OCI CLI ≥ 3.45 is installed and a profile is configured (`oci setup config`).
- IaC examples target: Terraform ≥ 1.6 with `oracle/oci` provider ≥ 6.x; Resource Manager stacks for managed execution.
- Region and compartment OCID are always explicit — no implicit tenancy-root assumptions.
- All examples use Resource Principal authentication for workloads and Instance Principal for Compute. User API keys appear only in developer local setups.
- Examples cover single-tenancy first; multi-region and dedicated-region callouts are marked explicitly.
