---
name: vultr-compute
description: Choose, design, or harden Vultr compute — Cloud Compute (Regular, High Performance, High Frequency, High Optimized AMD/Intel), Cloud GPU (NVIDIA fractional and dedicated), Bare Metal, Vultr Kubernetes Engine (VKE), Marketplace apps, ISO uploads, snapshots, startup scripts. Use when picking an instance plan, sizing capacity, designing a Kubernetes cluster, or auditing compute configuration.
---

# Vultr Compute

## When to use

- Choosing a Cloud Compute plan family or Bare Metal for a new workload.
- Sizing a VKE cluster (node pools, autoscaling, version management).
- Selecting a Cloud GPU plan for inference, training, or rendering.
- Configuring startup scripts, cloud-init, or Marketplace apps.
- Designing a snapshot strategy for stateful instances.
- Auditing SSH key assignment, firewall attachment, and VPC attachment on existing instances.

## Decision tree

1. **HTTP service or API, predictable throughput, no GPU** → Cloud Compute High Performance (AMD/Intel) behind a Load Balancer.
2. **Latency-critical, high-clock-speed single-threaded workload** → Cloud Compute High Frequency.
3. **Cost-optimized general workload or dev/test** → Cloud Compute Regular.
4. **CPU-bound batch (transcoding, analytics) or database host** → Cloud Compute High Optimized AMD or Intel — dedicated vCPU, no noisy neighbor.
5. **LLM inference, GPU-accelerated ML, 3D rendering** → Cloud GPU (NVIDIA A100 / L40S fractional or dedicated, A16 for inference). Note: GPU plans available in a subset of regions — verify before committing.
6. **Physical isolation, specific kernel, licensed OS, high-density storage** → Bare Metal. Note: limited region availability; no live migration.
7. **Containerized workload with orchestration, autoscaling, Helm** → VKE (Vultr Kubernetes Engine).
8. **Rapid provisioning of a known stack (LAMP, WordPress, Ghost, etc.)** → Marketplace app — starts with a pre-configured OS image.

## Defaults

### Cloud Compute

- **Plan family default:** High Performance AMD (`vhp` plans) — best price-performance ratio for general web workloads.
- **OS:** Debian 12 or Ubuntu 24.04 LTS. Never use "Upload ISO" in production without a tested build pipeline that rebuilds the image.
- **VPC 2.0:** Always attach to a VPC 2.0 network. Deploy without a VPC only for the specific instance that terminates public traffic; back-of-house instances must be private.
- **Firewall Group:** Attach a named Firewall Group on every instance — never rely on Vultr's default open posture. Default-deny inbound; allow only what the instance needs.
- **Backups:** Enable on every stateful instance (hourly automated backup window). For a pure ephemeral compute tier, skip backups — but only if state truly lives elsewhere.
- **IPv6:** Enable by default in regions that support it; IPv6 addresses are free and useful for monitoring and dual-stack clients.
- **SSH keys:** Attach at least one SSH key at provision time. Disable password authentication via startup script or cloud-init immediately after first boot.
- **Startup script / cloud-init:** Use for OS hardening (disable password auth, install audit tools, set hostname, configure NTP) rather than manual post-provision steps.

### Cloud GPU

- GPU instance availability varies by region. As of 2026-05, `ewr` (New Jersey), `ord` (Chicago), `lax` (Los Angeles), and `fra` (Frankfurt) have GPU plans. Verify before designing a GPU-dependent architecture for a specific region.
- NVIDIA A100 (80 GB, full card) for large-model training; NVIDIA A16 for multi-tenant inference (fractional). L40S for rendering + inference that benefits from Ada lovelace tensor cores.
- GPU instances are expensive idle. Build auto-shutdown scripts or Terraform `null_resource` destroy hooks for batch GPU workloads. The instance bills by the hour whether or not the GPU is computing.
- Always mount training data from Object Storage or Block Storage — do not bake large datasets into the OS disk.

### Bare Metal

- Region availability is narrower than Cloud Compute. Check `vultr-cli bare-metal plan list` or the Terraform data source before designing for a specific region.
- No live migration — Bare Metal instances cannot be moved between hypervisor hosts. Plan for maintenance windows.
- Boot from a custom ISO only if you have a repeatable OS build pipeline (Packer + Vultr plugin).
- Firewall Groups still apply at the network edge, even for Bare Metal.
- Backups: available for most Bare Metal plans; enable unless the workload is designed to be fully rebuilt from IaC.

### VKE (Vultr Kubernetes Engine)

- **Kubernetes version:** Pin to the latest supported minor version in IaC. Vultr supports N-2 minor versions; older clusters stop receiving patches.
- **Node pools:** Use at least two node pools — one for system workloads (small), one for application workloads. Enable autoscaling on the application pool.
- **Node plan:** High Performance or High Optimized AMD for production workloads. Do not use Regular plans for node pools that run I/O-sensitive services.
- **Network:** VKE automatically creates and attaches a VPC. Ensure the VPC CIDR does not overlap with any VPC you will peer or route between.
- **Load Balancer:** VKE provisions a Vultr Load Balancer automatically when a `Service` of type `LoadBalancer` is created. Each LB costs separately — consolidate exposed services behind an ingress controller (NGINX, Traefik) to minimize LB count.
- **Storage:** Use the Vultr CSI driver (pre-installed on VKE clusters) for PersistentVolumes backed by Block Storage (NVMe). Do not use `hostPath` for anything persistent.
- **Firewall:** VKE node pools use a managed Firewall Group that permits necessary Kubernetes traffic. Do not manually add rules that override cluster control-plane connectivity.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Regular plan "for cost" on a database host | Shared vCPU means noisy-neighbor CPU throttling. Use High Optimized for any stateful workload. |
| Instance without a Firewall Group | Default posture is open. Any port reached by your application is reachable from the internet. |
| Password auth left enabled | Password brute-force is the leading cloud account compromise vector. SSH key-only always. |
| GPU instance running 24/7 for batch work | GPU plans are $600–$3,000+/mo. Terminate when the job finishes; re-provision via IaC for the next run. |
| Bare Metal in a region that doesn't have it | Plan breaks at provision time — verify availability first. |
| VKE without autoscaling on the app pool | Traffic spikes exhaust node capacity with no relief. Enable autoscaling with sane min/max. |
| Manual post-provision steps via SSH | Undocumented drift. Everything reproducible goes in startup script or cloud-init. |
| Snapshot as the only backup | Snapshots capture disk state at a point in time; automated Backups provide a retention window. Use both for production stateful instances. |

## Security defaults

- Attach a Firewall Group with default-deny inbound on every instance at provision time.
- SSH key-only authentication; disable password auth in cloud-init or startup script.
- No public IP on back-of-house instances that do not need to accept public connections — use private VPC 2.0 IPs for internal communication.
- Never store credentials, API keys, or secrets in startup scripts in plaintext. Use environment variables injected at provision time from a secrets store, or pull from Object Storage at boot.
- For VKE, ensure RBAC is enabled (it is by default), use `kubectl` over the cluster's kubeconfig and rotate it regularly.

## Observability defaults

- Enable Vultr Metrics on every Cloud Compute and Bare Metal instance (on by default; verify via API/CLI after provision).
- Configure at least one Alert rule per production instance — CPU % and bandwidth are the two most useful built-in signals.
- For VKE, deploy the Prometheus / Grafana stack via Helm and point it at the node metrics exporter (already present in VKE nodes).
- Ship instance logs to an external aggregator (Datadog, Grafana Loki, or OpenSearch) using the vendor's agent — Vultr has no managed log aggregation service.

## Cost considerations

- **Bandwidth pool:** All Cloud Compute instances in an account share a monthly bandwidth pool. Bare Metal bandwidth is billed separately per instance. GPU instances have their own bandwidth allotment. Review `vultr-cli billing bandwidth` to see pool usage and overage exposure.
- **Hourly billing with monthly cap:** Instances bill per hour with a monthly ceiling. A running instance that is only used for testing still accumulates cost. Destroy instances that are not needed; snapshot them first if you want a restore point.
- **GPU cost discipline:** GPU plans do not pause when idle. Model batch GPU jobs, build job-completion triggers that destroy the instance, and re-provision from a snapshot or IaC the next time.
- **Reserved instances:** Vultr does not offer Reserved Instances or Savings Plans as of 2026-05. Cost commitments happen through Vultr credits or sales agreements for large accounts — no native pricing mechanism analogous to AWS RIs.
- **Region pricing variation:** Cloud Compute prices are largely consistent across regions, but Bare Metal and GPU plans differ by region. Always verify the plan price for the specific region.

## IaC hints

- Terraform resource: `vultr_instance` for Cloud Compute, `vultr_bare_metal_server` for Bare Metal, `vultr_kubernetes` for VKE.
- Provider: `vultr/vultr` ≥ 2.21.
- Use `data "vultr_plan"` and `data "vultr_region"` data sources to look up valid plan and region slugs rather than hard-coding opaque values.
- For GPU instances, use `data "vultr_plan"` with `type = "vgpu"` filter to find valid GPU plan IDs.
- Startup script content should be managed as a `vultr_startup_script` resource and referenced by ID on `vultr_instance`.
- Snapshot lifecycle: `vultr_snapshot_from_url` or `vultr_snapshot` for manual snapshots; combine with a `time_rotating` resource and `null_resource` to automate periodic snapshot rotation.

## Verification checklist

Before declaring a compute design complete:

- [ ] Instance plan family justified against the decision tree, not preference.
- [ ] Firewall Group with default-deny attached at provision time (not after).
- [ ] Password authentication disabled; SSH key(s) attached.
- [ ] VPC 2.0 network attached on every instance; private IPs used for internal communication.
- [ ] Backups enabled on stateful instances; snapshot strategy documented.
- [ ] For GPU instances: shutdown / destroy automation built for batch workloads.
- [ ] For VKE: node pool autoscaling configured; CSI driver used for PVs; ingress controller in front of multiple services.
- [ ] At least one alert configured per production instance (CPU / bandwidth).
- [ ] Regional availability verified for Bare Metal or GPU plans before designing around them.
