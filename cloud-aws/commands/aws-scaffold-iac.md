---
description: Scaffold an AWS Infrastructure-as-Code project — pick CDK, Terraform, CloudFormation, or SAM, with opinionated production-grade defaults.
argument-hint: <workload-description>
---

# AWS Scaffold IaC

Scaffold a new AWS Infrastructure-as-Code project for a workload described as: **$ARGUMENTS**

## What to do

1. **Confirm the choice of tool.** Ask the user which IaC tool they want, with a one-line recommendation based on the workload description:
   - Lambda-heavy serverless app → **SAM** (best local dev loop for Lambda + API Gateway).
   - AWS-only app with team comfortable in TS / Python → **CDK v2**.
   - Multi-cloud, multi-provider, or large org standard → **Terraform** (`hashicorp/aws` ≥ 5.x) or **OpenTofu**.
   - Inheriting CFN, GovCloud / China, or strict CFN parity → **CloudFormation**.
   Don't prescribe — recommend, then defer to the user.

2. **Confirm scope** with up to three questions if not obvious:
   - Single account or org (and target account / region)?
   - Network: new VPC, or existing one (CIDR / id)?
   - State: greenfield, or migrating from console (import vs greenfield)?

3. **Generate the project skeleton** in the current working directory (or a subdirectory the user picks). Use the layout below for the chosen tool. Every scaffold must include:
   - Pinned tool / provider versions and a lockfile.
   - Per-environment separation (`dev`, `stage`, `prod`).
   - Remote, locked state (Terraform) or CDK app config.
   - A `.gitignore` for the tool.
   - A `README.md` with bootstrap + deploy / destroy commands.
   - At least one stack: networking (VPC) + a compute placeholder + a state placeholder.
   - GitHub Actions (or equivalent) CI with OIDC role for plan / apply, plus lint (`tflint` / `checkov` / `tfsec` or `cdk-nag`).
   - Tagging policy applied via shared module / construct (`Environment`, `Service`, `Owner`, `CostCenter`).

4. **Wire safe defaults.** For each scaffold:
   - Encryption at rest on by default.
   - Stateful resources tagged with `prevent_destroy = true` / `RemovalPolicy.RETAIN`.
   - VPC with three-AZ, public / private / isolated subnets, one NAT per AZ, S3 + DynamoDB gateway endpoints.
   - IAM roles defined per workload — no `Action: "*"`.
   - CloudWatch log groups with bounded retention.

5. **Print next steps** — bootstrap commands the user must run (`cdk bootstrap`, `terraform init -backend-config=...`, `sam build`, etc.), plus an explicit reminder that the first deploy should target `dev`, not `prod`.

## Tool-specific layouts

### CDK v2 (TypeScript)

```
.
├── bin/
│   └── app.ts                 # CDK app, env / stack instantiation
├── lib/
│   ├── network-stack.ts       # VPC + subnets + endpoints
│   ├── compute-stack.ts       # Lambda / ECS placeholder
│   ├── data-stack.ts          # DDB / RDS placeholder, RemovalPolicy.RETAIN
│   └── shared/
│       └── tagging.ts         # Aspects-based tagger
├── test/
│   └── snapshot.test.ts       # cdk synth snapshot
├── cdk.json
├── tsconfig.json
├── package.json
├── package-lock.json
├── .github/workflows/
│   ├── cdk-diff.yml
│   └── cdk-deploy.yml
└── README.md
```

### Terraform (HCL)

```
.
├── envs/
│   ├── dev/
│   │   ├── backend.tf         # S3 backend, KMS-encrypted, locked
│   │   ├── main.tf            # Module instantiation per env
│   │   ├── terraform.tfvars
│   │   └── outputs.tf
│   ├── stage/...
│   └── prod/...
├── modules/
│   ├── network/
│   ├── compute/
│   └── data/
├── .terraform.lock.hcl
├── .github/workflows/
│   ├── tf-plan.yml
│   └── tf-apply.yml
└── README.md
```

### SAM

```
.
├── template.yaml              # SAM template
├── src/
│   └── functions/<fn>/
├── events/                    # Local-test events
├── samconfig.toml             # Per-env config
├── .github/workflows/
│   └── sam-deploy.yml
└── README.md
```

### CloudFormation

```
.
├── templates/
│   ├── network.yaml
│   ├── compute.yaml
│   └── data.yaml
├── params/
│   ├── dev.json
│   ├── stage.json
│   └── prod.json
├── pipeline.yaml              # CodePipeline if used
└── README.md
```

## After scaffolding

- Hand off to the `aws-architect` sub-agent for a same-day review of the generated stack before the first `apply`.
- Recommend the user run `aws-security-reviewer` once the first environment is deployed, before letting traffic on.
- Remind that IAM roles, KMS keys, and CloudTrail belong in a separate `bootstrap` stack the user owns, not in this app scaffold.
