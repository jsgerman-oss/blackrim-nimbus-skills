---
name: supabase-edge-functions-and-vector
description: Build or audit Supabase Edge Functions (Deno runtime, secrets, regions, background tasks, WebSockets, scheduled functions via pg_cron) and Vector / pgvector (HNSW vs IVF indexes, embedding workflows, Supabase AI client, OpenAI / Anthropic / local model integration). Use when writing server-side logic at the edge, scheduling jobs, or implementing semantic search and retrieval-augmented generation.
---

# Supabase Edge Functions and Vector

## When to use

- Writing server-side business logic that must not run in the browser (webhook handlers, payment flows, server-only API calls).
- Accessing the `service_role` key or other secrets from within a Supabase project.
- Scheduling periodic jobs (nightly summaries, data cleanup, report generation).
- Implementing semantic search, nearest-neighbor retrieval, or RAG over application data.
- Integrating with OpenAI, Anthropic, or a local embedding model.
- Streaming LLM responses to a client.

---

## Edge Functions

Edge Functions run on Deno Deploy, distributed across Supabase's edge network. Each function is a single TypeScript (or JavaScript) file at `supabase/functions/<function-name>/index.ts`.

### Runtime and constraints

- **Runtime:** Deno 1.45+ (no Node.js built-ins; use npm specifiers `npm:` or `https://` imports).
- **Timeout:** 60 seconds for HTTP responses; background tasks can continue up to 60 additional seconds after the response is sent.
- **Memory:** 256 MB per invocation.
- **Regions:** Deploy to specific regions via `supabase/config.toml` or default to the project's primary region.

```typescript
// supabase/functions/hello/index.ts
import { createClient } from "npm:@supabase/supabase-js@2";

Deno.serve(async (req: Request) => {
  const authHeader = req.headers.get("Authorization");
  if (!authHeader) {
    return new Response("Unauthorized", { status: 401 });
  }

  // Initialize Supabase client with the user's JWT — inherits their RLS context
  const supabase = createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_ANON_KEY")!,
    { global: { headers: { Authorization: authHeader } } }
  );

  const { data, error } = await supabase.from("items").select("*");
  if (error) return new Response(error.message, { status: 500 });

  return new Response(JSON.stringify(data), {
    headers: { "Content-Type": "application/json" },
  });
});
```

### When to use service role vs user JWT

| Scenario | Use |
| --- | --- |
| Acting on behalf of the authenticated user | User's JWT (forward `Authorization` header) — RLS applies |
| Admin operations, background jobs, cross-user queries | `SUPABASE_SERVICE_ROLE_KEY` — RLS bypassed |
| Calling Supabase from a webhook with no user context | Service role |

The `SUPABASE_URL`, `SUPABASE_ANON_KEY`, and `SUPABASE_SERVICE_ROLE_KEY` environment variables are auto-injected by Supabase into every function. Never hard-code them.

### Secrets

Store additional secrets (API keys, signing secrets, etc.) via the CLI:

```bash
supabase secrets set OPENAI_API_KEY=sk-...
supabase secrets set STRIPE_WEBHOOK_SECRET=whsec_...
```

List secrets (shows names, not values): `supabase secrets list`

Access in the function: `Deno.env.get("OPENAI_API_KEY")`

Never commit secrets to source control or embed them in function source. The `.env` file (used for local development with `supabase functions serve --env-file .env`) must be in `.gitignore`.

### Background tasks

Return an HTTP response immediately and continue work asynchronously using `EdgeRuntime.waitUntil`:

```typescript
Deno.serve(async (req) => {
  const payload = await req.json();

  // Respond immediately; process in background
  EdgeRuntime.waitUntil(processWebhookAsync(payload));

  return new Response("OK", { status: 200 });
});
```

Background work has up to 60 extra seconds after the response is sent. For longer jobs, enqueue to a Postgres table and process via a scheduled function or pg_cron.

### WebSocket support

Edge Functions support bidirectional WebSocket connections:

```typescript
Deno.serve((req) => {
  const { socket, response } = Deno.upgradeWebSocket(req);

  socket.onopen = () => console.log("WebSocket connected");
  socket.onmessage = (e) => socket.send(`Echo: ${e.data}`);
  socket.onclose = () => console.log("WebSocket closed");

  return response;
});
```

For real-time features, prefer Supabase Realtime (managed, scales automatically) over rolling your own WebSocket server in Edge Functions.

### Deploying Edge Functions

```bash
# Deploy a single function
supabase functions deploy hello

# Deploy all functions
supabase functions deploy

# Serve locally (with hot reload)
supabase functions serve --env-file .env
```

In GitHub Actions:

```yaml
- run: supabase functions deploy --project-ref $SUPABASE_PROJECT_REF
  env:
    SUPABASE_ACCESS_TOKEN: ${{ secrets.SUPABASE_ACCESS_TOKEN }}
```

### Invoking Edge Functions

```typescript
// From a client
const { data, error } = await supabase.functions.invoke("hello", {
  body: { name: "World" },
});

// Directly via HTTPS (useful for webhooks)
// POST https://<project-ref>.supabase.co/functions/v1/hello
```

### Scheduled functions via pg_cron

pg_cron runs Postgres jobs on a schedule. Use it to invoke Edge Functions or execute SQL directly:

```sql
-- Enable pg_cron (if not already enabled)
CREATE EXTENSION IF NOT EXISTS pg_cron;

-- Schedule a nightly cleanup at 02:00 UTC
SELECT cron.schedule(
  'nightly-cleanup',
  '0 2 * * *',
  $$DELETE FROM public.sessions WHERE expires_at < now() - interval '7 days'$$
);

-- Invoke an Edge Function on a schedule via pg_net
SELECT cron.schedule(
  'weekly-report',
  '0 9 * * 1', -- Monday 09:00 UTC
  $$
    SELECT net.http_post(
      url := current_setting('app.supabase_url') || '/functions/v1/send-report',
      headers := jsonb_build_object('Authorization', 'Bearer ' || current_setting('app.service_role_key')),
      body := '{}'::jsonb
    )
  $$
);
```

Store the Supabase URL and service role key as Postgres settings (`ALTER DATABASE ... SET app.service_role_key = '...'`) rather than hard-coding them in cron jobs.

---

## Vector / pgvector

pgvector adds vector similarity search to Postgres. Supabase enables it by default on all hosted projects.

### Enable pgvector

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### Storing embeddings

```sql
CREATE TABLE public.documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  content text NOT NULL,
  embedding vector(1536),  -- dimension must match your embedding model
  created_at timestamptz NOT NULL DEFAULT now()
);

-- RLS on top of vector tables — same rules apply
ALTER TABLE public.documents ENABLE ROW LEVEL SECURITY;
CREATE POLICY "users_select_own_docs"
  ON public.documents FOR SELECT TO authenticated
  USING (user_id = auth.uid());
```

Common embedding dimensions:

| Model | Dimension |
| --- | --- |
| OpenAI `text-embedding-3-small` | 1536 (or 256–3072 with matryoshka) |
| OpenAI `text-embedding-3-large` | 3072 |
| `all-MiniLM-L6-v2` (local) | 384 |
| Anthropic `voyage-3` | 1024 |
| Nomic `nomic-embed-text` | 768 |

### Indexes — HNSW vs IVF

| Index | Build speed | Query speed | Memory | Use when |
| --- | --- | --- | --- | --- |
| HNSW | Slow (hours for millions of rows) | Fast (sub-ms at scale) | High | Production, recall matters, rows > 100k |
| IVFFlat | Fast | Moderate | Lower | Prototype, smaller datasets, or when build time is constrained |

```sql
-- HNSW index (recommended for production)
CREATE INDEX ON public.documents USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);

-- IVFFlat index (faster build, lower recall)
-- Build AFTER loading data; lists ≈ sqrt(row_count)
CREATE INDEX ON public.documents USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);
```

Set `ivfflat.probes` (IVF) or `hnsw.ef_search` (HNSW) at query time to trade recall for speed:

```sql
SET hnsw.ef_search = 40;  -- higher = more accurate, slower
```

### Embedding workflows

Generate embeddings at write time via an Edge Function triggered by a Postgres trigger or a background job:

```typescript
// Edge Function: generate-embedding
import { createClient } from "npm:@supabase/supabase-js@2";
import OpenAI from "npm:openai@4";

const supabase = createClient(
  Deno.env.get("SUPABASE_URL")!,
  Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!
);
const openai = new OpenAI({ apiKey: Deno.env.get("OPENAI_API_KEY") });

Deno.serve(async (req) => {
  const { record } = await req.json(); // from Postgres Webhook

  const { data: embedding } = await openai.embeddings.create({
    model: "text-embedding-3-small",
    input: record.content,
  });

  await supabase
    .from("documents")
    .update({ embedding: embedding[0].embedding })
    .eq("id", record.id);

  return new Response("OK");
});
```

Trigger the function via a Postgres Webhook (Dashboard → Database → Webhooks) on `INSERT` to `public.documents`.

### Similarity search

```typescript
// Search for documents similar to a query
async function searchDocuments(query: string, userId: string, limit = 10) {
  const { data: embedding } = await openai.embeddings.create({
    model: "text-embedding-3-small",
    input: query,
  });

  const { data } = await supabase.rpc("match_documents", {
    query_embedding: embedding[0].embedding,
    match_threshold: 0.7,
    match_count: limit,
    p_user_id: userId,
  });

  return data;
}
```

Expose via a Postgres function (security definer, RLS aware):

```sql
CREATE OR REPLACE FUNCTION match_documents(
  query_embedding vector(1536),
  match_threshold float,
  match_count int,
  p_user_id uuid
) RETURNS TABLE (id uuid, content text, similarity float)
LANGUAGE sql STABLE AS $$
  SELECT id, content, 1 - (embedding <=> query_embedding) AS similarity
  FROM public.documents
  WHERE user_id = p_user_id
    AND 1 - (embedding <=> query_embedding) > match_threshold
  ORDER BY embedding <=> query_embedding
  LIMIT match_count;
$$;
```

### Supabase AI client

The Supabase Edge Runtime provides a built-in AI client for generating embeddings without an external API key (backed by an on-device model):

```typescript
const session = new Supabase.ai.Session("gte-small");
const embedding = await session.run("Hello world", { mean_pool: true, normalize: true });
```

Use this for cost-effective local embedding generation in development or for self-hosted deployments where you don't want OpenAI dependency.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Hard-coding `SUPABASE_SERVICE_ROLE_KEY` in function source | Any leak of the source exposes full database access. Use `Deno.env.get()`. |
| Service role client when user JWT is available | Bypasses RLS unnecessarily; expands the blast radius of any function compromise. |
| Not setting a timeout or retry limit on embedding API calls | Hanging calls hold the function invocation until the 60 s timeout; cascading failures under load. |
| HNSW index built on an empty table | Index is useless until data is inserted; build after loading initial data. |
| Storing raw OpenAI API responses in Postgres | Vendor format changes break deserialization. Store only the embedding vector and source text. |
| Generating embeddings synchronously in the HTTP request path | Adds 200–500 ms latency to every write. Use background tasks or a queue. |
| Using `ivfflat` without choosing `lists` thoughtfully | `lists = 1` = linear scan, no benefit; too high = poor recall. Target `sqrt(row_count)`. |
| Scheduling pg_cron jobs without idempotency | Double-execution (clock skew, restart) runs the job twice. Design all scheduled jobs to be safe to run multiple times. |

## Security defaults

- Secrets accessed via `Deno.env.get()` only; never embedded in source.
- Service role used only when a user JWT is not available or when bypassing RLS is intentional and documented.
- Edge Functions behind the Supabase API gateway — JWT verified automatically for functions that require it; set `Authorization` header requirement explicitly.
- pgvector tables have RLS enabled and policies scoped to `auth.uid()` or org membership.
- Webhook-invoked functions verify the webhook signature before processing the payload.
- pg_cron job credentials stored as Postgres settings, not embedded in SQL strings visible to all roles.

## Observability defaults

- Edge Function logs in the Supabase Dashboard → Functions → Logs.
- Instrument embedding generation calls with latency logging; alert when p99 > 1 s.
- Monitor `pg_stat_statements` for slow vector similarity queries; tune `ef_search` or `probes` as data grows.
- Track OpenAI / Anthropic API error rates and token usage in application logs.

## Cost considerations

- Edge Function invocations: billed per invocation and by compute time (GB-seconds). Keep functions lean.
- Embedding API costs: OpenAI `text-embedding-3-small` at $0.02/million tokens is inexpensive; scale matters at millions of documents.
- pgvector index memory: HNSW requires significant RAM proportional to `m × vector_dim × row_count`. Right-size database compute.
- pg_cron: free but executes on the primary database; avoid compute-heavy jobs during peak traffic.
- Local Supabase AI embeddings are free on self-hosted; on hosted Supabase they consume compute from your database add-on.

## IaC hints

- `supabase/config.toml` → `[functions.<name>]` block: set `import_map`, `verify_jwt`, and region overrides.
- Secrets: `supabase secrets set` in CI using `SUPABASE_ACCESS_TOKEN`.
- pg_cron jobs: declare in a migration (`supabase/migrations/`) with `cron.schedule(...)`.
- pgvector indexes: declare in migrations after the initial data load; add a guard `IF NOT EXISTS`.
- GitHub Actions: use `supabase/setup-cli@v1` and `supabase functions deploy`.

## Verification checklist

- [ ] All secrets accessed via `Deno.env.get()`, not hard-coded.
- [ ] Service role client only used where bypassing RLS is intentional; user JWT forwarded otherwise.
- [ ] `verify_jwt` is `true` in `config.toml` for all user-facing functions (default); explicitly set to `false` only for unauthenticated webhooks with their own signature verification.
- [ ] pgvector tables have RLS enabled with explicit policies.
- [ ] HNSW or IVFFlat index created after data is loaded; dimensions match the embedding model.
- [ ] Embedding generation is decoupled from the synchronous write path (background task or queue).
- [ ] pg_cron jobs are idempotent and tested for double-execution safety.
- [ ] Edge Function logs monitored; error rate alarm configured.
- [ ] Webhook-triggered functions verify the incoming signature before any state change.
