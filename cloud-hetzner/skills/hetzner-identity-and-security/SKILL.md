---
name: hetzner-identity-and-security
description: Design or audit Hetzner identity and security posture — API tokens (read-only vs read+write, project isolation), project-level access boundary and its RBAC limitations, SSH key management, Cloud Firewall policies, server password vs key-only auth, MFA on the Cloud console, Robot vs Cloud account separation. Use when scoping access, creating API tokens, auditing security posture, or hardening a Hetzner deployment.
---

# Hetzner Identity and Security

## When to use

- Creating or rotating API tokens for automation, CI/CD, or Terraform.
- Designing the project structure to enforce access boundaries.
- Hardening server authentication (SSH keys, no passwords).
- Auditing Cloud Firewall posture and inbound exposure.
- Setting up MFA for the Hetzner Cloud console and Robot panel.
- Separating Robot dedicated server access from Cloud access.
- Onboarding a new team member with appropriate access scope.
- Responding to a suspected credential or token compromise.

## Identity model — what Hetzner offers

Hetzner's identity model is far simpler than AWS IAM or Google Cloud IAM, and that simplicity is also its limitation.

| Layer | Mechanism | Scope |
| --- | --- | --- |
| Human console access | Hetzner account (email + password + MFA) | Full account; no per-project read-only for humans |
| API automation | API token | One project; read-only or read+write |
| Server auth | SSH key or password | Per-server at provisioning; global key store per account |
| Robot panel | Separate account credentials | Separate from Cloud |

**There is no account-wide RBAC.** A human with Hetzner Cloud account access can see and modify all projects. There are no IAM users, permission sets, or role bindings like AWS IAM Identity Center or GCP IAM. The only automated access boundary is the API token scoped to a project.

## API tokens

API tokens are the primary machine identity in Hetzner Cloud. They operate as Bearer tokens passed in the `Authorization` header of every hcloud API call.

Properties:

- **Project-scoped.** A token grants access only to the project it was created in. A token from project A cannot read or modify resources in project B.
- **Permission level.** `Read` (GET requests only) or `Read & Write` (all methods). There is no fine-grained resource-level permission; a write token can create, modify, and delete any resource in the project.
- **No expiry.** Tokens do not expire automatically. Rotation is manual.
- **No audit log.** Hetzner does not provide an API call log attributable to a specific token. You cannot query "what did this token do last week."

Best practices:

- Create one token per use case (one for Terraform, one for CI deployment, one for monitoring).
- Use read-only tokens for monitoring and read-only operations.
- Store tokens in a secrets manager (HashiCorp Vault, Doppler, GitHub Actions secrets) rather than in plaintext config files or environment files checked into git.
- Rotate tokens periodically (quarterly or on team member departure). Rotation is non-disruptive if automation reads from a secrets manager.
- Delete tokens that are no longer in use — they are invisible in the Hetzner audit surface, so unused tokens are an untracked risk.

```bash
# Create a token via hcloud CLI
hcloud context create myproject
# Prompts for the API token; stored in ~/.config/hcloud/cli.toml

# List contexts (projects)
hcloud context list
```

```hcl
# Use in Terraform
provider "hcloud" {
  token = var.hetzner_token  # passed via TF_VAR_hetzner_token or Vault
}
```

## Project isolation as the primary access boundary

Because Hetzner lacks account-wide RBAC, **projects are the access boundary** for automated systems. Use projects to enforce blast-radius limits:

- One project per environment (dev, staging, prod).
- One project per major product or team if multi-tenant.
- Separate the prod project's token from all non-prod tokens. A CI system building dev images should never hold a prod write token.

Projects do not provide network isolation — a server in project A can reach a server in project B over the public internet. Private Network isolation is provided by the Hetzner Private Network (not the project boundary). Use Cloud Firewalls and Private Networks for network isolation; use projects for API access isolation.

## SSH key management

Hetzner Cloud has a per-account SSH key store. Keys registered in the account can be assigned to servers at provisioning time.

Defaults:

- Register team public keys in the Hetzner account; reference by ID in Terraform.
- Assign multiple keys per server so that a single lost key does not lock you out.
- Do not use the same key pair across dev and production servers.
- Rotate keys on team member offboarding by removing the old key from the account and reprovisioning or running key rotation via Ansible.

```hcl
resource "hcloud_ssh_key" "deploy" {
  name       = "deploy-2026"
  public_key = file("~/.ssh/deploy_ed25519.pub")
}

resource "hcloud_server" "app" {
  name        = "app-01"
  server_type = "cpx31"
  image       = "ubuntu-24.04"
  location    = "nbg1"
  ssh_keys    = [hcloud_ssh_key.deploy.id]
}
```

Prefer `Ed25519` keys over RSA. Minimum RSA key size if forced: 4096 bits. Avoid ECDSA on secp256k1 (not the same curve as ed25519; ed25519 is preferred for its smaller key size and resistant design).

## Disable password authentication

Hetzner creates servers with a root password and email it to you when no SSH key is specified, or when a server is built from an OS image without cloud-init key injection. Always inject SSH keys via cloud-init and disable password authentication.

cloud-init snippet:

```yaml
#cloud-config
users:
  - name: deploy
    groups: sudo
    sudo: ['ALL=(ALL) NOPASSWD:ALL']
    ssh_authorized_keys:
      - ssh-ed25519 AAAA... deploy@example.com

ssh_pwauth: false
disable_root: true
```

If you receive a server where password auth is active, harden immediately:

```bash
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin prohibit-password/' /etc/ssh/sshd_config
systemctl restart sshd
```

## MFA on the Cloud console

Hetzner Cloud console and Robot panel both support TOTP-based MFA. Enable it for every human account that has console access.

- Cloud: Settings → Security → Two-factor authentication.
- Robot: Account → Security → 2FA.

Recovery codes should be stored in a team password manager (1Password, Bitwarden) shared with at least one other team member, not only on the account owner's device.

Hetzner does not support hardware security keys (FIDO2 / WebAuthn) for console login as of 2026-05.

## Robot vs Cloud account separation

Hetzner Cloud and Hetzner Robot use different account systems with separate credentials:

- **Cloud:** Managed at console.hetzner.cloud with hcloud API tokens.
- **Robot:** Managed at robot.your-server.de with a separate username/password and Robot REST API.

The Robot API does not use hcloud API tokens. Authenticate via HTTP Basic Auth (`Authorization: Basic base64(<user>:<password>)`) or via the Robot API key shown in the Robot panel.

Keep Robot and Cloud credentials in separate secrets; do not reuse passwords. If your automation touches both surfaces (e.g., provisioning a Robot server and then connecting it to a Cloud Private Network via vSwitch), store both credential sets separately.

## Cloud Firewall as security perimeter

Cloud Firewalls are enforced at the hypervisor — traffic never reaches the server's NIC if the firewall drops it. This makes them the authoritative inbound control, unlike iptables rules that operate inside a potentially compromised OS.

Default-deny strategy:

- Create a `base` firewall applied to all servers with: inbound SSH from management CIDR only, ICMP for reachability, all outbound TCP + UDP + ICMP permitted.
- Create workload-specific firewalls (e.g., `web`, `db`) that layer on top of the base with the minimum required ports.
- Attach firewalls via label selectors in Terraform so new servers with the right label automatically inherit the policy.

```hcl
resource "hcloud_firewall" "base" {
  name = "base"

  apply_to {
    label_selector = "env=prod"
  }

  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "22"
    source_ips = ["10.0.0.0/8"]  # Private Network management only
  }

  rule {
    direction  = "in"
    protocol   = "icmp"
    source_ips = ["0.0.0.0/0", "::/0"]
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
}
```

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Single read+write API token shared across all automation | One leaked token = write access to the entire project. Separate tokens per use case. |
| Token stored in a dotfile or `.env` checked into git | Git history is permanent. Pre-commit secret scanning is mandatory; rewrite history if leaked. |
| No token rotation schedule | A token in use for 2+ years has almost certainly been exposed somewhere. Rotate quarterly. |
| Password authentication enabled on servers | SSH brute-force bots attack new servers within seconds of provisioning. Disable immediately. |
| No MFA on the Hetzner Cloud account | Account takeover via phishing = all projects and servers compromised. Enable MFA for every human. |
| Same API token for dev and prod | A CI bug in dev deploys to prod or deletes prod servers. Separate projects, separate tokens. |
| Cloud Firewall applied after initial provisioning | The window between server creation and firewall application is open. Apply at creation via Terraform. |
| Relying on OS firewall (iptables) alone | An OS compromise can flush iptables. Cloud Firewall at hypervisor is the authoritative perimeter. |

## Security defaults

At account bootstrap:

- Enable MFA on every human Hetzner Cloud account (TOTP; store recovery codes in team password manager).
- Enable MFA on every Robot account used by the team.
- Create one read-only token for monitoring/audit and one read+write token per environment; no shared tokens.
- All tokens stored in a secrets manager; never in dotfiles, environment files, or git.
- Pre-commit hook scanning for secrets in all repositories using this infrastructure.

At server provisioning:

- SSH key injected via cloud-init; password authentication disabled.
- Cloud Firewall applied at creation (Terraform `hcloud_firewall_attachment`).
- No public IPv4 if the server only communicates via Private Network.
- Root login disabled or key-only (`PermitRootLogin prohibit-password`).

## Observability defaults

- Hetzner does not provide API call audit logs. Compensate with application-layer logging of all infrastructure changes (Terraform plan + apply outputs to a log store).
- Monitor SSH login events via `/var/log/auth.log` shipped to your observability platform; alert on unexpected login origins.
- Alert on failed authentication attempts — Fail2Ban or CrowdSec on each server as a real-time rate limiter.
- Track token usage via your automation's own logs; flag any token that has not been used in 90+ days for deletion.

## Cost considerations

- API tokens, SSH keys, projects, and Cloud Firewalls are all free; no cost consideration beyond management overhead.
- Project structure affects billing visibility — per-project cost breakdown is available in the Cloud console. Use one project per environment for clean cost attribution.
- Robot and Cloud are billed separately; the Robot invoice is separate from the Cloud invoice.

## IaC hints

- Terraform: `hcloud_ssh_key`, `hcloud_firewall`, `hcloud_firewall_attachment`. The `apply_to` block with `label_selector` is the preferred way to attach firewalls to dynamic server pools.
- Ansible: `hetzner.hcloud.hcloud_ssh_key`, `hetzner.hcloud.hcloud_firewall`, `hetzner.hcloud.hcloud_firewall_info`.
- Secret management: pass `HCLOUD_TOKEN` as an environment variable in CI; never hard-code in IaC files. Use `TF_VAR_hetzner_token` for Terraform.

## Verification checklist

- [ ] MFA enabled on every human Hetzner Cloud and Robot account.
- [ ] Separate API tokens per environment and per use case; read-only where write is not needed.
- [ ] All tokens stored in a secrets manager, not in git or dotfiles.
- [ ] Token rotation schedule defined and documented.
- [ ] SSH key-only auth enforced; password authentication disabled on all servers.
- [ ] Root login disabled or key-only on all servers.
- [ ] Cloud Firewall applied at server creation time; default-deny inbound.
- [ ] No API token shared between dev and prod environments.
- [ ] Pre-commit secret scanning in all IaC and application repositories.
- [ ] Unused tokens identified and deleted (audit monthly).
