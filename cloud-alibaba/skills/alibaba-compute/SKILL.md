---
name: alibaba-compute
description: Choose, design, or harden Alibaba Cloud compute — ECS (g7/c7/r7/ARM g8y, Spot), ACK Kubernetes (Standard/Pro/Serverless), Function Compute (FC), E-HPC, ECI, Serverless App Engine (SAE). Use when picking a runtime, sizing capacity, configuring autoscaling, or reviewing a compute architecture for cost, latency, or availability.
---

# Alibaba Compute

## When to use

- Designing a new workload and choosing between serverless, container, and VM compute.
- Selecting an ECS instance family or sizing an ACK node pool.
- Deciding between ACK Standard, ACK Pro, ACK Serverless, SAE, or Function Compute for a containerized or event-driven service.
- Configuring autoscaling on ECS Auto Scaling groups or ACK cluster autoscaler / Karpenter.
- Reviewing RAM execution roles attached to compute and ECS RAM role best practices.
- Auditing Spot instance configuration and interruption handling.

## Decision tree

1. **Event-driven, short-lived, irregular load, stateless** → Function Compute (FC). Sync invocation under 15 min; async trigger from OSS / MNS / EventBridge / API Gateway.
2. **Containerized HTTP service, no Kubernetes expertise, per-application auto-scale** → Serverless App Engine (SAE). Micro-billing per request when idle.
3. **Container fleet with sidecars, service mesh, GitOps, multi-tenant, complex scheduling** → ACK Pro (production) or ACK Standard (dev/test). ACK Serverless for burst-only or low-cardinality clusters.
4. **GPU, FPGA, HPC simulation, molecular dynamics, rendering** → E-HPC cluster or ECS with GPU instance family (`gn7`, `gn6v`, etc.).
5. **Container tasks without managing nodes, one-shot jobs, batch** → Elastic Container Instance (ECI) — pay per vCPU-second, no node pool overhead.
6. **Persistent VM needed: custom kernel, license-tied OS, ISV appliance, sustained single-tenant** → ECS. Pick the right family (see below).

## ECS instance families

| Family | Best for |
| --- | --- |
| `g7` / `g8y` (ARM, Yitian 710) | General-purpose; `g8y` is ~20% cheaper per vCPU than x86 equivalent. Prefer for stateless services. |
| `c7` / `c8y` (ARM compute-optimized) | CPU-intensive: transcoding, ML inference, compression. |
| `r7` / `r8y` (ARM memory-optimized) | In-memory databases, large JVM heaps. |
| `hfc7` / `hfg7` (high-frequency CPU) | Trading, real-time simulation, sub-ms latency compute. |
| `gn7` / `gn6v` (GPU) | Training and inference; `gn7` uses A10, `gn6v` uses V100. |
| `t6` (burstable) | Dev/CI/staging; monitor CPU credit balance in CloudMonitor. |
| Spot (Preemptible) | Stateless / restart-tolerant; up to 90% discount; design for 2-min interruption notice. |

Default: `g8y` (ARM) unless a dependency is x86-only. Check ARM compatibility before committing to x86 families.

## ACK (Container Service for Kubernetes)

### Cluster type selection

| Cluster type | When to pick |
| --- | --- |
| **ACK Pro** | Production; SLA-backed control plane, advanced node pools, managed `etcd`, ARMS trace integration, security hardening. |
| **ACK Standard** | Dev / staging environments; cost-reduced; manually managed `etcd` in a worker node. |
| **ACK Serverless (ASK)** | Burst capacity, isolated batch jobs, no node management; pods run on ECI under the hood. |
| **ACK One** (fleet) | Multi-cluster federation across regions or hybrid cloud with CEN attachment. |

### ACK defaults

- Node pools: managed node pools only; avoid mixing unmanaged nodes.
- Autoscaling: **cluster-autoscaler** for stable predictable workloads; **KEDA** for event-driven scale-to-zero; **Karpenter on ACK** (preview as of 2026) for bin-packing across instance families.
- RRSA (RAM Roles for Service Accounts): mandatory for any pod that calls Alibaba Cloud APIs — equivalent to AWS IRSA. Never use an AK/SK in a pod env-var.
- Control plane logging: ship API server / audit / controller logs to SLS; free quota included with ACK Pro.
- Add-ons: pin `flannel` / `Terway` (ENI-native networking — use Terway for pod-level Security Group policy), `CoreDNS`, `metrics-server`, `csi-plugin` versions in IaC.
- Terway vs Flannel: **Terway** for production (pod gets an ENI, Security Group enforcement, better bandwidth); Flannel for dev when ECS ENI quota is a constraint.

## Function Compute (FC)

- Runtime: prefer **Custom Runtime** (container image) for non-trivial dependency trees; built-in runtimes for simple Node/Python/Go functions.
- Architecture: `x86_64` is the current default; ARM (`arm64` Graviton-equivalent) available on FC 3.0 — test for compatibility.
- Memory: start 512 MB, profile with FC cold-start tooling, then tune.
- Timeout: set to 99th-percentile observed duration × 1.5; hard cap at 600 s for sync, 24 h for async.
- Concurrency: set **reserved concurrency** on prod functions to cap blast radius. Provision instances (Provisioned Concurrency) only when cold-start latency is user-visible and measured.
- Async invocations: configure a dead-letter queue (DLQ) and Destination (success + failure). Never fire-and-forget without a DLQ.
- Trigger sources: API Gateway (HTTP), OSS event, MNS, SLS ETL, Timer (cron), EventBridge — each has its own concurrency model; plan accordingly.
- Credentials: use FC's built-in RAM role binding — the runtime injects temporary credentials; no AK/SK in function config.

## Serverless App Engine (SAE)

- Billing: vCPU-second and GB-second; idle cost is near-zero. Best ROI for spiky HTTP services.
- Instance type: SAE manages the underlying ECS; specify vCPU + memory ranges, not instance families.
- Autoscaling: CPU / memory / RPS / custom CloudMonitor metric. Combine min-instance > 0 for latency-sensitive apps.
- Namespace: maps to a VPC + VSwitch; one namespace per environment.
- Log collection: ship stdout / stderr to SLS automatically via the SAE integration.
- Deployment: rolling update or canary (traffic-weighted); blue/green via SAE application version switch.

## Elastic High Performance Computing (E-HPC)

- Scheduler: **Slurm** (default, most compatibility) or **PBS Pro** / **LSF** for legacy workloads.
- Compute nodes: ECS Spot for cost; configure job preemption handling in the scheduler.
- Storage: shared NAS (CPFS — GPFS-equivalent — for high-throughput HPC workloads); OSS for cold outputs.
- Domain account: E-HPC manages an LDAP-based domain by default; integrate with enterprise LDAP/AD if needed.
- Network: use a single VSwitch across the cluster for low-latency; enable RDMA (ERI network) for GPU / MPI jobs.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| AK/SK credentials in ECS user-data or pod env-var | Static key leaks are permanent until rotated; use RAM Role / RRSA instead. |
| Single ECS instance "for simplicity" in prod | Single AZ SPOF and zero rolling-update path. Use Auto Scaling + multi-zone. |
| ACK Standard in production | No SLA on the control plane; a control-plane disruption blocks all scheduling. Use ACK Pro. |
| FC Provisioned Concurrency "just in case" | Billed continuously even when idle — measure cold-start impact before enabling. |
| ECS `latest` system image | Pinned image = known CVEs + reproducible rebuilds. Pin to a versioned AMI / image. |
| t6 burstable instance without credit monitoring | Credit exhaustion silently throttles CPU to baseline; no alarm = mystery latency. |
| Ignoring ARM compatibility | `g8y` saves ~20% but breaks x86-only native extensions — test before committing. |
| Spot without interruption handler | Spot instance get 2 min notice; unhandled interruption = in-flight request loss. |

## Security defaults

- Every ECS instance gets an **instance RAM role** — no AK/SK on the instance or in user-data.
- Every ACK pod that calls Alibaba Cloud APIs uses **RRSA** — RAM Role for Service Account scoped to a specific namespace / SA.
- Security Groups: default-deny outbound except known destinations; inbound 0.0.0.0/0 only on load-balancer SGs, never on application or database SGs.
- OS: Alibaba Cloud Linux 3 (kernel LTS, Aliyun-optimized) as default for ECS; CentOS 7 EOL — migrate.
- Image scanning: Container Registry `scan-on-push` enabled; block deployment on HIGH/CRITICAL findings.
- SSM-equivalent: use **Cloud Assistant** (ACS) for SSH-less operations; disable inbound 22 on all SGs.
- ECS metadata: IMDSv2 (`imdsv2=enabled`) on new instances — v1 is a SSRF/metadata-credential vector.
- Spot interruption hooks: register a `systemd` or init.d handler that drains connections before termination.

## Observability defaults

- CloudMonitor agent on every ECS instance for memory, disk, and process metrics (not reported by default).
- Custom CloudMonitor metrics or SLS-based metrics for application-level signals.
- ACK control-plane logs to SLS; node/pod metrics via ARMS Prometheus (or managed Prometheus addon).
- Function Compute: enable SLS log collection on the service; structure log output as JSON with a request-id field.
- One alarm per user-visible failure mode: error rate, p99 latency, ECS credit balance, Auto Scaling failure events.

## Cost considerations

- **ARM first**: `g8y` / `c8y` / `r8y` instances are ~15–20% cheaper per vCPU-second than equivalent x86 families.
- **Savings Plans**: Alibaba Cloud offers Compute-level Savings Plans covering ECS, ACK, and FC. Purchase after 30 d of stable usage; 1-year no-upfront is the conservative start.
- **Reserved Instances**: For steady-state ECS baseline; zonal RI for guaranteed capacity; regional RI for flexibility.
- **Spot with Auto Scaling**: use capacity policies with multiple instance types and AZs; diversification reduces interruption probability.
- **SAE vs ECS**: SAE eliminates idle-baseline cost for spiky workloads; break-even vs ECS is typically at < 60% average utilization.
- **NAT Gateway data charges**: route OSS traffic through an OSS VPC endpoint (no NAT); similar for other services with internal endpoints.

## IaC hints

- Terraform: `alicloud_instance` (ECS), `alicloud_cs_kubernetes_node_pool` (ACK), `alicloud_fc_function` (FC), `alicloud_sae_application` (SAE). Provider `aliyun/alicloud` ≥ 1.220.
- Use `alicloud_ecs_auto_scaling_group` + `alicloud_ecs_auto_scaling_configuration` for Auto Scaling groups; bind to multiple VSwitches across zones.
- Pin ECS image ID to a versioned Alibaba Cloud Linux image ID, not a family alias.
- For ACK: use `alicloud_cs_managed_kubernetes` (Pro) with `delete_protection = true` and `enable_rrsa = true`.
- ROS (Resource Orchestration Service): YAML-based, similar to CloudFormation; useful when team already uses ROS templates or China-region tooling constraints apply.

## Verification checklist

- [ ] Runtime choice justified against the decision tree, not habit.
- [ ] No AK/SK on any compute resource; RAM Role / RRSA in use everywhere.
- [ ] ARM-compatible (`g8y`) or explicitly justified x86 instance family.
- [ ] Multi-zone placement across ≥ 2 VSwitches for any stateful or user-facing service.
- [ ] Autoscaling configured with a throughput-correlated metric, not CPU alone.
- [ ] At least one CloudMonitor alarm wired to a real notification channel.
- [ ] Spot interruption handler registered (if using Spot).
- [ ] Image scanning enabled; pipeline blocks on HIGH/CRITICAL findings.
- [ ] Cost-per-request or cost-per-hour estimated and within target.
- [ ] China / International region constraint checked before finalizing architecture.
