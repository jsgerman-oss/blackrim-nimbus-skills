---
name: do-observability-and-cost
description: Wire up or audit DigitalOcean observability and cost — Monitoring (graphs, alert policies for CPU, disk, memory, bandwidth), Logs, Insights / metrics, project-level billing, Reserved capacity hooks, and snapshot lifecycle costs. Use when adding telemetry, tracking down a regression, or shrinking a bill.
---

# DigitalOcean Observability and Cost

## When to use

- Setting up monitoring and alert policies for a new Droplet, DOKS cluster, or Managed Database.
- Building an SLO dashboard or wiring an alert to an on-call channel.
- Diagnosing a performance or availability regression.
- Reviewing a monthly DigitalOcean bill and identifying cost drivers.
- Planning Reserved Droplet commitments after usage stabilizes.
- Auditing snapshot and image storage costs.

## Observability landscape

DigitalOcean's native observability tooling is intentionally lightweight. Plan around its gaps if you need deep application-level observability.

| Capability | DigitalOcean native | Common complement |
| --- | --- | --- |
| Infrastructure metrics (CPU, memory, disk, bandwidth) | Metrics Agent + Monitoring dashboard | Prometheus + Grafana on DOKS |
| Application metrics | None (first-party) | Prometheus, StatsD, Datadog, New Relic |
| Logs (infrastructure) | None (first-party log shipping) | Papertrail, Logtail, Loki, Datadog |
| Logs (App Platform) | 7-day in-platform retention | Forward via doctl / API to external sink |
| Tracing | None | OpenTelemetry → Jaeger, Honeycomb, Datadog |
| Uptime / synthetics | None | Better Uptime, Pingdom, Grafana Synthetic |
| Cost visibility | Project-level billing, usage reports | FinOps export to Spaces + query tool |

## Metrics Agent

Install the DigitalOcean Metrics Agent on every Droplet. Without it, the monitoring dashboard shows only network bandwidth; CPU, memory, and disk metrics require the agent.

- **Install:** via cloud-init user-data on first boot, or via Ansible / Terraform provisioner.
- **What it reports:** CPU utilization, memory utilization (total and used), disk utilization per mount, disk read/write IOPS, and outbound bandwidth.
- **Memory:** DigitalOcean reports available memory, not used memory. A Droplet at 90% memory available is at 10% utilization — check which direction the alert policy measures.

```bash
# Install on Ubuntu / Debian (run as root or with sudo)
curl -sSL https://repos.insights.digitalocean.com/install.sh | bash
```

For Terraform-managed Droplets, include the install in the `user_data` field or use a `remote-exec` provisioner.

## Alert policies

Alert policies fire on threshold crossings and notify via email or a webhook (Slack, PagerDuty).

- **Wire every alert to a real notification target.** An alert policy with no notification rule is useless.
- **Meaningful thresholds, not arbitrary round numbers:** CPU at 80% for 10 minutes means something if CPU-bound; for an I/O-bound service, CPU 80% is irrelevant. Think about what metric predicts user pain, not what looks like a normal alert.
- **Standard baseline alert policies for every production Droplet:**
  - CPU utilization > 80% for 5 minutes (sustained, not spike).
  - Memory utilization > 85%.
  - Disk utilization > 80% (expand or clean before it hits 100% — a full disk causes hard errors).
  - Outbound bandwidth > your expected baseline (detect unexpected egress / exfil).

```bash
doctl monitoring alert create \
  --type v1/insights/droplet/cpu \
  --compare GreaterThan \
  --value 80 \
  --window 5m \
  --entities droplet:<id> \
  --notifications '{"email":["ops@example.com"],"slack":[{"channel":"#alerts","url":"https://hooks.slack.com/..."}]}'
```

- **Managed Database alert policies:** available for CPU, disk, memory, and connection count. Apply the same set as Droplets plus connection count > 80% of the plan's `max_connections` limit.
- **Load Balancer:** monitor backend health via the LB metrics dashboard. There is no native LB alert policy — set up an external uptime check against your LB's public IP or domain.
- **DOKS:** install the DigitalOcean Kubernetes Monitoring add-on (Prometheus + Grafana) from the DOKS marketplace. It installs into the cluster and provides node-level and pod-level metrics out of the box.

## Logs

DigitalOcean has no first-party log aggregation or shipping service. You must choose a log destination.

- **Application logs:** ship structured JSON logs from your application to a log aggregation service. Common choices: Papertrail (simple, integrated with DigitalOcean Marketplace), Logtail (structured, affordable), Loki (self-hosted on DOKS), Datadog.
- **App Platform logs:** available for 7 days via the Control Panel or `doctl apps logs <app-id>`. For longer retention, configure a log drain to Papertrail or Datadog from the App Platform settings.
- **Syslog / journald:** forward via `rsyslog` or `vector` from Droplets to your log aggregation sink.
- **Structured logs:** emit JSON with a consistent schema including `request_id`, `service`, `environment`, `level`, and `timestamp`. These fields enable efficient filtering and correlation in any log aggregation product.
- **Retention:** keep at least 30 days of application logs, 90 days for security-relevant events (auth, access, errors), and as long as compliance requires for audit trails.

## DOKS observability

- **Kubernetes Monitoring add-on:** installs Prometheus (for metrics scraping), Grafana (for dashboards), and Alert Manager (for routing). Enable it on every production cluster.
- **Node-level metrics:** Prometheus node exporter (included in the add-on) scrapes CPU, memory, disk, and network on each node.
- **Pod-level metrics:** Prometheus scrapes pods that expose a `/metrics` endpoint. Instrument your applications with the Prometheus client for your language.
- **Persistent storage for Prometheus:** by default, the add-on stores metrics in a pod-local volume that is lost on pod restart. Attach a DigitalOcean Volume (via the `digitalocean-block-storage` storage class) to the Prometheus pod for durability.
- **kube-state-metrics:** included in the add-on; exposes Kubernetes object state (deployment replicas, pod status, node conditions) as Prometheus metrics. Alarm on `kube_pod_status_phase{phase="Failed"}` and `kube_node_status_condition{condition="Ready",status="false"}`.

## Cost visibility and management

### Billing structure

DigitalOcean billing is hourly, billed monthly. The bill has these major line items:

- Droplets (per hour, based on plan size)
- Managed Databases (per hour)
- Spaces storage ($0.02 / GB) and bandwidth ($0.01 / GB after free tier)
- Volumes ($0.10 / GB / month)
- Load Balancers ($12 / month per LB)
- Container Registry (plan fee + storage overages)
- Snapshots ($0.06 / GB / month)
- Kubernetes (no control-plane fee; you pay for worker node Droplets)
- Reserved IPs when unassigned ($0.006 / hour)

### Project-level cost attribution

Every resource should be assigned to a DigitalOcean Project. The billing dashboard shows per-project spend. Without project assignment, you cannot attribute costs to a team, environment, or service.

- Assign resources at creation time, not retroactively. Terraform `digitalocean_project_resources` is the IaC path.
- Review per-project cost monthly and compare against expected baselines. Unexpected growth in a project signals either a scaling event or a runaway resource.

### Cost optimization levers

| Lever | Where it pays |
| --- | --- |
| Reserved Droplets (1-year or 2-year) | 25–40% discount on stable, persistent Droplets. Buy after 3+ months of stable size. |
| Power off idle Droplets | Stopped Droplets still bill for reserved resources (disk, Reserved IP). Delete and restore from snapshot if idle > 1 week. |
| Right-size via Metrics Agent data | Over-provisioned Droplets are common. Check average CPU and memory utilization over 30 days before sizing up. |
| Prune snapshots | $0.06 / GB / month. Old snapshots accumulate. Set a retention policy and script deletion of expired snapshots. |
| Use Spaces CDN | Reduces origin egress; CDN bandwidth is cheaper than direct object-serve egress at volume. |
| Destroy test infrastructure | Terraform `plan` and `apply` pipelines should tear down ephemeral test environments after CI completes. |
| Evaluate Managed DB vs Droplet | At scale, self-hosting on Memory-Optimized Droplets can be 40–60% cheaper. Calculate honestly when managed markup becomes material. |

### Snapshot lifecycle costs

Snapshots are the most frequently overlooked cost in DigitalOcean accounts:

- A 100 GB Droplet snapshot costs $6 / month.
- Four weekly automated backups of a 100 GB Droplet cost $1.44 / month (charged at 20% of Droplet hourly rate).
- Volume snapshots are incremental; costs grow with data change rate, not full volume size.
- Audit snapshots monthly: `doctl compute snapshot list`. Delete snapshots older than your retention window.
- DOKS: Velero backup sets to Spaces cost based on Spaces storage of the backup data — plan the retention lifecycle.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| No Metrics Agent installed | CPU and memory metrics unavailable; you're flying blind on resource saturation. |
| Alert policies with no notification rule | Thresholds fire; nobody knows. |
| CPU-only alert for an I/O-bound service | Misses the actual bottleneck; false sense of monitoring. |
| No log retention policy | Log costs grow unbounded; old logs stay in expensive short-term storage. |
| Snapshots never pruned | Silent $0.06/GB/month accumulation. |
| Stopped Droplets assumed to be free | Stopped Droplets still bill for disk, Reserved IP. Delete if not needed. |
| DOKS with no persistent storage for Prometheus | Metrics lost on pod restart; post-incident forensics impossible. |

## Observability + cost together

The cheapest operations are ones where you find problems before they cause incidents. Invest in Metrics Agent coverage and alert policies early; the cost is low. Skimping on observability means you find out about problems from users, not dashboards.

Common false economies:

- Removing the Metrics Agent to save bandwidth — the bandwidth cost is negligible; the monitoring gap is not.
- Skipping log aggregation "until we grow" — you need logs most during early incident diagnosis when you have the least operational experience.
- Not setting up DOKS monitoring because it "adds complexity" — a pod crash loop at 3 AM without Prometheus/Grafana is expensive in engineer hours.

## IaC hints

- Terraform resource: `digitalocean_monitor_alert` for alert policy management.
- Cloud-init `user_data` for Metrics Agent installation on Droplet creation.
- `digitalocean_project_resources` to assign all resources to a project at creation.
- Manage Spaces lifecycle rules via `digitalocean_spaces_bucket_lifecycle_configuration` to automate snapshot bucket pruning.
- For DOKS, use the `digitalocean_kubernetes_cluster` resource's `auto_upgrade` and `maintenance_policy` arguments to control when the control plane upgrades — schedule for off-peak hours.

## Verification checklist

- [ ] Metrics Agent installed on every production Droplet.
- [ ] Alert policies defined for CPU, memory, disk, and bandwidth on each Droplet.
- [ ] Alert policies wired to a real notification target (email, Slack, PagerDuty).
- [ ] Log aggregation configured with at least 30-day retention for app logs.
- [ ] DOKS clusters have the Kubernetes Monitoring add-on installed with persistent storage.
- [ ] All resources assigned to projects; per-project cost visible in billing dashboard.
- [ ] Snapshot retention policy documented and automated deletion scripted.
- [ ] Monthly cost review scheduled; anomalies have a runbook for investigation.
- [ ] Reserved Droplet commitments reviewed quarterly against observed usage.
