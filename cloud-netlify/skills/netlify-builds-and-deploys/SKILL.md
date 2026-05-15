---
name: netlify-builds-and-deploys
description: Configure or debug Netlify builds and deployments — netlify.toml, build environment, Deploy Previews, Branch Deploys, Atomic Deploys, Instant Rollback, Build Plugins, framework presets, Skip CI, and build minutes budgeting. Use when setting up a new site, tuning build performance, debugging a broken deploy, or reviewing CI/CD posture.
---

# Netlify Builds and Deploys

## When to use

- Setting up a new site's build pipeline from scratch.
- Migrating from the Netlify dashboard into `netlify.toml`.
- Debugging a build failure or a broken Deploy Preview.
- Choosing or validating a framework preset (Next.js, Astro, SvelteKit, Nuxt, Vite).
- Auditing build minutes consumption and optimizing build speed.
- Reviewing Branch Deploy and Deploy Preview configuration for a team.
- Adding or configuring Build Plugins (community or custom scoped).

## `netlify.toml` — the canonical IaC

Everything that can go in `netlify.toml` should go in `netlify.toml`. Dashboard overrides drift silently and are unreviewed.

Minimum production `netlify.toml`:

```toml
[build]
  command   = "npm run build"
  publish   = "dist"            # or "out", ".next", "build" — framework-specific
  functions = "netlify/functions"

[build.environment]
  NODE_VERSION = "20"           # pin explicitly; never rely on platform default
  NPM_FLAGS    = "--legacy-peer-deps"   # only if needed

[context.production]
  command = "npm run build"

[context.deploy-preview]
  command = "npm run build"

[context.branch-deploy]
  command = "npm run build"

[[headers]]
  for = "/*"
  [headers.values]
    X-Frame-Options            = "DENY"
    X-Content-Type-Options     = "nosniff"
    Referrer-Policy            = "strict-origin-when-cross-origin"
    Permissions-Policy         = "camera=(), microphone=(), geolocation=()"
    Strict-Transport-Security  = "max-age=63072000; includeSubDomains; preload"
    Content-Security-Policy    = "default-src 'self'; script-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none';"
```

Security headers belong in `netlify.toml` (or `_headers`), not the app layer. Once set here they apply even if the origin drops them.

## Build environment — Ubuntu 22.04 (Jammy)

The default build image is Ubuntu 22.04 as of 2024. Key facts:

- Default Node.js version changes between build image releases — **always pin** `NODE_VERSION` in `[build.environment]`.
- `RUBY_VERSION`, `PYTHON_VERSION`, `GO_VERSION`, `HUGO_VERSION`, `PHP_VERSION` all supported as environment variables.
- Pre-installed tools: `npm`, `yarn`, `pnpm`, `bun`, `go`, `python3`, `ruby`, `hugo`, `deno`.
- Persistent cache: `node_modules/`, Yarn/pnpm stores, Go module cache are automatically cached between builds.
- Build timeout: 15 minutes (Starter), 30 minutes (Pro / Enterprise). Large monorepos may need `--filter` flags or `NETLIFY_BUILD_BASE` tricks.

```toml
[build.environment]
  NODE_VERSION  = "20"
  PNPM_VERSION  = "9"
```

## Deploy Previews

Every pull request gets a unique Deploy Preview URL (`deploy-preview-<PR#>--<site-name>.netlify.app`). Key behaviors:

- Built on every push to the PR branch.
- Uses `[context.deploy-preview]` in `netlify.toml` if present; falls back to `[build]`.
- Deploy Preview context sets `CONTEXT=deploy-preview` and `DEPLOY_URL` in the build environment.
- Persists until the PR is merged or the branch is deleted (then expires in 90 days by default).

**Access control.** For private codebases, gate Deploy Previews behind Visitor Access (site password or Identity role) so preview URLs aren't publicly crawlable. See `netlify-identity-and-security` skill.

**Environment variables in previews.** Variables scoped to `Deploy previews` context appear in preview builds only — use this to point previews at staging backends, not production APIs.

## Branch Deploys

Branch deploys create live URLs for long-lived non-production branches (`<branch-name>--<site-name>.netlify.app`).

```toml
[build]
  # ...

# Allow branch deploys only for named branches
[context."staging"]
  command = "npm run build:staging"

[context."release/*"]
  command = "npm run build"
```

Configure which branches get auto-published under **Site configuration → Build & deploy → Branch deploys** in the dashboard, or lock to specific patterns.

## Atomic Deploys and Instant Rollback

Every Netlify deploy is atomic — the CDN flips to the new version as a single unit; no partially-deployed states. This means:

- Rolling back is a one-click (or one-CLI) operation: `netlify deploy --prod --dir=<dir>` with an older build, or use the dashboard Deploys list to publish any previous deploy.
- The `--alias` flag creates a named deploy URL (`netlify deploy --alias=staging`) without changing the production pointer.
- Instant Rollback does not re-run the build; it republishes a previous snapshot. For broken builds, fix the code and redeploy.

## Build Plugins

Build Plugins run at defined lifecycle hooks: `onPreBuild`, `onBuild`, `onPostBuild`, `onSuccess`, `onError`, `onEnd`.

Installing a community plugin in `netlify.toml`:

```toml
[[plugins]]
  package = "@netlify/plugin-lighthouse"

[[plugins]]
  package = "netlify-plugin-checklinks"
  [plugins.inputs]
    todoPatterns = ["TODO", "FIXME"]
```

Run `npm install --save-dev @netlify/plugin-lighthouse` — plugins must be in `devDependencies`.

Recommended production Build Plugins:

| Plugin | Purpose |
| --- | --- |
| `@netlify/plugin-lighthouse` | Lighthouse score gate — fails deploy if score drops |
| `netlify-plugin-a11y` | Accessibility audit on every deploy |
| `netlify-plugin-checklinks` | Broken link detection |
| `@netlify/plugin-nextjs` | Required for Next.js App Router / Image Optimization on Netlify |
| `netlify-plugin-submit-sitemap` | Auto-submit sitemap on production deploy |

Scoped (local) plugins live under `netlify/plugins/<name>/index.js` and are referenced as `package = "./netlify/plugins/<name>"`.

## Framework presets

Netlify auto-detects many frameworks. Override detection with explicit `netlify.toml` settings.

| Framework | Build command | Publish dir | Notes |
| --- | --- | --- | --- |
| Next.js (App Router) | `next build` | `.next` | Requires `@netlify/plugin-nextjs`; SSR routes become Functions |
| Astro (SSR) | `astro build` | `dist` | `output: "server"` in `astro.config.mjs`; adapter `@astrojs/netlify` |
| SvelteKit | `vite build` | `build` | Adapter `@sveltejs/adapter-netlify` |
| Nuxt 3 | `nuxt build` | `.output/public` | Server routes → Netlify Functions via `@nuxt/netlify` |
| Vite (static) | `vite build` | `dist` | No special plugin needed |
| Hugo | `hugo --minify` | `public` | Pin `HUGO_VERSION` in environment |
| Gatsby | `gatsby build` | `public` | Gatsby Cloud migration: check plugin compatibility |

For Next.js and SvelteKit, framework-generated server routes and API routes are automatically converted to Netlify Functions by the adapter. Understand this mapping before debugging 404s on dynamic routes.

## Skip CI

To skip a build for a commit that only touches docs or non-code assets, include `[skip ci]` or `[skip netlify]` anywhere in the commit message. This preserves build minutes and avoids unnecessary Deploy Previews.

Be careful: skipping CI on a commit that introduces a real bug means the Deploy Preview reviewers never saw it. Use sparingly and only for clearly non-functional changes.

## Build minutes accounting

Build minutes are consumed per build, including Deploy Previews and Branch Deploys. Key facts:

- Starter plan: 300 minutes/month (shared across all sites in the team).
- Pro plan: 1,000 minutes/month; additional minutes are $7 / 500 min.
- Build time starts when the build runner starts and ends when the deploy completes.
- Monorepos without build caching or `--filter` flags build everything on every push — a major minutes drain.

Optimization strategies:

1. **Cache aggressively.** `node_modules/` is cached by default. For custom caches, use `netlify-plugin-cache`.
2. **Skip CI for non-code commits.** Docs changes, README updates, image optimizations.
3. **Scope Deploy Previews.** Disable auto-deploy-preview for repositories with many non-functional PRs (dependency bots, changelog PRs).
4. **Parallel builds.** Enterprise plan allows concurrent builds; lower plans queue.
5. **Use `netlify deploy --build` locally** for debugging build failures instead of pushing to burn minutes.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| No `NODE_VERSION` pin | Build image update silently changes runtime; breakage in CI, not locally. |
| Dashboard-only settings (no `netlify.toml`) | Unreviewed, unversioned, invisible to new team members. |
| Deploy Previews on a public-by-default site with private data | Preview URLs are guessable; unauthenticated users can reach staging data. |
| Installing Build Plugins without `devDependencies` | Build fails with "Cannot find module" in CI but works locally. |
| `publish` pointing to a non-existent directory | Deploys an empty site silently; no error from the platform. |
| Overriding `netlify.toml` settings from the dashboard | Dashboard wins for some settings; others defer to the file. Undefined behavior is the outcome. |
| Skipping the `[context.deploy-preview]` block | Preview builds inherit `[build]` command without environment differences — staging DB credentials vs prod DB credentials. |

## Security defaults

- Commit `netlify.toml` to source control. Treat it like `Dockerfile` — reviewed in PRs.
- Security headers via `[[headers]]` block or `_headers` file — never rely on the framework to set `Strict-Transport-Security` alone.
- Deploy Previews gated behind Visitor Access for any site with private data.
- Build secrets set as environment variables scoped to the narrowest applicable context, never committed in `netlify.toml`.
- Build Plugins from the community: review the plugin's npm package, check its permissions scope before installing.

## Observability defaults

- Enable deploy notifications (Slack / email) for production deploy success and failure.
- Build logs are available in the Netlify dashboard for 30 days. For longer retention, configure a Logs Drain (Pro+).
- Track `Build time (seconds)` over the Netlify dashboard's build history to detect slow creep.
- Alert on build failures via the Netlify webhook (`incoming_hook_event: deploy_failed`).

## Cost considerations

- Every Deploy Preview burns build minutes. Audit how many bots (Dependabot, Renovate, Snyk) are opening PRs.
- Large site with many pages: consider incremental build options (Next.js ISR, Gatsby DSG) to avoid full rebuilds.
- Build plugin execution adds to build time — measure with `netlify build --dry` or check per-plugin time in build logs.
- Upgrade from Starter to Pro only if you consistently exceed 300 minutes or need concurrent builds; use the dashboard usage graph.

## IaC hints

- `netlify.toml` is the primary IaC surface. Everything else (deploy hooks, environment variables) can be managed via the Netlify CLI or the Terraform `netlify/netlify` provider.
- `netlify env:set`, `netlify env:import` (from `.env` file) for bulk env var management.
- `netlify deploy --prod --dir=<dir> --message="release v1.2.3"` for scripted production deploys.

## Verification checklist

- [ ] `netlify.toml` committed to source, reviewed in the same PR as code.
- [ ] `NODE_VERSION` (and any other runtime version) pinned in `[build.environment]`.
- [ ] Security headers set via `[[headers]]` for `/*` with at minimum HSTS, CSP, X-Frame-Options, Referrer-Policy, Permissions-Policy.
- [ ] Deploy Previews gated (Visitor Access) if the site contains non-public data.
- [ ] Framework adapter / Build Plugin installed as `devDependency` and pinned.
- [ ] Build minutes consumption checked at least monthly; alert threshold configured.
- [ ] Deploy success / failure notifications wired to a real channel.
- [ ] Rollback tested: published a previous deploy manually at least once.
