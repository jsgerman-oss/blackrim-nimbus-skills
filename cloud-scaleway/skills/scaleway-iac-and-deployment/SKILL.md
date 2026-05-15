---
name: scaleway-iac-and-deployment
description: Choose, scaffold, or review Scaleway Infrastructure-as-Code and deployment — scw CLI, Terraform scaleway/scaleway provider, Pulumi pulumiverse/scaleway (community), Crossplane, GitOps with Kapsule, GitHub Actions OIDC patterns. Use when starting a new IaC project, picking a tool, or hardening a release path.
---

# Scaleway Infrastructure-as-Code and Deployment

## When to use

- Greenfield project — picking an IaC tool for Scaleway.
- Inheriting console-built infrastructure that needs to come into code.
- Designing a CI/CD pipeline for application + Scaleway infrastructure.
- Hardening a release for safe rollout and rollback on Kapsule or Serverless Containers.
- Reviewing an existing IaC repo for drift, secrets, and state hygiene.

## IaC tool — picking one

| Tool | Pick when |
| --- | --- |
| **Terraform / OpenTofu with `scaleway/scaleway` provider** | Primary recommendation. Best Scaleway coverage, active community, largest module ecosystem. Use for all new Scaleway projects. Provider ≥ 2.45 required for current resource parity. |
| **`scw` CLI** | Bootstrap tasks (initial Organization setup, one-off resource creation, scripted automation). Not a substitute for declarative IaC — use for commands where Terraform has no resource yet. |
| **Pulumi `pulumiverse/scaleway`** | Community-maintained Pulumi provider. Use if the team strongly prefers TypeScript/Python over HCL and is willing to accept community-tier support. Verify resource parity before committing. |
| **Crossplane `scaleway-crossplane-provider`** | When you want Kubernetes to be the control plane for Scaleway infra. Niche but powerful for platform engineering teams already running Kapsule. |
| **GitOps (Flux / ArgoCD)** | Not an IaC tool for Scaleway resources, but the right delivery mechanism for Kapsule application manifests. Combine with Terraform for infra + Flux/ArgoCD for app delivery. |

Scaleway does not publish a first-party CDK or CloudFormation equivalent. Terraform is the de-facto standard.

## State management (Terraform)

- Backend: Scaleway Object Storage as the Terraform state backend. Use the S3-compatible backend configuration with a Scaleway endpoint.
- Lock table: Scaleway Object Storage does not support DynamoDB-style state locking natively. Use Terraform Cloud/Enterprise, or a separate Postgres-based lock (via the `pg` backend), or accept the risk with process-level serialization in CI (one apply at a time per workspace).
- Per-environment separation: one state file per environment (`dev/`, `stage/`, `prod/`). Never share state across environments.
- Encryption: enable server-side encryption on the state bucket (SSE-S3 or CMEK via Key Manager).
- Stateful resources (Managed Databases, Object Storage buckets, Redis Clusters) in a separate Terraform workspace from compute (Instances, Kapsule, Serverless) — stateful resources outlive compute, and a failed apply to compute should not touch data-tier state.

Example Object Storage backend block:

```hcl
terraform {
  backend "s3" {
    bucket                      = "tfstate-myproject-prod"
    key                         = "compute/terraform.tfstate"
    region                      = "fr-par"
    endpoint                    = "https://s3.fr-par.scw.cloud"
    access_key                  = var.scw_access_key   # from Secret Manager at CI time
    secret_key                  = var.scw_secret_key
    skip_credentials_validation = true
    skip_metadata_api_check     = true
    skip_region_validation      = true
    force_path_style            = true
  }
}
```

## Provider configuration

```hcl
terraform {
  required_providers {
    scaleway = {
      source  = "scaleway/scaleway"
      version = "~> 2.45"
    }
  }
  required_version = ">= 1.6"
}

provider "scaleway" {
  zone       = "fr-par-1"
  region     = "fr-par"
  project_id = var.scaleway_project_id
  # access_key and secret_key from environment (SCW_ACCESS_KEY, SCW_SECRET_KEY)
  # or from ~/.config/scw/config.yaml (local dev only)
}
```

## Module hygiene

- Use Terraform modules for repeatable patterns (Kapsule cluster + node pool, Serverless Container + domain, Managed Database + Private Network attachment).
- Pin module source versions when using external modules — `?ref=vX.Y.Z` for git-based modules.
- Do not create a wrapper module until you have ≥ 3 consumers. Premature abstraction adds indirection with no benefit at small scale.
- Lockfile: commit `.terraform.lock.hcl` to git. Provider updates must be explicit (`terraform init -upgrade`).

## CI/CD pipeline — the spine

### Authentication

Scaleway does not support GitHub Actions OIDC federation as of 2026-Q2 (no native `sts.amazonaws.com`-equivalent for OIDC dynamic trust). The current pattern:

1. Create a dedicated CI IAM Application per environment (e.g., `ci-terraform-prod`).
2. Generate an API key with a limited expiry (90 days maximum; set a calendar reminder to rotate).
3. Store `SCW_ACCESS_KEY` and `SCW_SECRET_KEY` as encrypted secrets in the CI system (GitHub Actions encrypted secrets, GitLab CI variables).
4. Scope the CI Application's Policy to only the Terraform operations needed (compute read/write, network read/write) — not a blanket Organization-admin policy.
5. Rotate the key before expiry; update CI secrets atomically (create new → update CI → delete old).

Monitor for native OIDC support in Scaleway IAM; when available, migrate to short-lived tokens.

### Pipeline stages

1. **Lint / static analysis.** `terraform fmt -check`, `tflint`, `checkov --framework terraform` targeting Scaleway resources. Fail fast, sub-minute.
2. **Validate.** `terraform validate` with provider initialized.
3. **Plan.** `terraform plan -out=plan.tfplan`. Post the plan as a PR comment (use `terraform-plan-comment` GitHub Action or equivalent).
4. **Apply (dev/stage).** Merge to dev/stage branch → apply automatically.
5. **Apply (prod).** Manual approval gate or tag-based release (not auto-apply on main merge).
6. **Drift detection.** Scheduled `terraform plan -refresh-only` → alert if diff is non-empty.

### Deployment patterns for Kapsule (Kubernetes)

- **Rolling**: default Kubernetes `Deployment` rolling update. Set `maxSurge: 1` and `maxUnavailable: 0` for zero-downtime deploys.
- **Blue/green**: two `Deployment` objects sharing a `Service`; switch the `Service` selector label to cut over. Use Argo Rollouts for automated analysis + traffic shifting.
- **Canary**: Argo Rollouts or NGINX Ingress weight annotations. Start at 5% canary weight; promote after error/latency analysis.
- **Feature flags**: implement in application code (Unleash, Flagsmith, LaunchDarkly) — do not deploy new Kubernetes resources per flag.

### Deployment patterns for Serverless Containers

- Container revisions are immutable. Each deploy creates a new revision.
- Traffic splitting: Scaleway Serverless Containers supports traffic splitting between revisions. Use this for canary rollouts — route 5% to the new revision, promote after validation.
- Rollback: `scw container deploy <id> --revision <previous-revision-id>` or set Terraform to the previous image tag and apply.

Always set up rollback first, then the forward deploy.

## Secrets in IaC

- Never commit secrets in `terraform.tfvars` or as plaintext Terraform variables.
- For pipeline secrets: CI system encrypted secrets → environment variables → Terraform variables at plan/apply time.
- For application secrets: IaC creates the Secret Manager secret shell and version placeholder; actual secret values are populated by a separate secure process (manual via `scw secret version create`, or a secrets rotation job).
- `terraform output` of sensitive values: mark `sensitive = true` so they don't appear in CI logs or `terraform show` output.
- State files may contain sensitive resource attributes — ensure the state bucket is private and access-logged.

## `scw` CLI quick reference

```bash
# Profile setup
scw config set access-key <key>
scw config set secret-key <secret>
scw config set default-project-id <project-id>
scw config set default-region fr-par

# Kapsule bootstrap
scw k8s cluster create name=<name> version=1.31 cni=cilium

# Serverless Container deploy
scw container deploy <container-id> --image <registry>/<image>:<tag>

# Instance management
scw instance server create type=GP1-S image=ubuntu_jammy

# Managed Database
scw rdb instance create name=<name> engine=PostgreSQL-16 node-type=DB-GP-M

# Secret Manager
scw secret create name=<name> --description "..." 
scw secret version create <secret-id> --data "$(echo -n '<value>' | base64)"

# Audit Trail
scw audit-trail events list --project-id <id> --since 24h
```

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Console-built infrastructure never codified | Drift forever; no review trail; impossible to reproduce. Codify before second resource. |
| Single Terraform state for all environments | One bad apply touches everything. Per-env state separation. |
| `terraform apply` from a developer laptop against prod | No audit trail, no approval gate. Pipeline-only prod applies. |
| Long-lived CI API keys with Organization-admin scope | Leaked key = full Organization. Scope to Project; minimum required permissions. |
| Auto-apply to prod on merge to main | One bad merge = production outage. Manual approval gate. |
| No drift detection schedule | Console fixes during incidents become permanent invisible drift. |
| Serverless Container image tag `:latest` | Rollback is impossible — you don't know what `:latest` was. Tag with git SHA. |
| Pulumi `pulumiverse/scaleway` without verifying resource parity | Community provider may lag — missing resources silently become manual console steps. |

## Defaults — release pipeline

- Trunk-based development; feature branches short-lived (< 3 days ideal).
- PRs require: passing lint + plan + at least one human reviewer for infra changes.
- Container images tagged with git SHA (`<registry>/<image>:<sha>`); never `:latest` in production.
- Every deploy to prod emits a structured log / marker (deployment event) so Cockpit dashboards can correlate change with behavior change.
- Rollback is a single `terraform apply` with the previous image tag, or a `scw container deploy --revision` command — document it in the runbook.
- IaC is idempotent: re-running `terraform apply` on an unchanged plan succeeds and changes nothing.

## Cost considerations

- Terraform Cloud / Spacelift: evaluate only if self-hosted runners + Object Storage backend becomes operationally painful. For small teams, a GitHub Actions self-hosted runner + S3 backend is sufficient.
- Test infra (Terratest or `scw` CLI scripts) must be torn down in cleanup blocks — orphaned test databases and Instances accumulate quietly.
- CI runner: use Scaleway Serverless Jobs for ephemeral CI runs (Terraform plan + apply) to avoid always-on runner costs.

## Observability hints

- Tag every resource in IaC with `tags = ["env:prod", "team:platform", "service:api"]`.
- Pipeline metrics: track deployment frequency, lead time, change failure rate, and mean time to recovery as DORA metrics — they tell you whether the pipeline is helping or hurting.

## Verification checklist

- [ ] Terraform `scaleway/scaleway` provider ≥ 2.45 with lockfile committed.
- [ ] State stored in Object Storage; per-environment workspace separation; state bucket private and access-logged.
- [ ] No long-lived Organization-admin keys in CI — Project-scoped Application with minimum required permissions.
- [ ] Plan / diff posted on PR; human approval required for prod applies.
- [ ] Stateful resources (Managed DB, Redis, buckets) in separate Terraform workspace with `deletion_protection` or `prevent_destroy`.
- [ ] Tags applied to all resources in IaC.
- [ ] Container images tagged with git SHA; rollback procedure documented.
- [ ] Drift detection running on a schedule; alerts on non-empty plans.
- [ ] CI API keys have expiration; rotation calendar reminder set.
