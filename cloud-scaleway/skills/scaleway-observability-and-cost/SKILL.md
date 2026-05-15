---
name: scaleway-observability-and-cost
description: Wire up or audit Scaleway observability and cost — Cockpit (managed Grafana + metrics + logs), Cost Manager, Organization-level billing, Resource Tag filters, log retention tiers, alerting through Cockpit. Use when adding telemetry, tracking down a regression, building dashboards, or shrinking a bill.
---

# Scaleway Observability and Cost

## When to use

- Setting up logs, metrics, and alerts for a new Scaleway workload.
- Building an SLO dashboard in Cockpit for a Serverless Container or Kapsule service.
- Diagnosing a latency, error, or cost regression.
- Reviewing Organization or Project-level billing and planning optimization.
- Sizing a monthly cloud cost review and identifying savings levers.
- Wiring Cockpit alerts to PagerDuty, Slack, or email.

## Cockpit — the observability hub

Scaleway Cockpit is a managed Grafana + Prometheus + Loki stack. Each Project has its own Cockpit instance; you can view cross-Project data from the Organization Cockpit in supported configurations.

### What Cockpit ingests by default

| Source | What populates automatically |
| --- | --- |
| Instances | CPU, RAM, disk, network I/O metrics |
| Kapsule | Node CPU/RAM/disk, pod count, control-plane status |
| Serverless Containers | Invocation count, error count, cold-start latency, container CPU/RAM |
| Serverless Functions | Invocation count, error count, latency histogram |
| Managed Databases | Connections, CPU, free storage, replication lag, slow query count |
| Redis Cluster | Memory, evicted keys, connected clients, command throughput |
| Load Balancers | Request rate, active connections, backend health |
| Object Storage | Request count, egress bytes, error rate (via Cockpit or access logs) |

### Application-level telemetry

- **Metrics**: send via OpenTelemetry (OTLP) or Prometheus remote write to the Cockpit push endpoint. Use `scaleway_cockpit_token` (Terraform) to obtain a push token scoped to the Project.
- **Logs**: push via Loki-compatible API (promtail, OpenTelemetry Collector, Fluent Bit) to Cockpit. Structure logs as JSON with a `request_id` field for correlation across hops.
- **Traces**: Cockpit does not (as of 2026-Q2) provide a managed trace backend. Route traces to an external OTLP endpoint (Grafana Tempo, Jaeger, Honeycomb) and link from Cockpit dashboards via iframe or Grafana data source plugin.

### Grafana dashboards

- Scaleway pre-loads managed dashboards for its own services (Kapsule cluster overview, Serverless Container metrics). Do not edit managed dashboards — they are overwritten on updates.
- Create application dashboards in Cockpit's Grafana "user" folder. Export as JSON and version-control in git.
- Dashboard structure: top row = SLI (availability, request rate, error rate, latency p50/p95/p99). Middle = dependencies (upstream and downstream health). Bottom = capacity (memory pressure, connection pool saturation, queue depth).
- Variables: parameterize dashboards by `project`, `region`, and `environment` so a single dashboard JSON covers dev/staging/prod.

### Alerting

Cockpit supports alert rules via the Grafana Alerting interface (backed by Prometheus-compatible rule evaluation).

Good alert spec:
- **Signal**: which metric, at which percentile, over which window (e.g., error rate > 1% over 5 min).
- **Threshold**: the value that means a human needs to act now.
- **Routing**: which contact point — email, Slack webhook, PagerDuty, generic webhook.
- **Runbook link**: in the alert annotation, always. First thing the responder reads.

Bad alerts: "CPU > 80%" with no runbook, alerts that fire and are silenced daily, alerts with no owner.

Alert contact points: configured in Cockpit → Grafana → Alerting → Contact points. Configure a Slack webhook and an email as minimum viable routing.

## Log retention

- Cockpit Loki retention is tier-dependent. Check the current Cockpit plan; default free tier is short (check Scaleway docs for current figures — this changes across plan versions).
- For regulated workloads requiring 90-day or longer log retention: export logs to Scaleway Object Storage via a Fluent Bit or Vector sidecar alongside Cockpit push. Object Storage Glacier class for logs older than 30 days.
- Never treat Cockpit as your only log store for forensic or compliance purposes. Always have a cold-storage export path.
- Set explicit retention policies per log stream in Cockpit; do not let ingestion grow unboundedly.

## Cost Manager

Scaleway Cost Manager (in the console under Billing) provides:

- **Project-level cost breakdown**: see per-Project spend for the current and past months.
- **Resource-type breakdown**: how much is spent on Instances, Object Storage, Managed Database, etc.
- **Invoice download**: monthly invoices as PDF + CSV.

Limitations (as of 2026-Q2):
- Cost Manager does not support custom cost allocation tags like AWS Cost Explorer. Resource tagging is available but filtering in Cost Manager is limited — use the console breakdown and plan naming conventions to track costs by team or service.
- No anomaly detection built in. Implement budget alerts via billing thresholds (see below).

## Budget alerts and billing

- Set billing threshold alerts in the Scaleway console (Organization → Billing → Alerts) for 75%, 90%, and 100% of expected monthly spend.
- Alerts route to the Organization owner's email. Also configure a team inbox or Slack channel via the webhook alert type.
- For finer cost allocation: adopt a strict naming convention (`<env>-<team>-<service>`) for Projects and resources. Cost Manager's project breakdown becomes your cost allocation tool.
- Reserved resources (Elastic Metal with commitments, long-term Instance contracts): factor committed costs into the budget baseline before setting alert thresholds.

## Resource tags

- Scaleway supports resource tags on most Instances, Serverless Containers, Kapsule clusters, and Object Storage buckets.
- Use tags for: environment (`prod`, `staging`, `dev`), team (`platform`, `backend`, `data`), service name.
- Tags are filterable in the Scaleway console resource list but have limited integration with Cost Manager aggregation — use Project separation as the primary cost boundary.
- Apply tags in IaC via the `tags` attribute on each Terraform resource; enforce in code review.

## Cost optimization levers

| Lever | Where it pays |
| --- | --- |
| Serverless scale-to-zero | Serverless Containers / Jobs / Functions at $0 during idle periods. |
| Kapsule node pool right-sizing | Overprovisioned node pools are the largest silent cost on Kubernetes. Review actual usage monthly. |
| Object Storage Glacier tiering | Old backups and logs in Standard class are expensive. Lifecycle-tier at 90 days. |
| Elastic Metal on-demand vs commit | Hourly on-demand for variable workloads; ask Scaleway about commitment pricing for stable > 3-month workloads. |
| Private Network traffic | Cross-resource traffic in the same region via Private Networks is free. Routing through the internet or Public Gateway processes egress costs. |
| GPU Instances shutdown schedule | GPU time is expensive. Stop between training runs. Use Serverless Jobs for infrequent GPU batch. |
| Snapshot audit | Block Storage snapshots and Object Storage versioned objects accumulate. Purge quarterly. |
| Reserved IP release | Unattached flexible IPs are billed. Release when no longer needed. |

### Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Infinite Cockpit log retention | Plan costs rise; Loki ingestion isn't free. Bound retention and export to cold storage. |
| Alerts that fire weekly with no action | Alert fatigue; real incidents get missed. Fix or silence the underlying issue. |
| GPU Instance left running between training jobs | Expensive idle GPU time. Automate shutdown. |
| No billing alerts until the invoice arrives | Runaway workload discovered too late. Set 75% threshold. |
| All workloads in one Project with no cost separation | Impossible to attribute cost spikes to a team or service. Use Projects as cost boundaries. |
| Cockpit as the only log store | Short retention + no export = lost forensic evidence. Always export to Object Storage. |

## Observability defaults — every service

- Structured JSON logs with `request_id`, `service`, `environment` fields; ship to Cockpit Loki.
- Prometheus metrics exposed on `/metrics` or pushed via OTLP; scraped or pushed to Cockpit.
- At least one Cockpit alert per service tied to user-visible pain: error rate, latency p99, backend health.
- Cockpit dashboard created and committed to git as JSON on day one — not after the first incident.
- Runbook linked in every alert annotation.

## IaC hints

- Terraform `scaleway/scaleway` ≥ 2.45: `scaleway_cockpit`, `scaleway_cockpit_token`, `scaleway_cockpit_grafana_user` for managing Cockpit resources.
- Push tokens (`scaleway_cockpit_token`) are scoped per Project. Manage in IaC so they are auditable and rotatable.
- For Kapsule: install `kube-prometheus-stack` via Helm Chart; configure remote write to Cockpit's Prometheus endpoint for application-level metrics.
- Alert rule templates: export from Cockpit Grafana as JSON and commit to git. Apply via Terraform Grafana provider or manual import.
- Cost Manager API: available via Scaleway API for programmatic billing queries — useful for a monthly cost report script.

## Verification checklist

- [ ] Every service emits structured JSON logs with a request_id; logs flowing to Cockpit Loki.
- [ ] Prometheus metrics or OTLP metrics flowing to Cockpit per service.
- [ ] Log retention bounded; export to Object Storage for regulated or forensic data.
- [ ] At least one Cockpit alert per service tied to user-visible pain, with a linked runbook.
- [ ] Alert contact points configured: at least email + Slack (or PagerDuty) webhook.
- [ ] Billing threshold alerts at 75% and 100% of expected monthly spend.
- [ ] Tags applied to all resources in IaC; naming convention documented.
- [ ] Cockpit dashboards versioned in git; not relying on managed Scaleway dashboards for custom data.
- [ ] Cost review scheduled monthly; savings levers reviewed quarterly.
