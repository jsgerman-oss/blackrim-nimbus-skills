---
name: scaleway-compute
description: Choose, design, or harden Scaleway compute — Instances (Development / General Purpose / Compute Optimized / Enterprise / GPU / ARM), Elastic Metal (Bare Metal), Serverless Containers, Serverless Jobs, Serverless Functions, Kapsule (Kubernetes), Kosmos (multi-cloud Kubernetes), Apple Silicon (Mac mini M1). Use when picking a runtime, sizing capacity, configuring autoscaling, or reviewing a compute architecture for cost / latency / availability.
---

# Scaleway Compute

## When to use

- Designing a new workload and choosing between serverless, container, Kubernetes, and VM compute.
- Tuning Serverless Container memory / concurrency / scaling, or diagnosing cold-start latency.
- Right-sizing Instance types or Elastic Metal configurations.
- Deciding Serverless Containers vs Kapsule for a containerized workload.
- Reviewing autoscaling and capacity for Kapsule node pools.
- Auditing IAM Application permissions attached to compute workloads.
- Selecting the right Scaleway region for latency or data residency requirements.

## Decision tree

1. **Event-driven, short-lived, irregular load, stateless** → Serverless Functions (lightweight) or Serverless Jobs (longer-running, batch).
2. **Long-running HTTP service, container-friendly, no Kubernetes investment** → Serverless Containers behind a custom domain.
3. **Container fleet with sidecars, service mesh, GitOps, multi-tenant** → Kapsule (managed Kubernetes on Scaleway).
4. **Multi-cloud Kubernetes with nodes on other clouds or on-prem** → Kosmos (extends Kapsule externally).
5. **GPU / ML training / rendering** → GPU Instances (`gpu_3070_s`, `render-s`, or H100 range) — Elastic Metal GPU for dedicated hardware.
6. **Bare metal performance, predictable IOPS, license-restricted OS, compliance isolation** → Elastic Metal.
7. **macOS CI / app signing / iOS build farm** → Apple Silicon (Mac mini M1, `apple-m1-8c16g`).
8. **General-purpose VM, web server, database host, dev environment** → Instances (GP1 or DEV1 for small, POP2 for compute-heavy, ENT1 for enterprise-grade).

## Defaults

### Serverless Containers

- Region: `fr-par` default; consider `nl-ams` or `pl-waw` for GDPR residency closer to users.
- Memory: start at 256 MB; profile with real traffic before committing. Max 12 GB.
- Min scale: `0` for cost savings; set to `1` if cold-start latency affects user experience (time-to-first-byte SLA).
- Max scale: set explicitly — unbounded scale is an unbounded bill. Start at 20 and observe.
- Port: expose the port your container actually listens on; default `8080` if unset.
- Secrets: inject via Scaleway Secret Manager references, not literal env vars in the deploy config.
- Privacy: `public` only if the endpoint must be unauthenticated; `private` routes via Scaleway Private Networks.
- Health check: your container must respond to `GET /` (or a custom path) within the readiness timeout.

### Serverless Jobs

- Runtime: container image — any language, any binary.
- Timeout: set to observed max duration × 1.5; Scaleway enforces a hard max per tier.
- Cron: available natively for scheduled jobs; use ISO 8601 cron syntax.
- Resources: start small (70 mVCPU / 128 MB), scale up only after profiling.
- Idempotency: design every job to be safely retried — Scaleway may replay on transient failure.

### Serverless Functions

- Runtime: Node.js 22, Python 3.12, Go 1.21, PHP 8.3 — pick the most current supported version.
- Memory: 128 MB minimum; most lightweight functions need no more than 256 MB.
- Privacy: prefer `private` unless the function is a public webhook endpoint.
- Cold start: expect ~200 ms–1 s for Node/Python at 128 MB; factor this into latency budgets.
- Handler: follow the Scaleway function handler signature strictly — it differs from AWS Lambda.

### Kapsule (Managed Kubernetes)

- Kubernetes version: always deploy on the latest stable minor version Scaleway supports; pin in IaC and schedule regular upgrades.
- Node pools: use node pool autoscaling (min/max replicas) rather than fixed counts. Mix pool types — a general-purpose pool for everyday workloads, a GPU pool for ML inference.
- Node type: `PRO2-S` or `PRO2-M` for general-purpose production; `DEV1-M` only for non-prod.
- Container Network Interface: Cilium (default on new clusters) for eBPF-based policy and observability. Do not revert to flannel on new deployments.
- Private Networks: attach every Kapsule cluster to a Private Network — node-to-node traffic stays off the public internet.
- Control plane logging: enable Kubernetes audit logs; ship to Cockpit for retention and alerting.
- RBAC: on by default, never disable. Use Scaleway IAM to gate `kubeconfig` download per Project Application.
- Kapsule add-ons: install cert-manager, external-dns, and metrics-server from the Scaleway App Marketplace before workloads land.

### Kosmos (Multi-cloud Kubernetes)

- Use Kosmos when you need worker nodes outside Scaleway (other clouds, on-prem, edge) while keeping the Kapsule control plane.
- External nodes join via a Kilo-based WireGuard VPN tunnel — plan MTU and firewall rules accordingly.
- Keep control-plane-sensitive workloads (etcd, admission webhooks) on Scaleway nodes; only move stateless workloads to external nodes.

### Instances

- Type selection: `DEV1-S/M/L` for dev/test (burstable); `GP1-*` / `POP2-*` for production general-purpose; `C2M-*` for compute-intensive; `ENT1-*` for large memory-optimized workloads.
- Image: latest Debian 12 or Ubuntu 24.04 LTS from Scaleway marketplace — not custom images without a build pipeline.
- Block Storage: root volume is Local Storage (fast NVMe) or SBS — attach a separate SBS volume for data so the root stays disposable.
- SSH: disable password auth. Use SSH keys registered in your Scaleway Project; prefer SSM-style access via Cockpit terminal where available.
- Cloud-init / user-data: harden with: disable root login, configure fail2ban or similar, enable unattended-upgrades.
- Flexible IPs: attach only if the instance serves public traffic. Detach and re-attach allows drain-and-replace without DNS changes.

### Elastic Metal (Bare Metal)

- Commitment: Elastic Metal bills hourly but some SKUs have minimum rental periods — confirm before ordering.
- OS: Scaleway-managed (Ubuntu, Debian, Proxmox) vs manual install. Prefer managed for patching simplicity.
- RAID: configure at OS level. Scaleway does not manage RAID; plan the storage topology before provisioning.
- Use case: GPU-dense ML, licensed software (per-core pricing), workloads requiring dedicated hardware for compliance (HDS, PCI-DSS).

### Apple Silicon (Mac mini M1)

- Minimum rental is 24 hours — not suitable for ephemeral CI jobs shorter than that.
- Use for: macOS app signing, iOS builds, Xcode, notarization pipelines.
- Remote access: VNC or screensharing over a Scaleway Private Network — avoid exposing macOS remotely on public IPs.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Serverless Container min-scale 0 with a user-SLA on first request | Cold start shows as latency spike. Set min-scale 1 or pre-warm via a scheduled ping. |
| Kapsule node pool with no autoscaler | Manual scaling under load means manual incidents. Always set min/max. |
| Instances with root volume holding application data | Root is ephemeral in the "replace the instance" model. Data volume separate. |
| GPU Instance left running idle between training jobs | GPU time bills regardless. Stop/snapshot between jobs or use Serverless Jobs for batch ML. |
| `DEV1-*` instances for production traffic | Burstable CPU credits throttle under sustained load. GP1 or POP2 for prod. |
| Hard-coded Scaleway API tokens in container env | Secrets Manager + Secret Manager env injection at deploy time. |
| Kapsule without Private Networks | Node traffic crosses the public internet. Private Network required. |
| Kosmos external nodes without WireGuard MTU tuning | Packet fragmentation causes mysterious connection resets. Tune MTU on join. |

## Security defaults

- Every workload gets an **IAM Application** scoped to its Scaleway Project with a least-privilege Policy — never use the root Organization API key for workloads.
- Serverless Containers and Functions in `private` mode unless explicitly public; authenticate calls via Scaleway JWT tokens or a signed URL.
- Secrets injected at runtime from Secret Manager; never literal strings in deploy configuration.
- Kapsule RBAC on; Kubernetes service accounts per workload namespace — no shared `default` service account tokens in production pods.
- Instance SSH keys registered per-Project; root login disabled; SSH port should be firewalled except from known management IPs or Private Network peers.
- Container images scanned before push; use Scaleway Container Registry with vulnerability scanning enabled.

## Observability defaults

- Cockpit enabled on every Project; Scaleway-managed metrics for Instances, Kapsule, and Serverless auto-populate.
- Custom application metrics via OpenTelemetry → Cockpit remote write (Prometheus-compatible endpoint).
- Structured JSON logs with a request-id field; ship to Cockpit Loki for correlation.
- One Cockpit alert per "thing that wakes someone up": Serverless error rate, Kapsule node NotReady, Instance CPU saturation, Elastic Metal disk fill rate.
- Kapsule: enable control-plane audit log shipping; set up `kube-state-metrics` and `node-exporter` via Helm in Cockpit dashboards.

## Cost considerations

- Serverless Containers and Functions: billed per request and per GB·s of memory. Scale-to-zero during idle periods (nights, weekends) eliminates the idle bill entirely.
- Kapsule: control plane is free; you pay for nodes (same Instance pricing). Right-size node pools; don't over-provision for burst that hasn't happened yet.
- Elastic Metal: hourly but often pricier per unit than Instances — reserve only when bare-metal isolation or hardware access is a hard requirement.
- GPU Instances: expensive. Schedule training jobs; shut down after completion; use Serverless Jobs for infrequent batch GPU workloads.
- Apple Silicon: minimum 24-hour billing. Batch CI builds to fill the rental window.
- Snapshot costs are per-GB — purge stale snapshots quarterly.
- Public egress (data transferred out of Scaleway to the internet) is billed; Private Network traffic between resources in the same region is free.

## IaC hints

- Terraform `scaleway/scaleway` ≥ 2.45: `scaleway_container`, `scaleway_k8s_cluster`, `scaleway_k8s_pool`, `scaleway_instance_server`, `scaleway_baremetal_server`, `scaleway_function`.
- `scw` CLI: `scw container create`, `scw k8s cluster create`, `scw instance server create` for bootstrapping; automate everything beyond initial setup in Terraform.
- Kapsule kubeconfig: retrieve with `scw k8s kubeconfig install <cluster-id>` — do not store the kubeconfig in IaC state; rotate via `scw k8s kubeconfig install --force`.
- Pulumi `pulumiverse/scaleway`: mirrors the Terraform resource model; use when the team prefers TypeScript/Python over HCL.
- For GitOps on Kapsule: use Flux or ArgoCD installed via Helm chart. Store HelmRelease manifests in git; Kapsule reconciles.

## Verification checklist

Before declaring a compute design complete:

- [ ] Runtime choice justified against the decision tree, not preference.
- [ ] IAM Application scoped to Project with a least-privilege Policy; no root Organization key in production.
- [ ] Serverless min-scale and max-scale set explicitly; cold-start impact acknowledged.
- [ ] Kapsule node pool autoscaling configured with realistic min/max; Private Networks attached.
- [ ] At least one Cockpit alert wired to a real notification channel.
- [ ] Cost-per-request or cost-per-hour sketched and within target.
- [ ] Secrets from Secret Manager, not literal env vars.
- [ ] Region chosen for data residency and latency requirements — not just default.
- [ ] Rollback path is one IaC change away (container revision, image tag, node pool scale).
