---
name: azure-identity-and-security
description: Design or audit Azure identity, access, and security posture — Microsoft Entra ID, Managed Identities, Azure RBAC, Key Vault, Defender for Cloud, Microsoft Sentinel, Conditional Access, Privileged Identity Management. Use when writing role assignments, scoping identities, hardening an account, or responding to a Defender finding.
---

# Azure Identity and Security

## When to use

- Writing or reviewing Azure RBAC role assignments and custom role definitions.
- Configuring Managed Identities and their access to Key Vault, Storage, or other services.
- Standing up a new subscription, Management Group hierarchy, or Entra ID tenant.
- Rotating, scoping, or auditing secrets and certificates in Key Vault.
- Setting up org-wide security controls (Defender for Cloud, Sentinel, Conditional Access, PIM).
- Investigating an incident — Entra audit logs, Defender alerts, Sentinel incidents.

## Identity model

- **Humans → Microsoft Entra ID with Conditional Access.** Federate from an authoritative HR source (Workday, BambooHR) or an existing IdP. All human access uses Entra ID identities — no local accounts for Azure resource access.
- **Workloads → Managed Identities.** System-assigned for single-resource identities; user-assigned for identities shared across multiple resources (e.g., a Fleet of Functions sharing access to the same storage account). No service principal secrets stored or rotated manually.
- **External integrations → Workload Identity Federation.** GitHub Actions, GitLab CI, and other OIDC-capable systems federate to an app registration via a federated credential. No client secrets stored in CI pipelines.
- **Break-glass → time-bounded role activation via PIM.** Emergency admin access activates a role for hours, not permanently assigned. Every activation is audit-logged.

## Entra ID hardening

- **Conditional Access policies** as the primary access control layer for human identities:
  - Require MFA for all users, all apps — no exclusions without a documented exception.
  - Block legacy authentication protocols (IMAP, SMTP, POP3, older ActiveSync) — they bypass MFA.
  - Require compliant or Hybrid Azure AD-joined devices for privileged roles.
  - Block access from high-risk sign-in or risky user conditions (Identity Protection integration).
- **Emergency access accounts** (break-glass): two accounts excluded from all Conditional Access policies, each with a different global admin using hardware FIDO2 keys. Monitor their sign-in for any activity.
- **Security defaults**: if Conditional Access licenses are not available, enable Security Defaults as a baseline — better than nothing, but CA policies are strongly preferred.

## Azure RBAC discipline

- **Least privilege by default.** Every role assignment is justified and scoped to the smallest resource scope possible (resource > resource group > subscription > management group).
- **Built-in roles first.** Custom roles are a maintenance burden; audit built-in roles for fit before creating custom ones.
- **Scope hierarchy:** Management Group → Subscription → Resource Group → Resource. Assign at the resource-group scope for most application roles; use Management Group scope only for org-wide readers or governance requirements.
- **No Owner or Contributor at subscription scope for workload service identities.** Workloads get purpose-specific built-in roles (`Storage Blob Data Contributor`, `Key Vault Secrets User`, etc.).
- **Deny assignments** for immutable guardrails (read-only managed subscriptions, locked baseline resources).
- Audit role assignments quarterly; review external guest users with resource access.

## Managed Identity best practices

- Prefer **user-assigned Managed Identity** when the same identity needs to access multiple resources or when the lifecycle of the identity should outlive a single compute resource.
- Use **system-assigned** for single-purpose identities tightly coupled to a specific resource (one Function App + one Key Vault relationship).
- Grant the Managed Identity only the RBAC roles it needs, scoped to the specific resource — never Contributor at the subscription level.
- Rotate nothing — Managed Identities have no credentials to rotate; the platform manages the token lifecycle. This is the value.
- When switching from service principal to Managed Identity, revoke the old service principal client secret immediately after verifying the MI works.

## Key Vault

- **Standard tier** for software-protected keys and secrets. **Premium tier** (or Managed HSM) for hardware-protected keys when regulatory or compliance requirements mandate HSM-backed operations.
- Access model: use **Azure RBAC** for Key Vault data plane (`Key Vault Secrets User`, `Key Vault Crypto Service Encryption User`, etc.) — not legacy access policies which are harder to audit and don't integrate with PIM.
- Secret naming: `{service}-{env}-{purpose}` convention; version explicitly via secret versions. Do not store multiple secrets in a single value as JSON — one secret per value.
- Soft delete: on (enabled by default since 2020). Purge protection: on for any Key Vault holding production secrets or CMKs — prevents malicious deletion.
- Diagnostic settings: send Key Vault audit events (`AuditEvent`) to a central Log Analytics workspace; alert on secret access outside expected callers.
- Network: private endpoint for production Key Vaults; `publicNetworkAccess: 'Disabled'`. Allow access from trusted Azure services (AzureServices bypass) only when a private endpoint is not feasible for a specific service.
- Separate Key Vaults by environment and by domain: one for production CMKs, one for production app secrets, one per non-prod environment. Keys that control encryption at rest must not share a vault with app-tier secrets.

## Defender for Cloud

- Enable **Defender for Cloud** at the Management Group scope so every new subscription is automatically enrolled.
- CSPM (Cloud Security Posture Management): Foundational CSPM is free; **Defender CSPM** tier for attack path analysis, cloud security graph, and regulatory compliance dashboards.
- Workload protections to enable:
  - Defender for Servers (Plan 2) for VMs and AKS nodes — includes Microsoft Defender Antivirus, vulnerability assessment, and JIT VM access.
  - Defender for Containers for AKS image scanning and runtime threat detection.
  - Defender for Storage for malware scanning and sensitive-data discovery on blob workloads.
  - Defender for SQL (Azure SQL + SQL Server on VMs) for Advanced Threat Protection.
  - Defender for Key Vault, Defender for App Service, Defender for DNS.
- Secure Score: treat findings with score impact > 1% as actionable items in the sprint backlog; anything blocking regulatory compliance is P1.
- Recommendations: export to Azure DevOps / GitHub Issues via the Continuous Export feature so findings enter the normal engineering workflow.

## Microsoft Sentinel

- **Log Analytics workspace** as the Sentinel data store; choose a workspace topology (centralized single workspace vs per-region for data residency) before enabling — it is difficult to migrate.
- Data connectors: enable Microsoft 365 Defender (unified XDR), Entra ID (sign-in and audit logs), Azure Activity, Defender for Cloud alerts, and custom connectors for SaaS tools.
- Analytics rules: start with Microsoft's built-in Scheduled Analytics and NRT (Near Real-Time) rules for common attack patterns; customize thresholds to reduce alert fatigue.
- SOAR playbooks: Logic App-based playbooks for common response actions (disable compromised user, isolate VM, add IP to Firewall blocklist); require human approval before any destructive action.
- Threat hunting: use KQL notebooks to proactively hunt for indicators of compromise; save successful queries as analytics rules.
- Data retention: hot tier 90 days (included), auxiliary / long-term tier for 1–7 years compliance retention at lower cost.

## Privileged Identity Management (PIM)

- Activate eligible assignments (not permanent) for all privileged roles (Global Administrator, Privileged Role Administrator, Owner, User Access Administrator).
- Approval workflow: roles with blast radius > one subscription require a second approver.
- Activation duration: 1-4 hours maximum for highly privileged roles; 8 hours for day-to-day elevated roles.
- Access reviews: quarterly review for all PIM-eligible roles; any role not reviewed in 90 days is automatically removed.
- Alerts: PIM fires alerts on permanent admin assignments, roles not requiring MFA, and unusual activation patterns — route to Sentinel or a security operations channel.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Service principal client secret in CI pipeline or app config | Secret leaks are inevitable over time. Workload Identity Federation or Managed Identity. |
| Owner role permanently assigned to a workload identity | Any compromise of that identity = full subscription control. Scope to least privilege. |
| Key Vault access via legacy access policies only | Access policies are not auditable via PIM and don't support condition-based access. Use RBAC. |
| All secrets in one Key Vault, no environment separation | A dev engineer with Key Vault Secrets User on the shared vault can read prod secrets. Separate vaults. |
| Conditional Access policy with broad MFA exclusions | The exclusions become the attack surface. Every exclusion requires documented justification and review. |
| Legacy authentication protocols enabled | IMAP/POP3/SMTP bypass Conditional Access and MFA. Block unconditionally. |
| Break-glass accounts subject to Conditional Access | If Identity Protection triggers a block, you cannot access the tenant. These accounts must be excluded. |
| Global Administrator activated on demand without PIM | No audit trail, no approval gate. Every privileged role in PIM. |

## Defaults at subscription / tenant bootstrap

- Global Administrator: maximum 2 permanent global admins (ideally break-glass accounts only); all other admins use PIM.
- Conditional Access: baseline policies on day 1 — require MFA for all users, block legacy auth, require compliant devices for admin roles.
- Defender for Cloud: enabled at the Management Group scope before the first resource is deployed.
- Azure Policy: built-in initiatives for allowed locations, required resource tags, Defender for Cloud enablement, and diagnostic settings on key resource types.
- Activity Log: export Azure Activity Log to a central Log Analytics workspace and a Storage Account for long-term retention.
- Budget + anomaly alerts: per-subscription budget alert at 80% and 100% of expected monthly spend; anomaly detection via Cost Management.

## Observability defaults

- Entra ID audit logs and sign-in logs to a central Log Analytics workspace (retention: 90 days minimum).
- Key Vault audit events (`AuditEvent`) to Log Analytics; alert on access by unexpected service principals or outside business hours.
- Azure Activity Log to Log Analytics; alert on role assignment changes, policy exemptions, and Defender for Cloud recommendations dismissed.
- PIM activation events to Sentinel; correlation rule fires when a privileged role is activated more than twice in one day for the same user.
- Defender for Cloud security alerts exported to Sentinel automatically via the data connector.

## Cost considerations

- Defender for Cloud plans are priced per resource: Servers Plan 2 ~$15/server/month; Containers ~$7/AKS-core/month. Enable per plan where the threat model justifies it; Servers Plan 1 is free and covers basics for non-production.
- Sentinel charges per GB ingested (after the first 5 GB/day free per workspace) plus optional commitment tiers. Filter noisy low-value log sources before enabling the connector.
- PIM is included in Entra ID P2 (part of Microsoft 365 E5 or EMS E5); ensure licenses are in place before enabling PIM for groups.
- Key Vault is priced per operation — hardware key operations (Premium / HSM) are 3–10x more expensive than software operations. Use HSM-backed keys only where the compliance requirement mandates it.
- Conditional Access requires Entra ID P1 minimum; Identity Protection (risky user/sign-in) requires P2.

## IaC hints

- Bicep: `Microsoft.Authorization/roleAssignments` scoped to the target resource; `Microsoft.KeyVault/vaults` with `enableRbacAuthorization: true` and `enableSoftDelete: true`.
- Terraform: `azurerm_role_assignment` (specify `principal_id` from the Managed Identity output, not a hardcoded GUID); `azurerm_key_vault` with `enable_rbac_authorization = true` and `soft_delete_retention_days = 90`.
- Manage Conditional Access policies via `azuread_conditional_access_policy` (Terraform AzureAD provider >= 2.x); version-control CA policies as code alongside the resources they protect.
- Key Vault CMK setup: `azurerm_key_vault_key` → `azurerm_storage_account` / `azurerm_cosmosdb_account` with `customer_managed_key` block. The Key Vault must be deployed and the Managed Identity role assignment created before the dependent resource — use `depends_on`.
- Pre-commit: `checkov`, `tflint` with the `azurerm` ruleset, and `az bicep build` lint for static policy checks.

## Verification checklist

- [ ] No service principal client secrets in CI, app config, or source control.
- [ ] All human access via Entra ID; legacy auth protocols blocked by Conditional Access.
- [ ] Workload identities use Managed Identity; Workload Identity Federation for CI/CD.
- [ ] Every role assignment has a specific scope; no Owner at subscription scope for workloads.
- [ ] Key Vault RBAC enabled; soft delete + purge protection on; private endpoint deployed.
- [ ] Defender for Cloud enabled at Management Group scope; Secure Score reviewed.
- [ ] PIM configured for all privileged roles; permanent Global Administrator count <= 2.
- [ ] Conditional Access: MFA required for all, legacy auth blocked, risky sign-in policies on.
- [ ] Quarterly access review scheduled in PIM; role assignments older than 90 days reviewed.
- [ ] Break-glass accounts exist, tested, and excluded from Conditional Access with monitor alert on use.
