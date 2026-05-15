---
name: gcp-iac-and-deployment
description: Choose, scaffold, or review GCP Infrastructure-as-Code and deployment — Terraform (hashicorp/google + google-beta), Config Connector (KCC), Cloud Deployment Manager (legacy), Cloud Build, Cloud Deploy (continuous delivery), Workload Identity Federation for GitHub Actions / GitLab OIDC. Use when starting a new IaC project, picking a tool, designing a CI/CD pipeline, or hardening a release path.
---

# GCP Infrastructure-as-Code and Deployment

## When to use

- Greenfield project — picking an IaC tool for GCP resources.
- Moving console-built infrastructure into code.
- Designing a CI/CD pipeline for application code and infrastructure together.
- Evaluating Config Connector for teams using Kubernetes as the control plane.
- Hardening a release path for safe rollout and rollback.
- Reviewing an existing IaC repo for drift, secret exposure, or state hygiene.

## IaC tool — picking one

| Tool | Pick when |
| --- | --- |
| **Terraform / OpenTofu** | Multi-cloud, multi-provider (Cloudflare DNS + GitHub + GCP + ...), large community module ecosystem, team already knows HCL. The default choice for most GCP organizations. |
| **Config Connector (KCC)** | The platform team already manages GCP resources from Kubernetes and wants a unified control plane. GKE is the mandatory prerequisite. |
| **Pulumi** | Team strongly prefers a general-purpose language (Go, TypeScript, Python) over HCL and wants multi-cloud support. Same niche as Terraform with a different authoring model. |
| **Cloud Deployment Manager** | Existing large legacy investment and migration budget is zero. Otherwise: migrate to Terraform or KCC. Deployment Manager is in maintenance mode. |

For most teams starting fresh: **Terraform** with `hashicorp/google` ≥ 5.x and `hashicorp/google-beta` ≥ 5.x. Config Connector is the right answer specifically for platform teams that want GitOps over GCP resources alongside Kubernetes application delivery.

## Terraform for GCP — key patterns

### Provider configuration

```hcl
terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 5.0"
    }
  }
  required_version = ">= 1.6"
}

provider "google" {
  project = var.project_id
  region  = var.region
}
```

Use `google-beta` only for resources that are in beta. Keep the beta provider at the same version as the stable provider. Do not use `google-beta` for stable resources — it adds churn without benefit.

### State management

- GCS backend with a CMEK-encrypted bucket in a dedicated `infra-tfstate` project.
- One state file per environment (dev, stage, prod) and per major component (network, data, compute). Never one state file for the entire organization.
- State locking via the GCS backend's native object versioning — no separate lock table needed (unlike AWS where DynamoDB is required).
- The `infra-tfstate` project's bucket should have `uniform_bucket_level_access`, `versioning`, and `retention_policy` enabled; only the CI/CD pipeline SA gets `roles/storage.objectAdmin` on it.

### Module hygiene

- Use Terraform Registry community modules where they exist and are well-maintained: `terraform-google-modules/*` from the `GoogleCloudPlatform` org.
- Pin module versions: `~> 5.0` is acceptable; unpinned `>= 5.0` invites surprise across plan runs.
- Lockfile (`terraform.lock.hcl`) must be checked in.
- Separate modules for network (VPC, subnets, NAT), data (Cloud SQL, Firestore, Cloud Storage buckets), and compute (Cloud Run, GKE, Compute Engine). Don't mix layers in one module.
- `lifecycle { prevent_destroy = true }` on all stateful resources (databases, Cloud Storage buckets, KMS keys) in prod workspaces.

## Config Connector (KCC)

- KCC runs as a GKE add-on; it watches Kubernetes custom resources and reconciles them with GCP APIs.
- Each KCC resource corresponds to a GCP resource type (e.g., `StorageBucket`, `SQLInstance`, `PubSubTopic`).
- Workload Identity is mandatory: the KCC controller's Kubernetes service account is annotated with a GCP service account that holds the IAM roles needed to manage your resources.
- Namespace-scoped vs cluster-scoped mode: namespace-scoped (each namespace targets a different GCP project) is the right model for multi-team platforms.
- Config Connector complements Terraform: use Terraform for foundational infrastructure (projects, VPCs, IAM bindings, KMS keys) and KCC for resources that are tightly coupled to application delivery (Cloud SQL databases for a specific app, Pub/Sub topics for a microservice).

## CI/CD authentication to GCP — no keys

- **GitHub Actions → GCP**: use Workload Identity Federation with the `google-github-actions/auth` action. Trust policy scoped to the repo and optionally the ref (`refs/heads/main`) to limit which pipelines can apply Terraform to prod.
- **GitLab CI → GCP**: same pattern, but the OIDC issuer is `https://gitlab.com`; the subject claim encodes `project_path:ref_type:ref`.
- **Cloud Build**: Cloud Build runners are GCP VMs; they use a service account attached to the build. Scope this SA to the minimum roles needed (`roles/run.developer`, `roles/artifactregistry.writer`).
- Separate service accounts for plan (read-only: `roles/viewer` on target project) and apply (full resource management). Most PRs only need plan.

## Pipeline stages

1. **Lint and static analysis.** `terraform fmt -check`, `tflint --init && tflint`, `terraform validate`, and a security scanner (`checkov`, `trivy config`). Fail fast, sub-minute.
2. **Plan.** `terraform plan -out=plan.tfplan`. Post the plan output as a PR comment for human review. Use `terraform-plan-comment` or an equivalent action.
3. **Test.** For complex modules: `terratest` (Go) or `kitchen-terraform` for integration tests in a sandbox project. Snapshot tests for KCC YAML manifests.
4. **Apply (dev/stage).** Merge to a long-lived branch → apply automatically after plan review.
5. **Apply (prod).** Manual approval gate (PR approve + a pipeline job that requires a protected environment token) or a tag-based release trigger. Never `terraform apply` from a developer laptop in prod.
6. **Drift detection.** Scheduled `terraform plan -refresh-only` with a notification on any non-empty diff. Console changes during incidents become invisible drift without this.

## Cloud Build

- Define build steps in `cloudbuild.yaml`. Use substitutions for environment-specific variables.
- Trigger types: push to branch (PR CI), tag (release), manual (for prod apply).
- Use the `gcr.io/cloud-builders/gcloud` or a custom builder image with Terraform installed; pin the builder image tag.
- Cloud Build service account: grant only the IAM roles needed for that specific pipeline step. The default SA inherits `roles/editor` — replace it.
- Build logs: always routed to Cloud Logging. Enable `privatePool` for builds that need VPC connectivity (e.g., connecting to a private Cloud SQL instance during a migration).

## Cloud Deploy

- Cloud Deploy manages continuous delivery for containerized workloads on Cloud Run, GKE, and GKE Enterprise.
- Delivery pipeline: defines the sequence of targets (dev → stage → prod).
- Release: a snapshot of the configuration and container images at a point in time.
- Rollout: a promotion of a release to a specific target. Supports canary and blue/green strategies natively.
- Approval gates: mark a target as requiring approval (`requireApproval: true`) before a rollout to prod proceeds.
- Automation: use the automation resource to define policies like `auto-repair` (rollback if a release fails health checks) and `advance` (automatically promote to the next target after success).

## Deployment patterns

| Pattern | How on GCP |
| --- | --- |
| Blue/green | Cloud Run traffic splitting (`google_cloud_run_v2_service` with `traffic` blocks); GKE Deployment + Service with label swap |
| Canary | Cloud Run `traffic` block with percentage split; GKE with Istio / Cloud Service Mesh weighted routing |
| Rolling update | GKE Deployment rolling update strategy; Compute Engine managed instance group rolling replacement |
| Feature flags | Feature flag service (LaunchDarkly, Statsig) or a Firestore-backed flag store — GCP has no native feature flag service |

Always set up rollback first. A deploy you cannot safely undo is a deploy you should not do.

## Secrets in IaC

- Never commit secrets (Cloud SQL passwords, API keys, signing keys) to Terraform variable files or configuration files.
- For pipeline secrets: reference Secret Manager at build or apply time using `gcloud secrets versions access latest --secret=<name>` in a Cloud Build step, or via Terraform's `google_secret_manager_secret_version` data source.
- Terraform `sensitive = true` on any output containing a credential — prevents printing to CI logs.
- State encryption: the GCS backend does not natively encrypt state beyond GCS-level encryption (CMEK applies). Consider using the `encrypt_state_at_rest` option with a KMS key if regulatory requirements demand it.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Cloud Deployment Manager for new projects | Maintenance mode; limited provider ecosystem; HCL and JSON templates are harder to test than Terraform. Migrate forward. |
| Service-account key file as a CI secret | Persistent credential that is hard to rotate. Use Workload Identity Federation. |
| Single Terraform state file for the whole organization | One bad apply plan destroys shared network infrastructure. Split by blast radius. |
| `terraform apply` run from a developer laptop for prod | No audit trail, no lock enforcement, no approval gate. Pipeline-only applies. |
| `google-beta` provider for all resources | Adds unnecessary churn; beta features can be removed or changed. Use `google` for stable, `google-beta` only when needed. |
| No drift detection | Console fixes during incidents become invisible permanent drift. |
| Cloud Build SA with `roles/editor` on the project | Default but dangerous. Define a scoped SA per pipeline. |

## Defaults — release pipeline

- Trunk-based development. Feature branches are short-lived.
- PRs require: passing lint + plan + at least one human code review.
- Container images tagged with the full git SHA; never `:latest` in prod.
- Artifact Registry scan-on-push; gate prod Cloud Run or GKE deployments on `CRITICAL` and `HIGH` vulnerability findings.
- Every deployment emits a log entry to Cloud Logging with the git SHA and deployer identity so dashboards can correlate deploys with behavior changes.
- Rollback: single Terraform variable change (image tag) or a Cloud Run traffic split revert, checked in and applied via the pipeline.

## Cost considerations

- Cloud Build billed by build-minute. Cache Docker layers and use parallel build steps to minimize build time.
- Cloud Deploy: no additional charge beyond the underlying compute; the delivery pipeline overhead is negligible.
- Terraform state in GCS: storage cost is negligible; retrieval operations are cheap.
- Test infrastructure created by `terratest` must be torn down in the test teardown — orphaned test VPCs and Cloud SQL instances accumulate cost silently.

## Verification checklist

- [ ] Terraform ≥ 1.6 with `hashicorp/google` ≥ 5.x; lockfile checked in.
- [ ] GCS remote state backend; per-environment state files; state bucket CMEK-encrypted.
- [ ] No service-account key files in CI — Workload Identity Federation for all external CI.
- [ ] Plan output posted on PRs; human review required for prod apply.
- [ ] Stateful resources in isolated workspaces with `prevent_destroy = true`.
- [ ] Labels (`environment`, `service`, `owner`, `cost_center`) applied to every resource via a shared locals block.
- [ ] Cloud Build SA scoped per pipeline; no default `roles/editor` SA.
- [ ] Rollback procedure tested at least once per quarter.
- [ ] Drift detection running on a schedule; alert on non-empty refresh plans.
- [ ] Secrets referenced from Secret Manager at runtime, not baked into IaC or build images.
