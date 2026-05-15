---
description: Scaffold an OCI Infrastructure-as-Code project — pick Terraform with the oracle/oci provider or Resource Manager, with opinionated production-grade defaults.
argument-hint: <workload-description>
---

# OCI Scaffold IaC

Scaffold a new OCI Infrastructure-as-Code project for a workload described as: **$ARGUMENTS**

## What to do

1. **Confirm the tool choice.** Ask the user which IaC approach they prefer, with a one-line recommendation based on the workload description:
   - Team already uses Terraform across multiple providers → **Terraform with `oracle/oci` provider ≥ 6.x**.
   - Fully managed execution with no self-hosted runner, OCI-native drift detection, Vault-integrated secrets → **OCI Resource Manager** (Terraform under the hood, managed by OCI).
   - Team prefers a general-purpose programming language over HCL → **Pulumi with the OCI provider**.
   - Open-source Terraform-compatible engine without BSL licensing → **OpenTofu with `oracle/oci` provider**.
   Recommend; do not prescribe. Defer to the user's preference.

2. **Confirm scope** with up to three questions if not clear from the workload description:
   - Target tenancy region and home region?
   - New VCN or attaching to an existing one (compartment OCID / VCN OCID)?
   - Greenfield stack, or importing console-built resources?

3. **Generate the project skeleton** in the current working directory (or a subdirectory the user names). Every scaffold must include:
   - Pinned tool and provider versions with a lockfile.
   - Per-environment separation (`dev`, `staging`, `prod`).
   - Remote state (Terraform: Object Storage S3-compatible backend; Resource Manager: OCI-managed).
   - A `.gitignore` excluding `.terraform/`, `*.tfstate`, `*.tfstate.backup`, `*.tfvars` with secrets.
   - A `README.md` with bootstrap and apply commands, OCI CLI prerequisites, and environment variable notes.
   - Three stacks: `networking` (VCN + subnets + gateways + NSGs), `iam` (compartments + dynamic groups + policies + Vault), `workload` (compute or OKE + Load Balancer + monitoring).
   - GitHub Actions (or OCI DevOps pipeline spec) with OIDC federation for plan and apply, plus IaC linting (`tflint`, `checkov`).
   - Tag Defaults in the `iam` stack so every resource inherits `Environment`, `Service`, `Team`, `CostCenter`.

4. **Wire safe defaults.** For each scaffold:
   - Customer-managed Vault key referenced from every storage resource block (Object Storage `kms_key_id`, Block Volume `kms_key_id`, Autonomous Database `kms_key_id` and `vault_id`).
   - `lifecycle { prevent_destroy = true }` on all stateful resources in the workload stack.
   - VCN with three subnet tiers (public, private, database), one NAT Gateway, one Internet Gateway, one Service Gateway, Service Gateway route in every private and database subnet route table.
   - NSGs as the primary access control; Security Lists set only subnet-wide defaults.
   - Dynamic group scoped to the deployment compartment (not the tenancy root).
   - OCI Monitoring alarm resources with a Notification topic for each deployment unit.
   - Logging log group with explicit `retention_duration` for every service log.

5. **Print next steps** — bootstrap commands the user must run (OCI CLI profile setup, Terraform backend init, Resource Manager stack create, OIDC provider registration), plus an explicit reminder that the first apply should target `dev`, not `prod`.

## Tool-specific layouts

### Terraform (HCL) with `oracle/oci` provider

```
.
├── envs/
│   ├── dev/
│   │   ├── backend.tf         # Object Storage S3 backend, customer-managed Vault key
│   │   ├── main.tf            # Module calls per environment
│   │   ├── terraform.tfvars   # Non-secret env values only — no credentials
│   │   └── outputs.tf
│   ├── staging/...
│   └── prod/...
├── modules/
│   ├── networking/            # VCN, subnets, IGW, NAT GW, Service GW, NSGs, route tables
│   ├── iam/                   # Compartments, dynamic groups, policies, Vault, Tag Defaults
│   └── workload/              # Compute / OKE, Load Balancer, alarms, log groups
├── .terraform.lock.hcl
├── .github/workflows/
│   ├── tf-plan.yml            # OIDC auth, tflint + checkov, terraform plan on PR
│   └── tf-apply.yml           # OIDC auth, terraform apply on merge to main (with approval gate)
└── README.md
```

Key Terraform file excerpts the scaffold must contain:

- `versions.tf` declaring `required_providers { oci = { source = "oracle/oci", version = ">= 6.0" } }` and `required_version = ">= 1.6"`.
- `backend.tf` using the S3-compatible backend pointed at an OCI Object Storage bucket in the `platform` compartment.
- `modules/iam/main.tf` declaring the compartment hierarchy, dynamic groups, and a core policy granting the workload's dynamic group `use keys` in the Vault compartment and `read secret-family` in the platform compartment.
- `modules/networking/main.tf` with `prevent_destroy = true` on the VCN.
- `modules/workload/main.tf` with `prevent_destroy = true` on any stateful resource and explicit `kms_key_id` on each storage resource.

### OCI Resource Manager

```
.
├── main.tf                    # Root module — calls sub-modules
├── variables.tf               # Input variables (no secrets — use Vault variable source in RM)
├── outputs.tf
├── modules/
│   ├── networking/
│   ├── iam/
│   └── workload/
├── .github/workflows/
│   └── rm-plan.yml            # OCI CLI: oci resource-manager job create-plan-job (OIDC auth)
└── README.md
```

Resource Manager stacks are created via the OCI Console or OCI CLI: `oci resource-manager stack create --compartment-id <ocid> --config-source ./ --terraform-version "1.6.x"`. Secrets are injected via the Vault variables integration in the stack configuration, not via `terraform.tfvars`.

## After scaffolding

- Hand off to the `oci-architect` sub-agent for a same-day review of the generated stack before the first `apply`.
- Run `oci-security-reviewer` once the dev environment is deployed to catch any configuration drift from the intended posture.
- Reminder: IAM policies, Vault keys, and dynamic groups belong in the `iam` stack — they must be applied before the workload stack depends on them. Plan the dependency order before running `apply`.
- Enable OCI Resource Manager drift detection on a weekly schedule once the production stack is stable — any console change made during an incident will be visible within a week.
