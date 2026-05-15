---
name: supabase-auth
description: Design or implement Supabase Auth — email/password, magic links, OAuth providers, phone/SMS, MFA (TOTP and WebAuthn/passkeys), JWT structure and custom claims, auth hooks, session management, server-side auth with cookies, and auth redirects. Use when choosing an auth method, designing a user flow, auditing JWT handling, or wiring auth hooks.
---

# Supabase Auth

## When to use

- Choosing and wiring an authentication method for a new project.
- Designing an OAuth flow with provider restrictions.
- Adding MFA (TOTP or WebAuthn / passkeys) to an existing project.
- Inspecting or extending JWT claims with custom access token hooks.
- Debugging session expiry, redirect, or cookie issues.
- Reviewing the auth surface for a security audit.

## Authentication methods

### Email and password

Built-in; enabled by default. Users register with an email and password; Supabase sends a confirmation email before activating the account (configurable).

```typescript
const { data, error } = await supabase.auth.signUp({
  email: "user@example.com",
  password: "secure-password",
});
```

Always enable email confirmation in production (`Auth → Providers → Email → Confirm email: ON`). Disable only during development.

### Magic links / OTP

Passwordless — user receives a one-time link or code via email.

```typescript
const { error } = await supabase.auth.signInWithOtp({
  email: "user@example.com",
  options: { emailRedirectTo: "https://yourdomain.com/auth/callback" },
});
```

OTP codes expire in 1 hour by default (configurable); magic links are single-use.

### OAuth providers

Supabase supports Google, Apple, GitHub, GitLab, Bitbucket, Facebook, Twitter/X, LinkedIn, Slack, Spotify, Discord, Twitch, and others. Configure each in the Dashboard under `Auth → Providers`.

```typescript
const { error } = await supabase.auth.signInWithOAuth({
  provider: "google",
  options: {
    redirectTo: "https://yourdomain.com/auth/callback",
    queryParams: { access_type: "offline", prompt: "consent" }, // for refresh tokens
  },
});
```

**Production requirement:** Restrict allowed OAuth callback URLs to your exact domains in both the Supabase Dashboard (`Auth → URL Configuration → Redirect URLs`) and the provider's developer console. Wildcard redirect URLs are a security vulnerability — an attacker who controls any subdomain can steal authorization codes.

### Phone / SMS

SMS OTP via Twilio, MessageBird, Vonage, or Textlocal. Configure in `Auth → Providers → Phone`.

```typescript
// Send OTP
await supabase.auth.signInWithOtp({ phone: "+15555550100" });

// Verify
await supabase.auth.verifyOtp({ phone: "+15555550100", token: "123456", type: "sms" });
```

SMS OTP should be supplemented with a stronger second factor for sensitive operations.

### Multi-factor authentication

Supabase supports two MFA methods:

**TOTP (Time-based OTP)** — authenticator apps (Google Authenticator, Authy, 1Password):

```typescript
// Enroll TOTP
const { data } = await supabase.auth.mfa.enroll({ factorType: "totp" });
// data.totp.qr_code — display this QR code to the user

// Challenge + verify
const { data: challenge } = await supabase.auth.mfa.challenge({ factorId });
await supabase.auth.mfa.verify({ factorId, challengeId: challenge.id, code });
```

**WebAuthn / Passkeys** (hardware keys, biometric authenticators):

```typescript
const { data } = await supabase.auth.mfa.enroll({ factorType: "webauthn" });
// Triggers WebAuthn browser API
```

Enforce MFA at the database layer with an RLS policy using `auth.jwt()`:

```sql
-- Allow access only if the user has completed MFA (aal2 = second factor verified)
CREATE POLICY "require_mfa"
  ON public.sensitive_data
  FOR ALL
  TO authenticated
  USING ((auth.jwt() ->> 'aal') = 'aal2');
```

`aal1` = first factor only; `aal2` = at least one second factor verified in this session.

## JWT structure and custom claims

Every Supabase JWT payload includes:

```json
{
  "sub": "<user-uuid>",
  "email": "user@example.com",
  "role": "authenticated",
  "aal": "aal1",
  "iss": "https://<project-ref>.supabase.co/auth/v1",
  "aud": "authenticated",
  "exp": 1716000000,
  "iat": 1715996400,
  "app_metadata": { "provider": "google" },
  "user_metadata": { "name": "..." }
}
```

`auth.uid()` extracts `sub`; `auth.role()` extracts `role`; `auth.jwt()` returns the full payload as JSONB for use in RLS policies.

### Custom claims via the custom access token hook

Add arbitrary claims to the JWT without modifying the user_metadata (which is user-writeable and not trusted for authorization):

```sql
-- Create a Postgres function as the hook
CREATE OR REPLACE FUNCTION public.custom_access_token(event jsonb)
RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE
  claims jsonb;
  user_role text;
BEGIN
  -- Look up the user's application role
  SELECT role INTO user_role FROM public.user_roles
    WHERE user_id = (event ->> 'user_id')::uuid;

  claims := event -> 'claims';
  claims := jsonb_set(claims, '{app_role}', to_jsonb(COALESCE(user_role, 'viewer')));
  RETURN jsonb_set(event, '{claims}', claims);
END;
$$;
```

Register the hook in `supabase/config.toml`:

```toml
[auth.hook.custom_access_token]
enabled = true
uri = "pg-functions://postgres/public/custom_access_token"
```

Now RLS policies can use the custom claim:

```sql
CREATE POLICY "admins_only"
  ON public.admin_settings FOR ALL TO authenticated
  USING ((auth.jwt() ->> 'app_role') = 'admin');
```

### Other auth hooks

| Hook | When it fires | Use for |
| --- | --- | --- |
| `before_user_created` | Before a new user record is saved | Block signups from disallowed domains, enforce invite-only |
| `password_verification_attempt` | On every password check | Rate-limit, lock after N failures, custom logging |
| `mfa_verification_attempt` | On MFA code submission | Rate-limit MFA attempts |
| `send_email` | Before sending any auth email | Custom email templates via external provider |
| `send_sms` | Before sending an OTP SMS | Custom SMS provider |

## Session management

### Token lifetimes (configurable in Auth → Settings)

| Token | Default | Notes |
| --- | --- | --- |
| Access token (JWT) | 3600 s (1 hour) | Short-lived by design; reduce for sensitive apps |
| Refresh token | 604800 s (7 days) | Rotating — each use issues a new token |

Reducing the access token lifetime limits the window of JWT-based attacks (stolen token can only be used until expiry). Supabase client libraries auto-refresh transparently.

### Server-side auth (SSR / SSR frameworks)

For Next.js, SvelteKit, Remix, and similar frameworks, use `@supabase/ssr` (replaces the deprecated `@supabase/auth-helpers-*` packages):

```typescript
import { createServerClient } from "@supabase/ssr";

// In a Next.js Server Component / API route
const supabase = createServerClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
  { cookies: { getAll: () => cookieStore.getAll(), setAll: (cookies) => { ... } } }
);

const { data: { user } } = await supabase.auth.getUser();
// Always use getUser() server-side — not getSession(), which trusts the local token without re-validating
```

Never trust `getSession()` on the server side without also calling `getUser()`. `getSession()` reads the session from the cookie without re-validating the JWT signature against the Supabase server.

### Auth redirects

Configure all allowed redirect URLs in `Auth → URL Configuration → Redirect URLs`. Include:

- Your production domain: `https://yourdomain.com/**`
- Local development: `http://localhost:3000/**`
- Preview deploy patterns if using Vercel/Netlify preview URLs: `https://*-yourproject.vercel.app/**`

The wildcard `/**` matches any path under the domain. Never add `**` alone (matches any domain).

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Wildcard redirect URL (`**`) in provider console | Authorization code interception via open redirect. Scope to your exact domains. |
| Using `user_metadata` for authorization decisions | User-writeable; any authenticated user can set their own `user_metadata`. Use `app_metadata` (admin-only) or custom access token claims. |
| Calling `getSession()` server-side for identity | JWT not re-validated; a tampered or stolen session cookie passes the check. Always call `getUser()` server-side. |
| No email confirmation in prod | Allows account creation with any email address; blocks domain-based access control. |
| No MFA requirement for admin surfaces | Phished password = full admin. Enforce `aal2` in RLS for any privileged action. |
| Service role key used for user impersonation | Bypasses all RLS and leaves no audit trail. Use `auth.admin.getUserById()` server-side; never impersonate via service role from client code. |
| Long access token lifetime (> 1 hour) for sensitive apps | Extends the stolen-token blast radius. Reduce to 15–30 minutes for high-sensitivity applications. |

## Security defaults

- Email confirmation enabled in production.
- Redirect URLs allowlisted to exact domains in both Supabase and each OAuth provider's developer console.
- MFA available and encouraged; enforced via `aal2` RLS policy for any admin or privileged surface.
- Access token lifetime at or below 3600 s; consider 900 s for sensitive applications.
- Custom access token hook used for authorization claims; never `user_metadata` for RBAC.
- `auth.users` table never directly exposed via the REST API (it's in the `auth` schema, not `public`, but double-check column grants).

## Observability defaults

- Supabase Dashboard → Auth → Logs for auth events (signups, logins, failures).
- Auth error rate as a dashboard metric — spike in auth errors may indicate credential stuffing or brute force.
- Track MFA adoption rate — low adoption on an org-facing app is a risk signal.
- Alert on `user_deleted` events if unexpected user deletion could indicate an account takeover.

## Cost considerations

- Auth is included in all Supabase plans; no per-user fee.
- SMS OTP costs depend on your upstream SMS provider (Twilio, Vonage, etc.) — Supabase passes through the provider's cost.
- OAuth providers are free; Google Workspace / Apple developer account fees are external.
- Email delivery via Supabase's built-in SMTP is rate-limited on the free tier; configure a custom SMTP provider (Resend, Postmark, SendGrid) for production volumes.

## IaC hints

- Auth settings (`config.toml`): `[auth]` block controls token lifetimes, providers, and hooks.
- Custom SMTP: set via `[auth.email.smtp]` in `config.toml` or Supabase Dashboard.
- Auth hooks: `[auth.hook.*]` in `config.toml`, pointing to Postgres functions or HTTPS endpoints.
- OAuth credentials: store `client_id` and `client_secret` as Supabase secrets (`supabase secrets set`) or in the dashboard; never commit them.

## Verification checklist

- [ ] Email confirmation is enabled in production.
- [ ] OAuth redirect URLs are allowlisted to exact domains in Supabase Dashboard and each provider.
- [ ] No wildcard (`**`) redirect URL entry that would match arbitrary domains.
- [ ] MFA enrolled and enforced via `aal2` RLS policy for any privileged surface.
- [ ] Authorization decisions use custom access token claims or `app_metadata`, never `user_metadata`.
- [ ] Server-side code calls `getUser()` to validate identity, not `getSession()` alone.
- [ ] Custom SMTP configured for production email volumes.
- [ ] Auth hook functions are `SECURITY DEFINER` with minimal privileges and input validation.
- [ ] Access token lifetime reviewed against the sensitivity of the application.
