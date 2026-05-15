---
name: tencent-compute
description: Choose, design, or harden Tencent Cloud compute — CVM (Standard / High IO / Memory Optimized / Compute Optimized / GPU), Lighthouse VPS, TKE Kubernetes (Standard / Serverless / Edge), EKS serverless k8s, SCF serverless functions, BatchCompute, CFS Container Service. Use when picking a runtime, sizing capacity, configuring autoscaling, or reviewing a compute architecture for cost / latency / availability.
---

# Tencent Compute

## When to use

- Designing a new workload and choosing between serverless, container, and VM compute.
- Tuning SCF memory / timeout / concurrency, or diagnosing cold-start latency.
- Right-sizing CVM instance families or Lighthouse plans.
- Deciding TKE Standard vs TKE Serverless (EKS) for a containerized workload.
- Reviewing autoscaling, capacity, and spot instance configuration.
- Auditing CAM roles attached to compute resources.

## Decision tree

1. **Event-driven, short-lived, irregular load, no persistent connections** → SCF (Serverless Cloud Function).
2. **Long-running HTTP service, container-friendly, no Kubernetes investment** → TKE Serverless (EKS) behind CLB, or a small TKE Standard cluster with managed node pools.
3. **Container fleet with sidecars, service mesh, GitOps, multi-tenant** → TKE Standard (managed control plane, worker nodes you control).
4. **Edge compute or offline-region resilience** → TKE Edge (edge nodes join the central control plane).
5. **GPU workloads, HPC, deep learning training, rendering** → CVM GPU instances (GN / GNV / GNVX series) or BatchCompute.
6. **Light workload: personal project, staging env, small SaaS tenant** → Lighthouse (fixed-price VPS with simplified console).
7. **Batch / ETL / genomics / rendering at scale** → BatchCompute on Spot CVM instances across multiple AZs.

## Defaults

### SCF (Serverless Cloud Function)

- Runtime: Python 3.10, Node.js 20, or Go 1.20 — pin explicitly; do not use "latest" runtime aliases.
- Memory: start at 512 MB, profile with concurrent invocation load tests, then trim. SCF bills on GB-seconds.
- Timeout: set to 99th-percentile observed duration × 1.5; the platform maximum is 900 s for event-triggered functions.
- Concurrency: set **reserved concurrency** on prod functions to cap blast radius. Provisioned concurrency only for latency-critical cold-start-sensitive paths after measuring user pain.
- VPC: attach to a VPC only when the function genuinely needs to reach private resources (CDB, Redis, CFS). VPC-attached functions share NAT with the VPC's workloads — account for the data cost.
- Triggers: prefer CKafka (Kafka trigger) or COS event triggers over polling loops. API Gateway trigger for HTTP entry points.
- Idempotency: design every handler to be safely retried. Async invocations replay on failure; dead-letter queues via CMQ or CKafka for observability on failures.

### TKE Standard (managed Kubernetes)

- Control plane: Tencent-managed. You pay for worker nodes only.
- Node pools: use managed node pools; do not manually join CVM instances to the cluster.
- Autoscaling: **node-pool autoscaling** (HPA + cluster-level autoscaler). Scale on request rate or queue depth for I/O-bound services; CPU only for compute-bound.
- IRSA equivalent: **TKE Service Account Token Volume Projection (SVTP)** — bind CAM roles to Kubernetes service accounts so pods assume role-based credentials without static keys.
- Container network: use the **VPC-CNI** mode for production (pods get VPC IPs, lower latency, direct CLB binding). Global Router mode is fine for dev.
- Control plane logging: enable API server, scheduler, and controller-manager logs to CLS — load-bearing for incident forensics.
- Add-ons: `metrics-server`, `node-problem-detector`, `cbs-csi-driver`, `cos-csi-driver` via TKE managed add-ons with pinned versions.

### TKE Serverless / EKS (serverless Kubernetes)

- No node management — pods run on Tencent-managed serverless infrastructure billed per pod vCPU-second.
- Best fit: bursty or infrequent workloads where paying for idle nodes is wasteful.
- Pod scheduling: resource requests are the billing unit — right-size containers before deploying.
- Networking: each pod gets a VPC IP. CLB direct pod binding works as in TKE Standard.
- Not suitable for: DaemonSet workloads, GPU pods, very high-frequency short-lived jobs (SCF is cheaper there).

### CVM (Cloud Virtual Machine)

- Instance family selection:
  - `S` series (Standard): general web / app servers.
  - `C` series (Compute Optimized): CPU-bound, high thread-count.
  - `M` series (Memory Optimized): in-memory caches, databases.
  - `IT` series (High IO): I/O-bound databases on local NVMe.
  - `GN` / `GNV` / `GNVX` series: GPU training and inference.
- Image: latest TencentOS Server 3 (CentOS-compatible, Tencent-maintained) or Ubuntu 22.04 LTS. Never a custom-baked image without a build pipeline.
- Storage: CBS `CLOUD_PREMIUM` (HDD-backed, cost-effective) for non-critical data; `CLOUD_SSD` or `CLOUD_HSSD` (Enhanced SSD) for databases and I/O-sensitive workloads. Root volume separate from data volumes so the OS stays disposable.
- Spot: yes for stateless / restartable workloads. Diversify across instance families and AZs. Configure a termination-notice handler (2-minute warning via metadata API).
- Security: SSH key pair required; disable password login. Better still, use Tencent's **OrcaAgent** / **SSM TencentCloud** for session access without exposing port 22.

### Lighthouse

- Fixed-price VPS with simplified console. Not suitable for production workloads that need fine-grained networking or CAM role binding.
- Use for: personal projects, internal staging, demo environments, low-traffic hobby sites.
- Upgrade path: CVM is the upgrade target when Lighthouse limits are hit; snapshots can be migrated.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| SCF in VPC "just to be safe" | Cold-start latency tax, shared NAT bandwidth, you probably didn't need it. |
| Single large SCF function handling 10 responsibilities | One bad dependency update kills 10 features. Split by responsibility boundary. |
| TKE without SVTP — workloads using static SecretId/SecretKey in pods | Key leaks affect everything in the cluster. Bind CAM roles to k8s service accounts. |
| CVM with password authentication enabled | Password brute-force is constant background noise. Key pairs only. |
| `iam:*` equivalent — CAM policy `*` on `*` for "convenience" | Audit finding, over-privilege blast radius. Scope by resource and condition. |
| Autoscaling on CPU alone for I/O-bound services | Scales late, oscillates. Use request rate or queue depth as the scaling signal. |
| Lighthouse for production workloads | No VPC placement, no CAM role binding, no SLA parity with CVM. |
| BatchCompute jobs without checkpoint / retry design | A transient failure wastes hours of compute. Design for resumable execution. |

## Security defaults

- Every workload gets a **dedicated CAM role** — never the default service account with broad permissions.
- Outbound egress from CVM / TKE controlled by Security Group rules and, where it matters, Cloud Firewall FQDN-based egress filtering.
- Secrets via **SSM Parameter Store** (plaintext or encrypted) or **Secrets Manager** — never environment variable literals baked into pod specs or SCF configuration.
- Container image scanning: **TCR** (Tencent Container Registry) with vulnerability scanning enabled; gate prod deployments on `HIGH` / `CRITICAL` findings via pipeline policy.
- For CVM, enforce key-pair SSH, disable `PermitRootLogin`, install **CWP (Cloud Workload Protection)** agent on every production instance.

## Observability defaults

- Cloud Monitor metrics on for every compute resource by default.
- CLS log collection configured for SCF, TKE pods (via the log-collector DaemonSet), and CVM (via the CLS Agent).
- Structured JSON logs with a stable request-id field.
- At least one Cloud Monitor alarm per "thing that wakes someone up": SCF error rate, TKE pod restart rate, CVM CPU / memory saturation, BatchCompute job failure count.

## Cost considerations

- SCF: costs are GB-second invocations + request count + duration. A single poorly-sized function with high concurrency can surprise. Profile memory allocation.
- TKE Standard: you pay for worker CVM nodes. Use Spot nodes for non-critical node pools — 70–90% discount with interruption risk. Keep at least one on-demand node pool for critical system pods.
- TKE Serverless (EKS): billed per pod — more predictable than node billing for spiky workloads, but more expensive per unit for steady-state high-throughput workloads.
- CVM Reserved Instances: buy 1-year no-upfront reserved instances once a CVM's usage pattern is stable over 3+ months. Committed-use discounts are 30–50% vs on-demand.
- Spot CVM: use for BatchCompute and stateless TKE node pools. Diversify instance families to reduce interruption correlation.
- GPU instances: expensive. Use Spot for training runs; on-demand only for latency-sensitive inference.

## IaC hints

- Terraform: `tencentcloud_instance` (CVM), `tencentcloud_kubernetes_cluster` (TKE), `tencentcloud_scf_function` (SCF), `tencentcloud_batch_compute_job` (BatchCompute). Provider `tencentcloudstack/tencentcloud` ≥ 1.81.
- TKE node pools: `tencentcloud_kubernetes_node_pool` with `scaling_config` for auto-scaling, `spot_instance_type` and `spot_max_price` for Spot nodes.
- For SCF, define function code as a ZIP archive or COS reference in Terraform to keep function config and code deployment decoupled.
- Separate stateful resources (CBS volumes, CFS shares) from compute in their own Terraform workspaces with `prevent_destroy = true`.

## Verification checklist

Before declaring a compute design complete:

- [ ] Runtime choice justified against the decision tree.
- [ ] CAM role is task-scoped; no wildcard resource or action in the attached policies.
- [ ] Autoscaling target is throughput-correlated, not just CPU.
- [ ] Reserved / provisioned concurrency capped (SCF) or node-pool max set (TKE HPA).
- [ ] At least one alarm wired to a real notification channel (Cloud Monitor → WeCom / email / PagerDuty).
- [ ] CWP agent installed on all production CVM instances.
- [ ] Secrets delivered via SSM or Secrets Manager, not env var literals.
- [ ] Image scanning enabled in TCR; pipeline gates on severity.
- [ ] Rollback path is one IaC change away — image tag revert, alias swap, or traffic weight shift.
- [ ] For China workloads: ICP filing status confirmed before any internet-facing endpoint goes live.
