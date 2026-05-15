---
name: render-identity-and-security
description: Design or audit Render identity and security posture — Teams and member roles, Personal API tokens, Environment Groups, Secret Files, IP Access Control, SSO, SOC 2 posture, audit logs, GitHub/GitLab OAuth scopes. Use when configuring team access, managing secrets, reviewing credential hygiene, or hardening a Render account.
---

# Render Identity and Security

## When to use

- Setting up team member roles and access controls on a Render team.
- Managing secrets for services (Environment Groups, Secret Files).
- Configuring SSO for a production team.
- Reviewing credential hygiene before a launch or security audit.
- Understanding Render's SOC 2 posture and what it covers.
- Auditing GitHub / GitLab OAuth scopes granted to Render.

## Identity model

### Team members and roles

Render uses a team-based model. Every user is a member of one or more teams with an assigned role:

| Role | Capabilities |
| --- | --- |
| Owner | Full control: billing, team settings, delete services, manage members |
| Admin | Create/edit/delete services, manage Environment Groups, view secrets metadata |
| Developer | Create/edit services, view logs, trigger deploys |
| Viewer | Read-only: view services, metrics, logs (no deploy, no secret access) |

- Invite members by email; they accept and join the team.
- Assign the least-privileged role needed. Developers rarely need Admin access.
- Owners should be limited to 1–2 accounts (ideally a shared ops account, not a personal account).

### Personal API tokens

API tokens authenticate programmatic access (CI/CD, IaC, the `render` CLI). There is no service-account or machine-account concept in Render as of 2026-05 — tokens are issued to a user account.

**Token discipline:**

- Create a dedicated Render user account for CI/CD (e.g. `ci@yourcompany.com`) rather than using a personal user's token. This ensures CI access is not tied to an individual's employment status.
- Scope tokens by environment if possible — the Render API does not support per-token scoping as of 2026-05; this is a risk to acknowledge.
- Store tokens in your CI/CD secret store (GitHub Actions secrets, GitLab CI variables, HashiCorp Vault) — never in source control.
- Rotate tokens annually and immediately after any team member departure who had access.

## Secret management

### Environment Groups

Environment Groups are named collections of environment variables that can be attached to multiple services. They are the primary mechanism for sharing secrets (database URLs, API keys, JWT signing keys) across services without duplicating values.

**Best practices:**

- Create one Environment Group per environment (e.g. `prod-secrets`, `staging-secrets`) plus one per major secret category (e.g. `stripe-keys`, `sendgrid-keys`).
- Use `fromGroup:` in `render.yaml` to attach groups to services — this means the Group's contents are resolved at runtime, not baked into the Blueprint.
- Never put the actual secret value in `render.yaml`; only the group name.
- Audit which services are attached to each Environment Group quarterly — remove services that no longer need access.

```yaml
# Good: reference an Environment Group
envVars:
  - fromGroup: prod-secrets

# Bad: inline secret value
envVars:
  - key: DATABASE_URL
    value: postgres://user:password@host:5432/db
```

### Secret Files

Secret Files allow you to mount a file (e.g. `.env`, a JSON credential file, an mTLS certificate) into a service's filesystem at deploy time. The file content is stored encrypted in Render's backend.

**Use Secret Files when:**

- The application reads a file (not environment variables) for credentials — e.g. a Google service account JSON, a TLS private key, a Firebase admin SDK credential.
- You need to inject multi-line content (private keys, certificates) that would be awkward as an environment variable.

**Secret Files vs env vars:**

| Criterion | Environment Group | Secret File |
| --- | --- | --- |
| Single-line key/value credentials | Preferred | Possible but overkill |
| Multi-line content (certificates, JSON) | Awkward | Preferred |
| Shared across multiple services | Yes (attach group) | Per-service only |
| Visible in process environment | Yes | No (file on disk) |

### What not to do

- Never put secrets in `render.yaml` as plaintext `value:` entries — the file is committed to source control.
- Never log environment variable values or Secret File contents from your application.
- Never pass secrets as build arguments in Dockerfiles — they can appear in image history (`docker history`).

## SSO (Single Sign-On)

SSO is available on paid plans and allows your team to authenticate with Render via your identity provider (IdP) using SAML 2.0 or OIDC. Supported IdPs include Okta, Azure AD, Google Workspace, and others.

**When to enable SSO:**

- Mandatory for any team handling regulated data (SOC 2, PCI, HIPAA) — SSO enables centralized user lifecycle management.
- Strongly recommended for any team with > 5 members to avoid credential sprawl.
- After enabling SSO, disable email/password login for team members to enforce IdP-based authentication.

**SSO + MFA:**

- Enable MFA enforcement at the IdP level — Render SSO defers MFA to the IdP.
- For teams not on SSO, encourage individual Render account MFA; there is no team-level MFA mandate on non-SSO plans.

## Audit logs

Audit logs are available on Pro plans and above. They record team-level actions: member invitations, role changes, secret access, service creation/deletion, and deploy triggers.

- Export audit logs to your SIEM or log aggregation platform for long-term retention.
- Review audit logs after any suspected incident to understand what changed and when.
- As of 2026-05, audit log retention in the Render dashboard is 90 days; long-term retention requires exporting.

## SOC 2 posture

Render maintains a SOC 2 Type 2 report. Key coverage areas:

- Physical and environmental security of compute infrastructure.
- Data encryption at rest and in transit.
- Logical access controls (team roles, API tokens).
- Incident response and availability SLAs.

**What Render's SOC 2 does NOT cover:**

- Your application's security posture (that's your responsibility).
- Secret hygiene within your Environment Groups (you must audit access).
- Custom domain TLS configuration beyond automatic certificate provisioning.
- Source code security in your GitHub / GitLab repositories.

Request Render's SOC 2 report via their security page or sales channel; use it as evidence in your own SOC 2 vendor assessment.

## GitHub / GitLab OAuth scopes

Render connects to GitHub or GitLab to deploy from repositories. The OAuth scopes granted are broad:

- **GitHub**: Render requests read access to code, repository metadata, pull requests, and webhooks. For private repositories, this includes the ability to read all private repositories the user account can access.
- **GitLab**: Similar broad read access.

**Risk:** If Render's platform were compromised, the OAuth grant would expose your repositories. Mitigate by:

- Using a dedicated machine user (GitHub Machine User / GitLab Deploy Account) with access only to the repositories Render needs.
- Granting Render access to specific repositories, not the entire account.
- Reviewing the OAuth grant in GitHub Settings > Applications > Authorized OAuth Apps periodically.

## IP Access Control

IP Access Control (also called IP allowlists) restricts which IP ranges can reach a Web Service. Available on Pro plan and above (see `render-networking-and-edge` for networking details). From an identity perspective:

- IP allowlists are a coarse additional layer — they do not replace authentication and authorization in your application.
- Combine IP allowlists with application-level authentication for defense in depth.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Personal API token for CI/CD under a personal account | Token is revoked or lost when the employee leaves; CI breaks. Use a dedicated machine user. |
| Secrets as `value:` in `render.yaml` | Secret committed to source control; every historical git clone has the credential. Use Environment Groups. |
| All team members as Admin or Owner | Broad access means any compromised account has destructive capability. Apply least-privilege roles. |
| SSO not enforced for regulated workloads | Manual account management leads to stale access for departed employees. Enable SSO + IdP MFA. |
| Broad GitHub OAuth grant to personal account | Render can read all private repos the account can access. Use a machine user with scoped repo access. |
| No audit log retention beyond Render's 90-day window | Incident investigations need > 90d of history. Export to SIEM. |
| Sharing one Environment Group across dev, staging, and prod | Credential blast radius spans all environments. Separate groups per environment. |
| Database credentials in Secret Files but no rotation plan | Static credentials accumulate risk. Rotate on a schedule and after departures. |

## Security defaults

- Roles: Owner access limited to 1–2 operational accounts. Developers on Developer role.
- Secrets: Environment Groups per environment; no inline `value:` in `render.yaml`.
- SSO: mandatory on Pro plan teams with regulated data; recommended for all teams > 5 members.
- MFA: enforced at the IdP if on SSO; individual MFA otherwise.
- API tokens: one per integration, dedicated machine user, stored in CI secret store, rotated annually.
- GitHub/GitLab integration: machine user with repo-scoped access.
- Audit logs: exported to long-term storage for any team with compliance obligations.

## Observability defaults

- Review audit logs in the Render dashboard weekly for unexpected member role changes, secret edits, or service deletions.
- Alert on unexpected deploys outside of normal business hours (audit log + external SIEM rule).
- Track team member list quarterly — remove accounts for departed employees promptly.

## Cost considerations

- SSO and audit logs are Pro plan features — factor into plan selection.
- Dedicated machine user account requires a Render user seat on the team; check team seat pricing.
- IP allowlists (Pro plan) may require a plan upgrade from Standard for security-sensitive services.

## IaC hints

- Environment Groups are declared in the Render dashboard and referenced in `render.yaml` via `fromGroup:`.
- Secret Files are managed in the Render dashboard under the service's "Secret Files" tab.
- Team member roles cannot currently be managed via `render.yaml`; use the dashboard or Render API.
- The Terraform `render-oss/render` provider supports service creation but has limited coverage for Environment Groups and roles as of 2026-05 — check provider docs before relying on it for identity management.

## Verification checklist

- [ ] CI/CD uses a dedicated machine user account, not a personal user's API token.
- [ ] API token stored in CI secret store; not in source control or `.env` files.
- [ ] All secrets delivered via Environment Groups or Secret Files — no plaintext `value:` in `render.yaml`.
- [ ] Environment Groups are separated by environment (dev / staging / prod).
- [ ] Team member roles follow least-privilege; Owner count is minimal.
- [ ] SSO enabled and IdP MFA enforced for any team with compliance obligations.
- [ ] GitHub/GitLab OAuth granted to a machine user with repository-scoped access.
- [ ] Audit log export configured for any team handling regulated data.
- [ ] Token rotation plan documented and exercised at least annually.
