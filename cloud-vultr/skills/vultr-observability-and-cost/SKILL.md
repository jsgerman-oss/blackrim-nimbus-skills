---
name: vultr-observability-and-cost
description: Wire up or audit Vultr observability and cost — built-in metrics (CPU / memory / network / disk), Alerts, third-party observability via standard agents (Prometheus node exporter, Datadog agent, Grafana Alloy), billing model (hourly with monthly cap), bandwidth pool model and per-TB overage, and free-transfer differences across regions. Use when adding telemetry, wiring alerts, diagnosing a performance regression, or reviewing a Vultr bill.
---

# Vultr Observability and Cost

## When to use

- Setting up metrics and alerting for a new Vultr workload.
- Integrating a third-party observability platform (Datadog, Grafana, Prometheus) with Vultr instances.
- Diagnosing a latency, error, or cost regression.
- Reviewing the Vultr billing model before committing to a workload scale.
- Auditing bandwidth consumption and overage exposure.
- Building a dashboard for a Vultr-hosted service.

## Vultr's observability tier — what's built in

Vultr provides lightweight built-in metrics for Cloud Compute and Bare Metal instances:

- **CPU utilization** (percentage, 5-minute average).
- **Bandwidth in/out** (bytes per second, 1-hour buckets).
- **Disk read/write** (IOPS and throughput, 1-hour buckets).
- **Memory** (percentage used) — only available on instances running Vultr's guest agent or a cloud-init compatible OS.

These metrics are accessible via:
- Vultr control panel (graphical, last 24 h / 7 d / 30 d views).
- Vultr API: `GET /v2/instances/{instance-id}/bandwidth` and related endpoints.
- `vultr-cli instance bandwidth --id <id>`.

**Vultr does not provide:** managed log aggregation, managed distributed tracing, managed APM, alerting integrations (PagerDuty, OpsGenie) beyond email, or a query language for metrics.

For production observability, built-in metrics are a baseline signal only. Production workloads require a third-party agent.

## Third-party observability — recommended approach

### Prometheus + Grafana (self-hosted or Grafana Cloud)

Best fit for VKE clusters and multi-instance fleets.

- Deploy `prometheus/node_exporter` on each Cloud Compute / Bare Metal instance (systemd service, or as a DaemonSet in VKE).
- For VKE: deploy the `kube-prometheus-stack` Helm chart — includes Prometheus, Alertmanager, Grafana, and node + pod metric collection.
- Ship metrics to Grafana Cloud (free tier: 10,000 series) or a self-hosted Prometheus instance on Vultr Block Storage.
- **Loki** for log aggregation (via `promtail` or `grafana-alloy` agent shipping `/var/log`).
- **Tempo** for traces (wire OpenTelemetry SDKs to Tempo ingest endpoint).

### Datadog

Best fit for teams already using Datadog.

- Install the Datadog agent on each instance (DEB/RPM package or Docker/K8s DaemonSet).
- API key stored in a secrets manager; injected at instance provisioning via cloud-init.
- Enable log collection: `logs_enabled: true` in `datadog.yaml`; configure log paths for your application.
- Use Datadog NPM (Network Performance Monitoring) for VPC-level traffic visibility that Vultr does not expose natively.
- Cost: Datadog agent + infrastructure metrics are per-host. Factor Datadog cost into the workload budget alongside Vultr instance cost.

### OpenTelemetry (OTEL)

For application-layer traces and metrics, OTEL is the right abstraction regardless of backend.

- Instrument application code with OTEL SDKs (Python, Go, Node.js, Java — all have stable SDKs).
- Deploy an OTEL Collector on each instance (or as a VKE DaemonSet), configured to export to your backend (Grafana Tempo, Datadog, Honeycomb, etc.).
- Propagate `traceparent` headers across service calls to correlate traces end-to-end.

## Alerts

Vultr supports alerts via the Alerts feature in the control panel:

- **Supported triggers:** CPU % above threshold, bandwidth (in or out) above threshold, disk I/O above threshold.
- **Notification channel:** Email only (as of 2026-05). No native Slack/PagerDuty/OpsGenie webhooks from Vultr Alerts.
- **Recommended alerts to wire:**
  - CPU > 80% sustained for 5 minutes on any production instance.
  - Bandwidth out > 80% of the plan's monthly cap (to catch overage before it hits).
  - Disk I/O saturation for Managed Database instances.

For webhook-based alerting (Slack, PagerDuty), use your third-party observability platform's alerting (Grafana Alertmanager, Datadog Monitors, Prometheus Alertmanager) rather than Vultr-native Alerts.

## Billing model

Understanding Vultr's billing model prevents surprise invoices.

### Hourly with monthly cap

- Every Cloud Compute and Bare Metal instance bills per hour.
- There is a monthly maximum — once you have run an instance for its "monthly" equivalent of hours, additional hours in that billing period are free.
- **Example:** A $24/mo instance at $0.036/hr reaches its monthly cap at ~667 hours (≈ 28 days). Any remaining hours in that calendar month are billed at $0. But the hour meter resets at the start of each calendar month.
- **Implication:** Stopping an instance does not stop billing. Vultr bills for the reserved capacity, not for runtime state. To stop billing, you must **destroy** the instance. (Backups and snapshots persist after destruction and are billed separately.)

### Partial-month instance lifecycle

- A new instance started mid-month bills from that hour until the monthly cap.
- A destroyed instance bills until the hour it is destroyed.
- Plan this for short-lived workloads: a GPU instance provisioned at 3 AM and destroyed at 5 AM costs 2 hours × GPU hourly rate.

### Bandwidth pool model

- Cloud Compute instances share a per-account monthly bandwidth pool. The pool size is the sum of each instance's included bandwidth allotment.
- **Example:** An account with 10 × $24/mo instances (each with 2 TB included) has a pool of 20 TB/month.
- Bandwidth usage is measured as outbound egress from instances. Inbound (ingress) is not counted.
- Pool usage is visible via the Vultr billing dashboard and `vultr-cli billing bandwidth`.
- **Overage:** Once the pool is exhausted, additional egress is billed per GB (rates vary by region; verify on Vultr's pricing page). Overage charges can be significant for media-heavy or high-traffic workloads.

### Managed Databases billing

- Managed Databases bill monthly (not hourly). The monthly rate applies regardless of how much of the month the database has been running.
- Starting a new database mid-month incurs a prorated charge for the first month.
- Managed Database bandwidth does not consume from the Cloud Compute bandwidth pool — database internal network traffic is free; egress from the database to external clients is billed separately.

### Object Storage billing

- Charged per GB of storage per month, plus egress per GB (with a free outbound allotment per cluster).
- Verify current egress pricing for the specific region — pricing differs across Vultr regions and is lower in some than others.

### Bandwidth across regions

- Free transfer differences: bandwidth allotments per instance plan vary by region. For example, some regions have higher per-plan bandwidth inclusions than others. Review the plan details for your specific target region before designing a bandwidth-sensitive architecture.
- Cross-region traffic: traffic between Vultr instances in different regions goes over the public internet and counts as egress for the source instance. There is no private cross-region Vultr backbone for customer instances.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Relying on Vultr built-in metrics alone for production | No log aggregation, no traces, no custom application metrics. You are flying blind on anything above infrastructure level. |
| Vultr Alerts via email to a personal inbox | Alert emails get missed, buried in spam, or seen only after an incident. Wire to a shared channel via a third-party platform. |
| Not monitoring bandwidth pool consumption | Overage charges appear on the invoice at the end of the month with no early warning. Set an Alert at 80% of pool capacity. |
| Stopping (not destroying) instances to "pause billing" | Stopped instances still bill. Only destroying an instance stops compute charges. |
| GPU instance left running after batch job completes | GPU plans cost hundreds to thousands per month. Auto-destroy via a job-completion hook or scheduled Terraform destroy. |
| No log retention for security-relevant events | Auth log, application error log, and Managed Database slow query log need to be shipped and retained for 90+ days for any incident forensics. |
| Building dashboards manually in the Vultr control panel | Control panel dashboards do not survive account changes and cannot be version-controlled. Build dashboards in Grafana/Datadog, stored as IaC (Grafana dashboard JSON, Terraform datadog_dashboard). |

## Observability defaults — every production workload

- **Infrastructure metrics:** Deploy `node_exporter` (or Datadog agent) on every Cloud Compute / Bare Metal instance. VKE: `kube-prometheus-stack` Helm chart.
- **Application metrics:** OTEL SDK instrumented; export to Prometheus (or Datadog / Grafana Cloud). Custom business metrics alongside standard RED metrics (Requests, Errors, Duration).
- **Logs:** Ship all application logs and OS auth logs to a centralized log store (Loki, Datadog Logs, OpenSearch). Retention: 90 days minimum for security-relevant logs; 30 days for general app logs.
- **Traces:** OTEL traces from application code; export to Grafana Tempo or Datadog APM. Propagate `traceparent` headers.
- **Alerts (minimum viable):**
  - CPU > 80% for 5 minutes → page (production instances).
  - Bandwidth pool > 80% consumed → warning (billing alert).
  - Managed Database storage > 75% full → warning.
  - Disk I/O saturation on any production instance → warning.
  - No log ingest in 30 minutes from a production instance → alert (agent down).
- **Dashboard:** One Grafana dashboard per service/tier with RED metrics at the top and infrastructure metrics below.

## Cost considerations — optimization levers

| Lever | Where it pays |
| --- | --- |
| Right-size instance plans after 2 weeks of metrics | Over-provisioned instances are common. Check CPU utilization; a 4-vCPU instance averaging 10% CPU is a candidate for a 2-vCPU plan. |
| Destroy dev/test instances outside working hours | A $24/mo instance that runs only 8 hours/day × 5 days/week costs ~$7/mo. Use Terraform + a cron job or GitHub Actions scheduled workflow to destroy and recreate. |
| Monitor bandwidth pool; optimize large egress paths | Object Storage egress to the internet is cheaper than instance egress in most regions. Serve large files from Object Storage, not from instance-attached disks. |
| GPU batch: provision → run → destroy | Manual provisioning of GPU for scheduled jobs eliminates idle GPU cost. |
| Managed Database plan review | Managed Database plans have large RAM/CPU increments. Use the smallest plan where Managed DB metrics show < 60% utilization. |
| Use VPC-internal IPs for intra-service traffic | Internal VPC traffic is free. Avoid routing inter-service calls through public IPs, which consume bandwidth pool. |
| Review overage costs by region | If your workload is egress-heavy, compare bandwidth pricing per GB across Vultr regions — pricing varies and can affect the effective cost of a region. |

## IaC hints

- Vultr Alerts: `vultr_alert` resource (if available in your provider version; verify in the `vultr/vultr` provider changelog ≥ 2.21).
- For Prometheus + Grafana on VKE: use the `helm_release` Terraform resource to deploy `kube-prometheus-stack` from the `prometheus-community` Helm chart repository.
- Datadog agent on instances: deliver the agent install script via `vultr_startup_script`, with the API key injected from a Terraform `sensitive` variable (backed by a secrets manager lookup).
- Grafana dashboards as code: commit dashboard JSON files to a `dashboards/` directory; load via `grafana_dashboard` Terraform resource or Grafana provisioning.

## Verification checklist

- [ ] Infrastructure metrics agent deployed on every production instance (node_exporter or Datadog agent).
- [ ] Application instrumented with OTEL SDK; traces exported to a backend.
- [ ] Logs shipped to centralized store with 90-day retention for auth/security logs.
- [ ] Alerts wired for CPU, bandwidth pool, Managed DB storage, and agent-down condition — all routed to a shared team channel.
- [ ] Dashboard exists for each production service with RED metrics + infrastructure.
- [ ] Bandwidth pool consumption visible and monitored; overage risk assessed for the workload's traffic pattern.
- [ ] GPU instances have auto-destroy automation for batch workloads.
- [ ] Instance plan sizing reviewed against observed utilization after first 2 weeks in production.
- [ ] Dev/test instance shutdown automation in place.
- [ ] Billing alerts set in Vultr control panel for unexpected spend spikes.
