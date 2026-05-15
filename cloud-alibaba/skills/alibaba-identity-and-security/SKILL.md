---
name: alibaba-identity-and-security
description: Design or audit Alibaba Cloud identity, access, and security posture — RAM (users/groups/roles/policies), STS temporary credentials, KMS (Standard/Dedicated HSM), Secrets Manager, Cloud Config, Cloud Firewall, Security Center (Threat Detection), Anti-DDoS, ActionTrail, SDDP. Use when writing RAM policies, rotating secrets, scoping roles, or hardening an account.
---

# Alibaba Identity and Security

## When to use

- Writing or reviewing a RAM policy, role trust relationship, or STS assumption chain.
- Standing up a new account, sub-account structure, or Resource Management hierarchy.
- Rotating, scoping, or auditing AccessKey pairs and secrets.
- Setting up org-level guardrails (Cloud Config rules, Resource Management policies).
- Configuring ActionTrail, Cloud Firewall, Security Center, or Anti-DDoS posture.
- Investigating an incident — ActionTrail forensics, Cloud Firewall traffic analysis.

## Identity model

- **Humans → RAM users with MFA, or SAML federation from enterprise IdP (Okta, Entra ID, etc.).** No long-lived AK/SK pairs for human users in production accounts. RAM sub-users are acceptable in small teams; for larger organizations, federate via SAML 2.0 SSO into the Alibaba Cloud console.
- **Workloads → RAM Roles assumed by the runtime.** ECS instance RAM Role, RRSA (RAM Role for Service Accounts) in ACK, FC service RAM Role. No static AK/SK in application code, environment variables, or container images.
- **External CI/CD → OIDC federation with RAM Role trust.** GitHub Actions OIDC → RAM Role; scoped by `sub` claim to repo / ref. Never store an AK/SK in CI secrets.
- **Programmatic break-glass → STS AssumeRole with MFA, time-bounded, ActionTrail-logged.** Keep break-glass credentials offline; rotate quarterly.
- **China vs International**: RAM policies, KMS keys, and account structures are **entirely separate** between China and International accounts. An AK/SK valid in one cannot authenticate to the other.

## RAM policy discipline

- Default-deny. Every `Allow` statement is justified with a specific reason.
- **Resource-level ARNs**, not `Resource: "*"`. If the service supports resource-level permissions, scope to the specific ARN pattern (e.g., `acs:oss:*:*:my-bucket/*`).
- Conditions for context: `acs:SourceIp`, `acs:SecureTransport`, `acs:MFAPresent`, `acs:RequestedRegion`, `acs:ResourceTag/Environment=prod`.
- **Permission boundaries** (RAM policies attached to roles that cap what the role can grant) for developer-provisioned roles.
- **Resource Group policies** at the account or resource-group level for org-wide guardrails.
- No inline policies for production roles — managed (custom or system) policies only, version-controlled.
- Policy linting: use the RAM policy visual editor or `aliyun ram SimulatePrincipalPolicy` to verify before applying.

## STS (Security Token Service)

- STS tokens are time-bounded (15 min to 12 h); prefer shorter lifetimes for machine-to-machine authentication.
- `AssumeRole` requires the caller to hold `sts:AssumeRole` on the role ARN — scope this strictly.
- For ECS, the instance metadata service provides auto-refreshed STS credentials via the instance RAM Role — never call STS directly from an ECS-hosted workload.
- For ACK, RRSA eliminates the need for any STS call from a pod; the pod's service account token is exchanged for cloud credentials at the RAM API level.
- External ID: require `sts:ExternalId` in the trust policy of any role assumed by a third-party service — prevents confused-deputy attacks.

## KMS

- **Customer Master Keys (CMK)**: use CMKs for any data requiring access audit, key revocation, or rotation control. Service-managed keys (Alibaba-owned) are acceptable for test environments only.
- **Automatic rotation**: enable on symmetric CMKs (annual default, configurable to 30–180 d).
- **Key policy**: explicit `Principal` ARNs for who can use (`kms:Encrypt`, `kms:Decrypt`, `kms:GenerateDataKey`) vs administer (`kms:CreateKey`, `kms:ScheduleKeyDeletion`). No `*` principals.
- **Dedicated HSM (KMS Dedicated HSM)**: for FIPS 140-2 Level 3 or MLPS-mandated hardware isolation; higher cost, limited regions.
- **Key domains**: separate CMKs for data categories (storage / database / logs / transport) so a single compromise or regulatory hold does not unlock all data.
- **Multi-region keys**: available in International regions; use when cross-region encryption is required. Not available in China regions.

## Secrets Manager

- **Alibaba Cloud Secrets Manager** manages dynamic secrets (RDS/PolarDB credentials with auto-rotation, AK/SK pairs) and static secrets.
- **Dynamic secrets**: leverage the built-in RDS integration — Secrets Manager rotates the database password and updates the secret value automatically; zero downtime.
- **Reference by secret name / ARN**: application code fetches the secret at startup or via SDK; never bake credentials into environment variables at deploy time.
- **Audit**: every `GetSecretValue` call is logged in ActionTrail — review the caller list quarterly.
- **SSM-equivalent for config**: for non-secret configuration values, Alibaba Cloud App Configuration Service (ACS AppConfig) or OSS-hosted config files are the alternative.

## ActionTrail (Audit Logging)

- Enable **Organization Trail** (if using Resource Management) or a standalone trail per account.
- Trail destination: OSS bucket (cost-effective for long retention) + SLS Log Store (real-time query and alerting).
- **Log integrity**: enable trail log file verification (SHA-256 + RSA signature); validate regularly.
- **Encryption**: CMK on the OSS destination bucket.
- **Event scope**: management events on by default; data events (OSS object reads, KMS key usage, RDS query) for high-sensitivity assets — not everywhere (cost).
- **Retention**: minimum 180 d in SLS for real-time queries; archive to OSS Cold Archive for 1–3 year regulatory retention.
- **Anomaly alerting**: SLS alert rules on: root user login, AK/SK secret access from a new IP, bulk policy attachment, CMK deletion scheduled.

## Cloud Firewall

- **Internet Firewall**: inspects north-south traffic between the internet and ECS / ALB public IPs. Default-deny outbound policy is the recommended posture.
- **VPC Firewall**: east-west inspection between VPCs attached to the same CEN — critical for multi-VPC architectures where lateral movement is a concern.
- **NAT Firewall**: controls outbound NAT traffic; enables FQDN-based egress allow-list.
- Policy strategy: start with discovery mode (alert-only) for 1–2 weeks to build a traffic baseline; then enforce block rules.
- Integration: Cloud Firewall findings feed into Security Center for unified alerting.

## Security Center (Threat Detection / Cloud Security Center)

- **Enterprise Edition** for production: host-based agent, vulnerability management, baseline check, anomaly detection.
- Key capabilities: file integrity monitoring, process anomaly detection, network intrusion detection, web shell detection.
- Baseline check: run against **CIS Alibaba Cloud Foundations Benchmark** and the built-in Alibaba Cloud Security Baseline; remediate CRITICAL items before production launch.
- Vulnerability scanning: scheduled weekly; auto-create tickets or alert on HIGH/CRITICAL CVEs in ECS instances and container images.
- MLPS alignment: Security Center baseline checks include MLPS 2.0 Level 2 and Level 3 checks for China-region workloads.

## Anti-DDoS posture

- **Anti-DDoS Basic**: free; provides volumetric DDoS scrubbing for all ECS and ALB resources automatically.
- **Anti-DDoS Pro (China) / Anti-DDoS Premium (International)**: required for workloads expecting targeted volumetric or application-layer attacks. Configure your public IP / domain as a protected asset.
- **HTTP Flood (CC) protection**: configure under Anti-DDoS Pro's WAF component or standalone WAF.
- **Origin IP protection**: once Anti-DDoS proxies traffic, lock down the origin Security Group to Anti-DDoS forwarding IP ranges only.

## Account and organization structure

- **Resource Management**: Alibaba's organization layer — create resource groups per environment (dev / staging / prod) or per business unit. Attach RAM policies at the resource-group level for environment-scoped access.
- **Resource Directory**: for multi-account setups (China and International as separate member accounts); enables org-level ActionTrail and policy propagation.
- **Root account hardening**: enable MFA (hardware token preferred); do not create AK/SK on the root account; use RAM sub-users for all daily operations.
- **Account-level defaults**: enable default OSS Block Public Access, enable default EBS encryption with a CMK, set default region to restrict API calls.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Long-lived AK/SK for a workload or CI pipeline | Key leaks are permanent until rotated; no automatic rotation; ActionTrail attribution is "an AK" not a workload. Use RAM Role + RRSA + OIDC. |
| `"Action": ["*"]` policies "until we figure out what's needed" | Becomes permanent. Start with read-only, expand on observed Access Denied logs. |
| Shared RAM user account across team members | No per-user audit trail; one person leaving means shared credentials must rotate. Individual RAM users or federated IdP. |
| Root account with an AK/SK created | Root AK/SK can do anything including close the account; use RAM sub-user for programmatic access. |
| Inline RAM policies on production roles | No version history, no review trail. Use named managed policies checked into IaC. |
| Secrets in ECS user-data or environment variables | CloudMonitor, ActionTrail, and container inspection all expose env vars to authorized principals. Use Secrets Manager. |
| Disabling ActionTrail "to reduce OSS costs" | ActionTrail management events are free; disabling it makes post-incident forensics impossible. |
| KMS key shared across all environments | A compromised dev key can decrypt prod data if CMK is shared. One key domain per environment tier. |

## Defaults at account bootstrap

- Root account: MFA (hardware token); no AK/SK created; accessed only for the handful of operations that require root.
- RAM sub-user for the human administrator: named, with MFA required for console access; permission policy scoped to initial bootstrap only, then reduced.
- SAML SSO configured from enterprise IdP if the team is > 3 people.
- ActionTrail: account trail + org trail; OSS destination (Cold Archive lifecycle); SLS Log Store for real-time alerts; integrity validation on.
- Cloud Firewall enabled; initial internet policy in discovery mode.
- Security Center: Enterprise Edition enabled; baseline scan scheduled immediately.
- Resource Management: resource groups for dev, staging, and prod created and tagged.

## Observability defaults

- ActionTrail: shipped to SLS; alert on root login, AK/SK access from novel IP, bulk policy attachment, CMK deletion.
- Cloud Firewall: alert on blocked outbound connection spikes (potential C2) and new allowed-but-unplanned inbound services.
- Security Center: alert on HIGH/CRITICAL vulnerabilities, new web shell detections, failed SSH login spikes.
- RAM credential report: exported monthly; unused credentials flagged.

## Cost considerations

- ActionTrail management events: free; data events are paid — scope to high-value buckets/keys only.
- Security Center Enterprise Edition: per-asset per-month; disable on decommissioned instances promptly.
- KMS: per-CMK per-month + per-request fees; group keys by domain rather than per-resource.
- Dedicated HSM: significant fixed cost per cluster; only justified by FIPS or MLPS Level 3 requirements.
- Secrets Manager: per-secret per-month + per-API-call; cheap relative to the cost of a credential breach.

## IaC hints

- Terraform: `alicloud_ram_user`, `alicloud_ram_role`, `alicloud_ram_policy`, `alicloud_ram_role_policy_attachment`, `alicloud_kms_key`, `alicloud_kms_key_version`, `alicloud_actiontrail_trail`, `alicloud_cloud_firewall_control_policy`.
- RAM policy documents: use Terraform `data "alicloud_ram_policy_document"` (if available) or inline JSON with `jsonencode()`; never raw strings that bypass validation.
- KMS keys: manage in a dedicated `security` Terraform workspace / ROS stack; keys must outlive the resources that use them.
- For RRSA: `alicloud_cs_kubernetes_rrsa` or set `enable_rrsa = true` on `alicloud_cs_managed_kubernetes`.

## Verification checklist

- [ ] No AK/SK on ECS instances, ACK pods, FC functions, or CI pipelines — RAM Role / RRSA / OIDC everywhere.
- [ ] Root account has hardware MFA; no AK/SK; access logged in ActionTrail.
- [ ] Every RAM policy has explicit resource ARNs; no `Action: ["*"]` or `Resource: ["*"]` in production.
- [ ] KMS CMK per domain (storage / database / logs); key policies scoped to specific principals; automatic rotation on.
- [ ] ActionTrail: org-level trail, integrity validation, SLS real-time alerting, OSS cold-archive retention.
- [ ] Cloud Firewall enabled; internet policy reviewed; VPC Firewall on for multi-VPC.
- [ ] Security Center Enterprise on; baseline scan ≤ 7 d old; CRITICAL/HIGH vulnerabilities remediated.
- [ ] Secrets Manager used for all credentials; no secrets in environment variables or user-data.
- [ ] MLPS compliance level confirmed for China-region workloads; Security Center baseline aligned.
- [ ] China / International account separation confirmed; no cross-account-type credential sharing.
