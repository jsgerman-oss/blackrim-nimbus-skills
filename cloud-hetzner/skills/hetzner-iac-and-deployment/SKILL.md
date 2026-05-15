---
name: hetzner-iac-and-deployment
description: Choose, scaffold, or review Hetzner Infrastructure-as-Code and deployment — hcloud CLI, Terraform hetznercloud/hcloud provider (≥ 1.48), Ansible hetzner.hcloud collection, Packer for image baking, cloud-init for bootstrap, snapshot-as-golden-image pattern, GitHub Actions deploy with token from secrets. Use when starting a new IaC project, picking a tool, or hardening a release path for Hetzner infrastructure.
---

# Hetzner Infrastructure-as-Code and Deployment

## When to use

- Greenfield Hetzner project — picking an IaC tool.
- Codifying console-built Hetzner infrastructure.
- Designing a CI/CD pipeline for Hetzner server provisioning and app deployment.
- Baking server images with Packer for reproducible deployments.
- Bootstrapping servers with cloud-init.
- Reviewing an existing IaC repo for drift, secret hygiene, and state management.

## IaC tool — picking one

| Tool | Pick when |
| --- | --- |
| **Terraform / OpenTofu + hetznercloud/hcloud** | Primary choice for any new Hetzner project. Best community support, full resource coverage (Cloud and partial Robot), composable with other providers (Cloudflare DNS, GitHub). |
| **Ansible + hetzner.hcloud collection** | You already use Ansible for configuration management; Ansible can provision Hetzner servers and configure them in the same playbook. |
| **Pulumi + hcloud SDK** | Team prefers a real programming language over HCL; Pulumi's `@pulumi/hcloud` package covers Cloud resources. |
| **hcloud CLI + shell scripts** | Acceptable for single-server dev environments or one-off automation; not a production IaC strategy. |

Mixed approach: Terraform for server and network provisioning; Ansible for OS configuration, package installation, and service deployment. This is the most common pattern in Hetzner deployments.

## Terraform + hetznercloud/hcloud

Provider version: `hetznercloud/hcloud` ≥ 1.48.

Provider configuration:

```hcl
terraform {
  required_providers {
    hcloud = {
      source  = "hetznercloud/hcloud"
      version = ">= 1.48, < 2.0"
    }
  }

  backend "s3" {
    # Use Hetzner-compatible S3 (e.g., Cloudflare R2, Minio, Backblaze B2)
    # or a self-hosted Minio instance for remote state.
    bucket   = "tf-state"
    key      = "hetzner/prod/terraform.tfstate"
    region   = "auto"
    endpoint = "https://<account>.r2.cloudflarestorage.com"
    # Credentials via AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY env vars
  }
}

provider "hcloud" {
  token = var.hetzner_token  # passed via TF_VAR_hetzner_token
}
```

Note: Hetzner has no native Terraform state backend. Use an S3-compatible object store (Cloudflare R2 is free for state files; Backblaze B2 is cheap). Do not use local state for anything beyond experimentation.

Core resources:

| Resource | Purpose |
| --- | --- |
| `hcloud_server` | Cloud server provisioning |
| `hcloud_server_network` | Attaches a server to a Private Network |
| `hcloud_network` / `hcloud_network_subnet` | Private Network and subnet definition |
| `hcloud_load_balancer` | Load Balancer creation |
| `hcloud_load_balancer_service` | LB protocol, health check, TLS config |
| `hcloud_load_balancer_target` | Adds server or label-selector targets to LB |
| `hcloud_firewall` | Cloud Firewall definition |
| `hcloud_firewall_attachment` | Applies firewall to servers or label selectors |
| `hcloud_ssh_key` | Registers an SSH public key |
| `hcloud_volume` | Block storage volume |
| `hcloud_volume_attachment` | Attaches a volume to a server |
| `hcloud_placement_group` | Anti-affinity spread group |
| `hcloud_floating_ip` | Static public IP |
| `hcloud_managed_certificate` | Let's Encrypt certificate managed by Hetzner |
| `hcloud_rdns` | Reverse DNS PTR record |

State management for Hetzner:

- No native DynamoDB-equivalent for state locking. Cloudflare R2 supports S3-compatible locking via DynamoDB-emulation only through some backends. Use Terraform Cloud or a self-hosted Minio with the HTTP backend for proper locking if multiple team members run Terraform concurrently.
- One state file per environment (dev, staging, prod).
- Enable `prevent_destroy = true` on `hcloud_server` and `hcloud_volume` resources in prod.

## Ansible + hetzner.hcloud collection

Install: `ansible-galaxy collection install hetzner.hcloud`.

The `hetzner.hcloud` collection provides:

- `hetzner.hcloud.hcloud_server` — provision and manage Cloud servers.
- `hetzner.hcloud.hcloud_network` — Private Networks.
- `hetzner.hcloud.hcloud_firewall` — Cloud Firewalls.
- `hetzner.hcloud.hcloud_load_balancer` — Load Balancers.
- `hetzner.hcloud.hcloud_volume` — Block storage volumes.
- `hetzner.hcloud.hcloud_ssh_key` — SSH key registration.
- `hetzner.hcloud.hcloud_inventory` — Dynamic inventory plugin to populate Ansible groups from Hetzner Cloud server labels.

Dynamic inventory example (`hcloud.yml`):

```yaml
plugin: hetzner.hcloud.hcloud
token: "{{ lookup('env', 'HCLOUD_TOKEN') }}"
groups:
  web: "'env=prod' in (server_labels | dict2items | map(attribute='value'))"
  db:  "'role=db' in (server_labels | dict2items | map(attribute='value'))"
```

Typical playbook pattern (provision + configure):

```yaml
- name: Provision web servers
  hosts: localhost
  tasks:
    - name: Create server
      hetzner.hcloud.hcloud_server:
        name: web-01
        server_type: cpx31
        image: ubuntu-24.04
        location: nbg1
        ssh_keys:
          - deploy-2026
        labels:
          env: prod
          role: web
        state: present
      register: server

- name: Configure web servers
  hosts: hcloud_server_type_cpx31
  gather_facts: true
  roles:
    - common
    - nginx
```

## cloud-init for server bootstrap

cloud-init runs on first boot and is the standard mechanism for injecting SSH keys, creating users, disabling password auth, and installing base packages. Hetzner passes cloud-init config via the `user_data` field on server creation.

Best practice: keep cloud-init minimal — SSH key injection, user creation, basic hardening. Delegate configuration management to Ansible or your CM tool after the server is reachable.

```yaml
#cloud-config
users:
  - name: deploy
    groups: sudo
    sudo: ['ALL=(ALL) NOPASSWD:ALL']
    shell: /bin/bash
    ssh_authorized_keys:
      - ssh-ed25519 AAAA... deploy-key-2026

ssh_pwauth: false
disable_root: true

packages:
  - curl
  - git
  - fail2ban

runcmd:
  - systemctl enable fail2ban
  - systemctl start fail2ban
```

In Terraform:

```hcl
resource "hcloud_server" "web" {
  name        = "web-01"
  server_type = "cpx31"
  image       = "ubuntu-24.04"
  location    = "nbg1"
  ssh_keys    = [hcloud_ssh_key.deploy.id]
  user_data   = file("${path.module}/cloud-init.yml")
}
```

## Packer — server image baking

The snapshot-as-golden-image pattern bakes a configured server image (analogous to an AMI) for fast, reproducible provisioning.

Install the Hetzner Packer plugin: `packer plugins install github.com/hetznercloud/hcloud`.

Packer template (`hetzner.pkr.hcl`):

```hcl
packer {
  required_plugins {
    hcloud = {
      source  = "github.com/hetznercloud/hcloud"
      version = ">= 1.4"
    }
  }
}

variable "hcloud_token" {
  type      = string
  sensitive = true
}

source "hcloud" "base" {
  token         = var.hcloud_token
  server_type   = "cx22"
  image         = "ubuntu-24.04"
  location      = "nbg1"
  snapshot_name = "app-base-{{ timestamp }}"
  ssh_username  = "root"
}

build {
  sources = ["source.hcloud.base"]

  provisioner "ansible" {
    playbook_file = "./playbooks/base.yml"
  }

  post-processor "manifest" {
    output     = "packer-manifest.json"
    strip_path = true
  }
}
```

After a build:

1. Read the snapshot ID from `packer-manifest.json`.
2. Pass it to Terraform as `image = <snapshot-id>`.
3. New servers provision from the baked snapshot — faster than running full Ansible post-boot.

## CI/CD pipeline

### Authentication — GitHub Actions

Store the Hetzner API token as a GitHub Actions secret (`HCLOUD_TOKEN`) and pass it as an environment variable. Do not commit tokens to IaC files.

```yaml
# .github/workflows/tf-apply.yml
name: Terraform apply
on:
  push:
    branches: [main]
    paths: ["infra/**"]

permissions:
  contents: read

jobs:
  apply:
    runs-on: ubuntu-latest
    environment: production
    steps:
      - uses: actions/checkout@v4

      - uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: "1.8"

      - name: Terraform init
        run: terraform init
        working-directory: infra/
        env:
          TF_VAR_hetzner_token: ${{ secrets.HCLOUD_TOKEN }}

      - name: Terraform plan
        run: terraform plan -out=tfplan
        working-directory: infra/
        env:
          TF_VAR_hetzner_token: ${{ secrets.HCLOUD_TOKEN }}

      - name: Terraform apply
        run: terraform apply tfplan
        working-directory: infra/
        env:
          TF_VAR_hetzner_token: ${{ secrets.HCLOUD_TOKEN }}
```

### Deployment pattern for application code

Hetzner has no native blue/green or canary deployment service. Implement at the application layer:

| Pattern | How |
| --- | --- |
| Rolling deploy | Ansible serial: update one server at a time; health check before proceeding |
| Blue/green | Provision a second server set from the golden image, switch Load Balancer target; delete old set |
| Canary | Nginx upstream weights or Traefik weighted routing; shift traffic gradually |
| Immutable + swap | Packer-bake a new image, provision new servers, swap LB target, delete old servers |

For most Hetzner workloads, the immutable + swap pattern is the safest: old servers remain live until new servers are confirmed healthy.

## Secrets in IaC

- `HCLOUD_TOKEN` or `TF_VAR_hetzner_token`: inject via CI secrets or environment variable; never in `.tfvars` files committed to git.
- Database credentials: Ansible Vault or HashiCorp Vault; pass to cloud-init via `vars_files` or from a secrets manager.
- SSH private keys: never in IaC files. Distribute via SSH agent forwarding in Ansible (`--ssh-extra-args`) or ssh-agent in CI.
- `terraform output -raw` for any sensitive output: mark `sensitive = true` in the output definition to suppress from CI logs.

## Cost considerations

- Remote state storage on Cloudflare R2 is free for small state files (egress from R2 is free). Backblaze B2 is cheap (~$0.006/GB/mo). Self-hosted Minio on a small Hetzner CX11 adds ~€4.15/mo but gives you locking with the HTTP backend.
- Test server provisioning (for Terraform integration tests) should be torn down immediately after the test run — left running, even a CX22 at €4.15/mo per server accumulates fast with a large test matrix.
- Packer build servers are ephemeral — use the smallest server type that can run the build (typically CX22), and the build server is deleted automatically after the snapshot is taken.
- Pipeline compute (GitHub Actions runners) is billed by GitHub, not Hetzner. Self-hosted runners on Hetzner CX22 can reduce CI cost for large teams with heavy pipeline usage.

## Observability hints

- Tag every server in IaC with `env`, `role`, and `service` labels — these are the primary axis for cost and operational reporting in the Cloud panel.
- Ship Terraform plan and apply outputs to a log store (GitHub Actions artifacts, Loki, or a long-lived S3-compatible bucket) so infra change history is queryable outside of git.
- Pipeline metrics: lead time for changes (PR to deploy), deployment frequency, change failure rate. Track these even informally — they reveal whether the pipeline is helping or slowing the team.
- Drift detection: run `terraform plan -detailed-exitcode` on a schedule; treat a non-zero exit code (drift detected) as an alert.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Local Terraform state | Two team members applying simultaneously corrupt state; no recovery path. Use remote state from day one. |
| HCLOUD_TOKEN hard-coded in `.tf` or `.yml` files | Token in git history forever. Rotate and use env vars + secrets. |
| Entire fleet in a single `hcloud_server` count | One bad `terraform apply` deletes and recreates all servers simultaneously. Use separate resources or target at apply time. |
| cloud-init as the full configuration management | cloud-init runs once; Ansible can be run repeatedly. Complex configuration belongs in CM, not user_data. |
| No `prevent_destroy` on production servers and volumes | A resource rename in Terraform triggers delete + recreate. A production database is gone in seconds. |
| Packer build not saving the snapshot ID | You lose track of which snapshot corresponds to which version; builds become unmaintainable. Always write a manifest. |
| GitHub Actions applying to prod on every `main` push | A bad merge = immediate prod change. Require manual approval or environment protection rules for prod. |
| Ansible without dynamic inventory | Static inventory files drift from reality as servers are added / replaced. Use the `hetzner.hcloud.hcloud` inventory plugin. |

## Verification checklist

- [ ] Remote state backend configured; no local state for any environment.
- [ ] `prevent_destroy = true` on production servers and volumes.
- [ ] `HCLOUD_TOKEN` injected via CI secrets only; not committed to any file in the repo.
- [ ] Provider version pinned (`>= 1.48, < 2.0`); lockfile committed.
- [ ] cloud-init validates clean on `cloud-init schema --config-file cloud-init.yml` before deployment.
- [ ] Packer manifest output captured and snapshot ID passed to Terraform.
- [ ] GitHub Actions prod apply requires manual approval or environment protection.
- [ ] Ansible uses dynamic inventory (`hetzner.hcloud.hcloud` plugin); no static inventory for production.
- [ ] Rollback procedure documented (revert Terraform to previous snapshot ID or re-apply previous state).
- [ ] Drift detection: scheduled `terraform plan` in CI alerts on unexpected drift.
- [ ] No secrets in git; pre-commit secret scanning enforced.
