---
name: netlify-observability-and-cost
description: Set up or audit Netlify observability and cost management — server-side Analytics, Function / Edge Function / Build logs, Logs Drain (Datadog / Logflare), Real User Monitoring, bandwidth and build minutes dashboards, billing tiers (Starter / Pro / Enterprise), and spend cap configuration. Use when adding telemetry to a Netlify site, diagnosing a cost spike, or planning a billing tier decision.
---

# Netlify Observability and Cost

## When to use

- Adding logging or monitoring to a newly deployed Netlify site.
- Diagnosing a Function error spike, latency regression, or build failure.
- Understanding a bandwidth or build minutes overage on the bill.
- Choosing between Netlify Analytics and a third-party analytics solution.
- Wiring Netlify logs to an external observability platform (Datadog, Logflare, etc.).
- Preparing for a plan upgrade decision with data.
- Setting a spend cap to prevent surprise bills.

## Observability pillars

| Pillar | Netlify native | Third-party alternative |
| --- | --- | --- |
| Build logs | Dashboard build log (30 days) | Logs Drain → Datadog / Logflare |
| Function logs | Dashboard Functions → Logs (1 hour live; drain for longer) | Logs Drain |
| Edge Function logs | Dashboard Edge Functions → Logs | Logs Drain |
| Real User Monitoring | Netlify RUM (Pro+, add-on) | Datadog RUM, Sentry, Grafana Faro |
| Server-side analytics | Netlify Analytics (paid add-on) | Plausible, Fathom, Umami |
| Synthetic monitoring | Not native | Checkly, Pingdom, Grafana Cloud |
| Error tracking | Not native | Sentry, Honeybadger |

## Build logs

Every build generates a timestamped log stream in the Netlify dashboard (**Deploys → [deploy] → Deploy log**). Logs are retained for 30 days.

Key things to look for in build logs:

- `Build exceeded maximum allowed runtime` — hit the 15/30-minute limit; optimize or split.
- `Error: Cannot find module '...'` — missing devDependency; check `package.json`.
- `Dependency file: /opt/build/cache/node_modules` — cache hit confirmation.
- Plugin execution time (`netlify-plugin-lighthouse: 45.2s`) — flag slow plugins.

For longer build log retention, configure a Logs Drain (Pro+).

## Function logs

Serverless Function logs appear in **Site overview → Functions → [function name] → Logs**. The live tail shows the last 60 minutes.

Structured logging from Functions:

```javascript
// Always emit structured JSON from Functions
export const handler = async (event, context) => {
  const start = Date.now();
  console.log(JSON.stringify({
    level: "info",
    msg: "invocation start",
    requestId: context.awsRequestId,
    path: event.path,
    method: event.httpMethod,
  }));

  try {
    const result = await doWork(event);
    console.log(JSON.stringify({
      level: "info",
      msg: "invocation complete",
      requestId: context.awsRequestId,
      durationMs: Date.now() - start,
      statusCode: 200,
    }));
    return { statusCode: 200, body: JSON.stringify(result) };
  } catch (err) {
    console.error(JSON.stringify({
      level: "error",
      msg: "invocation error",
      requestId: context.awsRequestId,
      error: err.message,
      stack: err.stack,
    }));
    return { statusCode: 500, body: "Internal error" };
  }
};
```

Use `context.awsRequestId` as the correlation ID — it appears in Netlify's platform logs alongside your structured log lines, making cross-referencing straightforward.

## Edge Function logs

Edge Function logs appear in **Site overview → Edge Functions → [function name] → Logs**.

```typescript
export default async (request: Request, context: Context) => {
  console.log(JSON.stringify({
    level: "info",
    msg: "edge invocation",
    path: new URL(request.url).pathname,
    country: context.geo?.country?.code,
    ip: context.ip,
  }));
  return context.next();
};
```

Note: Edge Function logs have higher latency to appear in the dashboard than Function logs — allow up to 30 seconds.

## Logs Drain

Logs Drain forwards all Netlify log events (build, function, edge function, access) to an external destination in real time. Available on **Pro and Enterprise** plans.

Supported destinations:

- **Datadog** — select from the dashboard, provide an API key; logs appear in Datadog Log Management.
- **Logflare / Supabase** — provide an ingest endpoint and API key.
- **Custom HTTP endpoint** — POST JSON to any URL (useful for Grafana Loki, OpenSearch, Splunk, etc.).

Configure under **Site configuration → Logs → Log drains**.

Sample Datadog drain configuration:

```
Drain type: Datadog
Datadog API key: <your-key>
Datadog site: datadoghq.com
Service: <your-site-name>
```

With Logs Drain active, keep the dashboard Function log view for fast debugging; use Datadog / Logflare for historical queries, alerting, and anomaly detection.

Recommended Datadog monitors from Netlify logs:

- Error rate spike in Functions: `level:error` count > threshold in 5-minute window.
- Build failure: `event_type:deploy_failed` — page on-call.
- Edge Function latency: `durationMs > 500` on high-traffic routes.

## Netlify Analytics

Netlify Analytics is a **server-side** analytics add-on ($9/month per site as of 2026). Because it runs on Netlify's edge — not JavaScript in the browser — it captures:

- All traffic including bot traffic, ad blockers, no-JS browsers.
- Page views, unique visitors, top pages, top referrers, bandwidth per page.
- 404 and redirect counts (useful for detecting broken links post-deploy).

Limitations:

- No custom events or conversion tracking.
- No user sessions in the marketing analytics sense.
- No integration with ad platforms.

For marketing analytics, pair Netlify Analytics (for accurate traffic volume) with a privacy-first tool (Plausible, Fathom, or Umami) for behavioral analytics.

Enable under **Site configuration → Analytics → Enable analytics**.

## Real User Monitoring

Netlify RUM (Real User Monitoring) is available as an add-on on Pro+ plans. It captures:

- Core Web Vitals (LCP, FID/INP, CLS) from real user sessions.
- Time to first byte (TTFB) per page and region.
- Resource load times.

RUM data appears in the Netlify dashboard Analytics → Real User Monitoring.

For more powerful RUM (session replay, alerting, custom metrics), use Datadog RUM, Sentry, or Grafana Faro alongside Netlify RUM — they're not mutually exclusive.

## Bandwidth dashboard

Netlify's bandwidth meter is under **Team overview → Usage → Bandwidth**. Key facts:

- Bandwidth is measured as total data transferred from Netlify's CDN to users, including cached responses.
- Starter: 100 GB/month.
- Pro: 1 TB/month.
- Overage on Pro: $55 / 100 GB (verify current pricing in the dashboard).

Bandwidth reduction strategies:

1. **Enable aggressive asset caching** — set long `Cache-Control` max-age for hashed assets (JS, CSS, images). Netlify honors the `Cache-Control` header in your `_headers` or `netlify.toml`.
2. **Image optimization** — use a framework's image component (Next.js `<Image>`, Astro `<Picture>`) to serve WebP/AVIF and resize to display dimensions.
3. **Audit large assets** — use `netlify deploy --build --dry` to see file sizes before deploying; remove large unneeded assets from `publish`.
4. **Functions vs static** — traffic served from Functions does not benefit from CDN caching (unless you set `Cache-Control` on the response). Static files are cached and cheap.

## Build minutes dashboard

Build minutes are under **Team overview → Usage → Build minutes**.

| Plan | Included minutes/month | Overage cost |
| --- | --- | --- |
| Starter | 300 | Not available; upgrade required |
| Pro | 1,000 | $7 / 500 min |
| Enterprise | Custom | Negotiated |

Build minutes consumed per deploy: `build_time_seconds / 60`, rounded up. Every Deploy Preview and Branch Deploy consumes minutes.

Optimization strategies:

- **Skip CI** for non-functional commits.
- **Disable auto-deploy-preview** for dependency bot PRs (Dependabot, Renovate) via the Netlify dashboard → Build & deploy → Deploy preview settings → Stop builds from forks / bots.
- **Cache node_modules** — already on by default; verify cache hits in build logs.
- **Split large monorepos** — use `netlify.toml` `[build] ignore` script to skip builds when only unrelated packages changed.
- **Parallel builds** (Enterprise) — reduce wall-clock time for sites with many concurrent PRs.

## Billing tiers

| Feature | Starter (free) | Pro ($19/mo/site) | Enterprise (custom) |
| --- | --- | --- | --- |
| Bandwidth | 100 GB | 1 TB | Custom |
| Build minutes | 300/mo | 1,000/mo | Custom |
| Team members | 1 | Unlimited | Unlimited |
| Form submissions | 100/mo | 1,000/mo | Custom |
| Function invocations | 125,000/mo | 125,000/mo (+ pricing) | Custom |
| Analytics | Add-on | Add-on | Included |
| Password protection | Yes | Yes | Yes |
| SSO (dashboard) | No | No | Yes |
| Concurrent builds | 1 | 3 | Custom |
| Logs Drain | No | Yes | Yes |
| WAF / advanced DDoS | No | Basic | Full |
| SLA | None | 99.99% | 99.99% + |

## Spend cap configuration

Netlify does not have a hard spend cap by default. Overages on Pro accrue silently. To avoid surprise bills:

1. Enable email billing alerts under **Team settings → Billing → Billing alerts** — set a threshold in dollars.
2. Use the usage API (`GET /api/v1/sites/<site_id>/usage`) from a scheduled Function to emit a metric to your monitoring platform and alert when bandwidth or build minutes exceed a threshold.
3. For Pro+ plans, contact Netlify support to negotiate a hard cap (available for Enterprise).

A pragmatic manual cap: set a Slack notification for when bandwidth hits 80% of the monthly limit. This gives time to investigate before overage accrues.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Skipping structured logs | `console.log("error!")` is unsearchable in Datadog / Logflare; incidents take 10× longer to diagnose. |
| Relying solely on Netlify's 1-hour Function log window | Log evidence from yesterday's incident is gone; no Logs Drain means no forensics. |
| No spend cap awareness on Pro | Dependabot opening 50 PRs a day burns build minutes; bandwidth spike from a viral post surprises the billing contact. |
| JavaScript-only analytics | Ad blockers, bots, and no-JS environments are invisible. Server-side analytics is more accurate. |
| No alert on build failure | Failed deploys go unnoticed; production is stale while the team wonders why features aren't live. |
| Counting all analytics traffic as users | Netlify Analytics includes bot traffic in page views. Cross-reference with Plausible / Fathom for human-only counts. |

## Security defaults

- Logs contain request headers, paths, and error messages. Ensure your structured logs never emit `Authorization` headers, API keys, or PII.
- Logs Drain destination (Datadog, Logflare) has access to all log events. Treat the Logs Drain API key with the same care as a database credential.
- Netlify Analytics data is stored by Netlify; it does not leave to a third-party analytics vendor. This is a data-residency advantage over Google Analytics.

## IaC hints

- Logging and analytics are configured via the Netlify dashboard or API — no `netlify.toml` stanzas for these.
- `netlify env:set NETLIFY_LOG_LEVEL debug` in a Function context enables verbose Function logging for debugging builds.
- Bandwidth and build minutes usage available via the Netlify API (`GET /api/v1/accounts/<account_id>/usage`) — useful for building custom spend dashboards.
- Community Terraform `netlify/netlify` provider does not yet support Analytics or Logs Drain configuration.

## Verification checklist

- [ ] Functions emit structured JSON logs with a correlation ID on every invocation.
- [ ] Logs Drain configured (Pro+ sites) to a persistent destination (Datadog, Logflare).
- [ ] Deploy success / failure notifications wired to a team channel.
- [ ] Billing alert threshold set in Team settings → Billing.
- [ ] Bandwidth usage checked monthly; alert threshold set at 80% of plan limit.
- [ ] Build minutes usage checked monthly; Dependabot / bot PR deploy-previews disabled if consuming disproportionate minutes.
- [ ] Netlify Analytics (or equivalent) reporting reviewed weekly; 404 spike indicates a broken deploy.
- [ ] Log content audited to ensure no PII or secrets emitted in log lines.
