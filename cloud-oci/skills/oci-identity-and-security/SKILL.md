---
name: oci-identity-and-security
description: Design or audit OCI identity, access, and security posture — OCI IAM (compartments, groups, dynamic groups, identity domains), Resource Principal authentication, Vault (KMS + Secrets), Cloud Guard, Security Zones, Bastion service, Data Safe, Vulnerability Scanning. Use when writing policies, structuring compartments, scoping roles, or hardening a tenancy.
---

# OCI Identity and Security

## When to use

- Structuring a compartment hierarchy for a new tenancy or new environment.
- Writing or reviewing OCI IAM policies, dynamic groups, or identity domain configurations.
- Configuring Resource Principal authentication for a workload.
- Rotating or auditing Vault keys and secrets.
- Enabling Cloud Guard, Security Zones, or Bastion service for a compartment.
- Investigating a finding from Cloud Guard, Data Safe, or Vulnerability Scanning.

## Compartment architecture

Compartments are OCI's primary blast-radius boundary. They are free, hierarchical, and the correct place to express team and environment separation.

Recommended hierarchy:

```
root tenancy
├── platform/           ← shared services: VCN, DNS, Vault, Bastion
│   ├── networking/
│   └── security/
├── dev/
│   ├── team-a/
│   └── team-b/
├── staging/
└── prod/
    ├── team-a/
    └── team-b/
```

Rules:
- Apply IAM policies at the compartment level, not at the tenancy root, except for organization-wide guardrail policies.
- Each environment (dev, staging, prod) is a separate top-level compartment — a policy in `dev` cannot be expanded to reach `prod`.
- Shared infrastructure (VCN, Vault, Bastion, monitoring) lives in `platform/` with cross-compartment IAM policies that allow `prod/` to read networking definitions.
- Never place production workloads in the root compartment or in a compartment shared with development.

## Identity model

- **Human administrators** → OCI Identity Domains (SAML federation from your IdP: Okta, Entra ID, Google Workspace). Users authenticate via the IdP; OCI Identity Domains issues sessions. No local OCI user passwords for day-to-day access.
- **Human break-glass** → an OCI local user in the `Administrators` group, with hardware MFA, whose credentials are sealed in a physical break-glass process and audited monthly for last-use.
- **Workloads on Compute** → **Instance Principal**. The instance is a member of a dynamic group; a policy grants that group the needed permissions in a specific compartment. No API key files on instances.
- **Workloads in OKE** → **Workload Identity** (OKE Enhanced cluster). The Kubernetes service account is mapped to a dynamic group rule; pods present a projected service account token to authenticate to OCI APIs.
- **Functions** → **Resource Principal**. A Function application is automatically a resource principal; IAM policy grants the function's compartment principal the needed permissions.
- **CI/CD pipelines** → OIDC token federation. Create a dynamic group rule matching the pipeline's OIDC `sub` claim; grant the group permissions scoped to the target compartment. Never store API keys in pipeline secrets.
- **External third-party access** → a dedicated identity domain group, SAML-federated, with an explicit policy containing a condition on the source CIDR or MFA requirement.

## IAM policy discipline

- Default deny: every `Allow` is explicit. Absence of a matching `Allow` statement is a deny.
- Scope by compartment: `Allow group X to manage instances in compartment prod/team-a` is the correct form. Tenancy-level `manage all-resources in tenancy` policies are for the platform team only.
- Use **verb combinations** consciously: `inspect` < `read` < `use` < `manage`. Grant the minimum verb that lets the workload function.
- Conditions: `request.user.mfaTotpVerified = 'true'` for sensitive operations; `request.region = 'us-ashburn-1'` to restrict operators to approved regions; `target.compartment.name = 'prod'` when a policy at a higher level must distinguish subnets.
- Auditing: every `Allow` policy for `manage` on a sensitive resource type (`keys`, `vaults`, `secret-family`, `autonomous-databases`) should have a justification comment in the Terraform or policy document.

## Dynamic groups

Dynamic groups select resources as IAM members using matching rules:

- `instance.compartment.id = '<compartment-ocid>'` — all Compute instances in a compartment.
- `resource.type = 'fnfunc'`, `resource.compartment.id = '<compartment-ocid>'` — Functions in a compartment.
- `resource.type = 'cluster'`, `resource.compartment.id = '<compartment-ocid>'` — OKE clusters for workload identity.
- Avoid `instance.compartment.id = '<tenancy-ocid>'` (matches all instances in the tenancy) — scope to the production compartment only.
- Give dynamic groups descriptive names: `dg-prod-app-tier-instances`, `dg-prod-functions-notifier`.

## OCI Vault (KMS and Secrets)

- **Vault service** provides two capabilities: key management (KMS) and secrets management. Treat them as separate concerns.
- Create one Vault per security domain (e.g., one for platform keys, one per production environment). A Vault cannot be moved between compartments after creation.
- **Key types:** `AES` for symmetric encryption (Object Storage, Block Volume, Autonomous Database); `RSA` for asymmetric signing (JWT, document signing). Use the OCI-managed HSM-protected (`HSM`) protection mode for any key encrypting regulated data.
- **Key rotation:** schedule automatic key rotation (annually for symmetric keys). The current key version is used for new encryptions; old versions remain available for decryption of existing data.
- **Secrets:** store database passwords, API credentials, TLS private keys, and any credential string in Vault secrets. Reference secrets by OCID from workloads — never put secret values in IAM policies, Terraform state files, or application configs.
- **Secret rotation:** configure secret rotation with a target resource (e.g., ATP database password) and a rotation function; OCI rotates the secret and updates the target automatically.
- **Policy:** grant `use keys` to the compartment principal that needs encryption operations; grant `read secret-family` to the workload's dynamic group for secrets retrieval.

## Cloud Guard

- Cloud Guard is a cloud security posture management (CSPM) service. Enable it at the tenancy level with the reporting region set to your primary home region.
- Enable the following detector recipe families: Configuration Detector, Threat Detector, Activity Detector. The OCI-managed recipes cover the CIS Oracle Cloud Foundations Benchmark controls.
- Targets: apply Cloud Guard to all compartments except the Cloud Guard service compartment itself. A target at the root with `subcompartments = true` captures everything.
- Responders: wire at least `NOTIFICATION` type responders for `CRITICAL` findings to a Notification topic. For well-understood auto-remediable findings (e.g., public Object Storage bucket), enable the OCI-managed responder recipe to auto-remediate.
- Review the Cloud Guard Problem summary weekly; address all `Critical` and `High` problems within the SLA defined in your security policy.

## Security Zones

- Security Zones enforce a set of policies (a security zone recipe) that prevent non-compliant resource configurations in a compartment.
- Enable Security Zones for any compartment handling regulated data or classified as production.
- The `Maximum Security` zone recipe prevents: creating public IP resources without a Load Balancer, creating Object Storage buckets without customer-managed encryption keys, removing VCN flow logs, and other security-critical configurations.
- Security Zone violations result in the resource creation or update being blocked by the OCI control plane — enforcement is preventive, not detective.
- Customize the zone recipe to add organization-specific controls, but do not remove controls from the Maximum Security baseline without documented exception.

## Bastion Service

- OCI Bastion provides time-limited, audited SSH access to private Compute instances without opening port 22 on any security list or NSG.
- Create a Bastion in the private subnet that houses the target instances. The Bastion host is OCI-managed — you do not patch or maintain it.
- Session types: `MANAGED_SSH` for interactive access to instances running the OCI Bastion plugin; `PORT_FORWARDING` for tunneled access to services (RDP, DB ports) on private resources.
- Sessions have a maximum duration (configurable; 3 hours is a sensible cap for interactive sessions). Session history is available in OCI Logging.
- IAM policy for Bastion: grant `manage bastion-sessions` only to roles that need break-glass or on-call access, not to developers by default.

## Data Safe

- Register every Autonomous Database, Oracle DB System, and any on-premises Oracle database connected via Private Endpoint with OCI Data Safe.
- Enable Security Assessment (baseline and drift detection), User Assessment, Activity Auditing, Data Discovery, and Data Masking.
- Schedule a weekly security assessment and alert on any assessment that regresses from the prior baseline.
- Data Safe integrates with OCI Notifications and Events — trigger an alarm when a critical finding appears in the assessment.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| API key files on Compute instances | Key rotation is a manual, error-prone process; leaked keys have unlimited lifetime until manually revoked. Use Instance Principal. |
| IAM policy `manage all-resources in tenancy` for an application group | Any misconfigured workload in that group can destroy production resources. Scope to the minimum compartment and resource type. |
| Root tenancy compartment for production workloads | No blast-radius isolation; tenancy administrators can see and modify everything. Use a dedicated prod compartment. |
| Dynamic group rule matching the whole tenancy | `instance.compartment.id = '<tenancy-ocid>'` includes every Compute instance — a compromised dev instance gains production permissions. Scope to compartment. |
| Vault keys with Oracle-managed protection mode for regulated data | No hardware root of trust; key material could theoretically be exported. Use HSM-protected keys for regulated workloads. |
| Cloud Guard disabled or no responders | CSPM findings accumulate silently. Alert on Critical findings at minimum. |
| No Security Zones on regulated compartments | Control-plane enforcement is absent — a misconfigured IaC change can create a public resource in a regulated compartment. |

## Defaults at tenancy bootstrap

- Root compartment: contains no workload resources. Contains only `platform/` and environment top-level compartments.
- Tenancy administrator group: hardware MFA on every member. The group has break-glass access to the root. Log every Console sign-in to OCI Audit and alert on after-hours access.
- Identity Domain federation: SAML federation from the corporate IdP configured within 24 hours of tenancy creation. Local user passwords disabled for all users except break-glass.
- Cloud Guard: enabled at tenancy root, Maximum Security recipe, responders configured for Critical findings.
- Security Zones: enabled on `prod/` and any regulated compartment from day one.
- Vault: one platform vault, HSM-protected, in `platform/security/`. Master encryption keys created per resource domain (storage, database, secrets).
- Regions: IAM policy at tenancy root restricting resource creation to approved regions using a condition on `request.region`.

## Observability defaults

- OCI Audit logs to a centralized log group with ≥ 365-day retention; exported to Object Storage Archive tier for long-term retention.
- Cloud Guard problems → Notification topic → alert channel (email, PagerDuty, Slack via Function webhook).
- Data Safe weekly assessment findings → email notification on regression from baseline.
- IAM API key last-used report reviewed monthly for any key not used in 30 days (rotation or deletion).
- Bastion session history exported to the security log group for forensics.

## Cost considerations

- OCI IAM, Cloud Guard (for tenancies below the free threshold), Bastion, and Security Zones have no per-resource charge — only the Vault key rotation and API request counts incur cost.
- Vault keys are billed per key version per month. Use key rotation carefully on keys that protect many resources; the old version must be retained for decryption of existing data.
- Data Safe is included for Autonomous Database; charges apply for DB Systems and on-premises targets. Evaluate the target registration cost against the compliance requirement.

## IaC hints

- Terraform resources: `oci_identity_compartment`, `oci_identity_group`, `oci_identity_dynamic_group`, `oci_identity_policy`, `oci_kms_vault`, `oci_kms_key`, `oci_vault_secret`, `oci_cloud_guard_target`, `oci_bastion_bastion`.
- Manage all IAM policies in a dedicated `iam` Terraform workspace separate from workload stacks — policy changes are high-risk and deserve isolated plan/apply cycles.
- Dynamic group matching rules are strings in Terraform — use consistent naming conventions so grep finds all rules for a compartment.
- Security Zone targets cannot be removed from a compartment without first migrating all resources out; plan compartment layout carefully before enabling.

## Verification checklist

- [ ] Human access via Identity Domain federation; no local user passwords for regular users.
- [ ] Break-glass local user has hardware MFA; credentials are sealed and audited.
- [ ] Workloads authenticate via Instance Principal / Resource Principal / Workload Identity — no API key files.
- [ ] Every IAM `Allow` policy scoped to a specific compartment and resource type; no tenancy-root `manage all-resources`.
- [ ] Dynamic group rules scoped to specific compartments, not the tenancy.
- [ ] Vault keys HSM-protected for regulated data; rotation schedule configured.
- [ ] All secrets in Vault Secrets; no credentials in Terraform state output blocks or environment config files.
- [ ] Cloud Guard active at tenancy root; Critical responder notifications wired.
- [ ] Security Zones on all regulated and production compartments.
- [ ] Bastion service replaces any open SSH rules on all subnets.
- [ ] Data Safe active on all Oracle database instances.
