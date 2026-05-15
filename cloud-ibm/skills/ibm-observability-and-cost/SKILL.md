---
name: ibm-observability-and-cost
description: Wire up or audit IBM Cloud observability and cost — IBM Cloud Monitoring (Sysdig), IBM Cloud Logs (LogDNA), Activity Tracker, Cost Estimator, IBM Cloud Subscriptions (Committed Use), Showback / Chargeback patterns, Resource Group tagging. Use when adding telemetry to a new service, building dashboards, setting alerts, or analyzing cloud spend.
---

# IBM Cloud Observability and Cost

## When to use

- Setting up logs, metrics, and traces for a new IBM Cloud service or workload.
- Building SLO dashboards or wiring alerts to an on-call channel.
- Diagnosing a latency, error, or cost regression.
- Evaluating IBM Cloud Subscriptions vs on-demand for a stable workload.
- Sizing a quarterly IBM Cloud cost review or implementing Showback / Chargeback.

## Observability pillars

| Pillar | Service |
| --- | --- |
| Metrics | IBM Cloud Monitoring (powered by Sysdig SaaS) |
| Logs | IBM Cloud Logs (powered by LogDNA, re-branded IBM Cloud Logs) |
| Audit / Management events | Activity Tracker (IBM Cloud platform events, not application logs) |
| Synthetics / Uptime | IBM Cloud Monitoring — Sysdig Synthetic Monitoring |
| Distributed traces | IBM Cloud Monitoring — Sysdig Distributed Tracing (Jaeger-compatible) or OpenTelemetry → Sysdig |
| Application performance | IBM Cloud Monitoring — Sysdig APM |

## IBM Cloud Monitoring (Sysdig)

IBM Cloud Monitoring is the platform metric service — all IBM Cloud platform services (VPC VSIs, IKS, ROKS, Code Engine, ICD, COS) emit platform metrics to a Monitoring instance in the same region automatically when the instance is provisioned.

### Defaults

- One IBM Cloud Monitoring instance per region per account. All IBM Cloud services in that region emit platform metrics to it automatically.
- Enable platform metrics: `ibmcloud ob monitoring enable --cluster <cluster_id>` for IKS/ROKS. For VPC services it is automatic when a Monitoring instance exists in the region.
- Agent deployment: deploy the Sysdig agent as a DaemonSet on IKS/ROKS for host-level and pod-level metrics. Use the IBM-provided Helm chart for consistent defaults.
- Retention: Monitoring retains metrics for 15 months by default. Define dashboards and alerts before you need them — waiting until an incident to build dashboards is painful.
- Custom metrics: use `statsd` or `Prometheus` exporters scraping your application's `/metrics` endpoint. Sysdig's Prometheus-compatible endpoint ingests custom app metrics.
- Structured tags: apply resource tags (`env:prod`, `team:payments`, `service:api-gateway`) to all IBM Cloud resources — these tag dimensions are available in Monitoring for dashboard filtering.

### Alerts

Write alerts like contracts:

- **Signal**: which metric, at which percentile, over which window (e.g., `net.http.request.time.avg > 500 ms over 5 min`).
- **Threshold**: the number that means "human attention needed."
- **Channel**: IBM Cloud Monitoring notification channel — PagerDuty, Slack, email, webhook.
- **Runbook**: linked in the alert body — the first thing the responder reads.

Avoid: CPU-only alerts for I/O-bound workloads; floating thresholds with no documented rationale.

Required alerts per service:

- Error rate / 5xx rate above baseline.
- p99 latency above SLO threshold.
- Pod restart count (IKS/ROKS) or Code Engine revision error count.
- Disk usage > 80% for databases and persistent volumes.
- Certificate expiry < 30 days.

### Dashboards

- One dashboard per service, one per environment.
- Top row: SLI metrics (availability, error rate, p99 latency). Middle: dependencies (upstream call latency, downstream error rate). Bottom: resource utilization (CPU, memory, disk, connections).
- Use dashboard templates: IBM Cloud provides pre-built dashboards for IKS, ICD, COS, Code Engine — enable and customize rather than building from scratch.
- Dashboard-as-code: Sysdig supports JSON export of dashboards — store in version control and apply via Terraform (`ibm_resource_instance` + Monitoring API).

## IBM Cloud Logs (LogDNA-based)

IBM Cloud Logs is the platform log service — applications and platform services ship logs to a regional IBM Cloud Logs instance.

### Defaults

- One IBM Cloud Logs instance per region per account for production. Use separate instances for dev/stage if log volume or retention requirements differ.
- Platform log routing: enable automatic log routing for IBM Cloud platform services (IKS, ROKS, Code Engine, VPC VSIs via logging agent) using `ibmcloud ob logging enable`.
- Agent deployment: deploy the LogDNA agent as a DaemonSet on IKS/ROKS clusters. For VPC VSIs, install the logging agent binary; it tails configured log paths.
- Structured JSON logs: always emit structured JSON from application code. Flat string logs are unsearchable at scale. Mandatory fields: `timestamp`, `level`, `message`, `request_id`, `service`, `env`.
- Log levels: `DEBUG` off in production by default; `INFO` for normal operations; `WARN` for recoverable anomalies; `ERROR` for failures.
- Retention tiers: IBM Cloud Logs offers tiered retention — hot (searchable, expensive) and archive (COS export, cheap). Configure hot retention to 7–30 days; archive everything to COS with lifecycle rules.
- Exclusion rules: exclude health check traffic, high-volume debug logs, and low-value `GET /health` logs from hot storage to control costs. Log everything to archive.

### Log search and alerting

- Views: create saved Views for common searches (errors in prod, payment service logs, 5xx from load balancer).
- Alerts: IBM Cloud Logs supports presence/absence alerts (e.g., alert when "FATAL" appears; alert when no heartbeat log in 5 minutes).
- Line graph channels: route critical log alerts to PagerDuty or Slack via webhook.

## Activity Tracker

Activity Tracker records IBM Cloud management-plane events (API calls that create, modify, or delete resources). It is the control-plane audit log — not an application log service.

- Every IBM Cloud service generates Activity Tracker events for mutating actions.
- Route events to: COS bucket for long-term compliance storage; IBM Cloud Logs for searchable 90-day window.
- Key event categories to search and alert on: IAM changes, key management (Key Protect / HPCS key state changes), VPC Security Group modifications, instance creations/deletions, login failures.
- WORM storage: configure COS Object Lock on the Activity Tracker archive bucket — prevents tampering with the audit trail.
- Retention: 1 year minimum; 7 years for financial services / FFIEC.
- Log integrity: Activity Tracker events include a verification hash — validate with `ibmcloud at event` or the IBM Cloud SCC compliance assessment.

## Cost Estimator and Subscriptions

### IBM Cloud Cost Estimator

- Use the IBM Cloud Cost Estimator (`cloud.ibm.com/estimator`) to model costs before provisioning.
- Export estimates as CSV for FinOps reviews.
- The Estimator reflects on-demand pricing — apply Subscription discounts separately to get realistic committed-use cost.

### IBM Cloud Subscriptions (Committed Use)

IBM Cloud Subscriptions (formerly Committed Use Discounts) provide reduced rates in exchange for committed monthly spend.

- Available for: VPC compute, managed Kubernetes (IKS/ROKS), IBM Cloud Databases, Code Engine, Cloud Object Storage.
- Discount levels: typically 10–30% depending on committed amount and term (1-year vs 3-year).
- Break-even: calculate at roughly 60–70% of committed amount sustained. If you're consistently using 70%+ of on-demand spend, a Subscription saves money.
- Subscription credits roll over within the commitment period; unused credits at term end are forfeited.
- Enterprise accounts: subscriptions can apply at the enterprise account level and cascade across child accounts — useful for org-wide commitment.

### Showback and Chargeback

IBM Cloud doesn't provide native Showback / Chargeback — implement it via resource tagging + usage reports + an external tool or custom pipeline.

#### Tagging strategy

Tag every IBM Cloud resource at provisioning time in IaC:

| Tag key | Example values | Purpose |
| --- | --- | --- |
| `env` | `prod`, `stage`, `dev` | Environment cost split |
| `team` | `platform`, `payments`, `identity` | Team attribution |
| `service` | `api-gateway`, `order-svc` | Service-level cost |
| `cost-center` | `CC-1234` | Finance allocation code |
| `owner` | `jane@example.com` | FinOps contact |

- Enforce tags via IBM Cloud SCC custom rules or pre-commit IaC linting (`tflint` rules for required tags).

#### Cost reporting pipeline

1. Export IBM Cloud usage data via the Billing API (`ibmcloud billing account-usage --json`).
2. Group by tag dimensions.
3. Load into a BI tool (Looker, Tableau, Power BI, or a COS + Athena equivalent using IBM SQL Query).
4. Produce monthly Showback reports per team; escalate to Chargeback via internal billing when maturity warrants.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Skipping IBM Cloud Monitoring agent on IKS/ROKS | Platform metrics arrive; pod-level and host-level metrics don't. Outages are opaque. |
| Hot retention for all logs (no archive) | IBM Cloud Logs costs escalate steeply without tiered retention. Archive everything; hot-retain only what you query. |
| No structured logs | Log search becomes grep on unstructured strings. Impossible at scale. Enforce JSON from day one. |
| CPU-only alerts on I/O-bound workloads | Alert fires late or not at all. Use request rate, queue depth, or I/O wait. |
| IBM Cloud Subscriptions bought before usage stabilizes | Stranded commitment. Wait for 3+ months of stable spend before committing. |
| Resources with no tags | Cost reports are meaningless without attribution. Tags mandatory at provisioning. |
| Activity Tracker events not shipped to WORM storage | Audit trail can be deleted. Object Lock on the COS destination. |
| Infinite log hot retention | 15 months of debug logs at hot tier pricing is expensive. Tier aggressively. |

## Observability + cost together

Telemetry investment pays back in shorter incident resolution and fewer repeat incidents. Common false economies:

- Turning off IBM Cloud Monitoring to save Sysdig costs → hours of manual investigation during the next outage.
- Hot-retaining logs for 90 days when 7 days is enough → bloated log bill for data nobody queries beyond day 3.
- No structured logs → every log investigation requires a dedicated engineer and takes 3× longer.

Spend on telemetry; cut on over-retained cold data.

## IaC hints

- Terraform resources: `ibm_resource_instance` (IBM Cloud Monitoring, IBM Cloud Logs, Activity Tracker), `ibm_ob_monitoring` (IKS monitoring integration), `ibm_ob_logging` (IKS logging integration).
- IBM Cloud Monitoring: `ibm_monitor_alert` for alert rules; Sysdig REST API for dashboards and notification channels (no Terraform native support — use a provisioner or external script).
- IBM Cloud Logs: `ibm_resource_key` for service credentials; configure log routing via `ibmcloud ob logging enable` in bootstrap scripts.
- Activity Tracker: route to COS via `ibm_atracker_route` and `ibm_atracker_target` resources.
- Resource tags: use `ibm_resource_tag` resource or the `tags` attribute on each resource — tags cannot be applied after the fact to some IBM Cloud resources.
- Subscription discounts: no Terraform API — managed via the IBM Cloud console or Billing API. Model expected spend in a cost spreadsheet before IaC provisioning.

## Verification checklist

- [ ] IBM Cloud Monitoring instance in every active region; platform metrics enabled.
- [ ] Sysdig agent deployed on all IKS/ROKS clusters; LogDNA agent on VPC VSIs.
- [ ] IBM Cloud Logs instance per region; archive to COS with lifecycle rules (hot 7–30 d → COS archive).
- [ ] Activity Tracker events shipping to a WORM-protected COS bucket.
- [ ] Structured JSON logs emitted from all application services with `request_id` field.
- [ ] At least one alert per service tied to user-visible pain (error rate, p99 latency); runbook linked.
- [ ] Resource tagging policy enforced at provisioning time via IaC; at least `env`, `team`, `service` tags.
- [ ] IBM Cloud Subscriptions evaluated against 3+ months of usage data before commitment.
- [ ] Monthly cost report per team using tagged usage data; FinOps owner assigned.
- [ ] Dashboards for top services in version control; reviewed before production launch.
