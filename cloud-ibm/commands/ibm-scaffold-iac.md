---
description: Scaffold an IBM Cloud Infrastructure-as-Code project — Terraform IBM-Cloud/ibm provider or IBM Cloud Schematics, with opinionated production-grade defaults.
argument-hint: <workload-description>
---

# IBM Cloud Scaffold IaC

Scaffold a new IBM Cloud Infrastructure-as-Code project for a workload described as: **$ARGUMENTS**

## What to do

1. **Confirm the IaC tool.** Ask the user which tool they want, with a one-line recommendation based on the workload:
   - Default for new workloads → **Terraform with `IBM-Cloud/ibm` provider >= 1.65** (OpenTofu >= 1.7 for open-source). Largest community, best module ecosystem, works with any CI.
   - IBM Cloud-only team wanting managed state + native console → **IBM Cloud Schematics** (same `IBM-Cloud/ibm` provider; IBM manages state and execution; audit trail to Activity Tracker automatically).
   - Application delivery onto IKS/ROKS → **Helm + Argo CD (GitOps)** for app manifests, with Terraform or Schematics for cluster infrastructure.
   Don't prescribe — recommend, then defer to the user.

2. **Confirm scope** with up to three questions if not obvious:
   - Single account or enterprise account hierarchy? Target region(s)?
   - Network: new VPC, or existing VPC (provide ID and address prefixes)?
   - State: greenfield, or migrating from console (imports required)?

3. **Generate the project skeleton** in the current working directory (or a subdirectory the user picks). Every scaffold must include:
   - Pinned provider version and a `.terraform.lock.hcl` lockfile.
   - Per-environment separation (`dev/`, `stage/`, `prod/`).
   - Remote, locked state in a COS bucket (or Schematics workspace per environment).
   - A `.gitignore` for Terraform or Helm.
   - A `README.md` with bootstrap, deploy, and destroy commands.
   - At least one stack: networking (VPC) + compute placeholder + data placeholder.
   - CI pipeline (GitHub Actions or IBM Cloud Continuous Delivery Toolchain) with Trusted Profile OIDC auth for plan/apply, plus lint (`tflint`, `checkov`).
   - Tagging policy applied via a shared locals block (`env`, `team`, `service`, `cost-center`).

4. **Wire safe defaults.** For every scaffold:
   - Encryption at rest: Key Protect instance + root key per domain; IAM authorization policies for all services → Key Protect.
   - `prevent_destroy = true` on all stateful resources (ICD instances, COS buckets, Key Protect keys, VPC subnets with active workloads).
   - VPC with 3-zone layout, Security Groups deny-by-default, Public Gateway on private-tier only, Endpoint Gateways for COS / ICD / Secrets Manager / Key Protect / Container Registry.
   - IAM Access Groups defined per job function; no direct user IAM policies.
   - Trusted Profile for CI/CD and for each compute workload type.
   - IBM Cloud Monitoring and IBM Cloud Logs instances per region.
   - Activity Tracker instance per region, routed to a COS bucket with Object Lock.

5. **Print next steps** — bootstrap commands the user must run, plus an explicit reminder that the first deploy must target `dev`, not `prod`.

## Tool-specific layouts

### Terraform (default)

```
.
├── bootstrap/
│   ├── main.tf                # Resource groups, Key Protect, Secrets Manager, Activity Tracker
│   ├── iam.tf                 # Access Groups, Trusted Profiles, authorization policies
│   ├── variables.tf
│   └── outputs.tf
├── envs/
│   ├── dev/
│   │   ├── backend.tf         # COS backend; object key = dev/terraform.tfstate
│   │   ├── main.tf            # Module instantiation for dev
│   │   ├── terraform.tfvars   # Non-sensitive env vars (region, resource group names)
│   │   └── outputs.tf
│   ├── stage/ ...
│   └── prod/ ...
├── modules/
│   ├── vpc/                   # VPC, subnets, SGs, Public Gateways, Endpoint Gateways, Flow Logs
│   ├── compute/               # VPC VSI instance group / IKS cluster / Code Engine project
│   └── data/                  # ICD instance(s), COS bucket(s)
├── .terraform.lock.hcl
├── .tflint.hcl
├── .github/
│   └── workflows/
│       ├── tf-plan.yml        # Trusted Profile OIDC; plan on PR; post diff as comment
│       └── tf-apply.yml       # Trusted Profile OIDC; apply on merge to env branch (prod: manual)
├── .gitignore
└── README.md
```

### Schematics (managed Terraform)

```
.
├── main.tf                    # Root module — all environments use the same code; workspace vars separate them
├── variables.tf               # region, resource_group, environment, key_protect_crn, etc.
├── vpc.tf
├── compute.tf
├── data.tf
├── iam.tf
├── observability.tf           # Monitoring, Logs, Activity Tracker instances
├── outputs.tf
├── .tflint.hcl
└── README.md                  # Schematics workspace setup instructions
```

Schematics workspaces: one per environment (`myapp-dev`, `myapp-stage`, `myapp-prod`). Each workspace references the same Git repo + commit; workspace variables carry environment-specific values.

Bootstrap commands:

```bash
# Create dev workspace
ibmcloud schematics workspace new \
  --name myapp-dev \
  --template-url https://github.com/org/myapp-iac \
  --terraform-version 1.6 \
  --variable-store '[{"name":"environment","value":"dev"},{"name":"region","value":"us-south"}]'

# Apply
ibmcloud schematics apply --id <workspace-id> --force
```

### Helm + Argo CD (application delivery on IKS / ROKS)

```
.
├── charts/
│   └── myapp/
│       ├── Chart.yaml
│       ├── values.yaml        # Default values (non-sensitive)
│       ├── values-dev.yaml
│       ├── values-prod.yaml
│       └── templates/
│           ├── deployment.yaml
│           ├── service.yaml
│           ├── ingress.yaml
│           └── hpa.yaml
├── gitops/
│   ├── apps/
│   │   ├── myapp-dev.yaml     # Argo CD Application manifest
│   │   └── myapp-prod.yaml
│   └── applicationset.yaml    # Argo CD ApplicationSet for multi-env
└── README.md
```

## Module — VPC defaults

The `modules/vpc/` module generates:

- VPC with `address_prefix_management = "auto"` disabled — explicit address prefixes per zone.
- 3 zones, each with 3 subnets: `public` (ALB), `private` (application), `data` (databases/caches).
- `public` subnets attached to a Public Gateway per zone.
- `private` and `data` subnets with no Public Gateway.
- Security Groups: `sg-alb` (inbound 443/80 from `0.0.0.0/0`; outbound to `sg-app`), `sg-app` (inbound from `sg-alb`; outbound to `sg-data` and Endpoint Gateway IPs), `sg-data` (inbound from `sg-app` only; no outbound internet).
- VPC Flow Logs configured to ship to a `vpc-flow-logs-<env>` COS bucket.
- Endpoint Gateways for: Cloud Object Storage, IBM Cloud Databases (each engine used), Secrets Manager, Key Protect, IBM Cloud Container Registry.

## Module — IAM bootstrap defaults

The `bootstrap/iam.tf` generates:

- Access Groups: `ag-platform-admins`, `ag-network-operators`, `ag-app-deployers-<env>`, `ag-readonly-audit`.
- Trusted Profile — CI/CD: OIDC claim rule matching GitHub Actions `repository` and `ref` claims. Roles: `Editor` on IKS/ROKS or Code Engine in the environment's resource group; `Reader` on Container Registry.
- Trusted Profile — Compute: compute identity claim matching the VPC VSI CRN prefix or Code Engine project CRN. Roles: `Reader` on Secrets Manager secret group; `Reader` on Key Protect; `Writer` on ICD.
- IAM authorization policies: COS → Key Protect (`Reader`); ICD → Key Protect (`Reader`); Block Storage → Key Protect (`Reader`); Secrets Manager → Key Protect (`Reader`).

## After scaffolding

- Hand off to the `ibm-architect` sub-agent for a review of the generated stack before the first `apply`.
- Recommend the user run `ibm-security-reviewer` once the first environment is deployed, before letting production traffic on.
- Remind that IAM bootstrap resources (Access Groups, Trusted Profiles, Key Protect, Activity Tracker) belong in the `bootstrap/` workspace, applied before any application workspace.
- If the workload is in scope for IBM Cloud Framework for Financial Services: deploy to a Financial Services-validated region (`us-south`, `us-east`, `eu-de`, `eu-gb`); use HPCS (not Key Protect) for KYOK; apply the IBM Cloud FS SCC profile before launch.
