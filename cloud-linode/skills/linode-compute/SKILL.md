---
name: linode-compute
description: Choose, design, or harden Linode compute — Compute Instances (Nanode / Shared / Dedicated / High Memory / Premium / GPU), Linode Kubernetes Engine (LKE), Bare Metal, Marketplace apps. Use when picking an instance plan, sizing a Kubernetes cluster, configuring autoscaling node pools, or reviewing a compute architecture for cost and availability.
---

# Linode Compute

## When to use

- Picking an instance plan for a new workload (Nanode vs Shared vs Dedicated vs High Memory vs GPU).
- Designing or sizing an LKE cluster — node pool types, autoscaling, HA control plane.
- Deciding when Bare Metal is justified vs a Dedicated instance.
- Reviewing autoscaling, placement, and distribution configuration.
- Auditing SSH access, root login posture, and instance-level firewall attachment.
- Evaluating Marketplace apps (when and why to prefer manual provisioning instead).

## Decision tree

1. **Low-traffic app, dev/test, < 2 GB RAM budget** → Nanode 1 GB or Shared 2 GB plan. Note: Shared plans contend on CPU — unacceptable for latency-sensitive prod.
2. **General-purpose production service, predictable load** → Dedicated CPU instance (`dedicated-*`). Guaranteed vCPUs, no noisy-neighbor CPU.
3. **Database, JVM workload, in-memory cache needing > 32 GB RAM** → High Memory plan (`highmem-*`). RAM optimized; CPU count is lower relative to RAM.
4. **AI/ML inference, GPU-accelerated rendering** → GPU plan (`g6-*`). Linode GPU instances use NVIDIA GPUs; available in select regions.
5. **Hardware-pinned licensing, compliance requiring dedicated hardware, max single-instance performance** → Bare Metal. Longer provisioning time (minutes to hours). Not resizable.
6. **Containerized services, GitOps, horizontal scaling** → LKE. Use HA control plane for prod; add autoscaling node pools.
7. **Quick deployment of a known stack (WordPress, LAMP, etc.) without a full IaC investment** → Marketplace app. Use cautiously — validate what the StackScript installs, ensure hardening post-deploy.

## Instance plan selection

| Plan family | vCPUs | Characteristics | Good for |
| --- | --- | --- | --- |
| Nanode | 1 (shared) | Cheapest; burstable CPU | Dev, bots, static sites |
| Shared (`g6-standard-*`) | 1–32 (shared) | Flexible, affordable | Low-traffic prod, staging |
| Dedicated (`g6-dedicated-*`) | 2–64 (dedicated) | Guaranteed CPU cores | Production workloads |
| High Memory (`g6-highmem-*`) | 2–16 (dedicated) | High RAM-to-CPU ratio | Databases, caches |
| Premium (`g6-premium-*`) | 4–96 (dedicated) | Latest-gen hardware | Performance-sensitive prod |
| Premium AMD (`g6-amd-*`) | 4–96 (dedicated) | AMD EPYC, select regions | AMD-optimized workloads |
| GPU (`g6-nanode-*` with GPU) | Varies | NVIDIA GPU attached | ML inference, rendering |
| Bare Metal | Varies | No virtualization | Licensed software, max perf |

## LKE defaults

- **Control plane:** Always enable HA control plane for production clusters — single-control-plane LKE is a single point of failure and suitable only for dev/test.
- **Node pools:** Use autoscaling node pools. Set a minimum equal to baseline capacity and a maximum sized for your peak. Do not over-provision minimum — you pay for every idle node.
- **Node plan:** Dedicated CPU plans for production node pools. Shared CPU is acceptable for non-latency-sensitive dev pools.
- **Kubernetes version:** Pin to the most recent LKE-supported minor release. LKE patches node OS automatically; control-plane Kubernetes version is selectable at cluster creation and upgradeable.
- **Node OS:** Linode manages the node OS (currently Debian-based). You do not choose a distribution; you choose the Kubernetes version.
- **Kubeconfig:** Retrieve via `linode-cli lke kubeconfig-view <cluster-id>` or Terraform data source. Rotate when team members leave. Never commit to source control.
- **Cluster autoscaler:** LKE autoscaling is native (Linode-managed Cluster Autoscaler). Enable per node pool; set `min` / `max` counts in IaC.
- **Networking:** LKE clusters can attach to a VLAN or VPC. For any workload with private data, attach the node pools to a VPC subnet so pod-to-pod traffic stays off the public network.
- **NodeBalancer integration:** LKE auto-provisions a NodeBalancer when you deploy a `Service` of type `LoadBalancer`. This incurs a NodeBalancer cost per service — prefer a single ingress controller (nginx, Traefik) with one NodeBalancer, using path/host routing internally.

## Compute defaults (all instance types)

- **SSH:** Key-only authentication. Disable password login in `/etc/ssh/sshd_config` (`PasswordAuthentication no`). Never leave root SSH login enabled in production.
- **Root login:** Disable root SSH login (`PermitRootLogin no`). Create a named admin user with `sudo` in a provisioning script or cloud-init.
- **Firewall:** Attach a Cloud Firewall to every instance. Default policy: deny-inbound, allow only required ports. See `linode-networking` for rule design.
- **Backups:** Enable Linode Backups on every stateful instance at creation time. Cost is ~20% of the instance price. Do not rely solely on application-level backups.
- **Private IP:** Enable the private IP address for instances that communicate with other Linode resources in the same region. VLAN or VPC provides more controlled L2/L3 isolation — prefer those for multi-instance architectures.
- **Distribution:** Use a current LTS distribution — Ubuntu 22.04 LTS or Debian 12. Avoid Linode's older "one-click" distribution images unless you need a specific version.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Shared CPU plans for latency-sensitive production | CPU steal causes p99 spikes. Use Dedicated or Premium for prod. |
| Single-node LKE cluster | No pod rescheduling on node failure; control plane is also a SPOF without HA. |
| Root password login left enabled | Password brute-force is constant on public IPs. Key-only SSH, always. |
| Marketplace app without post-deploy hardening | StackScripts install a known configuration; security posture is your responsibility post-deploy. |
| No Cloud Firewall attached | Public IPv4 exposed to everything by default. Attach a firewall at instance creation. |
| Bare Metal for variable-load workloads | Bare Metal does not resize; you pay the full plan cost regardless of utilization. |
| LKE LoadBalancer per service | One NodeBalancer per `Service type: LoadBalancer`. 10 services = 10 NodeBalancers. Use an ingress controller. |
| Treating Nanode as prod baseline | 1 shared vCPU + 1 GB RAM is fine for dev. Production should start at Shared 2 GB minimum, Dedicated for anything CPU-sensitive. |

## Security defaults

- SSH: key-based only, root login disabled, `PasswordAuthentication no`, `AllowUsers <named-user>`.
- Cloud Firewall: applied at instance creation; default-deny inbound; allow only the ports your service actually uses.
- No public exposure of management ports (22, 3306, 5432, 6379, 27017) to `0.0.0.0/0`. If remote SSH is necessary, restrict to a known CIDR or use Linode's SSH Gateway / Lish console for emergency access.
- Lish (Linode Shell): the out-of-band console for emergency access. Enable per account, not per instance. Prefer Lish over opening inbound SSH to a wide CIDR.
- Updates: automate OS security patches (unattended-upgrades on Debian/Ubuntu). LKE nodes are patched by Linode for node-pool recycled nodes.

## Observability defaults

- Enable Longview on every non-LKE instance for lightweight CPU, memory, disk, and network stats (free tier: 10 hosts).
- For LKE: deploy a Prometheus + Grafana stack or integrate with a hosted metrics provider (Datadog, Better Stack). LKE does not include native cluster metrics.
- Cloud Manager graphs provide 24h / 30d CPU, network, and disk stats — useful for sizing but not for alerting.
- External uptime monitoring (Better Stack, UptimeRobot, or equivalent) for public endpoints. Linode does not include built-in uptime checks.

## Cost considerations

- Linode bills **per hour, capped at the monthly maximum** listed on the pricing page. If you spin up and destroy within a day, you pay the hourly rate.
- Transfer pool: each instance contributes outbound transfer to a shared regional pool. Inbound transfer is free. Pool overages bill at $0.005/GB (US pricing; verify current rate). Track pool utilization in Cloud Manager.
- LKE control plane: HA control plane incurs an additional hourly fee (check current pricing). Non-HA is free but not suitable for prod.
- Backups: ~20% of instance price per month. Budget for this when sizing.
- GPU instances are expensive — right-size the GPU plan to actual utilization and destroy when done with training runs.
- Bare Metal has a minimum commitment period (check current policy); not billed hourly in all cases.

## IaC hints

- Terraform: `linode_instance` resource, `linode_lke_cluster` for LKE. Pin `linode/linode` provider `>= 2.20`.
- For LKE node pools with autoscaling: set `autoscaler` block with `min` and `max` on each `pool` block.
- `linode_firewall` + `linode_firewall_device` to attach a Cloud Firewall to an instance in Terraform.
- `linode_sshkey` resource to manage SSH keys at the account level; reference them in `linode_instance.authorized_keys`.
- cloud-init: Linode instances support `user_data` (base64-encoded cloud-init config). Use for first-boot provisioning — disable root SSH, create admin user, install updates.

## Verification checklist

Before declaring a compute design complete:

- [ ] Instance plan justified against the decision tree — Dedicated or Premium for latency-sensitive production.
- [ ] SSH configured key-only; root login disabled; named admin user provisioned.
- [ ] Cloud Firewall attached with default-deny inbound.
- [ ] Backups enabled for stateful instances.
- [ ] For LKE: HA control plane on; autoscaling node pools sized; ingress controller used instead of per-service NodeBalancers.
- [ ] Private IP or VPC subnet in use for inter-instance communication.
- [ ] Longview or equivalent monitoring configured.
- [ ] Transfer pool budget reviewed against expected egress.
- [ ] IaC covers all resources — no console-only configuration.
