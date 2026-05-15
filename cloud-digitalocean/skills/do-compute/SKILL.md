---
name: do-compute
description: Choose, design, or harden DigitalOcean compute — Droplets (Basic, General Purpose, CPU-Optimized, Memory-Optimized, Storage-Optimized, GPU), App Platform, DOKS (DigitalOcean Kubernetes), Functions (Serverless), and Snapshots. Use when picking a runtime, sizing capacity, configuring autoscaling, or reviewing a compute architecture for cost, latency, or availability.
---

# DigitalOcean Compute

## When to use

- Choosing between a Droplet, App Platform, DOKS, or Functions for a new workload.
- Right-sizing a Droplet family or selecting a Premium AMD / Premium Intel plan.
- Configuring DOKS node pools, autoscaling, or cluster upgrades.
- Designing App Platform services with autoscaling and build pipelines.
- Reviewing snapshot strategies for backup and restore coverage.
- Auditing the IAM surface attached to compute (PAT scoping, project membership).

## Decision tree

1. **Event-driven, short-lived, stateless, irregular load** → Functions (Serverless). No infrastructure to manage; billed per invocation.
2. **HTTP service with no Kubernetes investment — managed build pipeline, simple autoscaling** → App Platform. Pick Basic for low-traffic, Professional for persistent workers or higher concurrency.
3. **Container fleet with sidecars, custom networking, GitOps, multi-tenant concerns** → DOKS. Managed control plane, node pools, integrated load balancer provisioning.
4. **Long-running VM, custom kernel, GPU workload, license-restricted software, database self-hosting** → Droplet. Pick family by workload shape (see below).
5. **Burstable dev or very low-traffic staging** → Basic Droplet (shared vCPU). Never use shared vCPU for production CPU-sensitive work.

## Droplet families

| Family | When to pick |
| --- | --- |
| Basic (shared vCPU) | Dev, CI runners, low-traffic staging. Never prod for compute-sensitive paths. |
| General Purpose | Balanced CPU-to-memory ratio; the default for most production web services and APIs. |
| CPU-Optimized | Video encoding, scientific computing, compilation, high-traffic reverse proxies. |
| Memory-Optimized | In-memory caches, real-time analytics, large JVM heaps, self-hosted databases with large working sets. |
| Storage-Optimized | High-IOPS self-hosted databases, time-series, search engines — NVMe-backed local storage. |
| GPU | Machine learning inference and training. Available in selected regions; price per hour is significant — reserve only when actively training. |
| Premium AMD / Premium Intel | Drop-in for General Purpose when you need deterministic single-core performance (e.g. latency-sensitive game servers, high-frequency trading data feeds). |

## App Platform defaults

- **Build:** pin the builder version; do not rely on auto-detected versions drifting on your behalf.
- **Autoscaling:** set `min_instance_count` to at least 2 for any production HTTP service — App Platform health checks will route around a failed instance only if another exists.
- **Environment variables:** inject secrets via the App Platform encrypted environment variable UI or pull from a Vault / Secrets Manager at startup. Never commit secrets in the App Spec YAML.
- **Deploy on push:** gate on a CI passing check before the App Platform deploy fires — use the `deploy_on_push.enabled = false` flag and trigger via `doctl apps create-deployment` from your CI.
- **Static sites:** prefer App Platform static sites over Droplets running nginx for pure frontend workloads; zero server management, global CDN-backed by default.

## DOKS defaults

- **Node pools:** separate node pools by workload class (e.g. `system` pool for cluster-critical pods, `app` pool for your services, `gpu` pool if applicable). Never mix system and application workloads on the same pool.
- **Autoscaling:** enable cluster autoscaler per pool with a non-zero `min_nodes` so the cluster never scales to zero and leaves critical pods unscheduled.
- **Control plane:** managed by DigitalOcean; no etcd access. Plan around this for disaster recovery — cluster backup via Velero to Spaces is the standard approach.
- **Kubernetes version:** stay within one minor version of the current stable release. DOKS end-of-life for older Kubernetes versions follows upstream; lagging versions eventually lose support.
- **Node size:** General Purpose Droplets as the default node type; CPU-Optimized for compute-heavy workloads; Memory-Optimized for in-cluster caches or analytics.
- **Load balancer:** DOKS provisions a DigitalOcean Load Balancer per `Service` of type `LoadBalancer`. Restrict to one per cluster entry point; use an internal nginx ingress + a single external LB for all HTTP traffic.
- **DOKS networking:** VPC-native node-to-node traffic by default. Pods use private IPs within the node's VPC. Do not expose the Kubernetes API server publicly unless operationally required; use the restricted API server endpoint option.

## Functions (Serverless) defaults

- **Namespace isolation:** one namespace per environment (dev / stage / prod). Functions in the same namespace share secrets and packages.
- **Runtime:** pin the runtime version (e.g. `python:3.11`, `nodejs:18`) — `latest` resolves at build time and will break after upstream updates.
- **Concurrency:** Functions scale automatically but have a per-namespace concurrency ceiling. Profile cold-start impact for latency-critical paths — Functions are not a replacement for a persistent HTTP service.
- **Secrets:** inject via namespace-level secrets rather than hardcoding in the function body. Use `doctl serverless secrets set` in CI.

## Snapshots

- **Automated Droplet backups:** enable weekly backups (DigitalOcean's managed backup — 4 snapshots retained) for any stateful Droplet. Supplement with manual snapshots before significant changes.
- **Volume snapshots:** snapshot persistent volumes before any resize or migration. Volume snapshots are incremental after the first.
- **DOKS snapshots:** Velero + Spaces is the standard; DigitalOcean does not provide first-party DOKS etcd snapshots to customers.
- **Snapshot lifecycle:** delete snapshots older than your retention window via `doctl compute snapshot delete` in a scheduled script. Snapshots cost $0.06 / GB / month — orphaned snapshots accumulate silently.
- **Cross-region restore drills:** periodically restore a Droplet from snapshot in a secondary region. The restore process is not zero-time; measure it, not assume it.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Basic shared-vCPU Droplet in production | CPU steal during noisy-neighbor events causes latency spikes. Use General Purpose or CPU-Optimized. |
| Single-node DOKS cluster | Control-plane upgrade or node replacement = cluster downtime. Min 3 nodes for prod. |
| App Platform with `min_instance_count=1` | A rolling deploy or health-check failure removes your only instance. Set to at least 2. |
| Snapshots as the only backup strategy without restore drills | Untested restores fail in the worst moment. Quarterly restore drill. |
| PAT with write scope stored in App Platform env vars in plaintext | Leaked via app logs or environment dump. Use scoped read-only PATs; store secrets in an encrypted vault. |
| GPU Droplet left running when idle | GPU plans run $2–$10+ per hour depending on size. Power off or snapshot when not training. |
| `:latest` container image tag in DOKS | Rollback is archaeology; image may have changed between pull and pin. Tag with git SHA. |

## Security defaults

- Run DOKS workloads with network policies (Cilium or Calico) — by default, all pods can reach all pods. Network policies are your east-west firewall.
- Use DigitalOcean's container registry vulnerability scanning before deploying images to DOKS.
- DOKS nodes have no public SSH access by default. Keep it that way — use `kubectl exec` or a bastion pattern for node-level debugging.
- App Platform pulls from your registry or GitHub; ensure the connected GitHub app has minimal repo scope.
- Restrict the DOKS API server endpoint; do not expose `0.0.0.0/0` on port 443 for the API server.

## Observability defaults

- Enable the DigitalOcean Metrics Agent on every Droplet for CPU, memory, disk, and bandwidth graphs.
- For DOKS, install the DigitalOcean Kubernetes Monitoring stack (Prometheus + Grafana via the marketplace) or forward metrics to your existing observability stack.
- App Platform exposes runtime logs via `doctl apps logs <app-id>` — ship these to a log aggregator (Papertrail, Logtail, or a self-hosted Loki on DOKS) for retention beyond 7 days.
- Wire at least one alert policy per Droplet or service: CPU threshold, memory threshold, and disk usage.

## Cost considerations

- **Droplet vs managed service:** self-hosting Postgres on a Memory-Optimized Droplet is meaningfully cheaper than a Managed Database cluster of similar spec — but you own HA, backups, and upgrades. Be honest about the operational cost.
- **Reserved Droplets:** DigitalOcean offers 1-year and 2-year Reserved Droplet commitments (25–40% discount). Buy only after 3+ months of stable usage at a predictable size.
- **App Platform:** per-container billing with no idle Droplet cost. Cheaper than a Droplet for workloads that spend significant time idle.
- **Snapshots:** $0.06 / GB / month. Prune old snapshots on a schedule.
- **GPU Droplets:** power off between jobs. A stopped GPU Droplet still charges for reserved resources — delete and restore from snapshot if idle for more than a few days.
- **Data transfer:** DigitalOcean bills outbound transfer above the free tier (~$0.01 / GB). Spaces CDN reduces origin egress for static assets.

## IaC hints

- Terraform: `digitalocean_droplet`, `digitalocean_kubernetes_cluster` (with `digitalocean_kubernetes_node_pool`), `digitalocean_app` (App Spec), `digitalocean_function` resources.
- Provider: `digitalocean/digitalocean` >= 2.40.
- Use `digitalocean_project_resources` to assign every Droplet, cluster, and database to a project for cost and access scoping.
- For DOKS, export the kubeconfig via `doctl kubernetes cluster kubeconfig save <cluster-id>` post-apply; do not store the kubeconfig in Terraform state.

## Verification checklist

- [ ] Droplet family chosen against the workload decision tree, not by price alone.
- [ ] DOKS cluster has at least 3 nodes across separate underlying hosts; autoscaling configured with non-zero min.
- [ ] App Platform min instance count >= 2 for any production HTTP service.
- [ ] Snapshot strategy defined with restore drill scheduled.
- [ ] No shared-vCPU Droplet in production for CPU-sensitive paths.
- [ ] Container images tagged with git SHA in DOKS, not `:latest`.
- [ ] GPU Droplets have power-off automation when idle.
- [ ] All compute resources assigned to a DigitalOcean Project for billing visibility.
