---
name: cf-workers-and-compute
description: Design or configure Cloudflare compute — Workers (modules, bindings), Workers AI, Durable Objects, Pages Functions, Workflows, Containers, Smart Placement. Use when choosing a runtime model, wiring bindings, sizing Durable Object state, or debugging CPU / wall-clock limits.
---

# Cloudflare Workers and Compute

## When to use

- Choosing between a Worker, Pages Function, Durable Object, or Container for a new workload.
- Designing a Worker that needs persistent state, coordination, or real-time connections.
- Debugging cold-start behaviour, CPU time exhaustion, or wall-clock timeout errors.
- Running AI inference at the edge via Workers AI.
- Designing a long-running or multi-step workflow with Cloudflare Workflows.
- Evaluating Smart Placement vs manual placement for latency-sensitive paths.

## Decision tree

1. **Stateless HTTP handler, sub-millisecond response, global distribution** → Workers (module syntax, standard isolate).
2. **Static site with dynamic edge logic, tied to a Pages project** → Pages Functions.
3. **Single-instance coordinating state across many clients (real-time, rate limiting, session fan-out)** → Durable Object.
4. **Multi-step durable execution: retries, sleeps, external calls that must complete even if the caller disconnects** → Cloudflare Workflows.
5. **AI inference close to users with GPU-backed models** → Workers AI (binding in the Worker, no separate deploy).
6. **Long-running process, arbitrary binaries, full OS environment, persistent disk** → Cloudflare Containers (where available for your plan).
7. **Anything that needs >30 s CPU or a long-lived TCP connection that isolates can't hold** → Containers or hybrid: Worker front-end + Container backend via Service Binding.

## Defaults

### Workers (module syntax)

- Always use **ES module syntax** (`export default { fetch(request, env, ctx) {} }`) — avoid the legacy Service Worker format for new code.
- `compatibility_date` in `wrangler.toml` / `wrangler.jsonc`: pin to a recent date and advance deliberately; breaking changes are gated here.
- CPU time limit: 10 ms (Free / Workers Bundled) to 30 s (Unbound / Workers Paid). Wall-clock limit is up to 30 s for HTTP requests. Design handlers to be fast; offload slow work to Queues or Workflows.
- Use `ctx.waitUntil(promise)` for fire-and-forget work (logging, analytics writes) after responding — do not block the response on it.
- Bindings (KV, R2, D1, Durable Objects, Queues, Service Bindings, AI) are declared in `wrangler.toml` and injected into `env`. Never hard-code resource names or access keys in code.
- Secrets via `wrangler secret put` — they appear in `env` alongside bindings, are encrypted at rest, and never appear in `wrangler.toml`.

### Durable Objects

- One Durable Object instance = one location. All writes from that instance are serialized — this is the design intent, not a limitation.
- Use **hibernation** (implement `webSocketMessage`, `webSocketClose` instead of keeping a loop alive) so idle DO instances don't consume CPU quota.
- Alarms (`state.storage.setAlarm`) for deferred work — more reliable than `setTimeout` in a non-hibernated context.
- Keep the DO's stored state small and well-structured. DO storage is a key-value store with up to 128 KiB per value; not a relational DB.
- Place DO instances with `locationHint` only when latency to a specific region matters and you've measured it; the default placement is usually correct.
- Stubs are obtained via a binding declared in `wrangler.toml`; always use `idFromName` for deterministic lookup rather than `newUniqueId` unless you explicitly want transient objects.

### Workers AI

- Declare the binding in `wrangler.toml`: `[ai]` block or `[[ai_bindings]]`.
- Model IDs are stable strings (e.g., `@cf/meta/llama-3-8b-instruct`); pin the model you've tested — Cloudflare updates model weights and may retire IDs.
- Streaming responses via `ai.run` with `stream: true` — use `ReadableStream` from the response to pipe to the client.
- Workers AI runs on Cloudflare's GPU fleet; latency varies by region and model size. For latency-critical inference, benchmark before committing.
- Rate limits apply per account; cache responses in KV or R2 where the same prompt appears frequently.

### Pages Functions

- File-based routing: `functions/api/[param].ts` maps to `/api/:param`. Middleware at `functions/_middleware.ts`.
- Pages Functions run the same Workers runtime; `env` bindings declared in the Pages project settings (or via `wrangler.toml` with `pages_build_output_dir`).
- For complex logic, prefer a Worker accessed via Service Binding from a thin Pages Function — keeps routing simple and the Worker independently deployable.

### Smart Placement

- Enabled per-Worker in `wrangler.toml` with `[placement] mode = "smart"`.
- Cloudflare measures round-trip time from Workers to origin and moves execution closer to the origin when that reduces total latency.
- Verify with `cf.colo` in the request context — Smart Placement may place the Worker in a non-edge datacenter.
- Disable if your workload is cache-read-heavy (edge proximity to user matters more than origin proximity).

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Storing mutable shared state in global Worker scope | Workers can run across many isolates; globals are per-isolate, not shared. Use Durable Objects for shared state. |
| Using Durable Objects for simple caching | KV is cheaper, faster, and globally replicated. DOs are for coordination, not cache. |
| Hard-coding `CLOUDFLARE_API_TOKEN` or account IDs in Worker code | Credentials in source = credential leak. Use secrets and bindings. |
| Blocking `fetch()` response on slow upstream without a timeout | Wall-clock limit will fire and the user gets a 1101. Set `signal: AbortSignal.timeout(ms)` on fetch. |
| Deploying with `wrangler deploy --env production` without reviewing `wrangler.toml` environment stanzas | Accidental production deploy from a dev branch. Use separate `wrangler.toml` per env or CI gating. |
| `addEventListener("fetch", ...)` (Service Worker syntax) for new code | Legacy format; no access to `env` bindings or `ctx`. Use module syntax. |
| Keeping a Durable Object alive in a tight loop for real-time connections | Hibernate instead. Active loop costs CPU quota and defeats hibernation savings. |

## Security defaults

- Workers secrets via `wrangler secret put` — encrypted at rest, scoped to the environment. Never plaintext in `wrangler.toml`.
- Validate and sanitize every incoming `request.url` and header before passing to downstream services or Durable Objects — Workers receive raw untrusted input from the internet.
- Set `Content-Security-Policy`, `X-Frame-Options`, `Strict-Transport-Security`, and `X-Content-Type-Options` response headers; Workers Transform Rules can enforce these at the zone level if not set by the Worker itself.
- Limit Durable Object stubs to internal Service Bindings — never expose a Durable Object ID as a public-facing identifier.
- CORS: explicit `Access-Control-Allow-Origin` with an allowlist, not `*`, for any Worker that touches user credentials or sensitive data.

## Observability defaults

- Log structured JSON via `console.log` — picked up by Logpush and Workers Logs (dashboard tail).
- Emit custom metrics via Workers Analytics Engine: one `writeDataPoint` per request with dimensions (`route`, `status`, `env`) and blobs for event context.
- Use Trace Workers (available on Workers Paid) to capture full request/response traces without modifying application code.
- Tail logs in development: `wrangler tail` streams live logs from a deployed Worker.
- For Durable Objects: log alarm fires and storage operations at `debug` level; surface errors at `error` level with the DO instance ID.

## Cost considerations

- **Workers Bundled (included in $5/mo Workers Paid plan):** 10 million requests/mo. CPU time limit 10 ms/request. Low-cost for simple API handlers.
- **Workers Unbound:** billed per request + per GB-second of CPU. No hard CPU cap; designed for heavier compute. Cost rises with complexity.
- **Durable Objects:** billed per request to the DO + per GB-month of storage + per GB-second of active duration. Hibernate aggressively to minimize duration cost.
- **Workers AI:** billed per neuron (inference unit). Cache repeated inferences in KV to avoid redundant charges.
- **Containers:** billed by container-hours. Shut down idle containers; use auto-stop policies.
- Smart Placement is free; the cost saving comes from reduced origin egress if origin is off-Cloudflare.

## IaC hints

- `wrangler.toml` is the primary config for Workers and Durable Objects; use `wrangler.jsonc` for JSON5 syntax with comments.
- Terraform `cloudflare/cloudflare` ≥ 5.x: `cloudflare_worker_script` resource for Worker code deployment; `cloudflare_worker_domain` for custom domains. Durable Object namespace: `cloudflare_worker_cron_trigger` and namespace bindings via the script resource's `lifecycle` binding blocks.
- Pin `wrangler` version in `package.json` devDependencies — minor wrangler versions can change build behavior.
- For multi-environment deploys, use `wrangler.toml` `[env.production]` stanzas OR separate `wrangler.production.toml` files; the latter is easier to reason about in CI.

## Verification checklist

- [ ] Module syntax used (ES module `export default`), not legacy Service Worker format.
- [ ] `compatibility_date` is pinned to a specific date and documented in the repo.
- [ ] All secrets use `wrangler secret put`, not plaintext in config.
- [ ] CPU / wall-clock usage profiled in development; no handler is routinely near the limit.
- [ ] Durable Objects use hibernation for any WebSocket or long-lived connection use case.
- [ ] Slow or optional work is offloaded via `ctx.waitUntil` or Queues.
- [ ] Analytics Engine or Logpush wired for request-level telemetry.
- [ ] CORS, CSP, and security response headers explicitly set.
- [ ] Smart Placement enabled only after measuring origin-fetch latency vs user-to-edge latency.
