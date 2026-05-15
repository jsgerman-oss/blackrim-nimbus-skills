---
name: cf-storage-and-databases
description: Design or audit Cloudflare storage and databases — R2, D1, Workers KV, Queues, Hyperdrive, Vectorize. Use when picking an edge-native data store, modeling access patterns, securing data, or integrating Cloudflare storage with existing origin databases.
---

# Cloudflare Storage and Databases

## When to use

- Choosing between R2, D1, KV, Queues, Hyperdrive, and Vectorize for a new workload.
- Migrating from S3 or an origin database to edge-native storage.
- Designing a data model for D1 (SQLite at the edge) with read replicas.
- Understanding the consistency tradeoffs of Workers KV.
- Connecting an existing Postgres / MySQL origin database through Hyperdrive.
- Building a vector search feature with Vectorize.

## Decision tree

| Need | Service |
| --- | --- |
| Large binary or blob storage, low egress cost, S3-compatible | R2 |
| Relational queries (SQL) at the edge, small-to-medium datasets | D1 |
| Fast global key-value reads, eventual consistency acceptable | Workers KV |
| Durable message delivery, decoupling producer/consumer | Queues |
| Edge-speed connections to a remote Postgres / MySQL | Hyperdrive |
| Approximate nearest-neighbor vector search | Vectorize |
| Ephemeral coordination state, single-region consistency | Durable Object storage (not a standalone service — part of a DO) |

## R2

R2 is Cloudflare's S3-compatible object store. The defining feature: **zero egress fees** for reads served through a Worker or a public R2 bucket URL.

### Defaults

- Access from Workers via the `R2Bucket` binding in `env` — never via S3-compatible API from inside a Worker (that would route over the public internet).
- Public bucket URLs: disabled by default. Enable only for truly public assets (images, downloads). For everything else, serve via a Worker that performs authorization before streaming the object.
- Signed URLs: use `bucket.createSignedUrl` in the Worker to grant time-limited access to private objects without exposing the bucket publicly.
- Encryption: R2 encrypts all objects at rest with AES-256. Customer-managed keys (BYOK) available for enterprise accounts.
- Metadata: store structured metadata in R2 object's custom metadata (`httpMetadata`, `customMetadata`) for lightweight attributes; avoid storing large metadata blobs.
- S3-compatible API: available for migration tooling and non-Worker clients. Use scoped R2 API tokens (not global API key) for any non-Worker access.
- Lifecycle rules: configure object expiry and multipart cleanup via dashboard or Terraform to avoid unbounded storage growth.

### CDN vs R2

R2 is storage; Cloudflare's CDN (cache) sits in front of it when accessed via a Worker or custom domain. A Worker serving R2 objects can set `Cache-Control` headers and call `caches.default.put` to cache the response at the edge — this reduces R2 API operation counts on repeated reads.

## D1

D1 runs SQLite at the edge. Each D1 database has one primary and can have up to 8 read replicas distributed globally (currently in beta; check current availability per plan).

### Defaults

- Access via the `D1Database` binding in `env`. Use `env.DB.prepare(sql).bind(...args).all()` — always parameterize queries, never interpolate user input into SQL strings.
- Read replicas: opt-in per database. Reads are routed to the nearest replica; writes always go to the primary. Design schemas to separate read-heavy from write-heavy operations.
- Migrations: manage schema evolution with numbered SQL migration files (`migrations/0001_init.sql`); apply with `wrangler d1 migrations apply`.
- Transactions: use `env.DB.batch([...statements])` for atomic multi-statement operations.
- Data size: D1 is suitable for gigabytes of structured data, not petabytes. If your dataset grows into the hundreds of GB range, evaluate whether an origin database via Hyperdrive is more appropriate.
- Backups: D1 supports time-travel queries (point-in-time restore to the previous 30 days). Export snapshots regularly for disaster recovery outside Cloudflare's control plane.

## Workers KV

KV is a globally distributed, eventually consistent key-value store. Reads are fast from any Cloudflare PoP after the first write propagates (typically seconds, up to 60 s for consistency).

### Defaults

- Use for: configuration, feature flags, user sessions, rate-limit counters (with `expirationTtl`), API response caches.
- Do not use for: data that requires strong consistency (two clients writing the same key concurrently may see divergent reads). Durable Objects are the right answer for that.
- TTL: always set `expirationTtl` on ephemeral data (sessions, tokens) — orphaned keys accumulate and are billed by storage.
- Value size: up to 25 MiB per value. Keys up to 512 bytes. For large structured data, use R2.
- Bulk writes: `kv.put` in a loop is inefficient. Use `wrangler kv bulk put` for import operations.
- Consistency SLA: eventual. After a write, propagation to all PoPs can take up to 60 seconds. Do not rely on KV for synchronized rate limiting across all PoPs — use Durable Objects for that.

## Queues

Queues provide durable, at-least-once message delivery between Workers.

### Defaults

- Producer (sender): `env.QUEUE.send(message)` or `env.QUEUE.sendBatch(messages)`. Batching reduces per-message overhead.
- Consumer: a Worker with a `queue` handler (`export default { async queue(batch, env) {} }`). The consumer can retry or explicitly `batch.ackAll()` / `batch.retryAll()`.
- Delivery guarantee: at-least-once. Design consumers to be idempotent — check a deduplication key in D1 or KV before processing.
- Dead-letter queue: configure a DLQ in `wrangler.toml` for messages that fail after max retries. Monitor the DLQ to detect systemic failures.
- Batch size: tune `max_batch_size` and `max_batch_timeout_ms` in `wrangler.toml` for the consumer. Larger batches improve throughput; smaller batches reduce latency.
- Do not use Queues for request/response — use Service Bindings for synchronous Worker-to-Worker calls.

## Hyperdrive

Hyperdrive pools and caches connections to a remote Postgres or MySQL database, making origin-DB access from Workers practical.

### Defaults

- Create via `wrangler hyperdrive create` or Terraform; wire as a binding in `wrangler.toml`.
- Use a Postgres client (`postgres` npm package) with the connection string from `env.HYPERDRIVE.connectionString`.
- Hyperdrive maintains a regional connection pool — queries are served from the nearest Cloudflare region that has a pooled connection to your origin. This reduces per-request connection setup latency dramatically.
- Caching: Hyperdrive caches read queries automatically (configurable TTL). Mark queries that must not be cached with `no-cache` pragma or configure `caching.disabled = true` in the binding if your workload requires strict consistency.
- Security: origin database must be reachable from Cloudflare's egress IP ranges. Configure firewall rules or a VPN tunnel accordingly. Do not expose the database directly to the internet.
- Use Hyperdrive for an existing origin DB during migration to edge-native D1, not as a permanent replacement for R2 or D1 for new workloads.

## Vectorize

Vectorize stores high-dimensional embeddings and performs approximate nearest-neighbor (ANN) search.

### Defaults

- Create an index with `wrangler vectorize create <name> --dimensions=<n> --metric=cosine|euclidean|dot-product`.
- Insert via `env.VECTORIZE_INDEX.insert(vectors)` in a Worker. Each vector has an `id`, `values`, and optional `metadata`.
- Query via `env.VECTORIZE_INDEX.query(vector, { topK: 10, filter: { key: value } })`.
- Metadata filtering reduces ANN results to a subset — useful for multi-tenant isolation or attribute-scoped search.
- Dimensions must match the embedding model output. Changing dimensions requires re-creating the index and re-inserting all vectors.
- Combine with Workers AI for fully edge-native RAG: embed user query with Workers AI, query Vectorize for top-k similar chunks, feed results to an LLM inference call.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Using KV for strongly consistent rate limiting | KV is eventually consistent — concurrent increments lose. Use Durable Objects for accurate per-user rate limits. |
| Public R2 bucket for authenticated content | Anyone with the URL can read the object. Worker + signed URL or Access in front. |
| Storing secrets in KV values | KV values are not encrypted at rest with customer-managed keys by default. Use `wrangler secret put`. |
| D1 queries with string interpolation (`"SELECT ... WHERE id = " + userId`) | SQL injection. Always use parameterized statements (`.bind()`). |
| Queue consumer without idempotency check | At-least-once delivery means duplicate processing. Guard with a dedup key. |
| Hyperdrive with no origin firewall rules | Origin DB reachable from the public internet is a security incident waiting to happen. |
| Growing a KV namespace without TTLs | Orphaned keys accumulate, storage costs grow, and stale data causes bugs. |

## Security defaults

- R2: disabled public access by default; Worker authorization gate before streaming private objects; scoped R2 API tokens for non-Worker access.
- D1: parameterized queries enforced; access via binding only — never expose the D1 REST API to untrusted callers.
- KV: no sensitive secrets stored in KV; access via binding; namespace-level access controls via API tokens.
- Queues: producer and consumer Workers use least-privilege API tokens; DLQ monitored and alerted.
- Hyperdrive: origin database in a private network; Cloudflare egress IPs allowlisted; credentials via `wrangler secret put`, not `wrangler.toml`.
- Vectorize: metadata does not contain PII; access is via Worker binding, not a public endpoint.

## Observability defaults

- R2: enable Logpush for R2 access logs to detect unexpected reads or writes; alert on error rate spikes.
- D1: emit query latency and row counts to Analytics Engine for slow-query detection.
- KV: track hit/miss ratio and expiration events via Analytics Engine custom dimensions.
- Queues: alarm on DLQ message count > 0 (indicates repeated consumer failures); monitor consumer lag.
- Hyperdrive: track connection pool utilization and query latency; alert on origin DB reachability failures.

## Cost considerations

- **R2:** $0.015/GB-month storage; $4.50/million Class A operations (writes, lists); $0.36/million Class B operations (reads); **zero egress fees** — the defining cost advantage over S3 for read-heavy public data.
- **D1:** first 5 GB and 25 million reads/day free on Workers Paid; beyond that, per-GB and per-row-read billing.
- **KV:** first 1 GB free; billed per read and write operation beyond the free tier. Reads are cheap; writes are 3× more expensive — cache aggressively at the Worker layer.
- **Queues:** billed per million message operations. Batching reduces cost.
- **Hyperdrive:** included in Workers Paid; no extra charge for connection pooling itself, but origin egress costs still apply from the origin provider.
- **Vectorize:** billed per stored vector dimension and per query. Right-size embedding dimensions; prune stale vectors.

## IaC hints

- Terraform `cloudflare/cloudflare` ≥ 5.x: `cloudflare_r2_bucket`, `cloudflare_d1_database`, `cloudflare_workers_kv_namespace`, `cloudflare_queue`. Worker binding declared in `cloudflare_worker_script` resource.
- R2 CORS configuration via `cloudflare_r2_bucket_cors_configuration` resource.
- D1 migrations are not yet fully managed by Terraform — run `wrangler d1 migrations apply` in CI after the database resource is created.
- Wrangler: declare all bindings in `wrangler.toml`; use `[env.production]` stanzas to separate per-environment resource names.

## Verification checklist

- [ ] Storage service chosen matches consistency and access-pattern requirements.
- [ ] R2 public access disabled unless explicitly required; Worker authorization gate in place.
- [ ] D1 queries use parameterized statements; no raw SQL string interpolation.
- [ ] KV values have TTLs set for any ephemeral data.
- [ ] Queue consumers are idempotent; DLQ is configured and monitored.
- [ ] Hyperdrive origin is in a private network; egress IP allowlist configured.
- [ ] Logpush or Analytics Engine wired for per-store observability.
- [ ] Storage lifecycle / TTL / expiry configured to prevent unbounded growth.
