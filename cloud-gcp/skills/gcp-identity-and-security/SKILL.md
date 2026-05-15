---
name: gcp-identity-and-security
description: Design or audit GCP identity, access, and security posture — Cloud IAM (allow + deny policies, conditions), Workload Identity Federation for non-GCP CI, Workload Identity for GKE, Secret Manager, Cloud KMS (CMEK + EKM), Security Command Center, BeyondCorp Enterprise, Binary Authorization, Org Policies. Use when writing IAM bindings, configuring Workload Identity, rotating secrets, scoping service accounts, or hardening an organization.
---

# GCP Identity and Security

## When to use

- Writing or reviewing IAM allow policies, deny policies, or trust configurations.
- Configuring Workload Identity Federation so a GitHub Actions or GitLab pipeline authenticates to GCP without a service-account key file.
- Setting up Workload Identity on GKE so pods assume a GCP service account without a mounted key.
- Auditing service-account key exposure or over-privileged IAM bindings.
- Standing up Org Policy constraints for an organization or folder.
- Rotating, scoping, or auditing secrets and encryption keys.

## Identity model

- **Humans → Cloud Identity or Google Workspace + IAM.** Use Google Groups for role binding rather than individual user accounts wherever possible. Never bind roles to `allUsers` or `allAuthenticatedUsers` on production resources.
- **Workloads on GCP (GCE, GKE, Cloud Run, etc.) → attached service accounts.** Each workload gets its own dedicated service account with only the IAM roles it needs.
- **Workloads outside GCP (GitHub Actions, GitLab CI, Jenkins, Terraform Cloud) → Workload Identity Federation.** Exchange a short-lived OIDC token from the CI provider for a short-lived GCP access token. No service-account key files, ever.
- **GKE workloads → Workload Identity.** Kubernetes service accounts annotated with a GCP service account. The GKE metadata server exchanges the pod's Kubernetes service account token for GCP credentials.
- **Break-glass access → short-lived impersonation.** Privileged roles are not granted to humans directly. They're granted to a group used only in emergencies, with all accesses logged in Cloud Audit Logs.

## IAM policy discipline

- **Principle of least privilege.** Grant only the roles needed for the specific task; prefer predefined roles over primitive roles (`roles/viewer`, `roles/editor`, `roles/owner`). Reserve primitive roles for bootstrapping only.
- **Resource-level bindings where supported.** Bind IAM at the lowest level possible: bucket-level for Cloud Storage, dataset-level for BigQuery, instance-level for Cloud SQL, topic-level for Pub/Sub.
- **IAM Conditions** for context-aware access: restrict by `resource.name` pattern, `request.time`, `api.getAttribute('iam.googleapis.com/modifiedGrantsByRole', [])` for deny policies, or `request.auth.claims.email` for federated identities.
- **IAM Deny policies** to create hard blocks that override allow policies: deny `roles/iam.serviceAccountKeyAdmin` to everyone except the break-glass group at the org level.
- **No primitive `roles/owner` or `roles/editor` on service accounts.** These are immediate findings in any security review.
- **Avoid granting `iam.serviceAccountTokenCreator`** broadly — it allows impersonation of any service account in the project.

## Workload Identity Federation (for external workloads)

Workload Identity Federation eliminates service-account key files for CI/CD pipelines, on-premises workloads, and third-party services:

1. Create a **Workload Identity Pool** in the project that hosts the service account.
2. Add a **provider** matching the OIDC or SAML issuer of the external IdP (e.g., `https://token.actions.githubusercontent.com` for GitHub Actions).
3. Set an **attribute mapping** to translate claims (`google.subject = assertion.sub`); set an **attribute condition** to restrict which subjects can authenticate (`attribute.repository == "org/repo"`).
4. Grant the external identity `roles/iam.workloadIdentityUser` on the target service account, scoped to the specific provider identity (e.g., `principalSet://iam.googleapis.com/projects/.../locations/global/workloadIdentityPools/.../attribute.repository/org/repo`).
5. In the CI pipeline, use `google-github-actions/auth` (or equivalent) with `workload_identity_provider` and `service_account` — no stored JSON key.

## Workload Identity for GKE

1. Enable Workload Identity on the cluster: `workload_pool = "<project>.svc.id.goog"`.
2. Create a Kubernetes service account (KSA) and annotate it: `iam.gke.io/gcp-service-account: <gcp-sa>@<project>.iam.gserviceaccount.com`.
3. Grant `roles/iam.workloadIdentityUser` on the GCP service account to the principal `serviceAccount:<project>.svc.id.goog[<namespace>/<ksa-name>]`.
4. Reference the KSA in the Pod spec. The GKE metadata server returns GCP credentials automatically.
5. Never mount a key file as a Kubernetes Secret — this pattern is explicitly prohibited.

## Cloud KMS

- **CMEK (Customer-Managed Encryption Keys):** supply a Cloud KMS key to encrypt Cloud Storage buckets, BigQuery datasets, Persistent Disks, Spanner, Cloud SQL, Pub/Sub, and more. Required for any workload with key-revocation or audit requirements.
- **EKM (External Key Manager):** integrate with Thales, Fortanix, or other partners for keys that live outside GCP. Required for certain compliance regimes (FedRAMP High, regulated financial).
- Key ring and key organization: one key ring per project (or per environment); one key per service domain (storage, database, logging). Cross-domain key sharing undermines audit isolation.
- Key rotation: automatic rotation enabled for symmetric keys (90-day period is a common default; align with your compliance posture).
- IAM on keys: `roles/cloudkms.cryptoKeyEncrypterDecrypter` granted to service agents only; `roles/cloudkms.admin` restricted to the security team. Never grant key admin to the same SA that uses the key.
- Key version destruction: requires a pending deletion period (7–90 days). Audit before destroying — you cannot recover data after the key is gone.

## Secret Manager

- Store all secrets (API keys, DB passwords, JWT signing keys, OAuth client secrets) in Secret Manager.
- Reference secrets from compute via the Secret Manager API at runtime, or mount as volumes / environment variables in Cloud Run, Cloud Functions, and GKE.
- Rotation: use automatic rotation with a Pub/Sub notification that triggers a Cloud Function to rotate and rewrite the secret version. At minimum, document a manual rotation runbook.
- Access audit: `secretmanager.versions.access` events in Cloud Audit Logs identify every secret read. Alert on reads from unexpected service accounts.
- IAM: grant `roles/secretmanager.secretAccessor` to the service account that needs the secret; never `roles/secretmanager.admin` to a workload SA.
- Regional secrets: choose the region that matches your compute location to avoid cross-region egress.

## Security Command Center

- Enable SCC at the organization level; tier choice depends on budget and compliance needs.
- Standard tier: basic asset discovery, vulnerability findings from Web Security Scanner, IAM anomalies.
- Premium tier: Event Threat Detection (ETL), Container Threat Detection, Virtual Machine Threat Detection, Security Health Analytics continuous posture checks, and compliance reporting (CIS, PCI DSS, NIST 800-53, ISO 27001).
- Export findings to Pub/Sub and route to your SIEM (Chronicle, Splunk, Elastic).
- Findings SLA: CRITICAL findings require same-day triage; HIGH findings within the sprint.

## BeyondCorp Enterprise

- Zero-trust access to internal web applications and Cloud Console without a VPN.
- IAP (Identity-Aware Proxy): protect Cloud Run services, GKE workloads behind an ILB, and GCE VMs with an IAP-enabled TCP-forwarding tunnel. Access requires a Google identity + access level (device policy, network).
- Access levels: define device-trust requirements (OS version, disk encryption, endpoint verification agent) so only managed devices reach sensitive applications.
- Context-aware access applies to Google Workspace admin console and GCP Console access as well.

## Binary Authorization

- Enforce attestation-based admission control on GKE clusters and Cloud Run.
- Require attestations from trusted attestors (e.g., Cloud Build signing after a passing build, Vulnerability Scanning) before any image is deployed to prod.
- Policy: `requireAttestation` in `ENFORCED` mode for prod; `AUDIT` mode (dry-run with logging) for staging to surface violations before enforcement.
- Attestors: use Cloud KMS asymmetric keys to sign attestations; only the build pipeline's service account can create attestations.

## Org Policies

Critical constraints to enable at the organization level:

- `constraints/iam.disableServiceAccountKeyCreation` — prevent any user from creating service-account key files.
- `constraints/iam.disableServiceAccountKeyUpload` — prevent uploading external keys to service accounts.
- `constraints/compute.requireOsLogin` — enforce OS Login on all Compute Engine instances.
- `constraints/compute.vmExternalIpAccess` — restrict which projects can create instances with external IPs.
- `constraints/storage.publicAccessPrevention` — prevent public Cloud Storage buckets across the org.
- `constraints/compute.restrictCloudNatUsage` — limit Cloud NAT to approved VPCs.
- `constraints/gcp.resourceLocations` — restrict resource creation to approved regions.
- `constraints/iam.allowedPolicyMemberDomains` — restrict IAM bindings to identities within your Cloud Identity or Workspace domain.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Service-account key file in a GitHub secret | Key is long-lived, hard to rotate, one leak = persistent GCP access. Use Workload Identity Federation. |
| `roles/owner` on a workload service account | That SA can modify IAM on any resource in the project, including granting itself arbitrary access. Scope down immediately. |
| Binding IAM at the project level when resource-level is possible | Grants access to all resources of that type. Bind at the resource level. |
| Shared service account across multiple workloads | A compromise of one workload's credentials grants access to everything the SA touches. One SA per workload. |
| Service accounts without any Org Policy restricting key creation | Any developer can create a key and export it. Enable `iam.disableServiceAccountKeyCreation`. |
| CMEK key deleted before encrypted data is migrated | Data is permanently unrecoverable. Destruction is irreversible. |
| SCC findings aging without triage | CRITICAL findings that sit for weeks are exploitable. Enforce a triage SLA. |

## Defaults at organization bootstrap

- Org Policy: all critical constraints above applied at the organization node.
- Cloud Audit Logs: `DATA_READ`, `DATA_WRITE`, and `ADMIN_ACTIVITY` logs enabled for all services at the org level. Exported to a centralized BigQuery dataset or Cloud Storage bucket in a dedicated security project.
- Security Command Center: enabled at the org level, Premium tier if budget allows.
- VPC Service Controls: enabled in dry-run mode; promote to enforced after access patterns are characterized.
- Org-level IAM: admin access to the org node restricted to a small break-glass group; all other access granted at folder or project level.
- Resource hierarchy: dedicated folders for prod, staging, dev, security tools, and shared services.

## Observability defaults

- Cloud Audit Logs forwarded to Cloud Logging and exported to a dedicated security project.
- Alert on: `google.iam.admin.v1.CreateServiceAccountKey` (key creation despite Org Policy), `iam.serviceAccounts.signJwt` from unexpected principals, large-scale IAM `SetIamPolicy` changes.
- Secret Manager: alert on `secretmanager.googleapis.com/secret_version_accessed` from unexpected service accounts.
- SCC: Pub/Sub → Cloud Function → PagerDuty / Jira for CRITICAL and HIGH findings.

## Cost considerations

- Cloud KMS: $0.06 per active key version per month, plus per-cryptographic-operation fee. At volume, grouping secrets by purpose under fewer keys is cheaper; at compliance, you may need per-resource keys.
- Secret Manager: $0.06 per active secret version per month; access operations are cheap. The cost of a secret exposure dwarfs the storage cost.
- SCC Premium: priced per GCP resource unit per month; evaluate against the detection coverage you get relative to your threat model.
- Cloud Audit Logs: exported logs incur Cloud Storage or BigQuery ingestion costs; log routers (sinks) allow you to filter before export to bound costs.

## IaC hints

- IAM bindings: `google_project_iam_member` (authoritative for a specific member+role), `google_project_iam_binding` (authoritative for the whole role — use carefully). Prefer `google_<resource>_iam_member` at the resource level.
- Workload Identity Federation: `google_iam_workload_identity_pool`, `google_iam_workload_identity_pool_provider`, `google_service_account_iam_member` with `roles/iam.workloadIdentityUser`.
- Org Policies: `google_org_policy_policy` (v2 API, preferred) or `google_organization_policy` (legacy).
- Secret Manager: `google_secret_manager_secret`, `google_secret_manager_secret_version`, `google_secret_manager_secret_iam_member`.
- Cloud KMS: `google_kms_key_ring`, `google_kms_crypto_key` (with `rotation_period`), `google_kms_crypto_key_iam_binding`.

## Verification checklist

- [ ] No service-account key files created or stored anywhere — Workload Identity Federation for external, Workload Identity for GKE.
- [ ] Every service account has a single dedicated purpose with only the roles it needs.
- [ ] Org Policies applied: no public storage, no external IPs except approved projects, no SA key creation.
- [ ] CMEK applied to all sensitive data stores; key rotation schedules set.
- [ ] Secrets in Secret Manager; no secrets in environment variable literals or code.
- [ ] Cloud Audit Logs exported and retained; alerts on high-risk operations.
- [ ] SCC enabled and findings triaged on a defined SLA.
- [ ] Binary Authorization policy enforced on prod GKE clusters and Cloud Run.
- [ ] A periodic IAM access review is scheduled (at least quarterly for prod).
