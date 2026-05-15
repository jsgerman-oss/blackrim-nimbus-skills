---
name: cf-observability-and-cost
description: Wire up or audit Cloudflare observability and cost — Workers Analytics Engine, Logpush, Trace Workers, Web Analytics, GraphQL Analytics API, dashboard alerts, and billing tiers. Use when adding telemetry to Workers, debugging a production issue, reviewing billing, or deciding when to upgrade plans.
---

# Cloudflare Observability and Cost

## When to use

- Adding request-level metrics to a Worker without a traditional APM agent.
- Shipping logs from Cloudflare products (WAF, Access, Tunnel, DNS) to a SIEM or data warehouse.
- Debugging a latency regression or error spike in a Worker or Durable Object.
- Building a custom analytics dashboard on top of Cloudflare telemetry.
- Reviewing the Cloudflare bill and identifying which products or traffic patterns drive cost.
- Deciding whether to stay on the current plan or upgrade to a higher tier.

## The edge observability constraint

Workers run in V8 isolates — traditional APM agents, sidecar collectors, and language-level instrumentation (OpenTelemetry SDK auto-instrumentation) do not work inside the isolate. Edge observability requires explicit instrumentation using Cloudflare-native primitives.

| Pillar | Cloudflare mechanism |
| --- | --- |
| Metrics | Workers Analytics Engine |
| Logs | Workers Logs (dashboard / `wrangler tail`) + Logpush |
| Traces | Trace Workers |
| RUM | Cloudflare Web Analytics |
| Synthetic uptime | Cloudflare Health Checks / Load Balancer monitors |
| Infrastructure | Workers Analytics Engine or Logpush for Durable Objects |

## Workers Analytics Engine

Analytics Engine (AE) is a time-series columnar store purpose-built for high-throughput event emission from Workers. Think of it as a managed ClickHouse endpoint accessible from within a Worker.

### Defaults

- Declare the AE dataset binding in `wrangler.toml`: `[[analytics_engine_datasets]]` with a `binding` name and `dataset` name.
- Emit from a Worker: `env.AE.writeDataPoint({ blobs: [...], doubles: [...], indexes: [...] })`. This is non-blocking — it does not add latency to the response path.
- **Blobs** (up to 20): arbitrary string dimensions (route, method, user tier, region, error code). Limited to 1 KiB each.
- **Doubles** (up to 20): numeric measurements (response time, bytes transferred, retry count).
- **Indexes** (up to 1): a single string field used as a primary group-by key for efficient SQL GROUP BY queries. Choose wisely — it cannot be changed per data point.
- Query via the **Workers Analytics Engine SQL API** (`/v1/accounts/{account_id}/analytics_engine/sql`). Use `SELECT blob1, sum(double1) FROM dataset WHERE timestamp > ...` syntax.
- AE data is available within seconds of emission; retention varies by plan (default 31 days, up to 90 days on Enterprise).
- Do not use `console.log` as a substitute for AE metrics — console output is not aggregatable and is ephemeral.

## Logpush

Logpush ships raw log data from Cloudflare products to external destinations (R2, S3, Datadog, Splunk, Google Cloud Storage, HTTP endpoint, and more).

### Available log sources

| Source | What it logs |
| --- | --- |
| HTTP requests | Every proxied request: URL, status, cache status, WAF action, origin response time, ray ID |
| Workers Logs | `console.log` output and exception traces from Workers |
| Firewall (WAF) events | Every rule match, action taken, rule ID |
| Access audit logs | Every Access policy evaluation: user, device, action, application |
| Gateway DNS | Every DNS query resolved by Gateway |
| Gateway HTTP | Every HTTP request inspected by Gateway |
| Network Analytics | Packet-level stats for Magic Transit / Magic WAN |
| Durable Objects | DO lifecycle events, storage operations |

### Defaults

- Route Logpush jobs to **R2 first** — zero egress cost, and you can query with Workers or export to a downstream system on your schedule.
- For real-time SIEM ingestion: Logpush to Datadog, Splunk, or an HTTP endpoint. Latency is typically < 60 s.
- Enable at minimum: HTTP request logs (zone-level), Workers Logs, and WAF event logs for every production zone and account.
- Fields: select only the fields you need — unnecessary fields add storage cost and noise.
- Logpush jobs have a configurable batch interval (minimum 30 s). For high-traffic sites, batches can be large; size your destination to handle it.
- Compress logs at rest (Logpush supports gzip); parse on read with your analytics stack.

## Trace Workers

Trace Workers receive trace data for every invocation of a Worker they are bound to — request headers, response status, log messages, exceptions, and timing — without modifying the observed Worker.

- Available on Workers Paid. Declare in `wrangler.toml` with `[[tail_consumers]]`.
- Use to forward traces to an external observability backend (Honeycomb, Grafana, New Relic) without changing application code.
- Trace Workers run after the observed Worker completes; they cannot modify the response.
- Limit: one Trace Worker per observed Worker. Chain if needed (Trace Worker → observability Worker → backend).

## `wrangler tail`

During development and incident response, `wrangler tail --env production` streams live log output from a deployed Worker to the terminal. Useful for:

- Rapid debugging without instrumenting Logpush.
- Verifying that a deploy behaved as expected.
- Watching Durable Object alarm fires in real time.

Not a substitute for Logpush for persistent log collection — `wrangler tail` drops logs if the WebSocket to the Cloudflare Workers backend disconnects.

## Web Analytics

Cloudflare Web Analytics provides privacy-preserving real-user monitoring without cookies or client-side JavaScript tracking that causes GDPR complexity.

- Enable by adding a lightweight JS snippet (or via the Cloudflare-served snippet for Pages / Workers-served sites).
- Metrics: Core Web Vitals (LCP, FID, CLS), page views, geographic distribution, device type.
- No personal data stored; no need for cookie banners for this analytics source.
- For deeper funnel analytics (user behavior, conversion tracking), complement with a privacy-safe analytics tool (Plausible, Fathom) — Web Analytics covers performance, not product analytics.

## GraphQL Analytics API

Every Cloudflare product's analytics are queryable via a GraphQL API (`/client/v4/graphql`).

- Use for custom dashboards, automated reporting, and alerting pipelines.
- Key datasets: `httpRequests1dGroups`, `firewallEventsAdaptiveGroups`, `workersAnalyticsEngineAdaptiveGroups`, `loadBalancingRequestsAdaptive`, `dnsFirewallAnalyticsAdaptive`.
- Rate limits apply per account. Batch queries and use `datetime_geq` / `datetime_leq` filters to bound result size.
- Authenticate with a scoped API token that has `Account Analytics: Read` permission.
- Cloudflare's own dashboard is built on this API — anything you see in the dashboard is queryable via GraphQL.

## Dashboard alerts

Cloudflare's **Notifications** system (dashboard > Account > Notifications) sends alerts via email, PagerDuty, Slack webhook, or generic webhook.

- Configure alerts for: DDoS attack detected, WAF attack volume spike, Load Balancer health-check failure, Worker error rate spike, certificate expiry, bot traffic anomaly.
- Every Notification policy is zone- or account-scoped. Ensure production zones have at minimum: DDoS alert, WAF spike alert, health check failure alert, and certificate expiry alert.
- Worker-specific metrics alerts are currently limited in the dashboard — supplement with Analytics Engine queries run on a schedule and alerting via your own pipeline.

## Billing tiers — when to upgrade

| Plan | Key thresholds |
| --- | --- |
| **Free** | 100k Worker requests/day, no Cron Triggers in production, no Durable Objects, no Logpush, limited WAF |
| **Workers Paid ($5/mo)** | 10M Worker requests/mo (included), Durable Objects, Cron Triggers, Logpush, Workers Unbound billing available, Pages Functions |
| **Pro ($20/mo/zone)** | Bot Fight Mode++, advanced WAF rules, image optimisation, 50 page rules equivalent (Cache Rules) |
| **Business ($200/mo/zone)** | 100% uptime SLA, advanced Bot Management, Page Shield enforcement, custom WAF rate limiting |
| **Enterprise** | Full Bot Management, Magic Transit, Magic WAN, Advanced DDoS, custom contracts, dedicated support |

**Upgrade triggers:**
- Free → Workers Paid: as soon as you need Durable Objects, Cron Triggers, Logpush, or >100k requests/day.
- Pro: as soon as you need advanced WAF custom rules or Bot Fight Mode for a public-facing site with measurable bot traffic.
- Business: SLA requirements, Page Shield enforcement, or advanced rate limiting.
- Enterprise: Magic Transit, full Bot Management, or contractual SLA commitments.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Relying only on `console.log` for production metrics | Logs are ephemeral and not aggregatable. Analytics Engine + Logpush are required for durable metrics. |
| No Logpush configured for WAF events | Security incidents leave no forensic trail. WAF Logpush is mandatory. |
| Querying GraphQL Analytics API from a Worker on every request | GraphQL API has rate limits. Query on a schedule, not per-user-request. |
| Logpush to S3 without R2 as a cost-saving intermediate | S3 egress from Cloudflare is non-zero; R2 is free egress and easier to access from Workers. |
| Trace Workers left on in high-traffic production permanently | Trace Workers add a small overhead per invocation. Profile the impact; use Logpush for high-volume persistent collection. |
| Web Analytics as the sole metrics source for API Workers | Web Analytics is RUM (browser page loads). It has no visibility into API Worker request patterns. Use Analytics Engine for APIs. |
| Upgrading to Enterprise before exhausting Business plan capabilities | Enterprise pricing is significantly higher. Business covers most production needs; upgrade only when a specific Enterprise feature is required. |

## Observability defaults

- **Every production Worker**: Analytics Engine binding wired; `writeDataPoint` on every request (route, status, latency, error type) and on every `catch` block.
- **Every production zone**: Logpush jobs for HTTP requests and WAF events, routing to R2.
- **Durable Objects**: Trace Worker bound to capture lifecycle events; AE writeDataPoint on alarm fires and significant storage operations.
- **Access/Gateway**: Logpush jobs enabled; logs forwarded to SIEM within 24 hours of enabling the Access application.
- **Dashboard Notifications**: DDoS, WAF spike, health-check failure, certificate expiry alerts configured on all production accounts.

## Cost considerations

- Analytics Engine: priced per million writes and per billion bytes scanned in queries. Reduce scan cost by setting a narrow `datetime` filter and using the `index` field for efficient group-bys.
- Logpush: billed per million log records delivered (check current pricing; it has changed with plan tiers). R2 destination has zero egress but storage cost applies.
- Workers Paid: $5/mo base covers most small-to-medium Workers workloads. Durable Object duration cost grows with active (non-hibernated) time — hibernate aggressively.
- Trace Workers: no explicit additional charge beyond Workers Paid, but they consume Worker invocations and CPU time — they count against your Workers usage.
- Web Analytics: free on all plans.
- GraphQL Analytics API: free queries; no per-query charge.

## IaC hints

- Analytics Engine dataset binding: `[[analytics_engine_datasets]]` in `wrangler.toml`.
- Logpush jobs: `cloudflare_logpush_job` resource in Terraform. Requires `cloudflare_logpush_ownership_challenge` + ownership verification before the job activates.
- Notification policies: `cloudflare_notification_policy` in Terraform; pair with `cloudflare_notification_policy_webhooks` for Slack/PagerDuty targets.
- Trace Workers: declared via `[[tail_consumers]]` in `wrangler.toml` of the observed Worker.

## Verification checklist

- [ ] Every production Worker emits to Analytics Engine on every request and every error path.
- [ ] Logpush jobs active for HTTP requests, WAF events, and Access audit logs.
- [ ] Logpush destination is R2 or a SIEM; retention > 90 days for security-relevant logs.
- [ ] `wrangler tail` tested and confirmed working for incident response use.
- [ ] Dashboard Notification policies cover DDoS, WAF spike, health-check failure, and certificate expiry.
- [ ] GraphQL Analytics API queries tested for custom alerting pipelines.
- [ ] Billing tier matches actual feature usage; no features gated above current plan are needed in production.
- [ ] Analytics Engine query costs bounded by proper `datetime` filters and index field selection.
