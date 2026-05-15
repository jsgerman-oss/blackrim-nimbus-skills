---
name: tencent-observability-and-cost
description: Wire up or audit Tencent Cloud observability and cost — Cloud Monitor (metrics, alarms, dashboards), CLS (Cloud Log Service — collection, search, dashboards), APM, COC (Cloud Operations Center), Cost Manager (bills, budget, cost allocation tags), reservation and savings models. Use when adding telemetry, tracking a performance regression, or optimizing a bill.
---

# Tencent Observability and Cost

## When to use

- Setting up metrics, logs, and traces for a new service.
- Building a Cloud Monitor dashboard or wiring an alarm to an on-call channel.
- Diagnosing a latency, error-rate, or cost regression.
- Designing a savings strategy (reserved instances, savings plans, spot usage).
- Preparing a monthly or quarterly cloud cost review.

## Observability pillars

| Pillar | Tencent Cloud Service |
| --- | --- |
| Metrics | Cloud Monitor (CM) — built-in + custom metrics |
| Logs | CLS (Cloud Log Service) — ingestion, search, dashboards, alarms |
| Traces | APM (Application Performance Management) — distributed tracing, service map |
| Synthetics | Cloud Monitor synthetic monitoring (HTTP / ICMP probes) |
| Real User Monitoring | Not native — integrate third-party RUM (Datadog, Sentry) via CLS log forwarding |
| Operations Hub | COC (Cloud Operations Center) — unified operations, runbook automation, change management |

## Defaults — every service

- **Structured JSON logs** with a stable `request_id` field shared across the call chain.
- Cloud Monitor metrics on by default for Tencent-managed services. For custom application metrics, publish via the Cloud Monitor custom metrics API (`PutMonitorData`).
- **CLS log collection**: configure the CLS log agent (LogListener) on CVM instances; use the TKE log-collector DaemonSet for Kubernetes pods; SCF logs route to CLS automatically.
- APM tracing: enable on all user-facing services. Propagate the trace context (`X-B3-TraceId` or W3C `traceparent`) across service calls and into CLS log fields.
- **At least one alarm per service** tied to user-visible pain: error rate, p99 latency, queue message age, dead-letter count. Never alarm only on CPU.
- **Log retention**: 7 days in CLS for hot search; archive to COS for 90 days (security logs) or 365 days (audit logs). Default indefinite retention is an unbounded cost.

## Cloud Monitor (CM) alarms — write them like contracts

A well-specified alarm:

- **Signal**: which metric, at which statistic (max, avg, p99), over which evaluation window (1 min, 5 min).
- **Threshold**: the value that means "a human needs to look at this".
- **Action**: which notification group (WeCom robot, email group, SMS) or COC runbook.
- **Runbook link**: in the alarm description — first thing the responder reads.

Badly specified alarms: `CPU > 80%` with no context, floating thresholds, alarms that fire more than once a week without action. These cause alert fatigue and get disabled.

For compound signals, CM supports **composite alarms** (`AND` / `OR` over child alarms) to suppress noise — for example, alert on high error rate AND p99 latency above threshold simultaneously, not independently.

## CLS (Cloud Log Service)

- **Log topics**: one topic per service per environment. Set retention period explicitly (7 / 30 / 90 / 365 days). Topics with unset retention accumulate indefinitely.
- **Index configuration**: create field indexes on `request_id`, `level`, `service`, `region` — fields you filter and aggregate on. Full-text index is expensive for high-volume logs; use it selectively.
- **CLS dashboards**: build one per service with: error rate, latency percentiles, log volume, top error messages. Tie CLS dashboards to Cloud Monitor dashboards for a unified view.
- **CLS alarms**: trigger on log keyword count (e.g., `level=ERROR` count > 10 in 5 min) or on SQL aggregation results (e.g., p99 latency > 500 ms). These complement Cloud Monitor metric alarms.
- **CLS to COS archiving**: configure a COS delivery task on each topic for long-term archiving. COS is 10× cheaper than CLS for cold storage.
- **LogListener agent**: install on every CVM via the Tencent Cloud agent installer. Configure multi-line parsing for stack traces; JSON parsing for structured application logs.

## APM (Application Performance Management)

- Install the APM SDK for your language (Java, Go, Python, Node.js, PHP). The SDK auto-instruments framework calls and propagates trace context.
- **Service map**: APM generates a topology map from span data. Review it after onboarding — unexpected upstream / downstream connections often surface here.
- Sampling: head-based 10% for high-traffic services; tail-based (error + latency sampling) via the APM agent to capture 100% of anomalous traces without storing all traces.
- Annotations: add `user_id`, `tenant_id`, `order_id` as span tags for high-cardinality filtering in the APM trace search.
- **Span every external call**: database queries, HTTP calls, cache reads, queue produces. Not just inbound request handlers.

## COC (Cloud Operations Center)

- COC is Tencent's unified operations hub: incidents, change management, runbook automation, and synthetic monitoring in one console.
- **Incident management**: route Cloud Monitor alarms to COC incident timelines. Configure escalation policies (L1 → L2 → L3) with timed escalation.
- **Runbook automation**: define runbook scripts (shell, Python) that COC can execute on CVM instances or TKE pods in response to an alarm. Use for auto-remediation of well-understood failure modes (restart a service, clear a disk, flush a cache).
- **Change management**: use COC change records for IaC applies, database schema migrations, and configuration deploys. Link change records to alarm timelines to correlate deployment-to-incident.

## Cost Manager

- **Bills**: view by resource, by product, by project, by tag. Export to COS for custom analysis in ClickHouse or a BI tool.
- **Cost allocation tags**: define tags (`Environment`, `Service`, `Owner`, `CostCenter`) and enforce them on all resources via a tagging policy. Without tags, bills are unattributable.
- **Budget alerts**: set monthly budgets per project / account. Alert at 80% consumed, 100% consumed, and on anomalous daily spend.
- **Cost trend analysis**: review month-over-month per-service cost trends. Unexpected increases are often caused by forgotten dev resources, accidental configuration changes (e.g., CDN origin pull rate increase), or runaway data egress.
- **Resource utilization report**: Cloud Monitor provides utilization summaries for CVM, CDB, and Redis. Use these to identify underutilized resources for rightsizing or deletion.

## Optimization levers

| Lever | Where it pays |
| --- | --- |
| CVM Reserved Instances (1-year) | 30–50% on stable CVM baseline vs on-demand |
| Spot CVM instances | 70–90% discount for stateless / restartable workloads |
| TKE Spot node pools | Batch and non-critical workloads on TKE |
| TDSQL-C Serverless for dev/staging CDB | Scales to zero when idle — eliminates idle-DB cost |
| COS lifecycle rules (Standard → IA → Archive) | 40–80% reduction on cold data stored as Standard |
| CLS retention limits + COS archiving | CLS hot storage is expensive; archive to COS after 7–30 days |
| SCF memory rightsizing | Profile function memory allocation; reduce to actual usage × 1.5 |
| CCN premium bandwidth scheduling | Bandwidth peaks off-peak hours at 30% discount |
| Reserved bandwidth packages | Predictable CDN / CLB bandwidth — commit for discount |
| Shutdown dev/staging nights + weekends | CVM and CDB instances incur charges when stopped (storage only); TKE Serverless scales to zero |

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Infinite CLS topic retention | CLS storage accumulates; bills grow unexpectedly. Set retention. |
| Alarms only on CPU | CPU is a lagging indicator. Alarm on request rate, error rate, latency. |
| No log field indexes | CLS queries scan full text; slow and expensive. Index your filter fields. |
| SCF provisioned concurrency "just in case" | Charged per GB-second even when idle. Measure cold-start pain before enabling. |
| CVM on-demand for workloads running 3+ months | Reserved instances would save 40%. Set up reserved after 90 days of stable usage. |
| Cost allocation tags applied inconsistently | Bills become unattributable; cost centers can't be charged back. Enforce tags in IaC. |
| No budget alerts | Runaway spend discovered at month-end. Alert at 80% budget consumed. |
| APM on every microservice but no service map review | Topology surprises (unexpected call chains, misrouted traffic) stay hidden. |

## Observability + cost together

The cheapest debugging is the alarm that links to a runbook. The most expensive debugging is the missing dashboard during an incident. Invest in telemetry; optimize elsewhere.

Common false economies:
- Disabling APM tracing to save ingestion costs → spending engineer hours diagnosing distributed latency blind.
- Over-aggressive log sampling → missing the single error trace needed to reproduce a production bug.
- Skipping CLS field indexing → slow queries during an incident when speed matters most.

## IaC hints

- Terraform: `tencentcloud_monitor_alarm_policy`, `tencentcloud_cls_logset`, `tencentcloud_cls_topic`, `tencentcloud_cls_index`, `tencentcloud_monitor_dashboard`.
- Always set `log_retention_period` on `tencentcloud_cls_topic`; there is no safe default.
- Manage notification groups (`tencentcloud_monitor_alarm_policy_notification`) in IaC so on-call routing is version-controlled and reviewable in PRs.
- For COS log archiving: `tencentcloud_cls_cos_shipper` — define retention and compression (LZ4 or GZIP).
- Tag every Cloud Monitor alarm with `Environment`, `Service`, `Owner` so ownership is clear during incidents.

## Verification checklist

- [ ] Every service emits structured logs, Cloud Monitor metrics, and APM traces with a shared `request_id`.
- [ ] CLS topic retention is bounded; long-term storage ships to COS.
- [ ] At least one alarm per service tied to user-visible pain, with a runbook link in the alarm description.
- [ ] Cost allocation tags enforced on all resources; Cost Manager slices match expected service / environment breakdown.
- [ ] Budget alerts configured at 80% and 100% for each environment.
- [ ] Reserved instances purchased for any CVM / CDB running steadily for 3+ months.
- [ ] Spot node pools enabled for non-critical TKE workloads.
- [ ] COC incident management configured; escalation policies tested.
- [ ] CLS field indexes created for filter and aggregation fields.
- [ ] Dashboards exist for top services and are generated from IaC.
