---
name: linode-iac-and-deployment
description: Choose, scaffold, or review Linode Infrastructure-as-Code and deployment — linode-cli, Terraform linode/linode provider, Ansible Linode collection, StackScripts (legacy), cloud-init bootstrap, GitHub Actions CI/CD. Use when starting a new IaC project, picking a tool, or hardening a release path.
---

# Linode Infrastructure-as-Code and Deployment

## When to use

- Greenfield project on Linode — picking an IaC tool.
- Inheriting manually-created Linode resources that need to come into code.
- Designing a CI/CD pipeline for application and infrastructure deployment.
- Reviewing an existing Terraform or Ansible repo for drift, secrets, and state hygiene.
- Replacing legacy StackScripts with a reproducible provisioning approach.
- Standing up LKE clusters with GitOps or Helm-based application delivery.

## IaC tool — picking one

| Tool | Pick when |
| --- | --- |
| **Terraform / OpenTofu + linode/linode provider** | Primary choice for most teams. Terraform is the most mature IaC option for Linode with the broadest resource coverage. Use OpenTofu as a drop-in open-source fork if license terms matter. |
| **Ansible Linode collection** | Team is already Ansible-heavy; you want idempotent instance configuration alongside provisioning. Ansible manages the instance lifecycle and runs configuration in one playbook run. |
| **linode-cli** | Operational companion; use for ad-hoc resource management, quick inspection, scripted one-shot tasks. Not a substitute for IaC — avoid managing long-lived resources with raw CLI. |
| **Pulumi (linode provider)** | Team prefers a general-purpose programming language over HCL; multi-cloud. Community-maintained Linode provider; verify coverage before committing. |
| **StackScripts** | Legacy only. StackScripts are shell scripts that run once at instance creation. Not idempotent, hard to test, no state. Use cloud-init for first-boot configuration; use Terraform + Ansible for everything beyond first-boot. |

The recommended default for new Linode projects: **Terraform** for infrastructure (instances, VPC, firewalls, NodeBalancers, databases, Object Storage) + **cloud-init** for first-boot configuration + **Ansible** or a container image for application deployment.

## Terraform — linode/linode provider

- **Provider version:** pin `>= 2.20` in `required_providers`. Check the [provider changelog](https://registry.terraform.io/providers/linode/linode/latest) for breaking changes before upgrading.
- **Authentication:** set the `LINODE_TOKEN` environment variable with a Personal Access Token scoped to the required resources. Do not hard-code the token in `.tf` files.
- **State backend:** use a remote state backend. For Linode-only shops, store state in Linode Object Storage (S3-compatible; use the `s3` backend with the Linode endpoint). Alternatively, use Terraform Cloud / HCP Terraform.
- **State locking:** Terraform's S3 backend supports DynamoDB for locking; Linode has no equivalent. Use a Terraform Cloud workspace, or accept the risk of concurrent applies for small teams with strong process controls.
- **Workspace per environment:** `dev`, `stage`, `prod` as separate Terraform workspaces or separate state files. Never `if var.env == "prod"` branching inside a single config — it makes blast radius analysis hard.
- **Stateful resources:** set `prevent_destroy = true` in `lifecycle` blocks for Managed Databases, Block Storage Volumes, and Object Storage buckets in production.

### Key Terraform resources

| Resource | Purpose |
| --- | --- |
| `linode_instance` | Compute Instance |
| `linode_lke_cluster` | LKE Kubernetes cluster with node pools |
| `linode_firewall` + `linode_firewall_device` | Cloud Firewall and attachment |
| `linode_vpc` + `linode_vpc_subnet` | VPC and subnets |
| `linode_nodebalancer` + `linode_nodebalancer_config` + `linode_nodebalancer_node` | Load balancer |
| `linode_volume` | Block Storage Volume |
| `linode_object_storage_bucket` + `linode_object_storage_key` | Object Storage |
| `linode_database_postgresql` / `linode_database_mysql` | Managed Database |
| `linode_sshkey` | Account-level SSH key |
| `linode_domain` + `linode_domain_record` | Linode DNS |

### State backend (Object Storage as S3 backend)

```hcl
terraform {
  backend "s3" {
    bucket                      = "my-tf-state"
    key                         = "prod/terraform.tfstate"
    region                      = "us-east-1"          # placeholder; Linode ignores region
    endpoint                    = "us-southeast-1.linodeobjects.com"
    access_key                  = var.obj_access_key   # from secrets manager, not hardcoded
    secret_key                  = var.obj_secret_key
    skip_credentials_validation = true
    skip_metadata_api_check     = true
    skip_region_validation      = true
    force_path_style            = true
  }
}
```

## Ansible Linode collection

- Collection: `linode.cloud` (from Ansible Galaxy). Install with `ansible-galaxy collection install linode.cloud`.
- Authentication: set `LINODE_TOKEN` environment variable or use the `api_token` module argument (prefer env var, not hardcoded).
- Key modules: `linode.cloud.instance`, `linode.cloud.lke_cluster`, `linode.cloud.firewall`, `linode.cloud.volume`, `linode.cloud.database_postgresql`, `linode.cloud.object_storage_bucket`.
- Idempotency: Linode Ansible modules are designed to be idempotent. Running a playbook twice should not recreate resources.
- Combine with Terraform: use Terraform to provision infrastructure, Ansible to configure the instances after provisioning. Terraform outputs can feed into Ansible inventory.

## linode-cli (operational companion)

- Install: `pip install linode-cli` (Python package). Requires `linode-cli >= 5.x`.
- Configure: `linode-cli configure` — prompts for a PAT and sets defaults.
- Common operational commands:
  - `linode-cli linodes list` — list instances.
  - `linode-cli linodes view <id>` — instance details.
  - `linode-cli lke clusters-list` — LKE clusters.
  - `linode-cli lke kubeconfig-view <id>` — get kubeconfig.
  - `linode-cli nodebalancers list` — NodeBalancers.
  - `linode-cli firewalls list` — Cloud Firewalls.
  - `linode-cli events list` — audit events.
- Use `--json` or `--text` for scripted consumption.

## cloud-init for first-boot provisioning

- Linode Compute Instances support cloud-init `user_data` (base64-encoded YAML). Pass via `linode_instance.metadata.user_data` in Terraform.
- Standard first-boot tasks:
  - Create a named admin user, add to `sudo`, install SSH public key.
  - Disable root SSH login (`PasswordAuthentication no`, `PermitRootLogin no`).
  - Run `apt-get update && apt-get upgrade -y` (or equivalent).
  - Install monitoring agent (Longview, node_exporter).
  - Configure unattended security upgrades.
- Keep `user_data` minimal. For complex configuration, trigger an Ansible run from cloud-init's `runcmd` (pull playbook from a private Object Storage bucket or a VPC-internal endpoint).

## StackScripts (legacy — do not use for new work)

- StackScripts are shell scripts that execute once at instance creation. They are not idempotent, have no state tracking, and are difficult to test.
- If you inherit a StackScript-based deployment, plan to replace it with cloud-init + Ansible on the next major provisioning cycle.
- StackScripts are still supported by Linode for Marketplace apps. Do not write new StackScripts for internal use.

## CI/CD pipeline

### Authentication — no OIDC on Linode

Linode does not support OIDC federation (unlike AWS, which supports GitHub Actions → OIDC → IAM role). This means you must use a PAT stored as a CI/CD secret. Keep the following practices:

- Create a dedicated PAT for each pipeline with minimum required scope and a short expiry.
- Store the PAT in GitHub Actions secrets (or equivalent CI secret store). Never log it.
- Rotate the PAT before expiry. Build rotation into your runbook.

### Pipeline stages

1. **Lint / validate:** `terraform fmt -check`, `terraform validate`, `tflint`, or `ansible-lint`. Run on every PR. Fast, blocks merge.
2. **Plan:** `terraform plan -out=tfplan`. Post the plan output as a PR comment. Reviewers must approve the plan for any prod change.
3. **Apply (dev/stage):** automatic on merge to a dev/stage branch. Allows fast iteration.
4. **Apply (prod):** manual trigger or tag-based gate. Require at least one human approval of the plan output before applying.
5. **Drift detection:** run `terraform plan -refresh-only` on a schedule (daily or weekly). Alert on non-empty diff.

### Example GitHub Actions structure

```
.github/workflows/
├── tf-plan.yml       # PR: validate + plan, post diff as comment
├── tf-apply-dev.yml  # Push to dev branch: auto-apply
├── tf-apply-prod.yml # Manual workflow_dispatch: apply prod
└── drift-check.yml   # Scheduled: terraform plan -refresh-only
```

### Application deployment patterns

| Pattern | Linode approach |
| --- | --- |
| Rolling deploy (containers / LKE) | Update the container image tag in the Kubernetes Deployment; `kubectl rollout status` |
| Blue/green (instances) | Provision a parallel set of instances; update NodeBalancer backend nodes; remove old nodes |
| Canary | Weighted NodeBalancer backends (set a percentage of backends to new version) |
| Immutable instance | Build a new Linode Image via Packer; replace instances from the new image |
| Kubernetes GitOps | Argo CD or Flux watching a Git repo; LKE cluster pulls manifests |

## Secrets in IaC

- Never commit PATs, Object Storage keys, or database passwords to source control.
- In Terraform: use `sensitive = true` on any output containing credentials. Prefer referencing credentials via environment variables over `terraform.tfvars` files.
- In GitHub Actions: use encrypted secrets. Do not print secrets in run steps.
- For application secrets in production: self-host HashiCorp Vault on a dedicated Linode instance, or use a hosted secrets manager (Doppler, Infisical, etc.). Linode has no native managed secrets service equivalent to AWS Secrets Manager.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Using StackScripts for internal provisioning | Not idempotent, hard to test, poor version control. Use cloud-init + Ansible. |
| Hard-coding the LINODE_TOKEN in `.tf` files | Token leaks via source control or Terraform state. Use environment variables. |
| Single Terraform state file for all environments | One bad apply can affect all environments. Separate state per environment. |
| Running `terraform apply` from a developer's laptop for prod | No audit trail, no peer review. Pipeline-only applies for any persistent environment. |
| No state locking | Concurrent applies corrupt state. Use Terraform Cloud or a locking mechanism. |
| Auto-applying to prod on merge | One bad merge = production outage. Manual gate or tag-based promotion for prod. |
| Infinite Terraform plan retention | Old plan files contain state snapshots — treat as sensitive and bound retention. |

## Verification checklist

- [ ] IaC tool chosen and pinned to specific provider version.
- [ ] Remote state backend configured; separate state per environment.
- [ ] `LINODE_TOKEN` sourced from environment / secrets manager; not in code.
- [ ] `prevent_destroy = true` on production stateful resources.
- [ ] CI pipeline: lint + plan on PR; apply gated (manual for prod).
- [ ] Drift detection scheduled.
- [ ] Application secrets not in IaC; stored in a secrets manager.
- [ ] Rollback procedure defined: for instances (restore from Image or Backup), for LKE (previous image tag rollout).
- [ ] Tagging strategy applied to all resources in IaC for cost attribution.
