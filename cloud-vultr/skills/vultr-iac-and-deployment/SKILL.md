---
name: vultr-iac-and-deployment
description: Choose, scaffold, or review Vultr Infrastructure-as-Code and deployment — vultr-cli (vultr CLI), Terraform vultr/vultr provider, Packer Vultr plugin, Ansible inventory plugin, cloud-init, GitHub Actions deploy, snapshot lifecycle. Use when starting a new IaC project for Vultr, designing a deployment pipeline, or auditing an existing IaC repo for drift and security posture.
---

# Vultr Infrastructure-as-Code and Deployment

## When to use

- Greenfield project — picking an IaC tool for Vultr.
- Automating Vultr instance lifecycle (create, configure, snapshot, destroy) via CI/CD.
- Building an image pipeline with Packer + Vultr.
- Designing a deployment pipeline for an application on Vultr Cloud Compute or VKE.
- Hardening a release process with safe defaults and rollback paths.
- Auditing an existing Vultr IaC repo for drift, secrets exposure, or missing defaults.

## IaC tool selection

| Tool | Pick when |
| --- | --- |
| **Terraform / OpenTofu + `vultr/vultr` provider** | Primary IaC choice for Vultr. Multi-provider (Cloudflare DNS + GitHub + Vultr), version-controlled state, large community, best coverage of Vultr resource types. |
| **`vultr-cli`** | Ad-hoc operations, scripted one-offs, CI steps where Terraform is not set up. Not a substitute for declarative IaC — instance state managed via CLI is not tracked and drifts. |
| **Ansible + Vultr inventory plugin** | Config management on running instances (OS hardening, software deploy, service configuration). Complements Terraform (provision infra) + Ansible (configure OS). |
| **Packer + Vultr plugin** | Building custom OS images (hardened, pre-configured). Produce a Vultr snapshot ID that Terraform references as the `os_id` for consistent instance provisioning. |

Avoid mixing Terraform and `vultr-cli` for the same resources — Terraform state becomes stale.

## Terraform — the primary path

### Provider setup

```hcl
terraform {
  required_providers {
    vultr = {
      source  = "vultr/vultr"
      version = ">= 2.21.0"
    }
  }
  required_version = ">= 1.6.0"
}

provider "vultr" {
  api_key     = var.vultr_api_key
  rate_limit  = 700   # ms between API calls; Vultr rate limit is ~2 req/s
  retry_limit = 3
}
```

- Never hard-code the API key. Use a `TF_VAR_vultr_api_key` environment variable or a secrets manager lookup (`vault_generic_secret`, `aws_secretsmanager_secret_version`, etc.).
- Set `rate_limit` to 700 ms or higher for large applies — Vultr API rate limits cause 429 errors without backoff.

### State management

- Remote state backend: Vultr has no managed Terraform state service. Use Terraform Cloud, HCP Terraform, AWS S3 + DynamoDB lock table, or a self-hosted MinIO instance on Vultr Object Storage (`vultr_object_storage` bucket as an S3-compatible backend).
- **Object Storage as Terraform backend:**
  ```hcl
  backend "s3" {
    bucket                      = "terraform-state-prod"
    key                         = "infra/terraform.tfstate"
    region                      = "us-east-1"   # placeholder — Vultr ignores region
    endpoint                    = "https://ewr1.vultrobjects.com"
    skip_credentials_validation = true
    skip_metadata_api_check     = true
    skip_region_validation      = true
    force_path_style            = true
  }
  ```
- One state file per environment (`dev`, `stage`, `prod`). Never share state between environments.
- Stateful resources (Block Storage, Managed Databases) in a separate Terraform workspace or module from compute — prevents accidental destroy during a compute-only apply.

### Module hygiene

- Use `vultr/vultr` provider data sources (`data "vultr_plan"`, `data "vultr_region"`, `data "vultr_os"`) to look up valid slugs rather than hard-coding opaque IDs.
- Structure modules by concern: `modules/network` (VPC 2.0, Firewall Groups), `modules/compute` (instance + startup script + snapshot), `modules/databases` (Managed DB, Block Storage).
- Pin the provider: `version = ">= 2.21.0, < 3.0.0"`. Check the `vultr/vultr` provider changelog before upgrading major versions.
- Lockfile (`terraform.lock.hcl`) committed to source control.

### Key resources reference

| Resource | Purpose |
| --- | --- |
| `vultr_instance` | Cloud Compute instance |
| `vultr_bare_metal_server` | Bare Metal instance |
| `vultr_kubernetes` | VKE cluster |
| `vultr_node_pool` | VKE node pool |
| `vultr_vpc2` | VPC 2.0 network |
| `vultr_firewall_group` | Firewall Group |
| `vultr_firewall_rule` | Individual firewall rule |
| `vultr_load_balancer` | Regional Load Balancer |
| `vultr_reserved_ip` | Static public IP |
| `vultr_block_storage` | Block Storage volume |
| `vultr_database` | Managed Database (Postgres, MySQL, Redis, Kafka) |
| `vultr_object_storage` | Object Storage cluster |
| `vultr_ssh_key` | SSH public key at account level |
| `vultr_startup_script` | Instance startup script |
| `vultr_snapshot` | Manual instance snapshot |
| `vultr_dns_domain` | DNS zone |
| `vultr_dns_record` | DNS record |

## `vultr-cli` — command reference for key operations

```bash
# Instance lifecycle
vultr-cli instance list --output json
vultr-cli instance create --region ewr --plan vc2-2c-4gb --os 1743 --label prod-web-01 \
  --ssh-key-id <key-id> --firewall-group-id <fg-id> --vpc2-id <vpc-id> \
  --ddos-protection=true --backups=enabled
vultr-cli instance destroy <id>

# Snapshots
vultr-cli snapshot list --output json
vultr-cli snapshot create --id <instance-id> --description "pre-deploy $(date +%Y%m%d)"

# Managed Databases
vultr-cli database list --output json
vultr-cli database create --database-engine pg --database-engine-version 16 \
  --region ewr --plan vultr-dbaas-hobbyist-cc-1-25-1 --label prod-db

# Bandwidth / billing
vultr-cli billing bandwidth
```

## cloud-init and startup scripts

- Use cloud-init (via `user_data` on `vultr_instance`) for OS-level idempotent setup: package installation, user creation, SSH hardening, hostname, NTP.
- Use Vultr Startup Scripts (`vultr_startup_script`) for provisioner-run scripts that are stored in the Vultr account and reusable across instances.
- cloud-init and startup scripts are **not secrets managers**. Do not write API keys, database passwords, or SSH private keys into either. Pull secrets from Object Storage (pre-signed URL), a secrets manager endpoint, or inject via Terraform `sensitive` output.

### Minimal cloud-init security hardening

```yaml
#cloud-config
package_update: true
packages:
  - ufw
  - fail2ban
runcmd:
  - sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
  - sed -i 's/^#*PermitRootLogin.*/PermitRootLogin prohibit-password/' /etc/ssh/sshd_config
  - systemctl reload ssh
  - ufw default deny incoming
  - ufw default allow outgoing
  - ufw allow from <management-cidr> to any port 22
  - ufw --force enable
  - systemctl enable fail2ban
```

## Packer — image pipeline

Use the Packer `vultr` plugin to build hardened OS images stored as Vultr snapshots.

```hcl
packer {
  required_plugins {
    vultr = {
      version = ">= 2.6.0"
      source  = "github.com/vultr/vultr"
    }
  }
}

source "vultr" "base" {
  api_key             = var.vultr_api_key
  os_id               = "2284"          # Debian 12
  plan_id             = "vc2-1c-1gb"
  region_id           = "ewr"
  snapshot_description = "hardened-base-${formatdate("YYYYMMDD", timestamp())}"
  ssh_username        = "root"
}

build {
  sources = ["source.vultr.base"]
  provisioner "shell" {
    script = "scripts/harden.sh"
  }
}
```

- Store the resulting snapshot ID in Terraform remote state or a parameter store so Terraform's `vultr_instance` can reference it via `os_id`.
- Rebuild images on a regular cadence (monthly minimum) to pick up OS security patches.

## Ansible — configuration management

Use Ansible for OS-level configuration that changes independently of infrastructure provisioning.

- The `vultr.cloud` Ansible collection provides dynamic inventory (`vultr.cloud.vultr`) that reads instance metadata from the Vultr API.
- Configure inventory: set `VULTR_API_KEY` environment variable; Ansible fetches instance list and groups by label, region, and tag.

```ini
# ansible.cfg
[inventory]
enable_plugins = vultr.cloud.vultr

[defaults]
inventory = inventory/vultr.yaml
remote_user = root
private_key_file = ~/.ssh/id_ed25519
```

- Separate Ansible playbooks from Terraform IaC in the repo (`terraform/` vs `ansible/`). Terraform provisions; Ansible configures. Do not use Terraform `local-exec` provisioners as a substitute for Ansible.

## CI/CD pipeline — GitHub Actions

### Authentication

- Store the Vultr API key in GitHub Actions Secrets (`VULTR_API_KEY`). Do not hard-code it.
- For Terraform remote state on Vultr Object Storage, also store `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` (the Object Storage S3 credentials).

### Pipeline stages

1. **Lint:** `terraform fmt -check`, `tflint`, `tfsec` or `trivy config` (for IaC security scanning), `ansible-lint`.
2. **Validate:** `terraform validate`.
3. **Plan:** `terraform plan -out=tfplan` — post the plan output as a PR comment.
4. **Apply (dev/stage):** Auto-apply on merge to `develop` or `staging` branch.
5. **Apply (prod):** Manual approval gate via GitHub Actions `environment: production` with required reviewers.
6. **Snapshot (pre-deploy):** Take a `vultr-cli snapshot create` before applying a production change as a rollback point.
7. **Drift detection:** Scheduled `terraform plan -refresh-only` on a cron — alert on any diff.

### Deployment patterns for app code

| Pattern | How to implement on Vultr |
| --- | --- |
| Blue/green | Provision a new instance set from a fresh snapshot; swing the Load Balancer backend pool; destroy old pool. |
| Rolling | Use Ansible `serial` to update instances one at a time; health-check between each. |
| Immutable (recommended) | Packer → snapshot → Terraform replace. New instance from the new snapshot; old instance destroyed. |
| VKE rolling | Standard Kubernetes Deployment rolling update; no special Vultr config needed. |

Immutable deployments (Packer + snapshot) are the safest pattern for Vultr Cloud Compute — they eliminate configuration drift and produce a testable artifact before the instance ever runs in production.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| `vultr-cli` for production provisioning, Terraform for IaC | State diverges. Terraform destroys resources it doesn't recognize, or ignores resources created by CLI. One tool per resource. |
| API key hard-coded in `terraform.tfvars` committed to git | Keys leak via git history. Use environment variable or secrets manager lookup. |
| Single state file for dev + prod | A plan targeting dev can accidentally affect prod resources in the same state. Per-environment state isolation. |
| `terraform apply` from a developer laptop to prod | No audit trail, no lock, race condition with CI. Pipeline-only applies for production. |
| Startup script that installs packages without pinned versions | `apt install nginx` installs whatever is latest — breaks idempotency and reproducibility. Pin versions or use a Packer image. |
| No snapshot before a prod apply | Rollback after a bad apply requires rebuilding from the last backup. Take a pre-apply snapshot for a 5-minute rollback. |
| VKE manifest changes applied with `kubectl apply` directly to prod | No review, no audit, no rollback path. Use GitOps (Argo CD, Flux) with PR-gated changes. |
| Manual Ansible runs against production | SSH into prod and run Ansible = no review, no log, no idempotency guarantee. Use CI-driven Ansible runs only. |

## Security defaults

- Terraform API key from environment variable or secrets manager; never in VCS.
- Remote state encrypted (Vultr Object Storage uses server-side encryption; verify TLS on the endpoint).
- Per-environment state isolation.
- IaC linting (`tfsec` / `trivy config`) in CI; gate PR merges on lint pass.
- All Vultr resources tagged with `environment`, `service`, `owner` labels (Vultr labels) for cost and audit attribution.
- Startup scripts reviewed in PR like application code — they run as root on first boot.

## Observability hints

- Tag every Vultr resource with `environment`, `service`, `owner` via the `label` map on `vultr_instance`, `vultr_database`, etc. This enables filtering in the Vultr control panel and cost reports.
- Deploy infrastructure: emit a `deploy_marker` annotation to your observability backend (Grafana annotation, Datadog event) from the CI pipeline on successful apply. Correlate deploy events with metrics changes.
- DORA metrics: track deployment frequency, lead time for changes, change failure rate, and MTTR in your CI system (GitHub Actions metrics, LinearB, etc.).

## Verification checklist

- [ ] Terraform provider pinned to `vultr/vultr` ≥ 2.21, Terraform ≥ 1.6.
- [ ] Remote state backend configured, encrypted, per-environment.
- [ ] API key from environment variable or secrets manager; not in any file committed to VCS.
- [ ] IaC linting (`tfsec` / `trivy config` + `tflint`) in CI; PRs blocked on failures.
- [ ] Plan posted on PR before apply; human review required for prod.
- [ ] Pre-apply snapshot taken before any production `terraform apply`.
- [ ] Startup scripts version-controlled and reviewed in PR like application code.
- [ ] Packer image pipeline in place for stateful instance types; image rebuilt monthly.
- [ ] Ansible inventory uses `vultr.cloud.vultr` dynamic inventory; no static host files.
- [ ] All resources labeled (`environment`, `service`, `owner`).
- [ ] Drift detection running on a schedule; alert on non-empty plan output.
