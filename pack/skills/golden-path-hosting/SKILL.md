---
name: golden-path-hosting
description: Scaffold and deploy a NEW web app end-to-end on the nimbus golden path — vite + voidzero (Vite/Vitest/Rolldown/Oxc) build, a Convex reactive backend, and Cloudflare (Workers static assets or Pages) hosting — from zero to a live URL with production-grade defaults. Use when starting a new app, choosing a hosting stack, wiring CI/CD for a frontend plus backend, or taking a local prototype to a deployed URL. When the golden path does not fit the target cloud, fall back to the 19 cloud-* provider skills.
---

# Golden-path hosting — deploy a new app (vite + voidzero + Cloudflare + Convex)

This is the **opinionated default** for standing up and shipping a new web app on a
gas city: one stack, the fewest decisions, zero to a live URL with production-grade
defaults baked in.

| Layer | Choice | Why |
| --- | --- | --- |
| **Build / test / lint** | **VoidZero** — Vite (build) + Vitest (test) + Rolldown (bundler) + Oxc/oxlint (lint) | One unified, Rust-fast toolchain from one team; no toolchain drift. |
| **Backend / data** | **Convex** — reactive database + serverless functions | Typed end-to-end, transactional, live-updating queries. No glue. |
| **Hosting / edge** | **Cloudflare** — Workers static assets (default) or Pages | Free global CDN, custom domains, WAF, room to add edge logic. |

The clean boundary that makes this work: **Cloudflare owns the edge** (static assets,
CDN, custom domain, WAF), **Convex owns data + server logic + reactivity**, and
**VoidZero owns the build**. Don't blur them — that is the source of most of the
anti-patterns below.

When the golden path doesn't fit, the **escape hatch** is the 19 curated `cloud-*`
provider skills (alibaba, aws, azure, cloudflare, digitalocean, fly, gcp, hetzner,
ibm, linode, netlify, oci, railway, render, scaleway, supabase, tencent, vercel,
vultr). This skill leans on the Cloudflare set for specifics — `cf-iac-and-deployment`,
`cf-workers-and-compute`, `cf-networking-and-edge`, `cf-zero-trust-and-security`,
`cf-observability-and-cost`.

## When to use

- Starting a **new** web app and you control the stack — pick this and go.
- Choosing where to host a frontend + reactive backend, or wiring its CI/CD.
- Taking a local prototype to a real, deployed, shareable URL.
- Adding a typed, live-updating data layer without standing up your own database.
- Reviewing a greenfield repo for production-readiness against a known-good default.

If you're operating an *existing* app on another cloud, or the constraints below push
you off the golden path, use the matching `cloud-*` provider skill instead.

## Decision tree

**Is the golden path right for this app?**

1. New app, you choose the stack, want the fewest decisions → **golden path** (this skill).
2. Must target a specific non-Cloudflare cloud (compliance, existing account, data
   residency) → drop to the matching `cloud-*` provider skill; keep what still fits.
3. Need a relational/SQL database, an existing Postgres, or heavy analytical queries →
   Convex may not fit. Consider `cloud-supabase` (managed Postgres) for data and keep
   Cloudflare for hosting.
4. Need long-running servers, containers, GPUs, or arbitrary binaries → this isn't an
   edge-static workload. See `cf-workers-and-compute` (Containers) or a VM provider skill.

**Which Cloudflare hosting model?**

1. SPA + Convex, want CLI/IaC deploys and room to add edge logic later →
   **Workers static assets** (the default — single `wrangler deploy`).
2. Want a dashboard Git-connected pipeline with automatic per-PR preview URLs and zero
   wrangler config → **Cloudflare Pages**.
3. Need SSR or server routes (a framework with a Cloudflare adapter — TanStack Start,
   React Router, Astro SSR) → **Workers** with the framework adapter and a `main` entry.

## Defaults

### Scaffold (VoidZero)

```bash
npm create vite@latest my-app -- --template react-ts
cd my-app
npm i -D vitest oxlint
```

Opt into the **Rolldown** bundler — the VoidZero toolchain standardizes on it — by
adding an override to `package.json` (it is becoming the default Vite bundler; check
whether your Vite already ships it before pinning):

```json
{
  "overrides": { "vite": "npm:rolldown-vite@latest" }
}
```

- **Test on Vitest, lint on oxlint.** One test runner, one linter — never ESLint *and*
  oxlint, or Jest *and* Vitest, side by side.
- **Typecheck explicitly**: Vite does not typecheck during build. Run `tsc --noEmit`
  (or `vue-tsc`) in CI as its own gate.
- Format with Prettier (or the emerging Oxc formatter once stable) — keep it a single
  formatter, run in CI.
- `npm run build` must produce a static `dist/`.

### Backend (Convex)

```bash
npm i convex
npx convex dev   # one-time: login, create a dev deployment, generate convex/_generated
```

- **Define `convex/schema.ts`** with validators before you ship — a schemaless prod
  deployment drifts and lands bad data silently.
- Queries / mutations / actions live in `convex/*.ts`; **validate every public
  function's args** and check identity inside the function — never trust the client.
- Wire the React client once, reading the URL from the build env:

  ```tsx
  // src/main.tsx
  import { ConvexProvider, ConvexReactClient } from "convex/react";
  const convex = new ConvexReactClient(import.meta.env.VITE_CONVEX_URL as string);
  // <ConvexProvider client={convex}><App /></ConvexProvider>
  ```

- Reactive `useQuery(api.foo.bar)` re-renders live; mutate with `useMutation`.
- **Server-side secrets** (third-party API keys used by Convex *actions*) live in
  **Convex** env, not Cloudflare: `npx convex env set STRIPE_KEY sk_…`.
- For auth, default to **Convex Auth** (`@convex-dev/auth`) or Clerk; enforce it in
  queries/mutations, not just the UI.

### Hosting (Cloudflare — Workers static assets, the default)

```toml
# wrangler.toml
name = "my-app"
compatibility_date = "2025-09-01"   # pin; advance deliberately (see cf-workers-and-compute)

[assets]
directory = "./dist"
not_found_handling = "single-page-application"   # SPA client-side routing fallback
```

Deploy with `npx wrangler deploy`. Need an API route alongside the static site? Add a
`main = "src/worker.ts"` entry and an `[assets] binding = "ASSETS"` — but for a pure
SPA + Convex app you don't, and shouldn't add one for data access (that's Convex's job).

**Pages alternative**: connect the Git repo in the dashboard with build `npm run build`
and output `dist/` (or `npx wrangler pages deploy dist`). You get automatic per-PR
preview deployments for free — the reason to pick Pages over Workers.

Custom domain, caching, WAF, and security headers: see `cf-networking-and-edge` and
`cf-zero-trust-and-security`.

### Env & secrets boundary

| Concern | Lives in | Exposure |
| --- | --- | --- |
| Convex deployment URL (`VITE_CONVEX_URL`) | `.env.local` (dev) / build env (prod) | **Public** — inlined into the client bundle; safe (it's a public endpoint). |
| `CONVEX_DEPLOY_KEY` | CI secret | **Secret** — deploys Convex prod. Never `VITE_`-prefixed, never in the bundle. |
| Server secrets (3rd-party keys for Convex actions) | Convex env (`npx convex env set`) | **Secret** — runs server-side in Convex. |
| `CLOUDFLARE_API_TOKEN` | CI secret, scoped | **Secret** — ships assets. Scope per `cf-iac-and-deployment`. |

Rule: **only `VITE_CONVEX_URL` is public.** Anything `VITE_*` is baked into the
client bundle — everything else is a CI or Convex secret.

### CI/CD (deploys from CI only)

```yaml
# .github/workflows/deploy.yml
name: Deploy
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - run: npm ci
      - run: npx oxlint && npx tsc --noEmit && npx vitest run   # quality gates
      - name: Deploy Convex (prod) + build the frontend against the prod URL
        run: npx convex deploy --cmd 'npm run build' --cmd-url-env-var-name VITE_CONVEX_URL
        env:
          CONVEX_DEPLOY_KEY: ${{ secrets.CONVEX_DEPLOY_KEY }}
      - name: Ship static assets to Cloudflare
        run: npx wrangler deploy
        env:
          CLOUDFLARE_API_TOKEN: ${{ secrets.CLOUDFLARE_API_TOKEN }}
```

**Order matters.** `convex deploy --cmd` pushes functions/schema to the prod Convex
deployment *first*, then runs `npm run build` with `VITE_CONVEX_URL` set to the prod
URL — so the bundle points at a backend that already exists. Only then does
`wrangler deploy` ship the built assets. Deploy the frontend before Convex and the
first load hits functions that aren't there yet.

## Zero to live URL (worked path)

```bash
# 1. Scaffold (Vite + VoidZero), opt into Rolldown, add Vitest + oxlint
npm create vite@latest my-app -- --template react-ts && cd my-app
#    add { "overrides": { "vite": "npm:rolldown-vite@latest" } } to package.json
npm i -D vitest oxlint wrangler && npm install

# 2. Add the reactive backend
npm i convex
npx convex dev          # login, create dev deployment, generate types
#    write convex/schema.ts + a first query/mutation; wire ConvexProvider

# 3. Configure Cloudflare hosting
#    write wrangler.toml (assets -> ./dist, SPA fallback, pinned compatibility_date)

# 4. First production deploy (Convex first, then the assets)
npx convex deploy --cmd 'npm run build' --cmd-url-env-var-name VITE_CONVEX_URL
npx wrangler deploy
#    -> live at https://my-app.<subdomain>.workers.dev
```

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Reaching for Cloudflare D1 / KV / Durable Objects for **app data** when Convex is the backend | Two sources of truth that drift; you lose Convex's reactivity and transactional guarantees. Convex owns data; CF storage is for edge-cache/asset concerns only. |
| Shipping the frontend **before** deploying Convex functions/schema | The client points at a deployment whose functions don't exist → runtime errors on first load. Deploy Convex first, or use `convex deploy --cmd` which orders it for you. |
| Putting `CONVEX_DEPLOY_KEY` or server secrets in a `VITE_`-prefixed var | Anything `VITE_*` is inlined into the public client bundle. Only the Convex URL belongs there; deploy keys and API secrets are CI/Convex secrets. |
| `wrangler deploy` or `convex deploy` from a laptop to prod | No test gate, no audit trail, no approval. Production deploys run from CI only. |
| Keeping ESLint **and** oxlint, or Jest **and** Vitest, side by side | Two linters/test runners drift and double CI time. Pick the VoidZero tool: oxlint + Vitest. |
| Plain Rollup/esbuild Vite on a greenfield app | The VoidZero golden path standardizes on Rolldown-Vite for build speed and one toolchain. Opt in via the `rolldown-vite` override. |
| No `convex/schema.ts` in production | Schemaless writes drift; bad data lands silently. Define a schema with validators before shipping. |
| Unpinned Workers `compatibility_date` | Runtime behavior shifts under you. Pin it; advance deliberately (see `cf-workers-and-compute`). |
| Committing `.env.local` / `.dev.vars` | Leaks the dev deployment URL/keys. `.gitignore` them before the first commit. |
| Building business logic into a Worker that belongs in a Convex function | Splits server logic across two runtimes. Keep app/server logic in Convex; use Workers only for edge concerns (headers, redirects, A/B, asset routing). |

## Security defaults

- **Only `VITE_CONVEX_URL` is public.** Every key and secret is a CI secret
  (`CONVEX_DEPLOY_KEY`, `CLOUDFLARE_API_TOKEN`) or a Convex env secret (action keys).
- Cloudflare API token **scoped to the deploy action** (`Account > Workers Scripts: Edit`
  for Workers, `Account > Cloudflare Pages: Edit` for Pages), per environment — never a
  global API key (see `cf-iac-and-deployment`).
- Convex: define a schema, **validate args in every public function**, and check the
  authenticated identity inside queries/mutations — never trust the client.
- Set security response headers (CSP, HSTS, `X-Content-Type-Options`, `X-Frame-Options`)
  on the static responses — a `_headers` file (Pages), a thin Worker, or zone Transform
  Rules (see `cf-networking-and-edge`, `cf-zero-trust-and-security`).
- `.env.local` and `.dev.vars` in `.gitignore` **before the first commit**.
- `npm ci` (not `npm install`) in CI; pin `wrangler` and `convex` in devDependencies.

## Observability defaults

- **Convex dashboard** is your backend lens: function logs, metrics, and a live data
  browser. `npx convex logs` tails function output; errors surface per-function.
- **Cloudflare**: `wrangler tail` immediately after a deploy to watch live traffic; turn
  on **Web Analytics** (free, privacy-first) for the static site; Workers Logs for any
  edge logic (see `cf-observability-and-cost`).
- **Stamp every deploy with the git SHA.** Convex deploy and `wrangler deploy` run in the
  same CI job — record the SHA so a prod issue maps back to a commit.
- Add `ctx.waitUntil` / Analytics Engine instrumentation only if you introduce a Worker
  for edge logic — a pure SPA + Convex app gets its telemetry from the two dashboards.

## Cost considerations

- **VoidZero** (Vite/Vitest/Rolldown/Oxc): free, open source.
- **Cloudflare**: static assets served free from the global CDN; Workers free tier
  (~100k requests/day); Pages free tier (~500 builds/month, unlimited static requests);
  custom domains free. Cost scales with request volume, not build minutes.
- **Convex**: a generous free tier covers a real small app (function calls, storage,
  bandwidth, one prod + one dev deployment); Pro plan when you outgrow it. Cost scales
  with function calls and storage.
- **Net**: a small golden-path app runs at roughly **$0/month** across all three on free
  tiers. Watch Convex function-call volume and Workers requests as the first paid signals.

## Verification checklist

- [ ] App scaffolded with Vite and the Rolldown override in place (`overrides.vite` → `npm:rolldown-vite`); `npm run build` produces `dist/`.
- [ ] Tests run on Vitest and linting on oxlint — no second test runner or linter in the project.
- [ ] `convex/schema.ts` defines the data model with validators; every public function validates its args and checks identity.
- [ ] `ConvexProvider` wired from `import.meta.env.VITE_CONVEX_URL`; a reactive `useQuery` renders live data against `npx convex dev`.
- [ ] Cloudflare hosting chosen deliberately (Workers static assets vs Pages); `wrangler.toml`/Pages settings pin `compatibility_date` and configure SPA fallback.
- [ ] Production deploy is ordered: Convex first via `convex deploy --cmd 'npm run build' --cmd-url-env-var-name VITE_CONVEX_URL`, then `wrangler deploy` / Pages publish.
- [ ] Only `VITE_CONVEX_URL` is public; `CONVEX_DEPLOY_KEY`, `CLOUDFLARE_API_TOKEN`, and server secrets are scoped CI/Convex secrets.
- [ ] Quality gates (`oxlint`, `tsc --noEmit`, `vitest run`) pass in CI before any deploy step; deploys run from CI only.
- [ ] `.env.local` / `.dev.vars` are git-ignored; no secret or deploy key is `VITE_`-prefixed or in the client bundle.
- [ ] Security headers set on static responses; Cloudflare API token scoped to the deploy action (see `cf-iac-and-deployment`).
- [ ] App reachable at its live URL; `wrangler tail` and the Convex dashboard show healthy traffic; the deploy is stamped with the git SHA.
- [ ] If the golden path didn't fit, the deviation is documented and the relevant `cloud-*` provider skill was used instead.
