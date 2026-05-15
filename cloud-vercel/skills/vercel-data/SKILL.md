---
name: vercel-data
description: Choose and configure Vercel-native data stores — Vercel KV (Upstash Redis), Vercel Postgres (Neon-backed), Vercel Blob (object storage), Edge Config (low-latency read-only), and marketplace integrations (Neon, Upstash, MongoDB Atlas, Supabase). Use when picking a data layer for a Vercel project, sizing storage, or evaluating portability tradeoffs.
---

# Vercel Data

## When to use

- Choosing a data store for a Vercel-hosted application.
- Adding a cache layer or session store without running Redis infrastructure.
- Storing user-uploaded files or build artifacts.
- Evaluating whether to use Vercel-native stores vs marketplace integrations.
- Understanding portability and lock-in tradeoffs before committing.

## Decision tree

| Need | Service |
| --- | --- |
| Key-value cache, sessions, rate limiting, pub/sub | Vercel KV (Upstash Redis) |
| Relational ACID, SQL queries, OLTP | Vercel Postgres (Neon) |
| Object / blob storage (images, files, artifacts) | Vercel Blob |
| Sub-millisecond feature flags / kill switches | Edge Config |
| Managed Postgres with branching, autoscale | Neon (marketplace) — same engine as Vercel Postgres |
| Redis with advanced features (streams, modules) | Upstash Redis (marketplace) — same engine as Vercel KV |
| MongoDB document store | MongoDB Atlas (marketplace) |
| Open-source Postgres alternative with row-level security | Supabase (marketplace) |

## Vercel KV (Upstash Redis)

Vercel KV is a serverless Redis-compatible key-value store powered by Upstash. It connects over HTTP, which means it works in both Edge and Serverless runtimes.

```typescript
import { kv } from '@vercel/kv';

// Set with expiry
await kv.set('session:abc123', JSON.stringify(sessionData), { ex: 3600 });

// Get
const session = await kv.get<SessionData>('session:abc123');

// Atomic increment for rate limiting
const requests = await kv.incr(`ratelimit:${userId}:${minuteBucket}`);
```

**Defaults:**

- Data persists across requests — not an in-memory cache (data survives restarts and cold starts).
- Connections are HTTP-based — no persistent TCP socket, no connection pooling needed.
- `KV_URL`, `KV_REST_API_URL`, `KV_REST_API_TOKEN`, `KV_REST_API_READ_ONLY_TOKEN` are injected automatically after linking.

**Portability note:** The `@vercel/kv` SDK wraps the Upstash REST API. Code using raw Upstash SDK (`@upstash/redis`) is portable to any runtime. Prefer the Upstash SDK for portability; use `@vercel/kv` only if you want automatic env var injection.

**When to use marketplace Upstash instead:** When you need Redis Streams, Pub/Sub, LUA scripting, or the Upstash workflow SDK — Vercel KV exposes a subset of Redis commands.

## Vercel Postgres (Neon)

Vercel Postgres is a serverless PostgreSQL database powered by Neon. It auto-scales to zero when idle and scales up on demand.

```typescript
import { sql } from '@vercel/postgres';

const { rows } = await sql`SELECT * FROM users WHERE id = ${userId}`;
```

**Connection pooling:** Vercel Postgres uses a connection pooler (PgBouncer-compatible) endpoint. Use the pooler URL (`POSTGRES_URL`) for application code; use the direct connection URL (`POSTGRES_URL_NON_POOLING`) only for migrations.

**Defaults:**

- `POSTGRES_URL`, `POSTGRES_PRISMA_URL`, `POSTGRES_URL_NON_POOLING`, `POSTGRES_USER`, `POSTGRES_HOST`, `POSTGRES_DATABASE`, `POSTGRES_PASSWORD` — all injected after linking.
- Compute regions: select the Postgres region closest to your Serverless Function region.
- Neon branching: each database instance supports branching — create a branch per PR for isolated testing. Access via the Neon dashboard or API.

```typescript
// With Drizzle ORM (common pattern for Next.js + Vercel Postgres)
import { drizzle } from 'drizzle-orm/vercel-postgres';
import { sql as vercelSql } from '@vercel/postgres';

const db = drizzle(vercelSql);
const users = await db.select().from(usersTable).where(eq(usersTable.active, true));
```

**Portability note:** `@vercel/postgres` resolves to a standard PostgreSQL connection. Replacing it with `pg` or `postgres.js` and reading connection strings from env vars is a one-file change. The database itself is standard Postgres — no vendor lock-in on the data model.

**When to use marketplace Neon instead:** When you need more control over Neon settings (autoscale limits, branch policies, IP allowlists) or when you have a Neon account with existing data to migrate.

## Vercel Blob

Vercel Blob is object storage for user-generated content, build artifacts, and static files. It is not a CDN replacement for public static assets (use Vercel's built-in CDN for those).

```typescript
import { put, del, list } from '@vercel/blob';

// Upload
const blob = await put('avatars/user-123.png', imageBuffer, {
  access: 'public',          // 'public' or 'private'
  contentType: 'image/png',
});
// blob.url is the permanent, CDN-backed URL

// List
const { blobs } = await list({ prefix: 'avatars/', limit: 50 });

// Delete
await del(blob.url);
```

**Client-side uploads (recommended for large files):**

```typescript
// In a Server Action or API route — issue a client upload token
import { handleUpload, type HandleUploadBody } from '@vercel/blob/client';

export async function POST(request: Request): Promise<Response> {
  const body = (await request.json()) as HandleUploadBody;
  const jsonResponse = await handleUpload({
    body,
    request,
    onBeforeGenerateToken: async (pathname) => ({
      allowedContentTypes: ['image/jpeg', 'image/png', 'image/webp'],
      maximumSizeInBytes: 5 * 1024 * 1024, // 5 MB
    }),
    onUploadCompleted: async ({ blob }) => {
      await saveUrlToDatabase(blob.url);
    },
  });
  return Response.json(jsonResponse);
}
```

**Defaults:**

- `BLOB_READ_WRITE_TOKEN` is injected automatically after linking.
- Public blobs are served from a global CDN with cache-control headers.
- Private blobs require a signed URL generated server-side.

**Portability note:** Blob URLs are Vercel-specific. Migrating away requires updating all stored URLs. If portability matters, store only the pathname/key in your database and generate the full URL at query time.

## Edge Config

Edge Config is a globally replicated key-value store optimized for reads with < 1 ms latency at the edge. It is not a general-purpose database — it is for config that changes rarely but must be read on every request with no perceptible latency.

```typescript
import { get, getAll } from '@vercel/edge-config';

// In Middleware
const isMaintenance = await get<boolean>('maintenance-mode');
if (isMaintenance) {
  return NextResponse.rewrite(new URL('/maintenance', request.url));
}
```

**Limits:** 512 bytes per value, plan-dependent total item count. Writes via the Vercel API only — not from application code.

See `vercel-functions-and-edge` for more detail.

## Marketplace integrations

Vercel Marketplace lets you connect external data providers and inject their connection strings as env vars.

| Provider | Best for | Notes |
| --- | --- | --- |
| **Neon** | Postgres with DB branching per PR, autoscale | Same engine as Vercel Postgres; more control over Neon settings |
| **Upstash Redis** | Redis with streams, pub/sub, workflow SDK | Superset of Vercel KV feature set |
| **MongoDB Atlas** | Document store, geospatial, time-series | Atlas serverless or shared tier for small workloads |
| **Supabase** | Postgres + real-time subscriptions + row-level security | Useful when you want Supabase Auth and Realtime alongside Postgres |

Marketplace integrations inject env vars in the same scope as Vercel-native stores; your code reads them the same way.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Using Vercel KV as a primary relational store | No joins, no transactions across keys. Use Postgres. |
| Postgres `POSTGRES_URL` (pooler) for migrations | Connection poolers break DDL migrations. Use `POSTGRES_URL_NON_POOLING` for `prisma migrate deploy`. |
| Storing Blob URLs without the path key separately | Impossible to reconstruct URLs if the CDN domain changes. Store the pathname; assemble the URL. |
| Writing to Edge Config from application code | Edge Config is read-only from the runtime. Writes are API-only; don't try to use it as a mutable store. |
| `access: 'public'` on Blob for sensitive files | Public blobs are accessible by anyone with the URL. Use `access: 'private'` + signed URLs. |
| Neon / Upstash marketplace + also Vercel KV / Postgres in the same project | Duplicate stores, conflicting env vars, double billing. Pick one per layer. |

## Security defaults

- `BLOB_READ_WRITE_TOKEN`, `POSTGRES_PASSWORD`, `KV_REST_API_TOKEN` — all Sensitive env vars. Never expose in client-side bundles or public API responses.
- Private Blob access: generate short-lived signed URLs server-side. Default expiry 1 hour.
- Postgres: use a least-privilege database user for application queries (no `SUPERUSER`, no `CREATEDB`). Reserve the admin user for migrations.
- KV: use `KV_REST_API_READ_ONLY_TOKEN` for any server path that only reads — limits blast radius if the token leaks.
- Restrict marketplace database IP allowlists to Vercel's CIDR ranges where the provider supports it.

## Observability defaults

- KV: request count and latency visible in the Vercel KV dashboard. No built-in alerting — pipe logs to a Logs Drain for programmatic alerting.
- Postgres: query count, connection count, and compute time visible in the Neon dashboard. Enable Neon's slow query logging for queries > 100 ms.
- Blob: bandwidth and storage consumption visible in the dashboard under Usage.
- Log connection errors explicitly in application code — silent connection failures are the most common source of latency regressions.

## Cost considerations

- **KV:** billed by commands and storage. Scan operations (`KEYS *`, `SMEMBERS` on large sets) are expensive — use them only in offline tooling, not on the request path.
- **Postgres:** billed by compute time (Neon active compute-hours) + storage. Auto-scale to zero means idle databases cost only storage. Monitor active compute-hours; a connection pool that keeps the DB awake 24/7 eliminates the zero-idle benefit.
- **Blob:** billed by storage + bandwidth. Large files (video, full-res images) egress adds up. Serve compressed/resized variants via Image Optimization or an external CDN for public assets.
- **Edge Config:** reads are free; writes count against API rate limits (not directly billed, but Vercel may throttle heavy writers).
- Vercel-native stores vs marketplace: Vercel-native stores are convenient but are often 20–40% more expensive than managing the same underlying service (Neon, Upstash) directly. The convenience premium is justified for small teams; evaluate at scale.

## IaC hints

- Terraform `vercel/vercel` provider: `vercel_project_environment_variable` manages env vars but does not create Vercel-native stores (KV, Postgres, Blob) — those are provisioned via the Vercel Dashboard or API.
- For Neon via marketplace: use the `koyeb/neon` or direct Neon Terraform provider to provision databases; inject connection strings as Vercel env vars via `vercel_project_environment_variable`.
- For Upstash via marketplace: `upstash/upstash` Terraform provider manages Redis instances; inject the REST URL and token as Vercel env vars.

## Verification checklist

- [ ] Data store choice justified against the decision tree.
- [ ] Postgres migrations use the non-pooling connection string; application queries use the pooler.
- [ ] All credential env vars marked Sensitive.
- [ ] Private Blob access uses signed URLs with appropriate expiry.
- [ ] KV read-only token used where writes are not needed.
- [ ] Database user is least-privilege — not the admin/superuser.
- [ ] Cost estimate reviewed: KV commands/month, Postgres compute-hours, Blob storage/bandwidth.
- [ ] No duplicate stores: one KV layer, one relational layer per project.
