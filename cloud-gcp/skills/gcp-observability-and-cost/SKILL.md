---
name: gcp-observability-and-cost
description: Wire up or audit GCP observability and cost — Cloud Monitoring, Cloud Logging (log sinks to BigQuery / GCS / Pub/Sub), Cloud Trace, Profiler, Error Reporting, Recommender, Active Assist, Committed Use Discounts, Spend Alerts. Use when adding telemetry, tracking down a regression, or shrinking a bill.
---

# GCP Observability and Cost

## When to use

- Setting up logs, metrics, and traces for a new GCP service.
- Building an SLO dashboard or wiring an alerting policy to an on-call channel.
- Diagnosing a latency, error, or cost regression.
- Evaluating Committed Use Discount purchases for Compute Engine or GKE.
- Running a quarterly cloud cost review against GCP billing.

## Observability pillars

| Pillar | GCP service |
| --- | --- |
| Metrics | Cloud Monitoring (includes GCP built-in metrics + custom metrics) |
| Logs | Cloud Logging (structured log ingestion, log-based metrics, log sinks) |
| Traces | Cloud Trace (native) + OpenTelemetry → Cloud Trace exporter |
| Continuous profiling | Cloud Profiler (CPU, heap, goroutine, thread profiling in production) |
| Error aggregation | Error Reporting (automatic grouping of exceptions from Cloud Logging) |
| Synthetics | Cloud Monitoring Uptime Checks (HTTP/S, TCP, ICMP) |
| Real User Monitoring | Firebase Performance Monitoring (for mobile/web apps) |

## Defaults — every service

- **Structured JSON logs** with at least `severity`, `message`, `traceId`, and a service-specific `requestId` field. GCP's log viewer and log-based metrics parse JSON automatically.
- **Cloud Trace** enabled on all services. For Cloud Run and Cloud Functions, the trace header (`X-Cloud-Trace-Context` or `traceparent`) is injected automatically by the platform; propagate it through all downstream calls.
- **Custom metrics** via the Cloud Monitoring API or as log-based metrics from structured logs — for business signals not covered by built-in metrics (e.g., queue depth, retry count, batch job completion rate).
- **Error Reporting** connected to Cloud Logging for automatic exception detection; configure notification channels so new error groups alert immediately.
- **Log retention**: Cloud Logging default is 30 days for `_Default` log bucket; use `_Required` log bucket (with 400-day retention) for audit logs. For longer retention, export via a log sink to Cloud Storage or BigQuery.

## Alerting policies — write them like contracts

A well-formed alerting policy has:

- **Condition:** which metric, alignment period, threshold, and duration (e.g., "Cloud Run request error rate > 1% over 5 minutes").
- **Notification channel:** PagerDuty, Slack, email, or Pub/Sub — route to the team that owns the service, not a generic inbox.
- **Documentation:** a link to the runbook in the policy description. The first thing an on-call engineer reads at 3 AM.

Avoid: CPU-only thresholds, thresholds without a duration window (causes flapping), and alerting policies with no attached notification channel.

Use **multi-condition alerting policies** (AND/OR across metrics) to reduce noise — e.g., alert only when error rate is high AND request rate is above a minimum baseline (so you don't page on errors during zero-traffic windows).

## Cloud Monitoring dashboards

- One dashboard per service, one per environment.
- Top row: the three golden signals — latency (p50, p95, p99), traffic (request rate), and error rate.
- Middle row: dependencies — upstream latency, downstream error rate, database query time.
- Bottom row: resource saturation — instance count, memory utilization, disk usage, connection pool.
- Create dashboards in Terraform (`google_monitoring_dashboard`) so they survive project recreation and are version-controlled.

## Cloud Trace and distributed tracing

- For services running on Cloud Run, GKE, or Compute Engine: use the Cloud Trace SDK (`cloud.google.com/go/trace`) or the OpenTelemetry Go/Python/Java/Node SDK with the Cloud Trace exporter.
- Propagate trace context (`X-Cloud-Trace-Context` or W3C `traceparent`) through HTTP headers, Pub/Sub message attributes, and gRPC metadata.
- Add span attributes for high-cardinality dimensions (user ID, tenant, request type) so you can filter traces in the Trace Explorer.
- Trace sampling: 100% for low-volume services; tail-based sampling at 5–10% for high-volume services using the OpenTelemetry Collector.

## Cloud Profiler

- Enable Cloud Profiler on long-running services (GKE workloads, Compute Engine services, App Engine Flex). It continuously samples CPU and heap usage with < 1% overhead.
- Profiler is not available for Cloud Run invocations shorter than a few seconds; for those, use Cloud Trace span data and log-based latency metrics instead.
- Use profiler comparisons (two time windows or two deployments) to measure whether a code change improved performance.

## Log sinks and long-term retention

- Export logs via **log sinks** (`google_logging_project_sink`) to:
  - **Cloud Storage**: cheap long-term archive; use lifecycle rules to Nearline/Coldline after 90 days.
  - **BigQuery**: for queryable log analytics (security investigations, anomaly detection, business queries on structured logs).
  - **Pub/Sub**: for real-time stream to an external SIEM (Chronicle, Splunk, Elastic, Datadog).
- Apply an **inclusion filter** on each sink to export only what you need — exporting all logs everywhere is both expensive and operationally noisy.
- Organization-level sinks: use an aggregated sink at the org level to centralize security-relevant logs (AuditActivity, IAM, SCC findings) to a dedicated security project.

## Cost — the actual playbook

### Visibility

- **Cloud Billing reports**: filter by service, project, label, and SKU. Tag every resource with labels (`environment`, `service`, `owner`, `cost_center`) enforced via Org Policy (`constraints/gcp.resourceLocations` doesn't help here, but `tags` do with billing export).
- **Billing export to BigQuery**: enable for detailed and resource-level billing data. Write SQL queries in BigQuery to slice cost by any dimension.
- **Budget alerts**: set budgets at the project and billing account level; send to Pub/Sub for programmatic response (e.g., auto-disable a project's billing if it spikes).
- **Recommender and Active Assist**: review VM rightsizing recommendations (`google_recommender_recommendation` data source), idle resource recommendations, and security health recommendations from the GCP console or `gcloud recommender recommendations list`.

### Optimization levers

| Lever | Where it pays |
| --- | --- |
| Committed Use Discounts (resource-based, 1y or 3y) | Compute Engine vCPU and memory; 37% (1y) or 55% (3y) discount on N2 / N2D. |
| Committed Use Discounts (flex, 1y) | Per-core and per-memory units that flex across machine types; better for varied fleets. |
| Spot VMs | Stateless, restartable Compute Engine workloads — 60–91% cheaper. |
| GKE Autopilot | Billed per Pod resource request, not per node; idle capacity is eliminated. |
| Cloud Run with min-instances=0 | Zero cost when idle; best for low-traffic or batch workloads. |
| Cloud Storage storage classes + OLM | Move infrequently accessed data to Nearline/Coldline/Archive automatically. |
| BigQuery slot reservations | Predictable analytics workloads: slot commitment + reservation assignment beats on-demand above a usage threshold. |
| Sustained Use Discounts (automatic) | Compute Engine VMs that run for more than 25% of a month get automatic discounts — no commitment needed. |
| Active Assist idle VM/disk recommendations | Clean up stopped VMs with attached persistent disks; unused PDs cost money. |
| Inter-region traffic reduction | Co-locate services that talk frequently; avoid unnecessary cross-region fan-out. |

### Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Cloud Logging with no log sinks and default retention only | 30 days isn't enough for compliance; also wastes the analytics value of log data. |
| Cloud Trace not propagating context across service hops | You can see spans inside one service but not the end-to-end trace. Propagate `traceparent` everywhere. |
| Infinite log-based metric cardinality | Custom metrics with high-cardinality labels (user ID, request ID) create millions of time series and unbounded cost. Aggregate before emitting. |
| No budget alerts until the bill arrives | Surprises compound monthly. Set budgets the day a project goes live. |
| Committed Use Discounts bought before usage stabilizes | You commit to resources you don't need. Wait for 30+ days of stable usage. |
| BigQuery on-demand without query cost controls | One analyst scanning a full multi-TB table without a partition filter costs more than a month of slot reservations. |
| Dashboards built only in the console | They're lost in a project recreation or when the creator leaves. IaC them. |

## Observability + cost together

Observability investment pays back in engineering time saved during incidents. The cheapest incident is the one detected in 30 seconds by an alerting policy pointing to a runbook — not the 4-hour firefight with no dashboards.

Common false economies:

- Disabling Cloud Trace to save trace ingestion costs → spending engineer hours correlating logs across services manually.
- Setting log retention to 7 days to save storage cost → missing the incident data needed for the post-mortem.
- Not enabling Cloud Profiler → shipping a CPU regression to prod with no production data to explain it.

## IaC hints

- Terraform: `google_monitoring_alert_policy`, `google_monitoring_dashboard`, `google_logging_project_sink`, `google_logging_metric`, `google_monitoring_notification_channel`, `google_monitoring_uptime_check_config`.
- Log-based metrics: `google_logging_metric` with a filter that parses structured JSON fields and a `metric_descriptor` with appropriate units and labels.
- Budget alerts: `google_billing_budget` with `threshold_rules` and a Pub/Sub topic for programmatic handling.
- Managed notification channels: define Slack and PagerDuty channels in Terraform (using the sensitive fields manager); avoid relying on console-only channel configuration.

## Verification checklist

- [ ] Every service emits structured JSON logs with at least `severity`, `message`, and `traceId`.
- [ ] Cloud Trace context propagated end-to-end across all service hops.
- [ ] Log retention bounded; log sinks configured for compliance and analytics.
- [ ] At least one alerting policy per service tied to a user-visible signal, with a linked runbook.
- [ ] Budget alerts set on every project and billing account; Pub/Sub handler for programmatic response.
- [ ] Recommender findings reviewed at least monthly; idle resources cleaned up.
- [ ] Committed Use Discount coverage tracked; commitments match stable usage baseline.
- [ ] Dashboards in IaC for top services and live in version control.
- [ ] Cloud Profiler enabled on long-running services; profiling data used in performance reviews.
