---
name: render-observability-and-cost
description: Wire up or audit Render observability and cost — built-in metrics (CPU, memory, request rate, response time), log streams and retention, Datadog / New Relic / Logtail integrations, alerts, billing by service plan and hours, free tier limits, and plan upgrade decisions. Use when adding telemetry, diagnosing a regression, or sizing a cost review.
---

# Render Observability and Cost

## When to use

- Setting up log streaming to an external provider for a new service.
- Diagnosing a latency or error spike using Render's built-in metrics.
- Deciding whether to upgrade a service plan based on resource utilization.
- Building a cost estimate for a Render-hosted application.
- Integrating Render logs with Datadog, New Relic, or Logtail.
- Understanding what Render's free tier gives you before you exceed it.

## Built-in metrics

Render provides per-service metrics for Web Services, Private Services, Background Workers, and Cron Jobs:

| Metric | What it measures |
| --- | --- |
| CPU utilization | Percentage of allocated vCPU consumed |
| Memory utilization | Percentage of allocated RAM consumed |
| Request rate | Requests per minute (Web Services only) |
| Response time | p50 / p95 / p99 response latency (Web Services only) |

**Retention**: Render stores metrics for 30 days. For longer retention, ship metrics to an external provider.

**Limitations**: Render's built-in metrics are instance-level, not service-level aggregated, when multiple replicas are running. The dashboard shows per-instance views — sum or average them manually for a fleet view. External providers aggregate better.

**Actionable thresholds for plan upgrades:**

- CPU consistently > 70% during normal traffic → plan is undersized; upgrade to the next tier.
- Memory consistently > 80% → risk of OOM kills (container restarts); upgrade or optimize.
- For Postgres: `DatabaseConnections` near the plan's connection limit → add PgBouncer or upgrade.

## Logs

Render provides rolling log access for each service via the dashboard. Logs are streamed in real time and retained for a rolling window (approximately 7 days on paid plans).

**Log streaming to external providers:**

Render supports native log stream integrations:

| Provider | Setup |
| --- | --- |
| Datadog | Configure in Render team settings: Datadog API key + site. Renders emits all service logs to Datadog's log intake. |
| New Relic | Configure with New Relic License Key. |
| Logtail (Better Stack) | Configure with Logtail source token. |
| Custom HTTP endpoint | Send logs to any HTTPS endpoint with a Bearer token. |

Enable log streaming on day one for any production service — Render's rolling 7-day window is not sufficient for incident forensics or compliance.

**Structured logging:**

- Emit structured JSON logs from your application. Render passes log lines through verbatim; structured logs are indexed and searchable in Datadog / Logtail.
- Include a `request_id` field in every log line and propagate it from incoming request headers (`X-Request-ID` or similar). This enables tracing a request through multiple services.
- Log at `INFO` level in production; do not log secrets, credentials, or PII.

## Alerts

Render has a native alerting system for Web Services:

| Alert type | Trigger |
| --- | --- |
| Deploy failed | Build or deploy step returns non-zero |
| Service down | Health check fails for N consecutive checks |
| CPU / memory threshold | Utilization exceeds a configured percentage |

Alerts deliver to email or a webhook (Slack, PagerDuty, etc.).

**Best practices:**

- Set up a deploy failure alert for every production service — failed deploys are a push-to-notify incident.
- Set CPU and memory alerts at 80% to give time to react before hitting resource limits.
- Use a webhook alert to route service-down notifications to your oncall channel.
- Supplement with external uptime monitoring (Checkly, BetterUptime, Pingdom) — Render's internal health checks gate deploys but do not provide continuous external monitoring.

## Integrations

### Datadog

Datadog is the most complete integration. It captures:

- Logs from all Render services.
- Custom metrics emitted via DogStatsD from your application (ship via UDP to a Datadog agent sidecar, or use the Datadog Lambda layer equivalent for your runtime).
- APM traces if you instrument your application with the Datadog APM SDK.

Render does not run a Datadog agent — you must emit metrics and traces from the application process itself.

### New Relic

Similar to Datadog: log forwarding plus application-level instrumentation via the New Relic agent in your app.

### Logtail / Better Stack

Logtail is a lower-cost log aggregation option when you only need logs and alerts, not full APM. Good fit for smaller teams or workloads where Datadog pricing is not justified.

## Billing model

Render charges by:

1. **Service plan tier**: flat rate per service per month (or prorated per hour for services started/stopped mid-month).
2. **Bandwidth**: outbound data transfer beyond the free allowance (~100 GB/month on paid plans as of 2026-05).
3. **Persistent Disk**: per GB per month.
4. **Build minutes**: paid plans include build minutes; overages are charged per minute.

**No idle charge exemptions**: Unlike serverless platforms, Render charges for a service even when it receives no traffic (except the free tier, which sleeps). If a service genuinely has no traffic for extended periods, delete it or move it to the free tier temporarily.

### Service plan cost reference (approximate as of 2026-05)

| Plan | Per-service per month |
| --- | --- |
| Free | $0 (with sleep) |
| Starter | $7 |
| Standard | $25 |
| Pro | $85 |
| Pro Plus | $175 |
| Pro Max | $450 |

Managed Postgres and Redis have separate per-plan pricing. Multiple instances (autoscaled replicas) multiply the plan cost proportionally.

## Free tier limits and semantics

- **Web Services**: sleep after 15 minutes of inactivity; wake on next request (30–60s cold start).
- **Postgres**: deleted after 90 days of inactivity; suspended after a shorter period of no activity.
- **Build minutes**: free tier has 500 build minutes/month; overages pause builds until the next billing cycle.
- **Static Sites**: free, no sleep, CDN-backed — no production-use restrictions.

Free tier is appropriate for development, proof-of-concept, and personal projects. It is not appropriate for any production service where latency, availability, or data persistence matter.

## When to upgrade plan tier

| Signal | Action |
| --- | --- |
| CPU consistently > 70% | Upgrade to next plan tier |
| Memory consistently > 80% | Upgrade or investigate memory leaks |
| Service sleeps (free tier) | Upgrade to Starter ($7/mo) |
| Need autoscaling | Upgrade to Standard |
| Need HA Postgres / PITR | Upgrade Postgres to Standard |
| Need read replicas | Upgrade Postgres to Standard |
| Hitting build minute limits | Upgrade plan or cache builds more aggressively |

## Cost optimization

- **Autoscaling with `minInstances: 1`**: avoid scale-to-zero (which would cause cold starts) while allowing scale-out only when needed.
- **Build caching**: use Render's build cache for Docker layer caching and `node_modules` caching. Build times directly affect build minute consumption.
- **Cron Jobs for batch**: use Cron Jobs for periodic tasks instead of a Background Worker that polls. Cron Jobs only consume compute during their run window.
- **Static Sites for frontends**: there is no charge for Static Sites; if your frontend is a pure SPA or static site, it should be a Static Site, not a Web Service serving HTML.
- **Review inactive services monthly**: it is common to accumulate staging/preview services that are no longer needed. Render's team dashboard lists all services with their plan; audit it monthly.
- **Preview environment expiry**: configure `previewsExpireAfterDays:` in `render.yaml` so Preview environments are automatically deleted; uncapped previews accumulate cost.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| No log streaming on a production service | Logs lost after 7 days; no history for incident investigations. Enable Datadog / Logtail on day one. |
| Relying on Render's dashboard-only monitoring | No alerting, no metrics retention > 30 days, no cross-service correlation. Supplement with external monitoring. |
| Free Postgres in production | Database is suspended or deleted after inactivity; data loss risk. Use Starter or above. |
| Uncapped `maxInstances` on autoscaled services | A traffic spike or DDoS results in an unexpectedly large bill. Set explicit `maxInstances`. |
| Deploy failure notifications going to no one | Failed deploys are silent until a user complains. Configure deploy failure alerts to oncall. |
| No external uptime monitor | Render's internal health checks only run during deploys; ongoing availability is unmonitored. Use Checkly or BetterUptime. |
| Preview environments accumulating indefinitely | Preview environments charge at full service plan rate; stale previews add up. Set `previewsExpireAfterDays:`. |

## IaC hints

- Log drain configuration is in Render team settings (not per-service); one log drain applies to all services in the team.
- Alert configuration is per-service in the Render dashboard or via the Render API.
- `previewsExpireAfterDays:` is set in the `previews:` block of `render.yaml`.
- Autoscaling bounds (`minInstances`, `maxInstances`) are set in the service's `autoscaling:` block.

## Verification checklist

- [ ] Log streaming enabled to an external provider (Datadog, Logtail, or custom) for all production services.
- [ ] Deploy failure alerts configured and routed to oncall / chat channel.
- [ ] CPU and memory alerts set at 80% for all production services.
- [ ] External uptime monitor in place for every user-facing Web Service.
- [ ] `maxInstances` explicitly set on all autoscaled services to cap spend.
- [ ] `previewsExpireAfterDays:` set in `render.yaml` to prevent stale preview environment accumulation.
- [ ] Free tier not used for production databases or user-facing Web Services.
- [ ] Monthly cost review conducted; inactive services pruned.
- [ ] Build cache enabled to minimize build minutes.
- [ ] Structured logging with `request_id` field emitted by all services.
