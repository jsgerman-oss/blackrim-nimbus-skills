---
description: Scaffold a Vultr Infrastructure-as-Code project — primary IaC is Terraform with the vultr/vultr provider; alt is Ansible for OS configuration management. Opinionated production-grade defaults throughout.
argument-hint: <workload-description>
---

# Vultr Scaffold IaC

Scaffold a new Vultr Infrastructure-as-Code project for a workload described as: **$ARGUMENTS**

## What to do

1. **Confirm the tool split.** Vultr IaC has two layers — recommend the right combination:
   - **Terraform (`vultr/vultr` provider ≥ 2.21):** Provision all Vultr infrastructure (instances, databases, networking, storage). Primary choice for all new projects.
   - **Ansible (`vultr.cloud` collection):** OS configuration management — package installation, service hardening, application deployment. Complements Terraform; does not replace it.
   - **`vultr-cli`:** Ad-hoc operations only; not for tracked infrastructure. Suggest its use for one-off queries and inspection during development.
   - **Packer (Vultr plugin):** If the workload benefits from a hardened custom OS image (stateful servers, GPU workloads with preloaded model weights, custom kernel), recommend adding a Packer pipeline.

   Do not prescribe — recommend based on the workload description, then defer to the user.

2. **Confirm scope** with up to three questions if not obvious:
   - Target region(s) and environment split (dev / stage / prod)?
   - Network: new VPC 2.0, or attach to an existing one?
   - State: greenfield, or migrating from console-built resources (import vs greenfield)?

3. **Generate the project skeleton** in the current working directory (or a subdirectory the user picks). Every scaffold must include:
   - Provider pinned to `vultr/vultr` ≥ 2.21 and Terraform ≥ 1.6, with a lockfile.
   - Per-environment separation (`dev`, `stage`, `prod`).
   - Remote state on Vultr Object Storage (S3-compatible backend) — includes instructions for initial bucket creation via `vultr-cli`.
   - A `.gitignore` for Terraform (`.terraform/`, `*.tfstate`, `*.tfstate.backup`, `*.tfplan`, `*.tfvars`).
   - A `README.md` with bootstrap + deploy / destroy commands.
   - At least one stack: networking (VPC 2.0 + Firewall Groups) + a compute placeholder + a state placeholder.
   - GitHub Actions CI with Vultr API key from secrets, plus lint (`tflint`, `trivy config`) and plan/apply stages.
   - Labels applied to every resource (`environment`, `service`, `owner`) for cost attribution.

4. **Wire safe defaults.** For every scaffold:
   - VPC 2.0 network created; all instances attached; public IPs removed from back-of-house instances.
   - Firewall Groups with default-deny inbound, created at the same time as instances (via `depends_on`).
   - DDoS Protection enabled on all public-facing instances (`ddos_protection = true`).
   - SSH key-only auth enforced via cloud-init (password auth disabled).
   - Backups enabled on stateful instances.
   - Managed Databases with HA mode on for any prod environment.
   - Object Storage buckets with private ACL by default.
   - API key passed via environment variable (`TF_VAR_vultr_api_key`); never in a committed file.

5. **Print next steps** — bootstrap commands the user must run, plus explicit reminders:
   - First apply must target `dev`, not `prod`.
   - The Vultr API key must be set before any `terraform` command.
   - After scaffolding, hand off to `vultr-architect` for a review of the generated stack.

## Tool-specific layouts

### Terraform + Ansible (recommended for most workloads)

```
.
├── terraform/
│   ├── modules/
│   │   ├── network/
│   │   │   ├── main.tf         # vultr_vpc2, vultr_firewall_group, vultr_firewall_rule
│   │   │   ├── variables.tf
│   │   │   └── outputs.tf
│   │   ├── compute/
│   │   │   ├── main.tf         # vultr_instance, vultr_startup_script, vultr_ssh_key ref
│   │   │   ├── variables.tf
│   │   │   └── outputs.tf
│   │   └── data/
│   │       ├── main.tf         # vultr_database, vultr_block_storage, vultr_object_storage
│   │       ├── variables.tf
│   │       └── outputs.tf
│   ├── envs/
│   │   ├── dev/
│   │   │   ├── backend.tf      # S3-compatible backend → Vultr Object Storage
│   │   │   ├── main.tf         # Module instantiation, dev-specific vars
│   │   │   ├── terraform.tfvars
│   │   │   └── outputs.tf
│   │   ├── stage/
│   │   │   └── ...
│   │   └── prod/
│   │       └── ...
│   ├── .terraform.lock.hcl
│   └── .gitignore
├── ansible/
│   ├── inventory/
│   │   └── vultr.yaml          # vultr.cloud.vultr dynamic inventory
│   ├── playbooks/
│   │   ├── harden.yml          # OS hardening: ufw, fail2ban, SSH config
│   │   ├── deploy.yml          # Application deploy
│   │   └── update.yml          # OS package updates
│   ├── roles/
│   │   └── common/             # Shared OS config role
│   ├── ansible.cfg
│   └── requirements.yml        # vultr.cloud collection
├── .github/
│   └── workflows/
│       ├── tf-lint.yml         # tflint + trivy config on PR
│       ├── tf-plan.yml         # terraform plan, post as PR comment
│       ├── tf-apply.yml        # terraform apply on merge (dev/stage auto, prod manual)
│       └── ansible-deploy.yml  # Ansible deploy on release tag
└── README.md
```

### Terraform-only (simple workload, no per-instance OS configuration)

```
.
├── main.tf                     # All resources (small projects)
├── variables.tf
├── outputs.tf
├── backend.tf
├── terraform.tfvars.example    # Never commit actual tfvars with secrets
├── .terraform.lock.hcl
├── .github/
│   └── workflows/
│       ├── tf-lint.yml
│       ├── tf-plan.yml
│       └── tf-apply.yml
└── README.md
```

### VKE (Kubernetes) workload

```
.
├── terraform/
│   ├── main.tf                 # vultr_kubernetes, vultr_node_pool, vultr_vpc2
│   ├── variables.tf
│   ├── outputs.tf              # kubeconfig output (sensitive = true)
│   ├── backend.tf
│   └── .terraform.lock.hcl
├── kubernetes/
│   ├── namespaces/
│   ├── ingress/                # Ingress controller (NGINX or Traefik)
│   ├── monitoring/             # kube-prometheus-stack Helm values
│   └── apps/                   # Application Helm charts / manifests
├── .github/
│   └── workflows/
│       ├── tf-plan.yml
│       ├── tf-apply.yml
│       └── k8s-deploy.yml      # kubectl apply / helm upgrade
└── README.md
```

## Core Terraform snippets — wire these in every scaffold

### Provider and backend

```hcl
# terraform/envs/prod/backend.tf
terraform {
  backend "s3" {
    bucket                      = "terraform-state-<project>-prod"
    key                         = "terraform.tfstate"
    region                      = "us-east-1"
    endpoint                    = "https://ewr1.vultrobjects.com"
    access_key                  = var.object_storage_access_key
    secret_key                  = var.object_storage_secret_key
    skip_credentials_validation = true
    skip_metadata_api_check     = true
    skip_region_validation      = true
    force_path_style            = true
  }
}
```

### Network module — VPC 2.0 + Firewall Group

```hcl
resource "vultr_vpc2" "main" {
  description    = "${var.environment}-vpc"
  region         = var.region
  ip_block       = "10.0.0.0"
  prefix_length  = 24
}

resource "vultr_firewall_group" "web" {
  description = "${var.environment}-web-tier"
}

resource "vultr_firewall_rule" "https" {
  firewall_group_id = vultr_firewall_group.web.id
  protocol          = "tcp"
  ip_type           = "v4"
  subnet            = "0.0.0.0"
  subnet_size       = 0
  port              = "443"
  notes             = "HTTPS from internet"
}

resource "vultr_firewall_rule" "https_v6" {
  firewall_group_id = vultr_firewall_group.web.id
  protocol          = "tcp"
  ip_type           = "v6"
  subnet            = "::"
  subnet_size       = 0
  port              = "443"
  notes             = "HTTPS from internet (IPv6)"
}

resource "vultr_firewall_rule" "ssh" {
  firewall_group_id = vultr_firewall_group.web.id
  protocol          = "tcp"
  ip_type           = "v4"
  subnet            = var.management_cidr
  subnet_size       = tonumber(split("/", var.management_cidr)[1])
  port              = "22"
  notes             = "SSH from management CIDR only"
}
```

### Compute module — instance with safe defaults

```hcl
resource "vultr_startup_script" "harden" {
  name   = "${var.environment}-harden"
  type   = "boot"
  script = base64encode(file("${path.module}/scripts/harden.sh"))
}

resource "vultr_instance" "app" {
  plan              = var.plan            # e.g. "vhp-2c-4gb"
  region            = var.region
  os_id             = var.os_id          # Debian 12 = 2284
  label             = "${var.environment}-app-01"
  firewall_group_id = vultr_firewall_group.web.id
  ssh_key_ids       = var.ssh_key_ids
  startup_id        = vultr_startup_script.harden.id
  vpc2_ids          = [vultr_vpc2.main.id]
  enable_ipv6       = true
  ddos_protection   = true
  backups           = var.environment == "prod" ? "enabled" : "disabled"

  user_data = base64encode(templatefile("${path.module}/cloud-init.yaml", {
    management_cidr = var.management_cidr
  }))

  tags = ["${var.environment}", "${var.service}", "${var.owner}"]
}
```

## After scaffolding

- Hand off to the `vultr-architect` sub-agent for a same-day review of the generated stack before the first `apply`.
- Run `vultr-security-reviewer` once the first environment is deployed and before accepting production traffic.
- Pre-apply snapshot: before every production `terraform apply`, run:
  ```bash
  vultr-cli snapshot create --id <instance-id> --description "pre-deploy-$(date +%Y%m%d-%H%M)"
  ```
- Remind that the Object Storage bucket for Terraform state must be created manually (via `vultr-cli` or the control panel) before `terraform init -backend-config=...` will work — Terraform cannot create its own state bucket.

## Bootstrap commands (run once, in order)

```bash
# 1. Install tools
brew install terraform tflint vultr-cli
pip install ansible

# 2. Install Ansible Vultr collection
ansible-galaxy collection install vultr.cloud

# 3. Set credentials (never commit these)
export VULTR_API_KEY="your-api-key-here"
export TF_VAR_vultr_api_key="$VULTR_API_KEY"

# 4. Create Terraform state bucket (one-time, before terraform init)
vultr-cli object-storage create --label terraform-state --cluster-id 2
# Note the S3 credentials from the output; set as TF_VAR_object_storage_access_key / secret_key

# 5. Initialize Terraform
cd terraform/envs/dev
terraform init -backend-config="access_key=$TF_VAR_object_storage_access_key" \
               -backend-config="secret_key=$TF_VAR_object_storage_secret_key"

# 6. Plan and review before applying
terraform plan -out=tfplan
terraform show tfplan   # Review before applying

# 7. Apply to dev first
terraform apply tfplan
```
