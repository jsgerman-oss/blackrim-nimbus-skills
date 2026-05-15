---
description: Scaffold a Tencent Cloud Infrastructure-as-Code project — Terraform tencentcloudstack/tencentcloud or TIC, with opinionated production-grade defaults for China or International accounts.
argument-hint: <workload-description>
---

# Tencent Scaffold IaC

Scaffold a new Tencent Cloud Infrastructure-as-Code project for a workload described as: **$ARGUMENTS**

## What to do

1. **Confirm the account type and IaC tool.** Ask the user:
   - **China account** (mainland China regions: `ap-beijing`, `ap-shanghai`, `ap-guangzhou`, etc.) or **International account** (Hong Kong, Singapore, Tokyo, etc.)? The answer affects ICP / MLPS requirements and provider credentials.
   - Which IaC tool:
     - **Terraform** (`tencentcloudstack/tencentcloud` ≥ 1.81): recommended for teams that want full resource coverage, community modules, and self-managed pipelines (GitHub Actions / GitLab CI).
     - **TIC** (Tencent Infrastructure-as-Code): recommended for teams that want Tencent-managed plan/apply execution and console integration, without maintaining a self-hosted CI Terraform runner.
   - Don't prescribe — recommend based on the workload description, then defer to the user.

2. **Confirm scope** with up to three questions if not obvious:
   - Target region(s) and single account or multi-account?
   - Network: new VPC, or existing one (ID / CIDR)?
   - State: greenfield, or migrating from console resources (import vs greenfield)?

3. **Generate the project skeleton** in the current working directory (or a subdirectory the user picks). Every scaffold must include:
   - Pinned provider version and a committed `.terraform.lock.hcl`.
   - Per-environment separation (`dev`, `staging`, `prod`).
   - Remote COS state backend, state file per environment.
   - A `.gitignore` for Terraform artifacts.
   - A `README.md` with bootstrap and deploy/destroy commands.
   - At least one stack: networking (VPC + subnets + NAT) + a compute placeholder + a state placeholder (COS bucket or CDB instance).
   - CI pipeline (GitHub Actions OIDC-to-CAM role, or Coding DevOps equivalent) with lint + plan + apply stages.
   - Tagging policy applied to all resources (`Environment`, `Service`, `Owner`, `CostCenter`).

4. **Wire safe defaults.** For every scaffold:
   - KMS CMK encryption on all stateful resources (CBS, COS, CDB).
   - Stateful resources tagged with `prevent_destroy = true`.
   - VPC with three-subnet tiers (public / private / isolated), at least two AZs, one NAT Gateway per AZ.
   - CAM roles per workload — no `action: *` or `resource: *` in any policy.
   - CLS log topics with explicit `log_retention_period` (never unlimited).
   - Cloud Monitor alarms on compute, database, and error-rate metrics wired to a notification group.
   - **For China accounts**: README note reminding the user to complete ICP filing before the first internet-facing DNS record, and to file MLPS classification before go-live.

5. **Print next steps** — bootstrap commands the user must run, plus a reminder that the first deployment should target `dev`, not `prod`.

## Tool-specific layouts

### Terraform (`tencentcloudstack/tencentcloud`)

```
.
├── envs/
│   ├── dev/
│   │   ├── backend.tf           # COS backend, versioning enabled
│   │   ├── main.tf              # Module instantiation per env
│   │   ├── terraform.tfvars     # Non-secret config values
│   │   └── outputs.tf
│   ├── staging/
│   │   └── ...
│   └── prod/
│       └── ...
├── modules/
│   ├── network/                 # VPC, subnets, NAT, SGs
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   ├── compute/                 # TKE cluster / CVM ASG placeholder
│   │   └── ...
│   └── data/                    # CDB / COS / Redis — prevent_destroy
│       └── ...
├── .terraform.lock.hcl
├── .tflint.hcl
├── .github/
│   └── workflows/
│       ├── tf-plan.yml          # OIDC-to-CAM role, plan on PR
│       └── tf-apply.yml         # Manual approval gate for prod
├── .gitignore
└── README.md
```

Key provider block (`modules/network/main.tf` preamble):

```hcl
terraform {
  required_providers {
    tencentcloud = {
      source  = "tencentcloudstack/tencentcloud"
      version = ">= 1.81, < 2.0"
    }
  }
}

provider "tencentcloud" {
  region = var.region
  # Credentials from environment: TENCENTCLOUD_SECRET_ID, TENCENTCLOUD_SECRET_KEY
  # In CI: sourced from STS assumed-role via OIDC — never static keys
}
```

State backend (`envs/prod/backend.tf`):

```hcl
terraform {
  backend "cos" {
    region = "ap-singapore"            # International; use ap-guangzhou for China
    bucket = "my-tfstate-prod-<appid>"
    prefix = "infra/prod"
  }
}
```

GitHub Actions OIDC-to-CAM role (`.github/workflows/tf-plan.yml` fragment):

```yaml
- name: Configure Tencent Cloud credentials
  env:
    TENCENTCLOUD_REGION: ap-singapore
  run: |
    CREDS=$(tccli sts AssumeRoleWithWebIdentity \
      --RoleArn arn:qcs::cam::uin/12345678:roleName/github-actions-plan \
      --WebIdentityToken "${{ steps.get-token.outputs.token }}" \
      --RoleSessionName github-pr-${{ github.run_id }} \
      --DurationSeconds 3600 \
      --output json)
    echo "TENCENTCLOUD_SECRET_ID=$(echo $CREDS | jq -r .Credentials.TmpSecretId)" >> $GITHUB_ENV
    echo "TENCENTCLOUD_SECRET_KEY=$(echo $CREDS | jq -r .Credentials.TmpSecretKey)" >> $GITHUB_ENV
    echo "TENCENTCLOUD_TOKEN=$(echo $CREDS | jq -r .Credentials.Token)" >> $GITHUB_ENV
```

### TIC (Tencent Infrastructure-as-Code)

TIC runs Terraform from the Tencent Cloud console, connected to a code repository.

```
.
├── main.tf                      # Root module: calls sub-modules
├── variables.tf
├── outputs.tf
├── modules/
│   ├── network/
│   ├── compute/
│   └── data/
├── .terraform.lock.hcl
└── README.md                    # TIC workspace setup instructions
```

TIC-specific steps:
1. Create a TIC workspace in the Tencent Cloud console.
2. Connect the workspace to your code repository (Coding DevOps, GitHub, or GitLab).
3. Configure the workspace environment variables: `TENCENTCLOUD_REGION`, and any workload-specific variables.
4. TIC manages state in Tencent-hosted COS — no backend configuration needed in `main.tf`.
5. Apply from the TIC console or trigger via the TIC API from a CI webhook.
6. **Note**: TIC does not support all Terraform features (provisioners, complex module structures). Evaluate for your workload before committing.

## Safe defaults — network module

Canonical VPC layout for the `modules/network/` module:

```hcl
# VPC
resource "tencentcloud_vpc" "main" {
  name       = "${var.env}-vpc"
  cidr_block = var.vpc_cidr   # e.g. "10.10.0.0/16"
  tags       = local.common_tags
}

# Subnets per AZ (repeat for each AZ)
resource "tencentcloud_subnet" "public" {
  for_each          = var.azs
  vpc_id            = tencentcloud_vpc.main.id
  name              = "${var.env}-public-${each.key}"
  cidr_block        = cidrsubnet(var.vpc_cidr, 4, index(var.azs, each.key))
  availability_zone = each.value
  tags              = local.common_tags
}

resource "tencentcloud_subnet" "private" { ... }   # app tier
resource "tencentcloud_subnet" "isolated" { ... }  # db tier, no default route

# NAT Gateway per AZ
resource "tencentcloud_nat_gateway" "main" {
  for_each    = var.azs
  name        = "${var.env}-nat-${each.key}"
  vpc_id      = tencentcloud_vpc.main.id
  # Use an EIP per NAT
  assigned_eip_set = [tencentcloud_eip.nat[each.key].public_ip]
  tags             = local.common_tags
}

# VPC Flow Logs
resource "tencentcloud_vpc_flow_log" "main" {
  vpc_id          = tencentcloud_vpc.main.id
  traffic_type    = "ALL"
  log_set_id      = var.cls_logset_id
  log_topic_id    = var.cls_flow_log_topic_id
}
```

## After scaffolding

- Hand off to the `tencent-architect` sub-agent for a same-day architecture review before the first `apply`.
- Run `tencent-security-reviewer` once the dev environment is deployed, before proceeding to staging.
- For **China accounts**: confirm ICP filing status and MLPS classification filing with your legal / compliance team before pointing any production DNS records at the deployed infrastructure. Skipping these steps is a regulatory violation, not a technical debt item.
- Remind users that CAM roles (and KMS keys) belong in a bootstrap workspace owned by the platform team, separate from this application scaffold. The application scaffold should reference role ARNs from SSM Parameter Store, not define them inline.
