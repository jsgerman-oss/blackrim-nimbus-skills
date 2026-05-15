---
name: tencent-identity-and-security
description: Design or audit Tencent Cloud identity, access, and security posture — CAM (users, groups, roles, policies), SSO and federated identity, SSM Secrets Manager, KMS (Standard + HSM), Cloud Firewall, CWP (Cloud Workload Protection), CSI (Cloud Security Inspection), CloudAudit. Use when writing policies, scoping roles, rotating secrets, standing up SSO, or hardening an account.
---

# Tencent Identity and Security

## When to use

- Writing or reviewing a CAM policy, role, or trust relationship.
- Configuring SSO federation from an enterprise IdP to Tencent Cloud.
- Rotating, scoping, or auditing secrets and encryption keys.
- Setting up account-wide guardrails (CloudAudit, Cloud Firewall, CWP).
- Investigating an incident — CloudAudit forensics, CAM access analysis.
- Classifying a workload under MLPS (Multi-Level Protection Scheme) and identifying baseline controls.

## Identity model

- **Humans → SSO federation via CAM Identity.** Federate from your IdP (corporate SAML 2.0 / OIDC provider). No long-lived sub-accounts with static SecretId/SecretKey for human access.
- **Workloads → CAM roles assumed by the runtime.** CVM instance roles, TKE service-account token projection (SVTP), SCF function roles. No static credentials in code or config.
- **External CI/CD → OIDC trust with CAM role.** GitHub Actions, GitLab CI, or Jenkins can assume a CAM role via OIDC — no SecretId/SecretKey stored in CI secrets.
- **Break-glass → temporary STS credentials.** `tccli sts assume-role` with explicit session duration (1 hour maximum for sensitive operations), audit-logged to CloudAudit.

## CAM policy discipline

- Default deny. Every `Allow` statement must be justified.
- **Resource-level ARNs**: scope policies to specific `qcs::` ARNs where the service supports resource-level permissions. Avoid `resource: *` except for services that do not support resource-level.
- **Conditions**: use CAM condition keys — `qcs:vpc`, `cam:sts:RoleArn`, `cos:x-cos-server-side-encryption`, request IP range — to add context beyond the principal and action.
- **Principle of least privilege**: start with read-only and expand on observed access denials. Never start with broad write then try to trim.
- **Inline vs managed policies**: prefer managed policies checked into IaC over inline policies. Inline policies drift; managed policies are versioned and reviewable.
- **Permission boundaries**: apply to developer-created sub-accounts or roles to cap maximum privilege even if they attach a broader policy.
- Regular access reviews: export CAM access reports quarterly and revoke unused sub-accounts and roles.

## CAM roles — the only acceptable credential for workloads

- CVM instance role: attach via the instance profile. The CVM metadata service (`metadata.tencentyun.com/latest/meta-data/cam/security-credentials/`) vends temporary credentials automatically. Applications call the SDK; no credential management code needed.
- TKE Service Account Token Volume Projection (SVTP): analogous to AWS IRSA. Kubernetes pods receive a projected service-account token; the SDK exchanges it for a CAM role temporary credential scoped to that service account.
- SCF execution role: every function has a configured execution role. Scope it to exactly what the function needs.
- Never store a SecretId/SecretKey in a pod spec, SCF environment variable, Dockerfile layer, or CI pipeline secret. If you see one, rotate it immediately.

## SSO federation

- Tencent Cloud supports SAML 2.0 federation for role-based access. Configure the IdP (Okta, Entra ID, ADFS, Google Workspace) as a SAML identity provider in CAM, then define role trust policies referencing the IdP's principal.
- Assign permission sets (via managed policies attached to the federated role) aligned to job functions: `Admin`, `PowerUser-Networking`, `ReadOnly-Audit`, `DeveloperWriteExcludeProd`.
- Session duration: set appropriate role session durations (4–8 hours for developers, 1 hour for sensitive admin roles).
- OIDC provider configuration: for OIDC-based federation (GitHub Actions, ArgoCD), register the provider's JWKS URI in CAM and scope the trust condition on `sub` claim.

## KMS

- **Customer-managed CMKs** for any data you need to audit, rotate, or revoke independently: COS bucket encryption, CBS volume encryption, CDB instance encryption, application secrets.
- **Standard KMS CMK**: software-backed. Suitable for most workloads.
- **HSM-backed CMK (KMS Exclusive)**: hardware security module backing. Required for financial industry workloads, MLPS Level 3+ requirements, or workloads with explicit HSM mandates.
- Key policy: explicit `Principal` ARNs for who can use vs who can admin the key. No `cam:*` on `*`.
- Automatic rotation: enable annual rotation for symmetric CMKs. Application-layer key versioning is your responsibility; KMS rotation handles the key material.
- Separate CMKs by domain: one for databases, one for object storage, one for secrets. A single compromised CMK unlocks only one domain.
- Key deletion: minimum 7-day scheduled-deletion waiting period. Never delete a CMK without confirming no data is still encrypted under it.

## SSM (Secrets Manager)

- Store all database credentials, API keys, JWT signing keys, and third-party tokens in **SSM Secrets Manager** (or **SSM Parameter Store** for simpler config-like secrets).
- Reference secrets from workloads by secret ARN / name; never hard-code values.
- Rotation: configure automatic rotation via a rotation function for supported engines (CDB passwords, Redis auth tokens). For unsupported engines, implement a rotation SCF.
- Audit: CloudAudit logs every `GetSecretValue` call. The list of callers should match the expected set of services. Alert on unexpected callers.

## Cloud Firewall (CFW)

- **Internet boundary protection**: CFW sits between public internet traffic and your VPC resources. Operates on CLB EIPs and NAT Gateway. Enforces access control based on FQDN, IP, protocol, and application identification.
- **VPC boundary protection**: east-west traffic inspection between VPCs in a CCN topology.
- **Egress control**: FQDN-based allow-lists for outbound traffic from CVM / SCF via NAT. Block all egress except explicitly allowed destinations for sensitive workloads.
- Modes: **monitor-only** first, then enforce. Premature enforcement breaks legitimate traffic.
- Intrusion prevention: CFW includes an IPS engine with Tencent threat intelligence. Enable for internet-facing workloads.

## CWP (Cloud Workload Protection)

- Install the **CWP agent** on every production CVM instance. Provides: vulnerability scanning, file integrity monitoring, malware detection, brute-force login detection, process behavior monitoring.
- CWP editions: **Basic** (free, limited features) vs **Professional** / **Ultimate** (paid, full detection + response). Use Professional or better for production.
- Vulnerability management: CWP scans installed packages and reports CVEs. Establish a patch cadence — critical CVEs within 72 hours, high within 14 days.
- File integrity: configure baseline alerts on `/etc/passwd`, `/etc/sudoers`, webroot directories, and application config files. Unexpected changes are high-confidence incident indicators.

## CSI (Cloud Security Inspection) / Cloud Security Center

- Tenant-wide posture assessment: scans CAM policies for over-privilege, COS buckets for public access, security group rules for exposure, and CloudAudit for anomalous API activity.
- Use CSI findings as a pre-launch security gate and as a quarterly review cadence item.
- Treat `CRITICAL` and `HIGH` CSI findings as P1 / P2 remediation items, not suggestions.

## CloudAudit

- Enable CloudAudit in every active region. Store logs in a **dedicated COS bucket** with:
  - KMS CMK encryption.
  - Versioning enabled.
  - Object Lock (compliance mode, minimum 90-day retention for security-relevant logs).
  - No delete permission for the service role that writes audit logs.
- Track data events (COS object reads, CDB query events) on buckets and databases that hold regulated data. Data events cost more; scope tightly.
- CloudAudit log integrity: enable log-file validation so you can detect tampering.
- Ship CloudAudit to CLS for queryable search and alerting on anomalous API calls (e.g., `DeleteBucket`, `StopInstances` in prod, `CreateUser` outside change-window).

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Static SecretId/SecretKey in a workload | Key leaks via code repo, log files, or environment variable dump. Use CAM roles. |
| `action: *` policies "for development convenience" | Becomes permanent. Start tight; expand on observed denies. |
| Root account used for day-to-day operations | Root credentials are the ultimate blast radius. Federate; restrict root to account management tasks only. |
| Shared sub-account credentials across developers | No auditability per individual. No revocation granularity. Individual federated identities. |
| CloudAudit disabled "to save storage cost" | CloudAudit costs are trivial; incident investigations without it are impossible. |
| SSM secrets referenced by value in IaC outputs | Secret appears in Terraform state. Mark outputs `sensitive = true`; reference by ARN. |
| KMS CMK deleted without confirming decryptable data | All data encrypted with that CMK becomes permanently unreadable. Verify before deletion. |
| CWP not installed on production CVM | Blind to malware, brute-force, and lateral movement. Install on every production instance. |

## MLPS (Multi-Level Protection Scheme) alignment

MLPS is China's mandatory cybersecurity framework for information systems. Production systems in China must be classified and filed with the Ministry of Public Security.

- **Level 1**: lowest risk, minor personal impact. Minimal baseline.
- **Level 2**: general internet services, internal business systems. Baseline for most production workloads. Requires: identity management, access control, audit logging (CloudAudit), communication security (TLS), data backup, intrusion detection (CWP).
- **Level 3**: important national information systems, large-scale internet platforms. Adds: mandatory HSM (KMS Exclusive), enhanced intrusion detection, security management center, physical security requirements.
- **Level 4 / 5**: critical infrastructure. Requires separate engagement with MPS and Tencent security team.

For most startups and businesses: **file at Level 2**. MLPS filing (grading and registration) is a legal requirement, not optional. Engage a qualified MLPS assessment vendor before launch.

## Defaults at account bootstrap

- Root account: hardware MFA, no programmatic API keys, used only for billing and account management.
- Sub-account creation: only via SSO federation for humans. Service sub-accounts only when SVTP / instance role is not available for the specific use case.
- CloudAudit: enabled in all active regions before any workload is deployed.
- CWP: enabled on all production CVM instances at launch.
- Cloud Firewall: deployed in monitoring mode from day one; enforcement after reviewing 48 hours of traffic.
- CSI: baseline scan completed before first production go-live.

## Observability defaults

- CloudAudit logs to CLS with alerts on: `DeleteBucket`, `DeleteInstance`, `CreateUser`, `AttachRolePolicy` (broad policy attachment), any `*Destroy*` action during production hours.
- CWP security events to a notification channel (WeCom / email) — high-severity events within 5 minutes.
- KMS: CloudAudit alert if a CMK is used by an unexpected caller (mismatched service principal).
- Failed console login alerts to a security channel.

## Cost considerations

- CloudAudit: management events are included; data events are priced per 100,000 events. Scope data events to regulated resources only.
- KMS: charged per CMK per month + per cryptographic operation. Group by domain rather than per-resource to limit key count.
- CWP Professional: per-CVM per-month subscription. Budget for all production instances; dev instances can use Basic.
- Cloud Firewall: priced on bandwidth tier. Right-size the firewall bandwidth to peak traffic, not theoretical max.

## IaC hints

- Terraform: `tencentcloud_cam_role`, `tencentcloud_cam_policy`, `tencentcloud_cam_role_policy_attachment`, `tencentcloud_kms_key`, `tencentcloud_ssm_secret`.
- For CAM policies, write policy JSON as a Terraform `data "tencentcloud_cam_policy_document"` data source rather than raw JSON strings — typed, lintable, diffable.
- CAM roles and KMS keys belong in a bootstrap / security workspace separate from application workspaces. Keys and roles outlive applications.
- Pre-commit: use `tfsec` or `checkov` with Tencent Cloud rules to lint CAM policies in CI before `apply`.

## Verification checklist

- [ ] No static SecretId/SecretKey in any workload — all using CAM roles or SVTP.
- [ ] Root account MFA enforced; no programmatic access keys on root.
- [ ] Every CAM policy has explicit resource ARNs and at least one condition where applicable.
- [ ] CloudAudit enabled in all regions; logs encrypted and retention-locked in COS.
- [ ] KMS CMKs per data domain; key policies scoped to specific service principals.
- [ ] CWP agent installed on all production CVM instances.
- [ ] Cloud Firewall deployed; egress rules documented and minimal.
- [ ] SSM Secrets Manager used for all credentials; rotation configured.
- [ ] CSI posture assessment reviewed before go-live and quarterly thereafter.
- [ ] For China accounts: MLPS classification filed and Level 2 baseline controls documented.
