---
name: railway-security-and-secrets
description: Design or audit Railway security posture — Variables (per-service and shared), Reference Variables for cross-service secret injection, Service Tokens, project tokens, GitHub OAuth integration scope, secret rotation, deployment protection (Pro plan), and audit log access. Use when wiring secrets, scoping service access, rotating credentials, reviewing team permissions, or hardening a production project.
---

# Railway Security and Secrets

## When to use

- Wiring database credentials, API keys, or other secrets to Railway services.
- Scoping access for a CI/CD pipeline using a Service Token.
- Reviewing or limiting GitHub OAuth permissions for the Railway integration.
- Rotating credentials after a suspected leak or scheduled rotation.
- Setting up deployment protection for a production environment.
- Auditing team member access and permissions.

## Variable model

Railway has two types of variables:

**Service Variables** — scoped to a single service within an environment. Set in the service's "Variables" panel. Not visible to other services.

**Shared Variables** — defined at the environment level and injected into every service in that environment. Use for values that every service needs (e.g., `ENVIRONMENT=production`, shared API keys).

### Reference Variables — cross-service injection

Reference Variables pull a value from another service in the same environment:

```text
DATABASE_URL=${{Postgres.DATABASE_URL}}
CACHE_URL=${{Redis.REDIS_URL}}
WORKER_SECRET=${{worker-service.INTERNAL_SECRET}}
```

- The source service name is case-sensitive and must match the Railway dashboard label.
- Reference Variables resolve at deploy time; services see the resolved value, not the reference syntax.
- Use Reference Variables for all inter-service credential sharing instead of copy-pasting connection strings. Copied strings become stale when the source changes; Reference Variables do not.

### Variable scope discipline

| Secret type | Where to put it |
| --- | --- |
| Database connection string (Plugin) | Reference Variable (`${{Postgres.DATABASE_URL}}`) |
| Third-party API key (e.g., Stripe) | Service Variable on the service that needs it |
| Shared internal token used by many services | Shared Variable or a reference from the service that owns it |
| CI/CD token for deploy | Service Token (not a Variable at all) |
| Sensitive config per-environment | Service Variable in each environment separately; never copy prod values to dev |

## Service Tokens

A Service Token is a scoped credential that grants programmatic access to deploy a specific Railway service. Use it in CI/CD pipelines instead of your personal account credentials.

**Create a Service Token:**

1. Railway dashboard → Project → Service → Settings → "Service Tokens".
2. Create a token; copy it immediately (it is shown only once).
3. Inject it into CI as `RAILWAY_TOKEN`.

```yaml
# GitHub Actions example
- name: Deploy to Railway
  env:
    RAILWAY_TOKEN: ${{ secrets.RAILWAY_TOKEN }}
  run: railway up --service my-api --detach
```

**Token scope:**

- A Service Token grants deploy access to a single service in a single environment. It cannot access other services or other environments.
- Generate one token per service per environment (e.g., `api-production`, `api-staging`). Do not reuse tokens across environments.
- Rotate tokens on team member departure or after any suspected exposure.

## Project Tokens (deprecated pattern)

Project tokens grant broader project-level access. Prefer Service Tokens for CI/CD pipelines — their blast radius is smaller. Use a project token only if you genuinely need multi-service deploy access from a single pipeline.

## GitHub OAuth scope

Railway's GitHub integration requests OAuth permissions to read repos and optionally write deploy statuses. Review and minimize:

- **Minimum needed:** read access to the repo(s) that Railway builds from.
- **Railway requests:** by default, Railway may request access to all repositories. During installation, select "Only selected repositories" and choose only the repos you use with Railway.
- Review authorized apps at `github.com/settings/applications` periodically. Revoke Railway if you no longer use it for a repo.
- Railway's GitHub App can be installed at the org level or user level — prefer org-level with restricted repo access for team projects.

## Secret rotation

**Plugin credentials (Postgres, Redis, MySQL, MongoDB):**

- Re-creating the Plugin generates new credentials. Update all Reference Variables — they resolve automatically.
- Coordinate a maintenance window; existing connections will drop when the Plugin is re-created.
- Prefer re-creation over manual password changes for simplicity.

**Third-party API keys (Stripe, SendGrid, etc.):**

1. Generate a new key at the provider.
2. Add the new key as a Variable.
3. Redeploy the service.
4. Verify the service is healthy with the new key.
5. Revoke the old key at the provider.

**Service Tokens:**

1. Create a new Service Token.
2. Update the secret in the CI provider (GitHub Actions secrets, etc.).
3. Trigger a test deploy to verify the new token works.
4. Revoke the old token in the Railway dashboard.

## Deployment protection (Pro plan)

Railway Pro plan supports deployment protection on environments, requiring approval before a deploy proceeds. Enable for production environments:

- Dashboard → Environment → Settings → "Deployment Protection".
- Approvers are notified and must approve before Railway applies the new deploy.
- Pairs with branch-protection rules in GitHub — PR must be approved before merging to the branch that Railway auto-deploys from.

## Team and permission model

| Role | Access |
| --- | --- |
| Admin | Full project control including billing, tokens, variable visibility |
| Member | Can deploy, view logs, see variables. Cannot manage tokens or billing |
| Viewer | Read-only access to logs and metrics |

- Assign the least-privileged role. Give Members access only to the environments they manage.
- Revoke access promptly when a team member leaves.
- Railway does not currently support per-environment role scoping (as of 2026-05) — role applies project-wide.

## MFA (Multi-Factor Authentication)

- Enable MFA on your Railway account under Account Settings → Security.
- For team accounts, Railway does not yet enforce org-wide MFA — enforce it as a policy and verify during access reviews.
- Use a TOTP authenticator app (Authy, 1Password, Google Authenticator), not SMS.

## Audit log access

- Railway project audit logs are available under Project Settings → Activity.
- Logs show deploys, environment changes, variable changes, and team member actions.
- Export is not automated — review manually or export periodically for compliance records.
- For Pro plan projects, contact Railway support for extended log retention.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Copying Plugin connection strings into Variables manually | String becomes stale when Plugin is re-created. Use Reference Variables. |
| One Service Token for all environments | Token exposure = all environments compromised. One token per environment. |
| Railway GitHub App with all-repos access | Unnecessary read access to repos unrelated to Railway. Scope to specific repos. |
| Prod Variables copy-pasted to staging | Staging workloads accidentally write to prod databases, send real emails, etc. |
| No rotation schedule for API keys | Long-lived keys extend the window of exposure after a leak. Rotate quarterly. |
| Viewer-level variables visible to all members | Railway members can see Variables — don't store plaintext secrets you'd never show a contractor. |
| Skipping deployment protection on production | Any team member (or compromised token) can push to production without review. |

## Security defaults

- All Variables (including those marked sensitive) are encrypted at rest in Railway's infrastructure.
- Variables are not logged in build or deploy output by default — ensure your application does not log them.
- Reference Variables never expose the raw value in the variable panel of the consuming service — the resolved value is only available inside the running container.
- Service Tokens: treat as production secrets — store in CI secret management (GitHub Actions Secrets, not in `.env` files committed to repos).
- Secrets committed to a public repo before Railway integration: rotate immediately, do not rely on Git history removal alone.

## Observability defaults

- Variable changes appear in the project Activity log with actor and timestamp.
- Deploy events (triggered by whom, from which branch, which service) are in the Activity log.
- Railway does not currently provide a dedicated security event stream — pipe Activity log entries to a SIEM manually if required.

## Cost considerations

- Security features (deployment protection, audit log) are Pro plan features.
- Free plan projects: no deployment protection; audit log retention is limited.
- Token proliferation is a security risk, not a cost issue — track and rotate regularly regardless of plan.

## Verification checklist

Before declaring a Railway security configuration complete:

- [ ] All Plugin connection strings injected via Reference Variables, not copy-pasted.
- [ ] Third-party secrets stored as Service Variables scoped to only the services that need them.
- [ ] One Service Token per service per environment in CI/CD; no personal credentials in CI.
- [ ] GitHub OAuth app scoped to specific repos only; reviewed in GitHub settings.
- [ ] Production environment has deployment protection enabled (Pro plan).
- [ ] MFA enabled on all Railway accounts with admin or member access.
- [ ] Team roles assigned at least-privilege; promptly revoked on departure.
- [ ] Rotation schedule defined for API keys (quarterly or on team member departure).
- [ ] Activity log reviewed monthly for unexpected deploys or variable changes.
- [ ] No secrets in `railway.json`, `railway.toml`, or any file committed to the repo.
