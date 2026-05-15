---
name: oci-compute
description: Choose, design, or harden OCI compute — Compute VMs and Bare Metal, GPU and A1 Ampere ARM shapes, Flex shapes, Container Engine for Kubernetes (OKE), Functions (Fn Project), Container Instances. Use when picking a runtime, sizing capacity, configuring autoscaling, or reviewing a compute architecture for cost, latency, or availability.
---

# OCI Compute

## When to use

- Selecting a shape family (Standard, Flex, GPU, A1 Ampere, Bare Metal) for a new workload.
- Deciding between Compute VMs, OKE, Functions, or Container Instances as the execution layer.
- Designing an OKE cluster — node pools, Virtual Nodes, cluster networking, add-ons.
- Right-sizing Flex shapes (OCPUs and memory chosen independently).
- Auditing instance principals, autoscaling policies, and security list attachments.
- Reviewing image provenance and instance configuration hardening.

## Decision tree

1. **Event-driven, short-lived, stateless, irregular load** → Functions (Fn Project).
2. **Containerized workload, no orchestration investment** → Container Instances behind a Load Balancer.
3. **Container fleet with sidecars, GitOps, multi-tenant, or you already run Kubernetes** → OKE (Container Engine for Kubernetes).
4. **GPU-intensive ML training or inference** → Compute `GPU3` / `GPU4` shapes or A10 Bare Metal; attach Block Volume for scratch.
5. **ARM-native, cost-sensitive, or energy-efficient workload** → A1 Flex (Ampere Altra); ~30% cheaper per OCPU than x86 Flex at comparable throughput.
6. **OLAP, HPC, or workloads requiring custom kernel / raw NVMe / SR-IOV** → Bare Metal.
7. **General server-style workload, not yet containerized** → Standard or Flex VM (`VM.Standard.E5.Flex` is the default for modern workloads).

## Defaults

### Compute VMs

- Shape: `VM.Standard.E5.Flex` for x86 workloads; `VM.Standard.A1.Flex` for ARM-native or cost-optimized workloads. Avoid fixed-shape `VM.Standard2.*` — Flex gives independent OCPU + memory sizing.
- OCPU / memory: start with the smallest that fits your p95 load; resize online for Flex shapes without a reboot.
- Image: Oracle Linux 9 (latest OCI-provided image) or Ubuntu 24.04 LTS from OCI's image catalog. Never bake a custom image without a pipeline — use cloud-init for day-1 config.
- Boot volume: 50 GB minimum; attach a separate Block Volume for application data so the boot volume stays disposable.
- Encryption: boot volume and attached Block Volumes encrypted with a customer-managed Vault key by default.
- SSH access: use OCI Bastion service with session-scoped keys, not long-lived keypairs with open port 22.
- Authentication: Instance Principal for any code that calls OCI APIs — never store API key files on an instance.
- Autoscaling: instance pool + autoscaling configuration (metric-based or schedule-based). Never hand-manage instance counts.

### OKE — Container Engine for Kubernetes

- Cluster type: **Enhanced** for all production workloads. Enhanced clusters support Virtual Nodes, cluster add-on lifecycle management, and workload identity federation. Basic clusters are for development or cost-constrained demos only.
- Kubernetes version: pin to the latest supported release; OKE's managed control plane handles upgrades on your schedule — set a maintenance window.
- Node pools: use Flex shapes (`VM.Standard.E5.Flex` or `VM.Standard.A1.Flex`). Separate node pools per workload tier (general, GPU, memory-optimized) to enable targeted autoscaling.
- Virtual Nodes: enabled for burst workloads where the overhead of provisioning real nodes is too slow; Virtual Nodes are OCI-managed (no OS-level access, fully serverless pod scheduling).
- Cluster networking: VCN-native pod networking (NPN) for production — pods get VCN-routable IPs, removing the overlay network layer. Flannel only for dev clusters.
- Autoscaling: OKE cluster autoscaler with scale-to-zero support for non-GPU node pools.
- Workload Identity: enable OIDC-based workload identity federation so pods authenticate to OCI APIs via projected service account tokens. Never mount API keys into pods.
- Add-ons managed through the OKE API: CoreDNS, kube-proxy, Flannel/VCN-NPN, OCI metrics and logging add-ons — pin versions, let OKE lifecycle-manage upgrades.

### Functions (Fn Project)

- Application and function config: store config values via OCI Application config; never inline secrets as function environment variables — reference Vault secrets by OCID instead.
- Shape: always `GENERIC_X86_ARM` for cross-architecture flexibility, or `GENERIC_ARM` to reduce cost on Ampere.
- Timeout: set to 2× the p99 observed duration; the hard maximum is 300 seconds for a single invocation.
- Concurrency: each function application has an implicit concurrency limit — scale-out is automatic, but use throttling policies at the API Gateway or Events layer to cap blast radius.
- Tracing: enable OCI APM tracing per function application for end-to-end latency visibility.
- Authentication: Functions automatically receive a Resource Principal token — use it for all OCI API calls from within the function.

### Container Instances

- Use Container Instances for one-off jobs, migration tasks, or small services where OKE overhead is not justified.
- Compartment: always in the same compartment as the workload it serves — compartment boundaries are the blast-radius boundary.
- Networking: always place on a private subnet; expose via internal Load Balancer if service-to-service, or via public Load Balancer + WAF for external traffic.
- Resource Principal: Container Instances support Resource Principal authentication; wire it instead of API keys.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Fixed-shape VMs instead of Flex | You pay for the fixed config even when you only need half — Flex shapes cost the same per unit and size independently. |
| API key files on compute instances | Key leaks, no rotation, blast radius is the full tenancy principal. Use Instance Principal. |
| OKE Basic cluster in production | No enhanced cluster add-on lifecycle, no Virtual Nodes, missing workload identity federation. |
| Open port 22 inbound on security lists | One misconfigured SG = SSH brute-force exposure. Use Bastion sessions. |
| Functions with env-var secrets | Visible in console, logs, and export APIs. Reference Vault secrets by OCID. |
| Single OKE node pool for all workload types | GPU workloads contend with general workloads; autoscaling interferes. Separate pools per tier. |
| `oci:tenancy` principal in dynamic group rules | The whole tenancy matches — scope to compartment or tag conditions. |

## Security defaults

- Every Compute instance and OKE node runs under an Instance Principal tied to a dynamic group scoped to that compartment.
- Boot and data volumes encrypted with a customer-managed Vault key (not Oracle-managed keys).
- Security lists and NSGs on private subnets permit only the minimum ports required; no `0.0.0.0/0` on non-load-balancer ingress.
- Images scanned before deployment; OKE node pools pull from OCI Container Registry with scan-on-push enabled.
- Bastion service for any interactive access; sessions are ephemeral, logged, and scoped to a single target.
- Cloud Guard detector recipe active in the compartment to catch public IP exposure and broad IAM policies on compute resources.

## Observability defaults

- OCI Monitoring agent installed and configured (automatically on OCI-provided images) — instance-level CPU, memory, disk, and network metrics stream to Monitoring.
- Logging: OS syslog + OCI Logging agent forwarding application logs to a log group in the same compartment.
- OKE: Container Insights equivalent via OCI Monitoring service + OKE log add-on for cluster, node, and container logs.
- Alarm: at minimum one alarm per compute tier on CPU utilization (p95 > 80%) and instance count vs autoscaling max.
- Functions: invocation count, error count, and p99 duration alarms wired to a Notification topic.

## Cost considerations

- A1 Flex (Ampere) is typically the lowest cost per OCPU for workloads that run on ARM — audit your dependencies for ARM compatibility before defaulting to x86.
- Flex shapes allow right-sizing without changing shape families — adjust OCPU and memory independently to match the actual measured bottleneck.
- OKE Virtual Nodes remove the node-pool idle cost for burst workloads — you pay only for active pod-seconds.
- Functions invocations under the OCI Always Free tier ceiling cost nothing — model your expected invocation rate before sizing.
- Stop non-production instances outside working hours via an autoscaling schedule or a DevOps lifecycle trigger.

## IaC hints

- Terraform: `oracle/oci` provider ≥ 6.x. Key resources: `oci_core_instance`, `oci_containerengine_cluster`, `oci_containerengine_node_pool`, `oci_functions_application`, `oci_functions_function`.
- Use `oci_core_instance_configuration` + `oci_core_instance_pool` for autoscaling groups rather than individual `oci_core_instance` resources.
- OKE cluster and node pool upgrades are managed resources — pin Kubernetes version in the node pool config; update on a schedule, not ad hoc.
- Declare autoscaling policies in Terraform so instance pool scaling rules are version-controlled alongside the rest of the stack.

## Verification checklist

Before declaring a compute design complete:

- [ ] Shape family justified against the decision tree, not habit or convention.
- [ ] Instance Principal (or Workload Identity for OKE) configured; no API key files anywhere.
- [ ] Boot and data volumes use a customer-managed Vault key.
- [ ] Bastion service session-based access replaces any open SSH rules.
- [ ] Autoscaling policy targets a meaningful signal (request rate, queue depth, CPU p95) — not just raw CPU threshold.
- [ ] At least one alarm tied to a notification topic that reaches a real responder.
- [ ] Non-production instances have a shutdown/stop schedule or autoscaling floor of 0.
- [ ] OKE cluster type is Enhanced for any production cluster.
- [ ] Image or container image provenance is verified; scan-on-push enabled in OCIR.
