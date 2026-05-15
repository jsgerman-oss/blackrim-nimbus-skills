---
name: azure-compute
description: Choose, design, or harden Azure compute — Azure Functions, AKS, Container Apps, App Service, Container Instances, Azure VMs, Batch. Use when picking a runtime, sizing capacity, configuring autoscaling, or reviewing a compute architecture for cost / latency / availability.
---

# Azure Compute

## When to use

- Choosing between serverless, container, and VM-based compute for a new workload.
- Tuning Azure Functions plan type, memory, or cold-start behaviour.
- Right-sizing AKS node pools or App Service plans.
- Deciding between AKS, Container Apps, App Service, and Container Instances.
- Reviewing autoscaling, node-pool topology, and workload scheduling.
- Auditing Managed Identity assignments attached to compute resources.

## Decision tree

1. **Event-driven, short bursts, variable load, no persistent connections** — Azure Functions (Consumption or Flex Consumption).
2. **Long-running HTTP service, team wants managed containers without Kubernetes** — Container Apps (serverless-scale) or App Service (plan-based, deterministic pricing).
3. **Container fleet with sidecars, GitOps, multi-tenant, custom CRDs, service mesh** — AKS.
4. **Ephemeral sidecar jobs, ad-hoc tasks, no persistent pod lifecycle needed** — Container Instances.
5. **GPU, custom kernel, license-restricted image, or 14-day+ stateful workloads** — Azure VMs (v5 / v6 families).
6. **Throughput-intensive batch (rendering, genomics, ML training, ETL at scale)** — Azure Batch on dedicated or Spot VMs.

## Defaults

### Azure Functions

- Plan: start with **Flex Consumption** for new workloads — granular per-instance scaling with always-ready instances available. Fall back to Premium for VNET integration + no cold-start requirements; Consumption only for true infrequent event processing.
- Runtime: pin the major version explicitly in `functionAppConfig`; never rely on auto-upgrade.
- Identity: system-assigned Managed Identity — no connection strings or storage account keys in app settings.
- Networking: deploy into a VNet-integrated subnet when the function needs private PaaS resources; delegate the subnet to `Microsoft.App/environments` or `Microsoft.Web/serverFarms` as appropriate.
- Idempotency: every trigger handler must be safely retried. Service Bus and Event Hubs triggers guarantee at-least-once delivery.
- Storage: the backing storage account uses private endpoint + Managed Identity authentication; disable shared-key access (`allowSharedKeyAccess: false`).

### AKS

- Version: pin to a supported minor release (>= 1.29); enable auto-upgrade channel `patch` for security fixes without node-pool churn.
- Node pools: one system pool (tainted `CriticalAddonsOnly`) using `Standard_D4ds_v5` or equivalent; separate user pools per workload family. Use Azure CNI Overlay for large pod-count clusters without CIDR exhaustion.
- Autoscaler: **Cluster Autoscaler** on each node pool, with KEDA for workload-driven pod scaling. Karpenter is not yet GA on AKS — use Cluster Autoscaler.
- Identity: use **Workload Identity** (Azure AD Workload Identity) for pod-to-Azure-service auth. Never mount a service principal secret into a pod.
- Managed add-ons: enable `monitoring` (Azure Monitor for containers), `azure-keyvault-secrets-provider`, `azure-policy` via the AKS managed add-on API — not self-installed Helm charts for these.
- Control plane logs: route `kube-apiserver`, `kube-audit`, `kube-controller-manager`, and `guard` (AAD auth) to a Log Analytics workspace — critical for incident forensics.
- Private cluster: use a private API server endpoint for any production cluster; pair with Azure Bastion or a jump VM for kubectl access.

### Container Apps

- Environment: one Container Apps Environment per workload group or per subscription tier; environments share a Log Analytics workspace.
- Scaling: configure scale rules based on HTTP concurrency, Azure Service Bus queue length, or CPU / memory — not on time alone.
- Ingress: external ingress only when the app must be internet-reachable; otherwise internal. Add a custom domain + managed TLS certificate.
- Identity: system-assigned Managed Identity; reference Key Vault secrets via `secretRef` with the Managed Identity, not hardcoded values.
- Dapr: enable only when the application actively uses Dapr building blocks — it adds overhead otherwise.

### App Service

- Plan: use **P-series (Premium v3)** for production — better CPU:cost ratio and VNet integration included. B-series for dev/test; F-series for ephemeral scratch only.
- Deployment slots: staging slot + slot-swap pattern for zero-downtime releases; traffic routing to validate canary before full swap.
- Authentication: enable Easy Auth (App Service Authentication) for user-facing apps; pair with Entra ID as the identity provider.
- Identity: system-assigned Managed Identity; pull secrets from Key Vault via Key Vault references in app settings (`@Microsoft.KeyVault(SecretUri=...)`).
- Custom domain + TLS: always provision via Azure-managed certificates or Key Vault certificates; disable HTTP-only access.

### Azure VMs

- Series: **Ddsv5 / Ddv5** for general workloads; **Lsv3** for storage-intensive; **NCv3 / NCasT4** for GPU. Avoid A- and D-series v1 — retired or near-EOL.
- Spot VMs: yes for stateless / restartable batch workloads with eviction-tolerant design; diversify across sizes and two AZs.
- Confidential VMs: **DCasv5 / ECasv5** (AMD SEV-SNP) when attestable memory isolation is required (regulated data, multi-tenant ML inference).
- Disk: Premium SSD v2 or Ultra Disk for IOPS-sensitive; Standard SSD for general OS volumes. Separate OS disk from data disk so the root stays disposable.
- Extensions: use Azure Monitor Agent (replacing legacy MMA / OMS), `AADSSHLoginForLinux` for passwordless SSH via Entra ID, and `AzureDiskEncryption` with a Key Vault CMK.
- IMDSv2 equivalent: on Azure, IMDS is always v2-style (session-scoped token header required since 2020). Verify `Metadata: true` header handling in any app that queries the IMDS endpoint.

### Azure Batch

- Pool allocation: user subscription mode for cost visibility; Batch service mode for simpler quota management.
- Authentication: pool Managed Identity for accessing Blob Storage and Key Vault — no storage account keys in task commands.
- Node image: use marketplace Ubuntu 22.04 LTS or Windows Server 2022 with container support; pin image version in the pool definition.
- Spot nodes: yes for non-time-critical jobs; implement retry on preemption via `maxTaskRetryCount`.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Functions in Consumption plan for VNET-integrated workloads | Cold starts are unbounded; VNET integration requires Premium or Flex Consumption. |
| AKS without Workload Identity — mounting a service principal secret | Secret rotation is manual; any pod compromise yields long-lived credentials. |
| Single AKS node pool for system and user workloads | System pod eviction under user-workload pressure causes cluster instability. |
| App Service on B1 plan in production | No autoscale, no VNet integration, no deployment slots — three problems in one. |
| VM with SSH port (22) open to 0.0.0.0/0 | One exposed key = full shell. Use Azure Bastion or Just-In-Time VM access. |
| Container Apps with external ingress on internal microservices | Unnecessary internet exposure. Use internal ingress and Front Door at the edge. |
| Azure Functions with hardcoded storage connection strings | One secret leak = full storage account access. Use Managed Identity. |
| AKS with `az aks upgrade` skipping minor versions | Kubernetes does not support jumping minor versions; upgrade sequentially. |

## Security defaults

- Every compute resource gets a **system-assigned Managed Identity** — no service principal secrets stored or rotated manually.
- Outbound traffic from AKS or Functions controlled by NSG + Azure Firewall policy in a hub VNet; exfiltration paths matter as much as ingress.
- Secrets and certificates via **Key Vault**, referenced by URI — never baked into environment variables or container images.
- Container image scanning: enable **Microsoft Defender for Containers** on the ACR registry; block deployment of images with `HIGH` / `CRITICAL` findings in the pipeline.
- Just-In-Time VM access via Microsoft Defender for Cloud for any VM that requires interactive SSH / RDP.
- AKS: Azure Policy add-on enforces pod security standards (disallow `privileged`, require read-only root filesystem, disallow host networking).

## Observability defaults

- Azure Monitor metrics on by default; emit custom metrics via Application Insights `TelemetryClient` or OpenTelemetry SDK.
- Application Insights auto-instrumentation for Functions, App Service (Linux), and Container Apps; manual SDK integration for AKS workloads.
- Structured JSON logs with a `correlationId` / request-id field shared across the call chain.
- One Azure Monitor alert per "thing that wakes someone up": function error rate, AKS pod restart count, App Service HTTP 5xx rate, VM disk full prediction.

## Cost considerations

- **Flex Consumption Functions** bill per execution and per instance-second of always-ready capacity — model expected concurrency before committing.
- **AKS Spot node pools** cut batch/preemptible cost by 60–80%; pair with PodDisruptionBudgets on critical deployments.
- **Azure Reservations** for AKS node pools running predictable steady-state traffic; buy 1-year before committing to 3-year until utilization is stable.
- **Container Apps scale-to-zero** for non-critical background workers; verify cold-start tolerance with p99 latency measurements.
- **App Service Autoscale** on request queue or CPU; over-provisioned fixed plans are common wastage.
- Track idle App Service plan cost — an empty Premium v3 plan costs ~$150/mo whether you deploy anything to it or not.

## IaC hints

- Bicep: `Microsoft.Web/sites` for Functions and App Service; `Microsoft.ContainerService/managedClusters` for AKS; `Microsoft.App/containerApps` and `Microsoft.App/managedEnvironments` for Container Apps.
- Terraform: `azurerm_linux_function_app`, `azurerm_kubernetes_cluster`, `azurerm_container_app`, `azurerm_linux_web_app`. Use the `azurerm_kubernetes_cluster_node_pool` resource for additional user pools rather than inlining them into the cluster resource.
- Deployment Stacks: group compute resources that share a lifecycle in a single Deployment Stack so a teardown removes orphaned resources automatically.
- For AKS add-ons, prefer the `addon_profile` / `oms_agent` block inside `azurerm_kubernetes_cluster` over post-provisioning Helm installs — the managed add-on lifecycle is tracked by ARM.

## Verification checklist

Before declaring a compute design complete:

- [ ] Runtime choice justified against the decision tree, not team preference alone.
- [ ] Managed Identity assigned; no service principal secrets in config or pipeline.
- [ ] Autoscaling target is throughput-correlated (queue depth, HTTP concurrency, custom metric).
- [ ] Reserved concurrency / instance counts capped to avoid runaway cost under bug conditions.
- [ ] At least one alert wired to a real notification channel (Azure Monitor action group).
- [ ] Cost-per-1k-requests (or per-hour) is sketched and within target.
- [ ] Rollback path is a single IaC change — slot swap, image tag, replica count.
- [ ] Private endpoints or VNet integration confirmed for any PaaS dependency.
- [ ] Container image scan gate active in the CI pipeline.
