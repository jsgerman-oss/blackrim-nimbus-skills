---
name: scaleway-identity-and-security
description: Design or audit Scaleway identity, access, and security posture — IAM (Organizations, Projects, Applications, Groups, Policies), Secret Manager, Key Manager (KMS), Audit Trail, OAuth tokens, MFA, SOC 2 / ISO 27001 / HDS certifications. Use when writing policies, rotating secrets, scoping application access, or hardening an Organization.
---

# Scaleway Identity and Security

## When to use

- Writing or reviewing a Scaleway IAM Policy for an Application, Group, or User.
- Standing up a new Organization, Project, or service account (Application).
- Rotating, scoping, or auditing API keys and secrets.
- Configuring Secret Manager or Key Manager for a production workload.
- Auditing Scaleway Audit Trail events after an incident.
- Assessing compliance posture (SOC 2, ISO 27001, HDS) for a workload.

## Identity model

- **Humans → Scaleway IAM Users** in the Organization. Federate from an IdP via SAML/OIDC where supported, or use Scaleway's native MFA-protected accounts. No shared accounts.
- **Workloads → IAM Applications** (service accounts) in the Project that owns the resource. Each application gets its own API key. No sharing across projects or workloads.
- **Groups → IAM Groups** for batching humans or Applications with the same permission needs. Attach Policies to Groups to reduce duplication.
- **CI/CD → IAM Applications** with project-scoped policies. API keys for CI are stored as encrypted secrets in the CI system (e.g., GitHub Actions encrypted secrets) — not committed in code. Rotate at least quarterly.
- **Break-glass → Organization owner credentials** with MFA. Used only for actions that require elevated access; all use logged via Audit Trail.

## IAM policy discipline

- Default deny: every `Permission` in a Policy is an explicit allow.
- Scope Policies to the narrowest `Project` (or resource group) needed. Avoid Organization-wide policies unless the workload genuinely spans all projects.
- Prefer `Permission Sets` (pre-defined Scaleway action groups) over hand-crafting long action lists — they are version-stable and Scaleway-curated.
- Available permission set categories: `Compute` (Instances, Serverless), `Storage` (Object Storage, Block Storage), `Database` (Managed DB, Redis), `Network` (Load Balancers, VPC), `Secret` (Secret Manager), `IAM` (user/policy management), `Billing`, `Audit`.
- Review Policies quarterly: remove Applications that are no longer in use; revoke stale API keys.
- For cross-project access: create a Policy in the target Project that references the source Application as the Principal. Avoid Organization-level wildcards.

## API keys and secrets

- **Scaleway API key** (access key + secret key pair): generated per IAM Application. The secret key is shown only at creation — store immediately in Secret Manager.
- Rotate API keys: use `scw iam api-key create --application-id <id>` to generate a new key, update the consuming service, then delete the old key. Zero-downtime rotation is possible because multiple keys per Application are allowed during the rotation window.
- Key expiration: set an expiration date on API keys for CI workloads. Prevents indefinite access from forgotten keys.
- **Secret Manager**: Scaleway's managed secret store. Store all application secrets (DB passwords, third-party API keys, signing keys) here. Reference secrets by path in runtime configuration; never bake into container images or IaC state.
- Secret versions: Secret Manager supports multiple versions per secret. Deploy the new version, verify the consuming workload, then disable the old version.
- **Key Manager (KMS)**: customer-managed encryption keys for Object Storage CMEK, Block Storage CMEK, and future Managed Database integration. Separate keys by domain (storage / database / logs) — a single key compromise does not unlock all data.
- Key rotation: automatic annual rotation available for symmetric keys in Key Manager. Enable it; document the rotation policy in your compliance runbook.

## MFA and account hardening

- MFA mandatory for all human IAM Users with production access. Scaleway supports TOTP (authenticator apps); hardware key (FIDO2/WebAuthn) support — check current console capabilities.
- Organization owner account: dedicated email address (not a personal inbox), TOTP MFA, documented break-glass procedure.
- API keys for human accounts: avoid. Human operators should use the console (SSO-backed session tokens) rather than long-lived API keys. API keys are for Applications.
- Unused accounts: disable or delete IAM Users who have left the team. Review quarterly.

## Audit Trail

- Scaleway Audit Trail records control-plane API calls (IAM changes, resource creation/deletion, secret access) across the Organization.
- Enable retention: export Audit Trail events to Object Storage for long-term archival (Scaleway's default retention window is limited — verify current docs for your tier).
- Alert on: failed authentication attempts, policy changes, API key creation/deletion, secret version access outside business hours, Audit Trail export deletion.
- Forensic use: after an incident, correlate Audit Trail events by `api_key_id`, `user_id`, or `application_id` to reconstruct what was accessed and from where.
- Export format: JSON lines. Ingest into a SIEM (Elastic, Splunk, etc.) via Object Storage event trigger or a polling job.

## Compliance certifications

Scaleway holds the following certifications as of 2026 (verify currency with Scaleway's Trust Center):

- **ISO 27001**: Information security management. Covers Scaleway's Paris and Amsterdam data centers.
- **SOC 2 Type II**: Security, availability, and confidentiality controls. Report available under NDA.
- **HDS (Hébergeur de Données de Santé)**: French health-data hosting certification. Required for workloads processing personal health data in France. Kapsule, Instances, and key storage services are HDS-certified — verify per-product applicability.
- **GDPR**: Scaleway is EU-based; data processing agreements (DPA) available. Paris, Amsterdam, and Warsaw regions are within EU jurisdiction for GDPR data residency.
- **SecNumCloud**: Not currently held (as of 2026) — workloads requiring SecNumCloud for sovereign French government must use a different provider.

## OAuth and preview API tokens

- Scaleway provides short-lived JWT tokens for accessing some APIs (Serverless Functions, certain preview APIs) via OAuth flows. These are separate from IAM API keys.
- Treat OAuth tokens like secrets: store in Secret Manager or the session; do not log.
- JWT token expiry is short — implement refresh logic; do not cache without respecting `exp` claims.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Using the Organization root credentials for a service | Root credentials have full access; a leaked key = full Organization compromise. |
| One IAM Application shared across multiple services | Blast radius on key leak = all services. One Application per service. |
| API key with no expiration date for CI | Forgotten CI key from a deleted project remains valid forever. Set expiry. |
| Storing secrets in container env vars baked at build time | Image in registry = plaintext secrets. Use Secret Manager runtime injection. |
| Policy attached to Organization scope when Project scope suffices | Inadvertent access to other projects. Scope to Project always. |
| No MFA on Organization owner account | Phish the owner = full account. MFA mandatory. |
| Audit Trail events not exported | Evidence gone after the retention window. Export to Object Storage immediately. |
| Rotating API keys without a zero-downtime plan | Service outage during rotation. Create new key, update service, delete old key — in that order. |

## Defaults at Organization and Project bootstrap

- Organization owner: dedicated email, TOTP MFA enabled, break-glass procedure documented.
- Every Project: create a `project-admin` IAM Application with a scoped Policy for IaC (Terraform) operations; separate `service` Application per deployed workload.
- API keys: expiration set (30–90 days for CI; 365 days for long-lived service keys that have a rotation runbook).
- Secret Manager: provision in the same Project as the workload; store all secrets there before first deployment.
- Key Manager: create domain-specific keys (storage, database) if the workload handles regulated data. Enable auto-rotation.
- Audit Trail: configure export to an Object Storage bucket in a dedicated logging Project from day one — retroactive export is limited.
- Billing alerts: set a budget alert at 80% and 100% of expected monthly spend.

## Observability defaults

- Audit Trail events exported to Object Storage and ingested into a monitoring pipeline.
- Alert on: IAM policy changes, API key creation/deletion, Organization owner login, failed secret access.
- Secret Manager: monitor secret version access count anomalies via Cockpit (if available) or Audit Trail correlation.
- Key Manager: log every key use event; alert if a key is used by an unexpected Application ID.

## Cost considerations

- IAM Applications, Groups, Users, Policies: no charge.
- Secret Manager: billed per secret per month + per API call. Cheap at normal usage; bulk-access patterns (polling instead of caching) can spike API call costs.
- Key Manager: billed per key per month + per cryptographic operation. Group secrets under one CMEK where key-level audit granularity is not required.
- Audit Trail: export to Object Storage (storage cost) — minimal compared to the compliance value.

## IaC hints

- Terraform `scaleway/scaleway` ≥ 2.45: `scaleway_iam_application`, `scaleway_iam_api_key`, `scaleway_iam_policy`, `scaleway_iam_group`, `scaleway_iam_user`, `scaleway_secret`, `scaleway_secret_version`.
- Key Manager resources: `scaleway_key_manager_key` (verify resource name in current provider — provider coverage for KMS may be incomplete; fall back to `scw` CLI for key creation if needed).
- Never store the API secret key value in Terraform state output as a non-sensitive field. Mark as `sensitive = true`.
- Manage Policies as code; track changes in git. Policy drift (console changes not reflected in IaC) is a common audit finding.
- Pre-commit: use `tflint` + `checkov` on Scaleway Terraform to catch overly permissive policies before merge.

## Verification checklist

- [ ] No workload using Organization root credentials. Every service has its own IAM Application.
- [ ] MFA enabled on all human accounts with production access.
- [ ] API keys have expiration dates; rotation schedule documented.
- [ ] All secrets stored in Secret Manager; no hardcoded credentials in code, IaC state, or container images.
- [ ] Policies scoped to Project; no Organization-wide wildcards without documented justification.
- [ ] Key Manager CMEK on Object Storage and Block Storage for regulated data.
- [ ] Audit Trail export to Object Storage configured from day one.
- [ ] Quarterly review of active Applications, API keys, and Group memberships scheduled.
- [ ] Compliance certification applicability verified per product and region (especially HDS for health data).
