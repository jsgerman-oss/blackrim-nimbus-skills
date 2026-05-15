---
description: Scaffold a Netlify site configuration — netlify.toml, _headers, _redirects, Functions and Edge Functions starters, environment variable split, Build Plugin example, and a GitHub Actions CI pipeline for preview and production deploys.
argument-hint: <site-description>
---

# Netlify Scaffold Project

Scaffold a new Netlify site configuration for: **$ARGUMENTS**

## What to do

1. **Confirm the framework.** Ask the user which framework they're using, with a one-line recommendation based on the site description:
   - Content / blog / marketing site → **Astro** (best static output; SSR optional) or **Hugo** (simplest, fastest).
   - React SPA with light server needs → **Vite** + Netlify Functions for API routes.
   - Full-stack Next.js / App Router → **Next.js** with `@netlify/plugin-nextjs`.
   - SvelteKit app → **SvelteKit** with `@sveltejs/adapter-netlify`.
   - Nuxt 3 → **Nuxt** with the Netlify preset.
   Don't prescribe — recommend based on the description, then defer.

2. **Confirm scope** with up to three questions if not obvious:
   - Are there dynamic API routes, user authentication, or server-rendered pages?
   - What are the data needs: Blobs, Forms, external DB (Supabase / PlanetScale), or all static?
   - Is this a public site, member-only site, or internal tool? (Drives default security posture.)

3. **Generate the project scaffold** in the current working directory. Every scaffold must include:
   - `netlify.toml` — build command, publish dir, Node version pin, context overrides, security headers, redirects.
   - `_headers` — security headers for `/*` (belt-and-suspenders alongside `netlify.toml`).
   - `_redirects` — SPA fallback and API proxy rule.
   - `netlify/functions/` directory with a health check function starter.
   - `netlify/edge-functions/` directory with a geo-routing / request-logging starter.
   - `netlify/plugins/` directory if a custom Build Plugin is appropriate.
   - `package.json` snippet showing required `devDependencies` (CLI, Build Plugins).
   - `.env.example` with all expected env vars documented with their correct scope.
   - `.gitignore` entry for `.env`, `.netlify/`.
   - `README.md` section on linking, local dev, and deploy commands.
   - GitHub Actions workflow for preview and production deploys.

4. **Wire production-grade defaults.** For every scaffold:
   - Security headers (HSTS, CSP, X-Frame-Options, Referrer-Policy, Permissions-Policy) in both `netlify.toml` and `_headers`.
   - Node.js version pinned via `[build.environment] NODE_VERSION`.
   - Deploy Previews behind Visitor Access for any non-public site (document the step in README).
   - Env vars split explicitly: public values in `Runtime`, secrets in `Functions`, build tokens in `Build`.
   - Build Plugins for Lighthouse and accessibility gates.
   - `[build] ignore` script to skip builds when only non-functional files change.
   - GitHub Actions stores `NETLIFY_AUTH_TOKEN` and `NETLIFY_SITE_ID` as repository secrets.

5. **Print next steps** — commands the user must run after scaffolding, in order.

---

## Generated file contents

### `netlify.toml`

```toml
[build]
  command        = "<framework-build-command>"
  publish        = "<publish-dir>"
  functions      = "netlify/functions"
  edge_functions = "netlify/edge-functions"
  ignore         = "git diff --quiet HEAD^ HEAD -- src/ netlify.toml"

[build.environment]
  NODE_VERSION = "20"

[context.production]
  command = "<framework-build-command>"

[context.deploy-preview]
  command = "<framework-build-command>"

[context.branch-deploy]
  command = "<framework-build-command>"

# Security headers — applied at CDN, before origin
[[headers]]
  for = "/*"
  [headers.values]
    Strict-Transport-Security = "max-age=63072000; includeSubDomains; preload"
    X-Frame-Options           = "DENY"
    X-Content-Type-Options    = "nosniff"
    Referrer-Policy           = "strict-origin-when-cross-origin"
    Permissions-Policy        = "camera=(), microphone=(), geolocation=()"
    Content-Security-Policy   = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self' https:; connect-src 'self' https:; object-src 'none'; base-uri 'none'; frame-ancestors 'none';"

[[headers]]
  for = "/api/*"
  [headers.values]
    Cache-Control = "no-store"
    X-Robots-Tag  = "noindex"

[[headers]]
  for = "/static/*"
  [headers.values]
    Cache-Control = "public, max-age=31536000, immutable"

# API → Functions proxy
[[redirects]]
  from   = "/api/*"
  to     = "/.netlify/functions/:splat"
  status = 200

# SPA fallback (remove if site is fully static)
[[redirects]]
  from   = "/*"
  to     = "/index.html"
  status = 200

# Build Plugins
[[plugins]]
  package = "@netlify/plugin-lighthouse"
  [plugins.inputs]
    fail_deploy_on_score_regression = "true"
    thresholds_performance          = 0.9
    thresholds_accessibility        = 0.95

[[plugins]]
  package = "netlify-plugin-a11y"

# Edge Functions
[[edge_functions]]
  function = "request-logger"
  path     = "/*"
```

---

### `_headers`

```
# Belt-and-suspenders: headers also declared in netlify.toml
# netlify.toml takes precedence on conflict; both should match.

/*
  Strict-Transport-Security: max-age=63072000; includeSubDomains; preload
  X-Frame-Options: DENY
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
  Permissions-Policy: camera=(), microphone=(), geolocation=()

/api/*
  Cache-Control: no-store

/static/*
  Cache-Control: public, max-age=31536000, immutable
```

---

### `_redirects`

```
# API routes → Netlify Functions
/api/*  /.netlify/functions/:splat  200

# SPA fallback — remove for purely static sites
/*  /index.html  200
```

---

### `netlify/functions/health.js`

```javascript
/**
 * Health check endpoint — GET /api/health
 * Returns 200 with build metadata. Used by uptime monitors.
 */
export const handler = async (_event, _context) => {
  return {
    statusCode: 200,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      status: "ok",
      deployId: process.env.DEPLOY_ID ?? "local",
      context: process.env.CONTEXT ?? "local",
      timestamp: new Date().toISOString(),
    }),
  };
};
```

---

### `netlify/edge-functions/request-logger.ts`

```typescript
/**
 * Request logger edge function — fires on every request.
 * Logs request metadata for observability; does not modify the response.
 * Remove or restrict the `path` binding in netlify.toml if overhead is a concern.
 */
import type { Context } from "netlify:edge";

export default async (request: Request, context: Context): Promise<void> => {
  const url = new URL(request.url);
  console.log(
    JSON.stringify({
      level: "info",
      msg: "request",
      method: request.method,
      path: url.pathname,
      country: context.geo?.country?.code ?? "unknown",
      ip: context.ip,
      ts: new Date().toISOString(),
    })
  );
  // context.next() is called implicitly when the edge function returns void
};
```

---

### `.env.example`

```dotenv
# ── Public (Runtime scope — visible in browser bundles) ─────────────────────
# These are safe to expose. Prefix with NEXT_PUBLIC_ / VITE_ / PUBLIC_ as needed.
NEXT_PUBLIC_SITE_URL=https://www.example.com
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...   # anon key — public-safe

# ── Build-only (Build scope — available during build, not at runtime) ────────
CONTENTFUL_ACCESS_TOKEN=              # CMS read token for build-time data fetch

# ── Server secrets (Functions scope — NEVER expose to the browser) ───────────
SUPABASE_SERVICE_ROLE_KEY=            # Full DB access — Functions only
STRIPE_SECRET_KEY=                    # Stripe server API key — Functions only
STRIPE_WEBHOOK_SECRET=                # Stripe webhook signature — Functions only
DATABASE_URL=                         # Direct DB connection string — Functions only
NETLIFY_IDENTITY_ADMIN_TOKEN=         # Identity admin — Functions only
```

---

### `package.json` (partial — `devDependencies` additions)

```json
{
  "devDependencies": {
    "netlify-cli": "^17.0.0",
    "@netlify/plugin-lighthouse": "^1.0.0",
    "netlify-plugin-a11y": "^0.3.0"
  }
}
```

---

### `.github/workflows/netlify-deploy.yml`

```yaml
name: Netlify Deploy

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write   # for PR comment with preview URL

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: "npm"

      - name: Install dependencies
        run: npm ci

      - name: Build
        run: npm run build
        env:
          # Public env vars passed as build env for the GHA build step.
          # Secrets stay in GitHub Actions secrets; never here.
          NODE_ENV: production

      - name: Deploy Preview
        if: github.event_name == 'pull_request'
        id: deploy-preview
        uses: netlify/actions/cli@master
        with:
          args: deploy --dir=<publish-dir> --alias=preview-${{ github.event.number }} --message="PR #${{ github.event.number }} preview"
        env:
          NETLIFY_SITE_ID: ${{ secrets.NETLIFY_SITE_ID }}
          NETLIFY_AUTH_TOKEN: ${{ secrets.NETLIFY_AUTH_TOKEN }}

      - name: Comment Preview URL on PR
        if: github.event_name == 'pull_request'
        uses: actions/github-script@v7
        with:
          script: |
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: `Deploy Preview ready: ${{ steps.deploy-preview.outputs.NETLIFY_URL }}`
            })

      - name: Deploy Production
        if: github.ref == 'refs/heads/main' && github.event_name == 'push'
        uses: netlify/actions/cli@master
        with:
          args: deploy --dir=<publish-dir> --prod --message="Deploy from main @ ${{ github.sha }}"
        env:
          NETLIFY_SITE_ID: ${{ secrets.NETLIFY_SITE_ID }}
          NETLIFY_AUTH_TOKEN: ${{ secrets.NETLIFY_AUTH_TOKEN }}
```

---

## After scaffolding

### Mandatory next steps (in order)

1. **Install dependencies:**
   ```bash
   npm install
   ```

2. **Link to a Netlify site:**
   ```bash
   npx netlify link
   # If the site doesn't exist yet:
   npx netlify sites:create --name <site-name>
   ```

3. **Set environment variables:**
   ```bash
   # Public (Runtime)
   netlify env:set NEXT_PUBLIC_SUPABASE_URL "https://xxx.supabase.co" --scope runtime
   # Secrets (Functions)
   netlify env:set SUPABASE_SERVICE_ROLE_KEY "eyJ..." --scope functions
   netlify env:set STRIPE_SECRET_KEY "sk_live_..." --context production --scope functions
   ```

4. **Test locally:**
   ```bash
   npx netlify dev
   ```

5. **Add GitHub Actions secrets:**
   - `NETLIFY_SITE_ID` — from `netlify sites:list` or the Netlify dashboard (Site configuration → General → Site ID).
   - `NETLIFY_AUTH_TOKEN` — from Netlify user settings (User settings → OAuth applications → Personal access tokens → New access token).

6. **Configure Visitor Access** (for non-public sites):
   - Netlify dashboard → Site configuration → Access control → Visitor access → Password protection.
   - Enable for Deploy Previews and Branch Deploys.

7. **Hand off to `netlify-architect`** for a pre-launch architecture review before opening traffic.

8. **Run `netlify-security-reviewer`** after the first production deploy to validate security header scores and env var scoping.

---

## Security reminders

- `NETLIFY_AUTH_TOKEN` is stored as a **GitHub Actions secret** — not as a Netlify env var. Anyone with repo access can use a Netlify env var in a custom build step.
- The `_headers` and `netlify.toml` `[[headers]]` CSP policy above uses `'unsafe-inline'` for styles. If your framework does not require inline styles, remove it and tighten.
- Deploy Previews created by fork PRs receive `deploy-preview` context env vars. Restrict auto-previews to team members in the Netlify dashboard if those vars contain any non-public values.
- Rotate the deploy key (Site configuration → Build & deploy → Deploy key) if any repository collaborator with write access leaves the team.
