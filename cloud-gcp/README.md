# cloud-gcp

Google Cloud development toolkit for Claude Code. Loads as a plugin from the parent `plugins/` marketplace.

<!-- BEGIN: what's inside -->
## What's inside

**Skills** — invoked automatically by description match, or with `/<skill-name>`:

| Skill | Description |
| --- | --- |
| `gcp-compute` | Choose, design, or harden GCP compute — Cloud Run, GKE (Autopilot vs Standard), Cloud Functions Gen 2, App Engine, Compute Engine. Use when picking a runtime, sizing capacity, configuring autoscaling, or reviewing a compute architecture for cost, latency, or availability. |
| `gcp-iac-and-deployment` | Choose, scaffold, or review GCP Infrastructure-as-Code and deployment — Terraform (hashicorp/google + google-beta), Config Connector (KCC), Cloud Deployment Manager (legacy), Cloud Build, Cloud Deploy (continuous delivery), Workload Identity Federation for GitHub Actions / GitLab OIDC. Use when starting a new IaC project, picking a tool, designing a CI/CD pipeline, or hardening a release path. |
| `gcp-identity-and-security` | Design or audit GCP identity, access, and security posture — Cloud IAM (allow + deny policies, conditions), Workload Identity Federation for non-GCP CI, Workload Identity for GKE, Secret Manager, Cloud KMS (CMEK + EKM), Security Command Center, BeyondCorp Enterprise, Binary Authorization, Org Policies. Use when writing IAM bindings, configuring Workload Identity, rotating secrets, scoping service accounts, or hardening an organization. |
| `gcp-networking-and-edge` | Design or audit GCP networking — VPC (auto vs custom, Shared VPC), Cloud Load Balancing (Global vs Regional, Application / Network), Cloud CDN, Cloud Armor, Cloud DNS, VPC Service Controls, Private Service Connect, Cloud NAT. Use when standing up a new VPC, exposing a service, hardening edge, or auditing connectivity. |
| `gcp-observability-and-cost` | Wire up or audit GCP observability and cost — Cloud Monitoring, Cloud Logging (log sinks to BigQuery / GCS / Pub/Sub), Cloud Trace, Profiler, Error Reporting, Recommender, Active Assist, Committed Use Discounts, Spend Alerts. Use when adding telemetry, tracking down a regression, or shrinking a bill. |
| `gcp-storage-and-databases` | Design or audit GCP storage and database tiers — Cloud Storage, Persistent Disk, Cloud SQL, AlloyDB, Spanner, Firestore, Memorystore, BigQuery. Use when picking a data store, modeling access patterns, sizing capacity, securing data, or configuring lifecycle and backups. |

**Sub-agents** — call explicitly via `subagent_type`:

| Agent | Description |
| --- | --- |
| `gcp-architect` | Google Cloud Architecture Framework reviewer. Use when the user asks for an architecture review, "is this design sound", a pre-launch audit, or wants findings against the six Google Cloud Architecture Framework pillars (operational excellence, security and compliance, reliability, cost optimization, performance optimization, system design). |
| `gcp-security-reviewer` | GCP security reviewer. Use when the user asks for a security audit, IAM least-privilege review, pre-launch security check, incident-readiness review, or wants to validate posture against CIS GCP Benchmarks, GCP Security Foundations, or Org Policy guardrails. |

**Slash commands:**

| Command | Description |
| --- | --- |
| `/gcp-scaffold-iac` | Scaffold a Google Cloud Infrastructure-as-Code project — Terraform (primary) or Config Connector for GKE-centric teams, with opinionated production-grade defaults. |
<!-- END: what's inside -->

## Install

This plugin ships inside the Blackrim.dev repo's `plugins/` marketplace. From a Claude Code session:

```text
/plugin marketplace add /Users/jayse/Code/blackrim/plugins
/plugin install cloud-gcp@blackrim-cloud-toolkits
```

## Design principles

1. **Defaults are production-grade, not demo-grade.** CMEK encryption by default. Private GKE clusters and private Cloud SQL instances unless public access is explicitly justified. Workload Identity instead of service-account key files — always.
2. **Cost is a first-class concern.** Every skill flags cost-amplifying choices (unattached persistent disks, NAT egress, BigQuery on-demand vs slot reservations, idle baselines) at decision time.
3. **Observability before launch.** No workload ships without Cloud Monitoring metrics, Cloud Logging sinks, Cloud Trace, and at least one alerting policy.
4. **IaC over Console.** Console steps appear only as one-time bootstrap (project creation, billing linkage). Everything else is code.
5. **Architecture Framework as a checklist, not a vibe.** The `gcp-architect` agent maps findings to the six Google Cloud Architecture Framework pillars.

## Conventions

- Skills assume the `gcloud` CLI ≥ 470.x is installed and configured (`gcloud auth list`, `gcloud config list`).
- IaC examples target Terraform ≥ 1.6 with `hashicorp/google` provider ≥ 5.x and `hashicorp/google-beta` ≥ 5.x.
- Project and region are always explicit — no implicit `us-central1` defaults.
- All examples assume single-project first; multi-project / Shared VPC / folder hierarchy is called out where it changes the answer.
- Service account key files are never generated or referenced. Workload Identity Federation is the answer for external workloads; Workload Identity for Kubernetes is the answer for GKE pods.
