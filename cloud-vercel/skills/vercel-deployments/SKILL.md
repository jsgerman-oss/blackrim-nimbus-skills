---
name: vercel-deployments
description: Design, configure, or debug Vercel deployments — Production / Preview / Branch deploys, Git integrations (GitHub / GitLab / Bitbucket), monorepo configuration, build caching, build environment variables, framework presets (Next.js / SvelteKit / Astro / Remix / Nuxt / Vite), build skipping, and immutable deployments. Use when setting up a new project, tuning build performance, diagnosing a failed deploy, or choosing framework preset settings.
---

# Vercel Deployments

## When to use

- Connecting a Git repository to Vercel for the first time.
- Configuring Production vs Preview branch targets.
- Tuning build cache hit rates or diagnosing cache misses.
- Setting up a monorepo with multiple Vercel projects from a single repo.
- Choosing and customizing a framework preset (Next.js, SvelteKit, Astro, Remix, Nuxt, Vite).
- Diagnosing a failed or stuck build.
- Understanding immutable deployment URLs and promotion mechanics.

## Deployment types

| Type | Trigger | URL pattern | Promoted to production? |
| --- | --- | --- | --- |
| Production | Push / merge to production branch | `project.vercel.app` (alias) | Yes |
| Preview | Push to any non-production branch or PR | `project-<hash>-team.vercel.app` | No — requires explicit promote |
| Branch preview | Persistent per-branch alias | `branch-name.project.vercel.app` | No |

Immutability is a core guarantee: every deployment gets a unique, permanent URL tied to that exact build output. Promotion means assigning an alias (e.g., `www.example.com`) to a previously-built deployment — no rebuild happens.

## Git integration defaults

- **Production branch:** `main` (configurable per project). Pushes here trigger a Production deployment.
- **Preview deployments:** every other branch and every pull request automatically gets a Preview deployment.
- **Deploy hooks:** webhook URLs that trigger a build without a Git push (useful for CMS-triggered ISR rebuilds or scheduled jobs).

### GitHub-specific nuances

- The Vercel GitHub App creates a Check Run on every commit. A failed build fails the check and blocks merge if branch protection rules require it.
- `VERCEL_GIT_COMMIT_SHA`, `VERCEL_GIT_COMMIT_AUTHOR_NAME`, and related env vars are injected automatically during builds — do not set these manually.
- PR previews get a comment with the preview URL; this requires the GitHub App to have write access to the repo.

## Framework presets

| Framework | Preset build command | Output directory | Notes |
| --- | --- | --- | --- |
| Next.js | `next build` | `.next` | App Router default; `output: 'standalone'` not needed on Vercel — Vercel handles it |
| SvelteKit | `vite build` | `.svelte-kit/output` | Requires `@sveltejs/adapter-vercel` |
| Astro | `astro build` | `dist` | Requires `@astrojs/vercel` adapter for SSR; static output needs no adapter |
| Remix | `remix vite:build` | `build` | Requires Vercel adapter or manual `vercel.json` route config |
| Nuxt | `nuxt build` | `.output` | Zero-config with Nitro's Vercel preset |
| Vite (SPA) | `vite build` | `dist` | Static only; no SSR without a framework adapter |

Override the build command and output directory in Project Settings or `vercel.json` when the preset does not match your setup.

## Build caching

Vercel caches `node_modules`, framework build caches (Next.js `.next/cache`, Turbo remote cache), and custom cache keys across builds.

- **Cache hit rate** is visible in the build log under "Restoring Build Cache."
- **Cache miss causes:** changing `package.json` dependencies, switching Node.js version, forcing `vercel --force`.
- **Remote cache with Turborepo:** set `TURBO_TOKEN` + `TURBO_TEAM` env vars; tasks with unchanged inputs skip entirely, dramatically cutting monorepo build time.
- **Custom cache directories:** not directly configurable via `vercel.json` — use Turborepo or framework-native mechanisms.

## Build environment variables

Three scopes — **Development**, **Preview**, and **Production** — each receive distinct values. Best practice:

- Development: local values, non-sensitive, may differ from staging.
- Preview: test/sandbox credentials, scoped to preview environments.
- Production: live credentials, always marked Sensitive.

The `VERCEL_ENV` variable is injected automatically (`development` | `preview` | `production`) — use it in code to branch behavior without adding a manual env var.

## Monorepo configuration

Two patterns:

1. **One project per package.** Create separate Vercel projects, each pointed at the monorepo root but with different Root Directory settings (e.g., `apps/web`, `apps/api`). Each gets independent deployments, domains, and env vars.
2. **Turborepo + Vercel.** Vercel natively supports Turborepo's remote cache. Run `turbo build --filter=web` as the build command; Vercel injects `TURBO_TOKEN` and `TURBO_TEAM` automatically when the integration is connected.

Ignore builds for packages that didn't change:

```bash
# vercel.json or Project Settings → "Ignored Build Step"
npx turbo-ignore
```

`turbo-ignore` exits 1 (skip build) when no files changed that affect the current package.

## Build skipping

Skipping prevents unnecessary builds and minutes consumption:

- **`VERCEL_SKIP_BUILD_STEP` env var:** set to `1` in a build script to conditionally exit early.
- **`turbo-ignore`:** Turborepo-aware; respects the task graph.
- **Ignored Build Step command (Project Settings):** a shell command that exits 0 to skip or 1 to build. Vercel runs it before the full build.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Pushing secrets as plain env vars | Visible in build logs and via Vercel API. Always mark secrets Sensitive. |
| Using `output: 'standalone'` in `next.config.js` on Vercel | Vercel's build system handles standalone output automatically; enabling it manually can break the deployment. |
| `main` branch as both production and active development branch | A broken commit ships to production. Use a `release` or `production` branch as the Vercel production target; merge to it deliberately. |
| Hardcoding preview domain names | Preview URLs are per-commit hashes. Use `VERCEL_URL` env var for dynamic self-reference, not a hardcoded preview domain. |
| `--force` deploys as a habit | Busts the build cache every time. Reserve for actual cache corruption. |
| Multiple projects pointing at the same root directory without a Root Directory override | Both build the same output; one silently shadows the other. |

## Security defaults

- Deployment Protection enabled for all Preview deployments (Vercel Auth by default; Password Protection as a simpler alternative for external reviewers).
- Production deployments protected by your domain's DNS — no extra gate needed, but WAF rules apply.
- Git integration scoped to the minimum: repo read + deployment status write. Do not grant the Vercel GitHub App admin access unless required.
- `VERCEL_AUTOMATION_BYPASS_SECRET` (Deployment Protection bypass token) treated as a secret — rotate quarterly, never expose in client-side code.

## Observability defaults

- Build logs retained per deployment; access via Dashboard or `vercel logs --build <deployment-url>`.
- Build duration visible in the Deployments tab — alert on builds that trend > 2× baseline.
- `VERCEL_GIT_COMMIT_SHA` is available at runtime as well as build time; log it in your application startup so deployment attribution is trivial.

## Cost considerations

- Build minutes are consumed per build, not per deployment alias. Skipping unnecessary builds (turbo-ignore, Ignored Build Step) directly cuts usage.
- Concurrent builds are plan-limited; a queue forms at the limit. Monitor queue time in the dashboard.
- Serverless Function invocations and bandwidth count regardless of whether the build was fast.
- Edge Function invocations are billed per million; a single misconfigured middleware that runs on every route can spike costs.

## IaC hints

- Terraform `vercel/vercel` provider: `vercel_project` resource manages project settings, env vars, and Git integration. `vercel_deployment` is available but prefer Git push triggers over API deployments for auditability.
- The `ignored_build_step` field on `vercel_project` accepts the same shell command as Project Settings.
- Environment variable scopes map to `target` values: `["production"]`, `["preview"]`, `["development"]`.

## Verification checklist

- [ ] Production branch is a deliberate, protected branch — not `main` used as both dev and prod target.
- [ ] Deployment Protection enabled on Preview deployments.
- [ ] All secret values marked Sensitive in env var settings.
- [ ] `VERCEL_URL` used (not hardcoded) for self-referential URLs in server code.
- [ ] Build skipping configured for monorepos (turbo-ignore or Ignored Build Step).
- [ ] Build cache hit rate > 50% on steady-state builds (check the build log).
- [ ] Framework preset override documented if the default was changed.
- [ ] Deploy hook URLs treated as secrets (they trigger authenticated builds without a Git push).
