---
name: fly-observability-and-cost
description: Wire up or audit observability and cost on Fly.io — built-in Grafana metrics, fly logs (NATS-backed), shipping to external observability stacks, OpenTelemetry support, Fly pricing model (machine-seconds, volumes, egress). Use when adding telemetry to a Fly app, diagnosing a regression, or sizing a cost review.
---

# Fly Observability and Cost

## When to use

- Setting up metrics, logs, and traces for a new Fly-hosted service.
- Diagnosing a latency spike, error surge, or cold-start regression.
- Shipping logs or metrics to an external observability stack (Datadog, Grafana Cloud, etc.).
- Auditing current Fly spend and identifying cost reduction opportunities.
- Setting up OpenTelemetry instrumentation end-to-end.

## Observability pillars on Fly

| Pillar | Fly native | How to extend |
| --- | --- | --- |
| Metrics | Built-in Grafana + Prometheus-compatible endpoint | Ship via OTEL collector or push to Datadog / Grafana Cloud |
| Logs | `fly logs` (NATS-backed, recent window) | Ship via `fly-log-shipper` or NATS subscriber to external SIEM / log store |
| Traces | Not built-in | Add OTEL SDK to your app; ship to Tempo, Jaeger, Honeycomb, Datadog |
| Synthetics | Not built-in | External uptime monitor (BetterUptime, Cronitor, Pingdom) |
| Machine health | Fly Proxy health checks + Grafana | Alert via Fly's built-in alert rules or external alertmanager |

## Built-in metrics — Fly Grafana

Fly includes a Grafana-backed metrics platform at `https://fly.io/apps/<app>/metrics`. It exposes per-machine and per-app metrics including:

- CPU utilization (user, system, steal).
- Memory usage and swap.
- Network bytes in/out.
- Machine restarts and health check status.
- HTTP request rate, response time percentiles, and error rates (for apps using the Fly HTTP handler).
- Volume IOPS and throughput.

These metrics are retained for a rolling window (currently 30 days). For longer retention, ship to an external store.

### Prometheus-compatible scraping

Fly exposes a Prometheus-compatible metrics endpoint. You can configure an external Prometheus or Grafana Cloud agent to scrape it. Fly also supports pushing metrics via the OTEL Collector.

## Logs — `fly logs` and NATS

`fly logs` streams live log output from all machines of an app. It is backed by NATS and delivers logs with low latency. Limitations:

- **Short retention:** `fly logs` provides a real-time stream. Historical log storage is not provided natively.
- **No built-in search.** For search and retention, ship logs externally.

For production observability, treat `fly logs` as a live tail tool only. All logs must be shipped externally for retention and search.

### Shipping logs externally

Fly provides a `fly-log-shipper` app (open-source) that subscribes to the NATS log stream and forwards to supported backends:

```bash
# Deploy fly-log-shipper to your org
# (see github.com/superfly/fly-log-shipper for configuration)
```

Supported sinks: Papertrail, Datadog, Logtail, S3 / Tigris (for cheap archival), Elasticsearch / OpenSearch, syslog-compatible endpoints.

Alternatively, ship structured logs from within your app process using HTTP or gRPC to any external endpoint.

## OpenTelemetry (OTEL) support

Fly supports receiving OpenTelemetry traces via OTLP. As of 2025, Fly provides an experimental OTEL ingest endpoint; check current documentation for GA status.

For robust OTEL coverage:

1. **Instrument your app** with the OTEL SDK (Python, Go, Node.js, Java, etc.).
2. **Run an OTEL Collector** as a sidecar or standalone Fly Machine in your org.
3. **Export** from the Collector to your backend (Honeycomb, Grafana Tempo, Jaeger, Datadog).

```yaml
# otel-collector-config.yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317

exporters:
  otlphttp:
    endpoint: "https://api.honeycomb.io"
    headers:
      x-honeycomb-team: "${HONEYCOMB_API_KEY}"

service:
  pipelines:
    traces:
      receivers: [otlp]
      exporters: [otlphttp]
```

Set `OTEL_EXPORTER_OTLP_ENDPOINT` and `OTEL_EXPORTER_OTLP_HEADERS` as Fly secrets on your app machines.

## Application logs — what to emit

- **Structured JSON logs** with a stable `request_id` field that propagates through the full call chain.
- **Timing and error fields** on every external call (database, HTTP client, queue consumer).
- **Machine ID and region** in log fields — Fly machines have `FLY_MACHINE_ID`, `FLY_REGION`, `FLY_APP_NAME` as environment variables; include them in every log record.

```go
// Example: Go structured log with Fly context
log.Info("request completed",
    "request_id", r.Header.Get("X-Request-Id"),
    "duration_ms", time.Since(start).Milliseconds(),
    "status", status,
    "fly_region", os.Getenv("FLY_REGION"),
    "fly_machine_id", os.Getenv("FLY_MACHINE_ID"),
)
```

## Alarms and alerting

Fly's built-in Grafana supports creating alert rules. For production services, define at minimum:

- **Machine restart rate:** alert when any machine restarts more than once in 5 minutes (crash loop signal).
- **Health check failures:** alert when health checks fail on any machine.
- **HTTP 5xx rate:** alert when 5xx response rate exceeds a threshold.
- **Volume fill:** alert when disk utilization on any volume exceeds 80%.
- **Postgres replication lag:** alert when replica falls behind primary by more than your RPO.

For PagerDuty / Slack / email routing, configure Grafana alert contact points and notification policies in the Fly Grafana dashboard.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Relying on `fly logs` for retention | Logs are a live stream only. A past incident has no searchable history. |
| No structured logs | `grep` on unstructured logs during an incident is slow and error-prone. |
| Omitting `FLY_REGION` / `FLY_MACHINE_ID` from logs | During a multi-region incident, you cannot tell which machine produced which log line. |
| No external OTEL backend | Fly's built-in metrics give infra-level signals; you cannot trace a request through your app's business logic without instrumentation. |
| Alarms only on CPU | CPU is a lagging indicator. Alarm on request rate, error rate, queue depth, and health check status. |
| Infinite Grafana retention assumption | Fly's built-in metrics have a retention window. Archive to your own store for long-term trend analysis. |

## Observability defaults

- Every machine emits structured JSON logs to stdout/stderr.
- Logs shipped externally via `fly-log-shipper` or in-process HTTP shipper.
- OTEL Collector deployed as a Fly Machine; traces exported to an external backend.
- Fly Grafana alert rules defined for: machine restarts, health check failures, 5xx rate.
- External uptime monitor confirms app reachability from outside Fly's network.

## Fly pricing model — cost

### How billing works

Fly bills on actual consumption, not reservation:

| Component | Billing unit |
| --- | --- |
| Machine compute | Per-second of runtime (rounded up), per machine class |
| Stopped machine | Free |
| Suspended machine | Small charge for memory preservation |
| Volume storage | GB-month provisioned |
| Volume snapshots | GB stored |
| Network egress | Per GB, by source region |
| Dedicated IPv4 | ~$2/month per IP |
| Fly Redis (Upstash) | Per command + bandwidth |
| Tigris storage | Per GB stored + operations + egress |

### Cost optimization levers

| Lever | Where it helps |
| --- | --- |
| `auto_stop_machines = "stop"` | Zero charge for idle machines. Net zero for zero-traffic services. |
| `min_machines_running = 0` | No always-warm machines. Accept cold starts. |
| `shared-cpu` vs `performance` | Shared CPU is cheaper; use performance only for consistently high-CPU workloads. |
| Fewer regions | Each region with `min_machines_running >= 1` adds a baseline charge. |
| Volume sizing discipline | Provision minimum viable volume; resize up. No charge discount for under-use. |
| Tigris over external S3 | Tigris egress within Fly's network is cheaper than egress to an external AWS S3. |
| Remove unused dedicated IPs | $2/mo per allocated IP, whether in use or not. |
| Postgres right-sizing | Fly Postgres machines are billed as standard machines. A `shared-cpu-1x` is sufficient for many dev/staging Postgres instances. |

### Cost visibility

- **Dashboard:** `fly.io/dashboard` shows spending by app and by resource type.
- **Budget alerts:** configure via Fly billing settings → Spending Limits. Alert before exceeding a monthly budget.
- **Estimate before scaling:** `machine_count * machine_hours * hourly_rate + volumes + egress`. Back-of-envelope before spinning up 10 machines.

### Common cost surprises

- **Volume persists after machine delete.** `fly volumes delete` is a separate step. Volumes accumulate quietly if you destroy and recreate machines frequently.
- **Postgres replica in a second region.** Adds two machine-hours (primary + replica) plus two volumes. Plan this cost explicitly.
- **Egress from high-traffic regions.** Egress rates from `lax` (Los Angeles), `iad` (Ashburn), `lhr` (London) differ. Serve large files from Tigris, not from machine memory.
- **LiteFS WAL archival to Tigris.** Frequent writes generate frequent WAL segments; monitor Tigris operations cost.

## IaC hints

- Fly Grafana alert rules can be exported as JSON and version-controlled for reproducibility.
- OTEL Collector configuration is a `fly.toml` + a config file in the image; treat it as a standard Fly app.
- Cost monitoring: pull spend data from Fly billing API or use the dashboard export. There is no native AWS Cost Explorer equivalent; build a simple scraper if automated cost alerting is needed.

## Verification checklist

- [ ] Every service emits structured JSON logs with `request_id`, `fly_region`, and `fly_machine_id` fields.
- [ ] Logs are shipped to an external store with ≥ 30-day retention.
- [ ] OTEL traces are collected and searchable in an external backend.
- [ ] Fly Grafana alert rules defined for machine restarts, health failures, and 5xx rate.
- [ ] External uptime monitor confirms availability from outside Fly.
- [ ] Volume fill alarm set at 80%.
- [ ] `fly volumes list` shows no orphaned volumes from deleted machines.
- [ ] Fly billing dashboard reviewed; unexpected charges investigated within 7 days of appearance.
- [ ] Budget limit set; alert fires before overage.
