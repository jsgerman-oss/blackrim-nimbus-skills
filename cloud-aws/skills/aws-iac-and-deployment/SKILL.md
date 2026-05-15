---
name: aws-iac-and-deployment
description: Choose, scaffold, or review AWS Infrastructure-as-Code and deployment — CDK, Terraform, CloudFormation, SAM, CodePipeline, CodeBuild, CodeDeploy, GitHub Actions OIDC, blue/green, canary. Use when starting a new IaC project, picking a tool, or hardening a release path.
---

# AWS Infrastructure-as-Code and Deployment

## When to use

- Greenfield project — picking an IaC tool.
- Inheriting console-built infrastructure that needs to come into code.
- Designing a CI/CD pipeline for app + infra.
- Hardening a release for safe rollout / rollback.
- Reviewing an existing IaC repo for drift, secrets, state hygiene.

## IaC tool — picking one

| Tool | Pick when |
| --- | --- |
| **AWS CDK (v2)** | Team is comfortable in TypeScript / Python; you want first-class AWS abstractions and you'll stay AWS-only for the foreseeable future. |
| **Terraform / OpenTofu** | Multi-cloud, multi-provider (Cloudflare DNS + GitHub repos + AWS + ...), or you want a single tool across the org. Largest community, best module ecosystem. |
| **AWS SAM** | Lambda-heavy serverless app where 80% of IaC is functions + APIs + EventBridge. SAM CLI's local dev loop is the win. |
| **CloudFormation (raw)** | You already have huge CFN investment, or you're shipping to GovCloud / China and tooling pinning matters. Otherwise, prefer CDK over raw CFN. |
| **Pulumi** | Same niche as CDK but multi-cloud; pick if your team strongly prefers a real programming language over HCL. |
| **CrossPlane** | You want Kubernetes to be the control plane for cloud infra. Niche but powerful for platform teams. |

Mixed tools are fine but draw clean boundaries — Terraform for foundations (VPC, IAM, accounts), CDK for app stacks, SAM for serverless components. Resist Terraform-managing-an-EKS-cluster-that-deploys-CDK-stacks unless you really have to.

## State management

- Terraform: S3 backend + DynamoDB lock table, separate state file per environment, KMS-encrypted.
- CDK / CloudFormation: state lives in CloudFormation itself; cross-stack refs via `Exports` (sparingly) or SSM Parameter Store.
- One workspace / stack per environment. Never `if env == "prod"` branching inside a single stack — duplicate config beats lazy abstraction.
- Stateful resources (RDS, S3, DynamoDB) in separate stacks from compute, with `DeletionPolicy: Retain` / `prevent_destroy = true`.

## Module / construct hygiene

- Use ecosystem modules where they exist: `terraform-aws-modules/*`, AWS Solutions Constructs (CDK).
- Don't wrap a community module in your own wrapper "for consistency" until you have ≥ 3 consumers; premature abstraction.
- Pin module / provider versions. `~> 5.0` is acceptable; `>= 5.0` invites surprise.
- Lockfiles checked in (`.terraform.lock.hcl`, `cdk.context.json`, `package-lock.json`).

## CI/CD — the spine

### Authentication

- **GitHub Actions / GitLab / Buildkite → AWS:** OIDC federation, `aws-actions/configure-aws-credentials` (or equivalent). The role's trust policy gates on `aud=sts.amazonaws.com` + a `sub` claim scoped to the repo / ref. No static keys, ever.
- Separate roles for `plan`-style read access vs `apply`-style write — most PRs only need plan.

### Stages

1. **Lint / static analysis.** `terraform fmt`, `tflint`, `checkov`, `tfsec`, `cfn-lint`, CDK `synth`. Fail fast, sub-minute.
2. **Plan.** `terraform plan` or `cdk diff`. Post the plan / diff as a PR comment for review.
3. **Test.** Unit tests for CDK constructs (`@aws-cdk/assertions`); `terraform validate` + `terratest` where it matters. Snapshot tests for synthesized templates.
4. **Apply (dev/stage).** Merge to a long-lived branch → apply to non-prod environments automatically.
5. **Apply (prod).** Manual approval gate, or tag-based release, or both.
6. **Drift detection.** Scheduled `terraform plan -refresh-only` (or CFN drift detection) — alert on diff.

### Deployment patterns for app code

| Pattern | Service |
| --- | --- |
| Blue/green | ECS (CodeDeploy), Lambda aliases + weighted alias routing, App Runner |
| Canary | API Gateway stage variables, Lambda aliases, CloudFront origin groups |
| Rolling | ECS default, EKS Deployments |
| Feature flags | AWS AppConfig (lightweight) or LaunchDarkly / Statsig (full-featured) |

Always set up **rollback first**, then the forward deploy. A deploy you can't safely undo is a deploy you can't safely do.

## Secrets in IaC

- Never `terraform.tfvars` with secrets checked in.
- For pipeline secrets: GitHub Actions secrets / OIDC short-lived tokens / Secrets Manager pulled at deploy time.
- For app secrets: reference Secrets Manager / Parameter Store ARNs in IaC, resolve at runtime.
- `terraform output` of sensitive values: mark `sensitive = true` so they don't land in CI logs.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| ClickOps + "we'll codify later" | Drift forever, no review trail. Codify before second resource. |
| Single huge state file for the whole org | One bad apply blasts everything. Split by blast radius. |
| Cross-stack imports / refs as a web | Renames become migrations. Use SSM Parameter Store as a loose contract. |
| `terraform apply` from a laptop in prod | No audit trail, no lock, mystery state. Pipeline-only applies. |
| Long-lived AWS access keys in CI | Leaks = full account. OIDC. |
| Auto-apply on merge to main for prod | One bad merge = outage. Manual approval or tag-gated. |
| No drift detection | Console fixes during incidents become permanent invisible drift. |

## Defaults — release pipeline

- Trunk-based development; feature branches short-lived.
- PRs require: passing lint + plan + at least one human reviewer.
- Build artifacts (container images, Lambda zips) tagged with git SHA; never `:latest` in prod.
- Image scan + SBOM generated on every build; gate prod on findings severity.
- Deployment is idempotent — re-running succeeds.
- Every deploy emits a marker to CloudWatch / Datadog / etc. so dashboards correlate change to behavior.
- Rollback is a single command or one IaC change (image tag revert, traffic shift, alias).

## Cost considerations

- Plan + apply runs are cheap; storage of plan artifacts isn't — bound retention.
- Test infra (terratest) should be torn down in `defer` / cleanup; an orphaned test VPC adds up.
- Use Terraform Cloud / Spacelift / env0 only if the value > $0/mo savings of self-hosted runners; for small teams a self-hosted runner + S3 backend is fine.

## Observability hints

- Tag every resource in IaC with `Environment`, `Service`, `Owner`, `CostCenter`. SCPs / Config rules enforce.
- Pipeline metrics: lead time for changes, deployment frequency, change failure rate, mean time to recovery. These are the DORA four, and they tell you whether the pipeline is helping or hurting.

## Verification checklist

- [ ] One IaC tool primary; mixed tools have clean boundaries.
- [ ] State backend remote, locked, encrypted; per-env separation.
- [ ] No long-lived cloud credentials in CI — OIDC.
- [ ] Plan / diff posted on PR; human review required for prod.
- [ ] Stateful resources isolated in their own stack(s) with deletion protection.
- [ ] Tag policy applied in code, enforced by policy.
- [ ] Rollback procedure tested at least once per quarter.
- [ ] Drift detection running on a schedule.
- [ ] Pipeline secrets are short-lived; app secrets via Secrets Manager.
