# blackrim-nimbus site

The marketing and docs site for `blackrim-nimbus-skills`: the cloud-toolkits
marketplace and its GasCity hosting pack. Static, prerendered, multi-page.

Design system: `site/DESIGN.md` (the blackrim "Working Lab Notebook" system with
nimbus's vapor-cyan accent). Reference implementation in the same family:
`gascity-cockpit/site`.

## Stack

Built on the voidzero toolchain.

- **Vite** (multi-page build, vanilla, no framework runtime)
- **Vitest** (copy and data-integrity tests)
- **@fontsource-variable** Inter + JetBrains Mono (self-hosted, no CDN)
- Hand-written CSS reasoned in OKLCH, two full-fidelity themes

No Tailwind, no router: three real HTML pages with relative inter-page links,
so the build is base-agnostic and works under any path.

## Pages

| Route | File | What it is |
|-------|------|------------|
| `/` | `index.html` | Landing, with the golden-path deploy terminal |
| `/providers` | `providers/index.html` | The cloud matrix of all 19 clouds |
| `/pack` | `pack/index.html` | The GasCity hosting pack and the golden path |

## Develop

```bash
cd site
npm install
npm run dev      # vite dev server
npm run build    # static build to dist/
npm run preview  # serve the built dist/
npm test         # vitest: house style + data integrity
```

## Deploy

GitHub Pages, via `.github/workflows/deploy-site.yml`. Set the Pages source to
"GitHub Actions" in the repository settings; the workflow builds `site/` and
publishes `site/dist/`.

The site uses relative links between pages, so only hashed asset URLs depend on
the base path. The workflow sets `SITE_BASE` to `/<repo>/` for a project page by
default. For a custom domain (or an org root page), set a repository variable
`SITE_BASE` to `/`. Cloudflare Pages can build the same `dist/` later.
