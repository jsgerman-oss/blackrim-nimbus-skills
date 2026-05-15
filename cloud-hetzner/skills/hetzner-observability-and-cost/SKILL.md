---
name: hetzner-observability-and-cost
description: Wire up or audit Hetzner observability and cost — hcloud server metrics (CPU / network / disk via API), Cloud Status page, Robot server monitoring, pairing with external observability stacks (Grafana Cloud, Datadog, Better Stack, Prometheus), Hetzner billing model (hourly capped at monthly), egress traffic allowances and per-TB overage, IPv4 surcharge. Use when adding telemetry, tracking down a cost regression, or sizing a monthly bill.
---

# Hetzner Observability and Cost

## When to use

- Setting up server metrics and alerting for a Hetzner-hosted workload.
- Choosing and integrating an external observability platform.
- Diagnosing a latency, error, or resource exhaustion problem.
- Estimating and controlling Hetzner monthly costs.
- Auditing egress traffic and IPv4 spend.
- Planning traffic allowance across multiple servers.

## Observability reality check

Hetzner provides no managed observability service. There is no equivalent of CloudWatch, Google Cloud Monitoring, or Azure Monitor. What you get:

| What Hetzner provides | What you must provide externally |
| --- | --- |
| hcloud API server metrics (CPU, network, disk IOPS) — last 30 days | Log aggregation and long-term metric storage |
| Cloud Status page (status.hetzner.com) | Alerting, dashboards, SLO tracking |
| Robot panel basic PING / TCP monitoring | Distributed tracing |
| Traffic usage meter in the Cloud panel | APM, profiling |

Budget for an external observability platform from day one. The operational cost of debugging without it far exceeds the subscription cost.

## hcloud server metrics

The hcloud API exposes per-server metrics over a time range via `GET /servers/{id}/metrics`:

- `cpu` — average CPU utilization (0–100%).
- `network` — bytes in/out per second on the public network interface.
- `disk` — IOPS read/write on the attached volumes or root disk.

Access via hcloud CLI:

```bash
hcloud server metrics <server-id> --type cpu,network,disk \
  --start "2026-05-01T00:00:00Z" --end "2026-05-02T00:00:00Z"
```

Limitations:

- 30-day retention only.
- No alerting — you must poll and alert externally.
- No memory metrics (Hetzner cannot observe guest OS memory from the hypervisor).
- No per-process or application-level metrics.

For memory, disk space, and process-level data, install the Prometheus Node Exporter or Datadog / Grafana Alloy agent on each server.

## External observability stacks

### Prometheus + Grafana Cloud (recommended for cost-sensitive setups)

1. Deploy `prometheus/node_exporter` on every server (DEB/RPM package or Docker).
2. Scrape with a Prometheus instance in the same Private Network, or use Grafana Alloy in push mode.
3. Remote-write to Grafana Cloud's Prometheus endpoint (free tier: 10,000 series, 14-day retention).
4. Import Hetzner-specific dashboards from grafana.com/grafana/dashboards.

```yaml
# prometheus.yml snippet
scrape_configs:
  - job_name: hetzner_nodes
    static_configs:
      - targets:
          - "10.0.1.10:9100"  # server-01 via Private Network
          - "10.0.1.11:9100"  # server-02
```

### Datadog

Install the Datadog Agent on each server. The Agent collects CPU, memory, disk, network, and process metrics. Hetzner has no native Datadog integration — configure via `DATADOG_API_KEY` in the Agent config. Use Private Network IPs in Agent config to avoid public egress charges.

### Better Stack (Uptime + logs)

Better Stack (formerly Logtail + Uptime) provides HTTPS ping / TCP-port uptime monitoring with alerting (Slack, PagerDuty, webhooks) and structured log ingestion. Useful as a lightweight layer for uptime alerting without a full metrics stack.

### Grafana Alloy / Vector + Loki / Elasticsearch

For log aggregation: deploy Vector or Grafana Alloy on each server to collect and forward `/var/log/**` and application logs. Ingest to Grafana Loki, Elasticsearch, or a managed provider (Grafana Cloud Logs, Datadog Logs, Better Stack Logs).

## Cloud Status

Hetzner publishes infrastructure status at [https://status.hetzner.com](https://status.hetzner.com). Subscribe to the RSS feed or the status page notifications for location-specific incident alerts.

The status page covers Cloud (by location) and Robot infrastructure. During an incident, check the status page before diagnosing your own stack.

## Robot server monitoring

Robot dedicated servers have basic built-in monitoring configurable via the Robot panel:

- **PING monitoring**: Hetzner sends ICMP probes to the server's public IP. If unreachable for a threshold period, an alert email is sent to the account contact.
- **TCP port check**: optional additional check on a specified port.

This is minimally sufficient for "is the server reachable" alerting. For everything else — service health, application metrics, log alerts — run your external observability stack on Robot servers the same way as Cloud servers.

## Alerting approach

Hetzner provides no alerting. Build alerting into your external observability stack:

| Signal | Recommended alert |
| --- | --- |
| CPU sustained > 80% for 10 min | Scale up or investigate; scheduled jobs competing with traffic |
| Memory > 85% (Node Exporter) | Risk of OOM kill; add swap or scale |
| Disk usage > 80% | Add volume or prune data before full |
| Network egress rate spike | Potential data exfil or traffic surge; verify against expected pattern |
| Server ICMP unreachable | Immediate page; correlate with Cloud Status |
| SSH login from unexpected IP | Potential unauthorized access; investigate immediately |
| LB health check failure | Backend server unhealthy; rotate or investigate |

## Billing model

Hetzner Cloud billing is **hourly, capped at a monthly maximum**.

- A server running for a full month pays exactly the monthly price shown on the pricing page.
- A server running for 5 hours pays 5× the hourly rate (= monthly_price / 672 hours × 5), never more than the monthly cap.
- Deletion before month-end charges only for the hours run.

Implications:

- Short-lived workloads (CI jobs, batch processing) pay only for runtime — no idle minimum.
- Shutdown (powered-off) servers still accrue charges; the server is reserved and the IP is held. Delete rather than power off for true cost elimination.
- Snapshots continue to be charged for their stored size even after the source server is deleted.

## Traffic allowances and egress billing

Each Hetzner Cloud server and Load Balancer includes a monthly traffic allowance:

| Server / component | Included traffic |
| --- | --- |
| CX11 | 20 TB/mo |
| CPX11 | 20 TB/mo |
| CCX13 | 20 TB/mo |
| CAX11 | 20 TB/mo |
| LB11 | 5 TB/mo |
| LB21 | 20 TB/mo |
| LB31 | 100 TB/mo |

(Exact allowances vary by type; verify at hetzner.com/cloud/pricing.)

**Traffic pooling**: traffic allowances across all servers in the same project are pooled. A low-traffic server's unused allowance covers a high-traffic server's overage before charges apply.

**Overage rate**: ~€1.19/TB (as of 2026-05, verify current rate).

Traffic that does not count against the allowance:

- Traffic between servers on a Hetzner Private Network.
- Traffic between a server and Hetzner Storage Box within the same location.
- Traffic between a server and Hetzner Load Balancer backends on the Private Network.

Traffic that does count:

- All public internet egress from a server's public IP.
- Load Balancer to its public IP (client-facing traffic).

**Inbound traffic**: not billed.

## IPv4 surcharge

Public IPv4 addresses assigned to Cloud servers cost **€0.001/hr = ~€0.72/mo** each. This is billed in addition to the server cost.

Minimization strategies:

- Suppress public IPv4 on servers that communicate only via Private Network (`ipv4_enabled = false` in Terraform).
- Route external traffic through a Load Balancer (1 public IPv4 at the LB, hidden backends) rather than one public IP per server.
- Use IPv6 for services where all clients can reach IPv6 routes.
- Floating IPs: charged at €1.19/mo when unassigned; €0 extra overhead when assigned (the server's IPv4 cost applies).

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Relying on Hetzner's built-in metrics alone | No memory metrics, no alerting, 30-day retention limit. You're blind during incidents. |
| Powered-off servers left running for months | Same cost as a running server; delete if not needed. |
| No traffic pooling awareness | Team assumes servers have independent limits; one high-traffic server exceeds the project pool and triggers overage charges. |
| Public IPv4 on every server in a fleet | €0.72/mo × 50 servers = €36/mo; 95% of those servers only need Private Network access. |
| No egress monitoring | Traffic overage appears on the invoice at month-end with no early warning. Monitor egress rate daily. |
| Snapshots never pruned | A graveyard of old snapshots at €0.01/GB/mo accumulates into meaningful cost. |
| External log shipper pushing to the public internet | Routes through the server's traffic allowance and incurs latency. Use Private Network to a log collector in the same zone. |

## Observability defaults

- Node Exporter on every server, scraped via Private Network (no public IP exposure).
- Alerting on CPU, memory, disk, and ICMP reachability — minimum viable set.
- Log forwarding: ship application logs and `/var/log/auth.log` to your log platform.
- LB health check failure alert wired to on-call channel.
- Traffic usage alert at 80% of the project's combined allowance — not per-server.

## Cost considerations

- Hetzner costs are dramatically lower than AWS, GCP, or Azure at equivalent specs. A CCX13 (2 dedicated vCPU, 8 GB) is ~€9.90/mo versus an AWS `m7g.medium` at ~$30/mo (plus EBS, data transfer).
- The main cost-amplifiers on Hetzner: unnecessary public IPv4 addresses, snapshots accumulation, and traffic overage.
- Do a monthly review of the Cloud console traffic meter, snapshot list, and server list. Prune anything inactive.
- For large-bandwidth workloads (CDN origin, video streaming), assess whether Hetzner's traffic allowance model is cheaper than Cloudflare R2 or Backblaze B2's free egress options.

## IaC hints

- Traffic and billing are not manageable via Terraform; query via the hcloud API programmatically (`GET /servers/{id}/metrics?type=network`).
- Automate snapshot pruning with a cron job or GitHub Actions workflow calling `hcloud image delete <id>` for images older than N days.
- Terraform `hcloud_server` `public_net { ipv4_enabled = false }` to suppress IPv4.
- For Prometheus Node Exporter provisioning: use Ansible `hetzner.hcloud.hcloud_server` to provision the server, then `ansible.builtin.apt` + `ansible.builtin.systemd` for the exporter.

## Verification checklist

- [ ] External observability stack deployed; Node Exporter or equivalent agent on every server.
- [ ] Memory, disk, and process-level metrics visible in dashboards (hcloud API does not cover these).
- [ ] Alerts defined for CPU, memory, disk, network, and server reachability.
- [ ] LB health check failure alert wired to on-call channel.
- [ ] SSH login alerting from unexpected origins active.
- [ ] Traffic allowance usage monitored; alert at 80% of project pool.
- [ ] IPv4 count minimized; all unnecessary public IPs suppressed.
- [ ] Snapshot lifecycle managed; stale snapshots pruned monthly.
- [ ] Hetzner Cloud Status RSS or notification subscription active for locations in use.
- [ ] Monthly cost review scheduled; billing breakdown per project understood.
