---
name: alibaba-observability-and-cost
description: Wire up or audit Alibaba Cloud observability and cost — CloudMonitor (metrics/alarms), Simple Log Service (SLS logs/metrics/query), ARMS (APM traces), Cost Manager (bills/budgets/anomaly), Resource Management (groups/tags), reservation and savings models. Use when adding telemetry, tracking a regression, or shrinking the bill.
---

# Alibaba Observability and Cost

## When to use

- Setting up logs, metrics, and traces for a new service.
- Building an SLO dashboard or wiring an alarm to an on-call channel.
- Diagnosing a latency, error rate, or cost regression.
- Evaluating whether to purchase Savings Plans or Reserved Instances.
- Sizing a quarterly cloud cost review with resource group and tag-based breakdowns.

## Observability pillars

| Pillar | Service |
| --- | --- |
| Infrastructure metrics | CloudMonitor (metrics, host metrics, custom metrics, alarm rules) |
| Logs (ingest + query + alert) | Simple Log Service (SLS) — Logstore for raw logs, Metricstore for timeseries metrics |
| APM / distributed traces | ARMS (Application Real-Time Monitoring Service) — trace, profiling, RUM |
| Synthetics | ARMS Synthetic Monitoring (canary-style availability checks) |
| Real User Monitoring | ARMS Front-End Monitoring (browser + mobile SDK) |
| K8s observability | ARMS Prometheus (managed Prometheus + Grafana for ACK clusters) |
| Dashboards | CloudMonitor custom dashboards, SLS Dashboards, ARMS Service Map, Grafana |

## Defaults — every service

- **Structured JSON logs** with a stable request-id field propagated across the call chain.
- **CloudMonitor host agent** on every ECS instance for memory, disk, and process metrics (not reported by the hypervisor by default).
- **SLS log ingestion** from every compute runtime (ECS, FC, ACK pods, SAE) — `stdout` + `stderr` collected by Logtail agent or SLS SDK.
- **ARMS trace SDK** (OpenTelemetry or Alibaba-native) for any service with user-visible latency; propagate `TraceId` as a log field.
- **At least one alarm** per service tied to user-visible pain — error rate, p99 latency, queue depth, dead-letter count. Never alarm on CPU alone.
- **SLS Logstore TTL**: set explicitly (30–90 d for hot query; archive to OSS Cold Archive for long retention). Default unlimited TTL is an unbounded bill.

## CloudMonitor

- **Metrics coverage**: ECS / ACK node / RDS / Redis / OSS / SLB metrics are ingested automatically once the resource is created. Explicit agent install required for in-OS memory and disk.
- **Custom metrics**: use CloudMonitor custom metric API or embedded-format logs (SLS-based) for application-level signals; batch `PutCustomMetricData` calls to stay within rate limits.
- **Alarm rules**: specify metric, statistic (avg / max / sum), period (1 min minimum), threshold, and evaluation count. Alarm action: notification contact group (DingTalk, email, SMS) or EventBridge for programmatic response.
- **Event rules**: resource events (ECS Spot interruption, Auto Scaling activity, RDS failover) are CloudMonitor events — wire to EventBridge → Function Compute for automated response.
- **Composite alarms**: supported; combine multiple metric alarms to suppress noise (e.g., alert only when both error rate and latency exceed threshold simultaneously).
- **System event alarms**: subscribe to Alibaba Cloud service disruptions and maintenance events via CloudMonitor system events.

## Simple Log Service (SLS)

### Project and store structure

- One SLS Project per environment (dev / staging / prod) or per business domain.
- **Logstore** for raw logs; **Metricstore** for structured timeseries metrics (Prometheus-compatible remote-write supported).
- Shard capacity: 1 shard = 5 MB/s write + 10 MB/s read; provision based on peak ingest rate; auto-split for new projects.
- TTL and archiving: hot tier (SLS native) for 7–90 d; cold tier (OSS via scheduled export) for regulatory retention. Enable OSS archival from day one for compliance workloads.

### Log pipelines

- **Logtail** (ECS agent): collect `stdout` / `stderr`, custom log files, container logs; regex or JSON structured mode.
- **ACK log collection**: deploy the SLS DaemonSet via ACK addon; mount Logtail config as a ConfigMap.
- **FC log**: SLS log collection enabled per FC service; automatic request/response log for each invocation.
- **OSS access logs**: SLS can ingest OSS server access logs directly via OSS delivery channel.
- **Kafka compatibility**: SLS Consumer Groups expose a Kafka-compatible consumer interface; downstream consumers (Flink, Spark) can read without SLS SDK.

### Alerting

- SLS alert rules support SQL / SPL (SLS Processing Language) for complex threshold logic.
- De-duplication and silence periods configurable.
- Action policies: route different severity alerts to DingTalk group, PagerDuty, or SMS — one SLS project can fan out to multiple channels.

## ARMS (Application Real-Time Monitoring Service)

- **Trace SDK**: OpenTelemetry agent (preferred for portability) or ARMS proprietary agent; both report to ARMS backend.
- **Service map**: auto-generated from trace data; shows upstream / downstream latency and error rate.
- **Profiling**: continuous CPU and memory profiling available for Java workloads (low overhead, always-on).
- **Synthetic monitoring**: HTTP / browser checks from Alibaba PoPs globally; alert on availability and latency.
- **Front-End Monitoring**: browser SDK for JS error collection and user timing; correlate with backend trace via TraceId.
- **ARMS Prometheus for ACK**: managed Prometheus with pre-built dashboards for node, pod, workload, and API server metrics; no self-hosted Prometheus infra required.

## Alarms — write them like contracts

Good alarm spec:

- **Signal**: which metric, which statistic, over which window (1 min / 5 min / 15 min).
- **Threshold**: the number that means "human attention needed" — verified against historical baselines.
- **Action**: which contact group / DingTalk webhook / EventBridge rule.
- **Runbook**: linked from the alarm description — first thing the responder reads.

Avoid floating thresholds and "CPU > 80%"-only alarms. For SLO tracking, set alarms at error-budget burn rate (e.g., 2% errors in 5 min = paging).

## Cost — the actual playbook

### Visibility

- **Cost Manager**: view bills by service, region, resource, and tag. Export to OSS for custom analysis.
- **Resource tags**: enforce `Environment`, `Service`, `Owner`, `CostCenter` tags on all resources; Cloud Config rules can detect untagged resources.
- **Resource groups**: map to billing dimensions in Cost Manager — one resource group per environment gives an instant per-environment cost view.
- **Cost Anomaly Detection**: enabled in Cost Manager; sends alert when daily spend deviates from ML-predicted baseline. Free, zero-config.
- **Budgets**: set monthly budget per account and per resource group; action alerts at 50%, 80%, 100%.

### Optimization levers

| Lever | Where it pays |
| --- | --- |
| Compute Savings Plans (1y) | 20–55% discount on ECS, ACK, FC, SAE — covers most compute. Buy after 30+ d of stable usage. |
| ECS Reserved Instances | Steady-state ECS baseline; zonal RI for guaranteed capacity, regional RI for flexibility. |
| ARM instances (`g8y`, `c8y`, `r8y`) | ~15–20% cheaper per vCPU than x86 equivalent for compatible workloads. |
| Spot / Preemptible instances | Up to 90% discount for stateless or fault-tolerant batch workloads. |
| OSS storage tiering | Standard → IA: ~45% savings; → Archive: ~80%. Lifecycle rules from day one. |
| Resource Manager auto-stop | ECS and RDS dev/staging stop on a schedule (evenings + weekends via Cloud Assistant). |
| NAT Gateway → VPC private endpoints | Cut NAT data-processing charges for traffic to OSS, RDS, Redis, SLS. |
| AnalyticDB / Lindorm Elastic mode pause | Pause compute nodes outside query windows; pay storage only when idle. |
| SLS cold-tier archiving | Move logs to OSS Cold Archive after 30–90 d; cost < 10% of SLS hot storage. |

### Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| SLS Logstore with unlimited TTL | Logs accumulate forever; bill grows unexpectedly. Always set TTL + OSS archive. |
| CloudMonitor alarms on CPU alone | CPU rarely maps to user pain; alarm on error rate, latency, and queue depth. |
| Savings Plans bought before usage stabilizes | Wrong instance family or region coverage; stranded discount. Wait 30+ d. |
| Untagged resources | Cost report is unreadable when bill grows; retroactive tagging is expensive toil. |
| Reserved Instances in wrong zone | Zonal RI does not apply cross-zone; regional RI is more flexible. |
| ARMS trace sampling at 100% | At high throughput, full sampling creates significant SLS write overhead; use tail-based or probabilistic sampling. |
| No anomaly detection | Cost spikes from runaway auto-scaling or mis-configured jobs discovered at month end. |

## Observability + cost together

The cheapest debugging is the alarm that points to the runbook. The most expensive debugging is the missing dashboard during an incident.

Common false economies:

- Turning off ARMS tracing to save SLS write cost → spending 10× more in engineer hours on next incident.
- Setting SLS TTL to 3 d "for cost" → missing the evidence needed 5 d into a forensics investigation.
- Skipping ARMS Prometheus for ACK → opaque pod-level scheduling and OOM events.

## IaC hints

- Terraform: `alicloud_cms_alarm` (CloudMonitor alarm), `alicloud_log_project` + `alicloud_log_store` + `alicloud_log_store_index` (SLS), `alicloud_arms_prometheus` (ARMS Prometheus for ACK), `alicloud_log_audit` (SLS audit service).
- Always set `retention_period` (days) on every `alicloud_log_store` resource — never omit.
- Use `alicloud_cms_metric_rule_template` to reuse alarm templates across services.
- Cost Manager and budgets are managed via console or `aliyun bss` CLI; limited Terraform support as of provider 1.220 — script via `aliyun` CLI in bootstrap pipelines.

## Verification checklist

- [ ] Every service emits structured logs to SLS, metrics to CloudMonitor, and traces to ARMS with a shared request-id.
- [ ] SLS Logstore TTL is bounded; long-term storage exported to OSS Cold Archive.
- [ ] At least one alarm per service tied to user-visible pain, with a linked runbook.
- [ ] Resource tags (`Environment`, `Service`, `Owner`, `CostCenter`) enforced; Cost Manager slices match expected breakdown.
- [ ] Cost Anomaly Detection enabled; daily spend baseline reviewed monthly.
- [ ] Savings Plan / Reserved Instance coverage reviewed after 30 d of stable usage.
- [ ] ARMS Prometheus deployed for each ACK cluster; node + pod + workload dashboards available.
- [ ] CloudMonitor host agent installed on every ECS instance (memory + disk metrics).
- [ ] SLS alert rules tested end-to-end (fire a test event; verify the notification reaches the channel).
