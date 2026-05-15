---
name: vercel-functions-and-edge
description: Design or configure Vercel compute — Edge Functions (V8 isolates), Edge Middleware, Serverless Functions (Node.js / Python), Streaming responses, ISR and on-demand revalidation, Image Optimization, Cron Jobs, Edge Config, and function memory / duration limits per plan. Use when choosing where to run code, tuning cold start, implementing middleware, or wiring ISR revalidation.
---

# Vercel Functions and Edge

## When to use

- Choosing between Edge Functions, Edge Middleware, and Serverless Functions for a new route.
- Implementing request-time logic (auth, redirects, A/B, geolocation) that must not add origin round-trips.
- Tuning ISR revalidation strategy (time-based vs on-demand) for a Next.js app.
- Configuring Image Optimization domains or device sizes.
- Setting up a Cron Job for scheduled work.
- Reading Edge Config in low-latency feature flags or kill switches.

## Decision tree

1. **Request-time logic with no I/O (auth checks, header rewrites, geo redirects, A/B routing)** → Edge Middleware. Runs before routing, globally, V8 isolate.
2. **Lightweight dynamic response, latency-critical, no Node.js APIs needed** → Edge Function (`export const runtime = 'edge'`). V8 isolate, distributed globally.
3. **Full Node.js runtime, NPM packages, database connections, > 1 MB response, > 30 s duration** → Serverless Function (Node.js or Python). Runs in a specific region.
4. **Static page that needs periodic or event-driven refresh** → ISR (Incremental Static Regeneration). Revalidate by time (`revalidate` export) or on-demand (`revalidateTag` / `revalidatePath`).
5. **Image resizing / format conversion at the edge** → Image Optimization (`next/image` or `<Image>`). No custom code needed.
6. **Scheduled task (cleanup, sitemap rebuild, cache warm)** → Cron Job. Calls a Serverless or Edge Function on a cron schedule.
7. **Low-latency feature flags / kill switches read on every request** → Edge Config. Read in Middleware for ~1 ms latency, no database round-trip.

## Edge Functions

Edge Functions run in V8 isolates at Vercel's edge network, close to the user. They share the Web API surface (Request, Response, fetch, crypto, URL) but not the Node.js runtime.

**Constraints (as of 2026-05):**

| Limit | Value |
| --- | --- |
| Runtime | V8 isolate (Web APIs only, no Node.js built-ins) |
| Max execution time | 25 s (Hobby) / 25 s (Pro, configurable up to 900 s via duration limit) |
| Max memory | 128 MB |
| Max response size | Streaming: unlimited; buffered: 4 MB |
| Cold start | < 1 ms (warm) — isolates reuse fast |
| Regions | Global (all Vercel edge regions) |

**Portability note:** Edge Functions use the WinterCG subset of Web APIs. Code is portable to Cloudflare Workers and other V8-isolate runtimes in theory; in practice, Vercel-specific helpers (`@vercel/edge`) and Edge Config SDK create coupling.

```typescript
// app/api/hello/route.ts — Next.js 15 App Router edge route
export const runtime = 'edge';

export async function GET(request: Request): Promise<Response> {
  return new Response(JSON.stringify({ region: process.env.VERCEL_REGION }), {
    headers: { 'Content-Type': 'application/json' },
  });
}
```

## Edge Middleware

Middleware runs before a request is matched to a route. It can rewrite, redirect, set headers, or short-circuit with a response. It always runs at the edge, globally.

```typescript
// middleware.ts at the project root
import { NextRequest, NextResponse } from 'next/server';

export function middleware(request: NextRequest): NextResponse {
  const country = request.geo?.country ?? 'US';
  if (country === 'DE') {
    return NextResponse.rewrite(new URL('/de' + request.nextUrl.pathname, request.url));
  }
  return NextResponse.next();
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
};
```

**Matcher discipline:** keep the matcher tight. Middleware that runs on `/_next/static/*` assets wastes edge CPU on every page load. Exclude static asset paths explicitly.

**Lock-in note:** `NextRequest.geo`, `NextRequest.ip`, and `NextResponse.rewrite` with Vercel-specific behavior are platform-coupled. Abstracting middleware into a handler that receives `{country, ip}` makes it portable.

## Serverless Functions

Serverless Functions run Node.js (default) or Python in a single Vercel region. Choose the region closest to your primary database to minimize round-trip latency.

**Defaults and limits (as of 2026-05):**

| Limit | Hobby | Pro | Enterprise |
| --- | --- | --- | --- |
| Max duration | 60 s | 300 s | 900 s |
| Max memory | 1024 MB | 1024 MB (configurable to 3008 MB) | 3008 MB |
| Max response size | 4.5 MB | 4.5 MB | 4.5 MB |
| Concurrent executions | 6 | 1000 | Unlimited |
| Region | Single (configurable) | Single (configurable) | Multi-region |

```typescript
// app/api/users/route.ts — Node.js Serverless Function
export const maxDuration = 60; // seconds; must not exceed plan limit

export async function GET(): Promise<Response> {
  const users = await db.select().from(usersTable).limit(100);
  return Response.json(users);
}
```

**Region pinning:** set `export const preferredRegion = 'iad1'` (or the region closest to your DB). Without it, Vercel picks a region at invocation time, which can cause high latency to a DB pinned to one region.

## Streaming responses

Both Edge and Serverless Functions support streaming via the Web Streams API or Node.js `ReadableStream`. Next.js 15 streams React Server Components by default.

```typescript
// Streaming a long response
export async function GET(): Promise<Response> {
  const stream = new ReadableStream({
    async start(controller) {
      for (const chunk of await getLargeDataset()) {
        controller.enqueue(new TextEncoder().encode(JSON.stringify(chunk) + '\n'));
      }
      controller.close();
    },
  });
  return new Response(stream, { headers: { 'Content-Type': 'application/x-ndjson' } });
}
```

## ISR — Incremental Static Regeneration

ISR serves a cached static page and regenerates it in the background. Two strategies:

**Time-based revalidation:**

```typescript
// app/posts/[id]/page.tsx
export const revalidate = 60; // seconds; 0 = no cache; false = permanent cache

export default async function Page({ params }: { params: { id: string } }) {
  const post = await fetchPost(params.id);
  return <article>{post.content}</article>;
}
```

**On-demand revalidation (recommended for CMS-driven sites):**

```typescript
// app/api/revalidate/route.ts
import { revalidateTag } from 'next/cache';
import { NextRequest } from 'next/server';

export async function POST(request: NextRequest): Promise<Response> {
  const secret = request.headers.get('x-revalidate-secret');
  if (secret !== process.env.REVALIDATE_SECRET) return new Response('Unauthorized', { status: 401 });
  const { tag } = await request.json();
  revalidateTag(tag);
  return Response.json({ revalidated: true });
}
```

**Lock-in note:** ISR (`revalidate`, `revalidateTag`, `revalidatePath`) is a Next.js + Vercel feature. Self-hosting Next.js with ISR requires a custom cache handler. Other frameworks have analogous patterns (SvelteKit `config.isr`), but the API is not portable.

## Image Optimization

`next/image` (or the equivalent for other frameworks) proxies images through Vercel's Image Optimization service: resizes to the requested `sizes`, converts to WebP / AVIF, caches at the CDN edge.

```typescript
import Image from 'next/image';

// next.config.js — allow external domains
const nextConfig = {
  images: {
    remotePatterns: [{ hostname: 'cdn.example.com' }],
    formats: ['image/avif', 'image/webp'],
    deviceSizes: [640, 750, 828, 1080, 1200, 1920],
  },
};
```

Image optimization invocations are billed separately on Pro/Enterprise plans. For high-traffic image-heavy sites, evaluate whether serving pre-optimized images from Vercel Blob or an external CDN is cheaper.

## Cron Jobs

Cron Jobs call an HTTP endpoint on a schedule defined in `vercel.json`. The endpoint must respond within the function's `maxDuration`.

```json
{
  "crons": [
    {
      "path": "/api/cron/cleanup",
      "schedule": "0 3 * * *"
    }
  ]
}
```

- Cron Jobs use UTC. The call arrives as a standard HTTP request with a `Authorization: Bearer <CRON_SECRET>` header — verify it in the handler.
- Hobby plan: 2 crons, 1-day minimum interval. Pro plan: 40 crons, 1-minute minimum interval.
- Cron execution is best-effort — do not use for work that cannot tolerate a missed tick.

## Edge Config

Edge Config is a key-value store with < 1 ms reads from Vercel's edge network. Use it for feature flags, kill switches, allowlists, and other low-latency read-only config.

```typescript
import { get } from '@vercel/edge-config';

// In Middleware (Edge runtime)
const featureEnabled = await get<boolean>('new-checkout-flow');
```

- Writes to Edge Config happen via the Vercel API, not from your application — it is a read-heavy, write-rare store. Do not use it as a general-purpose database.
- Edge Config items have a 512-byte value limit per item; total store limited by plan.
- Edge Config reads are free; writes count against API rate limits.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Node.js APIs in an Edge Function | Runtime error at deploy. V8 isolates have no `fs`, `net`, `child_process`, etc. |
| Middleware without a tight matcher | Runs on every static asset request, burning edge CPU and adding latency. |
| Serverless Function in `us-east-1` with a database in `eu-west-1` | 80–120 ms added to every DB round-trip. Pin function region to DB region. |
| ISR `revalidate = 0` on a slow data source | Defeats static generation; every request hits your origin. Use dynamic rendering explicitly instead. |
| Storing large objects in Edge Config | Hard 512-byte per-item limit; use Vercel KV or Blob for larger payloads. |
| Cron Job without secret verification | Any internet caller can trigger your cron handler. Always verify `CRON_SECRET`. |
| Image Optimization on every user-uploaded image | Invocation costs add up. Pre-process uploads at ingest; serve pre-optimized from Blob. |

## Security defaults

- Cron Job handlers verify `Authorization: Bearer ${process.env.CRON_SECRET}` — never skip this check.
- On-demand revalidation endpoints check a `REVALIDATE_SECRET` — rotate quarterly.
- Edge Middleware validates JWTs or session cookies at the edge before forwarding requests to origins — never trust auth from inside a Serverless Function alone if Middleware can intercept.
- `VERCEL_OIDC_TOKEN` is available in Serverless Functions for workload identity to external services (AWS IRSA-style) — prefer over long-lived secrets.

## Observability defaults

- Function logs visible in the Vercel Dashboard under Logs tab, per deployment.
- `VERCEL_REGION` env var is available at runtime — log it so regional latency patterns are visible.
- Duration, invocation count, and error rate for Serverless Functions visible in the Functions tab.
- For production alerting, ship logs to a Logs Drain (see `vercel-observability-and-cost`) — the dashboard is not suitable for programmatic alerting.

## Cost considerations

- Edge Function invocations: charged per million on Pro/Enterprise. Middleware running on every request at high traffic volumes can meaningfully consume this.
- Serverless Function invocations: charged per million GB-seconds. Memory × duration = cost. Right-size `maxDuration` — do not set 300 s if your P99 is 2 s.
- ISR: cached pages are free CDN hits. Cache misses trigger a Serverless Function invocation. High miss rate = high invocation cost. Monitor ISR cache hit rate in Function logs.
- Image Optimization: charged per source image transformation. Not per CDN hit — the transformed image is cached at the edge.
- Cron Jobs: count against function invocation limits.

## Verification checklist

- [ ] Runtime choice (Edge vs Serverless) justified against the decision tree.
- [ ] Edge Middleware matcher excludes static asset paths.
- [ ] Serverless Function `preferredRegion` pinned to the same region as primary database.
- [ ] ISR revalidation strategy chosen (time-based or on-demand) and documented.
- [ ] Cron Job handlers verify `CRON_SECRET`; on-demand revalidation handlers verify their secret.
- [ ] Image Optimization `remotePatterns` lists only trusted hostnames — wildcard patterns are a SSRF vector.
- [ ] Function `maxDuration` set to a realistic value — not the plan maximum by default.
- [ ] Edge Config used only for small, read-heavy, write-rare config — not as a general store.
