---
name: ibm-identity-and-security
description: Design or audit IBM Cloud identity and security posture — IAM Account / ResourceGroup / Service policies, Access Groups, Trusted Profiles for OIDC and compute identity, Secrets Manager, Key Protect (BYOK), Hyper Protect Crypto Services (KYOK / FIPS 140-2 Level 4), Security and Compliance Center, Activity Tracker, App ID. Use when writing IAM policies, scoping Access Groups, rotating secrets, managing encryption keys, or hardening account security posture.
---

# IBM Cloud Identity and Security

## When to use

- Writing or reviewing IAM access policies, Access Groups, or Trusted Profiles.
- Setting up a new IBM Cloud account or enterprise account hierarchy.
- Deciding between Key Protect (BYOK) and Hyper Protect Crypto Services (KYOK).
- Rotating, scoping, or auditing secrets and encryption keys.
- Running a Security and Compliance Center (SCC) profile scan and remediating findings.
- Hardening an account against credential theft, privilege escalation, and audit gaps.

## IBM Cloud IAM model

IBM Cloud IAM has three levels of authorization scope:

1. **Account level** — policies that apply across the entire account.
2. **Resource Group level** — policies scoped to a resource group (the primary blast-radius boundary for IBM Cloud resources).
3. **Service / Resource instance level** — policies scoped to a specific service instance or resource type.

Least privilege means granting at the most specific level possible. A `Manager` role on a specific Secrets Manager instance is better than `Manager` on all Secrets Manager instances in the account.

### IAM identity types

| Identity type | Use |
| --- | --- |
| **IBMid user** | Human operators; federated via your IdP (Okta, Azure AD, Ping) using IBMid federation or direct SAML. |
| **Service ID** | A non-human identity for applications or automation that cannot use Trusted Profiles. Use with short-lived API keys rotated via Secrets Manager. |
| **Trusted Profile — Compute Identity** | For workloads running on IBM Cloud compute (VPC VSIs, Code Engine, IKS/ROKS pods). The workload acquires an IAM token from the instance metadata service — no API key needed. |
| **Trusted Profile — OIDC / Federated Identity** | For workloads outside IBM Cloud (GitHub Actions, GitLab CI, external OIDC provider). The external JWT is exchanged for an IAM token via Trusted Profile OIDC claims. |

**Rule of thumb:** Use Trusted Profiles wherever the compute or CI/CD platform supports it. Fall back to Service IDs with rotated API keys only when Trusted Profiles are not available.

### Access Groups

Access Groups are the correct way to manage IAM policies at scale on IBM Cloud. A policy is attached to an Access Group; users, Service IDs, and Trusted Profiles are members.

- Never assign IAM policies directly to individual users. Assign users to Access Groups.
- Design Access Groups around job functions or least-privilege permissions, not org chart structure.
- Example Access Group hierarchy:
  - `ag-platform-admins` — `Administrator` on all services in the account.
  - `ag-network-operators` — `Operator` on VPC resources, `Editor` on Transit Gateway.
  - `ag-app-deployers-prod` — `Writer` on IKS clusters in `rg-prod`; `Reader` on COS buckets in `rg-prod`.
  - `ag-readonly-audit` — `Viewer` on all services in the account.
- Dynamic membership rules: Access Groups support dynamic rules based on IdP attributes (department, role claim) — prefer dynamic assignment over manual management.

### Trusted Profiles for Compute Identity

Trusted Profiles eliminate the need for API keys in workloads running on IBM Cloud compute.

- **VPC VSI**: instance metadata service provides an IAM-compatible token bound to the Trusted Profile. Application calls `http://169.254.169.254/instance_identity/v1/token` and exchanges it for an IAM token via the IAM `iam.cloud.ibm.com/identity/token` endpoint.
- **Code Engine**: bind the Code Engine project to a Trusted Profile; all Code Engine apps, jobs, and functions in the project inherit the profile's IAM roles.
- **IKS / ROKS pods**: configure the cluster's Pod IAM integration (IBM Cloud's analog of IRSA). The pod's service account is bound to a Trusted Profile; the pod acquires an IAM token without a stored API key.
- Claims-based matching: define which compute resources can assume the Trusted Profile using CRN or tag-based conditions — prevents lateral movement between environments.

## Key management — BYOK vs KYOK

| Approach | Service | When to use |
| --- | --- | --- |
| IBM-managed key | Default (no action required) | Development, non-regulated workloads. IBM rotates and controls the key. |
| BYOK (Bring Your Own Key) | **Key Protect** | Production workloads requiring customer key control, audit, and rotation. FIPS 140-2 Level 1 HSM. |
| KYOK (Keep Your Own Key) | **Hyper Protect Crypto Services (HPCS)** | Regulated workloads requiring FIPS 140-2 Level 4, financial services, FedRAMP High, EU data sovereignty. Customer controls the HSM master key; IBM cannot access plaintext keys. |

### Key Protect (BYOK)

- Root key: one root key per domain (database encryption, storage encryption, secrets encryption, log encryption) — limits blast radius of a key compromise.
- Customer-managed rotation: set 90-day automatic rotation; ICD, COS, and Block Storage automatically re-wrap data keys.
- Key states: enabled → disabled (data unreadable but key exists) → deleted (data unrecoverable). Test the disable/re-enable path before relying on it.
- IAM authorization: grant `Reader` on Key Protect to each service that needs to wrap/unwrap data keys (e.g., `ibm_iam_authorization_policy` for COS → Key Protect).

### Hyper Protect Crypto Services (HPCS)

- Dedicated HSM: each HPCS instance is a dedicated FIPS 140-2 Level 4 HSM — physically tamper-evident.
- Master key initialization: requires smart card ceremony (Crypto Unit Administrators with smart cards). IBM cannot retrieve or reset the master key.
- GREP11 API: HPCS exposes EP11 (Enterprise PKCS#11) API for cryptographic operations from applications — use for key wrapping, signing, and random generation in regulated workloads.
- Financial Services-validated: HPCS is available in Financial Services-validated regions (`us-south`, `us-east`, `eu-de`, `eu-gb`).
- Use HPCS when: SOX, FedRAMP High, DISA IL5, EU banking regulators (EBA, BaFin), or contractual key custody requirements apply.

## Secrets Manager

IBM Cloud Secrets Manager is the managed secrets service — analogous to HashiCorp Vault or AWS Secrets Manager.

- Secret types: arbitrary, username/password, IAM credentials (Service ID API keys), public/private certificates, key-value.
- IAM credentials type: Secrets Manager generates and rotates Service ID API keys on your behalf; consumers fetch the current key from Secrets Manager at runtime.
- Auto-rotation: configure TTL and rotation schedule per secret. Secrets Manager rotates and notifies consumers via Event Notifications.
- Private endpoint: always consume Secrets Manager from VPC workloads via the private endpoint.
- Key Protect integration: Secrets Manager encrypts secrets with a Key Protect root key (or HPCS root key for KYOK).
- Access policy: grant consuming services the `SecretsReader` role on Secrets Manager (or on specific secret groups). Never grant `Manager` to workloads.
- Secret groups: organize secrets by environment or team; Access Group policies can be scoped to specific secret groups.

## Security and Compliance Center (SCC)

SCC is IBM Cloud's continuous compliance posture manager — defines profiles (control sets), runs scans against your IBM Cloud resources, and produces findings with remediation guidance.

### Profiles available

| Profile | Framework |
| --- | --- |
| CIS IBM Cloud Foundations Benchmark | CIS-derived hardening baseline for IBM Cloud accounts |
| IBM Cloud Framework for Financial Services | IBM FS Cloud controls for regulated financial workloads |
| NIST SP 800-53 | US federal security controls |
| ISO 27001 | Information security management standard |
| SOC 2 | Service Organization Control 2 |
| PCI DSS | Payment Card Industry Data Security Standard |

### Defaults

- Enable SCC at account creation; attach the CIS IBM Cloud Foundations Benchmark profile as the minimum baseline.
- For financial services workloads: attach the IBM Cloud Framework for Financial Services profile and resolve all `HIGH` findings before production launch.
- Schedule scans daily; route findings to a dedicated security team channel via Event Notifications.
- SCC integrates with Activity Tracker and IBM Cloud Monitoring — findings can trigger automated remediation workflows.

## Activity Tracker

Activity Tracker records all management-plane events for IBM Cloud services — who did what, when, on which resource. It is the audit log for IBM Cloud.

- Route all Activity Tracker events to a central COS bucket with Object Lock (WORM) for compliance.
- Retain for at least 1 year (regulatory minimum for many frameworks); 7 years for FFIEC / financial services.
- Activity Tracker can route events to IBM Cloud Logs for search and correlation.
- Key events to alert on: IAM policy changes, Access Group membership changes, Key Protect key deletion/disable, Security Group rule changes, VPN gateway config changes.

## App ID

App ID is IBM Cloud's application-layer identity service for adding user authentication and authorization to applications.

- Use for: adding login flows to web apps and APIs; managing end-user identities separate from IBM Cloud IAM; supporting social login (Google, Facebook) or SAML federation.
- Not a replacement for IAM — App ID manages application user identities; IAM manages IBM Cloud resource access.
- Token customization: inject application-specific claims into the identity token for RBAC inside the application.
- MFA: enforce for all App ID users in production — TOTP or email OTP.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Long-lived API key stored as a Kubernetes secret | No rotation, no audit trail tying it to a workload. Use Trusted Profiles for pod IAM. |
| IAM policy assigned directly to a user | Policy must be managed per-user; Access Groups scale; individual assignments don't. |
| `Administrator` role on all IBM Cloud services for a CI service account | CI pipeline compromise = full account takeover. Scope to minimum required roles per resource group. |
| Root account (account owner) used for day-to-day operations | No MFA requirement on root by default for some actions; use a dedicated admin user. Enable IBMid MFA. |
| Key Protect root key shared across all services | Single key compromise exposes all encrypted data. One key per domain. |
| Secrets in environment variables baked into container images | Image layer contains the secret in plaintext. Use Secrets Manager and fetch at runtime. |
| SCC scans disabled to avoid findings | Findings are the point. Running with SCC off removes your only continuous compliance signal. |
| Trusted Profile with wildcard resource condition | Any compute resource can assume the profile. Use CRN or tag-based conditions to scope to specific instances or environments. |

## Defaults at account bootstrap

- IBMid MFA: enable for all account users (`ibmcloud iam account-settings` → `mfa=TOTP`). Hardware FIDO2 token preferred for account owner and platform admins.
- Access Groups: create before inviting users. Never let users accumulate direct IAM policies.
- Resource Groups: create separate resource groups for each environment and application (`rg-prod-webapp`, `rg-stage-webapp`). Default resource group is for nothing — put everything somewhere intentional.
- Activity Tracker: instance in every region where workloads run; route events to a central COS bucket.
- SCC: enable at account creation; attach CIS IBM Cloud Foundations Benchmark immediately.
- Trusted Profiles: create for each distinct workload before deploying compute.
- Key Protect: create instance and root keys before provisioning any data-at-rest resources.
- Secrets Manager: create instance; configure Key Protect integration for envelope encryption of secrets.

## Observability defaults

- Activity Tracker events to COS (long-term) and IBM Cloud Logs (searchable 30-day window).
- IBM Cloud Monitoring: alert on IAM policy changes, failed login attempts (via Activity Tracker → Event Notifications), SCC finding count increase.
- Secrets Manager: alert on secret expiry approaching (30 days out); failed rotation attempts.
- Key Protect: alert on key state changes (disabled, deleted) via Event Notifications.

## Cost considerations

- Key Protect: billed per key version per month (~$1/key/month) plus API call volume. Group keys by domain rather than per-resource to control key count.
- HPCS: higher cost than Key Protect (dedicated HSM) — justified only when FIPS 140-2 Level 4 or KYOK is a hard requirement.
- Secrets Manager: billed per active secret per month. Review secret count quarterly; delete unused secrets.
- SCC: billed per resource evaluation. Profile scope and scan frequency drive cost — daily scans across all resources are typical.
- Activity Tracker: billed per GB of events ingested to storage. High-volume accounts (many API calls) should set up log routing rules to filter noise before storage.

## IaC hints

- Terraform resources: `ibm_iam_access_group`, `ibm_iam_access_group_policy`, `ibm_iam_access_group_members`, `ibm_iam_trusted_profile`, `ibm_iam_trusted_profile_claim_rule`, `ibm_iam_trusted_profile_link`, `ibm_resource_instance` (Key Protect, HPCS, Secrets Manager, SCC).
- Key Protect: `ibm_kms_key` for root keys; `ibm_iam_authorization_policy` to authorize COS / ICD to use the key.
- Access Group policies: use `ibm_iam_access_group_policy` with `resource_attributes` to scope to resource groups, specific service instances, or resource types.
- Trusted Profiles: `ibm_iam_trusted_profile_claim_rule` with `type = "VSI"` for compute identity; `type = "Profile-OIDC"` for external IdP/CI claims.
- Account settings: `ibm_iam_account_settings` for MFA enforcement, session length, IP restrictions.
- Do not hard-code API keys in Terraform variables — use environment variable injection (`IC_API_KEY`) or fetch from Secrets Manager in the pipeline.

## Verification checklist

- [ ] No direct IAM policies on individual users — all access via Access Groups.
- [ ] No long-lived API keys in compute workloads — Trusted Profiles or rotating Service ID keys via Secrets Manager.
- [ ] MFA enforced for all account users (TOTP minimum; hardware token for admins).
- [ ] Key Protect root keys created per domain (database, storage, secrets, logs); HPCS for KYOK-required workloads.
- [ ] Secrets Manager holds all application secrets; rotation schedule defined and tested.
- [ ] SCC with CIS IBM Cloud Foundations Benchmark attached and scans running.
- [ ] Activity Tracker instances in all active regions; events shipped to WORM-protected COS.
- [ ] Trusted Profiles scoped with CRN or tag conditions — not wildcard compute.
- [ ] IAM authorization policies created for all BYOK/KYOK integrations (COS, ICD, Block Storage → Key Protect).
- [ ] At least quarterly access review: who is in which Access Group, what roles do they have.
