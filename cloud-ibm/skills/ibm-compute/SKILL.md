---
name: ibm-compute
description: Choose, design, or harden IBM Cloud compute — VPC Virtual Server Instances, VPC Bare Metal, Code Engine (serverless containers / Jobs / Functions), IKS, Red Hat OpenShift on IBM Cloud (ROKS), and Power Systems. Use when picking a runtime, sizing capacity, configuring autoscaling, or reviewing a compute architecture for cost, latency, or availability.
---

# IBM Cloud Compute

## When to use

- Choosing between serverless, container, and VM compute on IBM Cloud.
- Sizing VPC VSI profiles (bx2, cx2, mx2) or bare metal options.
- Deciding between Code Engine, IKS, and ROKS for containerized workloads.
- Configuring Code Engine application autoscaling, job concurrency, or Function triggers.
- Reviewing IAM execution identity (Trusted Profiles) attached to compute resources.
- Auditing IKS or ROKS cluster node pool configuration and autoscaling.

## Decision tree

1. **Event-driven, short-lived, HTTP or trigger-based, no persistent state** → Code Engine Functions (Knative eventing) or Code Engine Applications scaled to zero.
2. **Long-running HTTP service, container-friendly, no Kubernetes investment** → Code Engine Application (managed Knative) with autoscaling.
3. **Batch processing, ETL, model training runs, or scheduled jobs** → Code Engine Jobs or Job Runs.
4. **Container fleet with sidecars, service mesh, GitOps, multi-tenant** → IKS (standard Kubernetes) or ROKS (OpenShift, preferred for regulated workloads).
5. **GPU workloads, high-performance computing, or bare metal performance** → VPC Bare Metal or Power Systems (for AIX / IBM i / Linux on POWER).
6. **General-purpose VM, lift-and-shift, licensing requiring dedicated hosts** → VPC Virtual Server Instance.

## VPC Virtual Server Instances

### Profile families

| Family | Use |
| --- | --- |
| `bx2` (Balanced) | General-purpose workloads; equal vCPU and memory ratio (1:4). |
| `cx2` (Compute) | CPU-intensive workloads; 1:2 ratio — web servers, batch processing, CI runners. |
| `mx2` (Memory) | In-memory caching, large JVM heaps, analytics; 1:8 ratio. |
| `ox2` (Very High Memory) | SAP HANA, in-memory databases; up to 1:14 ratio. |
| `ux2` (Ultra High Memory) | Largest in-memory needs; mainframe-class vertical scale. |
| `gx2` (GPU) | ML inference, rendering, HPC with NVIDIA GPUs. |

### Defaults

- Boot volume: encrypted with a customer-managed root key (Key Protect or HPCS). `100 GB` minimum; detach and retain the data volume separately so the instance stays disposable.
- SSH keys: add SSH key at creation for emergency access; prefer IBM Cloud VPN or Session Manager equivalent (`ibmcloud is instance-console`) for day-to-day access — no inbound port 22 in Security Group for production.
- User data: cloud-init script for bootstrap; provision secrets via Secrets Manager at startup, not baked into images.
- Dedicated hosts: use for software licensing, compliance isolation, or predictable latency; not the default for most workloads.
- Instance templates + instance groups for autoscaling horizontal fleets; scaling policies on CPU or custom metrics via IBM Cloud Monitoring.

## Code Engine

Code Engine is IBM Cloud's fully managed, serverless container platform built on Knative. It runs three primitives: **Applications** (HTTP-triggered, autoscaling to zero), **Jobs** (batch run-to-completion), and **Functions** (short-lived event-driven code).

### Defaults

- Project: one Code Engine project per environment (dev / stage / prod). Projects are the IAM and network boundary.
- Image: pull from IBM Cloud Container Registry (ICR). Configure an ICR pull secret bound to a Service ID with `Reader` role on the registry namespace.
- Trusted Profile: bind the Code Engine project to a Trusted Profile — workloads acquire IAM tokens via compute identity, not a long-lived API key.
- Application scaling: `min-scale=0` for cost savings on dev/stage; `min-scale=1` for prod if cold-start latency matters. Set `max-scale` to cap blast radius.
- Concurrency: set `--concurrency` per instance based on app characteristics — stateless handlers can push 100+; stateful or CPU-bound handlers should be closer to 1–10.
- CPU / memory: start at `0.25 vCPU / 0.5 GB`; profile under realistic load and size up. Code Engine bills per vCPU-second and GB-second consumed.
- Jobs: use `--array-size` for embarrassingly parallel batch; `--retrylimit` for fault tolerance.
- Secrets and config maps: mount as environment variables or volume files — never bake values into image layers.

## IKS — IBM Kubernetes Service

- Kubernetes version: stay within N-1 of the current supported upstream; IKS offers managed control plane upgrades.
- Worker pools: use multiple pools with different profiles for mixed workloads (e.g., `mx2.4x32` for in-memory, `cx2.4x8` for compute-intensive). Enable autoscaling on each pool.
- Cluster autoscaler: IBM Cloud's managed cluster autoscaler — configure `minSize` / `maxSize` per pool; set `balanceSimilarNodeGroups=true` for HA across zones.
- Pod IAM: configure pod-level IAM using IBM Cloud's **Trusted Profiles for OIDC** or bind a Service ID to a Kubernetes service account via a Secret. Never use a shared API key mounted as a secret.
- Ingress: IBM-managed Ingress with built-in ALB; use custom Ingress class for advanced routing. TLS termination via IBM-managed certificates or bring your own via Secrets Manager.
- VPC integration: IKS on VPC (Gen 2) — use VPC Security Groups to control pod egress; VPC Load Balancer for services of type `LoadBalancer`.

## ROKS — Red Hat OpenShift on IBM Cloud

ROKS is the preferred platform for regulated workloads (Financial Services, HIPAA, FedRAMP) due to OpenShift's built-in security context constraints, integrated audit logging, and IBM's compliance attestation.

- Use Financial Services-validated regions when workloads are in scope for IBM Cloud Framework for Financial Services: `us-south`, `us-east`, `eu-de`, `eu-gb`.
- SCC (Security Context Constraints) are enforced by default — workloads that rely on privileged containers need explicit review.
- Built-in OpenShift image registry or ICR as the pull source; ICR preferred for enterprise consistency.
- GitOps: Red Hat OpenShift GitOps (Argo CD) is the standard delivery mechanism for ROKS workloads.
- Operators: use OperatorHub / Operator Lifecycle Manager for cluster services (databases, monitoring, mesh); avoid raw Helm where an Operator exists.

## Power Systems

IBM Power Systems Virtual Servers are designed for AIX, IBM i, and Linux on POWER workloads — primarily legacy enterprise applications, SAP HANA, and Oracle DB.

- Not a first choice for new cloud-native workloads — use VPC VSIs or Code Engine instead.
- Useful for lift-and-shift of POWER-architecture workloads that cannot be replatformed.
- Connectivity to VPC via Transit Gateway or Direct Link.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Long-lived API key mounted as a secret in Code Engine / IKS | Rotation is manual and error-prone. Use Trusted Profiles and compute identity. |
| Code Engine Application with `min-scale=0` and latency SLA | Cold starts take 3–10 s. Set `min-scale=1` for latency-sensitive paths. |
| IKS cluster with a single worker pool in one zone | Zone outage = cluster outage. Multi-zone worker pools mandatory for production. |
| VPC VSI in default Security Group | Default SG is permissive. Create a workload-specific SG with deny-by-default. |
| ROKS for a stateless HTTP microservice with no OpenShift dependencies | Operational overhead without benefit. Use Code Engine or IKS. |
| Instance group without health check | Unhealthy instances stay in rotation. Always configure VPC health check. |
| Code Engine Job without `--retrylimit` | Transient failures are not retried. Set a reasonable retry limit. |

## Security defaults

- Every Code Engine project, IKS cluster, and ROKS cluster is bound to a Trusted Profile — workloads never use a long-lived API key for IBM Cloud API access.
- Instance metadata service used for dynamic IAM token acquisition on VPC VSIs (similar to IMDS on AWS/Azure) — disable classic metadata endpoint if available.
- Container images scanned by Vulnerability Advisor in IBM Cloud Container Registry; block deploys with `HIGH` or `CRITICAL` findings in Toolchain or pipeline.
- No inbound port 22 from `0.0.0.0/0` on any VPC Security Group. Use `ibmcloud is instance-console` or a VPN / bastion pattern.
- Secrets Manager integration for runtime secrets — not environment variable literals in Code Engine config or Kubernetes secrets backed by etcd without KMS envelope encryption.

## Observability defaults

- IBM Cloud Monitoring (Sysdig) with the platform metrics integration — automatically collects VPC VSI, IKS, ROKS, and Code Engine metrics.
- IBM Cloud Logs (LogDNA) for application and platform logs; configure log routing from cluster to the instance in the same region.
- Activity Tracker for control-plane audit events (instance creates, scale events, config changes).
- Structured JSON logs with a `request_id` field propagated across service calls.
- One IBM Cloud Monitoring alert per SLI: error rate, p99 latency, pod restart count, autoscaler failure.

## Cost considerations

- Code Engine bills on consumed vCPU-seconds and GB-seconds — bursty or intermittent workloads are dramatically cheaper than a standing VM.
- VPC VSIs: IBM Cloud Subscriptions reduce on-demand rates by 10–30% for committed monthly spend. Calculate break-even at ~60% utilization of committed amount.
- IKS and ROKS: free for the control plane on VPC; pay for worker node VSIs — apply Subscription discounts here.
- Dedicated hosts: use only when licensing or compliance requires; they carry a significant per-host floor cost.
- Code Engine Functions: very granular billing (per 100 ms) — best for irregular, spiky traffic; break even vs Application at roughly 50% sustained request rate.

## IaC hints

- Terraform: `ibm_is_instance` (VPC VSI), `ibm_is_bare_metal_server`, `ibm_code_engine_project` + `ibm_code_engine_app` / `ibm_code_engine_job`, `ibm_container_cluster` (IKS), `ibm_container_vpc_cluster` (IKS on VPC).
- Provider: `IBM-Cloud/ibm` >= 1.65. Pin exact version in `.terraform.lock.hcl`.
- Code Engine apps: use `ibm_code_engine_secret` for registry pull secrets and runtime secrets; reference via `env_from_secret`.
- IKS node pools: `ibm_container_vpc_worker_pool` with `zones` list for multi-zone placement.

## Verification checklist

- [ ] Runtime choice justified against the decision tree, not familiarity.
- [ ] All compute resources bound to a Trusted Profile or Service ID with least-privilege roles.
- [ ] No inbound SSH (port 22) from `0.0.0.0/0` in any Security Group.
- [ ] Multi-zone placement for production IKS / ROKS worker pools.
- [ ] Autoscaling configured and tested — not just enabled.
- [ ] Container images scanned; pipeline gates on severity findings.
- [ ] IBM Cloud Monitoring and IBM Cloud Logs wired before first production traffic.
- [ ] Secrets sourced from Secrets Manager at runtime; no literals in config.
- [ ] Cost estimate sketched: on-demand vs Subscription break-even confirmed.
