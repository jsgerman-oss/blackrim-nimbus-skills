---
name: supabase-storage-and-realtime
description: Design or implement Supabase Storage (buckets, RLS for objects, image transformations, signed URLs, resumable uploads via TUS) and Realtime (Postgres changes via WAL, Broadcast, Presence, channel auth, scaling). Use when storing files, serving user-generated content, streaming database changes, or building collaborative features.
---

# Supabase Storage and Realtime

## When to use

- Creating or auditing Storage buckets (public vs private, access patterns).
- Writing RLS policies for the `storage.objects` table.
- Implementing image transformations or CDN delivery.
- Building file upload flows (standard or resumable for large files).
- Subscribing to Postgres row changes in real time.
- Building chat, collaborative editing, or live-presence features.
- Scaling Realtime to handle many concurrent connections.

---

## Storage

### Bucket types

| Type | Access | Use for |
| --- | --- | --- |
| Public | Anyone can read the URL | Marketing assets, product images, public avatars |
| Private | Requires signed URL or RLS policy | User documents, private media, receipts |

Create buckets via the CLI or dashboard. In IaC, declare them in a seed migration:

```sql
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES
  ('avatars', 'avatars', true, 5242880, ARRAY['image/jpeg', 'image/png', 'image/webp']),
  ('documents', 'documents', false, 52428800, ARRAY['application/pdf', 'image/*']);
```

Set `file_size_limit` and `allowed_mime_types` in every production bucket. Unrestricted uploads enable abuse and storage cost spikes.

### RLS for Storage objects

Storage objects are rows in `storage.objects`. RLS applies there exactly as it does to application tables — and is just as mandatory.

```sql
-- Users can read their own files in a private bucket
CREATE POLICY "users_select_own_objects"
  ON storage.objects FOR SELECT TO authenticated
  USING (bucket_id = 'documents' AND (storage.foldername(name))[1] = auth.uid()::text);

-- Users can upload to their own folder
CREATE POLICY "users_insert_own_objects"
  ON storage.objects FOR INSERT TO authenticated
  WITH CHECK (bucket_id = 'documents' AND (storage.foldername(name))[1] = auth.uid()::text);

-- Users can delete their own files
CREATE POLICY "users_delete_own_objects"
  ON storage.objects FOR DELETE TO authenticated
  USING (bucket_id = 'documents' AND (storage.foldername(name))[1] = auth.uid()::text);
```

Structure object paths as `<user-id>/<filename>` or `<org-id>/<user-id>/<filename>` to enable simple folder-based policies without cross-user leakage.

### Public buckets — still need policies for writes

A public bucket allows unauthenticated reads of any object URL. You still need RLS policies on `storage.objects` for INSERT, UPDATE, DELETE to prevent arbitrary writes.

### Signed URLs (private buckets)

Generate signed URLs server-side with a bounded expiry:

```typescript
const { data } = await supabase.storage
  .from("documents")
  .createSignedUrl("user-id/report.pdf", 3600); // 1 hour
```

Rules for signed URLs:
- Generate them server-side only; never expose the service role in client code.
- Set the shortest expiry that satisfies the use case. One-time downloads: 60 s. Document preview: 15–30 min. Long-lived sharing: use a separate public share link stored in the database, not an infinitely long signed URL.
- Signed URLs bypass RLS — anyone with the URL can access the object. Do not embed user IDs or sensitive metadata in the URL structure.

### Image transformations

Supabase Storage can resize, crop, and format images on the fly via URL parameters (Pro+ feature):

```typescript
const { data } = supabase.storage.from("avatars").getPublicUrl("photo.jpg", {
  transform: { width: 200, height: 200, resize: "cover", format: "webp", quality: 80 },
});
```

Cache transformed images at the CDN layer. Transformation is billed per invocation — avoid transforming on every page load for static assets.

### Resumable uploads (TUS protocol)

For files > 6 MB, use resumable uploads. Supabase Storage implements the TUS protocol:

```typescript
import { Upload } from "tus-js-client";

const upload = new Upload(file, {
  endpoint: `${SUPABASE_URL}/storage/v1/upload/resumable`,
  retryDelays: [0, 3000, 5000, 10000],
  headers: { Authorization: `Bearer ${session.access_token}`, "x-upsert": "true" },
  metadata: { bucketName: "documents", objectName: `${userId}/large-file.zip` },
  chunkSize: 6 * 1024 * 1024,
  onError: (err) => console.error(err),
  onSuccess: () => console.log("Upload complete"),
});
upload.start();
```

Resumable uploads can be paused and resumed across browser sessions. Store the upload ID to support explicit pause/resume from your UI.

---

## Realtime

Supabase Realtime streams data to clients via WebSocket. Three channels:

| Channel type | What it streams | Use for |
| --- | --- | --- |
| Postgres Changes | INSERT / UPDATE / DELETE on a table or filtered subset (via WAL) | Activity feeds, dashboards, live record updates |
| Broadcast | Arbitrary JSON messages, ephemeral, no persistence | Chat, game state, collaborative cursors |
| Presence | Who is online right now, with arbitrary metadata | User lists, "typing..." indicators, cursor tracking |

### Postgres Changes

```typescript
const channel = supabase
  .channel("table-changes")
  .on("postgres_changes",
    { event: "*", schema: "public", table: "messages", filter: "room_id=eq.42" },
    (payload) => console.log(payload)
  )
  .subscribe();
```

**Important:** Postgres Changes replicates rows from WAL. A row change is sent to the subscriber only if:
1. The user is subscribed and connected.
2. The row satisfies the filter.
3. The row passes an RLS `SELECT` policy (Realtime checks RLS server-side).

Enable the `REALTIME` publication on tables you want to stream:

```sql
-- Add a table to the realtime publication
ALTER PUBLICATION supabase_realtime ADD TABLE public.messages;
```

Realtime does **not** backfill historical rows — it only streams changes that happen after the subscription is established. Load the initial state via a regular query, then listen for deltas.

### Broadcast

```typescript
const channel = supabase.channel("room:42");

// Send
channel.send({ type: "broadcast", event: "cursor", payload: { x: 100, y: 200 } });

// Receive
channel.on("broadcast", { event: "cursor" }, (payload) => updateCursor(payload));

channel.subscribe();
```

Broadcast messages are not persisted. They are delivered to currently-connected subscribers and dropped if no subscriber is listening. For message history, store in a Postgres table and use Postgres Changes or an initial fetch.

### Presence

```typescript
const channel = supabase.channel("room:42");

channel.on("presence", { event: "sync" }, () => {
  const state = channel.presenceState();
  console.log("Online users:", state);
});

channel.subscribe(async (status) => {
  if (status === "SUBSCRIBED") {
    await channel.track({ user_id: userId, cursor: { x: 0, y: 0 } });
  }
});
```

Presence syncs a key-value map of who is online. Each client tracks its own entry; Supabase merges them and broadcasts the full state on join/leave/update.

### Channel authentication

By default, any client can subscribe to any channel. Restrict access using Row Level Security on the `realtime.channels` and `realtime.messages` tables (Supabase Realtime v2+), or by validating the JWT in a custom Realtime authorization function.

For production, always verify that Postgres Changes subscriptions are gated by table-level RLS — Realtime will enforce the authenticated user's policies server-side before broadcasting a change.

### Scaling Realtime

Supabase hosts a managed Elixir-based Realtime cluster. Scaling limits per plan:

| Plan | Max concurrent connections |
| --- | --- |
| Free | 200 |
| Pro | 500 |
| Team | 3000 |
| Enterprise | Custom |

For applications approaching the connection limit:
- Use a single channel per logical room rather than per-user channels.
- Debounce Presence updates — track position at most every 100 ms, not every mousemove.
- Prefer Broadcast for ephemeral data; don't subscribe to Postgres Changes on high-write tables from every client.
- On self-hosted Supabase, scale Realtime horizontally by running multiple `supabase/realtime` instances behind a load balancer.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Public bucket with no RLS on INSERT | Anyone on the internet can upload arbitrary files. |
| Private bucket with over-permissive RLS (`USING (true)`) | All users can read all private files. Scope to `auth.uid()` or org membership. |
| Long-lived signed URLs (hours or days) | URL leaks mean durable access. Keep expiry short; use database-stored share links for long-term sharing. |
| Subscribing to Postgres Changes on tables without RLS | Realtime will broadcast rows to any subscriber who matches the filter, ignoring access intent. |
| One Realtime channel per user for presence | Connection count scales with user count. Use one channel per room/resource. |
| Storing large blobs in Postgres (BYTEA) instead of Storage | Bloats the database, bypasses CDN, and hurts query performance. Store objects in Storage, reference by URL. |
| Image transformation on every request without CDN caching | Transformation is billed per call; same image transformed 1000× costs 1000× as much. |

## Security defaults

- Every bucket has `file_size_limit` and `allowed_mime_types` set.
- Private buckets have explicit RLS policies on `storage.objects` for SELECT, INSERT, UPDATE, DELETE.
- Public buckets have RLS policies restricting INSERT / UPDATE / DELETE to authenticated owners.
- Signed URLs generated server-side only; expiry ≤ 3600 s for general use, ≤ 60 s for one-time downloads.
- Realtime Postgres Changes subscriptions gated by table-level RLS — confirmed before launch.
- Broadcast and Presence channels authenticated via JWT claims where possible.

## Observability defaults

- Storage: monitor bucket size and egress in the Supabase Dashboard → Storage → Usage.
- Alert on unexpected egress spikes (CDN hotlinking, data exfil).
- Realtime: monitor concurrent connection count in Dashboard → Realtime → Metrics.
- Track channel subscription errors — sudden spikes indicate auth issues or Realtime restarts.

## Cost considerations

- Storage charges: GB-month stored + egress (download) bandwidth. Public buckets with heavy traffic need CDN in front.
- Image transformation billed per unique transformation call on Pro+.
- Realtime billing: based on peak concurrent connections and messages per month.
- Resumable upload costs: Supabase does not charge extra for TUS, but large-upload egress from the client counts against bandwidth if hosted on your CDN.
- Self-hosted: Storage egress from your cloud provider's network is billed by your provider, not Supabase.

## IaC hints

- Buckets: declare via seed SQL migration or `supabase/config.toml` bucket definitions.
- Storage RLS: SQL migrations in `supabase/migrations/` alongside table RLS.
- Realtime publication: `ALTER PUBLICATION supabase_realtime ADD TABLE ...` in a migration.
- `config.toml` controls Realtime JWT secret and max connections for self-hosted.

## Verification checklist

- [ ] Every bucket has `file_size_limit` and `allowed_mime_types` configured.
- [ ] Private buckets have SELECT, INSERT, UPDATE, DELETE RLS policies on `storage.objects`.
- [ ] Public buckets have INSERT / UPDATE / DELETE RLS policies to prevent arbitrary uploads.
- [ ] Signed URLs are generated server-side; expiry is bounded and matches the use case.
- [ ] Tables used with Postgres Changes are in the `supabase_realtime` publication.
- [ ] Realtime subscriptions respect table RLS — verified in a test environment.
- [ ] Concurrent connection count is below 80% of plan limit at peak; scaling plan chosen if approaching limit.
- [ ] Broadcast channels are not used for data that must persist — persistence goes to Postgres.
- [ ] Image transformation results are cached via CDN.
