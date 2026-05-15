---
name: netlify-identity-and-security
description: Design or audit Netlify identity and security posture — Netlify Identity (Gotrue), Visitor Access (basic auth / role-based at edge), site password protection, Single Sign-On, JWT secrets, environment variable scoping (Functions vs Build vs Runtime), DDoS / WAF (Pro+ and Enterprise), and security headers via `_headers` / `netlify.toml`. Use when locking down a site, implementing authentication, rotating secrets, or reviewing a security posture before launch.
---

# Netlify Identity and Security

## When to use

- Adding user authentication to a Netlify site without a separate auth server.
- Restricting access to Deploy Previews or Branch Deploys.
- Protecting a site or section behind a password or role.
- Rotating JWT signing secrets without downtime.
- Auditing environment variable scope (which values are exposed where).
- Configuring security headers (CSP, HSTS, etc.) at the CDN layer.
- Evaluating DDoS and WAF coverage for a Pro or Enterprise plan.

## Netlify Identity (Gotrue)

Netlify Identity is a managed auth service built on the open-source [Gotrue](https://github.com/netlify/gotrue) library. It handles user registration, login (email+password, magic link, OAuth providers), JWT issuance, and user metadata.

**When to use Netlify Identity:**
- Site needs simple user auth without a dedicated backend.
- Users are technical contributors or internal team members.
- You want OAuth social login (GitHub, Google, GitLab) with minimal setup.

**When to prefer an alternative (Auth0, Supabase Auth, Clerk, etc.):**
- More than ~5,000 monthly active users (Netlify Identity has a soft limit; Enterprise is required above that).
- Complex RBAC with fine-grained permissions.
- Multi-tenant applications where tenants need organizational isolation.
- You need SCIM provisioning, directory sync, or enterprise SSO with custom IdP metadata.

### Enabling Identity

In the Netlify dashboard: **Site configuration → Identity → Enable Identity**.

Add the Netlify Identity Widget script to your site's `<head>`:

```html
<script src="https://identity.netlify.com/v1/netlify-identity-widget.js"></script>
```

Or use the `netlify-identity-widget` npm package for SPA integration.

### JWT claims and user metadata

On successful login, the widget issues a JWT stored in `localStorage`. Include it in requests to Functions:

```javascript
// Browser
const user = netlifyIdentity.currentUser();
const jwt = await user.jwt();
fetch("/.netlify/functions/protected", {
  headers: { Authorization: `Bearer ${jwt}` }
});
```

```javascript
// Function — verify and read claims
export const handler = async (event, context) => {
  const { clientContext } = context;
  if (!clientContext?.user) {
    return { statusCode: 401, body: "Unauthorized" };
  }
  const { sub, email, app_metadata, user_metadata } = clientContext.user;
  const roles = app_metadata?.roles ?? [];
  if (!roles.includes("admin")) {
    return { statusCode: 403, body: "Forbidden" };
  }
  // proceed
};
```

### Roles and `app_metadata`

Roles are stored in `app_metadata.roles` (a string array). Set them via:

- The Netlify dashboard (Identity → Users → Edit user).
- A Function that calls the Netlify Identity admin API (`/_netlify/identity/admin/users/<id>` with the `NETLIFY_IDENTITY_ADMIN_TOKEN`).
- An Identity hook (event-triggered Function) that runs on `validate`, `signup`, or `login`.

`app_metadata` is set by your server; users cannot modify it themselves. `user_metadata` is user-editable.

### JWT secret rotation

Netlify Identity signs JWTs with a site-specific secret. To rotate:

1. In **Site configuration → Identity → JSON Web Tokens → JWT secret**, click **Roll secret**.
2. Immediately, all issued JWTs are invalidated.
3. Users must log in again. The widget handles re-auth transparently if the site is open.
4. If you use the JWT secret in external systems (Supabase RLS, custom verifiers), update those with the new secret before rolling.

There is no zero-downtime rotation path for Netlify Identity JWTs — plan the rotation for a low-traffic window and communicate to users if the site is member-only.

## Visitor Access

Visitor Access restricts site or section access at the CDN layer — before the origin or function sees the request. Configured under **Site configuration → Access control → Visitor access**.

### Site password protection

A single shared password for the whole site. Useful for:

- Pre-launch sites that shouldn't be indexed.
- Internal tools that don't need per-user auth.
- Gating Deploy Previews and Branch Deploys from public crawling.

```toml
# netlify.toml — no config here; set via dashboard or CLI
```

```bash
netlify env:set BASIC_AUTH_CREDENTIALS "user:password" --context deploy-preview
```

**Important:** Site password applies to the site globally, including Deploy Previews — this is the correct default for private codebases. Do not disable it for previews unless you have an explicit reason.

### Role-based access via Identity

With Netlify Identity enabled, you can restrict entire paths to authenticated users or specific roles:

In **Site configuration → Access control → Visitor access → JWT-based access control**:

```toml
# netlify.toml
[[redirects]]
  from = "/admin/*"
  to = "/.netlify/identity/authorize"
  status = 401
  force = true
  [redirects.conditions]
    Role = ["admin"]
```

The CDN checks the incoming JWT's `app_metadata.roles` against the condition before allowing the request to reach the origin.

## Single Sign-On (SSO)

Netlify Enterprise supports SAML 2.0 SSO for the Netlify dashboard itself (not site visitors). Configure via **Team settings → SSO → SAML configuration**. Supported IdPs: Okta, Azure AD, Google Workspace, Ping, ADFS.

For site-visitor SSO (OIDC / OAuth), use Netlify Identity's external OAuth providers or a dedicated auth service (Auth0, Clerk).

## Environment variable scoping

Netlify environment variables have three **availability scopes**:

| Scope | Exposed where | Use for |
| --- | --- | --- |
| `Builds` | Build-time only (in build scripts, Build Plugins) | API keys for content fetching at build time, CMS tokens |
| `Functions` | Runtime (Serverless, Edge, Background, Scheduled Functions) | Database credentials, payment keys, Identity admin tokens |
| `Runtime` | Build AND bundled into client-side JS (via frameworks) | Public keys only — this value is visible to every user |

**Critical rule:** Never put a secret in `Runtime` scope. Anything in `Runtime` is effectively public — the browser receives it. `SUPABASE_ANON_KEY` (public-safe) goes in `Runtime`; `SUPABASE_SERVICE_ROLE_KEY` (full DB access) goes in `Functions` only.

Set scope via the Netlify dashboard or CLI:

```bash
netlify env:set STRIPE_SECRET_KEY "sk_live_..." --context production --scope functions
netlify env:set NEXT_PUBLIC_STRIPE_KEY "pk_live_..." --context production --scope runtime
```

For `NEXT_PUBLIC_*` (or `VITE_*`) prefixed variables, the framework will embed these in the client bundle — only ever put public keys here.

## DDoS and WAF

### Starter and Pro plans

Netlify's CDN absorbs volumetric DDoS attacks at the network layer (included at all plan tiers). HTTP-layer DDoS mitigation and WAF rules are not configurable by default on Starter.

Pro plan adds:

- **Rate limiting** — configurable via the dashboard (requests per IP per minute).
- **Bot mitigation** — basic bot scoring on Functions traffic.

### Enterprise plans

Enterprise adds:

- **Managed WAF** — OWASP ruleset + custom rules via the Netlify dashboard.
- **DDoS Advanced Protection** — Netlify's edge shields the origin at L7.
- **IP allowlist / denylist** — per-site IP rules.
- **Custom rate limiting rules** per path.

For sites with significant traffic or sensitive data on Starter/Pro, supplement Netlify's built-in protections with Cloudflare in front of the Netlify origin (point Cloudflare's orange cloud at Netlify's load balancer IP). This gives you Cloudflare's WAF and DDoS protection without an Enterprise plan.

## Security headers

Security headers should be set at the CDN layer — not just in the framework. Use the `[[headers]]` block in `netlify.toml` or the `_headers` file:

### `_headers` file (repo root)

```
/*
  X-Frame-Options: DENY
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
  Permissions-Policy: camera=(), microphone=(), geolocation=()
  Strict-Transport-Security: max-age=63072000; includeSubDomains; preload
  Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self' https:; connect-src 'self' https:; object-src 'none'; base-uri 'none'; frame-ancestors 'none';

/api/*
  Cache-Control: no-store
  X-Robots-Tag: noindex
```

### `netlify.toml` equivalent

```toml
[[headers]]
  for = "/*"
  [headers.values]
    X-Frame-Options            = "DENY"
    X-Content-Type-Options     = "nosniff"
    Referrer-Policy            = "strict-origin-when-cross-origin"
    Permissions-Policy         = "camera=(), microphone=(), geolocation=()"
    Strict-Transport-Security  = "max-age=63072000; includeSubDomains; preload"
    Content-Security-Policy    = "default-src 'self'; script-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none';"

[[headers]]
  for = "/api/*"
  [headers.values]
    Cache-Control = "no-store"
    X-Robots-Tag  = "noindex"
```

Note on CSP: `'unsafe-inline'` for scripts or styles weakens the policy significantly. Use nonces (via an Edge Function that injects a per-request nonce into headers and the HTML `<script>` tags) for a strict CSP with inline script support.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| `STRIPE_SECRET_KEY` in `Runtime` scope | Visible in every user's browser. Full Stripe API access, including charges and payouts. |
| Deploy Previews publicly accessible on a private site | Unauthenticated access to work-in-progress features, staging data, and environment variables baked into the build. |
| `Content-Security-Policy: *` or missing CSP | XSS attacks succeed silently. At minimum, set `default-src 'self'; object-src 'none'`. |
| No JWT validation in Function | Any string that looks like a Bearer token is accepted. Check `clientContext.user` or verify the JWT signature explicitly. |
| Using `user_metadata` for RBAC decisions | `user_metadata` is user-editable; `app_metadata.roles` is server-controlled. RBAC from `user_metadata` can be bypassed by any authenticated user. |
| Rolling the JWT secret without notifying users | All active sessions invalidated simultaneously; users see mysterious auth failures. Communicate before rolling. |
| Site password disabled for Deploy Previews | GitHub PR reviewers and Dependabot PRs create publicly crawlable previews with your dev environment's data. |

## Security defaults

- **All sites:** Security headers in `_headers` or `netlify.toml` at minimum: HSTS (preload-ready), CSP, X-Frame-Options, Referrer-Policy, Permissions-Policy.
- **Private sites:** Deploy Previews behind site password or Visitor Access.
- **Identity-enabled sites:** All Function routes that serve user data validate `clientContext.user` and check `app_metadata.roles`.
- **Environment variables:** Explicit scope on every variable. No secret in `Runtime`. Audit quarterly.
- **JWT secrets:** Document rotation procedure. Rotate at least annually or when a team member with access leaves.
- **Forms:** Honeypot on every form. reCAPTCHA on forms that feed business data.

## Observability defaults

- **Access logs:** Pro+ plan allows Logs Drain to Datadog / Logflare — wire it and alert on `401` / `403` spikes.
- **Identity events:** Netlify Identity emits webhook events on signup, login, and logout. Log these to an audit trail.
- **Security header audit:** Use [securityheaders.com](https://securityheaders.com) after every deploy that modifies `_headers` or `netlify.toml`.
- **Environment variable audit:** Run `netlify env:list` quarterly and compare against expected set; revoke unused variables.

## Cost considerations

- Netlify Identity: up to 1,000 active users on free; Pro includes 5,000. Enterprise for more. At scale, dedicated auth services (Auth0, Clerk) are often cheaper per-MAU.
- WAF / advanced DDoS on Enterprise: evaluate against the cost of a Cloudflare Pro/Business proxy plan + Netlify Pro for most use cases.
- Site password protection: no additional cost at any plan tier.
- SSO for the Netlify dashboard: Enterprise only; factor into the enterprise plan decision.

## IaC hints

- Security headers in `netlify.toml` `[[headers]]` or `_headers` file — both committed to source and reviewed in PRs.
- Environment variables managed via `netlify env:set` (CLI) or dashboard; the community Terraform provider supports env vars but lags the API.
- Identity configuration (providers, registration settings) is dashboard-only; no `netlify.toml` stanza.
- For role assignment automation, use a Netlify Identity hook (Function triggered by `identity-signup` event).

## Verification checklist

- [ ] Security headers present for `/*` at minimum: HSTS, CSP, X-Frame-Options, Referrer-Policy, Permissions-Policy.
- [ ] Deploy Previews behind Visitor Access for any site with non-public data.
- [ ] Every environment variable has an explicit scope; nothing sensitive in `Runtime`.
- [ ] RBAC decisions use `app_metadata.roles`, not `user_metadata`.
- [ ] JWT validation in every Function that serves protected data.
- [ ] JWT rotation procedure documented; schedule in place.
- [ ] Forms have honeypot; business forms have reCAPTCHA.
- [ ] `netlify env:list` output reviewed and trimmed of unused variables.
- [ ] Security headers validated post-deploy (securityheaders.com or equivalent).
