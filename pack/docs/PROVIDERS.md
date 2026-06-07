# Providers — the breadth behind the golden path

The nimbus pack is opinionated: the **golden path** is one stack
(`vite + voidzero + cloudflare + convex`) that takes a new app from zero to a live
URL with the fewest decisions. See the
[`golden-path-hosting`](../skills/golden-path-hosting/SKILL.md) skill for the full
worked path.

This document is the **escape hatch**: the 19 cloud providers curated in this
marketplace, and *which one to reach for when the golden path doesn't fit*. It maps
each golden-path layer to the breadth behind it, so leaving the golden path is a
deliberate, one-step move rather than a fresh research project.

> **The live list is generated.** The authoritative, always-current roster is the
> [`nimbus providers`](#reaching-the-breadth) command, backed by
> [`nimbus/providers.json`](../nimbus/providers.json) — a snapshot regenerated from
> the `cloud-*` plugin manifests by `npm run regen:pack-providers` and drift-checked
> by the `pack-providers-in-sync` validator rule. The categories below are by *need*
> (stable); the exact membership is whatever the index says.

## Golden path → breadth

Each layer of the golden path has a default and a set of providers to fall back to
when a constraint pushes you off it.

| Golden-path layer | Default | Leave it when… | Reach for |
| --- | --- | --- | --- |
| **Build / test / lint** | VoidZero (Vite + Vitest + Rolldown + Oxc) | — | Toolchain, not a cloud — it stays the same on every provider below. |
| **Backend + data** | Convex (reactive, typed) | You need relational/SQL, an existing Postgres, or heavy analytics | **Managed data:** `cloud-supabase` (managed Postgres + auth). **Self-hosted DB:** a VPS provider + a hyperscaler managed database (RDS / Cloud SQL / Azure DB). |
| **Hosting / edge** | Cloudflare (Workers static assets or Pages) | You want dashboard Git previews elsewhere, long-running servers/containers, GPUs, or a specific cloud for compliance/residency | **Other edge/Jamstack:** `cloud-vercel`, `cloud-netlify`. **App platforms:** `cloud-fly`, `cloud-render`, `cloud-railway`. **Full control / compliance:** a hyperscaler. **Cheap VMs:** a VPS provider. |

The rule of thumb: **stay on the golden path unless a hard constraint forces a
move, then move only the layer that's constrained** — keep VoidZero for the build
and Cloudflare for the edge even if Convex gives way to Supabase, and keep Convex +
VoidZero even if hosting moves to Vercel.

## The 19 providers, by need

Grouped by what they're for. Each provider is a `cloud-<name>` plugin in this
marketplace; its skills (compute, IaC, storage/databases, networking, identity &
security, observability & cost) load once the plugin is installed.

| Category | Providers | Reach for it when… |
| --- | --- | --- |
| **Edge / frontend hosting** | `cloudflare` (golden path), `vercel`, `netlify` | Static sites, SPAs, Jamstack, edge functions, per-PR preview URLs. |
| **App platforms (PaaS)** | `fly`, `render`, `railway` | Long-running services, containers, background workers, scale-to-zero — more than static, less than a VM fleet. |
| **Managed backend / data** | `supabase` | A managed Postgres with auth and storage — the SQL alternative when Convex doesn't fit. |
| **Hyperscalers** | `aws`, `gcp`, `azure`, `oci`, `ibm`, `alibaba`, `tencent` | Full-stack breadth, compliance/data-residency, an existing account, or services with no PaaS equivalent. |
| **Developer clouds / VPS** | `digitalocean`, `linode`, `vultr`, `hetzner`, `scaleway` | Cheap, predictable VMs and managed databases when you want raw control without a hyperscaler's surface area. |

## Reaching the breadth

From inside a city that has the pack installed:

```bash
nimbus providers                 # the 19 clouds + skill counts (the breadth list)
nimbus providers --json          # the full generated index (providers.json)
nimbus providers vercel          # one provider's skills (accepts 'vercel' or 'cloud-vercel')
nimbus providers cloud-aws --json
```

Each provider's deep knowledge lives in its `cloud-*` plugin skills. The golden-path
skill leans on the Cloudflare set (`cf-iac-and-deployment`, `cf-workers-and-compute`,
`cf-networking-and-edge`, `cf-zero-trust-and-security`, `cf-observability-and-cost`);
the same six-skill shape (compute, IaC, storage/databases, networking, identity &
security, observability & cost) repeats for every provider, so moving off the golden
path lands you on a familiar map.

## Staying in sync (no drift)

`providers.json` is **derived**, never hand-edited:

1. The `cloud-*/.claude-plugin/plugin.json` manifests and `skills/*/SKILL.md`
   frontmatter are authoritative.
2. `npm run regen:pack-providers` (folded into `npm run regen`) rebuilds
   `pack/nimbus/providers.json` from them.
3. The `pack-providers-in-sync` rule fails `npm run check` if the committed index
   diverges from that regen output.

So adding, removing, or re-describing a provider is a single `npm run regen` away,
and CI refuses to let the pack's snapshot drift from the marketplace it curates.
