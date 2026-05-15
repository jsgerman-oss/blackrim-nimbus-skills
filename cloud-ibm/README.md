# cloud-ibm

IBM Cloud development toolkit for Claude Code. Loads as a plugin from the parent `plugins/` marketplace.

IBM Cloud has two account models: the **Classic infrastructure** (legacy bare metal, VLANs, classic VSIs) and **VPC / Gen 2** (software-defined networking, VPC VSIs, VPC Bare Metal). This plugin defaults to **VPC / Gen 2** — the current standard for all new workloads. Classic references appear only where migration or legacy context is relevant.

<!-- BEGIN: what's inside -->
## What's inside

**Skills** — invoked automatically by description match, or with `/<skill-name>`:

| Skill | Description |
| --- | --- |
| `ibm-compute` | Choose, design, or harden IBM Cloud compute — VPC Virtual Server Instances, VPC Bare Metal, Code Engine (serverless containers / Jobs / Functions), IKS, Red Hat OpenShift on IBM Cloud (ROKS), and Power Systems. Use when picking a runtime, sizing capacity, configuring autoscaling, or reviewing a compute architecture for cost, latency, or availability. |
| `ibm-iac-and-deployment` | Choose, scaffold, or review IBM Cloud Infrastructure-as-Code and deployment — Terraform IBM-Cloud/ibm provider, IBM Cloud Schematics (managed Terraform), IBM Cloud Continuous Delivery Toolchains, Tekton pipelines, GitOps for ROKS/IKS, ibmcloud CLI and plugin ecosystem. Use when starting a new IaC project, picking a delivery tool, or hardening a release pipeline. |
| `ibm-identity-and-security` | Design or audit IBM Cloud identity and security posture — IAM Account / ResourceGroup / Service policies, Access Groups, Trusted Profiles for OIDC and compute identity, Secrets Manager, Key Protect (BYOK), Hyper Protect Crypto Services (KYOK / FIPS 140-2 Level 4), Security and Compliance Center, Activity Tracker, App ID. Use when writing IAM policies, scoping Access Groups, rotating secrets, managing encryption keys, or hardening account security posture. |
| `ibm-networking` | Design or audit IBM Cloud networking — VPC, subnets, Security Groups, ACLs, Public Gateways, Floating IPs, VPN-for-VPC, Transit Gateway, Direct Link, Cloud Internet Services, Private Path / Endpoint Gateways. Use when standing up a new VPC, connecting workloads, exposing services, or hardening network posture. |
| `ibm-observability-and-cost` | Wire up or audit IBM Cloud observability and cost — IBM Cloud Monitoring (Sysdig), IBM Cloud Logs (LogDNA), Activity Tracker, Cost Estimator, IBM Cloud Subscriptions (Committed Use), Showback / Chargeback patterns, Resource Group tagging. Use when adding telemetry to a new service, building dashboards, setting alerts, or analyzing cloud spend. |
| `ibm-storage-and-databases` | Design or audit IBM Cloud storage and database tiers — Cloud Object Storage, Block/File Storage for VPC, Cloudant, Db2 on Cloud, Databases for PostgreSQL / Redis / MongoDB / Elasticsearch / etcd / RabbitMQ / MySQL, Hyper Protect DBaaS. Use when picking a data store, modeling access patterns, sizing, securing, or configuring backups. |

**Sub-agents** — call explicitly via `subagent_type`:

| Agent | Description |
| --- | --- |
| `ibm-architect` | IBM Cloud architecture reviewer. Use when the user asks for an architecture review, "is this design sound", a pre-launch audit, or wants findings against the IBM Cloud Architecture Framework pillars — regulated-workload fit, reliability, security, performance efficiency, cost optimization, and operational excellence. |
| `ibm-security-reviewer` | IBM Cloud security reviewer. Use when the user asks for a security audit, threat model, IAM least-privilege review, pre-launch security check, or wants to validate posture against IBM Cloud Framework for Financial Services, CIS IBM Cloud Foundations, ISO 27001, NIST 800-53, or SCC profile findings. |

**Slash commands:**

| Command | Description |
| --- | --- |
| `/ibm-scaffold-iac` | Scaffold an IBM Cloud Infrastructure-as-Code project — Terraform IBM-Cloud/ibm provider or IBM Cloud Schematics, with opinionated production-grade defaults. |
<!-- END: what's inside -->

## Install

This plugin ships inside the Blackrim.dev repo's `plugins/` marketplace. From a Claude Code session:

```text
/plugin marketplace add /Users/jayse/Code/blackrim/plugins
/plugin install cloud-ibm@blackrim-cloud-toolkits
```

## Design principles

1. **VPC Gen 2 by default.** Classic infrastructure is legacy. All new designs use VPC subnets, VPC Security Groups, and VPC-native services unless the workload has an explicit Classic dependency.
2. **Defaults are production-grade, not demo-grade.** Encryption at rest with Key Protect or Hyper Protect Crypto Services. Private subnets for workloads. IAM Access Groups — no inline per-user policies. Activity Tracker on from day one.
3. **Regulated-workload awareness.** IBM Cloud has Financial Services-validated regions (`us-south`, `us-east`, `eu-de`, `eu-gb`) with additional controls for FFIEC, DORA, and FedRAMP. Surface these options where relevant.
4. **Trusted Profiles over API keys.** Workloads running on IBM Cloud compute authenticate via Trusted Profiles with compute identity — not long-lived API keys. This applies to Code Engine jobs, VPC VSIs, IKS pods, and ROKS.
5. **Cost is a first-class concern.** IBM Cloud Subscriptions (Committed Use) reduce effective rates significantly for stable workloads. Every skill flags the subscription / on-demand trade-off.
6. **Observability before launch.** IBM Cloud Monitoring (Sysdig) and IBM Cloud Logs (LogDNA) wired up before any workload reaches production.
7. **IaC over console.** The `IBM-Cloud/ibm` Terraform provider and IBM Cloud Schematics are the primary delivery mechanisms. Console steps appear only for initial account setup.

## Conventions

- Skills assume the `ibmcloud` CLI (>= 2.25) is installed and `ibmcloud login --sso` has been run.
- IaC examples target `IBM-Cloud/ibm` Terraform provider >= 1.65 with OpenTofu >= 1.7 or Terraform >= 1.6.
- Resource Group usage is assumed — no resources placed in `Default` resource group for production.
- All examples assume single-account first; enterprise account hierarchy with account groups is called out where it changes the answer.
- Region defaults are explicit — no implicit `us-south` magic.
