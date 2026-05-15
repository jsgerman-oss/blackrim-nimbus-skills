---
name: aws-compute
description: Choose, design, or harden AWS compute — Lambda, ECS / Fargate, EKS, EC2, App Runner, Batch. Use when picking a runtime, sizing capacity, configuring autoscaling, or reviewing a compute architecture for cost / latency / availability.
---

# AWS Compute

## When to use

- Designing a new workload and choosing between serverless and container / VM compute.
- Tuning Lambda memory / timeout / concurrency, or chasing cold-start latency.
- Right-sizing ECS task definitions or EC2 instance families.
- Deciding ECS vs EKS for a containerized workload.
- Reviewing autoscaling, capacity, and warm-pool configuration.
- Auditing IAM execution roles attached to compute.

## Decision tree

1. **Event-driven, < 15 min, irregular load, no persistent connections** → Lambda.
2. **Long-running HTTP service, container-friendly, no Kubernetes investment** → App Runner *or* ECS / Fargate behind ALB.
3. **Container fleet with sidecars, service mesh, GitOps, multi-tenant** → EKS.
4. **GPU, FPGA, custom kernel, license-restricted AMI, > 14-day workloads** → EC2.
5. **Throughput-oriented batch (rendering, genomics, ETL)** → AWS Batch on Fargate or EC2 Spot.

## Defaults

### Lambda

- Architecture: `arm64` (Graviton) unless a native dep is x86-only — ~20% cheaper, often faster.
- Memory: start at 1024 MB, profile with [Lambda Power Tuning](https://github.com/alexcasalboni/aws-lambda-power-tuning), then trim.
- Timeout: set to 99p observed duration × 1.5; never the API-Gateway-mandated 29 s unless intentional.
- Concurrency: set **reserved concurrency** on every prod function to cap blast radius from a runaway upstream.
- VPC: only attach to a VPC if you actually need private resources — ENI cold-starts hurt.
- Packaging: container image if dependencies > 50 MB; otherwise zip with Lambda layers for shared deps.
- Idempotency: design every handler to be safely retried. SQS triggers will replay; EventBridge will redeliver.

### ECS / Fargate

- Platform version: `LATEST`, but pin in IaC so a new release doesn't surprise you mid-incident.
- Task CPU / memory: pick from the [supported pairs](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task-cpu-memory-error.html); over-provisioning memory is cheaper than CPU-bound throttling.
- Service discovery: AWS Cloud Map or service connect — avoid hand-rolled DNS.
- Deployment: `CODE_DEPLOY` blue/green for any user-facing service; `ECS` rolling for back-of-house.
- Health check grace period: at least 60 s for JVM / .NET, 30 s for Go / Node / Python.

### EKS

- Cluster autoscaler: **Karpenter** for new clusters, not the old Cluster Autoscaler — faster scale-up, better bin-packing.
- Node groups: use managed node groups OR Karpenter — not both for the same workload.
- IRSA (IAM Roles for Service Accounts): mandatory for every workload that calls AWS APIs. Never share a node role.
- Control plane logging: enable `api`, `audit`, `authenticator` to CloudWatch — cheap and load-bearing for incidents.
- Add-ons: `vpc-cni`, `coredns`, `kube-proxy`, `aws-ebs-csi-driver` via EKS managed add-ons, pinned versions.

### EC2

- AMI: latest Amazon Linux 2023 (or pinned Ubuntu LTS) — never a custom-baked AMI without a build pipeline.
- Instance: `m7g.*` / `c7g.*` (Graviton) unless you need x86. `t-series` only for bursty dev / small services with credit budgets watched.
- Storage: gp3 root volume, sized for OS + logs + 30% headroom; data on a separate EBS volume so the root stays disposable.
- Spot: yes for stateless / restartable workloads with diversified instance pools (≥ 6 types across ≥ 3 AZs).
- IMDSv2: enforce `HttpTokens=required`. v1 is a SSRF / metadata-credential exfil class vulnerability.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Lambda in VPC "just to be safe" | Cold-start tax, NAT bandwidth bills, and you didn't need it. |
| Single huge Lambda doing 10 jobs | One bad dep update kills 10 features. Split by responsibility. |
| ECS `:latest` image tag | Rollback is now archaeology. Tag with git SHA or semver. |
| EC2 keypair SSH for ops | Use SSM Session Manager. No bastion, no inbound 22. |
| `iam:*` on `Resource: *` for "convenience" | Will be the finding that fails your audit. Scope down. |
| EKS without IRSA — pod credentials from node role | Any pod = full node IAM. Mandatory IRSA. |
| Autoscaling on CPU alone for I/O-bound workloads | Scales late and oscillates. Use request rate or queue depth. |

## Security defaults

- Every compute runtime gets a **task-scoped** IAM role — never the default service role.
- Outbound egress controlled by SG and, where it matters, a VPC endpoint or egress-filter (e.g., AWS Network Firewall) — exfil paths matter as much as ingress.
- Secrets via Secrets Manager or SSM Parameter Store (`SecureString`); never env-var literals in task / function config.
- Image scanning: ECR scan-on-push enabled; block deploy of `HIGH`/`CRITICAL` findings in the pipeline.
- For EC2, disable IMDSv1, require IMDSv2 hop-limit 1 (1 means container workloads on the host can't reach the metadata service to grab the role).

## Observability defaults

- CloudWatch metrics on by default; add **custom embedded-metric-format** logs for app-level signals.
- X-Ray active tracing on Lambda + API Gateway; OpenTelemetry sidecar / Lambda layer for non-AWS-native traces.
- Structured JSON logs with a request-id field shared across the call chain.
- One CloudWatch alarm per "thing that wakes someone up": error rate, p99 latency, queue age, dead-letter count.

## Cost considerations

- Compute Savings Plans cover Lambda + Fargate + EC2 — buy *coverage*, not max term, until you have 6+ months of stable usage.
- Graviton is ~20% cheaper at similar perf — default to `arm64` and only fall back when blocked.
- Lambda provisioned concurrency is **expensive** — only use it for verifiably cold-start-sensitive paths with measured user pain.
- Track NAT Gateway data-processing charges; a VPC endpoint for S3 / DynamoDB / Secrets Manager pays for itself fast.

## IaC hints

- CDK: `aws-cdk-lib/aws-lambda`, `aws-cdk-lib/aws-ecs-patterns` (`ApplicationLoadBalancedFargateService` is the right starter).
- Terraform: `hashicorp/aws` provider, modules like `terraform-aws-modules/lambda`, `terraform-aws-modules/ecs`, `terraform-aws-modules/eks`.
- SAM: best fit for Lambda + API GW + DynamoDB / EventBridge workloads where most of the IaC is event mappings.
- For multi-service workloads, prefer one stack per bounded context; resist the urge to put everything in one CFN stack.

## Verification checklist

Before declaring a compute design complete:

- [ ] Runtime choice justified against the decision tree, not preference.
- [ ] IAM role is task-scoped (resource-level conditions where possible).
- [ ] Autoscaling target is throughput-correlated, not just CPU.
- [ ] Reserved / provisioned concurrency capped (Lambda) or service-level max set (ECS / EKS HPA).
- [ ] At least one alarm wired to a real notification channel.
- [ ] Cost-per-1k-requests (or per-hour) is sketched and within target.
- [ ] Rollback path is one IaC change away — image tag, alias, or canary weight.
