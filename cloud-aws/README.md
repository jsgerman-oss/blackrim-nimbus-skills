# cloud-aws

AWS development toolkit for Claude Code. Loads as a plugin from the parent `plugins/` marketplace.

<!-- BEGIN: what's inside -->
## What's inside

**Skills** — invoked automatically by description match, or with `/<skill-name>`:

| Skill | Description |
| --- | --- |
| `aws-compute` | Choose, design, or harden AWS compute — Lambda, ECS / Fargate, EKS, EC2, App Runner, Batch. Use when picking a runtime, sizing capacity, configuring autoscaling, or reviewing a compute architecture for cost / latency / availability. |
| `aws-iac-and-deployment` | Choose, scaffold, or review AWS Infrastructure-as-Code and deployment — CDK, Terraform, CloudFormation, SAM, CodePipeline, CodeBuild, CodeDeploy, GitHub Actions OIDC, blue/green, canary. Use when starting a new IaC project, picking a tool, or hardening a release path. |
| `aws-identity-and-security` | Design or audit AWS identity, access, and security posture — IAM, SSO (IAM Identity Center), KMS, Secrets Manager, GuardDuty, Security Hub, CloudTrail, Macie, IAM Access Analyzer. Use when writing policies, rotating secrets, scoping roles, or hardening an account. |
| `aws-networking-and-edge` | Design or audit AWS networking — VPC, subnets, route tables, security groups, NAT, VPC endpoints, Transit Gateway, ALB / NLB, API Gateway, CloudFront, Route 53, WAF, PrivateLink. Use when standing up a new VPC, exposing a service, or hardening edge. |
| `aws-observability-and-cost` | Wire up or audit AWS observability and cost — CloudWatch metrics / logs / alarms, X-Ray, OpenTelemetry, Container Insights, Cost Explorer, budgets, Compute Optimizer, Savings Plans. Use when adding telemetry, tracking down a regression, or shrinking a bill. |
| `aws-storage-and-databases` | Design or audit AWS storage and database tiers — S3, EBS, EFS, RDS / Aurora, DynamoDB, ElastiCache, OpenSearch, Redshift. Use when picking a data store, modeling access patterns, sizing, securing, or backing up data. |

**Sub-agents** — call explicitly via `subagent_type`:

| Agent | Description |
| --- | --- |
| `aws-architect` | AWS Well-Architected reviewer. Use when the user asks for an architecture review, "is this design sound", a pre-launch audit, or wants findings against the six Well-Architected pillars (operational excellence, security, reliability, performance efficiency, cost optimization, sustainability). |
| `aws-security-reviewer` | AWS security reviewer. Use when the user asks for a security audit, threat model, IAM least-privilege review, pre-launch security check, incident-readiness review, or wants to validate posture against CIS / AWS Foundational Security Best Practices. |

**Slash commands:**

| Command | Description |
| --- | --- |
| `/aws-scaffold-iac` | Scaffold an AWS Infrastructure-as-Code project — pick CDK, Terraform, CloudFormation, or SAM, with opinionated production-grade defaults. |
<!-- END: what's inside -->

## Install

This plugin ships inside the Blackrim.dev repo's `plugins/` marketplace. From a Claude Code session:

```text
/plugin marketplace add /Users/jayse/Code/blackrim/plugins
/plugin install cloud-aws@blackrim-cloud-toolkits
```

## Design principles

1. **Defaults are production-grade, not demo-grade.** Encryption-at-rest on by default. Private subnets unless public access is explicitly required. Least-privilege IAM scoped to specific resources, not `*`.
2. **Cost is a first-class concern.** Every skill flags cost-amplifying choices (NAT gateways, cross-AZ traffic, idle baselines) at decision time.
3. **Observability before launch.** No workload ships without metrics, logs, traces, and at least one alarm.
4. **IaC over console.** Console steps appear only as bootstrap (root account hardening). Everything else is code.
5. **Well-Architected as a checklist, not a vibe.** The `aws-architect` agent maps findings to specific pillar best practices.

## Conventions

- Skills assume the AWS CLI v2 is installed and a profile is configured (`aws configure list`).
- IaC examples target the most current stable version: CDK v2 (TypeScript), Terraform >= 1.6 with AWS provider >= 5.x, SAM >= 1.100.
- Region defaults are explicit — no implicit `us-east-1` magic.
- All examples assume single-account first; multi-account / Control Tower is called out where it changes the answer.
