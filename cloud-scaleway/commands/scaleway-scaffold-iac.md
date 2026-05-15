---
description: "Scaffold a Scaleway Infrastructure-as-Code project — primary Terraform scaleway/scaleway provider, with opinionated production defaults. Alt path: scw CLI bootstrap for Kapsule clusters."
argument-hint: <workload-description>
---

# Scaleway Scaffold IaC

Scaffold a new Scaleway Infrastructure-as-Code project for a workload described as: **$ARGUMENTS**

## What to do

1. **Confirm the choice of IaC tool.** Recommend based on the workload description:
   - Any Scaleway workload → **Terraform with `scaleway/scaleway` provider ≥ 2.45** (default recommendation — best resource coverage, active provider, S3-compatible state backend on Scaleway Object Storage).
   - Team prefers TypeScript/Python over HCL → **Pulumi `pulumiverse/scaleway`** (community-maintained; verify resource parity for your specific resources before committing).
   - Quick Kapsule cluster bootstrap, one-off resource creation, or scripted automation → **`scw` CLI** (not a substitute for declarative IaC — use for bootstrapping and operational tasks).
   - Kubernetes-native control plane (platform engineering) → **Crossplane with Scaleway provider** (niche; only if you're already running Crossplane).
   Don't prescribe — recommend, then defer to the user.

2. **Confirm scope** with up to three questions if not obvious:
   - Which Scaleway region(s) and Project ID? (EU regions: `fr-par`, `nl-ams`, `pl-waw` — note that global latency outside EU may require a separate CDN strategy.)
   - Network: new VPC + Private Networks, or join existing? Existing Private Network IDs?
   - State: greenfield, or migrating from console (resource import needed)?

3. **Generate the project skeleton** in the current working directory (or a subdirectory the user picks). Every scaffold must include:
   - Pinned provider versions and a committed `.terraform.lock.hcl`.
   - Per-environment separation (`dev`, `stage`, `prod`).
   - Remote state in Scaleway Object Storage (S3-compatible backend).
   - A `.gitignore` for Terraform artifacts.
   - A `README.md` with bootstrap + deploy / destroy commands.
   - At least one stack: networking (VPC + Private Network + Public Gateway) + a compute placeholder + a data placeholder.
   - GitHub Actions CI with a CI IAM Application credential workflow (plan on PR, apply on merge / manual approval for prod).
   - Tagging applied to all resources (`tags = ["env:${var.environment}", "service:${var.service_name}", "team:${var.team}"]`).

4. **Wire safe defaults.** For every scaffold:
   - Encryption at rest on all data resources (SSE-S3 on Object Storage; Managed Database encrypted by default).
   - Stateful resources tagged with `prevent_destroy = true` in `lifecycle` blocks.
   - Private Networks for all backend-to-backend traffic; no Managed Database or Redis with public IP.
   - IAM Application per workload with least-privilege Policy (not Organization-admin).
   - Cockpit token resource for pushing application metrics and logs.
   - All secrets referenced from Secret Manager, not hardcoded.

5. **Print next steps** — bootstrap commands the user must run, plus explicit reminders:
   - Create Object Storage bucket for Terraform state before `terraform init`.
   - First deploy should target `dev`, not `prod`.
   - Obtain Scaleway API credentials (`scw iam api-key create --application-id <ci-app-id>`) and store in CI secrets before running the pipeline.

## Terraform (HCL) layout

```
.
├── envs/
│   ├── dev/
│   │   ├── backend.tf          # S3 backend, Scaleway Object Storage endpoint
│   │   ├── main.tf             # Module instantiation for this env
│   │   ├── terraform.tfvars    # Non-secret env vars (region, node_type, etc.)
│   │   └── outputs.tf
│   ├── stage/
│   │   └── …
│   └── prod/
│       └── …
├── modules/
│   ├── network/
│   │   ├── main.tf             # VPC, Private Networks, Public Gateway
│   │   ├── variables.tf
│   │   └── outputs.tf
│   ├── compute/
│   │   ├── main.tf             # Kapsule cluster or Serverless Container placeholder
│   │   ├── variables.tf
│   │   └── outputs.tf
│   └── data/
│       ├── main.tf             # Managed Database, Redis, Object Storage bucket
│       ├── variables.tf        # prevent_destroy = true on stateful resources
│       └── outputs.tf
├── .terraform.lock.hcl         # Committed; updated explicitly via terraform init -upgrade
├── .gitignore                  # .terraform/, *.tfstate, *.tfstate.backup, *.tfplan
├── .github/
│   └── workflows/
│       ├── tf-plan.yml         # Runs on PR: fmt, tflint, checkov, terraform plan
│       └── tf-apply.yml        # Runs on merge or manual dispatch: terraform apply
└── README.md
```

## Core module starters

### network/main.tf (starter)

```hcl
resource "scaleway_vpc" "main" {
  name   = "${var.environment}-vpc"
  region = var.region
  tags   = ["env:${var.environment}", "team:${var.team}"]
}

resource "scaleway_vpc_private_network" "app" {
  name   = "${var.environment}-app-net"
  vpc_id = scaleway_vpc.main.id
  tags   = ["env:${var.environment}", "tier:app"]
}

resource "scaleway_vpc_private_network" "db" {
  name   = "${var.environment}-db-net"
  vpc_id = scaleway_vpc.main.id
  tags   = ["env:${var.environment}", "tier:db"]
}

resource "scaleway_vpc_public_gateway" "main" {
  name = "${var.environment}-gw"
  type = "VPC-GW-S"
  tags = ["env:${var.environment}"]
}

resource "scaleway_vpc_gateway_network" "app" {
  gateway_id         = scaleway_vpc_public_gateway.main.id
  private_network_id = scaleway_vpc_private_network.app.id
  dhcp {
    subnet = var.app_subnet_cidr
  }
}
```

### data/main.tf (starter — Postgres Managed Database)

```hcl
resource "scaleway_rdb_instance" "main" {
  name              = "${var.environment}-postgres"
  engine            = "PostgreSQL-16"
  node_type         = var.db_node_type  # "DB-DEV-S" for dev, "DB-GP-M" for prod
  is_ha_cluster     = var.environment == "prod"
  disable_backup    = false
  backup_schedule_frequency = 24
  backup_schedule_retention = var.environment == "prod" ? 30 : 7

  private_network {
    ip_net = var.db_private_ip
    pn_id  = var.db_private_network_id
  }

  lifecycle {
    prevent_destroy = true
  }

  tags = ["env:${var.environment}", "service:${var.service_name}"]
}
```

### IAM Application + Policy (CI scaffold)

```hcl
resource "scaleway_iam_application" "ci_terraform" {
  name        = "ci-terraform-${var.environment}"
  description = "Terraform CI/CD for ${var.environment}"
}

resource "scaleway_iam_policy" "ci_terraform" {
  name           = "ci-terraform-policy-${var.environment}"
  application_id = scaleway_iam_application.ci_terraform.id

  rule {
    project_ids          = [var.scaleway_project_id]
    permission_set_names = [
      "InstancesFullAccess",
      "ContainersFullAccess",
      "KubernetesFullAccess",
      "ObjectStorageFullAccess",
      "DatabasesFullAccess",
      "LoadBalancersFullAccess",
      "VPCFullAccess",
      "SecretManagerFullAccess",
    ]
  }
}

resource "scaleway_iam_api_key" "ci_terraform" {
  application_id = scaleway_iam_application.ci_terraform.id
  description    = "CI Terraform key — rotate every 90 days"
  expires_at     = timeadd(timestamp(), "2160h")  # 90 days
  # Output the secret_key once and store in CI secrets immediately
}

output "ci_api_key_access" {
  value     = scaleway_iam_api_key.ci_terraform.access_key
  sensitive = false
}

output "ci_api_key_secret" {
  value     = scaleway_iam_api_key.ci_terraform.secret_key
  sensitive = true  # Never print in CI logs
}
```

## GitHub Actions CI (plan workflow)

```yaml
name: Terraform Plan
on:
  pull_request:
    paths:
      - 'envs/**'
      - 'modules/**'

jobs:
  plan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: "~> 1.6"

      - name: Lint
        run: |
          terraform fmt -check -recursive
          pip install checkov
          checkov -d . --framework terraform --quiet

      - name: Terraform Init
        run: terraform init
        working-directory: envs/dev
        env:
          SCW_ACCESS_KEY: ${{ secrets.SCW_ACCESS_KEY_DEV }}
          SCW_SECRET_KEY: ${{ secrets.SCW_SECRET_KEY_DEV }}

      - name: Terraform Plan
        run: terraform plan -out=plan.tfplan
        working-directory: envs/dev
        env:
          SCW_ACCESS_KEY: ${{ secrets.SCW_ACCESS_KEY_DEV }}
          SCW_SECRET_KEY: ${{ secrets.SCW_SECRET_KEY_DEV }}
          TF_VAR_scaleway_project_id: ${{ secrets.SCW_PROJECT_ID_DEV }}

      # Post plan output as a PR comment
      - name: Comment Plan
        uses: borchero/terraform-plan-comment@v2
        with:
          plan-path: envs/dev/plan.tfplan
```

## `scw` CLI — Kapsule cluster bootstrap (alt path)

For teams that want a quick Kapsule cluster before Terraform is fully set up:

```bash
# 1. Configure CLI
scw config set access-key $SCW_ACCESS_KEY
scw config set secret-key $SCW_SECRET_KEY
scw config set default-project-id $SCW_PROJECT_ID
scw config set default-region fr-par

# 2. Create a Private Network
scw vpc private-network create name=kapsule-net

# 3. Create Kapsule cluster on that Private Network
scw k8s cluster create \
  name=my-cluster \
  version=1.31 \
  cni=cilium \
  private-network-id=$(scw vpc private-network list name=kapsule-net -o json | jq -r '.[0].id')

# 4. Add a node pool
scw k8s pool create \
  cluster-id=$(scw k8s cluster list name=my-cluster -o json | jq -r '.[0].id') \
  name=default \
  node-type=PRO2-S \
  size=2 \
  min-size=1 \
  max-size=5 \
  autohealing=true \
  autoscaling=true

# 5. Get kubeconfig
scw k8s kubeconfig install $(scw k8s cluster list name=my-cluster -o json | jq -r '.[0].id')
```

Import the CLI-created resources into Terraform after initial setup:
```bash
terraform import scaleway_k8s_cluster.main fr-par/<cluster-id>
```

## After scaffolding

- Hand the generated scaffold to `scaleway-architect` for a same-day review before the first `terraform apply` to production.
- Run `scaleway-security-reviewer` after the first dev environment is deployed, before enabling external traffic.
- Confirm the Scaleway Cockpit token is configured and application metrics/logs are flowing before launch.
- Remind the team: prod applies require manual approval; never `terraform apply` from a laptop against production.
- Set calendar reminders for CI API key expiry (90 days from generation).
