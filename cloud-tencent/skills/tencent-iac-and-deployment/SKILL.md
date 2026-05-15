---
name: tencent-iac-and-deployment
description: Choose, scaffold, or review Tencent Cloud Infrastructure-as-Code and deployment — Tencent Cloud CLI (tccli), Terraform tencentcloudstack/tencentcloud provider, TIC (Tencent Infrastructure-as-Code managed Terraform runner), Coding DevOps CI/CD, GitOps for TKE, GitHub Actions and Jenkins integrations. Use when starting a new IaC project, picking a tool, or hardening a release pipeline.
---

# Tencent IaC and Deployment

## When to use

- Greenfield project — picking an IaC tool for Tencent Cloud.
- Codifying console-built infrastructure that has drifted from any controlled state.
- Designing a CI/CD pipeline for application and infrastructure.
- Hardening a release for safe rollout and rollback.
- Reviewing an existing IaC repo for drift, exposed secrets, or state hygiene.

## IaC tool — picking one

| Tool | Pick when |
| --- | --- |
| **Terraform with `tencentcloudstack/tencentcloud` provider** | Multi-service Tencent Cloud workload; team is comfortable with HCL; best coverage of Tencent Cloud resources. Primary recommendation as of 2026. |
| **TIC (Tencent Infrastructure-as-Code)** | You want a Tencent-managed Terraform runner with native console integration, state managed by Tencent, and no self-hosted pipeline. Runs `tencentcloudstack/tencentcloud` under the hood. |
| **Pulumi** | Team strongly prefers TypeScript / Go / Python over HCL and is willing to maintain Tencent Cloud provider bindings. Less community support than Terraform for Tencent-specific resources. |
| **tccli scripts** | One-off automation, quick incident response, or bootstrapping tasks that precede IaC. Not a substitute for declarative IaC for persistent resources. |

Mixed tools are acceptable but draw clean lines: Terraform for foundations (VPC, IAM, accounts, KMS), TIC for app-team self-service stacks, tccli scripts for bootstrapping. Avoid circular dependencies between toolchains.

## tccli (Tencent Cloud CLI)

- Version: `tccli` ≥ 3.0. Install via `pip install tccli` or the platform package.
- Authentication: configure named profiles in `~/.tccli/` using `tccli configure --profile <name>`. Use separate profiles for each account (China vs International) and environment (dev / prod).
- For CI/CD: inject credentials via environment variables `TENCENTCLOUD_SECRET_ID` and `TENCENTCLOUD_SECRET_KEY` (short-lived STS tokens from an assumed CAM role, not permanent keys).
- Output format: default to `--output json` in scripts. Parse with `jq`.
- Useful for: audit commands (`tccli cam ListPolicies`, `tccli cos GetBucketPolicy`), incident response, and one-time data migrations.

## Terraform — `tencentcloudstack/tencentcloud` provider

- Provider version: pin to `>= 1.81, < 2.0` in `required_providers`. The `1.x` line is the stable branch as of 2026.
- Lockfile: commit `.terraform.lock.hcl`. Provider updates are reviewed PRs, not surprises.
- Authentication: provider reads `TENCENTCLOUD_SECRET_ID`, `TENCENTCLOUD_SECRET_KEY`, `TENCENTCLOUD_REGION` from environment. In CI, source these from STS assumed-role credentials, not long-lived keys.
- Region: always set explicitly in the provider block. Do not rely on an environment default.
- Multiple regions / accounts: use provider aliases (`provider "tencentcloud" { alias = "beijing" region = "ap-beijing" }`) and pass the alias to resources that differ.
- China vs International: separate Terraform workspaces (and separate provider credentials) for China-region and International-region resources.

## State management

- **Remote backend**: store Terraform state in COS (Cloud Object Storage):
  ```hcl
  terraform {
    backend "cos" {
      region = "ap-singapore"
      bucket = "my-tfstate-prod-1234567890"
      prefix = "infra/prod"
    }
  }
  ```
- State locking: Tencent COS backend uses object-level locking. Ensure the bucket has **versioning enabled** so state files are recoverable.
- **Per-environment state**: separate state file per environment (`infra/dev`, `infra/staging`, `infra/prod`). Never share a state file across environments.
- **Separate workspaces for stateful resources**: databases, COS buckets, KMS keys — in their own workspace with `prevent_destroy = true`. They outlive application Terraform stacks.
- Never run `terraform apply` locally against production without an explicit approval gate in the pipeline.

## Module hygiene

- Prefer community-maintained modules in the `terraform-tencentcloud-modules` GitHub org when they exist — they encode Tencent-specific defaults and edge cases.
- Pin module versions with `source = "github.com/terraform-tencentcloud-modules/terraform-tencentcloud-vpc?ref=v1.2.3"`.
- Do not wrap community modules in a local wrapper until you have ≥ 3 consumers. Premature abstraction.
- Avoid using `count` or `for_each` to deploy across environments — separate workspaces are cleaner and safer.

## TIC (Tencent Infrastructure-as-Code)

- TIC is a managed Terraform execution service hosted in the Tencent Cloud console. It connects to your code repository (Coding, GitHub, GitLab), runs `terraform plan` and `terraform apply`, and stores state in Tencent-managed COS.
- **When to use TIC over self-managed Terraform CI**: platform teams that want to offer infrastructure self-service to app teams via the Tencent console, without managing Jenkins / GitHub Actions runners for Terraform.
- TIC supports workspace environments, approval gates, and role-based access to workspaces.
- TIC uses `tencentcloudstack/tencentcloud` provider; all provider features apply.
- **Limitation**: TIC does not support all Terraform features (e.g., complex provisioners). Evaluate for your use case before committing.

## Coding DevOps CI/CD

- Tencent's **Coding DevOps** is a full CI/CD suite (code hosting, pipelines, artifact registry, project management) available to Tencent Cloud accounts.
- CI pipeline: Jenkinsfile-compatible DSL or a Coding-native YAML pipeline. Stages: lint → test → build → push to TCR → deploy to TKE / SCF.
- Artifact registry: **TCR (Tencent Container Registry)** for Docker images. Enable vulnerability scanning on push; gate deployment on findings severity.
- Authentication to Tencent Cloud from Coding pipelines: Coding supports native Tencent Cloud credential binding — no static keys needed; the pipeline authenticates via a bound CAM role.
- For teams already on GitHub or GitLab: Coding DevOps can mirror and build from external repositories. Alternatively, use GitHub Actions or GitLab CI with OIDC-to-CAM role federation (see below).

## GitHub Actions with Tencent Cloud OIDC

Configure OIDC federation between GitHub Actions and Tencent Cloud CAM:

1. Register GitHub's OIDC provider in CAM: JWKS URI `https://token.actions.githubusercontent.com/.well-known/jwks`.
2. Create a CAM role with trust policy scoped to the specific repo / workflow ref (`sub` condition: `repo:<org>/<repo>:ref:refs/heads/main`).
3. In the workflow, use `tencentcloudstack/tencent-cloud-action` or a custom step to call `cam:AssumeRoleWithWebIdentity` and source credentials from the resulting STS token.
4. Scope the role to only what the pipeline needs: `plan`-only role for PRs, `apply`-capable role for main branch.

No `TENCENTCLOUD_SECRET_ID` / `TENCENTCLOUD_SECRET_KEY` in GitHub Actions secrets. Rotate-free, audit-logged.

## GitOps for TKE

- Use **Argo CD** (self-deployed on TKE) or **Tencent Cloud's native TKE GitOps** integration (Coding DevOps → TKE deployment) for continuous delivery to Kubernetes.
- Application manifests in a dedicated Git repository; Argo CD watches and syncs to TKE clusters.
- Image promotion: CI pipeline builds and pushes a tagged image (git SHA) to TCR; GitOps pipeline updates the image tag in the manifests repository and submits a pull request; merge triggers Argo CD sync.
- Rollback: revert the manifest pull request and merge — Argo CD syncs back to the previous image tag within seconds.
- Avoid `image: latest` in any Kubernetes manifest. Always reference a specific SHA or semver tag.

## CI/CD pipeline stages — the minimum

1. **Lint + static analysis**: `terraform fmt -check`, `tflint`, `checkov` (Tencent Cloud rules), `tccli` schema validation. Fail fast, sub-minute.
2. **Plan**: `terraform plan`. Post diff as a pull request comment for human review before merge.
3. **Test**: unit tests for Terraform modules (`terraform validate`, `terratest` for integration); TKE manifest schema validation (`kubeval` / `kubeconform`).
4. **Build + push**: Docker image built, tagged with git SHA, pushed to TCR, vulnerability scan completed.
5. **Deploy to dev/staging**: apply on merge to the integration branch. Automatic.
6. **Deploy to production**: manual approval gate, or tag-based release trigger. Never auto-apply to prod on merge.
7. **Drift detection**: scheduled `terraform plan -refresh-only` on production workspaces. Alert on any diff — silent console changes are operational risk.

## Deployment patterns for application code

| Pattern | Service |
| --- | --- |
| Blue/green | TKE (two Deployments, shift CLB traffic weight) or SCF aliases |
| Canary | TKE traffic splitting via CLB weighted rules or service mesh |
| Rolling update | TKE Deployment `rollingUpdate` strategy (default) |
| Feature flags | Application-level (LaunchDarkly, Growthbook); not native in Tencent Cloud |

Always define a **rollback procedure before the first deploy**. A deployment you cannot roll back safely is a deployment you cannot do safely.

## Secrets in IaC

- No secrets in `.tfvars`, `terraform.tfvars`, or any checked-in file.
- Pipeline secrets: short-lived STS tokens from an assumed CAM role via OIDC. No permanent SecretId/SecretKey in CI configuration.
- Application secrets: reference SSM Parameter Store paths or Secrets Manager ARNs in Terraform `data` sources; resolve at runtime, never in plan output.
- Terraform outputs that contain secrets: mark `sensitive = true` so they do not appear in CI logs or `terraform show` output.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Console-first, "we'll codify later" | Drift is immediate and permanent. Codify before the second resource is created. |
| Single state file for all environments | One bad apply in staging blasts production resources. Separate state per environment. |
| `terraform apply` from a developer laptop in production | No audit trail, no peer review, no lock. Pipeline-only applies. |
| Long-lived SecretId/SecretKey in CI secrets | Key leaked via log scraping or CI secret exposure. OIDC-to-CAM role. |
| Auto-apply to production on merge to main | One bad merge = production outage before anyone can react. Manual approval or tag-gated. |
| No drift detection | Console emergency-fixes during an incident become permanent invisible drift. |
| `image: latest` in Kubernetes manifests | Rolling back is archaeology. Tag by git SHA or semver. |
| TIC for complex Terraform with provisioners | TIC does not support all Terraform features; discover limits before committing to it. |

## Defaults — release pipeline

- Trunk-based development; feature branches short-lived (< 2 days).
- PRs require: passing lint + plan + at least one human reviewer.
- Build artifacts (container images, SCF packages) tagged with git SHA; `latest` tag only for local dev builds.
- Container vulnerability scan + SBOM on every build; pipeline gates prod on `HIGH` / `CRITICAL` findings in TCR.
- Deployment is idempotent — re-running succeeds without side effects.
- Every deployment emits a marker event to Cloud Monitor (custom metric `deploy_event`) so dashboards can correlate deployments to metric changes.
- Rollback is one IaC change or one manifest revert away — never requires manual console intervention.

## Cost considerations

- Terraform plan / apply runs are free. COS state storage is negligible.
- Terratest integration tests spin up real resources — tear them down in `defer` or `AfterTest`; an orphaned test VPC accumulates cost.
- Coding DevOps is billed per build-minute. Cache Docker layers in TCR to reduce build time and cost.
- TIC is included in Tencent Cloud; no additional charge for the managed runner. Evaluate before building a self-hosted CI Terraform runner.

## Observability hints

- Tag every Terraform-managed resource with `Environment`, `Service`, `Owner`, `CostCenter`. Cloud Monitor and Cost Manager cost attribution depend on tags.
- Pipeline metrics worth tracking: build success rate, deploy frequency, change failure rate, mean time to recovery (DORA four). These indicate whether the pipeline improves or inhibits delivery.

## Verification checklist

- [ ] IaC tool chosen; mixed tools have documented, non-overlapping scopes.
- [ ] Remote COS backend; per-environment state; state file versioning enabled on COS bucket.
- [ ] No long-lived credentials in CI — OIDC-to-CAM role federation.
- [ ] Terraform plan posted on PR; human review required for production.
- [ ] Stateful resources in a separate workspace with `prevent_destroy = true`.
- [ ] Container images tagged by git SHA; vulnerability scan gates prod deployment.
- [ ] Rollback procedure tested at least once per quarter.
- [ ] Drift detection (scheduled `plan -refresh-only`) running on production workspaces.
- [ ] Pipeline secrets are short-lived STS tokens; application secrets via SSM / Secrets Manager.
- [ ] All resources tagged; Cost Manager cost allocation is working.
