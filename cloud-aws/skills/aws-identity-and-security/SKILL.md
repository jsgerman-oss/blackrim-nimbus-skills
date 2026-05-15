---
name: aws-identity-and-security
description: Design or audit AWS identity, access, and security posture — IAM, SSO (IAM Identity Center), KMS, Secrets Manager, GuardDuty, Security Hub, CloudTrail, Macie, IAM Access Analyzer. Use when writing policies, rotating secrets, scoping roles, or hardening an account.
---

# AWS Identity and Security

## When to use

- Writing or reviewing an IAM policy / role / trust relationship.
- Standing up an account, an org, or a new SSO permission set.
- Rotating, scoping, or auditing secrets and keys.
- Setting up org-wide guardrails (SCPs, GuardDuty, Security Hub).
- Investigating an incident — CloudTrail forensics, IAM Access Analyzer findings.

## Identity model

- **Humans → IAM Identity Center (SSO)**. Federate from your IdP (Okta, Entra ID, Google, JumpCloud). No long-lived IAM users for humans.
- **Workloads → IAM roles** assumed by the runtime (Lambda execution role, ECS task role, IRSA for EKS, EC2 instance profile). No static access keys.
- **External integrations → OIDC + IAM role** with a trust policy gated on `aud` / `sub` claims (GitHub Actions, GitLab CI, Buildkite). Never store an `AKIA...` in CI secrets.
- **Programmatic break-glass → temporary credentials** via `aws sts assume-role` with MFA, time-bounded, audit-logged.

## IAM policy discipline

- Default deny. Every `Allow` is justified.
- Resource-level ARNs, not `Resource: "*"`. If the service supports resource-level perms, use them.
- Conditions for context: `aws:SourceVpc`, `aws:PrincipalOrgID`, `aws:SecureTransport=true`, `aws:MultiFactorAuthPresent`, `aws:ResourceTag/Environment=prod`.
- Permission boundaries on dev-owned roles so devs can grant access but not escalate above the boundary.
- Service Control Policies (SCPs) at the org / OU level to set hard limits even root can't exceed (e.g., deny region usage outside an approved list, deny disabling CloudTrail).
- IAM Access Analyzer in every account. Findings are not optional.

## KMS

- Customer-managed CMKs for anything you might need to revoke, rotate, or audit per-key.
- Key policy first-class: explicit `Principal` ARNs for who can use vs admin the key. No `kms:*` to `*`.
- Automatic rotation on for symmetric keys (yearly).
- Multi-region keys only when you have a real cross-region requirement; otherwise keep keys regional.
- Separate keys by domain (db / storage / logs) so a single compromise doesn't unlock everything.

## Secrets

- **Secrets Manager** for credentials (DB passwords, API keys, JWT signing keys). Auto-rotation via Lambda for supported engines.
- **SSM Parameter Store SecureString** for config-like secrets that don't need rotation; cheaper.
- Reference secrets from compute by ARN; never bake into env vars at build time.
- Audit `secretsmanager:GetSecretValue` via CloudTrail — list of consumers should match expected services.

## CloudTrail and audit

- One organization trail to a centralized logging account, log integrity validation on, KMS-encrypted, MFA-delete on the destination bucket.
- Data events (S3 object reads, Lambda invokes) on for sensitive buckets / functions — not everywhere (cost).
- CloudTrail Lake for queryable history when you need it.
- Config recording on for compliance posture; conformance packs for CIS / PCI baselines.

## Detection and response

- GuardDuty at org level, EKS / S3 / Malware / RDS protection on.
- Security Hub aggregating findings from GuardDuty, Inspector, IAM Access Analyzer, Macie, Config — to a single security account.
- AWS Inspector for EC2 + ECR + Lambda vulnerability scanning.
- Automated remediation via EventBridge → SSM Automation / Lambda for well-understood findings (public S3 bucket, exposed access keys); manual for everything else.
- Incident response playbook: who has break-glass, where the audit log lives, how to revoke an IRSA role, how to rotate KMS.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Long-lived IAM user with `AKIA...` for a service | Key leaks, no rotation, no audit trail tying it back to a workload. |
| `"Action": "*"` policies "until we figure out what's needed" | Becomes permanent. Start tight; expand on observed denies. |
| Shared SSH key passed around the team | No auditability, no revocation granularity. SSM Session Manager. |
| Root user with no MFA | One phish = full account ownership. MFA mandatory. |
| Inline policies for prod roles | Drift everywhere, no review trail. Managed policies, version-controlled. |
| Secrets in env vars committed in `.env` | Git history is forever. Pre-commit secret scanning, rewrite-history if leaked. |
| Disabling CloudTrail "to save money" | Costs are tiny; investigations without it are impossible. |

## Defaults at account bootstrap

- Root user: hardware MFA token, no API access keys, used only for the few things only root can do (close account, change support plan).
- IAM Identity Center configured with permission sets aligned to job functions (Admin, PowerUser-Networking, ReadOnly-Audit, etc.).
- Org-level SCPs: deny disabling CloudTrail / GuardDuty / Config, deny IAM user creation outside Identity Center, deny region usage outside the approved list.
- Org-level GuardDuty + Security Hub + Access Analyzer.
- Account baseline: S3 Block Public Access, default EBS encryption, default region set, IMDSv2 required on new EC2.
- Billing: budgets + anomaly detection alerts to a real channel.

## Observability defaults

- CloudTrail to centralized account.
- IAM credential report exported monthly.
- Access Analyzer findings → SecurityHub → ticketing.
- Failed-login alerts (Console / Identity Center) to a SOC channel.
- KMS key usage alarm if a key is used outside its expected callers (CloudTrail + EventBridge rule).

## Cost considerations

- CloudTrail management events are free; data events bill — scope tightly.
- GuardDuty bills by data volume scanned — usage-based, but cheap relative to a breach.
- KMS keys $1/mo each + per-request fees — group by domain rather than per-resource.
- Macie expensive on large S3 estates — sample mode or scope to sensitive buckets only.

## IaC hints

- IAM via Terraform `aws_iam_policy_document` data sources (typed JSON) or CDK `PolicyDocument` — both beat hand-written JSON.
- SCPs: `aws_organizations_policy` (Terraform) or `cdk-organizations` constructs.
- KMS: managed in a security/IAM stack separate from data resources — keys outlive databases.
- Identity Center permission sets: Terraform `aws_ssoadmin_*` resources. Manage account assignments in code, not the console.
- Pre-commit: `tflint`, `cfn-lint`, `checkov`, `tfsec` for IaC linting.

## Verification checklist

- [ ] No IAM users for humans (Identity Center only); root locked down + hardware MFA.
- [ ] Workloads run under role-based credentials only (no `AKIA...` in code, CI, or env).
- [ ] Every policy has explicit resource ARNs and at least one condition where applicable.
- [ ] Org-wide CloudTrail, GuardDuty, Security Hub, Access Analyzer on.
- [ ] SCPs prevent the obvious foot-guns (region escape, disabling logging, IAM user creation).
- [ ] Secrets in Secrets Manager / Parameter Store, referenced by ARN, rotated where supported.
- [ ] KMS CMKs per domain; key policies scoped to specific principals.
- [ ] At least one quarterly access review (who can do what in prod).
