---
name: alibaba-iac-and-deployment
description: Choose, scaffold, or review Alibaba Cloud Infrastructure-as-Code and deployment — Alibaba Cloud CLI (aliyun ≥ 3.0.230), Terraform aliyun/alicloud provider (≥ 1.220), Resource Orchestration Service (ROS), Cloud Assistant, GitOps for ACK, GitHub Actions / Jenkins with RAM Role OIDC. Use when starting an IaC project, picking a tool, or hardening a release path.
---

# Alibaba IaC and Deployment

## When to use

- Greenfield project — picking an IaC tool for Alibaba Cloud.
- Inheriting console-built infrastructure that needs to come into code.
- Designing a CI/CD pipeline for application and infrastructure deployment.
- Hardening a release for safe rollout and rollback.
- Reviewing an existing IaC repo for drift, secret leakage, or state hygiene.
- Wiring RAM Role OIDC authentication for GitHub Actions or Jenkins.

## IaC tool — picking one

| Tool | Pick when |
| --- | --- |
| **Terraform (`aliyun/alicloud`)** | Primary recommendation. Multi-cloud or multi-provider (Cloudflare + GitHub + Alibaba), or a single IaC standard across the org. Largest community; best module ecosystem; `aliyun/alicloud` provider ≥ 1.220 has comprehensive coverage. |
| **ROS (Resource Orchestration Service)** | Team already standardized on ROS; China-region tooling constraints; you need native Alibaba console integration; or you are shipping templates inside Alibaba Cloud Marketplace. Syntax is similar to CloudFormation. |
| **Pulumi** | Team strongly prefers a real programming language (Go, Python, TypeScript) and `alicloud` Pulumi provider suits the workload. Niche but viable. |
| **Alibaba Cloud CLI + scripts** | Bootstrap-only steps (account root hardening, KMS key creation, first Terraform state bucket) where IaC would be circular. |

Terraform is the default. ROS is acceptable when Alibaba ecosystem tooling (DataWorks, ACK console integration, commercial marketplace) makes it the better fit. Avoid mixing tools for the same resource layer — Terraform for foundations and ROS for app stacks is fine; Terraform managing a resource while ROS re-provisions it is not.

## Alibaba Cloud CLI

- Version: `aliyun` ≥ 3.0.230. Install via the official installer or `brew install aliyun-cli` on macOS.
- Authentication: configure a named profile with a RAM Role + STS assumption, not a root AK/SK.
  ```bash
  aliyun configure --mode RamRoleArn --profile prod \
    --region cn-hangzhou \
    --ram-role-arn acs:ram::123456789:role/deploy-role \
    --ram-session-name ci-session
  ```
- Output format: `--output json` in scripts for deterministic parsing; `--output table` for humans.
- Pagination: use `--page-size` and loop on `--page-number`; many list APIs page at 10–50 by default.
- Dry-run mode: `--dry-run` on mutating commands where supported; not available for all APIs — verify before relying on it.

## Terraform — aliyun/alicloud provider

### Provider configuration

```hcl
terraform {
  required_providers {
    alicloud = {
      source  = "aliyun/alicloud"
      version = ">= 1.220, < 2.0"
    }
  }
  required_version = ">= 1.6"
}

provider "alicloud" {
  region = var.region
  # Credentials via environment variables:
  # ALICLOUD_ACCESS_KEY + ALICLOUD_SECRET_KEY (short-lived STS)
  # or ALICLOUD_ECS_ROLE_NAME for ECS-hosted pipelines
  # Never hardcode credentials in provider config.
}
```

### State management

- S3-compatible backend (`oss` backend type) using an OSS bucket:
  - Enable OSS versioning on the state bucket.
  - Enable OSS server-side encryption with a KMS CMK.
  - Enable OSS access logging to a separate log bucket.
- Use Terraform Workspace per environment (dev / staging / prod); one state file per environment per stack.
- Separate Terraform stacks by blast radius: `foundation` (VPC, RAM, KMS), `data` (RDS, OSS, Redis), `app` (ECS, ACK, FC). Never a single all-resources stack.
- Stateful resources (`alicloud_db_instance`, `alicloud_oss_bucket`, `alicloud_polardb_cluster`): set `deletion_protection = true` (where supported) and `prevent_destroy = true` in `lifecycle` blocks.

### Module hygiene

- Use community modules where mature: check [registry.terraform.io](https://registry.terraform.io) for `alicloud/` namespace modules; evaluate quality (stars, recent commits) before adopting.
- Pin module versions: `version = "~> 3.0"`, not floating `>= 3.0`.
- Don't wrap a community module unless you have ≥ 3 consumers; premature abstraction adds maintenance burden.
- Lockfile checked in: `.terraform.lock.hcl` committed; provider version pinned to the patch level in CI.

## ROS (Resource Orchestration Service)

- Template language: YAML or JSON; top-level sections are `ROSTemplateFormatVersion`, `Description`, `Parameters`, `Resources`, `Outputs`.
- Stack policies: attach a stack policy to production stacks to prevent accidental deletion of critical resources.
- Change sets: always create and review a change set before `UpdateStack`; treat it like `terraform plan`.
- Nested stacks: for large architectures, split into a master stack with nested `ALIYUN::ROS::Stack` resources.
- ROS Designer: console visual editor for generating templates; useful for bootstrapping but output should be reviewed and committed to source control.
- China vs International: ROS is available in both; resource type names are the same. Service availability per region differs — check the console before writing templates.

## CI/CD — the spine

### Authentication — RAM Role OIDC

The correct approach for GitHub Actions (and other OIDC-capable CI systems) is RAM Role OIDC federation — no static AK/SK in CI.

1. Create a RAM OIDC Provider pointing to `token.actions.githubusercontent.com`.
2. Create a RAM Role with a trust policy gating on the OIDC subject claim (repo / ref):
   ```json
   {
     "Principal": {
       "Federated": "acs:ram::ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com"
     },
     "Action": "sts:AssumeRoleWithOIDC",
     "Condition": {
       "StringLike": {
         "oidc:sub": "repo:YOUR_ORG/YOUR_REPO:ref:refs/heads/main"
       }
     }
   }
   ```
3. In GitHub Actions, use `aliyun-actions/configure-aliyun-credentials` with `role-to-assume`.
4. Separate roles for `plan`-only (read access) vs `apply` (write access) — PR jobs only need plan.

### Pipeline stages

1. **Lint / static analysis.** `terraform fmt -check`, `terraform validate`, `tflint`, `checkov` (supports `alicloud` resource checks), `ros-lint` for ROS templates. Fail fast; sub-minute.
2. **Plan / change-set.** `terraform plan -out=plan.tfplan` or ROS change-set. Post the diff as a PR comment.
3. **Security scan.** `checkov --framework terraform` scans for open Security Groups, unencrypted disks, public OSS buckets, missing KMS. Gate on HIGH severity.
4. **Apply to dev.** Merge to a long-lived branch → apply to dev automatically.
5. **Apply to staging.** Tagged release or manual trigger; plan is reviewed before applying.
6. **Apply to prod.** Manual approval gate (GitHub Actions `environment: prod` with required reviewers) or tag-gated.
7. **Drift detection.** Scheduled `terraform plan -refresh-only` (or ROS drift detection) — alert on any detected diff.

### GitOps for ACK (Kubernetes)

- **FluxCD or ArgoCD** for continuous delivery of Kubernetes manifests / Helm charts to ACK clusters.
- Source of truth: Git repo contains all Kubernetes manifests; ACK cluster reconciles to match.
- Image update: FluxCD ImageUpdateAutomation writes back the new container tag to the manifest repo on each build.
- RRSA for FluxCD: the FluxCD controller service account uses RRSA to authenticate to Alibaba Container Registry (ACR) and to SLS for audit log delivery.
- Multi-cluster: ArgoCD `ApplicationSet` or FluxCD `Kustomization` with cluster selectors for promoting changes across dev → staging → prod clusters.

### Application deployment patterns

| Pattern | Service |
| --- | --- |
| Blue/green | SAE application version switch, ACK with ingress traffic weights, Function Compute alias weights |
| Canary | ALB listener rule with weighted target groups, ACK Ingress canary annotations |
| Rolling | ECS Auto Scaling rolling replacement policy, ACK Deployment rolling update |
| Feature flags | Alibaba Cloud AppConfig (dynamic config) or LaunchDarkly |

Always configure rollback first. A deploy you cannot safely undo is a deploy you cannot safely do.

## Cloud Assistant

- Alibaba's SSM-equivalent: run scripts on ECS instances without SSH.
- **OOS (Operation Orchestration Service)**: higher-level runbook automation — pre-built templates for patch, compliance check, resource inventory. Works across ECS fleets.
- Never open port 22 inbound; use Cloud Assistant or OOS for all interactive shell access.
- Secrets in Cloud Assistant commands: reference Secrets Manager ARNs in the command body; Cloud Assistant resolves them at execution time.

## Secrets in IaC

- Never check AK/SK into `terraform.tfvars` or any file in the repo.
- For pipeline secrets: OIDC short-lived tokens via `sts:AssumeRoleWithOIDC`; no static credentials.
- For app secrets: reference Secrets Manager secret ARNs in IaC; resolve at runtime in application code.
- Terraform `output` of sensitive values: mark `sensitive = true`; they will not appear in CI plan output.
- Pre-commit: run `gitleaks` or `trufflehog` as a pre-commit hook; block pushes containing credential patterns.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| `aliyun configure` with root AK/SK on CI runner | Root key leak = full account ownership; use RAM Role OIDC or ECS instance role. |
| Console-only infrastructure ("we'll codify later") | Drift is immediate; the second resource created without IaC will never be codified. Start with code. |
| Single all-resources Terraform state file | One bad apply can break everything; one slow `plan` blocks all other work. Split by blast radius. |
| `terraform apply` from a developer laptop in prod | No audit trail, no lock, mystery state, no approval gate. Pipeline-only prod applies. |
| ROS stack without stack policy in production | `UpdateStack` with a DELETE action on a production database is a one-command disaster. |
| Auto-apply on merge to main for prod | One broken PR = production outage. Manual approval or tag-gated promotion. |
| No drift detection | Console changes during incidents become permanent invisible drift; next IaC run surprises everyone. |

## Cost considerations

- Terraform plan runs are cheap; don't over-provision runner hours — use Alibaba Cloud's own ECS spot runners for CI.
- Terratest or OPA policy-as-code tests that spin up real resources must be torn down in a `defer` / cleanup step; an orphaned test VPC adds up.
- ROS stack pricing: no extra charge for ROS itself; you pay only for the resources the stack creates.
- OOS (Cloud Assistant) and ROS change-set operations are free.

## Observability hints

- Tag every resource in IaC with `Environment`, `Service`, `Owner`, `CostCenter` — Cloud Config rules can detect and alert on untagged resources.
- Pipeline metrics: track deployment frequency, lead time for changes, change failure rate, MTTR. Wire to SLS or a dashboard — these are leading indicators of IaC health.
- Enable Terraform state versioning in OSS so every apply produces a recoverable state snapshot.

## Verification checklist

- [ ] One IaC tool primary per layer (foundation / data / app); mixed tools have documented boundaries.
- [ ] State backend: OSS bucket with versioning, KMS encryption, and lifecycle policy for old versions.
- [ ] No static AK/SK in CI — RAM Role OIDC or ECS instance role for all CI authentication.
- [ ] Plan / change-set posted on PR; human approval required before prod apply.
- [ ] Stateful resources in dedicated stack(s) with `prevent_destroy = true` and deletion protection.
- [ ] Tag policy applied in code; Cloud Config rule enforces coverage.
- [ ] Rollback procedure documented and tested at least once per quarter.
- [ ] Drift detection scheduled (weekly minimum).
- [ ] Security scan (`checkov`) in CI; pipeline gates on HIGH findings.
- [ ] `aliyun` CLI ≥ 3.0.230 and `alicloud` Terraform provider ≥ 1.220 pinned in lockfile.
