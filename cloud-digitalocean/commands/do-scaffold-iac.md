---
description: Scaffold a DigitalOcean Infrastructure-as-Code project — Terraform `digitalocean/digitalocean` provider or App Platform App Spec YAML, with opinionated production-grade defaults.
argument-hint: <workload-description>
---

# DigitalOcean Scaffold IaC

Scaffold a new DigitalOcean Infrastructure-as-Code project for a workload described as: **$ARGUMENTS**

## What to do

1. **Confirm the IaC tool.** Ask the user which approach they want, with a one-line recommendation based on the workload description:
   - App Platform-hosted service (web app, API, worker, static site) → **App Spec YAML** — declarative, no state file, deployed with `doctl apps create/update`.
   - Droplets, DOKS clusters, Managed Databases, VPCs, firewalls — anything infrastructure → **Terraform** with `digitalocean/digitalocean` >= 2.40 and OpenTofu / Terraform >= 1.6.
   - Mixed workload (e.g., DOKS cluster + Managed Database + App Platform front end) → **Terraform for infrastructure, App Spec for the App Platform app**, committed to the same repo with separate apply paths.
   Don't prescribe — recommend, then defer to the user.

2. **Confirm scope** with up to three questions if not obvious:
   - Target region or regions (e.g., `nyc3`, `sfo3`, `lon1`, `ams3`, `fra1`, `sgp1`)? Multi-region, or single datacenter?
   - New VPC, or an existing one to integrate with?
   - Greenfield, or migrating console-built resources (implies a Terraform import phase)?

3. **Generate the project skeleton** in the current working directory or a subdirectory the user picks. Every scaffold must include:
   - Pinned provider / tool versions and a lockfile.
   - Per-environment separation (`dev`, `stage`, `prod`).
   - Remote state in a Spaces bucket (Terraform) or no state file (App Spec).
   - A `.gitignore` appropriate for the tool.
   - A `README.md` with bootstrap and deploy / destroy commands.
   - At least one module or resource group: networking (VPC, firewall) + a compute placeholder + a state / database placeholder.
   - GitHub Actions CI with PAT-based authentication for plan / apply, plus IaC lint (`tflint`, `checkov` or `trivy --scanners config`).
   - Tagging via DigitalOcean Projects (every resource assigned to a project).

4. **Wire safe defaults.** For each scaffold:
   - VPC explicitly named and CIDRed; no resources in the default VPC.
   - Cloud Firewall rules use tags as sources/destinations; no `0.0.0.0/0` on management ports.
   - All Managed Databases have `private_network_uuid` set and public interface disabled.
   - `prevent_destroy = true` on all stateful resources (databases, Volumes, Spaces buckets).
   - PAT injected via environment variable (`TF_VAR_do_token`); never in `terraform.tfvars`.
   - All resources assigned to a `digitalocean_project` via `digitalocean_project_resources`.
   - Metrics Agent install in Droplet `user_data` where applicable.

5. **Print next steps** — bootstrap commands the user must run, plus an explicit reminder that the first apply should target `dev`, not `prod`.

## Tool-specific layouts

### Terraform (HCL) — infrastructure workloads

```
.
├── envs/
│   ├── dev/
│   │   ├── backend.tf         # Spaces S3-compatible backend
│   │   ├── main.tf            # Module instantiation
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   └── terraform.tfvars   # Non-secret values only
│   ├── stage/
│   │   └── ...
│   └── prod/
│       └── ...
├── modules/
│   ├── networking/            # VPC + firewall
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   ├── compute/               # Droplets or DOKS cluster
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   └── data/                  # Managed Database + Volumes
│       ├── main.tf
│       ├── variables.tf
│       └── outputs.tf
├── .terraform.lock.hcl
├── .gitignore
├── .github/
│   └── workflows/
│       ├── tf-plan.yml        # On PR: lint + plan, post as PR comment
│       └── tf-apply.yml       # On merge to main, manual approval for prod
└── README.md
```

Provide a `backend.tf` template for the Spaces S3-compatible backend:

```hcl
terraform {
  backend "s3" {
    endpoint                    = "https://${var.spaces_region}.digitaloceanspaces.com"
    region                      = "us-east-1"
    bucket                      = "${var.project_name}-tf-state"
    key                         = "${var.environment}/terraform.tfstate"
    skip_credentials_validation = true
    skip_metadata_api_check     = true
    skip_region_validation      = true
    force_path_style            = true
    # Credentials via env: AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY (Spaces keys)
  }
}
```

Provide a minimal networking module:

```hcl
resource "digitalocean_vpc" "main" {
  name     = "${var.project_name}-${var.environment}"
  region   = var.region
  ip_range = var.vpc_cidr
}

resource "digitalocean_firewall" "app" {
  name = "${var.project_name}-${var.environment}-app"
  tags = [digitalocean_tag.app.name]

  inbound_rule {
    protocol         = "tcp"
    port_range       = "80"
    source_addresses = ["0.0.0.0/0", "::/0"]
  }

  inbound_rule {
    protocol         = "tcp"
    port_range       = "443"
    source_addresses = ["0.0.0.0/0", "::/0"]
  }

  # SSH restricted to bastion tag; never 0.0.0.0/0
  inbound_rule {
    protocol    = "tcp"
    port_range  = "22"
    source_tags = [digitalocean_tag.bastion.name]
  }

  outbound_rule {
    protocol              = "tcp"
    port_range            = "1-65535"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }

  outbound_rule {
    protocol              = "udp"
    port_range            = "1-65535"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }
}

resource "digitalocean_project" "main" {
  name        = "${var.project_name}-${var.environment}"
  description = "All resources for ${var.project_name} ${var.environment}"
  purpose     = "Web Application"
  environment = var.environment
}

resource "digitalocean_project_resources" "main" {
  project   = digitalocean_project.main.id
  resources = [
    # Populate as other modules create resources
  ]
}
```

### App Spec YAML — App Platform workloads

```
.
├── app.yaml                   # App Platform App Spec; committed to source control
├── .github/
│   └── workflows/
│       ├── ci.yml             # Test + build; on pass, trigger App Platform deploy
│       └── app-deploy.yml     # doctl apps update --spec app.yaml (on merge to main)
├── .gitignore
└── README.md
```

Provide an `app.yaml` starter:

```yaml
name: my-app
region: nyc

services:
  - name: api
    github:
      repo: myorg/myrepo
      branch: main
      deploy_on_push: false   # Drive deploys from CI
    build_command: npm ci && npm run build
    run_command: node dist/server.js
    environment_slug: node-js
    instance_count: 2
    instance_size_slug: professional-xs
    http_port: 3000
    health_check:
      http_path: /healthz
      initial_delay_seconds: 10
    envs:
      - key: NODE_ENV
        value: production
        scope: RUN_TIME
        type: GENERAL
      - key: DATABASE_URL
        scope: RUN_TIME
        type: SECRET
        value: ""   # Set via: doctl apps update <id> --spec app.yaml
                    # or Control Panel; never commit the real value here

databases:
  - name: db
    engine: PG
    version: "16"
    size: db-s-1vcpu-1gb
    num_nodes: 1    # Increase to 2 for HA standby in production
    production: false   # Set to true in prod app.yaml
```

### Mixed (Terraform + App Spec)

```
.
├── infra/                     # Terraform for DOKS, VPC, Managed DB, etc.
│   ├── envs/dev/ stage/ prod/
│   └── modules/networking/ compute/ data/
├── apps/
│   ├── frontend/
│   │   └── app.yaml           # App Platform spec for the static frontend
│   └── api/
│       └── app.yaml           # App Platform spec for the API service
├── .github/
│   └── workflows/
│       ├── infra-plan.yml
│       ├── infra-apply.yml
│       └── app-deploy.yml
└── README.md
```

## GitHub Actions CI — reference

```yaml
# tf-plan.yml
name: Terraform Plan
on:
  pull_request:
    paths:
      - 'infra/**'

jobs:
  plan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: "1.8"

      - name: Install tflint
        run: curl -s https://raw.githubusercontent.com/terraform-linters/tflint/master/install_linux.sh | bash

      - name: Terraform Init
        working-directory: infra/envs/dev
        run: terraform init
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.SPACES_ACCESS_KEY }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.SPACES_SECRET_KEY }}

      - name: tflint
        working-directory: infra/envs/dev
        run: tflint --recursive

      - name: checkov IaC scan
        uses: bridgecrewio/checkov-action@v12
        with:
          directory: infra/
          framework: terraform

      - name: Terraform Plan
        working-directory: infra/envs/dev
        run: terraform plan -no-color -out=tfplan
        env:
          TF_VAR_do_token: ${{ secrets.DIGITALOCEAN_ACCESS_TOKEN }}

      - name: Post plan to PR
        uses: actions/github-script@v7
        with:
          script: |
            const output = `<details><summary>Terraform Plan</summary>\n\n\`\`\`\n${{ steps.plan.outputs.stdout }}\n\`\`\`\n</details>`;
            github.rest.issues.createComment({ issue_number: context.issue.number, owner: context.repo.owner, repo: context.repo.repo, body: output });
```

## After scaffolding

- Hand off to the `do-architect` sub-agent for a same-day review of the generated stack before the first `apply`.
- Recommend the user run `do-security-reviewer` once the first environment is deployed, before opening traffic to the internet.
- Remind that the DigitalOcean PAT stored in CI secrets must have an expiry date set and be rotated on a 30-day schedule.
- Note that Terraform state locking is not supported natively via the Spaces S3 backend. If multiple operators will run Terraform concurrently, evaluate HCP Terraform (free tier available) or Atlantis for locking.
