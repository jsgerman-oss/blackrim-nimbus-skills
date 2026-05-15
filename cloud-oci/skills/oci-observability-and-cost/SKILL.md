---
name: oci-observability-and-cost
description: Wire up or audit OCI observability and cost — Monitoring (metrics, alarms), Logging (custom, service, audit), Logging Analytics, APM, Stack Monitoring, Cost Analysis, Budgets, Tag Defaults, Cost-Tracking Tags. Use when adding telemetry, tracing a regression, building dashboards, or analyzing a bill.
---

# OCI Observability and Cost

## When to use

- Wiring metrics, logs, and traces for a new OCI workload.
- Building an alarm or dashboard for an operational SLO.
- Diagnosing a latency, error, or cost regression.
- Configuring a budget or spending alert.
- Setting up Tag Defaults and Cost-Tracking Tags for per-service cost attribution.
- Investigating an anomalous spend line in the Cost Analysis report.

## Observability pillars

| Pillar | OCI Service |
| --- | --- |
| Metrics | OCI Monitoring (service metrics) + custom namespace metrics via Monitoring API |
| Logs | OCI Logging (service logs, custom logs via agent) + Logging Analytics for long-term queries |
| Traces | OCI APM (Application Performance Monitoring) — distributed tracing, span data, synthetics |
| Synthetics | OCI APM Synthetics — scripted browser and REST monitors |
| Infrastructure | Stack Monitoring — topology-aware monitoring of full stacks (compute, DB, middleware) |

## Metrics and alarms

- OCI emits service metrics for every managed resource (Compute, Load Balancer, Autonomous Database, Object Storage, OKE, Functions) automatically — no agent required for the service layer.
- Emit **custom metrics** from applications using the OCI Monitoring Ingest API. Use a metric namespace per application (`<team>_<service>_metrics`). Custom metrics carry dimensions (key-value labels) for slicing alarms by region, compartment, or version.
- Alarm definition best practice:
  - **Signal:** the metric name, statistic (max, p99, sum), and evaluation window.
  - **Threshold:** the value that requires human attention, derived from your SLO — not a round number you guessed.
  - **Suppression:** set a suppression window around planned maintenance.
  - **Notification:** wire to a Notification topic that reaches the on-call channel. A topic with no subscriptions is a silent alarm.
- Use composite alarm logic (expression-based alarms) to combine related signals — alert on `error_rate > 1%` AND `request_rate > 100/s` together, not on error count alone.
- Alarm severity: Critical (page now), Warning (page during business hours), Informational (log only).

## Logging

- **Service logs:** enable for every resource that supports them — Load Balancer access and error logs, VCN flow logs, Autonomous Database audit logs, WAF logs, Vault access logs. Service logs are pre-configured; you only need to select a log group and name.
- **Custom logs:** deploy the OCI Logging unified monitoring agent on Compute instances. Configure agent plugins to ship application log files (syslog, application-specific) to a log group in the same compartment.
- **Audit logs:** OCI generates tenancy-wide audit logs automatically. Ensure the audit log group retention is set to ≥ 365 days and the underlying Object Storage destination uses Archive tier for cost-efficient long-term storage.
- **Log group organization:** one log group per compartment per log category (access logs, error logs, audit logs). Avoid a single tenancy-wide log group — compartment-scoped log groups match your IAM boundary model.
- **Log retention:** set explicit retention on every log group. Default retention in OCI Logging is 30 days; for security and compliance, extend security-relevant logs to 90–365 days. Ship older logs to Object Storage Archive tier for cost-efficient long-term retention.

## Logging Analytics

- Use Logging Analytics for long-term log search, pattern analysis, and compliance reporting where OCI Logging's 30–365-day window is insufficient.
- Logging Analytics can ingest from OCI Logging, from on-premises sources via a log collector, and from third-party sources.
- Create a scheduled search query per compliance requirement (e.g., "all privileged access events in the last 90 days") — export results to a report Object Storage bucket.
- Parsers: OCI Logging Analytics includes built-in parsers for OCI service log formats, Oracle Database, and common OS log sources. Use them before writing a custom parser.

## APM — Application Performance Monitoring

- Enable APM for every customer-facing service that requires latency SLOs.
- Create one APM domain per environment (dev, staging, prod). APM domains collect spans, traces, and synthetic monitor results independently.
- Instrument applications using the OCI APM SDK (Java, Python, Node.js, .NET, Go) or the OpenTelemetry SDK (OCI APM accepts OTLP via the APM data collector endpoint). Prefer OpenTelemetry for new projects — it is vendor-neutral and portable.
- Trace every external call (DB, HTTP, queue) in addition to inbound requests. Propagate the trace context header across service boundaries.
- Synthetics: create at minimum one REST or scripted browser monitor per public endpoint. Configure a monitor to run every 5 minutes from the closest OCI region.
- Configure an alarm on APM synthetic monitor failures and on p99 trace duration regression.

## Stack Monitoring

- OCI Stack Monitoring discovers the full resource stack supporting an application: Compute instances, Autonomous Databases, Load Balancers, OKE clusters, middleware agents.
- Enable Stack Monitoring for any production application where manual topology tracking is error-prone.
- Stack Monitoring integrates with OCI Monitoring alarms — a Stack Monitoring discovery resource can act as the target for a composite alarm that represents the entire application's health.

## Cost — the operational playbook

### Visibility

- **Cost Analysis:** available in the OCI Console and via API. Filter by compartment, service, tag, or resource to attribute costs. Default view is monthly; switch to daily for regression isolation.
- **Usage Reports:** automatically generated in an Object Storage bucket (`reports.oci.oraclecloud.com`). The detailed usage CSV is the equivalent of AWS CUR — import into your BI tool or query with Athena or a similar service.
- **Cost-Tracking Tags:** designated tag namespace and key marked as a cost-tracking tag in OCI Tag Defaults. Tags that appear on resources flow through to Cost Analysis automatically. Set at least `Environment`, `Service`, `Team`, and `CostCenter` as cost-tracking tags.
- **Tag Defaults:** configure Tag Defaults at the compartment level so every new resource inherits mandatory tags automatically. Without Tag Defaults, untagged resources appear as unattributed cost.
- **Budgets:** create a budget per compartment (or per tag value) with alert thresholds at 80% and 100% of the projected monthly spend. Wire budget alerts to a Notification topic.

### Optimization levers

| Lever | Where it pays |
| --- | --- |
| A1 Flex (Ampere ARM) shapes | ~30% cheaper per OCPU than x86 Flex for ARM-compatible workloads. Default to A1 first; fall back on binary incompatibility. |
| Preemptible instances | Up to 50% discount for stateless, interruptible workloads. OCI terminates with 30-second notice. |
| Autonomous Database auto-pause | Serverless ATP/ADW can be configured to pause after N minutes of inactivity — no OCPU charge when paused. |
| Object Storage tier transitions | Move cold objects to Infrequent Access (31-day min) and Archive (90-day min) via lifecycle rules. |
| Flex shape right-sizing | Audit observed CPU and memory utilization; reduce OCPU count or memory independently without reshaping. |
| Stop dev/staging resources off-hours | Use OCI Autoscaling schedules or DevOps pipeline triggers to stop non-production Compute instances outside working hours. |
| Reserved capacity | Commit to 1-year or 3-year reserved Compute capacity for steady-state workloads — up to 60% discount. |
| Service Gateway | Eliminates NAT Gateway data-processing charges for traffic to OCI services — zero-cost path. |

### Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Indefinite log retention in OCI Logging | OCI Logging charges per GB stored; logs that are never queried after 30 days should be in Object Storage Archive. |
| Alarm with no Notification subscriber | A valid alarm rule with no subscription fires silently. Always verify the Notification topic has at least one subscription. |
| Cost Analysis without Tag Defaults | Untagged resources appear as a single unattributed line. Tag Defaults at compartment creation prevent this. |
| Autonomous Database never paused in dev | OCPU billing is continuous unless paused. Always configure auto-pause for dev/test ATP/ADW. |
| APM domain in production collecting 100% of traces at high traffic | Trace storage is per-span charged. Use sampling (1–5% head-based for high-volume paths, 100% for error paths). |
| Preemptible instances for stateful workloads | Termination at 30-second notice corrupts in-flight writes. Use preemptible only for stateless / batch. |
| Reserved capacity commitment before usage stabilizes | Stranded commitment for capacity you don't consume. Wait until 3+ months of stable usage data. |

## IaC hints

- Terraform: `oci_monitoring_alarm`, `oci_ons_notification_topic`, `oci_ons_subscription`, `oci_logging_log_group`, `oci_logging_log`, `oci_apm_apm_domain`, `oci_budget_budget`, `oci_budget_alert_rule`, `oci_identity_tag`, `oci_identity_tag_default`.
- Manage Tag Defaults in a shared `tagging` Terraform workspace that runs before any workload stack — tags must exist before resources that reference them.
- Declare alarms for every managed resource in the same Terraform workspace as the resource itself — alarms that drift from the resource they monitor are as bad as no alarms.
- Notification topics are shared across an environment — define them once in the platform stack and reference by OCID from workload stacks.

## Verification checklist

- [ ] Every production service emits at minimum one alarm tied to a user-visible SLO signal (error rate, latency, availability).
- [ ] All alarms route to a Notification topic with at least one active subscription.
- [ ] Service logs enabled for every production resource that supports them.
- [ ] Log retention explicitly set on every log group; security logs ≥ 90 days.
- [ ] APM domain active for customer-facing services; at least one synthetic monitor per public endpoint.
- [ ] Cost-Tracking Tags defined; Tag Defaults applied at compartment level for `Environment`, `Service`, `Team`.
- [ ] Budgets with 80% and 100% thresholds in place for every top-level environment compartment.
- [ ] Cost Analysis reviewed monthly; unattributed cost lines investigated and tagged.
- [ ] Autonomous Database auto-pause configured for all non-production instances.
- [ ] Stack Monitoring enabled for complex multi-tier production applications.
