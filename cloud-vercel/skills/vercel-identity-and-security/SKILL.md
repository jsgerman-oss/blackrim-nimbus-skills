---
name: vercel-identity-and-security
description: Design or audit Vercel identity and security posture — team membership and roles, Project / Team access controls, Vercel Authentication (SSO), Deployment Protection (Vercel Auth, Password, Trusted IPs, Bypass tokens), WAF (custom + managed rules), DDoS mitigation, Attack Challenge Mode, environment variable encryption, and Sensitive flag usage. Use when hardening a project before launch, onboarding a new team, or auditing access controls.
---

# Vercel Identity and Security

## When to use

- Onboarding a team to Vercel and assigning roles.
- Setting up SSO for a Vercel team.
- Hardening Preview deployments against unauthorized access.
- Adding WAF rules to a Production project.
- Rotating bypass tokens or deployment secrets.
- Auditing who has access to what within a Vercel team.

## Team and project roles

Vercel uses a two-level access model: **Team** roles and **Project** roles.

### Team roles

| Role | What they can do |
| --- | --- |
| Owner | Full control: billing, SSO, member management, delete team |
| Member | Create projects, deploy, manage project settings |
| Viewer | Read deployments, logs, and analytics; no writes |
| Developer (Enterprise) | Member-equivalent with configurable project-level restrictions |
| Billing (Enterprise) | Billing only; no project access |

**Principle of least privilege:** most contributors need Member or Viewer. Reserve Owner for the engineering leads who need billing and SSO control.

### Project access

Individual projects can be restricted to specific team members (Enterprise plan). By default, all team members can access all projects.

## Vercel Authentication (SSO)

Enterprise teams can enforce SSO via SAML 2.0 or OIDC:

- **Supported IdPs:** Okta, Entra ID (Azure AD), Google Workspace, OneLogin, custom SAML.
- **SCIM provisioning:** Okta and Entra ID support automatic user provisioning and deprovisioning.
- **Enforcement:** once SSO is configured and enforced, team members must authenticate through the IdP. Token-based access (Vercel CLI, API tokens) is still permitted for non-interactive flows.

SSO does not automatically protect deployments — that is a separate control (Deployment Protection, below).

## Deployment Protection

Deployment Protection gates access to Vercel deployments. Three mechanisms:

### 1. Vercel Authentication (recommended for teams)

Preview and branch deployments require the viewer to be authenticated to the Vercel team. Zero-config if the viewer has a Vercel account on the team. No credentials to share.

```
Project Settings → Deployment Protection → Vercel Authentication → On
```

**Limitation:** requires the viewer to have a Vercel account. Not suitable for external stakeholders without Vercel access.

### 2. Password Protection

A shared password gates access to preview deployments. Vercel stores a session cookie after the password is entered.

- Set a strong, randomly generated password (not a word).
- Rotate it when a team member leaves.
- Suitable for external reviewers who cannot or will not create a Vercel account.

### 3. Trusted IPs (Enterprise)

Restrict deployment access to a list of CIDR ranges. Useful for internal preview environments that should be reachable only from corporate IPs or VPN.

### Bypass tokens (`VERCEL_AUTOMATION_BYPASS_SECRET`)

Automation (CI, screenshot tests, synthetic monitors) needs to access protected deployments without going through the auth flow. The Automation Bypass token allows this:

```http
GET /protected-path
Cookie: _vercel_jwt=<bypass-token>
```

Or pass as a query parameter: `?_vercel_jwt=<token>`.

**Security requirements for bypass tokens:**

- Treat as a secret — store in CI secrets, not in code.
- Rotate quarterly or on team membership changes.
- Never include in client-side code or public build artifacts.
- Set via the Vercel Dashboard, not `vercel.json`.

**Default:** Deployment Protection is ON for Preview deployments in new projects. Do not disable it without a documented reason.

## WAF (Web Application Firewall)

Vercel WAF is available on Pro and Enterprise plans. It sits in front of all Vercel edge traffic for the project.

### Managed rule sets

| Rule set | What it blocks |
| --- | --- |
| OWASP Core Rule Set | Common web exploits (SQLi, XSS, command injection) |
| Known bad IPs | Requests from known threat actors and bots |
| AI bots | AI training crawlers (configurable — allow or block) |

Enable managed rules in Project Settings → WAF. Start in **Log** mode, review false positives for 24–48 hours, then switch to **Block**.

### Custom rules

Custom rules let you match on headers, paths, country, IP CIDR, JA3 fingerprint (TLS fingerprint), and more:

```json
{
  "name": "Block non-EU traffic on /admin",
  "action": "block",
  "conditions": [
    { "type": "path", "op": "prefix", "value": "/admin" },
    { "type": "geo_country", "op": "not_in", "value": ["DE", "FR", "GB", "NL"] }
  ]
}
```

**WAF rule authoring discipline:**

- Log first, enforce after reviewing hits.
- Test rules against a Preview deployment before enabling on Production.
- Custom rules fire before managed rules; order matters for overlapping conditions.

### Rate limiting

Vercel Pro/Enterprise includes rate limiting as a WAF rule type:

```json
{
  "name": "Rate limit login",
  "action": "rate_limit",
  "conditions": [{ "type": "path", "op": "equals", "value": "/api/auth/login" }],
  "rate_limit": { "requests": 10, "window": "60s", "by": "ip" }
}
```

Set rate limits on every unauthenticated mutation endpoint. A public login, signup, or password-reset route without rate limiting is vulnerable to credential stuffing.

## DDoS mitigation and Attack Challenge Mode

Vercel provides automatic DDoS mitigation at the edge for all plans.

**Attack Challenge Mode** is an additional layer that presents an interactive challenge (Turnstile / JavaScript challenge) to all visitors when an attack is detected or configured:

- **Automatic:** Vercel detects a traffic spike and enables challenge mode temporarily.
- **Manual:** enabled from the Dashboard during a known attack.
- **Per-rule:** trigger a JS challenge instead of a hard block for specific WAF rule matches.

Attack Challenge Mode is a blunt instrument — enable manually only when you know you are under attack and the cost of degraded UX is lower than the cost of the attack.

## Environment variable security

Vercel stores env vars encrypted at rest. The **Sensitive** flag provides additional protection:

| Flag | Behavior |
| --- | --- |
| Plain | Visible in the Dashboard, returned via Vercel API, logged in some contexts |
| Sensitive | Masked in the Dashboard, not returned via API, never logged |

**Rule:** any value that is a credential, API key, JWT signing secret, or service token MUST be marked Sensitive. Set this at creation time — you cannot make a plain env var Sensitive retroactively without deleting and recreating it.

```bash
# Vercel CLI — set a sensitive env var
vercel env add DATABASE_PASSWORD production --sensitive
```

**Rotation practice:**

- Rotate Sensitive env vars when a team member with access leaves.
- Never share env var values via Slack or email — use `vercel env pull` to a local `.env.local` (which is gitignored).
- The `vercel env pull` command writes values to `.env.local`. Confirm `.env.local` is in `.gitignore` before running.

## Security headers via `vercel.json`

Add security headers globally via the `headers` key in `vercel.json`:

```json
{
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        { "key": "Strict-Transport-Security", "value": "max-age=63072000; includeSubDomains; preload" },
        { "key": "X-Content-Type-Options", "value": "nosniff" },
        { "key": "X-Frame-Options", "value": "DENY" },
        { "key": "Referrer-Policy", "value": "strict-origin-when-cross-origin" },
        { "key": "Permissions-Policy", "value": "camera=(), microphone=(), geolocation=()" }
      ]
    }
  ]
}
```

For Content-Security-Policy, set it in Edge Middleware where you can inject nonces for inline scripts dynamically — a static CSP in `vercel.json` typically cannot accommodate nonces.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Deployment Protection off for Preview | Preview URLs contain your unreleased code and potentially real data from staging APIs. |
| Bypass token in a public GitHub Actions step | Token leaks into the Actions log, accessible to any repo collaborator. |
| Plain env vars for API keys | Visible via Vercel API and CLI to all team Members — not just Owners. |
| WAF rules deployed straight to Block without Log review | False positives block real users. Always log first. |
| Shared Vercel account (one login for the whole team) | No auditability, no role separation, no SSO. Create individual accounts. |
| `vercel env pull` without confirming `.gitignore` | Committing `.env.local` is a credential leak. |
| Owner role for every engineer | Billing and SSO control for the whole team. Use Member role for engineers. |

## Security defaults at project creation

- Deployment Protection: ON for Preview (Vercel Auth if team members are reviewers; Password if external reviewers are involved).
- All secret env vars: Sensitive flag set.
- WAF managed rules: enabled in Log mode; evaluate and switch to Block within the first week.
- Rate limiting: configured on `/api/auth/*` and any unauthenticated mutation endpoint.
- HSTS header: set with `max-age=63072000; includeSubDomains`.
- `X-Content-Type-Options: nosniff` and `X-Frame-Options: DENY`: set globally.

## Observability defaults

- Vercel audit logs (Enterprise): record team membership changes, env var access, and project setting changes. Export to SIEM via Logs Drain.
- WAF: log blocked and challenged requests. Set up a Logs Drain to ship WAF events to your SIEM for alerting.
- Track deployment bypass token usage in access logs — unexpected usage is an indicator of token leakage.

## Cost considerations

- WAF is a Pro/Enterprise feature. Managed rules are included; custom rules and rate limiting may have usage-based components at Enterprise scale — verify with Vercel pricing.
- Deployment Protection (Vercel Auth, Password) is included on all paid plans.
- Trusted IP allowlists are Enterprise-only.
- SSO and SCIM provisioning are Enterprise-only.

## IaC hints

- Terraform `vercel/vercel` provider: `vercel_project_environment_variable` with `sensitive = true` creates Sensitive env vars. `vercel_team_member` manages role assignments.
- WAF rules are not yet fully supported in the Terraform provider (as of provider v1.x) — manage via Dashboard or Vercel API.
- Deployment Protection settings are configurable via the Vercel API (`PATCH /v9/projects/{id}`) even if not exposed in the Terraform provider.

## Verification checklist

- [ ] Deployment Protection enabled on all Preview deployments.
- [ ] Bypass token (`VERCEL_AUTOMATION_BYPASS_SECRET`) stored as CI secret, not in code.
- [ ] All credential env vars marked Sensitive.
- [ ] WAF managed rules enabled; custom rate-limiting rules on auth endpoints.
- [ ] Security headers (HSTS, X-Content-Type-Options, X-Frame-Options, Referrer-Policy) set.
- [ ] Team roles follow least privilege — Owner only for those who need billing/SSO control.
- [ ] SSO configured for teams on Enterprise plan.
- [ ] `.env.local` in `.gitignore`; `vercel env pull` not committed.
- [ ] Bypass token rotation schedule documented.
