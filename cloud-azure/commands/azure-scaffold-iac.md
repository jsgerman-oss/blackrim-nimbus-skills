---
description: Scaffold an Azure Infrastructure-as-Code project — primary Bicep or Terraform, with opinionated production-grade defaults. ARM templates are legacy and are not generated.
argument-hint: <workload-description>
---

# Azure Scaffold IaC

Scaffold a new Azure Infrastructure-as-Code project for a workload described as: **$ARGUMENTS**

## What to do

1. **Confirm the tool choice.** Ask the user which IaC tool they want, with a one-line recommendation based on the workload description:
   - Azure-only shop, team comfortable with a typed DSL, wants no state file → **Bicep** (recommended default for Azure-focused teams).
   - Multi-cloud, multi-provider, or org already standardized on HCL → **Terraform** (`hashicorp/azurerm` >= 4.x + `Azure/azapi` >= 2.x) or **OpenTofu**.
   - The user mentions ARM JSON templates → recommend Bicep instead. ARM JSON is legacy; Bicep compiles to ARM and is the recommended authoring surface for all new Azure IaC.
   Do not prescribe — recommend, then defer to the user.

2. **Confirm scope** with up to three questions if not obvious from the workload description:
   - Single subscription, or multi-subscription with a Management Group hierarchy?
   - Network: new VNet, or integrating with an existing hub-spoke topology?
   - State: greenfield, or migrating from portal-built infrastructure (requires `az resource show` imports)?

3. **Generate the project skeleton** in the current working directory or a subdirectory the user specifies. Every scaffold must include:
   - Pinned tool / provider versions.
   - Per-environment separation (`dev`, `stage`, `prod`).
   - Remote, locked state (Terraform) or ARM-native state via Bicep.
   - A `.gitignore` appropriate to the tool.
   - A `README.md` with bootstrap and deploy / destroy commands.
   - At least one module / template set: networking (VNet + NSGs + private DNS zones) + a compute placeholder + a data placeholder.
   - GitHub Actions (or Azure DevOps Pipeline YAML) with Workload Identity Federation for plan / apply, plus lint (`az bicep build --lint` / `tflint` + `checkov`).
   - Tagging policy applied via a shared parameter or local variable (`Environment`, `Service`, `Owner`, `CostCenter`).

4. **Wire safe defaults.** For every scaffold:
   - Customer-managed key encryption at rest: Key Vault deployed first; CMK created; storage / database resources reference it.
   - Managed Identity on every compute resource: `identity: { type: 'SystemAssigned' }` in Bicep; `identity { type = "SystemAssigned" }` in Terraform.
   - Private endpoints for every PaaS data service; `publicNetworkAccess: 'Disabled'` on storage and databases.
   - VNet with dedicated subnets for compute, data, and management; NSG on each subnet with default-deny inbound.
   - Log Analytics workspace with bounded retention (30 days hot, 90 days for security tables); Application Insights linked to the same workspace.
   - Diagnostic settings on every resource routing audit logs to the Log Analytics workspace.
   - Azure Policy assignment for required tags; deny effect.
   - Resource lock (`CanNotDelete`) on every stateful production resource.

5. **Print next steps** — bootstrap commands the user must run before first deploy, plus a reminder that the first deployment should target `dev`, not `prod`.

## Tool-specific layouts

### Bicep

```
.
├── main.bicep                     # Subscription-scope entry point (resource groups, RBAC)
├── modules/
│   ├── network.bicep              # VNet, subnets, NSGs, private DNS zones
│   ├── compute.bicep              # Functions / AKS / App Service placeholder
│   ├── data.bicep                 # Storage, database, Redis placeholder
│   ├── keyvault.bicep             # Key Vault, CMK, diagnostic settings
│   └── monitoring.bicep           # Log Analytics workspace, App Insights, alerts
├── environments/
│   ├── dev.bicepparam             # Dev parameter values (no secrets — Key Vault refs only)
│   ├── stage.bicepparam
│   └── prod.bicepparam
├── .github/workflows/
│   ├── bicep-whatif.yml           # PR: az deployment what-if, post diff as comment
│   └── bicep-deploy.yml           # Merge: deploy to dev/stage; manual approval for prod
├── .gitignore
└── README.md
```

**Key Bicep conventions:**

- `targetScope = 'subscription'` in `main.bicep` for resource group creation and RBAC; `targetScope = 'resourceGroup'` in modules.
- Sensitive parameters use Key Vault secret references via `getSecret()` — never store values in `.bicepparam` files.
- `az bicep build --lint main.bicep` must pass before any PR merge.
- `az deployment sub what-if --template-file main.bicep --parameters environments/dev.bicepparam` in CI, piped to a PR comment via `gh pr comment`.

### Terraform (HCL)

```
.
├── envs/
│   ├── dev/
│   │   ├── backend.tf             # azurerm backend, separate storage account per env
│   │   ├── main.tf                # Module instantiation
│   │   ├── terraform.tfvars       # Non-sensitive env values only
│   │   └── outputs.tf
│   ├── stage/...
│   └── prod/...
├── modules/
│   ├── network/                   # VNet, subnets, NSGs, private DNS zones, private endpoints
│   ├── compute/                   # AKS / Functions / App Service
│   ├── data/                      # Storage account, database, Redis
│   ├── keyvault/                  # Key Vault, CMK, RBAC assignments
│   └── monitoring/                # Log Analytics, App Insights, alerts, action groups
├── .terraform.lock.hcl
├── .github/workflows/
│   ├── tf-plan.yml                # PR: terraform plan, post diff as comment
│   └── tf-apply.yml               # Merge: apply dev/stage; manual approval gate for prod
├── .gitignore
└── README.md
```

**Key Terraform conventions:**

- `azurerm` backend: `resource_group_name`, `storage_account_name`, `container_name`, `key` pointing to `<env>.tfstate`. The state storage account is deployed separately before any other resource.
- `prevent_destroy = true` on all stateful resources (storage accounts, databases, Key Vault, AKS cluster) in the `prod` environment.
- Secrets via `data "azurerm_key_vault_secret"` — never in `.tfvars` or `outputs` without `sensitive = true`.
- `tflint --chdir=envs/dev` + `checkov --directory=envs/dev` in CI; fail on any check-failed result.

## After scaffolding

- Hand the generated IaC to the `azure-architect` sub-agent for a same-day review before the first `az deployment ... create` or `terraform apply`.
- Run `azure-security-reviewer` once the first environment is deployed and before admitting any external traffic.
- Remind the user that the Key Vault, Managed Identity, and RBAC bootstrap resources in the `keyvault` and `monitoring` modules belong to a dedicated bootstrap deployment that the team owns — they should not be re-created by an application-tier pipeline.
- Confirm that the Workload Identity Federation credential is scoped to the correct branch ref (`refs/heads/main` for apply; `refs/pull/*/merge` for plan) — overly broad subjects (`*`) negate the security value of federation.
