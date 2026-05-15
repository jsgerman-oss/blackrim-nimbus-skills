---
name: oci-iac-and-deployment
description: Choose, scaffold, or review OCI Infrastructure-as-Code and deployment — Terraform with the oracle/oci provider, Resource Manager (managed Terraform), OCI DevOps service (build and deploy pipelines), GitOps with OKE, OCI CLI. Use when starting a new IaC project, designing a CI/CD pipeline, or hardening a release path.
---

# OCI IaC and Deployment

## When to use

- Greenfield project — picking between Terraform and Resource Manager.
- Codifying console-built OCI infrastructure.
- Designing a CI/CD pipeline using OCI DevOps or GitHub Actions targeting OCI.
- Reviewing an existing Terraform repo for drift, state hygiene, secret handling, or security posture.
- Deploying to OKE via GitOps (Flux or ArgoCD).

## IaC tool — picking one

| Tool | Pick when |
| --- | --- |
| **Terraform with `oracle/oci` provider** | Team already uses Terraform; multi-cloud (OCI + Cloudflare, GitHub, etc.); largest ecosystem. |
| **OpenTofu with `oracle/oci` provider** | Same as above, but you need a fully open-source Terraform-compatible engine without BSL licensing. |
| **OCI Resource Manager** | You want fully managed Terraform execution with no self-hosted runner, native OCI Console / API integration, and drift detection built in. |
| **Pulumi with OCI provider** | Team strongly prefers a general-purpose programming language (Python, TypeScript, Go) over HCL; supports OCI via the Pulumi OCI provider. |

Mixed tools are acceptable with clear boundaries — Terraform for foundations (VCN, compartments, IAM, Vault), OCI DevOps pipelines for application code delivery. Resist deeply nested tool chains without a documented ownership model.

## State management — Terraform

- Backend: OCI Object Storage backend (`oracle/oci` provider supports the S3-compatible backend pointing to an OCI namespace). Encrypt the state bucket with a customer-managed Vault key.
- DynamoDB equivalent: OCI does not have a built-in state lock table equivalent. Use the `lockfile` path argument or Terraform Cloud / HCP Terraform for locking.
- One workspace per environment. Never `if var.environment == "prod"` conditional logic inside a single workspace — separate workspaces and separate state files per env.
- Stateful resources (Autonomous Database, Object Storage buckets, Block Volumes) isolated in their own Terraform stack with `lifecycle { prevent_destroy = true }`. Compute and networking can share another stack.

## Resource Manager — managed Terraform

- Resource Manager executes Terraform plans in OCI's managed environment. No self-hosted runners, no state backend configuration — OCI stores and manages the state.
- Stack: create one Resource Manager stack per environment per scope (networking, compute, database). Stacks share a job history and state.
- Authentication: Resource Manager uses a Resource Principal with the permissions of the Resource Manager service itself in the target compartment — no user API keys in the pipeline.
- Drift detection: Resource Manager can run a `detect drift` job on a schedule — wire the job result to an OCI Events rule and notify on detected drift.
- Variable sources: Resource Manager supports OCI Vault secrets as variable source — pass sensitive values (DB password, API credentials) directly from Vault rather than embedding in the stack configuration.

## Module hygiene

- Use the `oracle/oci` provider ≥ 6.x. Pin the exact version in `required_providers` and check in the `.terraform.lock.hcl` file.
- Prefer community-maintained modules from the Terraform Registry (`oracle-terraform-modules/network/oci`, `oracle-terraform-modules/compute/oci`, etc.) over hand-rolled resources where they cover the use case.
- Don't wrap a community module in your own module "for consistency" until you have ≥ 3 consumers — premature abstraction adds indirection without benefit.
- Each module has its own `README.md`, typed input variables, typed output values, and a `versions.tf`. Never accept untyped `any` variables for inputs that carry resource OCIDs.

## OCI DevOps — build and deploy pipelines

OCI DevOps is a fully managed CI/CD service that integrates natively with OCI Artifact Registry, Container Registry, OKE, Compute instances, Serverless Functions, and Resource Manager.

### Build pipelines

- A build pipeline contains one or more stages. Each stage runs in a managed build runner (OCI-managed or custom, based on an OCI Compute shape and image).
- Reference Vault secrets in build spec using the `vaultVariables` section — secrets are injected as environment variables within the runner only, not logged.
- Artifact output: push container images to OCI Container Registry (OCIR) and deployment artifacts to OCI Artifact Registry. Tag images with the pipeline's `build_run_id` or the triggering Git commit SHA — never `latest`.
- Scan images using OCI Vulnerability Scanning Service after push; gate deployment pipeline execution on the scan result via a wait-for-approval stage or an OCI Events rule checking for `CRITICAL` findings.

### Deploy pipelines

- Deploy pipeline stages: Blue/Green, Canary, Rolling (in-place). All three are supported natively for OKE and Compute instance group deployments.
- Blue/Green for OKE: OCI DevOps deploys to a new namespace, runs health checks, then shifts traffic at the Load Balancer. Rollback is a single-step traffic shift back to the blue namespace.
- Canary for Compute: deploys to a percentage of the instance pool first; a traffic shift stage adjusts the Load Balancer listener rule. Promote to 100% or rollback based on alarm state.
- Approval gate: insert a manual-approval stage before any deploy to production. The approver confirms in the OCI Console or via the CLI — no auto-apply to prod without a sign-off.
- Deployment rollback: every deploy pipeline should have a matching rollback pipeline parameterized by artifact version. Test the rollback pipeline in staging before it is needed in production.

### GitOps with OKE

- Flux or ArgoCD deployed inside the OKE cluster watches a Git repository for manifest changes.
- Image policy: configure Flux's `ImageUpdateAutomation` controller or ArgoCD's image updater to detect new OCIR tags matching a semver pattern and open a PR / auto-commit to the GitOps repository.
- The OCI DevOps build pipeline pushes the image to OCIR; the GitOps controller detects the new tag and applies it to the cluster, completing the loop without manual `kubectl apply`.
- RBAC: the GitOps controller's Kubernetes service account has RBAC permissions to apply manifests in its managed namespaces only. Use Workload Identity to map this service account to an OCI IAM dynamic group with `read` on OCIR and `use` on Artifact Registry.

## Authentication for CI/CD pipelines

- **GitHub Actions / GitLab CI → OCI:** configure OIDC federation between the CI provider and OCI IAM. Create an Identity Provider in OCI that trusts the CI provider's JWKS endpoint. A dynamic group rule matches the pipeline's OIDC `sub` claim; a policy grants that group the permissions needed for the target compartment. No OCI API keys stored in pipeline secrets.
- Separate dynamic groups for plan-equivalent and apply-equivalent access — read-only dynamic group for pull request checks; write dynamic group for merge-to-main deploys.
- OCI DevOps: uses Resource Principal internally — no credentials to manage.

## Secrets in IaC

- Never put secret values in `.tfvars` files checked into Git.
- For Terraform: reference OCI Vault secret OCIDs as data sources (`data.oci_vault_secret.password.id`) and pass the OCID to the resource; resolve the value at apply time using the `oci_secrets_secretbundle` data source.
- Mark sensitive Terraform outputs with `sensitive = true` — this prevents the value from appearing in CI logs on `terraform output`.
- Resource Manager: supply secrets via the Vault variables integration — the secret value is never written to the stack configuration or job history.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Console-provisioned infrastructure with no IaC | Drift is inevitable; reprovisioning or disaster recovery requires reconstruction from memory. |
| API key files for CI/CD in pipeline secret stores | Key rotation is manual; a leaked secret persists until manually rotated. OIDC federation is zero-credential. |
| Single monolithic Terraform state for the whole tenancy | One failed apply risks destroying unrelated production resources. Split by blast-radius scope. |
| Auto-apply on merge to main for the production stack | One bad merge = a production outage. Manual approval gate for every production apply. |
| `latest` image tag in OKE deployment manifests | Rollback requires finding what `:latest` was before — archaeology. Tag with SHA or semver. |
| No Resource Manager drift detection | Console changes during an incident become invisible permanent drift. Schedule weekly drift jobs. |
| Secrets in Terraform state output blocks | `terraform output -json` in a CI log exposes the secret in plaintext. Mark outputs `sensitive = true`; use Vault for runtime resolution. |

## Defaults — release pipeline

- Trunk-based development; short-lived feature branches merged to main by PR.
- PRs require: passing `terraform fmt -check`, `tflint`, `oci-resource-manager validate` (or `terraform validate`), and `checkov`; one human reviewer.
- Build artifacts tagged with git SHA; `:latest` not used in any environment.
- Vulnerability scan gated before production deployment; builds with `CRITICAL` CVEs cannot promote.
- Every deploy emits an OCI Events notification and a Monitoring custom metric for deployment markers so dashboards correlate behavior changes with deploys.
- Rollback is one pipeline run away — parameterized rollback pipeline promotes the previous artifact version.

## Observability hints

- Tag every OCI resource in IaC with `Environment`, `Service`, `Team`, `CostCenter` using Tag Defaults and explicit `freeform_tags` / `defined_tags` in Terraform.
- Track pipeline metrics: build success rate, deploy frequency, mean time to recovery. OCI DevOps exposes these via the Monitoring service.

## IaC hints — key resources

- `oci_devops_project`, `oci_devops_repository`, `oci_devops_build_pipeline`, `oci_devops_deploy_pipeline`, `oci_devops_deploy_stage`, `oci_artifacts_container_repository`.
- `oci_resourcemanager_stack`, `oci_resourcemanager_job` for Resource Manager stacks managed from Terraform (meta-IaC pattern).
- Use `oci_identity_auth_token` only for OCI Container Registry authentication from external CI systems — prefer OIDC Instance Principal for everything inside OCI.
- OCI CLI ≥ 3.45: `oci devops deployment create-pipeline-deployment`, `oci resource-manager job create-plan-job`, `oci artifacts container image scan list`.

## Verification checklist

- [ ] IaC tool choice justified; Resource Manager vs self-hosted Terraform documented.
- [ ] State backend remote, encrypted with a customer-managed Vault key; per-env state separation.
- [ ] No OCI API key files in CI — OIDC federation or Resource Principal.
- [ ] Plan / diff posted as PR comment; human approval required before production apply.
- [ ] Stateful resources isolated in separate Terraform stacks with `prevent_destroy = true`.
- [ ] Tag policy applied in IaC; Tag Defaults configured in the platform stack.
- [ ] Rollback pipeline exists and has been tested in staging.
- [ ] Resource Manager drift detection running on a weekly schedule.
- [ ] Build artifacts tagged with SHA; `:latest` absent from all deployment configurations.
- [ ] Vulnerability scan passes before any deploy reaches production.
