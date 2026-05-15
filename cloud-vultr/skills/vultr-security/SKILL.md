---
name: vultr-security
description: Design or audit Vultr security posture — Firewall Groups and per-instance application, SSH key management, API Access keys (account level, scope carefully), 2FA enforcement, sub-accounts (limited RBAC), audit log access, and public IP discipline. Use when hardening an account, reviewing access controls, rotating credentials, or designing a least-privilege posture.
---

# Vultr Security

## When to use

- Hardening a Vultr account before onboarding a production workload.
- Reviewing Firewall Group rules across an instance fleet.
- Rotating or scoping API keys for a service or CI/CD pipeline.
- Enforcing 2FA and SSH key policy for the team.
- Designing a sub-account model for team or project isolation.
- Auditing public IP exposure across the account.

## Vultr security model — know the limits

Vultr's security model is simpler than hyperscaler IAM. Key facts to build your posture on:

- **No resource-level IAM.** API keys are account-scoped. An API key can do anything in the account that the HTTP API permits (create, delete, resize any instance, read any backup, etc.). There is no fine-grained resource policy.
- **Sub-accounts provide limited isolation.** Sub-accounts are separate Vultr accounts linked for billing purposes. A sub-account cannot access the parent account's resources, and vice versa. This is Vultr's RBAC substitute — but sub-accounts are entire separate accounts, not roles within one account.
- **Firewall Groups are the primary network control.** Vultr has no managed WAF, no VPC Security Groups with dynamic SG-to-SG references, and no PrivateLink. Firewall Groups + OS-level firewall are the defense.
- **2FA is per-user, not per-API-key.** 2FA protects control panel logins. API key requests are not protected by 2FA — key security is entirely about secrecy and rotation.

## Account bootstrap — security baseline

1. **2FA on every human account.** Enable TOTP 2FA (Google Authenticator, 1Password, etc.) on the root account and every sub-account immediately. Vultr supports TOTP; hardware key (FIDO2) is not available as of 2026-05.
2. **Do not use the root account for API access.** The root account API key has full access to every resource and billing function. Create a sub-account (or a dedicated user-level integration) for each system or team that needs API access.
3. **API keys: one per purpose, minimum required access.** Vultr API keys are account-scoped and cannot be restricted to specific resources or actions as of 2026-05. This means key hygiene — not scoping — is the primary control. Create separate keys for: Terraform IaC, CI/CD deploy pipeline, monitoring agents, developer break-glass.
4. **SSH keys: account-level management.** Upload SSH public keys to the Vultr account, then assign them to instances at provision time. Never distribute the same SSH keypair to multiple instances or multiple engineers.
5. **No password auth on instances.** Disable password authentication in SSH configuration (or via startup script / cloud-init) on every instance immediately after provision.

## Firewall Groups — posture design

Firewall Groups are the primary perimeter control for all instances.

### Design by tier

- **`fg-edge`**: Public-facing (Load Balancers, NAT instances, jump hosts). Allows 443, 80 (redirect), DDoS-mitigated if applicable. SSH restricted to management CIDR only.
- **`fg-app`**: Application tier. Inbound from VPC CIDR on app port only; no direct public inbound. SSH from management CIDR or jump host VPC IP.
- **`fg-db`**: Database / cache tier. Inbound on database port (5432, 3306, 6379, 9092) from VPC CIDR of app tier only. No public IP; no SSH from public.

### Rule writing discipline

- Default deny inbound is the starting state of a new Firewall Group — do not add a permissive allow-all to unblock an issue.
- Source CIDR for intra-VPC rules: use the VPC 2.0 network CIDR, not `0.0.0.0/0`.
- Source CIDR for management SSH: your office/VPN CIDR or a bastion/jump host VPC IP. Document which and why.
- Review all Firewall Group rules on a schedule (quarterly minimum). Rules added "temporarily" during incidents are a common source of permanent exposure.
- Apply Firewall Groups via IaC — `vultr_firewall_rule` in Terraform — so rules are version-controlled and reviewed in PRs.

### Firewall Group gaps to close

- Firewall Groups do not support logging of blocked traffic as of 2026-05. Use OS-level firewall logs (`ufw`, `iptables -j LOG`) on sensitive instances for visibility into blocked probes.
- Firewall Groups apply at the hypervisor edge, not inside the OS. An OS-level firewall in addition to the Firewall Group provides defense-in-depth and catches traffic on interfaces that bypass the hypervisor (loopback, VPC interfaces).
- Firewall Groups do not support service tags, SG-to-SG references, or dynamic source sets. For environments with frequently changing source IPs, manage sources via CIDR update automation or WireGuard VPN with a fixed VPN CIDR as the source.

## SSH key management

- Generate Ed25519 keys: `ssh-keygen -t ed25519 -C "your-name@your-company.com"`. Prefer Ed25519 over RSA for new keys.
- Upload the public key to the Vultr account. Name the key after the person or system it belongs to — not generic names like "deploy key".
- Assign specific keys to specific instances at provision time. Do not assign all account keys to every instance.
- Rotate SSH keys at minimum annually or on personnel change. Removing an old key from the Vultr account does not remove it from running instances — run an audit to remove stale keys from `~/.ssh/authorized_keys` on each instance.
- For CI/CD systems that need SSH access: use a dedicated keypair, stored in the CI secrets manager, with access to only the instances it must reach.

## API key hygiene

- Store API keys in a secrets manager (HashiCorp Vault, Doppler, 1Password Secrets Automation, GitHub Actions Secrets). Never in code, `.env` files checked into version control, or plain text on disk.
- Rotate API keys at minimum annually or on team member departure. Vultr API keys do not expire by default.
- Revoke keys via the Vultr control panel (`Account → API`). After revocation, the key stops working immediately — no grace period.
- Use the principle of key separation: one key per system or service. If a CI/CD pipeline key is compromised, you revoke only that key without impacting Terraform automation or monitoring agents.
- Audit active API keys periodically. Remove keys that are no longer needed. Vultr does not provide last-used timestamps for API keys as of 2026-05 — track key usage in your secrets manager.

## Sub-accounts

- Sub-accounts are separate Vultr accounts with their own billing, API keys, and resources. They are Vultr's model for team isolation.
- Use sub-accounts to separate prod, stage, and dev if account-level blast-radius control is a requirement. A compromised prod API key cannot affect resources in a separate sub-account.
- Sub-accounts receive separate invoices. Billing is consolidated to the parent account, but resource spending is attributed per sub-account — useful for cost allocation by project or team.
- **Limitation:** Sub-accounts do not support shared resources (shared VPCs, shared Managed Databases) with the parent account. Isolation is complete — nothing can be shared.
- If granular team-level RBAC within a single account is required, Vultr cannot satisfy this requirement as of 2026-05. Hyperscalers (AWS IAM, GCP IAM, Azure RBAC) provide this; factor this into cloud selection for security-sensitive workloads.

## Audit log access

- Vultr does not provide a structured, searchable control-plane audit log (equivalent to AWS CloudTrail) as of 2026-05.
- Compensating controls:
  - Enable account-level email notifications for instance creation / deletion events.
  - Ship API key usage logs from your secrets manager and CI/CD system to a SIEM.
  - Use `vultr-cli` with `--output json` and pipe to a log aggregator for audit-trail approximation.
  - For instance-level actions (SSH logins, sudo activity), ship `/var/log/auth.log` and `/var/log/audit/audit.log` to a centralized log store (Grafana Loki, Datadog, OpenSearch).
- This is a material gap relative to hyperscaler audit capabilities. Design compensating controls explicitly; do not assume Vultr provides native audit.

## Public IP discipline

- Audit public IPs across the account regularly: `vultr-cli instance list --output json | jq '.[].main_ip'`.
- Remove public IPs from instances that have no legitimate reason for public reachability. Vultr allows disabling the public interface and using VPC-only.
- Every public IP on a production instance should have: a Firewall Group with explicit rules, DDoS Protection enabled, and a documented reason for the public IP in IaC.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Root account API key in CI/CD pipeline | Key leak = full account takeover, including billing access. Use a sub-account or dedicated key. |
| Shared API key across systems | Single revocation event takes down all systems at once; cannot attribute usage to a specific system. One key per purpose. |
| Password auth enabled on instances | SSH brute-force is the number one initial access vector in public cloud. SSH key-only always. |
| Firewall Group added after instance runs for a day | Every minute without a Firewall Group is internet-open. Attach at provision time via IaC. |
| 2FA disabled "for convenience" on the control panel | Control panel access without 2FA is one phished password from full account compromise. |
| SSH open to `0.0.0.0/0` | Even with key auth, exposing SSH to the internet invites key-cracking attempts and zero-day exploitation. Restrict to VPN/management CIDR. |
| API keys in environment variables baked at build time | Keys stored in container images, AMIs, or build artifacts persist long after rotation. Pull from secrets manager at runtime. |
| No key rotation on staff departure | Former employees retain access via API keys they set up. Rotate all keys on departure; document which keys belong to which person. |

## Security defaults

- 2FA on every control panel account (root + all sub-accounts).
- Firewall Group with default-deny inbound on every instance, attached at provision time.
- SSH key-only authentication; password auth disabled via cloud-init.
- No public IP on back-of-house instances.
- DDoS Protection enabled on every public-facing IP.
- API keys stored in a secrets manager; one key per service; rotated annually minimum.
- OS-level firewall (`ufw` or `iptables`) active as defense-in-depth behind the Firewall Group.
- Instance log forwarding to a centralized log store as a compensating audit control.

## Observability defaults

- Auth log monitoring (`/var/log/auth.log`): alert on repeated SSH failure or any login from a source IP not in the management CIDR.
- Failed API calls: if your secrets manager supports webhook logs, forward anomalous API usage patterns to a SIEM or alert channel.
- Firewall Group rule changes: not natively logged by Vultr. Use Terraform with a remote state and PR workflow so all rule changes go through code review and commit history.
- Instance create/delete: Vultr email notifications; wire the email to a shared security channel, not a personal inbox.

## Cost considerations

- 2FA, SSH key management, Firewall Groups, and API key rotation are all zero-cost security controls. There is no security tier or premium that unlocks additional features.
- Sub-accounts: no additional cost for creating sub-accounts. Billing rolls up to the parent.
- DDoS Protection is the only security-related line item ($10–$20/mo per IP depending on region). Enable it on public-facing IPs without exception.

## IaC hints

- Firewall Group: `vultr_firewall_group` + `vultr_firewall_rule` resources. Pin the group to each instance via `firewall_group_id` on `vultr_instance`.
- SSH keys: `vultr_ssh_key` resource stores the public key at the account level. Reference by ID in `vultr_instance.ssh_key_ids`.
- No Terraform resource for 2FA — this is a control panel operation performed once per user, not an IaC concern.
- API key management: Vultr does not expose API key CRUD via the API. Manage keys via the control panel; store them in a secrets manager outside IaC.
- DDoS Protection: `ddos_protection = true` on `vultr_instance`.

## Verification checklist

- [ ] 2FA enabled on the root account and all sub-accounts used by humans.
- [ ] Firewall Group with default-deny attached on every instance at provision time.
- [ ] SSH inbound restricted to management CIDR (not `0.0.0.0/0`).
- [ ] Password authentication disabled on every instance via cloud-init or startup script.
- [ ] No public IP on any database, cache, or internal application instance.
- [ ] DDoS Protection enabled on all public-facing IPs.
- [ ] API keys in a secrets manager; one key per purpose; creation date and owner documented.
- [ ] OS-level firewall (`ufw` / `iptables`) active as defense-in-depth layer.
- [ ] Instance auth logs shipped to a centralized log store.
- [ ] Public IP audit scheduled quarterly; undocumented IPs investigated.
