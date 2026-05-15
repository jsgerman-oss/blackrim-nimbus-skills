---
name: vercel-observability-and-cost
description: Wire up or audit Vercel observability and cost — Web Analytics (privacy-first, no cookies), Speed Insights (Core Web Vitals), Logs (real-time + Logs Drains to Datadog / Logflare / etc.), OpenTelemetry traces, Spend Management (budgets, hard limits), and tracking edge / function / bandwidth / image-optimization consumption. Use when adding telemetry, investigating a performance regression, or controlling a growing bill.
---

# Vercel Observability and Cost

## When to use

- Adding observability to a new Vercel project before launch.
- Investigating a Core Web Vitals regression (LCP, FID/INP, CLS).
- Shipping function logs to an external aggregation system.
- Setting a hard spend limit to prevent surprise bills.
- Diagnosing a bandwidth or function invocation spike.
- Building a performance budget and tracking it over time.

## Observability pillars

| Pillar | Vercel-native tool | Best external alternative |
| --- | --- | --- |
| Real-user metrics (Core Web Vitals) | Speed Insights | DataDog RUM, Sentry Performance |
| Pageview analytics (no cookies) | Web Analytics | Plausible, Fathom |
| Function logs (real-time) | Logs tab in Dashboard | DataDog, Logflare, Better Stack |
| Structured log shipping | Logs Drains | DataDog, Logflare, Axiom |
| Traces / distributed tracing | OpenTelemetry (OTEL) | DataDog APM, Honeycomb, Jaeger |
| Build output analysis | Dashboard / CLI | — |

## Web Analytics

Vercel Web Analytics is a privacy-first pageview counter that uses no cookies, requires no consent banner, and complies with GDPR and CCPA out of the box.

```typescript
// app/layout.tsx — Next.js App Router
import { Analytics } from '@vercel/analytics/react';

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html>
      <body>
        {children}
        <Analytics />
      </body>
    </html>
  );
}
```

**What it tracks:** pageviews, unique visitors, referrers, browsers, OS, country. No user-level identity, no cross-site tracking.

**What it does not track:** custom events, conversions, funnel analysis, user sessions. For those needs, add a specialized analytics tool (PostHog, Mixpanel) alongside Web Analytics.

**Sampling:** Web Analytics samples at high traffic volumes. It is a trend tool, not an exact counter. For billing-critical pageview counting, use a server-side log counter instead.

## Speed Insights (Core Web Vitals)

Speed Insights collects real-user Core Web Vitals (LCP, INP, CLS, TTFB, FCP) from actual browsers and surfaces them in the Vercel Dashboard per-route.

```typescript
// app/layout.tsx
import { SpeedInsights } from '@vercel/speed-insights/next';

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html>
      <body>
        {children}
        <SpeedInsights />
      </body>
    </html>
  );
}
```

**Using the data:**

- Filter by route to find which page has the worst LCP.
- Filter by country/device to find geography- or device-specific regressions.
- "Good" thresholds: LCP < 2.5 s, INP < 200 ms, CLS < 0.1. Set these as performance budgets.
- Speed Insights reports P75 by default — the 75th percentile is what Google measures for Search ranking.

**Limitations:** Speed Insights data is only available in the Vercel Dashboard — no API to export raw CWV events. For programmatic alerting or correlation with deploys, instrument your own RUM alongside Speed Insights.

## Logs (real-time)

The Vercel Dashboard Logs tab provides real-time streaming of Serverless and Edge Function logs per deployment. Useful for debugging; not suitable for programmatic alerting or long-term retention.

```bash
# Stream logs for the production deployment
vercel logs https://my-project.vercel.app --follow

# Stream logs for a specific deployment URL
vercel logs https://my-project-abc123.vercel.app
```

**Log format:** Vercel wraps your function's stdout/stderr with deployment metadata. Structure your application logs as JSON for downstream parsing:

```typescript
// Structured logging pattern
console.log(JSON.stringify({
  level: 'info',
  message: 'User login',
  userId: user.id,
  requestId: request.headers.get('x-vercel-id'),
  region: process.env.VERCEL_REGION,
}));
```

Use `x-vercel-id` (the request header Vercel injects) as a correlation ID — it ties a single request across Edge Middleware and Serverless Function hops.

## Logs Drains

Logs Drains ship function logs in real time to an external system. Configure at the team level (applies to all projects) or per-project.

**Supported drain types:** HTTP (any endpoint), DataDog, Logflare (Supabase-owned), Better Stack, New Relic, Amazon Kinesis.

```json
// Vercel API — create a Logs Drain
{
  "url": "https://http-intake.logs.datadoghq.com/api/v2/logs",
  "sources": ["static", "edge", "function", "build", "external"],
  "headers": { "DD-API-KEY": "<redacted>", "Content-Type": "application/json" }
}
```

**Sources to drain:**

| Source | What it contains |
| --- | --- |
| `function` | Serverless Function stdout/stderr |
| `edge` | Edge Function and Middleware logs |
| `build` | Build step logs (useful for CI debugging) |
| `static` | Static asset request logs |
| `external` | ISR and external fetch logs |

**Set up alerting in the drain destination** — Vercel itself has no native alerting on log content.

## OpenTelemetry

Vercel supports OTEL-compatible traces from Serverless Functions via the `@vercel/otel` package. Traces flow to any OTLP-compatible backend (DataDog, Honeycomb, Jaeger, Tempo).

```typescript
// instrumentation.ts (Next.js instrumentation hook)
import { registerOTel } from '@vercel/otel';

export function register() {
  registerOTel({ serviceName: 'my-app' });
}
```

Set the OTLP endpoint and auth header as env vars:

```bash
OTEL_EXPORTER_OTLP_ENDPOINT=https://api.honeycomb.io/v1/traces
OTEL_EXPORTER_OTLP_HEADERS=x-honeycomb-team=<token>
```

**Trace propagation:** Next.js 15 propagates trace context across Server Components, Route Handlers, and Server Actions automatically when `@vercel/otel` is registered. Instrument outgoing `fetch` calls and database queries for a complete trace.

**Portability:** `@vercel/otel` is a thin wrapper over the OpenTelemetry JS SDK. The backend is fully swappable — this is not platform-coupled.

## Spend Management

Vercel Pro and Enterprise plans support Spend Management — budgets and hard limits that prevent bill overruns.

**Budget types:**

| Type | Effect |
| --- | --- |
| Soft limit (notification) | Email alert when spend exceeds threshold; service continues |
| Hard limit (cutoff) | Service is throttled or suspended when spend exceeds threshold |

**Set a hard limit at project creation, not after an incident.**

```bash
# Via Vercel CLI — not directly supported; use Dashboard or API
# Project Settings → Usage → Spend Management → Set Limit
```

**Recommended per-project limits for new projects:**

- Start with 2× your estimated monthly cost as a notification threshold and 5× as a hard limit.
- Revisit monthly until usage stabilizes.

## Usage categories and what drives them

| Usage category | Primary driver | How to reduce |
| --- | --- | --- |
| **Edge Function invocations** | Every request hitting Edge Functions or Middleware | Tighten Middleware matcher; cache aggressively |
| **Serverless Function invocations** | API route hits, ISR cache misses | Increase ISR `revalidate` interval; cache database reads |
| **Serverless Function GB-seconds** | Memory × duration per invocation | Right-size `maxDuration`; reduce memory usage |
| **Bandwidth** | All outbound traffic from Vercel | Serve assets from CDN; compress responses; use Blob for large files |
| **Image optimization** | `next/image` transformations (unique source × size combinations) | Serve pre-optimized images; reduce `deviceSizes` array |
| **Build minutes** | Every build triggered by a push | Use `turbo-ignore`; skip builds for unaffected packages |
| **KV commands** | Reads and writes per request | Batch reads; use `mget`; cache in-process for hot keys |
| **Blob bandwidth** | Downloads of Blob-stored files | Pre-compress; use Image Optimization for images |

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| `console.log` with large objects in production | Logs volume consumes Logs Drain bandwidth and external storage costs. Log fields, not full objects. |
| No Spend Management limits | A traffic spike or runaway ISR cache miss loop creates a surprise invoice. |
| Relying on Dashboard Logs for production alerting | Dashboard Logs have no alerting surface. Use a Logs Drain + downstream alert. |
| Speed Insights without a performance budget | Data without a threshold is decoration. Set LCP < 2.5 s, INP < 200 ms, CLS < 0.1 as acceptance criteria. |
| Draining `build` logs in production at high volume | Build logs are verbose. If storage cost at the drain destination matters, filter to `function` + `edge` only. |
| Image Optimization on server-rendered images without `sizes` hint | Vercel generates many redundant size variants. Always provide `sizes` on `next/image`. |

## Observability defaults for every project

- Web Analytics: on from day one (zero config, zero cookies, zero compliance overhead).
- Speed Insights: on from day one.
- Structured JSON logs in application code (with request ID and region).
- Logs Drain to DataDog / Logflare: configured before launch.
- OTEL instrumentation: wired to a backend before launch if the app has Serverless Functions with external I/O.
- Spend Management: soft limit = 2× estimated monthly, hard limit = 5× estimated monthly.

## IaC hints

- Terraform `vercel/vercel` provider: `vercel_project` has no direct spend management field — configure via Vercel API or Dashboard.
- Logs Drains are configurable via the Vercel API (`POST /v1/integrations/log-drains`) — script this in onboarding automation.
- `@vercel/otel` and `@vercel/analytics` and `@vercel/speed-insights` are npm packages; version-pin them in `package.json`.

## Verification checklist

- [ ] Web Analytics and Speed Insights enabled and emitting data.
- [ ] Logs Drain configured to an external system with alerting capability.
- [ ] Structured JSON logging in all Serverless and Edge Functions, including request ID.
- [ ] OTEL traces wired to a backend for any function doing multi-hop I/O.
- [ ] Spend Management soft and hard limits set.
- [ ] Performance budget defined: LCP, INP, CLS thresholds documented per key route.
- [ ] Usage categories reviewed: bandwidth, function GB-seconds, image optimization invocations within expected range.
- [ ] No unbounded `console.log(largeObject)` calls in production hot paths.
