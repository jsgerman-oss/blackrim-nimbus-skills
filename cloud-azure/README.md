# cloud-azure

Microsoft Azure development toolkit for Claude Code. Loads as a plugin from the parent `plugins/` marketplace.

<!-- BEGIN: what's inside -->
## What's inside

**Skills** — invoked automatically by description match, or with `/<skill-name>`:

| Skill | Description |
| --- | --- |
| `azure-compute` | Choose, design, or harden Azure compute — Azure Functions, AKS, Container Apps, App Service, Container Instances, Azure VMs, Batch. Use when picking a runtime, sizing capacity, configuring autoscaling, or reviewing a compute architecture for cost / latency / availability. |
| `azure-iac-and-deployment` | Choose, scaffold, or review Azure Infrastructure-as-Code and deployment — Bicep, ARM templates, Terraform (azurerm + azapi), Azure DevOps Pipelines, GitHub Actions with OIDC federation, Deployment Stacks. Use when starting a new IaC project, picking a tool, or hardening a release path. |
| `azure-identity-and-security` | Design or audit Azure identity, access, and security posture — Microsoft Entra ID, Managed Identities, Azure RBAC, Key Vault, Defender for Cloud, Microsoft Sentinel, Conditional Access, Privileged Identity Management. Use when writing role assignments, scoping identities, hardening an account, or responding to a Defender finding. |
| `azure-networking-and-edge` | Design or audit Azure networking — VNet, subnets, NSGs, peering, hub-spoke, Application Gateway, Azure Front Door, API Management, Private Link, Azure Firewall, ExpressRoute. Use when standing up a new VNet, exposing a service to the internet, or hardening the network perimeter. |
| `azure-observability-and-cost` | Wire up or audit Azure observability and cost — Azure Monitor, Application Insights, Log Analytics, diagnostic settings, Cost Management + Billing, Azure Advisor, Reservations, Savings Plans, Spot scheduling. Use when adding telemetry, tracking down a regression, or shrinking an Azure bill. |
| `azure-storage-and-databases` | Design or audit Azure storage and database tiers — Blob Storage, ADLS Gen2, Azure Files, Azure SQL DB, Cosmos DB, PostgreSQL / MySQL Flexible Server, Azure Cache for Redis Enterprise, Synapse Analytics. Use when picking a data store, modeling access patterns, sizing, securing, or backing up data. |

**Sub-agents** — call explicitly via `subagent_type`:

| Agent | Description |
| --- | --- |
| `azure-architect` | Azure Well-Architected reviewer. Use when the user asks for an architecture review, "is this design sound", a pre-launch audit, or wants findings against the five Azure Well-Architected Framework pillars (reliability, security, cost optimization, operational excellence, performance efficiency). |
| `azure-security-reviewer` | Azure security reviewer. Use when the user asks for a security audit, threat model, Managed Identity posture review, pre-launch security check, incident-readiness review, or wants to validate posture against Microsoft Cloud Security Benchmark (MCSB), CIS Azure Foundations, or Defender for Cloud recommendations. |

**Slash commands:**

| Command | Description |
| --- | --- |
| `/azure-scaffold-iac` | Scaffold an Azure Infrastructure-as-Code project — primary Bicep or Terraform, with opinionated production-grade defaults. ARM templates are legacy and are not generated. |
<!-- END: what's inside -->

## Install

This plugin ships inside the Blackrim.dev repo's `plugins/` marketplace. From a Claude Code session:

```text
/plugin marketplace add /Users/jayse/Code/blackrim/plugins
/plugin install cloud-azure@blackrim-cloud-toolkits
```

## Design principles

1. **Defaults are production-grade, not demo-grade.** Encryption at rest with customer-managed keys in Key Vault. Private endpoints for PaaS where supported. Managed Identities instead of service principal secrets. NSG default-deny.
2. **Cost is a first-class concern.** Every skill flags cost-amplifying choices (idle App Service plans, premium tier for unpredictable workloads, cross-region replication overhead) at decision time.
3. **Observability before launch.** No workload ships without metrics, logs, traces, and at least one alert routed to a real channel.
4. **IaC over portal.** Portal steps appear only for bootstrapping (root/global admin hardening). Everything else is Bicep or Terraform.
5. **Azure Well-Architected as a checklist, not a vibe.** The `azure-architect` agent maps findings to specific pillar best practices.

## Conventions

- Skills assume the Azure CLI v2.65+ is installed and a subscription is active (`az account show`).
- IaC examples target the most current stable versions: Bicep >= 0.27, `hashicorp/azurerm` provider >= 4.x, `Azure/azapi` provider >= 2.x.
- Resource location (region) is always explicit — no implicit region magic.
- All examples assume a single subscription first; multi-subscription / Management Group topology is called out where it changes the answer.
- ARM templates are treated as legacy output format. All new authoring uses Bicep, which compiles to ARM.
