---
name: railway-observability-and-cost
description: Set up or audit Railway observability and cost — built-in log streaming (live and historical), service Metrics (CPU / memory / network), the Observability dashboard (Pro plan), external log drains (Datadog, Better Stack, Logflare), Railway's per-second billing model, and a cadence for reviewing the Usage page. Use when adding telemetry to a service, wiring a log drain, diagnosing a cost spike, or setting up a regular billing review.
---

# Railway Observability and Cost

## When to use

- Setting up log shipping from Railway to an external provider (Datadog, Better Stack, Logflare).
- Diagnosing why a service is crashing, slow, or using more resources than expected.
- Reviewing the Railway Usage page for cost surprises.
- Establishing a regular billing review cadence.
- Adding structured logging to an app deployed on Railway.
- Using the Pro plan Observability dashboard for aggregated metrics.

## Built-in logs

Railway captures all `stdout` and `stderr` output from every service and Plugin. Access:

- **Dashboard (live):** Service → "Logs" tab. Streams in real-time. Filter by service, deployment, and time range.
- **Railway CLI:**

  ```bash
  railway logs --service my-api          # tail live
  railway logs --service my-api --tail 200  # last 200 lines
  ```

Log retention on Railway:

- **Free plan:** limited (short rolling window).
- **Pro plan:** longer retention, configurable in project settings.

For compliance or debugging history beyond Railway's retention, configure a log drain immediately — Railway does not buffer logs for you.

## Structured logging best practices

Railway's log UI and all drains work best with JSON-formatted log lines:

```json
{"level":"info","msg":"request handled","path":"/api/orders","latency_ms":42,"request_id":"abc-123","ts":"2026-05-13T10:00:00Z"}
```

- Include a `request_id` (or `trace_id`) in every log line and propagate it through internal calls via headers (`X-Request-ID`, `traceparent`).
- Log at `info` in production for normal paths; `error` with a stack trace for failures. Avoid `debug` in production unless temporarily enabled — it generates volume that inflates drain costs.
- Never log secrets, full connection strings, or PII.

## Service Metrics

Every Railway service (including Plugins) emits built-in metrics visible in the dashboard:

| Metric | What it tells you |
| --- | --- |
| CPU usage (%) | Whether the service is CPU-bound or has headroom |
| Memory usage (MB) | Whether OOM kills are imminent |
| Network in / out (bytes/s) | Unexpected egress spikes |
| Disk read / write (Plugins) | I/O saturation on database Plugins |

Access: Service → "Metrics" tab.

Gaps in the built-in metrics:

- No application-level metrics (request count, error rate, latency percentiles) — these must come from your app's instrumentation or a drain.
- No alerting on metrics thresholds — alerts require a drain to an external system.

## Observability dashboard (Pro plan)

Pro plan projects get an aggregated Observability dashboard with cross-service metric views, log search, and configurable time ranges. Useful for:

- Correlating a spike in one service's CPU with elevated error rates in a downstream service.
- Cross-service log search without switching between service log tabs.

For Free plan projects: there is no aggregated view. Navigate per-service in the dashboard or rely on drain aggregation.

## Log drains

Configure a log drain to ship all Railway logs to an external provider. Supported drains (as of 2026-05):

| Provider | Setup path |
| --- | --- |
| **Datadog** | Project Settings → Observability → Log Drains → Datadog. Provide API key + site. |
| **Better Stack (Logtail)** | Project Settings → Observability → Log Drains → Better Stack. Provide source token. |
| **Logflare / Supabase** | Project Settings → Observability → Log Drains → Logflare. Provide API key + source ID. |
| **Custom HTTP drain** | Any HTTP endpoint that accepts a POST with log lines. |

Drain covers all services in the project. There is no per-service drain scoping.

**Datadog setup example:**

```text
Provider: Datadog
API Key: <your DD API key>
Site: datadoghq.com  # or datadoghq.eu, etc.
```

Once configured, Railway ships structured logs as Datadog log events. Add `service` and `env` tags via Railway Variables:

```text
DD_SERVICE=my-api
DD_ENV=production
```

**Better Stack example:**

1. Create a source in Better Stack.
2. Copy the source's "Source token".
3. Add the drain in Railway with the token.
4. Better Stack parses Railway's JSON log format automatically.

## Billing model

Railway charges per-second CPU and memory usage across all services and Plugins. There is no fixed monthly server bill — you pay for what runs.

**Pricing components (as of 2026-05):**

| Resource | Unit |
| --- | --- |
| CPU | $/vCPU-minute |
| Memory | $/GB-minute |
| Network egress | $/GB |
| Volume storage | $/GB-month |

**Free plan:** includes a monthly credit (check Railway's pricing page for current amount). Services pause after the credit is consumed.

**Pro plan:** no spending cap by default; pay what you use. Set a spending limit in Billing settings to avoid surprise invoices.

**What drives costs:**

- Always-on services with generous resource limits.
- Preview environments with Plugins that are left running after PR merge.
- High network egress from services sending large responses or streaming data.
- Volumes that accumulate data without a cleanup strategy.

## Usage page review cadence

Review the Railway Usage page (Project → Usage) at least:

- **Weekly** during a new project's first month — watch for unexpected Plugin costs or preview environment accumulation.
- **Monthly** thereafter — compare to the previous month; investigate any step-change.

What to look for:

| Signal | Probable cause |
| --- | --- |
| CPU spike on a specific service | Runaway job, memory leak causing GC pressure, traffic spike |
| Memory creep over time | Memory leak in the app; set a lower memory limit and fix the leak |
| Network egress spike | Large payloads, misconfigured CDN bypass, log drain sending uncompressed data |
| Many small Plugin instances | Preview environments not cleaned up; delete stale environments |
| Usage jump after a deploy | New code path with expensive computation; profile and optimize |

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Unstructured logs (plain print statements) | Log drain can't parse fields; searches are substring-only; no metric extraction. |
| No log drain on Free plan | Logs disappear after Railway's short retention window; post-mortem is impossible. |
| No spending limit on Pro plan | A runaway service or forgotten preview environment generates an unbounded bill. |
| Preview environments left running after PR merge | Each environment has its own Plugin(s); accumulates cost invisibly until the bill arrives. |
| Logging secrets or connection strings | Drain ships them to a third-party service; exposure is permanent once the log exists. |
| Ignoring memory metrics until OOM kills occur | OOM kills cause sudden restarts; monitor memory and set limits proactively. |

## Security defaults

- Log drain API keys and source tokens are secrets — store them in Service Variables, not in code.
- Railway's log drain sends logs over HTTPS/TLS; data in transit is encrypted.
- If logs contain customer data, verify the drain provider's data residency and compliance certifications before enabling.
- Sanitize PII from log lines before they reach Railway (filter at the application layer, not the drain layer).

## Cost considerations

- Set a spending limit in Railway Billing Settings (Pro plan) as the first step after upgrading.
- Delete preview environments promptly after PR merge (manually or via a GitHub Actions cleanup job).
- Right-size resource limits — Railway bills on actual usage up to the limit; a service idling at 5% CPU with a 4 vCPU limit still has that limit available for bursts, but idle cost is based on actual consumption.
- Better Stack (Logtail) has a free tier sufficient for small projects; Datadog log ingestion is priced per GB — set log-level appropriately to control volume.

## IaC hints

Log drain configuration is dashboard-only (no `railway.json` support as of 2026-05). Automate drain setup via the Railway API if you provision projects programmatically:

```bash
# Railway GraphQL API example (check Railway docs for current schema)
POST https://backboard.railway.app/graphql/v2
Authorization: Bearer $RAILWAY_API_TOKEN
{ mutation { createLogDrain(input: { ... }) { id } } }
```

## Verification checklist

Before declaring observability and cost configuration complete:

- [ ] App emits structured JSON logs with `request_id` on every line.
- [ ] Log drain configured and verified (send a test request; confirm it appears in the drain).
- [ ] No secrets or PII in log output (verified by inspecting sample log lines).
- [ ] Spending limit set in Railway Billing (Pro plan).
- [ ] Usage page review cadence established (weekly first month, monthly thereafter).
- [ ] Memory and CPU limits set in service settings; baseline metrics reviewed.
- [ ] Preview environment cleanup process in place (manual policy or automated GitHub Action).
- [ ] Datadog / Better Stack dashboard or alert configured for service error rate and memory usage (if drain is in use).
