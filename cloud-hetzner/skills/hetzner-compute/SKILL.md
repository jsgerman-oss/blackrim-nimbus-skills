---
name: hetzner-compute
description: Choose, design, or harden Hetzner compute — Cloud server types (CX / CPX / CCX / CAX ARM Ampere), placement groups, snapshots vs backups vs images, server rescue, Robot dedicated server families (AX / EX / SX / GEX GPU), Auctions, server reset. Use when picking a server type, sizing capacity, designing for HA, or managing server lifecycle.
---

# Hetzner Compute

## When to use

- Choosing between Hetzner Cloud (on-demand, API-driven) and Robot dedicated servers (bare-metal, legacy API).
- Picking the right server type family and size for a workload.
- Designing placement groups for fault isolation across cloud servers.
- Planning snapshot vs backup vs image strategy for recovery and immutable deploys.
- Configuring server rescue mode for a broken OS or key rotation.
- Evaluating Robot Auctions for permanent dedicated capacity at a steep discount.
- Assessing GPU server options (GEX family) for ML inference or batch compute.

## Cloud server families

Hetzner Cloud server types as of 2026-05. All support cloud-init, snapshots, and Private Networks.

| Family | CPU | Use for |
| --- | --- | --- |
| **CX** (shared vCPU, Intel/AMD) | Intel XEON or AMD EPYC, shared | Dev, test, bursty small services, lowest entry price |
| **CPX** (shared vCPU, AMD) | AMD EPYC, shared | Better single-thread perf than CX at modest cost premium |
| **CCX** (dedicated vCPU, AMD) | AMD EPYC, dedicated cores | Production stateless workloads, databases on VMs, consistent latency |
| **CAX** (ARM, Ampere Altra) | Ampere Altra, dedicated cores | Arm-native workloads, Go / Rust / Node services, ~30% cheaper than CCX at same core count |

Sizing guidance:

- `cx22` (2 vCPU, 4 GB) — minimum for a Docker-hosted application; fine for staging.
- `cpx21` (3 vCPU, 4 GB) / `cpx31` (4 vCPU, 8 GB) — preferred for shared-CPU production when bursting headroom matters.
- `ccx13` (2 dedicated, 8 GB) onward — production databases, Kafka brokers, anything latency-sensitive.
- `cax11` (2 ARM, 4 GB) through `cax41` (16 ARM, 32 GB) — ARM-native CI, Go / Rust services; validate your dependencies compile on `aarch64` first.
- `ccx63` (48 dedicated, 192 GB) — database primaries, ElasticSearch nodes, in-memory caches that need predictable NUMA.

## Decision tree

1. **Dev / staging / CI runners** → CX or CPX shared. Price beats consistency.
2. **Stateless HTTP service, ≤ 16 cores, no CPU-pinning requirement** → CAX (ARM) if all dependencies are arm64-compatible; CPX otherwise.
3. **Stateful workload (database, queue, cache) or latency-sensitive** → CCX dedicated.
4. **High-memory needs (Redis, JVM heap, in-memory analytics)** → CCX high-memory variants; or Robot EX series for dedicated RAM at lower cost.
5. **GPU workload (ML inference, batch render, LLM serving)** → Robot GEX (NVIDIA A30, A40, H100 variants) — Cloud has no GPU offerings as of 2026-05.
6. **Permanent high-traffic load at cost-minimized TCO** → Robot AX or EX via Auction if you can absorb 14+ day lead time.

## Robot dedicated server families

| Family | Hardware profile | Typical use |
| --- | --- | --- |
| **AX** | AMD EPYC, high core count, NVMe | Database primaries, compute clusters |
| **EX** (Entry) | Intel Xeon, high RAM, SATA/NVMe | General dedicated, cheaper entry point |
| **SX** (Storage) | High-density HDD / SSD arrays, Xeon | Object storage clusters, backup targets, large media |
| **GEX** (GPU) | NVIDIA A30 / A40 / H100 + Xeon / EPYC host | ML training, GPU inference, HPC |

Robot servers are provisioned in Hetzner's Robot panel or via the Robot REST API. There is no hcloud CLI support for Robot; use the Robot API or the `hetzner.hcloud` Ansible collection's `robot_*` modules.

**Robot Auctions.** Retired or returned dedicated servers sold at 20–60% below list. Auction inventory is visible at [https://www.hetzner.com/sb](https://www.hetzner.com/sb). Lead time is typically same-day to 2 days. Trade-off: no hardware guarantee, no warranty period. Suitable for long-lived batch compute, cold storage, or DR clusters where exact hardware spec is secondary.

## Placement groups

Hetzner Cloud placement groups ensure servers run on different physical hosts within a location. Only type `spread` is available; anti-affinity only, not affinity.

- Use a placement group for any set of servers whose simultaneous failure would cause an outage.
- A placement group is location-scoped — all members must be in the same location.
- Maximum 10 servers per placement group (as of 2026-05).
- Assign at server creation time; you cannot retroactively add a running server.

```hcl
resource "hcloud_placement_group" "app" {
  name = "app-spread"
  type = "spread"
}

resource "hcloud_server" "app" {
  count              = 3
  name               = "app-${count.index}"
  server_type        = "cpx31"
  image              = "ubuntu-24.04"
  location           = "nbg1"
  placement_group_id = hcloud_placement_group.app.id
}
```

## Snapshots vs backups vs images

| Mechanism | What it is | Retention | Cost | When to use |
| --- | --- | --- | --- | --- |
| **Backup** | Automated daily snapshot of the server disk | 7 slots, weekly cycle; oldest rotates | 20% of server price/mo | Ongoing recovery baseline for production servers |
| **Snapshot** | On-demand point-in-time disk image | Manual retention; billed at €0.01/GB/mo | Per-GB | Pre-migration, pre-upgrade, immutable golden image baking |
| **Image** | Custom image uploaded from ISO or created from a server | Manual | Per-GB | Base OS images, Packer-baked AMI equivalents |

Backups and snapshots are stored in the same Hetzner location as the server. **They do not replicate cross-location** — for cross-location DR, download a snapshot and re-upload to the target location, or re-provision from IaC.

Snapshot-as-golden-image pattern (analogous to baking an AMI):

1. Provision a throwaway server.
2. Run Packer or your configuration management to install and configure software.
3. Take a snapshot (`hcloud server poweroff` then `hcloud server create-image --type snapshot`).
4. Store the snapshot ID in Terraform state or a variable file.
5. Reference the snapshot ID in subsequent server provisioning.

## Server rescue mode

Hetzner Cloud and Robot both offer rescue mode — boot into a minimal Linux environment from the hypervisor / IPMI, bypassing the installed OS.

Cloud rescue:

```bash
hcloud server enable-rescue <server-id> --type linux64
hcloud server reset <server-id>
# SSH using the root rescue credentials shown in the response
```

Robot rescue: enable via Robot panel or `POST /rescue` in the Robot API. The rescue system fingerprint is shown at activation; verify it on first connect to guard against MITM.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Shared-CPU server (CX / CPX) for a latency-sensitive database | CPU steal during host contention spikes p99. Use CCX dedicated for DBs. |
| No placement group for a replicated service | Two replicas on the same host fail together. Placement group cost is zero. |
| Backups off to save 20% of server cost | Recovery from a corrupt disk becomes a full redeploy from IaC + data restore from an off-site copy you may not have. |
| Snapshots as the sole DR strategy | Snapshots stay in the same location. A location outage takes them with it. Supplement with cross-location restore capability. |
| ARM server without validating arm64 compatibility | Proprietary binaries, x86-only Docker images, or unported dependencies break silently at runtime. |
| Robot Auction server as primary application host | Auctions have no hardware guarantee; a hardware failure means delay, not SLA-backed replacement. Use for cold-standby or batch only. |
| Manual console provisioning of production servers | No audit trail, drift certain within weeks. Use hcloud CLI + Terraform for everything reproducible. |

## Security defaults

- Disable password authentication on all servers; SSH key-only auth enforced in cloud-init or Ansible hardening.
- Apply a Cloud Firewall to every server at creation time; default-deny inbound, allow only the ports you need.
- Do not assign a public IPv4 address to servers that communicate only via Private Network — saves €0.001/hr and removes internet attack surface.
- Rescue mode generates a temporary root password; change the fingerprint verification procedure so team members validate the host key before trusting the session.

## Observability defaults

- hcloud API exposes CPU, network, and disk metrics per server via the Metrics API (`hcloud server metrics --type cpu,network,disk`).
- For production servers, ship `/proc/stat` and network counters to your external observability platform (Grafana Cloud, Datadog, Prometheus + push gateway) — Hetzner provides no managed alerting.
- Robot servers expose basic PING / TCP-port monitoring configurable in the Robot panel; supplement with an external uptime check (Better Stack, UptimeRobot).

## Cost considerations

- Hetzner bills hourly, capped at a monthly maximum. A server deleted before month-end pays only the hours used, never the monthly cap.
- Snapshots cost €0.01/GB/mo — a 50 GB snapshot is €0.50/mo; benign if kept tidy, meaningful if you accumulate hundreds.
- CAX ARM servers offer roughly 30% better price/core than equivalent CCX AMD — benchmark your workload before assuming the benefit carries through.
- Hetzner's SX storage servers offer bulk HDD capacity at much lower per-TB cost than Cloud Volumes — viable for log archival, video storage, or backup targets.
- Robot servers cost less per CPU-hour than Cloud servers at scale, but require more operational overhead (rescue, RAID management, hardware failure coordination).

## IaC hints

- Terraform: `hetznercloud/hcloud` provider ≥ 1.48, `hcloud_server`, `hcloud_server_network`, `hcloud_placement_group`.
- Ansible: `hetzner.hcloud` collection, `hetzner.hcloud.hcloud_server` module.
- Packer: `hcloud` builder in the `hetznercloud` plugin; snapshot-ID output piped to Terraform.
- cloud-init: standard YAML config; Hetzner passes it via `user_data` on `hcloud_server`. Encode as base64 if using Terraform's `sensitive` function.

## Verification checklist

Before declaring a compute design complete:

- [ ] Server type family justified (shared vs dedicated vs ARM vs dedicated GPU) against the decision tree.
- [ ] Placement groups assigned to any service where N > 1 replica must survive a host failure.
- [ ] Backup enabled on every server holding state; retention policy understood.
- [ ] Cloud Firewall applied at server creation; no default-allow inbound.
- [ ] Public IPv4 suppressed for servers that only need Private Network access.
- [ ] SSH key-only auth enforced; no password login.
- [ ] Snapshot golden image strategy documented if Packer-baking is used.
- [ ] ARM compatibility verified for any CAX deployment.
