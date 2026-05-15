---
name: netlify-functions-and-edge
description: Design, implement, or audit Netlify serverless compute — Serverless Functions (Node.js / Go), Edge Functions (Deno runtime), Background Functions (async long-running), Scheduled Functions (cron), Blobs reads from functions, and geographic routing at the edge. Use when adding an API endpoint, customizing request handling, running cron jobs, or deciding between Functions and Edge Functions.
---

# Netlify Functions and Edge

## When to use

- Adding a server-side API endpoint to a JAMstack site.
- Choosing between a Serverless Function, an Edge Function, or a Background Function.
- Implementing geographic routing or request personalization at the edge.
- Writing a cron job (scheduled task) without managing a server.
- Accessing Netlify Blobs from a function.
- Debugging a function timeout, cold start, or invocation error.
- Auditing function IAM-equivalent (env var scoping, secret access) posture.

## Decision tree — which function type?

1. **Synchronous response needed, < 10 seconds, global state is fine** → **Serverless Function** (Node.js or Go).
2. **Synchronous, latency matters (sub-50 ms), request context (geo/IP) needed, no npm heavy deps** → **Edge Function** (Deno).
3. **Work can be deferred, may take up to 15 minutes** → **Background Function** (Node.js, async fire-and-forget).
4. **Needs to run on a timer without an HTTP trigger** → **Scheduled Function** (Node.js, cron syntax).
5. **Pure CDN manipulation, no business logic, < 1 ms response** → **Edge Function with early return** (no origin hit).

Netlify is not the right platform for persistent WebSocket servers, long-lived daemon processes, or functions that need more than 15 minutes. For those, use Fly.io, Render, or a container platform.

## Serverless Functions (Node.js)

Located in the directory specified by `functions` in `netlify.toml` (default: `netlify/functions/`).

**10-second synchronous limit.** If your handler hasn't responded in 10 seconds, Netlify returns a gateway error to the caller. Use Background Functions for anything that might run longer.

Minimal handler:

```javascript
// netlify/functions/hello.js
export const handler = async (event, context) => {
  return {
    statusCode: 200,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: "hello" }),
  };
};
```

Handler is invoked at `/.netlify/functions/<filename>`. Redirect to a cleaner path via `_redirects`:

```
/api/hello  /.netlify/functions/hello  200
```

Request context available on `event`:

- `event.httpMethod` — GET, POST, etc.
- `event.headers` — all request headers
- `event.queryStringParameters` — parsed query params
- `event.body` — raw body string (parse JSON manually)
- `event.isBase64Encoded` — for binary payloads
- `context.clientContext` — Netlify Identity user object if the request carries a JWT

Node.js version is controlled by `AWS_LAMBDA_JS_RUNTIME` or the site-level Node.js version setting. Pin via `[build.environment] NODE_VERSION = "20"` — Functions inherit the build image's Node version.

### Go Functions

```go
// netlify/functions/hello/main.go
package main

import (
    "context"
    "github.com/aws/aws-lambda-go/events"
    "github.com/aws/aws-lambda-go/lambda"
)

func handler(ctx context.Context, request events.APIGatewayProxyRequest) (events.APIGatewayProxyResponse, error) {
    return events.APIGatewayProxyResponse{
        StatusCode: 200,
        Body:       `{"message":"hello"}`,
    }, nil
}

func main() {
    lambda.Start(handler)
}
```

Go functions are compiled; ensure `go.mod` is present and dependencies are vendored or fetched during build.

## Edge Functions (Deno runtime)

Edge Functions run in a Deno environment at Netlify's CDN PoPs — geographically close to the user with no cold start in the traditional sense.

Located in `netlify/edge-functions/` by default (configure via `netlify.toml`).

```toml
[[edge_functions]]
  function = "geolocation"
  path     = "/personalized"
```

Minimal edge function:

```typescript
// netlify/edge-functions/geolocation.ts
import type { Context } from "netlify:edge";

export default async (request: Request, context: Context) => {
  const country = context.geo?.country?.code ?? "US";
  const response = await context.next();
  response.headers.set("X-User-Country", country);
  return response;
};
```

**Context object.** `context.geo` — `{ city, country: { code, name }, subdivision, timezone, latitude, longitude }`. `context.ip` — client IP. `context.account` — Netlify account info. `context.site` — site info. `context.next()` — pass to the next handler or to the origin.

**Runtime constraints:**
- Deno runtime — use `https://` imports or `npm:` specifiers. No `require()`.
- No filesystem access. No native Node.js modules (`fs`, `crypto` built-in except via Web Crypto API).
- Response must be returned or `context.next()` called. Returning nothing passes through to origin.
- 50 MB uncompressed script size limit per function.

**Geographic routing example:**

```typescript
export default async (request: Request, context: Context) => {
  const country = context.geo?.country?.code;
  if (country === "DE") {
    return Response.redirect("https://de.example.com" + new URL(request.url).pathname);
  }
  return context.next();
};
```

**Access control example (A/B testing gate):**

```typescript
export default async (request: Request, context: Context) => {
  const url = new URL(request.url);
  const bucket = Math.random() < 0.5 ? "a" : "b";
  url.pathname = `/${bucket}${url.pathname}`;
  return context.rewrite(url.toString());
};
```

## Background Functions

Background Functions respond to the caller with `202 Accepted` immediately and then continue running for up to 15 minutes. Use for: webhook processing, image optimization, PDF generation, email sending, async data pipelines.

```javascript
// netlify/functions/process-upload-background.js
export const handler = async (event, context) => {
  // Heavy work here — caller already received 202
  const body = JSON.parse(event.body);
  await processHeavyJob(body);
  // No meaningful return — caller isn't listening
};
```

Name the file with the `-background` suffix to trigger Background Function behavior. The caller receives `{ id: "<uuid>" }` in the 202 body. There is no built-in way to poll the result — implement your own status tracking (Blobs, a database, a webhook back to the caller).

## Scheduled Functions

Run a function on a cron schedule without an HTTP trigger:

```javascript
// netlify/functions/cleanup.js
export const config = {
  schedule: "@hourly",  // or "0 * * * *" cron syntax
};

export const handler = async () => {
  await deleteExpiredRecords();
  return { statusCode: 200 };
};
```

Supported cron shortcuts: `@hourly`, `@daily`, `@weekly`, `@monthly`. Cron syntax follows standard POSIX cron (5-field UTC). Scheduled Functions run in the same Node.js runtime as regular functions and share the same 10-second limit — use Background Function pattern for longer jobs triggered by schedule.

Scheduled Functions cannot be triggered via HTTP in production (the URL is non-routable); test locally with `netlify functions:invoke <name>`.

## Netlify Blobs from functions

Blobs provide persistent key-value storage that survives across deploys. Read and write from functions:

```javascript
import { getStore } from "@netlify/blobs";

export const handler = async (event) => {
  const store = getStore("my-store");       // site-wide store, persists across deploys
  // OR: getStore({ name: "my-store", deployScoped: true })  // deploy-scoped, wiped on new deploy

  await store.set("last-sync", new Date().toISOString());
  const value = await store.get("last-sync");

  return { statusCode: 200, body: value };
};
```

Blob reads from Edge Functions use the same API — import from `netlify:blobs` (edge variant):

```typescript
import { getDeployStore } from "netlify:blobs";
export default async (req: Request, context: Context) => {
  const store = getDeployStore();
  const cached = await store.get("homepage-data", { type: "json" });
  // ...
};
```

## Request context injection

Every Function invocation receives the following automatically from Netlify:

- `context.clientContext.identity` — Netlify Identity JWT claims (if the request carries a valid Identity token).
- `context.clientContext.user` — decoded user object (sub, email, app_metadata, user_metadata).
- `event.headers["x-nf-geo"]` — JSON-encoded geo info in Functions (see Edge Functions for richer `context.geo`).
- `event.headers["client-ip"]` — true client IP (may differ from `x-forwarded-for` on some paths).

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Synchronous Function doing > 10 s of work | Gateway timeout; caller gets an error with no retry. Use Background Function. |
| Edge Function with heavy npm dependencies | Import overhead bloats script size; cold-path latency increases. Edge is for thin, fast logic. |
| Storing secrets in Function code or committed `.env` | Pre-commit scan won't catch runtime secrets baked into source. Use Netlify env vars scoped to Functions. |
| Using Background Function for a response the caller needs | Caller gets 202; your result is orphaned. If the caller needs data, use a synchronous Function. |
| Scheduled Function doing > 10 s of CPU work | Hits the synchronous limit. Invoke a Background Function from a Scheduled Function instead. |
| Calling `context.next()` and returning a response | Sends two responses; one is dropped unpredictably. Pick one. |
| Edge Function importing Node.js built-ins (`path`, `crypto`) | Deno runtime; use Web APIs (`crypto.subtle`, `URL`) instead. |

## Security defaults

- Secrets accessed via environment variables scoped to `Functions` context only — not `Build` or `Runtime`.
- Never log `event.headers["authorization"]` or any value that could contain a token or credential.
- Validate all inputs. Functions are public endpoints unless explicitly gated by an authorizer.
- For Identity-protected routes: verify `context.clientContext.user` is present and check `app_metadata.roles` before serving protected data.
- Edge Functions that modify response headers: ensure you don't strip security headers set elsewhere in the chain.

## Observability defaults

- Structured JSON logs (`console.log(JSON.stringify({ level: "info", msg, requestId }))`).
- Log every function invocation result (status, duration_ms, error if any) at the handler boundary.
- Function logs are visible in the Netlify dashboard (site → Functions → Logs) for the last hour; configure a Logs Drain for longer retention.
- Track invocation counts and error rates in the dashboard Functions tab; alert on sustained error spikes.

## Cost considerations

- Starter plan: 125,000 function invocations/month; Edge Function invocations are separate and generous (500k included).
- Go beyond included limits: ~$25 / 500k additional synchronous invocations.
- Background Functions count as regular invocations but run longer — watch for the combination of high frequency + long execution.
- Edge Function invocations are cheap relative to Serverless Functions; prefer Edge for high-traffic, low-logic routes.
- Scheduled Functions count against invocation limits on each run; a `@hourly` function burns 720 invocations/month.

## IaC hints

- `netlify.toml` `[functions]` block configures function directory, included/excluded files, and per-function settings.
- Per-function configuration (bundler, node version, timeout override):
  ```toml
  [functions.my-function]
    node_bundler = "esbuild"
    included_files = ["data/*.json"]
  ```
- Edge Function path bindings declared in `netlify.toml` `[[edge_functions]]` blocks.
- `netlify functions:invoke <name> --payload '{"key":"val"}'` for local testing without deploying.

## Verification checklist

- [ ] Function type justified against the decision tree (sync vs background vs edge vs scheduled).
- [ ] 10-second limit respected for synchronous functions; background used for long work.
- [ ] Secrets in environment variables, not source; scoped to `Functions` context.
- [ ] Input validation present at every handler entry point.
- [ ] Identity claims verified before serving protected data (not just "header is present").
- [ ] Structured logs with a correlation ID propagated across hops.
- [ ] Invocation limit checked against expected traffic volume for the billing tier.
- [ ] Edge Functions tested against Deno import constraints — no Node.js-only modules.
