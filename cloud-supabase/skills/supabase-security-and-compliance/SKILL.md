---
name: supabase-security-and-compliance
description: Audit or harden the security posture of a Supabase project — RLS coverage on every table, service_role discipline, JWT verification, secret management, database password rotation, MFA enforcement, network restrictions (IP allowlists), SOC 2 Type II / HIPAA tier requirements, and audit logging. Use when reviewing a project before launch, running a security audit, or responding to a compliance requirement.
---

# Supabase Security and Compliance

## When to use

- Pre-launch security review of a Supabase project.
- Compliance assessment for SOC 2, HIPAA, or similar frameworks.
- Auditing RLS coverage across all application tables.
- Reviewing secret management and key rotation practices.
- Hardening a project found to have a security issue.
- Designing a security posture for a new multi-tenant application.

## The most common Supabase security failure: missing or incomplete RLS

Row Level Security is the single most important security control in Supabase. Because Supabase exposes Postgres directly over an HTTP API (PostgREST), every table without RLS — or with an overly permissive policy — is a potential data breach waiting for someone to try a direct API call.

**Every table in the `public` schema must have RLS enabled. No exceptions.**

The audit process:

```sql
-- Find tables in public schema without RLS
SELECT tablename
FROM pg_tables
WHERE schemaname = 'public'
  AND tablename NOT IN (
    SELECT relname FROM pg_class
    WHERE relrowsecurity = true AND relnamespace = 'public'::regnamespace
  );
```

Any row returned by this query is a security gap. Fix it before deploying.

```sql
-- Find tables with RLS enabled but zero policies (= no rows accessible, but also no intentional access grant)
SELECT c.relname AS table_name
FROM pg_class c
JOIN pg_namespace n ON c.relnamespace = n.oid
WHERE n.nspname = 'public'
  AND c.relkind = 'r'
  AND c.relrowsecurity = true
  AND NOT EXISTS (
    SELECT 1 FROM pg_policies p
    WHERE p.schemaname = 'public' AND p.tablename = c.relname
  );
```

A table with RLS but no policies is inaccessible — which may be intentional (admin-only via service role) but is usually an oversight.

## `service_role` discipline

The service role key (`SUPABASE_SERVICE_ROLE_KEY`) bypasses all Row Level Security. It is equivalent to a database superuser credential for data-plane operations.

**Where it must never appear:**

- Client-side JavaScript or TypeScript bundles (React, Next.js client components, Vue, etc.)
- Any file committed to version control
- Browser environment variables (prefixed with `NEXT_PUBLIC_`, `VITE_`, `REACT_APP_`, etc.)
- Mobile app bundles or configuration files shipped to devices
- Logs or error messages

**Where it belongs:**

- Server-side environment only: Next.js server components / API routes, Express / Fastify servers, Edge Functions, GitHub Actions secrets
- Fetched at runtime from a secrets manager (AWS Secrets Manager, HashiCorp Vault, etc.)
- Set as a CI/CD secret and never printed in logs

Detection: search your codebase for the service role key value directly, and for any pattern that might expose it:

```bash
# Check for common exposure patterns in client code
grep -r "SUPABASE_SERVICE_ROLE_KEY\|service_role" \
  --include="*.ts" --include="*.tsx" --include="*.js" --include="*.jsx" \
  src/ pages/ components/ app/
```

Any hit in client-side code directories is a critical finding.

## JWT verification

Supabase issues JWTs signed with your project's JWT secret. Any service that accepts Supabase JWTs must verify the signature.

**Never trust the decoded JWT payload without verification.** A client can construct any claims payload; only a valid signature proves the token came from Supabase.

In Edge Functions, JWT verification is automatic when `verify_jwt = true` (the default). For external services (your own Node.js server, etc.):

```typescript
import { createRemoteJWKSet, jwtVerify } from "npm:jose@5";

const JWKS = createRemoteJWKSet(
  new URL(`${process.env.SUPABASE_URL}/auth/v1/.well-known/jwks.json`)
);

async function verifySupabaseJWT(token: string) {
  const { payload } = await jwtVerify(token, JWKS, {
    issuer: `${process.env.SUPABASE_URL}/auth/v1`,
    audience: "authenticated",
  });
  return payload;
}
```

Alternatively, verify against the raw JWT secret (simpler, appropriate for internal services):

```typescript
import { verify } from "npm:@tsndr/cloudflare-worker-jwt@3";

const valid = await verify(token, process.env.SUPABASE_JWT_SECRET!, "HS256");
```

Never use `none` algorithm or skip algorithm verification.

## Secret management

| Secret | Where to store | Rotation |
| --- | --- | --- |
| Supabase service role key | Server env / CI secret | Rotate via Dashboard → Settings → API → Reset key |
| Database password | Server env / CI secret | Rotate via Dashboard → Settings → Database → Reset password |
| JWT secret | Server env only (never rotate without coordinating token invalidation) | Rare; rotation invalidates all active sessions |
| OAuth client secrets | Supabase secrets (`supabase secrets set`) | Per provider's rotation policy |
| External API keys (OpenAI, Stripe, etc.) | Supabase secrets / server env | Per vendor recommendation |

Supabase Vault (available on Pro+) stores secrets encrypted within the database using `pgsodium`. Use it for secrets that need to be accessed inside Postgres functions or RLS policies:

```sql
-- Insert a secret into Vault
SELECT vault.create_secret('my-api-key', 'sk-...', 'OpenAI API key');

-- Read it in a function (SECURITY DEFINER to access Vault)
CREATE FUNCTION get_api_key() RETURNS text
  SECURITY DEFINER STABLE LANGUAGE sql AS $$
    SELECT decrypted_secret FROM vault.decrypted_secrets WHERE name = 'my-api-key';
  $$;
```

## Database password rotation

Rotate the database password on schedule (quarterly, or after any staff departure) and immediately after a suspected credential leak:

1. Dashboard → Settings → Database → Reset database password.
2. Update `DATABASE_URL` in all server-side environments and CI/CD secrets.
3. Update `supabase/config.toml` if it references the local Postgres password.
4. Test connectivity from all services before closing the rotation window.

## MFA enforcement for team members

Enable MFA for all team members with access to the Supabase Dashboard:

- Dashboard → Organization → Members → enforce MFA requirement (Enterprise feature).
- For self-hosted: configure GoTrue's MFA settings and require TOTP enrollment before granting access.

Enforce MFA at the application level using `aal2` in RLS policies for any privileged surface (see `supabase-auth` skill for implementation).

## Network restrictions (IP allowlists)

Supabase Pro+ supports IP allowlists for database connections:

Dashboard → Settings → Network → Restrict IP access.

Add only the IPs / CIDR ranges of your application servers and CI/CD runners. This prevents an attacker who obtains the connection string from connecting from an arbitrary network.

For the REST API and Auth endpoints: use Cloudflare WAF, your CDN's IP filtering, or an API gateway in front of Supabase for additional network-layer controls.

## Audit logging

Supabase logs are available via:

- Dashboard → Logs: filterable view of API, Auth, Edge Functions, and Postgres logs.
- Log Drains (Pro+): stream logs to an external SIEM (Datadog, Grafana Loki, Elastic) via HTTP.

Configure log drains for any project with a compliance requirement. Retention in the dashboard is limited; an external SIEM provides durable audit trails.

Events to monitor and alert on:
- Unusual auth events: `sign_up` from unexpected domains, high rate of `sign_in` failures (credential stuffing).
- Service role key usage from unexpected IPs.
- Schema changes during off-hours (may indicate unauthorized access).
- Mass DELETE or UPDATE without a WHERE clause in the query log.

## SOC 2 Type II and HIPAA

**Hosted Supabase:**

- SOC 2 Type II: available on Team / Enterprise plans. Request the report via the Supabase Trust Center.
- HIPAA: available on Enterprise with a signed Business Associate Agreement (BAA). Requires Enterprise plan, dedicated infrastructure, and Supabase security review.

On any HIPAA-scope project:
- Enable PITR for the Postgres database.
- Enable audit logging with a durable external log drain.
- Restrict database access via IP allowlists.
- Use Vault for secrets within the database.
- Enforce MFA for all team members.
- Apply encryption in transit (all Supabase endpoints are HTTPS/TLS by default).

**Self-hosted:**
- SOC 2 and HIPAA compliance are entirely your responsibility.
- Use Postgres `pgaudit` extension for detailed query-level audit logging.
- Ensure TLS on all internal services (Supabase Docker Compose supports TLS termination at the load balancer).
- Implement network segmentation to isolate the database from public network access.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Table without RLS enabled | Any authenticated user can read, write, or delete any row via the REST API. |
| `USING (true)` or `WITH CHECK (true)` on a policy without narrowing | Every authenticated user has full access. Defeats RLS entirely. |
| Service role key in a client-side environment variable | Any user who opens DevTools and checks the network tab or source maps can extract it. |
| JWT decoded client-side and trusted for authorization | Unverified claims. A user can forge any claim in the payload. Always verify the signature server-side. |
| Database password never rotated | Increases blast radius of a credential leak; stolen credentials stay valid indefinitely. |
| No log drain configured for a compliance-sensitive project | Dashboard retention is short; regulatory audits require durable, tamper-evident logs. |
| OAuth client secret stored in Supabase Dashboard only, not in a secrets manager | Dashboard is the single point of failure; extraction incident has no mitigation path. |
| MFA disabled for admin users | Phished password = full admin access to all tenant data. |

## Security defaults

- RLS enabled and forced on every table in `public` schema.
- `service_role` key absent from all client bundles, frontend code, and committed files.
- JWT signature verified on every server-side request that relies on identity claims.
- Database password stored in a secrets manager; rotation scheduled quarterly.
- MFA enabled for all project team members.
- IP allowlist configured to application server ranges only (Pro+).
- Log drain active for any project with a compliance scope.
- Vault used for secrets accessed inside Postgres functions.

## Observability defaults

- Auth error rate monitored: high failure rates indicate brute force or credential stuffing.
- Schema change events logged and alerted outside business hours.
- Service role key usage correlated with known server IPs; anomalies trigger investigation.
- Quarterly access review: who has Supabase Dashboard access, what roles do they have.

## Cost considerations

- IP allowlists: Pro+ feature, included in the plan.
- Log drains: Pro+ feature, usage billed by log volume at the destination.
- HIPAA compliance: Enterprise plan required — costs are project-specific.
- Supabase Vault: available on Pro+, no additional cost.
- External SIEM / log aggregation is priced by the vendor.

## IaC hints

- Network restrictions: not yet in the Terraform provider (as of 2026-05); configure via Dashboard or Supabase Management API.
- Log drains: configure via Supabase Management API or Dashboard.
- RLS policies: SQL migrations in `supabase/migrations/`.
- Vault secrets: manageable via `supabase/setup-secrets` scripts or Dashboard.

## Verification checklist

- [ ] `SELECT tablename FROM pg_tables WHERE schemaname = 'public'` returns zero tables without RLS.
- [ ] No policy uses unconditional `USING (true)` or `WITH CHECK (true)` without documented justification.
- [ ] `SUPABASE_SERVICE_ROLE_KEY` absent from all client-side code, browser env vars, and committed files.
- [ ] JWT verification implemented on every external service that consumes Supabase JWTs.
- [ ] Database password is in a secrets manager; rotation scheduled.
- [ ] MFA enabled for all team members with dashboard access.
- [ ] IP allowlist configured in Pro+ projects.
- [ ] Log drain configured and shipping to external SIEM for compliance-scoped projects.
- [ ] Supabase Vault used for secrets accessed inside Postgres functions.
- [ ] For HIPAA: BAA signed, Enterprise plan active, PITR enabled, dedicated infrastructure confirmed.
