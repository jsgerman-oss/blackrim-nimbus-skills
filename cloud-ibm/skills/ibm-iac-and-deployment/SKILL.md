---
name: ibm-iac-and-deployment
description: Choose, scaffold, or review IBM Cloud Infrastructure-as-Code and deployment — Terraform IBM-Cloud/ibm provider, IBM Cloud Schematics (managed Terraform), IBM Cloud Continuous Delivery Toolchains, Tekton pipelines, GitOps for ROKS/IKS, ibmcloud CLI and plugin ecosystem. Use when starting a new IaC project, picking a delivery tool, or hardening a release pipeline.
---

# IBM Cloud IaC and Deployment

## When to use

- Greenfield IBM Cloud project — picking an IaC and delivery tool.
- Inheriting console-built IBM Cloud infrastructure that needs to come into code.
- Designing a CI/CD pipeline for application or infrastructure.
- Hardening a release for safe rollout and rollback.
- Reviewing an existing IaC repo for drift, secrets, state hygiene.
- Setting up GitOps delivery for IKS or ROKS.

## IaC tool — picking one

| Tool | Pick when |
| --- | --- |
| **Terraform with IBM-Cloud/ibm provider** | Default choice for new IBM Cloud IaC. Multi-cloud compatibility, large community, best module ecosystem. Use OpenTofu for a fully open-source stack. |
| **IBM Cloud Schematics** | You want IBM-managed Terraform state, automated drift detection, and a native IBM Cloud console experience. Uses the same `IBM-Cloud/ibm` provider under the hood. |
| **Ansible + IBM Cloud collection** | Day-2 configuration management, package install, OS configuration on VPC VSIs. Complements Terraform (provision with Terraform, configure with Ansible). |
| **Helm + GitOps (Argo CD / Flux)** | Application delivery onto IKS or ROKS clusters. Terraform or Schematics provisions the cluster; Helm + GitOps delivers apps. |
| **IBM Cloud Continuous Delivery + Tekton** | Full IBM Cloud-native CI/CD: build, test, scan, and deploy pipelines integrated with IBM Cloud services (Toolchain, DevOps Insights, DORA metrics). |

Mixed tools are fine with clean boundaries: Terraform for IBM Cloud foundations (VPC, IAM, ICD); Helm + Argo CD for application delivery on ROKS; Tekton Toolchain for CI build and image push.

## Terraform IBM-Cloud/ibm provider

The `IBM-Cloud/ibm` provider is the canonical Terraform interface for IBM Cloud resources.

- Version: pin `>= 1.65` in `required_providers`; test against the latest before pinning.
- Authentication: use `IC_API_KEY` environment variable (short-lived Service ID key rotated via Secrets Manager) or `IC_TRUSTED_PROFILE_ID` + compute identity in Schematics workspaces. Never hard-code an API key in `terraform.tfvars` or Terraform variable files.
- Resource Groups: every IBM Cloud resource must be in a named resource group. Create resource groups in a bootstrap workspace before other workspaces reference them.
- Region and zone: always explicit (`ibmcloud_region`, `ibmcloud_zone`). No implicit defaults.

### State management

- Remote state: store Terraform state in Cloud Object Storage (COS) using the `ibmcloud` backend (or S3-compatible backend for broad ecosystem compatibility).
- State locking: COS backend supports object-level locking via conditional PUT. Alternatively, use Schematics which handles state internally.
- Per-environment separation: one state file per environment (`dev/`, `stage/`, `prod/`). Never share a state file between environments.
- Sensitive outputs: mark sensitive values `sensitive = true`; they are redacted in plan output and CI logs.
- Deletion protection: `lifecycle { prevent_destroy = true }` on all production stateful resources (ICD instances, COS buckets holding live data, Key Protect keys, VPC subnets with active workloads).

### Module hygiene

- Reference IBM Cloud community modules where available: check `registry.terraform.io/IBM-Cloud/` for VPC, IKS, and database modules.
- Pin module versions. `~> 1.5` is acceptable; `>= 1.5` invites surprise upgrades.
- Lockfile checked in (`.terraform.lock.hcl`).
- One module per bounded concern: `modules/vpc/`, `modules/iam/`, `modules/databases/`. Resist putting VPC + IAM + databases in a single module.

## IBM Cloud Schematics

Schematics is IBM Cloud's managed Terraform service — IBM hosts and manages Terraform state, plan, and apply execution.

### When to choose Schematics over self-managed Terraform

- Team is IBM Cloud-only and wants native console integration.
- You want drift detection (Schematics can schedule periodic `plan` runs and alert on drift).
- Compliance requirement for audit trail of all `plan` and `apply` operations (Schematics logs all actions to Activity Tracker).
- No existing CI/CD pipeline for IaC — Schematics provides a managed execution environment.

### Schematics workspace structure

- One Schematics workspace per environment per module stack.
- Link workspace to a Git repo or upload a TAR of the Terraform root module.
- Workspace variables: set via the Schematics API or console. Mark sensitive variables as `sensitive` — they are encrypted at rest.
- Trusted Profile binding: bind the Schematics workspace to a Trusted Profile instead of embedding an API key. The workspace authenticates to IBM Cloud using compute identity.

## IBM Cloud Continuous Delivery — Toolchains and Tekton

IBM Cloud Continuous Delivery provides fully managed Toolchains that orchestrate CI/CD pipelines using Tekton (Kubernetes-native pipelines).

### Toolchain composition

A Toolchain integrates tool integrations (Git repo, pipeline, issue tracker, Slack, DevOps Insights) into a delivery pipeline:

1. **Source**: GitHub, GitLab, IBM Cloud Git Repos and Issue Tracking.
2. **Pipeline**: Tekton or Classic pipeline. Tekton is preferred for new workloads.
3. **Registry**: IBM Cloud Container Registry (ICR) for container images.
4. **Deploy**: `kubectl apply`, `helm upgrade`, `ibmcloud ce application update` (Code Engine), or a Schematics workspace apply.
5. **Evidence**: DevOps Insights captures build and test results; integrates with IBM Cloud Framework for Financial Services evidence requirements.

### Tekton pipeline defaults

- Use cluster-level `Pipeline` and `PipelineRun` resources; avoid inline task definitions in complex pipelines.
- Tasks: lint → build → scan → test → push → deploy.
- Image scanning: IBM Cloud Container Registry Vulnerability Advisor scans images on push. Gate deployment on zero `HIGH` or `CRITICAL` findings using a `check-va-scan` task.
- Secrets: inject secrets from IBM Cloud Secrets Manager into pipeline environment variables via the `secrets` integration in the Toolchain — never store secrets in the pipeline YAML.
- SBOM: generate a Software Bill of Materials on every build (`syft` or `cyclonedx`); upload to DevOps Insights.
- Signing: sign container images with `cosign` using a Key Protect key; verify signatures at deploy time.

## GitOps for ROKS and IKS

Red Hat OpenShift GitOps (Argo CD) is the standard GitOps delivery mechanism for ROKS. Flux is also supported on IKS.

- Git repo structure: separate application manifests into a `gitops/` directory in the app repo, or a dedicated config repo per cluster.
- Environment promotion: dev → stage → prod via branch or directory promotion in the config repo. Argo CD `ApplicationSet` with path-based generators handles multi-environment deployments.
- Image updater: use `argocd-image-updater` or Flux's `ImageAutomation` to automatically update image tags in the config repo when a new image is pushed to ICR.
- Sync policy: `prune: true` in production; `selfHeal: true` to prevent configuration drift from kubectl.
- RBAC: Argo CD RBAC roles mapped to IBM Cloud IAM Access Groups via OIDC — no separate user management.

## `ibmcloud` CLI and plugin ecosystem

- CLI version: >= 2.25 (`ibmcloud --version`).
- Essential plugins:
  - `infrastructure-service` (is) — VPC management.
  - `kubernetes-service` (ks / oc) — IKS and ROKS.
  - `container-registry` (cr) — ICR.
  - `code-engine` (ce) — Code Engine.
  - `schematics` — Schematics workspaces.
  - `secrets-manager` — Secrets Manager.
- Authentication in automation: use `ibmcloud login --apikey <key>` with a Service ID key, or `ibmcloud login --iam-trusted-profile-id <id>` in Schematics or compute environments.
- CI/CD auth: IBM Cloud Continuous Delivery Toolchain provides automatic `ibmcloud login` via the IAM integration — no embedded credentials.

## IaC pipeline structure

### Stages

1. **Lint / static analysis**: `terraform fmt -check`, `terraform validate`, `tflint` (with `ibm` plugin), `checkov` for security policy.
2. **Plan**: `terraform plan -out=plan.tfplan`; post plan output as PR comment. Schematics: trigger a plan action via API.
3. **Test**: `terratest` for critical infrastructure modules; `terraform validate` for all.
4. **Apply (dev/stage)**: automatic on merge to the environment branch.
5. **Apply (prod)**: manual approval gate, or tag-based release.
6. **Drift detection**: scheduled `terraform plan -refresh-only` or Schematics scheduled plan; alert on non-empty diff.

### Authentication (CI/CD → IBM Cloud)

- **IBM Cloud Continuous Delivery Toolchain**: authenticates automatically using the Toolchain's IAM service binding.
- **GitHub Actions → IBM Cloud**: use Trusted Profiles with OIDC federation. Configure the Trusted Profile claim rule to match `repository`, `ref`, and `environment` claims from GitHub OIDC token. No stored API keys.
- **GitLab CI → IBM Cloud**: same pattern — GitLab OIDC tokens exchanged for IAM tokens via Trusted Profile.
- Separate Trusted Profiles (or Service IDs) for `plan` (read-only) vs `apply` (write) — most PRs only need plan-level access.

## Deployment patterns for application code

| Pattern | Platform | How |
| --- | --- | --- |
| Blue/green | Code Engine | Create new revision; route traffic 0% → 100% via traffic split. |
| Canary | Code Engine | Traffic split: 90% old revision, 10% new; monitor; promote. |
| Rolling | IKS/ROKS | Kubernetes `RollingUpdate` deployment strategy; set `maxUnavailable=0`, `maxSurge=1`. |
| GitOps progressive delivery | ROKS | Argo Rollouts with Sysdig metrics for automated canary analysis. |
| Feature flags | Any | IBM Cloud AppConfig for lightweight flags; LaunchDarkly for full-featured. |

Always configure rollback before shipping forward: Code Engine traffic split reverts in one CLI command; IKS deployment rollback via `kubectl rollout undo`.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| API key in `terraform.tfvars` committed to Git | Key exposed forever. Use environment variable injection or Schematics variables. |
| Console-built resources never codified | Drift accumulates; next refactor requires full re-import or rebuild. Codify before deploying a second resource. |
| Single Schematics workspace for all environments | A failed prod `apply` on the wrong workspace drops everything. One workspace per environment. |
| `ibmcloud login` with a long-lived API key in CI | Leaks = full access. Use Trusted Profiles + OIDC federation for GitHub Actions / GitLab CI. |
| Auto-apply on merge to main for production | One bad merge = production outage. Manual approval gate for prod. |
| No drift detection | Console fixes during incidents become permanent invisible drift. |
| Deploying new revision to 100% traffic on Code Engine without a canary | No rollback window. Traffic split to 10% first; monitor; promote. |
| `lifecycle { prevent_destroy = false }` on ICD instances | Accidental `terraform destroy` = data loss. `prevent_destroy = true` mandatory. |

## Defaults — release pipeline

- Trunk-based development; feature branches short-lived (< 1 day).
- PRs require: passing lint + plan + at least one human reviewer.
- Container images tagged with git SHA; never `:latest` in production.
- Vulnerability Advisor scan gated in CI — zero `HIGH` / `CRITICAL` before deploy to prod.
- Image SBOM generated on every build.
- Every deploy emits an event to IBM Cloud Monitoring so dashboards show change markers correlated with metrics.
- Rollback is one command: `ibmcloud ce application update --revision <old>` or `kubectl rollout undo`.

## Cost considerations

- Schematics: no additional charge for workspace plan/apply — pay only for IBM Cloud resources provisioned.
- Continuous Delivery: free for unlimited Tekton pipeline executions. Classic pipelines limited to 500 stage runs/month on the free tier.
- IBM Cloud Container Registry: billed per GB stored and per GB of image pull traffic. Enable image retention policies to delete old, untagged images.
- Terratest: destroy test infrastructure in `defer` / cleanup to avoid orphaned VPC VSIs and databases.

## Observability hints

- Tag every IaC-provisioned resource with `env`, `team`, `service`, `cost-center` — enforced in the pipeline via `tflint` required-tags rule.
- DORA metrics from DevOps Insights: deployment frequency, lead time for change, change failure rate, mean time to restore — track these to know whether the pipeline is helping.
- Schematics workspace activity logs shipped to Activity Tracker — every `plan` and `apply` is auditable.

## Verification checklist

- [ ] Terraform provider `IBM-Cloud/ibm` >= 1.65 pinned; `.terraform.lock.hcl` checked in.
- [ ] State in COS (or Schematics); per-environment separation; no shared state files.
- [ ] No long-lived API keys in CI — Trusted Profiles + OIDC for GitHub Actions / GitLab CI.
- [ ] Plan / diff posted on PR; human review required before prod apply.
- [ ] `prevent_destroy = true` on all production stateful resources.
- [ ] Tag policy applied in IaC; `tflint` enforces required tags on every resource.
- [ ] Vulnerability Advisor gate in CI pipeline — zero HIGH/CRITICAL before prod deploy.
- [ ] Rollback procedure defined and tested (Code Engine traffic split or `kubectl rollout undo`).
- [ ] Drift detection scheduled and alerting.
- [ ] Pipeline secrets via Secrets Manager; no hardcoded values in pipeline YAML.
