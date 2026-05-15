---
description: Scaffold an Alibaba Cloud Infrastructure-as-Code project — Terraform aliyun/alicloud or ROS, with opinionated production-grade defaults. Handles China vs International region specifics.
argument-hint: <workload-description>
---

# Alibaba Scaffold IaC

Scaffold a new Alibaba Cloud Infrastructure-as-Code project for a workload described as: **$ARGUMENTS**

## What to do

1. **Confirm the IaC tool.** Recommend based on the workload description, then defer to the user:
   - Multi-cloud, multi-provider, or org-wide standard → **Terraform** (`aliyun/alicloud` ≥ 1.220 provider). Default choice.
   - Alibaba Cloud Marketplace delivery, ACK console integration, or existing ROS investment → **ROS (Resource Orchestration Service)**.
   - Team prefers a full programming language over HCL → **Pulumi** with the Alibaba Cloud provider.

2. **Confirm scope** with up to three questions if not obvious:
   - China region (`cn-*`), International region, or both? This changes ICP / MLPS requirements, endpoint URLs, and account assumptions.
   - New VPC, or existing one (VPC ID / CIDR)?
   - Greenfield, or migrating from console (requires `terraform import` or ROS `ADOPT`)?

3. **Generate the project skeleton** in the current working directory (or a subdirectory the user picks). Every scaffold must include:
   - Pinned provider / tool versions and lockfile.
   - Per-environment separation (`dev`, `staging`, `prod`).
   - Remote, locked state (OSS backend for Terraform) or equivalent.
   - A `.gitignore` for the chosen tool.
   - A `README.md` with bootstrap and deploy / destroy commands.
   - At least one stack: networking (VPC + VSwitch) + compute placeholder + data store placeholder.
   - GitHub Actions (or Jenkins / GitLab) CI with RAM Role OIDC for plan / apply, plus linting.
   - Tagging policy applied via shared module / variable (`Environment`, `Service`, `Owner`, `CostCenter`).

4. **Wire safe defaults.** For each scaffold:
   - KMS CMK encryption at rest on all data stores.
   - Stateful resources tagged with `prevent_destroy = true` / deletion protection.
   - VPC with multi-zone VSwitch layout (public / private / isolated tiers, ≥ 2 zones), NAT Gateway per zone, OSS VPC endpoint configured.
   - RAM Role per workload — no `Action: ["*"]` or root AK/SK.
   - SLS Logstore with explicit TTL (30 d hot; OSS lifecycle for archive).
   - CloudMonitor alarm on at least one user-visible signal per service.

5. **Print next steps** — bootstrap commands (OSS state bucket creation, provider init, first plan), plus an explicit reminder that the first apply targets `dev`, not `prod`, and that ICP filing must be confirmed before pointing any CDN / public IP at China-region audiences.

## Tool-specific layouts

### Terraform (primary)

```
.
├── envs/
│   ├── dev/
│   │   ├── backend.tf          # OSS backend, KMS-encrypted, versioned
│   │   ├── main.tf             # Module calls per env
│   │   ├── terraform.tfvars    # Non-secret env config
│   │   └── outputs.tf
│   ├── staging/...
│   └── prod/...
├── modules/
│   ├── network/                # VPC, VSwitch, NAT Gateway, Security Groups
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   ├── compute/                # ECS Auto Scaling / ACK / FC placeholder
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   └── data/                   # RDS/PolarDB, OSS, Redis placeholder
│       ├── main.tf
│       ├── variables.tf
│       └── outputs.tf
├── .terraform.lock.hcl         # Provider lock file — always committed
├── .gitignore
├── .github/workflows/
│   ├── tf-plan.yml             # PR: RAM Role OIDC, checkov scan, plan + comment
│   └── tf-apply.yml            # Merge/tag: manual approval for prod
└── README.md
```

**OSS backend configuration (bootstrap before first `terraform init`):**

```bash
# Run once — creates the state bucket with versioning + KMS encryption
aliyun oss mb oss://my-tf-state-${ACCOUNT_ID} --region cn-hangzhou
aliyun oss bucket-versioning --method put oss://my-tf-state-${ACCOUNT_ID} Enabled
aliyun oss bucket-encryption --method put oss://my-tf-state-${ACCOUNT_ID} \
  '{"SSEAlgorithm":"KMS","KMSMasterKeyID":"<your-cmk-id>"}'
```

`backend.tf` example:

```hcl
terraform {
  backend "oss" {
    bucket              = "my-tf-state-123456789"
    prefix              = "prod/network"
    region              = "cn-hangzhou"
    encrypt             = true
    acl                 = "private"
    tablestore_endpoint = "https://my-lock-table.cn-hangzhou.ots.aliyuncs.com"
    tablestore_table    = "terraform_state_lock"
  }
}
```

**GitHub Actions plan job:**

```yaml
jobs:
  plan:
    runs-on: ubuntu-latest
    permissions:
      id-token: write
      contents: read
    steps:
      - uses: actions/checkout@v4
      - name: Authenticate to Alibaba Cloud
        uses: aliyun-actions/configure-aliyun-credentials@v2
        with:
          role-to-assume: acs:ram::${{ vars.ALICLOUD_ACCOUNT_ID }}:role/github-actions-plan
          oidc-provider-arn: acs:ram::${{ vars.ALICLOUD_ACCOUNT_ID }}:oidc-provider/github-oidc
          role-session-name: terraform-plan
      - uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: "1.9.x"
      - run: terraform -chdir=envs/prod init
      - run: pip install checkov && checkov -d . --framework terraform --soft-fail-on MEDIUM
      - run: terraform -chdir=envs/prod plan -out=plan.tfplan
      - name: Post plan to PR
        uses: actions/github-script@v7
        # ... post plan output as PR comment
```

### ROS (Resource Orchestration Service)

```
.
├── templates/
│   ├── network.yaml            # VPC, VSwitch, NAT Gateway, Security Groups
│   ├── compute.yaml            # ECS / ACK / FC placeholder
│   └── data.yaml               # RDS, OSS, Redis placeholder; DeletionPolicy: Retain
├── params/
│   ├── dev.json
│   ├── staging.json
│   └── prod.json
├── stack-policy-prod.json      # Protects stateful resources from accidental DELETE action
├── pipeline/
│   └── Jenkinsfile             # Or GitHub Actions workflow for ROS change-set + apply
└── README.md
```

`stack-policy-prod.json` (protect data resources):

```json
{
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "Update:*",
      "Principal": "*",
      "Resource": "*"
    },
    {
      "Effect": "Deny",
      "Action": ["Update:Delete", "Update:Replace"],
      "Principal": "*",
      "Resource": "acs:ros:*:*:stack/prod-data/*"
    }
  ]
}
```

## China-region specifics — checklist before first deploy

The following items only apply to China-region (`cn-*`) accounts and have no equivalent in International accounts.

- [ ] **ICP filing status confirmed**: ICP Bei'an (informational) or ICP License (commercial) obtained for the public domain before pointing CDN / public IP at mainland China audiences. Serving without ICP risks ISP-level blocking.
- [ ] **MLPS classification determined**: system classified at MLPS Level 1, 2, or 3 with the team's security officer. Level 2 requires filing with the local public security bureau; Level 3 requires formal annual evaluation.
- [ ] **PIPL / DSL data mapping**: any personal information of mainland China residents identified; cross-border transfer compliance status documented (CAC assessment or SCC filing if data crosses the border).
- [ ] **Endpoint URLs**: confirm Alibaba Cloud service endpoints use `cn-*` hostnames, not International (`ap-*` or global) hostnames — they are different and not interchangeable.
- [ ] **RDS / OSS internal endpoints**: using VPC-internal endpoints (`*.rds.aliyuncs.com` internal, `oss-cn-hangzhou-internal.aliyuncs.com`) to avoid NAT and keep data on the Alibaba backbone.

## After scaffolding

- Hand off to the `alibaba-architect` sub-agent for a same-day review of the generated scaffold before the first `apply`.
- Run `alibaba-security-reviewer` once the first dev environment is deployed, before allowing any non-team traffic.
- Confirm with the team whether China-region ICP filing and MLPS classification are required before finalizing region selection.
- Remind: RAM Roles, KMS CMKs, and ActionTrail trails belong in a `foundation` stack owned by the security team — separate from this app scaffold.
