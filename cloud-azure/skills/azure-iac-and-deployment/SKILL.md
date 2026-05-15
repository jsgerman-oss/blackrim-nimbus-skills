---
name: azure-iac-and-deployment
description: Choose, scaffold, or review Azure Infrastructure-as-Code and deployment — Bicep, ARM templates, Terraform (azurerm + azapi), Azure DevOps Pipelines, GitHub Actions with OIDC federation, Deployment Stacks. Use when starting a new IaC project, picking a tool, or hardening a release path.
---

# Azure Infrastructure-as-Code and Deployment

## When to use

- Greenfield project — choosing between Bicep and Terraform for Azure resources.
- Inheriting portal-built infrastructure that needs to come into code.
- Designing a CI/CD pipeline for application and infrastructure changes.
- Hardening a release for safe rollout and rollback.
- Reviewing an existing IaC repo for drift, secret hygiene, and state management.

## IaC tool — picking one

| Tool | Pick when |
| --- | --- |
| **Bicep** | Azure-only shop; team wants first-class Azure type safety, no state file, and ARM-native idempotency. Recommended default for Azure-focused teams. |
| **Terraform / OpenTofu (`hashicorp/azurerm`)** | Multi-cloud, multi-provider (Azure + Cloudflare DNS + GitHub Actions + Datadog), or org-wide standard already in place. Best module ecosystem; plan / apply workflow is well-understood by most platform teams. |
| **Terraform (`Azure/azapi`)** | Using `azurerm` but need a resource not yet supported — `azapi` wraps the ARM REST API directly. Pair `azurerm` + `azapi` in the same configuration; `azapi` fills the gaps. |
| **ARM templates (JSON)** | Legacy — you are inheriting existing ARM templates or deploying to an environment where only ARM is accepted (some GovCloud / sovereign cloud restrictions). Prefer Bicep over raw ARM for all new authoring; Bicep compiles to ARM and is fully equivalent. |
| **Deployment Stacks** | Azure-native stack lifecycle management: creates a Stack that owns all its resources and can delete orphaned resources on update. Complements Bicep; no equivalent in Terraform yet. Use for greenfield environments where you want ARM-managed cleanup. |
| **Pulumi** | Same niche as Bicep / Terraform but with a general-purpose language (TypeScript, Python, Go). Pick if the team strongly prefers a real programming language over HCL or Bicep DSL. |

Mixed tools are acceptable with clean boundaries: Bicep for Azure foundations (VNet, Key Vault, RBAC), Terraform for multi-cloud integrations (DNS, GitHub, monitoring SaaS). Avoid Terraform managing an AKS cluster that deploys Helm charts that deploy Bicep — pick a boundary and hold it.

ARM templates are a legacy output format. Never write new ARM JSON by hand — use Bicep and compile.

## Bicep conventions

- **Module structure**: one module per bounded context (network / compute / data / identity). Modules reference each other via `existing` resource references or output parameters — avoid cross-module `resourceId()` string construction.
- **Parameter files**: one `.bicepparam` file per environment (`dev.bicepparam`, `prod.bicepparam`). Sensitive parameters (connection strings, secrets) are not stored in parameter files — reference Key Vault secret URIs using the `getSecret()` function.
- **Deployment scope**: resource group is the default scope; subscription scope for resource groups, policy assignments, and RBAC; management group scope for policy initiatives and org-wide RBAC.
- **Idempotency**: Bicep / ARM deployments are idempotent by default (Complete mode removes untracked resources; Incremental mode leaves them). Use Incremental mode for brownfield; Complete mode only in greenfield environments where you want Deployment Stack-style cleanup.
- **linting**: `az bicep build --lint` in CI; install the Bicep VS Code extension for local type checking. No resource should deploy without passing lint.

## Terraform conventions

- **State**: Azure Blob Storage backend with a separate storage account per environment; enable blob versioning and soft delete on the state storage account. KMS-equivalent: use a CMK in Key Vault for the state storage account encryption.
- **Workspace or directory separation**: one directory (or Terraform Cloud workspace) per environment. Never `var.environment == "prod"` conditional branching inside a single configuration — duplicate the environment directories rather than adding conditional complexity.
- **Provider pinning**: `required_providers { azurerm = { version = "~> 4.0" } azapi = { version = "~> 2.0" } }`. Lockfile (`.terraform.lock.hcl`) checked in.
- **Module hygiene**: use community modules from the Terraform Registry (`Azure/` namespace modules verified by Microsoft) where they exist; don't wrap a community module in your own until you have at least three consumers.
- **`prevent_destroy = true`** on all stateful resources (storage accounts, databases, Key Vaults) in production workspaces. Deleting a Key Vault holding CMKs renders encrypted data unreadable.

## State management

- Terraform: Azure Blob Storage backend (`azurerm` backend type), separate container per environment, KMS-encrypted storage account. Lock via blob lease (built into the `azurerm` backend — no DynamoDB equivalent needed).
- Bicep / ARM: stateless from the IaC perspective — state lives in ARM itself. Use `az deployment group show` or `what-if` to understand the current state before applying.
- Stateful resources (Azure SQL, Cosmos DB, storage accounts, Key Vault) belong in a separate Bicep module or Terraform workspace from compute, with resource locks (`CanNotDelete`) applied in IaC.

## CI/CD — the spine

### Authentication

- **GitHub Actions / GitLab / Azure DevOps → Azure:** Workload Identity Federation to an App Registration (or Managed Identity with a federated credential for user-assigned MIs). No service principal client secrets in CI pipelines, ever.
- GitHub Actions: `azure/login@v2` action using `client-id`, `tenant-id`, `subscription-id` with OIDC — role assigned to the App Registration at the subscription / resource group scope.
- Azure DevOps: service connection of type `Azure Resource Manager` using Workload Identity Federation (not certificate or secret). Created via the Azure DevOps UI or via `az devops service-endpoint azurerm create --workload-identity-federation`.
- Separate service principals for **plan**-equivalent read access (e.g., `Reader` + `Bicep Deployment Reader`) vs **apply**-equivalent write access (specific contributor roles scoped to target resource groups).

### Stages

1. **Lint / static analysis.** `az bicep build --lint`, `tflint`, `checkov` (Terraform + Bicep), `tfsec`. Fail fast; must complete in < 2 minutes.
2. **What-if / plan.** `az deployment group what-if` (Bicep) or `terraform plan`. Post the diff as a PR comment. Block merge on plan failure.
3. **Test.** Bicep: `Test-BicepFile` (PSRule for Azure) or integration test via Pester against a test resource group. Terraform: `terratest` for integration-level validation.
4. **Apply (dev / stage).** Merge to a long-lived branch → apply to non-production environments automatically via pipeline.
5. **Apply (prod).** Manual approval gate, or a tag-gated release pipeline, or both. Never auto-apply to production on merge to main.
6. **Drift detection.** Scheduled `az deployment group what-if --no-prompt` (Bicep) or `terraform plan -refresh-only` against production — alert on unexpected diff.

### Deployment patterns for application code

| Pattern | Azure mechanism |
| --- | --- |
| Blue/green | App Service deployment slots + slot swap; AKS blue/green via separate deployments + traffic shift |
| Canary | Azure Front Door origin weights (10% canary / 90% stable); APIM revision-based canary |
| Rolling | AKS RollingUpdate deployment strategy; VMSS rolling upgrade mode |
| Feature flags | Azure App Configuration feature flags (simple) or a full-featured feature management SDK |

Set up rollback first, then the forward deploy. A deploy you cannot safely undo is a deploy you cannot safely do. Slot-swap rollback for App Service is instant; AKS rollback is `kubectl rollout undo`; Bicep rollback is a redeployment of the previous revision.

## Deployment Stacks

- Deployment Stacks track all resources deployed as part of a stack; a stack update can `--deny-settings DenyWriteAndDelete` on managed resources to prevent out-of-band modifications.
- Use `--action-on-unmanage DeleteAll` for ephemeral environments (PR previews, feature branches) so teardown is a single `az stack group delete` command with no orphan cleanup.
- Deployment Stacks do not yet support rollback natively — combine with slot-swap or image-tag revert at the application layer.

## Secrets in IaC

- Never commit secrets to Bicep parameter files or Terraform `.tfvars` — use Key Vault secret references (`getSecret()` in Bicep, `data "azurerm_key_vault_secret"` in Terraform).
- Pipeline secrets: Workload Identity Federation short-lived tokens; no stored client secrets in GitHub Secrets or Azure DevOps variable groups for Azure auth.
- App secrets: reference Key Vault secret URIs in app settings — `@Microsoft.KeyVault(SecretUri=https://vault.vault.azure.net/secrets/name/version)` — resolved at runtime by the Azure platform using the app's Managed Identity.
- `terraform output` of sensitive values: mark `sensitive = true`; never print raw outputs in CI logs.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Writing raw ARM JSON templates instead of Bicep | Verbose, error-prone, no type checking. Bicep compiles to ARM — use it. |
| Single Terraform state file for the entire organization | One bad apply with an error blast radius = everything. Split by environment and bounded context. |
| Service principal client secret in Azure DevOps variable group | Rotated manually (or not at all); secret exposure risk. Workload Identity Federation. |
| `az deployment group create` from a developer laptop in production | No approval trail, no lock, possible state inconsistency. Pipeline-only applies for production. |
| `terraform apply -auto-approve` on main branch merge for production | One bad PR + merge = production outage. Manual approval gate or tag-gated release. |
| No drift detection | Portal quick-fixes during incidents become permanent invisible drift. Schedule `what-if` daily. |
| Bicep Complete mode on a shared resource group | Complete mode removes resources not in the template — including any resources other teams deployed. Use Incremental or Deployment Stacks. |
| Hard-coded resource IDs or secrets in Bicep / Terraform | IDs change between environments; secrets leak into source control. Use parameters and Key Vault references. |

## Defaults — release pipeline

- Trunk-based development; feature branches short-lived (< 2 days).
- PRs require: passing lint + what-if / plan + at least one human reviewer.
- Container images tagged with git SHA; never `:latest` in production.
- Image scan in CI via Microsoft Defender for Containers or `trivy`; gate production deploys on findings severity.
- Every deploy emits a deployment marker to Application Insights (`az monitor app-insights events create` or SDK call) so dashboards correlate changes to behaviour.
- Rollback is one command: `az webapp deployment slot swap`, `kubectl rollout undo`, or a Bicep redeployment of the previous parameter file version.

## Cost considerations

- Azure DevOps parallel jobs have a cost above the free tier — self-hosted agents on Azure Container Instances or a small VM scale set are cheaper at scale.
- Terraform plan artifacts (stored in CI) don't expire automatically; add a retention policy on plan storage (7 days is sufficient).
- Test infrastructure provisioned by `terratest` or Pester should be torn down by the pipeline even if the test fails — use a `defer`-style cleanup or pipeline `finally` block.
- Azure Deployment Environments (ADE) for developer self-service; cost governance via environment types with allowed SKUs and auto-shutdown schedules.

## Observability hints

- Tag every resource in IaC with `Environment`, `Service`, `Owner`, `CostCenter`. Enforce with Azure Policy; block deploys that omit required tags.
- Pipeline metrics: track lead time, deployment frequency, change failure rate, and mean time to recovery (DORA four) via Azure DevOps Analytics or GitHub Actions data in Log Analytics.
- `az deployment group show` or `terraform show` outputs surfaced in the PR comment — reviewers see what changes before approving.

## Verification checklist

- [ ] One primary IaC tool; mixed tools have clean, documented boundaries.
- [ ] State backend remote, versioned, CMK-encrypted; per-environment separation.
- [ ] No service principal client secrets in CI — Workload Identity Federation.
- [ ] What-if / plan diff posted on PR; human approval required for production.
- [ ] Stateful resources isolated in their own module with `CanNotDelete` resource locks.
- [ ] Tag policy applied in code; enforced by Azure Policy with deny effect.
- [ ] Rollback procedure documented and tested at least once per quarter.
- [ ] Drift detection scheduled; alert on unexpected diff between IaC and live state.
- [ ] Bicep linting (`az bicep build --lint`) or `tflint` + `checkov` in CI, failing on errors.
- [ ] No secrets in parameter files, `.tfvars`, or pipeline variable groups — Key Vault references throughout.
