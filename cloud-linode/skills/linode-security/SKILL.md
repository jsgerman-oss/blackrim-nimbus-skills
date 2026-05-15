---
name: linode-security
description: Design or audit Linode security posture — Linode Manager users and roles, Personal Access Tokens (scopes and expiry), MFA and SSH key requirements, Cloud Firewall posture, root-user discipline, Akamai Shield DDoS, audit logs, OAuth applications. Use when hardening an account, scoping API access, reviewing access grants, or responding to a security event.
---

# Linode Security

## When to use

- Setting up a new Linode account with production-grade access controls.
- Scoping a Personal Access Token for a CI/CD pipeline or Terraform deployment.
- Reviewing user grants and removing excess privileges.
- Auditing Cloud Firewall posture across instances and NodeBalancers.
- Hardening SSH access configuration on Compute Instances.
- Responding to a suspected unauthorized access event.
- Rotating compromised credentials (PAT, Object Storage keys, SSH keys).

## Identity model

Linode does not have an equivalent of AWS IAM with policy documents. Access control is coarser-grained:

| Principal type | Linode mechanism | Notes |
| --- | --- | --- |
| Human operators | Linode Manager users + resource grants | Per-account users; no federated SSO from external IdP natively. |
| Automation / CI/CD | Personal Access Token (PAT) | Scoped to specific capabilities; set a short expiry. |
| Terraform / IaC | PAT | Same as automation; store in a secrets manager, not in code. |
| Object Storage clients | Object Storage Access Keys | Separate key type; scoped to buckets. |
| OAuth applications | OAuth 2.0 application registration | For apps acting on behalf of users; not for server-side automation. |

**No native SSO federation.** Linode Manager does not federate with Okta, Entra ID, or Google Workspace directly. Workaround: use a password manager with MFA for shared access, or consider a third-party identity proxy. This is a meaningful gap compared to AWS IAM Identity Center.

## Linode Manager users and roles

- **Account owner:** the root account credential. Protect aggressively — hardware MFA, dedicated email, long random password. The account owner can grant and revoke access for all other users.
- **User grants:** users can be granted access to specific resources (individual instances, NodeBalancers, Volumes, domains) or account-wide access. Avoid account-wide `full` grants for everyday operators.
- **Grant levels per resource:** `read_only` or `read_write`. Use `read_only` for monitoring and audit users. Use `read_write` only for the resources a user genuinely needs to modify.
- **No group-based policies.** Access is assigned per user per resource type. This makes least-privilege tedious to maintain at scale. Compensate by limiting user count and reviewing grants quarterly.
- **Restricted users:** a user can be created as "restricted" (access only to granted resources) vs unrestricted (full account access). Default new users to restricted.

## Personal Access Tokens (PATs)

- **Scope:** select only the permissions the token needs. Permissions are coarse (e.g., `linodes:read_write`, `databases:read_only`) — select the minimum set.
- **Expiry:** always set an expiry. Tokens can be set to expire in 6 months or less for CI/CD; use shorter for high-risk operations. Tokens with no expiry (`never`) are a liability — avoid them.
- **Rotation:** build token rotation into your operational cadence. For Terraform: update the `LINODE_TOKEN` secret in your CI/CD system and in `linode-cli`'s config.
- **Storage:** store PATs in a secrets manager (HashiCorp Vault, AWS Secrets Manager, GitHub Actions secrets). Never commit to source control, never in environment variables printed in build logs.
- **One token per consumer.** Do not share a PAT between multiple systems. Separate tokens for Terraform, CI/CD pipelines, monitoring agents, and any automation. This enables per-consumer revocation without disrupting others.
- **Audit:** Linode's audit log (`Events` in Cloud Manager) does not attribute actions to individual PATs — it attributes to the user who owns the PAT. Keep a mapping of which system uses which PAT label.

## MFA

- **Enforce MFA** for every human Linode Manager user. Linode supports TOTP-based MFA (Google Authenticator, Authy, 1Password TOTP, etc.).
- The account owner should use a hardware security key (FIDO2/WebAuthn) where supported. Verify current browser-based FIDO2 support on Linode Manager.
- Recovery codes: store securely (password manager, physical safe). Losing MFA access without recovery codes can lock a user out permanently.
- **There is no org-wide MFA enforcement policy in Linode Manager** (unlike AWS account-level IAM policies). Enforce by procedure: verify all users have MFA via the Users page in Cloud Manager, and make it a documented onboarding step.

## SSH key management

- Register SSH public keys in Linode Manager (Profile > SSH Keys). Keys registered here can be deployed to instances at creation time.
- **Team SSH keys:** add all operators' keys before creating instances. Do not deploy instances with only one key — if that key is lost or the operator leaves, you lose emergency SSH access.
- **Remove keys when team members offboard.** Linode does not automatically revoke instance-level keys when a Cloud Manager key is removed — removing from Cloud Manager only prevents future instances from getting that key. On running instances, remove the key from `~/.ssh/authorized_keys` manually or via automation.
- **Root SSH:** disable root SSH login in `sshd_config` on every instance. Named admin users only. Automate this in cloud-init or Ansible.
- **Lish access:** Linode Shell (Lish) provides out-of-band console access without SSH. This bypasses Cloud Firewall. Restrict Lish access in user grants to only the users who genuinely need it. Lish is the break-glass path; audit who has it.

## Cloud Firewall posture

See `linode-networking` for rule design detail. Security summary:

- Default-deny inbound on every instance, NodeBalancer, and VPC.
- Never allow any database or cache port inbound from `0.0.0.0/0`.
- SSH restricted to a known management CIDR. Prefer Lish for emergency access over opening SSH wide.
- Review firewall rules quarterly. Remove stale allow rules immediately when a service is decommissioned.

## Root-user discipline

- The Linode Manager account owner (root account) should use a unique strong password and hardware MFA.
- Do not use the account owner credential for day-to-day operations. Create named restricted users for operators.
- On Compute Instances, the `root` Linux user is enabled by default. Disable direct root SSH (`PermitRootLogin no`). Create a named admin user with `sudo`. Automate this at boot via cloud-init.
- Rotate the Linux root password on instances using random generation at provision time (store in a password manager). The Linux root password is a last-resort credential; Lish is the console alternative.

## Akamai Shield (DDoS)

- Akamai's network-level DDoS scrubbing is included for Linode resources at no additional charge. It handles volumetric attacks at the upstream network layer.
- **Application-layer DDoS / WAF:** not included in standard Linode pricing. For protection against Layer 7 attacks (HTTP floods, SQLi, XSS), an additional service is required — Cloudflare, Fastly, or Akamai App & API Protector (separate Akamai product line).
- **Rate limiting at the application layer:** implement in your application or at a NodeBalancer / reverse proxy level. Linode does not offer a native WAF or rate-limiting service.

## Audit logs

- **Cloud Manager Events:** every resource action (instance creation, deletion, reboot, firewall change, user grant change, etc.) is logged in the Events feed. Accessible in Cloud Manager and via the Linode API (`GET /account/events`).
- **Retention:** events are retained for a limited period in the API (check current policy). For compliance, export events periodically to your own storage (script against the Events API and store in Object Storage).
- **Attribution:** events are attributed to the user account that owns the PAT. Individual PATs cannot be separately identified in audit logs. Compensate with a PAT naming convention (e.g., `terraform-prod-2026`) and an internal mapping document.
- **Login events:** Cloud Manager login events are included in the Events log. Set up alerts if your external monitoring can consume the Events API.
- **No native SIEM integration.** Export the Events API response to your SIEM manually or via a connector script.

## OAuth applications

- Linode supports OAuth 2.0 for applications that act on behalf of user accounts. Scope the application to the minimum required permissions.
- OAuth application credentials (client ID + secret) must be stored securely, not in source code.
- Revoke OAuth applications that are no longer in use.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| PAT with no expiry used in production | Credentials that never expire create indefinite exposure if leaked. Set an expiry. |
| Shared PAT across multiple systems | One compromise requires rotating across all systems simultaneously. One token per consumer. |
| Account-wide `full` grants for operators | Operators can delete any resource. Use restricted users with per-resource grants. |
| No MFA on any user | Credential stuffing or phishing = full account access. MFA on all human users. |
| Root SSH login enabled on instances | Direct root compromise path. Disable, use named admin user + `sudo`. |
| Object Storage keys with unrestricted scope | A leaked key can access all buckets. Scope keys to specific buckets. |
| Not rotating credentials when team members leave | Ex-team-member SSH keys and PATs remain valid. Immediate revocation procedure required. |
| Assuming Akamai Shield covers application attacks | Shield handles volumetric DDoS. Layer 7 attacks require a separate WAF. |

## Defaults at account bootstrap

- Account owner: hardware MFA or TOTP MFA; dedicated email; unique strong password; not used for day-to-day ops.
- Create named restricted users for each operator; grant only the resources they own.
- Register all operators' SSH keys in Cloud Manager before creating instances.
- Create a dedicated PAT for each automated system (Terraform, CI/CD, monitoring); set expiry ≤ 6 months.
- Store all PATs in a secrets manager.
- Enable Linode Backups on all production instances at creation.
- Attach a Cloud Firewall with default-deny inbound to every instance at creation.

## Observability defaults

- Export the Cloud Manager Events API to your logging system on a schedule (daily minimum).
- Alert on failed login events and unusual resource-creation patterns (unexpected new instances, firewall rule deletions).
- Quarterly review: audit all users and their grants, remove accounts for departed team members, rotate PATs.
- Verify MFA status for all users at each quarterly review.

## Cost considerations

- Security controls on Linode are largely free (Cloud Firewall, MFA, SSH key management). The main cost is operational discipline.
- Object Storage access key management and PAT management have no direct cost.
- DDoS scrubbing (Akamai Shield) is included. Application WAF is a separate product with its own cost structure.

## IaC hints

- Terraform: `linode_token_v2` (if using service accounts via OAuth) is provider-version-dependent. Verify current provider support.
- Manage SSH keys at the account level with `linode_sshkey` resource; reference in `linode_instance.authorized_keys`.
- Cloud Firewall rules in Terraform: `linode_firewall` with `inbound_policy = "DROP"`, `outbound_policy = "ACCEPT"`, and explicit `inbound` rule blocks.
- PAT rotation: use a Terraform variable or secret reference for `LINODE_TOKEN`. Update the secret in CI/CD, then re-plan to verify no drift.

## Verification checklist

- [ ] Account owner uses MFA (hardware token preferred); not used for day-to-day operations.
- [ ] All operator users are restricted; grants scoped to the resources they manage.
- [ ] All human users have MFA enabled.
- [ ] Each automated system (Terraform, CI/CD, monitoring) has a dedicated PAT with expiry and minimum scope.
- [ ] PATs stored in a secrets manager; not committed to source control.
- [ ] SSH key-only authentication; root login disabled on all instances.
- [ ] Cloud Firewall with default-deny inbound attached to every instance and NodeBalancer.
- [ ] No database or cache ports open to the internet.
- [ ] Offboarding procedure removes SSH keys from running instances and revokes Cloud Manager access.
- [ ] Events API exported and retained for audit purposes.
- [ ] Quarterly review of users, grants, and PAT expiry scheduled.
