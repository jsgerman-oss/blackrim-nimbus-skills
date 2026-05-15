---
description: Scaffold a Linode Infrastructure-as-Code project — primary tool is Terraform (linode/linode provider); alternative is Ansible Linode collection. Generates production-grade defaults for networking, compute, firewalls, and state management.
argument-hint: <workload-description>
---

# Linode Scaffold IaC

Scaffold a new Linode Infrastructure-as-Code project for a workload described as: **$ARGUMENTS**

## What to do

1. **Confirm the tool choice.** Ask the user which IaC tool they want, with a one-line recommendation based on the workload description:
   - Deploying and managing Linode resources (instances, VPC, firewalls, databases, LKE) → **Terraform** with the `linode/linode` provider (>= 2.20). Best coverage, declarative, state-managed.
   - Team is already Ansible-heavy, or you need to combine provisioning with system configuration in one playbook → **Ansible** with the `linode.cloud` collection. Good for small fleets; less suited to complex dependency graphs.
   - Mixed: **Terraform** for infrastructure + **Ansible** for post-provision configuration. Recommended for most medium-to-large environments.
   Do not prescribe — recommend, then defer to the user.

2. **Confirm scope** with up to three questions if not obvious:
   - Which Linode region(s)? (Region is always explicit — no default assumed.)
   - New VPC, or connecting to an existing one?
   - Greenfield, or importing existing console-built resources?

3. **Generate the project skeleton** in the current working directory (or a subdirectory the user chooses). Every scaffold includes:
   - Pinned provider / collection version and a lockfile.
   - Per-environment separation (`dev`, `stage`, `prod`).
   - Remote state backend (Object Storage as S3 backend for Terraform, or Terraform Cloud).
   - A `.gitignore` for the tool.
   - A `README.md` with bootstrap + deploy / destroy commands.
   - At least one module: networking (VPC + Subnets + Cloud Firewall) + a compute placeholder + a state placeholder.
   - GitHub Actions CI with PAT secret for plan / apply, plus lint (`tflint` / `ansible-lint`).
   - Tagging strategy applied via a shared locals block or variable (`environment`, `service`, `owner`).

4. **Wire production-grade defaults.** For every scaffold:
   - VPC with private subnets; instances use VPC private IPs for inter-service communication.
   - Cloud Firewall with default-deny inbound; explicit allow rules for only required ports.
   - SSH key-only authentication; root login disabled in cloud-init `user_data`.
   - Linode Backups enabled on all stateful instances (`backups_enabled = true`).
   - Object Storage buckets default private (`acl = "private"`).
   - `prevent_destroy = true` in `lifecycle` blocks for Managed Databases and production Volumes.
   - `LINODE_TOKEN` sourced from environment variable, not hard-coded in any file.
   - Log group / retention for any managed logging (handled in application layer — Linode has no managed log service).

5. **Print next steps** — bootstrap commands the user must run (`terraform init`, `ansible-galaxy collection install linode.cloud`, etc.) plus an explicit reminder that the first apply should target `dev`, not `prod`.

## Tool-specific layouts

### Terraform (HCL) — primary

```
.
├── envs/
│   ├── dev/
│   │   ├── backend.tf           # Object Storage S3 backend, or Terraform Cloud
│   │   ├── main.tf              # Module instantiation for dev
│   │   ├── terraform.tfvars     # Non-secret var overrides for dev
│   │   └── outputs.tf
│   ├── stage/...
│   └── prod/...
├── modules/
│   ├── networking/
│   │   ├── main.tf              # linode_vpc, linode_vpc_subnet, linode_firewall
│   │   ├── variables.tf
│   │   └── outputs.tf
│   ├── compute/
│   │   ├── main.tf              # linode_instance (with backups, cloud-init user_data)
│   │   ├── variables.tf
│   │   └── outputs.tf
│   └── database/
│       ├── main.tf              # linode_database_postgresql (HA, prevent_destroy)
│       ├── variables.tf
│       └── outputs.tf
├── .terraform.lock.hcl
├── .gitignore
├── .github/workflows/
│   ├── tf-plan.yml              # PR: validate + plan, post plan as comment
│   ├── tf-apply-dev.yml         # Push to dev: auto-apply
│   ├── tf-apply-prod.yml        # Manual workflow_dispatch: apply prod
│   └── drift-check.yml          # Scheduled: terraform plan -refresh-only
└── README.md
```

Key Terraform provider block:

```hcl
terraform {
  required_version = ">= 1.6"
  required_providers {
    linode = {
      source  = "linode/linode"
      version = ">= 2.20"
    }
  }
}

provider "linode" {
  # Token sourced from LINODE_TOKEN environment variable — do not set here.
}
```

State backend (Linode Object Storage as S3-compatible backend):

```hcl
terraform {
  backend "s3" {
    bucket                      = "my-tf-state"
    key                         = "prod/terraform.tfstate"
    region                      = "us-east-1"   # ignored by Linode; placeholder required
    endpoint                    = "us-southeast-1.linodeobjects.com"
    access_key                  = "<from secrets manager>"
    secret_key                  = "<from secrets manager>"
    skip_credentials_validation = true
    skip_metadata_api_check     = true
    skip_region_validation      = true
    force_path_style            = true
  }
}
```

### Ansible — alternative

```
.
├── inventories/
│   ├── dev/
│   │   ├── hosts.yml            # Dynamic inventory from linode.cloud.instance_info
│   │   └── group_vars/
│   ├── stage/...
│   └── prod/...
├── playbooks/
│   ├── provision.yml            # Provision instances, VPC, firewall via linode.cloud modules
│   ├── configure.yml            # Post-provision: OS hardening, app install
│   └── teardown.yml             # Destroy resources (run manually only)
├── roles/
│   ├── linode_instance/
│   ├── linode_firewall/
│   └── os_harden/               # Disable root SSH, enable key-only auth, install updates
├── requirements.yml             # linode.cloud collection pin
├── ansible.cfg
├── .gitignore
├── .github/workflows/
│   ├── lint.yml                 # ansible-lint on PR
│   └── deploy-dev.yml           # Push to dev branch: provision + configure dev
└── README.md
```

`requirements.yml`:

```yaml
collections:
  - name: linode.cloud
    version: ">=0.15.0"
```

### Terraform + Ansible (recommended for medium/large environments)

Combine both layouts above. Terraform manages all Linode resources. After `terraform apply`, an Ansible playbook uses the Terraform outputs (instance IPs, database endpoints) as its inventory source. The CI/CD pipeline runs Terraform first, then Ansible.

## Cloud Firewall defaults in the scaffold

Every scaffold generates a Cloud Firewall module with these opinionated rules as a starting point:

```hcl
resource "linode_firewall" "main" {
  label = "${var.service}-${var.environment}"

  inbound_policy  = "DROP"   # deny-unmatched inbound
  outbound_policy = "ACCEPT" # allow-unmatched outbound

  inbound {
    label    = "allow-ssh-management"
    action   = "ACCEPT"
    protocol = "TCP"
    ports    = "22"
    ipv4     = [var.management_cidr]  # NOT 0.0.0.0/0
  }

  inbound {
    label    = "allow-app-https"
    action   = "ACCEPT"
    protocol = "TCP"
    ports    = "443"
    ipv4     = ["0.0.0.0/0"]
    ipv6     = ["::/0"]
  }
}
```

The user adds additional rules for their service ports. The scaffold does NOT open 80, 3306, 5432, 6379, 27017, or any other port by default.

## After scaffolding

- Hand off to the `linode-architect` sub-agent for a review of the generated IaC before the first `apply`.
- Recommend the user run `linode-security-reviewer` once the dev environment is up, before allowing production traffic.
- Remind the user that the Linode Manager account owner MFA, named restricted users, and PAT creation are one-time account-level steps that IaC cannot automate — document them in the project README under "Account Bootstrap."
- For LKE workloads: deploy the nginx ingress controller via Helm after cluster creation so there is one NodeBalancer for all HTTP(S) services.
