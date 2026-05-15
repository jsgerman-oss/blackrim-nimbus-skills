---
name: aws-observability-and-cost
description: Wire up or audit AWS observability and cost — CloudWatch metrics / logs / alarms, X-Ray, OpenTelemetry, Container Insights, Cost Explorer, budgets, Compute Optimizer, Savings Plans. Use when adding telemetry, tracking down a regression, or shrinking a bill.
---

# AWS Observability and Cost

## When to use

- Setting up logs / metrics / traces for a new service.
- Building an SLO dashboard or wiring an alarm to oncall.
- Diagnosing a latency / error / cost regression.
- Negotiating a Savings Plan or Reserved Instance commitment.
- Sizing a quarterly cloud cost review.

## Observability pillars

| Pillar | Service |
| --- | --- |
| Metrics | CloudWatch Metrics + Container Insights + Lambda Insights |
| Logs | CloudWatch Logs (with Logs Insights), or OpenSearch / S3 + Athena for long retention |
| Traces | X-Ray (AWS-native) or OpenTelemetry → AWS Distro for OpenTelemetry (ADOT) |
| Synthetics | CloudWatch Synthetics (canaries) |
| Real User Monitoring | CloudWatch RUM |
| Service map | X-Ray Service Map / CloudWatch ServiceLens |

## Defaults — every service

- Structured JSON logs with a stable request-id field.
- Embedded Metric Format (EMF) for app-level metrics — emit from logs, cheaper than `PutMetricData`.
- Tracing on (X-Ray or OTEL), with the request-id propagated as a trace baggage / annotation.
- At least one alarm per service tied to user pain (error rate, p99 latency, queue age, dead-letter count). Never alarm on "CPU > 80%" alone.
- Log retention: 30 d for app logs in CloudWatch; ship to S3 + Athena for longer if regulated. Default infinite retention is an unbounded bill.

## Alarms — write them like contracts

Good alarm spec:

- **Signal:** which metric, at which percentile, over which window.
- **Threshold:** the number that means "human attention needed".
- **Action:** which SNS topic / EventBridge rule / PagerDuty integration.
- **Runbook:** linked in the alarm description — first thing the responder reads.

Bad alarms: floating thresholds, "CPU > 80%", anything that fires more than once a week without action.

For composite signals, use CloudWatch composite alarms (`AND`/`OR` over child alarms) to suppress noise.

## Dashboards

- One per service, one per environment.
- Top row: SLI metrics (availability, latency, error rate). Below: dependencies (upstream latency, downstream error rate). Below that: capacity (memory, queue depth, db connections).
- Variables (regions, env) for dashboards reused across deployments.
- Generated from IaC so they survive account moves.

## X-Ray and OpenTelemetry

- Sampling: tail-based via ADOT collector if traffic is high; head-based 5% as the cheap default.
- Annotations for high-cardinality user / tenant IDs (filterable in service map).
- One trace context propagated end-to-end — `X-Amzn-Trace-Id` for AWS-native, W3C `traceparent` for OTEL. Pick one and translate at boundaries.
- Span every external call (DB, HTTP, queue), not just inbound requests.

## Container / Lambda Insights

- Container Insights on for every ECS / EKS cluster — node + pod metrics, control-plane logs, performance log events.
- Lambda Insights on for prod functions — enhanced metrics + Lambda extension for memory / network detail.
- Use CloudWatch agent on EC2 for memory + disk; default metrics miss both.

## Cost — the actual playbook

### Visibility

- Cost Explorer on, with cost allocation tags (`Environment`, `Service`, `Owner`) enforced via SCP / Config rule.
- AWS Cost and Usage Report (CUR) to S3 + Athena / QuickSight for arbitrary slices.
- AWS Cost Anomaly Detection — free, automatic, surfaces unknown-unknowns.
- Budgets with action-based notifications (email + chat); split into per-service budgets so one runaway doesn't hide.

### Optimization levers

| Lever | Where it pays |
| --- | --- |
| Compute Savings Plans (1y, no upfront) | 20–60% on Lambda + Fargate + EC2 baseline. |
| EC2 Reserved Instances | Steady-state EC2 if SP doesn't fit. |
| Graviton (arm64) | ~20% on EC2 / Lambda / Fargate for compatible workloads. |
| Spot instances | Stateless / batch workloads; diversify across instance pools. |
| Compute Optimizer | Right-size EC2, EBS, Lambda, ECS based on observed utilization. |
| S3 Intelligent-Tiering | Buckets with unpredictable access. |
| VPC endpoints for S3 / DynamoDB | Cut NAT data charges. |
| Auto-stop dev / staging | Saturday-Sunday + nights. |
| Egress audit | Public IPv4, NAT egress, cross-AZ traffic — usually the silent line items. |

### Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Infinite CloudWatch log retention | Logs cost more than compute eventually. |
| Per-resource alarms with no aggregation | Alarm fatigue, missed real signals. |
| Lambda provisioned concurrency turned on "just in case" | $$ even when idle. |
| Reserved instances bought before usage stabilizes | Stranded commitments. |
| 3-year all-upfront Savings Plan as a first move | Lose flexibility for headline discount. Start with 1y no-upfront. |
| Cross-AZ data in microservices | Mesh chatter = bandwidth bill. Place co-dependent services AZ-local. |
| No tagging strategy | Cost reports useless when bill grows. |

## Observability + cost together

The cheapest debugging is the alarm that points to the runbook. The most expensive debugging is the missing dashboard during an incident. Spend on telemetry; cut elsewhere.

Common false economies:

- Turning off X-Ray to save tracing dollars → spending 10× more in engineer hours diagnosing.
- Sampling logs too aggressively → missing the one error trace you needed.
- Skipping Container Insights → opaque pod-level outages.

## IaC hints

- CDK: `aws-cdk-lib/aws-cloudwatch` for alarms / dashboards; `aws-cdk-lib/aws-cloudwatch-actions` for SNS targets.
- Terraform: `aws_cloudwatch_metric_alarm`, `aws_cloudwatch_dashboard`, `aws_cloudwatch_log_group` (with `retention_in_days` ALWAYS set).
- Manage SNS topics + chatbot configuration in IaC so on-call routing isn't tribal knowledge.

## Verification checklist

- [ ] Every service emits structured logs, metrics, and traces with a shared request ID.
- [ ] Log retention is bounded; long-term storage is S3.
- [ ] At least one alarm per service ties to user-visible pain, with a linked runbook.
- [ ] Tagging policy enforced; Cost Explorer slices match expected service / env breakdown.
- [ ] Compute Optimizer + Anomaly Detection findings reviewed at least monthly.
- [ ] Savings Plan / RI coverage tracked; commitments match steady-state.
- [ ] Dashboards exist for top services and live in IaC.
