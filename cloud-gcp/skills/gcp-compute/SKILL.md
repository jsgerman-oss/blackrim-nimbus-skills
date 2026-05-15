---
name: gcp-compute
description: Choose, design, or harden GCP compute — Cloud Run, GKE (Autopilot vs Standard), Cloud Functions Gen 2, App Engine, Compute Engine. Use when picking a runtime, sizing capacity, configuring autoscaling, or reviewing a compute architecture for cost, latency, or availability.
---

# GCP Compute

## When to use

- Selecting a compute platform for a new workload.
- Tuning Cloud Run concurrency, CPU allocation, or minimum instances.
- Deciding between GKE Autopilot and GKE Standard for a containerized fleet.
- Sizing Compute Engine machine families or evaluating Spot VM economics.
- Reviewing autoscaling behavior, warm-up latency, or Workload Identity configuration.
- Auditing service accounts attached to compute.

## Decision tree

1. **Stateless HTTP service, container-based, traffic-driven** → Cloud Run (fully managed).
2. **Event-driven function, short execution, no server management** → Cloud Functions Gen 2.
3. **Container fleet with sidecars, service mesh, GitOps, complex scheduling** → GKE Autopilot first; GKE Standard only when Autopilot constraints block you.
4. **GPU workloads, specialized hardware, long-running VMs, license-tied OS** → Compute Engine.
5. **Legacy application with App Engine APIs, or you're already invested** → App Engine Standard (still maintained, but prefer Cloud Run for new work).
6. **Throughput-heavy batch, HPC, genomics, rendering** → Batch on Compute Engine Spot VMs, or Dataflow for streaming/batch ETL.

## Defaults

### Cloud Run

- CPU allocation: **CPU always allocated** for latency-sensitive services; CPU-throttled-only for truly bursty cost-sensitive jobs.
- Minimum instances: 1 for user-facing services to avoid cold-start latency; 0 only for background workers that tolerate a 2–4 s startup.
- Concurrency: 80 concurrent requests per instance is the starting point; profile under load and adjust. CPU-bound workloads should lower this to 1–10.
- Max instances: set an explicit ceiling on every service to cap cost and downstream DB connection storms.
- Service account: every Cloud Run service gets a **dedicated least-privilege service account** — never the Compute Engine default SA.
- Ingress: `all` only when the service must accept direct internet traffic; prefer `internal-and-cloud-load-balancing` and put a Global Application Load Balancer in front.
- VPC connector or Direct VPC Egress: use Direct VPC Egress (no connector overhead) for Cloud Run services that need private VPC access.
- Secrets: mount Secret Manager secrets as volumes or environment variables — never hard-code in container image or service config.

### Cloud Functions Gen 2

- Gen 2 over Gen 1 for all new functions — backed by Cloud Run, more resource options, VPC access, longer timeouts (up to 60 min).
- Memory: start at 256 MiB, tune with Cloud Profiler before committing.
- Timeout: set to 99th-percentile observed duration × 1.5; do not leave at the 60-second default.
- Trigger: Pub/Sub or Eventarc (CloudEvents). Direct HTTP trigger only for endpoints that genuinely need HTTP semantics.
- Service account: dedicated per-function — same rule as Cloud Run.
- Retry-on-failure: on for Pub/Sub-triggered functions because Pub/Sub will redeliver. Design every function handler to be safely idempotent.

### GKE — Autopilot vs Standard

- **Autopilot** is the default choice. Google manages node provisioning, scaling, OS patching, and security hardening. You pay per Pod resource request, not per node.
- **Standard** is warranted when: you need DaemonSets, you require a specific node kernel or machine type (e.g., A3 GPU), you're running specialized hardware accelerators, or you need fine-grained node-pool controls not yet supported by Autopilot.
- Workload Identity: mandatory on both. Annotate Kubernetes service accounts with the GCP service account email. Never mount service-account key files as Kubernetes secrets.
- Private clusters: enabled by default. Control plane authorized networks restricted to your corp / CI CIDR. Nodes have no public IP.
- Binary Authorization: enabled; enforce attestation policy before any image lands in prod namespaces.
- Release channel: `regular` for most clusters; `stable` only if you need maximum change-control lead time.
- Add-ons: enable `Config Connector` for teams that want to manage GCP resources from Kubernetes manifests; `Managed Prometheus` for metric scraping without a separate Prometheus install.

### Compute Engine

- Machine family: `n2` (Intel) or `n2d` (AMD) for general purpose; `c3` / `c3d` for compute-intensive; `e2` for dev and cost-sensitive workloads. Arm (`t2a`) where software is ARM-compatible.
- Spot VMs: for stateless, restartable, fault-tolerant workloads. Diversify across zones. Handle the preemption signal (`SIGTERM`) with a 30-second shutdown hook.
- Confidential VMs: for regulated workloads where in-use data encryption matters; select `n2d` or `c3d` with `confidential_instance_config.enable_confidential_compute = true`.
- OS: Container-Optimized OS for container workloads; Ubuntu LTS or Debian for general-purpose. Pin the image family; don't reference mutable `latest` tags.
- IMDSv2 equivalent: set `metadata.disable-legacy-endpoints=true` on every instance and project. Prevents v1-style metadata credential exfil.
- No external IPs on instances that don't need them. Use Cloud NAT for egress, IAP TCP tunneling or Identity-Aware Proxy for admin access.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Cloud Run service with the Compute Engine default SA | Any Cloud Run → Cloud SQL / GCS call inherits far broader access than needed. Dedicated SA. |
| GKE Standard cluster with service-account key files in Kubernetes Secrets | Keys rotate slowly or never; if the Secret leaks, the blast radius is the full SA. Use Workload Identity. |
| Compute Engine instance with an external IP "for SSH" | Use IAP TCP tunneling. External IP widens the attack surface and adds a public-IP charge. |
| App Engine Flexible for new workloads | Slow deploy cycles, opaque underlying infrastructure. Migrate to Cloud Run. |
| Cloud Functions Gen 1 for new work | Gen 1 is in maintenance mode. Gen 2 has all the same triggers plus better resource limits and VPC support. |
| Autoscaling on CPU alone for I/O-bound Cloud Run services | Scales late; connections exhaust downstream DB pools. Use request concurrency or queue depth as the signal. |
| GKE Autopilot cluster with no Workload Identity | Pod credentials fall back to node SA, which means every pod = full node access. Workload Identity is mandatory. |
| Cloud Run min-instances=0 for a user-facing API | Cold starts are 1–4 s; users see them. Set min=1 for latency-sensitive paths. |

## Security defaults

- Every compute identity (Cloud Run SA, Cloud Function SA, GKE Workload Identity SA, Compute Engine instance SA) gets only the IAM roles needed for its exact job.
- No `roles/editor` or `roles/owner` on any compute service account.
- Workload Identity is the only approved method for GKE workloads calling GCP APIs. No key files, ever.
- Binary Authorization policy enforced in prod clusters; attestation required before deployment.
- OS Login enabled on Compute Engine VMs; project-level SSH keys disabled.
- Shielded VMs: Secure Boot + vTPM + integrity monitoring enabled.
- Container image scanning via Artifact Registry on every push; CI gates on `CRITICAL` and `HIGH` vulnerabilities.

## Observability defaults

- Cloud Run: request latency, request count, and container instance count are built-in; add application-level structured logs with a `traceId` field.
- GKE: enable Managed Service for Prometheus; deploy `kube-state-metrics` for cluster-level metrics; enable Cloud Logging for system and workload components.
- Compute Engine: install the Cloud Ops Agent for host metrics (CPU, disk, memory, network) and application log collection.
- Cloud Trace: instrument every service with the Cloud Trace SDK or OpenTelemetry → Cloud Trace exporter.
- Alerting policy for: Cloud Run error rate, p99 latency, GKE node NotReady, Compute Engine high disk utilization, Spot VM preemption rate.

## Cost considerations

- Cloud Run billed per request plus CPU and memory — min-instances=0 is free at idle; min-instances≥1 incurs always-on cost. Calculate the crossover based on your traffic pattern.
- GKE Autopilot billed per Pod resource request; over-requesting memory is the common waste vector. Right-size request/limit ratios and check `kubectl top pods`.
- Committed Use Discounts (CUDs) cover Compute Engine and GKE Standard node machine types — buy resource-based CUDs once usage is stable for 30+ days.
- Spot VMs are 60–91% cheaper than on-demand for the same machine type. Combine with managed instance groups for automatic zone-level restarts.
- Artifact Registry: storage is cheap; egress for image pulls within the same region is free. Avoid multi-region pulls unnecessarily.

## IaC hints

- Terraform: `google_cloud_run_v2_service`, `google_container_cluster`, `google_container_node_pool`, `google_compute_instance_template` + `google_compute_instance_group_manager`.
- GKE Autopilot: `google_container_cluster` with `enable_autopilot = true`; node pool management is not applicable.
- Workload Identity in Terraform: `google_service_account`, `google_service_account_iam_member` with role `roles/iam.workloadIdentityUser`, and a Kubernetes service account annotation binding.
- Use `google_project_service` to explicitly enable required APIs (`run.googleapis.com`, `container.googleapis.com`, `compute.googleapis.com`) — don't rely on the console having already enabled them.
- Tag every resource with labels (`environment`, `service`, `owner`, `cost_center`) via a shared locals block.

## Verification checklist

Before declaring a compute design complete:

- [ ] Runtime choice justified against the decision tree, not team familiarity alone.
- [ ] Every service has a dedicated, least-privilege service account — no default Compute SA.
- [ ] GKE Workload Identity configured; no SA key files exist anywhere in the cluster.
- [ ] Autoscaling signal is traffic-correlated (request rate, queue depth), not just CPU.
- [ ] Private cluster / no external IPs enforced; IAP or IAP TCP tunneling for admin access.
- [ ] Binary Authorization policy applied on prod GKE clusters.
- [ ] At least one alerting policy tied to a real user-visible signal.
- [ ] Cost per 1k requests (or per hour) sketched and within target.
- [ ] Rollback path is a single IaC change — Cloud Run traffic split, GKE rollout undo, instance template swap.
