---
name: linode-observability-and-cost
description: Wire up or audit Linode observability and cost — Longview agent, Cloud Manager metrics, external monitoring (Datadog / Better Stack / Grafana Cloud), alerts, billing model (per-hour with monthly cap), and the regional transfer pool. Use when adding telemetry, diagnosing a cost spike, or planning a billing review.
---

# Linode Observability and Cost

## When to use

- Setting up monitoring for new Compute Instances or an LKE cluster.
- Diagnosing unexpected CPU, memory, disk, or network behavior.
- Building alerts for an on-call rotation.
- Understanding a Linode bill or investigating a transfer overrun.
- Planning a cost review for a Linode environment.
- Migrating from Cloud Manager's built-in graphs to a full observability stack.

## The Linode observability gap

Linode's native observability is lightweight compared to AWS CloudWatch, GCP Cloud Monitoring, or Azure Monitor. Be direct with users about what is and is not built in:

| Need | Linode built-in | External solution |
| --- | --- | --- |
| CPU, memory, disk, network stats (per host) | Longview (free tier: 10 hosts; paid: unlimited) | Datadog, Prometheus + node_exporter |
| Historical metrics (> 24 h) | Longview paid (30 d history); Cloud Manager (30 d basic) | External time-series DB |
| Application-level metrics | None | Prometheus, StatsD, OpenTelemetry |
| Distributed traces | None | Jaeger, Tempo, Datadog APM |
| Log aggregation | None | Grafana Loki, Datadog Logs, Better Stack |
| Uptime / synthetic monitoring | None | Better Stack, UptimeRobot, Datadog Synthetics |
| Alerting (threshold-based) | Basic Cloud Manager alerts | PagerDuty, Grafana alerting, Datadog monitors |
| Kubernetes cluster metrics | None (LKE) | Prometheus + kube-state-metrics + node_exporter |
| Cost / billing alerts | Cloud Manager billing alert | Manual export of billing API |

For any production workload, plan for external observability from day one. Longview is a lightweight entry point for per-host stats; it is not a substitute for a full observability stack.

## Longview

- **What it is:** a lightweight stats agent (Linode-managed) that collects CPU, memory, disk I/O, and network throughput from a Compute Instance and displays them in Cloud Manager.
- **Free tier:** up to 10 hosts on the free plan. Data resolution: last 24 h at full resolution; up to 12 h for the free tier (verify current tier limits). Plan retention is limited — not suitable for capacity planning over months.
- **Longview Pro:** paid plan for unlimited hosts and 30-day metric retention. Worth it if you have many instances and don't have an external metrics platform yet.
- **Installation:** `curl -s https://lv.linode.com/<token> | sudo bash`. Managed via the Longview panel in Cloud Manager. Tokens are per-account.
- **What it does not cover:** application-layer metrics, custom metrics, LKE/container metrics, external endpoint checks.
- **Agent footprint:** small but non-zero. The Longview agent runs as a daemon; factor in its CPU/memory impact on very small instances (Nanode 1 GB).

## Cloud Manager built-in metrics

- Every Compute Instance has CPU, network in/out, and disk I/O graphs in Cloud Manager covering the last 24 hours and 30 days.
- These graphs have no alerting capability — they are diagnostic-only.
- NodeBalancer connection rate, traffic in/out, and node status are visible in Cloud Manager.
- These built-in graphs are useful for ad-hoc investigation; they are not a monitoring strategy.

## External monitoring — recommended stack

### Option A: Prometheus + Grafana (self-hosted or Grafana Cloud)

- Deploy `node_exporter` on each Compute Instance. Scrape with Prometheus.
- For LKE: deploy `kube-prometheus-stack` (Helm chart) — includes Prometheus, Grafana, kube-state-metrics, node_exporter, and pre-built Kubernetes dashboards.
- Grafana Cloud free tier covers small environments (check current limits). Self-hosted Grafana + Prometheus + Loki is cost-effective but requires maintenance.
- Alerting via Grafana Alertmanager to PagerDuty, Slack, or email.

### Option B: Datadog

- Datadog agent on each instance; Datadog Kubernetes integration for LKE.
- Strong out-of-box Kubernetes dashboards, APM, log management.
- Cost scales with host count and features; plan carefully before committing.

### Option C: Better Stack (formerly BetterUptime / Logtail)

- Lightweight uptime monitoring and log management.
- Good entry-level option for small teams. Collect logs via the Better Stack vector agent or rsyslog forwarding.
- Does not cover infrastructure metrics natively — combine with Prometheus or Longview.

### Minimum viable observability for a production instance

1. Longview installed (or node_exporter + Prometheus).
2. External uptime check on the public endpoint (Better Stack, UptimeRobot, or equivalent).
3. An alert that fires when the instance is unreachable for > 2 minutes.
4. An alert on disk usage > 80%.
5. Log shipping to a searchable log store.

## Alerts

- **Linode Cloud Manager alerts:** basic email alerts for CPU spikes, network spikes, and disk I/O. Configure in the instance settings. Threshold-based only; no composite or multi-condition alerts.
- **External alerting:** recommended for any production workload. Grafana Alertmanager, Datadog monitors, or Better Stack incident channels provide richer alerting with on-call routing.
- **Write alerts as contracts:** every alert should have a defined signal, threshold, window, and a linked runbook. "CPU > 80%" without a runbook and a threshold-validation window is noise.

## Billing model

- **Per-hour billing, capped at the monthly price.** If an instance runs for 24 hours on a $10/month plan, you are charged approximately $0.015/hour × 24 = $0.36. If it runs all month, you pay $10.
- **Partial hours round up.** An instance alive for 1 minute costs one full hour.
- **Delete to stop billing.** Powering off an instance does NOT stop billing. An instance must be deleted to stop accruing charges. If you want to "pause" compute, create a snapshot / Image first, then delete the instance.
- **Volume charges continue while the Volume exists**, regardless of whether it is attached or the instance is powered off/deleted.
- **NodeBalancer charges are flat monthly.** One NodeBalancer cost = one NodeBalancer line item on your bill, regardless of traffic volume (plus any overage fees).
- **Object Storage:** charged per GB-month of storage + per-request + egress overages.
- **Managed Database:** plan-based monthly price.

## Transfer pool model

This is one of the most important billing concepts on Linode. Understand it before designing for egress.

- **Per-region pool:** each Linode instance contributes its included transfer to a shared pool for that region. The pool total for a region is the sum of all instance transfer allocations in that region.
- **Inbound transfer:** free. Counts toward no pool.
- **Outbound to the internet:** counts against the regional pool. Pool overages bill at the overage rate (approximately $0.005/GB — verify current rate).
- **Outbound between Linode instances in the same data center:** free (private IP / VLAN / VPC traffic). Counts against no pool.
- **Outbound between Linode regions:** does count against the originating region's pool (or may bill separately — verify current policy).
- **Maximizing pool value:** run multiple instances in the same region — their transfer allocations pool. A 10-instance cluster in one region has a larger pool than 10 instances spread across 10 regions.

### Transfer pool visibility

- Check current regional pool usage in Cloud Manager under Account > Transfer.
- Set a billing alert in Cloud Manager to notify before reaching the pool limit.
- Build monthly transfer budget estimates based on expected egress before deployment.

## Cost optimization

| Lever | Where it pays |
| --- | --- |
| Destroy unused instances | Powered-off instances still bill. Destroy and re-provision from a snapshot. |
| Right-size instance plans | Longview or external metrics show sustained CPU < 20%? Step down a plan. |
| Concentrate instances in one region | Larger shared transfer pool reduces overage risk. |
| Remove orphaned Volumes | Volumes bill per GB regardless of attachment. Audit and delete unused Volumes. |
| Image instead of pause | Snapshot to a Linode Image, destroy the instance; pay only for Image storage. |
| Managed Database vs self-managed | For small teams, Managed Database simplifies ops; at high data volume, self-managed may be cheaper per GB. |
| LKE autoscaling | Set autoscaler `min` to the genuine minimum — idle nodes bill full node price. |
| Object Storage tier awareness | Large infrequently-accessed datasets are cheap at rest; egress is where costs appear. |

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Powering off an instance to "pause" billing | Billing continues. You must delete to stop charges. |
| No external uptime monitoring | Cloud Manager has no outward-facing uptime checks. You learn about downtime from users. |
| Relying on Cloud Manager graphs for capacity planning | 30-day retention, no aggregation, no alerting. Not a capacity planning tool. |
| Not tracking transfer pool per region | Overage surprises appear on the monthly invoice. Monitor the pool in real time. |
| Spreading instances across many regions for no availability reason | Fragments the transfer pool; no cross-region pool sharing. |
| Orphaned Block Storage Volumes after instance deletion | Volumes persist and bill. Audit and delete after any instance teardown. |
| No alerts until users report problems | External uptime check + a minimum viable alert set is non-negotiable for production. |

## IaC hints

- Longview: install via cloud-init `user_data` or Ansible playbook post-provision. The Longview token is a Linode account-level secret; store in your secrets manager.
- Billing exports: use the Linode API (`GET /account/invoices`) to pull billing history. Script a monthly export to Object Storage for your records.
- Transfer pool monitoring: `GET /account/transfer` returns current pool usage. Wire to an alerting script that fires when pool usage exceeds a configured threshold.

## Verification checklist

- [ ] Longview or external metrics agent installed on every non-LKE instance.
- [ ] External uptime check configured for every public endpoint.
- [ ] At minimum: disk usage and endpoint availability alerts wired to a notification channel.
- [ ] Log aggregation configured; logs queryable for incident investigation.
- [ ] Regional transfer pool budget calculated and billing alert set in Cloud Manager.
- [ ] Billing alert set to notify before pool exhaustion.
- [ ] No powered-off instances that should be destroyed (billing audit).
- [ ] Orphaned Volumes reviewed and cleaned up.
- [ ] For LKE: Prometheus + Grafana or equivalent installed; Kubernetes-level metrics visible.
