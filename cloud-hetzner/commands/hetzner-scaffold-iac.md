---
description: Scaffold a Hetzner Infrastructure-as-Code project — Terraform hetznercloud/hcloud or Ansible hetzner.hcloud, with opinionated production-grade defaults for compute, networking, firewalls, and storage.
argument-hint: <workload-description>
---

# Hetzner Scaffold IaC

Scaffold a new Hetzner Infrastructure-as-Code project for a workload described as: **$ARGUMENTS**

## What to do

1. **Confirm the IaC tool.** Ask the user which tool they want, with a one-line recommendation:
   - New project, team uses HCL, or multi-provider (Cloudflare DNS + Hetzner + GitHub) → **Terraform + hetznercloud/hcloud ≥ 1.48** (recommended default).
   - Existing Ansible shop, config management and provisioning in one tool → **Ansible + hetzner.hcloud collection**.
   - Team prefers TypeScript / Python over HCL → **Pulumi + @pulumi/hcloud**.
   - One-off dev environment or quick experiment → **hcloud CLI + shell scripts** (not suitable for production).

   Recommend, then defer to the user.

2. **Confirm scope** with up to three questions if not obvious:
   - Which Hetzner location(s)? (e.g., `nbg1` / `fsn1` / `hel1` / `ash` — EU-central default.)
   - Greenfield, or migrating existing console-built infrastructure (import vs fresh)?
   - Does the workload need an external managed database, or self-hosted?

3. **Generate the project skeleton** in the current working directory or a subdirectory the user chooses. Every scaffold must include:
   - Pinned provider / collection versions and a lockfile.
   - Per-environment separation (`dev`, `staging`, `prod`).
   - Remote state backend configuration (S3-compatible: Cloudflare R2, Backblaze B2, or self-hosted Minio).
   - A `.gitignore` for the tool.
   - A `README.md` with bootstrap and deploy / destroy commands.
   - At minimum: networking (Private Network + subnets), one server per tier, a Cloud Firewall, and a Load Balancer.
   - GitHub Actions CI for plan + apply (or Ansible equivalent) with the `HCLOUD_TOKEN` injected from secrets.
   - Tagging strategy applied via labels (`env`, `role`, `service`) — Hetzner uses server labels, not tags.

4. **Wire safe defaults.** For each scaffold:
   - SSH key-only auth enforced via cloud-init (`ssh_pwauth: false`, `disable_root: true`).
   - Cloud Firewall default-deny inbound applied at server creation (not after).
   - Private Network for inter-server communication; public IPv4 suppressed on backend servers.
   - Automated backups enabled on servers holding state.
   - `prevent_destroy = true` on production servers and volumes.
   - Load Balancer with HTTPS + Let's Encrypt managed certificate if the workload is HTTP-facing.

5. **Print next steps** — exact commands to run after scaffolding: `terraform init`, `export HCLOUD_TOKEN=...`, first `terraform plan`, Ansible Galaxy install command, etc. Remind the user that the first apply should target `dev`, not `prod`.

## Tool-specific layouts

### Terraform (recommended)

```
.
├── modules/
│   ├── network/
│   │   ├── main.tf          # hcloud_network, hcloud_network_subnet
│   │   ├── variables.tf
│   │   └── outputs.tf
│   ├── compute/
│   │   ├── main.tf          # hcloud_server, hcloud_server_network
│   │   ├── cloud-init.yml   # SSH key injection, disable password auth
│   │   ├── variables.tf
│   │   └── outputs.tf
│   ├── loadbalancer/
│   │   ├── main.tf          # hcloud_load_balancer, service, targets
│   │   ├── variables.tf
│   │   └── outputs.tf
│   └── firewall/
│       ├── main.tf          # hcloud_firewall, hcloud_firewall_attachment
│       ├── variables.tf
│       └── outputs.tf
├── envs/
│   ├── dev/
│   │   ├── backend.tf       # S3-compatible remote state
│   │   ├── main.tf          # Module instantiations
│   │   ├── terraform.tfvars
│   │   └── outputs.tf
│   ├── staging/
│   │   └── ...
│   └── prod/
│       └── ...
├── .terraform.lock.hcl      # Committed to repo
├── .gitignore
├── .github/
│   └── workflows/
│       ├── tf-plan.yml      # On PR: plan + comment diff
│       └── tf-apply.yml     # On merge to main: apply dev; prod requires approval
└── README.md
```

Key files:

```hcl
# modules/compute/cloud-init.yml
#cloud-config
users:
  - name: deploy
    groups: sudo
    sudo: ['ALL=(ALL) NOPASSWD:ALL']
    ssh_authorized_keys:
      - ${ssh_public_key}
ssh_pwauth: false
disable_root: true
packages:
  - fail2ban
runcmd:
  - systemctl enable fail2ban && systemctl start fail2ban
```

```hcl
# modules/firewall/main.tf
resource "hcloud_firewall" "web" {
  name = "${var.env}-web"

  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "443"
    source_ips = ["0.0.0.0/0", "::/0"]
  }

  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "80"
    source_ips = ["0.0.0.0/0", "::/0"]
  }

  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "22"
    source_ips = var.management_cidrs
  }

  rule {
    direction       = "out"
    protocol        = "tcp"
    port            = "any"
    destination_ips = ["0.0.0.0/0", "::/0"]
  }

  rule {
    direction       = "out"
    protocol        = "udp"
    port            = "53"
    destination_ips = ["0.0.0.0/0", "::/0"]
  }

  rule {
    direction       = "out"
    protocol        = "icmp"
    destination_ips = ["0.0.0.0/0", "::/0"]
  }

  apply_to {
    label_selector = "env=${var.env},role=web"
  }
}
```

### Ansible

```
.
├── inventory/
│   └── hcloud.yml           # Dynamic inventory: plugin: hetzner.hcloud.hcloud
├── group_vars/
│   ├── all.yml              # Common variables; HCLOUD_TOKEN from env
│   ├── web.yml
│   └── db.yml
├── host_vars/               # Per-server overrides if needed
├── roles/
│   ├── common/              # SSH hardening, fail2ban, base packages
│   ├── web/                 # Nginx / Caddy / application server
│   └── db/                  # Postgres / MySQL self-hosted setup
├── playbooks/
│   ├── provision.yml        # Hetzner resource creation (hcloud_* modules)
│   ├── configure.yml        # OS configuration via roles
│   └── deploy.yml           # Application deployment
├── requirements.yml         # collections: [hetzner.hcloud, community.general]
├── ansible.cfg
├── .github/
│   └── workflows/
│       ├── ansible-check.yml   # ansible-playbook --check on PR
│       └── ansible-apply.yml   # ansible-playbook on merge
└── README.md
```

Key snippet:

```yaml
# inventory/hcloud.yml
plugin: hetzner.hcloud.hcloud
token: "{{ lookup('env', 'HCLOUD_TOKEN') }}"
groups:
  web: "labels.role == 'web'"
  db:  "labels.role == 'db'"
compose:
  ansible_host: public_ipv4
```

## After scaffolding

- Recommend running `hetzner-architect` (the sub-agent) for a same-day review of the generated design before the first apply.
- Recommend running `hetzner-security-reviewer` (the sub-agent) once the first environment is deployed and before directing traffic to it.
- Remind the user:
  - Store `HCLOUD_TOKEN` in GitHub Actions secrets only; never commit to the repo.
  - Add a pre-commit secret scanner (`gitleaks`, `detect-secrets`) before the first commit.
  - Check `hcloud server list` after the first apply to confirm server labels match expectations for firewall label-selector attachment.
  - Enable `backup = true` or `hcloud server enable-backup` on any server holding state before going live.
