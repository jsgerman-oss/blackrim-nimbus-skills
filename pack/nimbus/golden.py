"""The nimbus golden-path knowledge: the opinionated stack, the file templates a
scaffolded app gets, the deploy-readiness requirements, and the breadth of the 19
cloud providers curated in this marketplace.

This module is the single, pure source of truth — data plus pure render helpers,
no filesystem and no network. It is to nimbus what ``contract.py`` is to cockpit:
the knowledge the operation modules build on. :mod:`nimbus.scaffold` writes a
project from it; :mod:`nimbus.readiness` checks a project against it.

The stack mirrors the ``golden-path-hosting`` skill (nim-ulq) so the runnable
scaffold and the written process stay in lock-step: a React + TypeScript SPA built
by the VoidZero toolchain (Vite + Vitest + Rolldown + Oxc/oxlint), a Convex
reactive backend, and Cloudflare Workers static-asset hosting.

Pure stdlib (``json`` + ``re``).
"""

from __future__ import annotations

import json
import re
from typing import Any

SCHEMA = "nimbus.v0"

# The opinionated golden-path stack. Each layer names the tool the scaffold wires.
STACK: dict[str, str] = {
    "build": "vite",          # Vite dev server + build (VoidZero: + Vitest/Rolldown/Oxc)
    "toolchain": "voidzero",  # rolldown-vite + vitest + oxlint
    "hosting": "cloudflare",  # Cloudflare Workers static assets
    "backend": "convex",      # Convex reactive backend
}

# Order the stack layers render in (so `info` / `providers` print left-to-right).
STACK_ORDER: tuple[str, ...] = ("build", "toolchain", "hosting", "backend")

# Breadth: the 19 providers curated in this marketplace (the escape hatch). The
# golden path targets `cloudflare`; the rest are surfaced as curated skills
# (nim-6y5). Keep this list in sync with docs/DESIGN.md §2 and the cloud-* plugins.
PROVIDERS: tuple[str, ...] = (
    "alibaba", "aws", "azure", "cloudflare", "digitalocean", "fly", "gcp",
    "hetzner", "ibm", "linode", "netlify", "oci", "railway", "render",
    "scaleway", "supabase", "tencent", "vercel", "vultr",
)

GOLDEN_PROVIDER = "cloudflare"

# Pinned version ranges for the generated package.json — kept here so the scaffold
# is reproducible and there is one place to bump. Not load-bearing for the tests
# (no npm runs); nim-114 refreshes them at launch quality.
_REACT = "^19.0.0"
_CONVEX = "^1.17.0"
_VITE = "^6.0.0"
_VITEST = "^2.1.0"
_PLUGIN_REACT = "^4.3.0"
_TYPESCRIPT = "^5.6.0"
_OXLINT = "^0.15.0"
_WRANGLER = "^3.90.0"
_TYPES_REACT = "^19.0.0"
# wrangler compatibility_date stamped into generated apps — pin; advance
# deliberately (matches the golden-path-hosting skill).
COMPAT_DATE = "2025-09-01"

# Deploy-readiness requirements (what `nimbus readiness` asserts). Data-driven so
# the marker written into a scaffolded app can carry them and the checker can
# assess without re-deriving. REQUIRED_FILES must stay a subset of render_files().
REQUIRED_FILES: tuple[str, ...] = (
    "package.json", "tsconfig.json", "vite.config.ts", "index.html",
    "wrangler.toml", "convex/schema.ts",
)
# Deploy-time credentials, checked against the environment (never committed). Per
# the skill's env boundary: both are CI secrets (VITE_CONVEX_URL is produced by
# `convex deploy`, so it is not a pre-set requirement).
REQUIRED_ENV: tuple[str, ...] = ("CLOUDFLARE_API_TOKEN", "CONVEX_DEPLOY_KEY")
# Toolchain expected on PATH to build + deploy.
REQUIRED_TOOLS: tuple[str, ...] = ("node", "npm", "npx")

# App name: lowercase, must start alphanumeric, then alnum/`.`/`-`/`_`. This both
# yields a valid-ish npm/dir name and blocks path traversal (no `/`, no leading
# `.` so `..`/`../x` are rejected).
_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


def valid_name(name: str) -> bool:
    """True if ``name`` is a safe app/directory name (see :data:`_NAME_RE`)."""
    return bool(name) and len(name) <= 100 and bool(_NAME_RE.match(name))


def golden_path() -> str:
    """The stack rendered as ``vite + voidzero + cloudflare + convex``."""
    return " + ".join(STACK[k] for k in STACK_ORDER)


# --------------------------------------------------------------------------- #
# file templates                                                              #
# --------------------------------------------------------------------------- #
#
# Brace-heavy templates (TS/TSX/HTML) use the ``__NAME__`` sentinel rather than
# str.format so literal ``{}`` need no escaping. _render() substitutes it.

_VITE_CONFIG = """\
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// rolldown-vite (the VoidZero bundler) is wired via the `overrides` field in
// package.json, so this stays a stock vite config. The build output goes to
// dist/, which `wrangler deploy` ships as Cloudflare Workers static assets.
export default defineConfig({
  plugins: [react()],
  build: { outDir: 'dist' },
})
"""

# Flat tsconfig (no project references) — valid for both `tsc --noEmit` and vite,
# and simpler than the split app/node template.
_TSCONFIG = {
    "compilerOptions": {
        "target": "ES2022",
        "useDefineForClassFields": True,
        "lib": ["ES2022", "DOM", "DOM.Iterable"],
        "module": "ESNext",
        "skipLibCheck": True,
        "moduleResolution": "bundler",
        "allowImportingTsExtensions": True,
        "resolveJsonModule": True,
        "isolatedModules": True,
        "moduleDetection": "force",
        "noEmit": True,
        "jsx": "react-jsx",
        "strict": True,
        "noUnusedLocals": True,
        "noUnusedParameters": True,
        "noFallthroughCasesInSwitch": True,
    },
    "include": ["src", "convex"],
}

_INDEX_HTML = """\
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>__NAME__</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
"""

_VITE_ENV_DTS = """\
/// <reference types="vite/client" />
"""

_MAIN_TSX = """\
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { ConvexProvider, ConvexReactClient } from 'convex/react'
import App from './App.tsx'

// VITE_CONVEX_URL is public (inlined into the bundle) and written by
// `convex dev` / `convex deploy`. Everything else stays a CI/Convex secret.
const convex = new ConvexReactClient(import.meta.env.VITE_CONVEX_URL as string)

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ConvexProvider client={convex}>
      <App />
    </ConvexProvider>
  </StrictMode>,
)
"""

_APP_TSX = """\
import { useQuery } from 'convex/react'
import { api } from '../convex/_generated/api'

export default function App() {
  // Reactive query: re-renders live as the backend changes. Until `convex dev`
  // generates ./convex/_generated, this import is unresolved — that is expected.
  const tasks = useQuery(api.tasks.list) ?? []
  return (
    <main>
      <h1>__NAME__ — vite + voidzero + cloudflare + convex</h1>
      <ul>
        {tasks.map((t) => (
          <li key={t._id}>{t.text}</li>
        ))}
      </ul>
    </main>
  )
}
"""

_CONVEX_SCHEMA = """\
import { defineSchema, defineTable } from 'convex/server'
import { v } from 'convex/values'

// Define your schema with validators before shipping — a schemaless prod
// deployment drifts and lands bad data silently.
export default defineSchema({
  tasks: defineTable({
    text: v.string(),
    done: v.boolean(),
  }),
})
"""

_CONVEX_TASKS = """\
import { query, mutation } from './_generated/server'
import { v } from 'convex/values'

// Validate every public function's args and check identity inside the function —
// never trust the client.
export const list = query({
  args: {},
  handler: async (ctx) => await ctx.db.query('tasks').collect(),
})

export const add = mutation({
  args: { text: v.string() },
  handler: async (ctx, { text }) => {
    await ctx.db.insert('tasks', { text, done: false })
  },
})
"""

_WRANGLER_TOML = """\
name = "__NAME__"
compatibility_date = "__COMPAT_DATE__"

# Cloudflare Workers static assets (the golden-path default — a single
# `wrangler deploy`). For per-PR preview deploys instead, use Cloudflare Pages
# (`wrangler pages deploy dist`); see the golden-path-hosting skill.
[assets]
directory = "./dist"
not_found_handling = "single-page-application"
"""

_ENV_EXAMPLE = """\
# Copy to .env.local and fill in. Never commit real secrets (.env.local is gitignored).
# Only VITE_-prefixed vars are public (inlined into the client bundle).

# Convex backend URL — written by `npx convex dev` / `convex deploy`. PUBLIC.
VITE_CONVEX_URL=

# Deploy-time secrets (CI only) — NOT VITE_-prefixed, never in the bundle:
# Convex prod deploy key (from `npx convex dashboard`)
CONVEX_DEPLOY_KEY=
# Cloudflare API token that ships the static assets (scope it narrowly)
CLOUDFLARE_API_TOKEN=
CLOUDFLARE_ACCOUNT_ID=
"""

_GITIGNORE = """\
node_modules/
dist/
.env.local
.convex/
convex/_generated/
*.tsbuildinfo
"""

_README = """\
# __NAME__

A web app on the **nimbus golden path**: vite + voidzero + cloudflare + convex —
a React + TypeScript SPA built by the VoidZero toolchain (Vite + Vitest + Rolldown
+ oxlint), a Convex reactive backend, and Cloudflare Workers static-asset hosting.
Scaffolded by `nimbus scaffold`; see the `golden-path-hosting` skill for the full
process.

## Develop

```bash
npm install
npx convex dev      # one-time: login, create a dev deployment, write VITE_CONVEX_URL
npm run dev         # vite dev server (rolldown-vite via the package.json override)
```

## Quality gates

```bash
npm run lint        # oxlint
npm run typecheck   # tsc --noEmit (vite does not typecheck during build)
npm run test        # vitest
```

## Deploy

Secrets live in CI, never locally. Convex first, then the frontend (the build
needs the prod `VITE_CONVEX_URL`):

```bash
npm run convex:deploy   # push schema + functions to Convex prod
npm run deploy          # vite build && wrangler deploy (Workers static assets)
```

Check deploy readiness first:

```bash
nimbus readiness .
```
"""


def _render(template: str, name: str) -> str:
    """Substitute the template sentinels for a concrete app."""
    return template.replace("__NAME__", name).replace("__COMPAT_DATE__", COMPAT_DATE)


def _package_json(name: str) -> str:
    pkg = {
        "name": name,
        "private": True,
        "version": "0.0.0",
        "type": "module",
        "scripts": {
            "dev": "vite",
            "build": "vite build",
            "preview": "vite preview",
            "lint": "oxlint",
            "typecheck": "tsc --noEmit",
            "test": "vitest run",
            "convex:dev": "convex dev",
            "convex:deploy": "convex deploy",
            "deploy": "vite build && wrangler deploy",
        },
        "dependencies": {
            "convex": _CONVEX,
            "react": _REACT,
            "react-dom": _REACT,
        },
        "devDependencies": {
            "@types/react": _TYPES_REACT,
            "@types/react-dom": _TYPES_REACT,
            "@vitejs/plugin-react": _PLUGIN_REACT,
            "oxlint": _OXLINT,
            "typescript": _TYPESCRIPT,
            "vite": _VITE,
            "vitest": _VITEST,
            "wrangler": _WRANGLER,
        },
        # voidzero: route `vite` to the rolldown-powered drop-in. This is the
        # documented rolldown-vite opt-in (an npm alias override).
        "overrides": {"vite": "npm:rolldown-vite@latest"},
    }
    return json.dumps(pkg, indent=2) + "\n"


def render_files(name: str) -> dict[str, str]:
    """Return ``{relative_path: contents}`` for a golden-path app named ``name``.

    These are the app's own source files. The ``.nimbus.json`` marker is built
    separately by :func:`marker_payload` (it is generated nimbus metadata, not app
    source) and written by :mod:`nimbus.scaffold`.
    """
    return {
        "package.json": _package_json(name),
        "tsconfig.json": json.dumps(_TSCONFIG, indent=2) + "\n",
        "vite.config.ts": _VITE_CONFIG,
        "index.html": _render(_INDEX_HTML, name),
        "src/main.tsx": _render(_MAIN_TSX, name),
        "src/App.tsx": _render(_APP_TSX, name),
        "src/vite-env.d.ts": _VITE_ENV_DTS,
        "convex/schema.ts": _CONVEX_SCHEMA,
        "convex/tasks.ts": _CONVEX_TASKS,
        "wrangler.toml": _render(_WRANGLER_TOML, name),
        ".env.example": _ENV_EXAMPLE,
        ".gitignore": _GITIGNORE,
        "README.md": _render(_README, name),
    }


def marker_payload(name: str) -> dict[str, Any]:
    """The ``.nimbus.json`` marker a scaffolded app carries.

    Records that nimbus generated the app, the stack, and the deploy-readiness
    requirements — so :mod:`nimbus.readiness` can check the app data-driven from
    the marker rather than re-deriving from this module.
    """
    return {
        "schema": SCHEMA,
        "kind": "nimbus-golden-path-app",
        "name": name,
        "stack": dict(STACK),
        "provider": GOLDEN_PROVIDER,
        "requirements": {
            "files": list(REQUIRED_FILES),
            "env": list(REQUIRED_ENV),
            "tools": list(REQUIRED_TOOLS),
        },
    }
