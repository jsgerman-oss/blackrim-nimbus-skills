---
name: aws-networking-and-edge
description: Design or audit AWS networking — VPC, subnets, route tables, security groups, NAT, VPC endpoints, Transit Gateway, ALB / NLB, API Gateway, CloudFront, Route 53, WAF, PrivateLink. Use when standing up a new VPC, exposing a service, or hardening edge.
---

# AWS Networking and Edge

## When to use

- Designing a new VPC for an account or workload.
- Exposing an internal service to the internet (or another VPC / account).
- Tuning latency, TLS, or WAF posture at the edge.
- Auditing east-west connectivity (peering, TGW, PrivateLink, VPN).
- Tracking down NAT / cross-AZ data costs.

## VPC layout — the boring default

- One VPC per environment (dev / stage / prod). Multi-account if you have any compliance pressure — accounts are the cheapest blast-radius boundary AWS gives you.
- CIDR: `/16` per VPC. `/19` or `/20` per subnet — leave room.
- Subnets per AZ, across at least 3 AZs in the region:
  - `public` (IGW route) — only for load balancers and NAT.
  - `private` (NAT route) — application workloads.
  - `isolated` (no NAT) — databases, internal-only.
- IPv6 dual-stack if you have any large-scale or egress-cost-sensitive workload — public-IPv4 charges starting 2024 make this matter.
- VPC Flow Logs to S3 (cheaper) or CloudWatch — at least `REJECT` for security baseline, `ALL` for forensics-ready accounts.

## Subnet, SG, NACL discipline

- Security Groups: stateful, the primary control. Reference SGs from SGs (`sg-app-tier` can reach `sg-db-tier:5432`), never raw CIDR for intra-VPC traffic.
- NACLs: stateless, leave at default-allow unless you have a real reason. They're hard to debug and rarely catch what SGs miss.
- No `0.0.0.0/0` on a database SG. Ever.
- No `0.0.0.0/0` inbound on port 22 / 3389. Use SSM Session Manager.

## NAT and egress

- One NAT Gateway per AZ for HA; cross-AZ NAT is a silent uptime + cost trap.
- For high-volume egress to AWS services, use VPC endpoints (Gateway for S3 / DynamoDB; Interface PrivateLink for nearly everything else) — bypasses NAT, often cheaper, stays on the AWS backbone.
- For controlled egress to the internet, AWS Network Firewall or a Transit Gateway with centralized egress is the grown-up answer.

## Load balancing

| Use case | Pick |
| --- | --- |
| HTTPS service, host- / path-based routing | Application Load Balancer (ALB) |
| TLS passthrough, UDP, static IP needed, extreme TPS | Network Load Balancer (NLB) |
| Cross-region, latency-sensitive global | Global Accelerator in front of ALB / NLB |
| Internal service-to-service | Internal ALB / NLB or App Mesh / Service Connect |

ALB defaults: HTTP→HTTPS redirect listener, `ELBSecurityPolicy-TLS13-1-2-2021-06`, access logs to S3, deletion protection on, idle timeout tuned to your app (60 s default is fine for most).

## API Gateway

- HTTP APIs > REST APIs for new work — 70% cheaper, lower latency, more than enough features for most workloads. Pick REST only if you need WAF on the API (HTTP APIs route WAF via CloudFront in front).
- Custom domain + ACM certificate; no `*.execute-api.amazonaws.com` URLs in production.
- Throttle per method or per usage plan; never expose an unbounded route.
- Authorizer at the edge — JWT (HTTP API) or Lambda (REST) — never "verify in the handler".

## CloudFront

- OAC (Origin Access Control) for S3 origins — never public buckets, never the old OAI.
- Cache policies: explicit managed policies (`CachingOptimized`, `CachingDisabled`); custom only when you must.
- Response headers policy for security headers (HSTS, CSP, Referrer-Policy, Permissions-Policy) — apply at the edge so misconfigured origins can't drop them.
- Functions (lightweight, viewer-request) for header rewriting and redirects; Lambda@Edge only when you genuinely need it.
- Geo restrictions / signed URLs / cookies for paid content or compliance.

## Route 53

- Public hosted zones in a dedicated account for prod domains — registrar account separation is a real security boundary.
- Failover, latency, weighted, and geolocation routing — pick consciously, not by default.
- Health checks on every alias to load balancers; CloudWatch alarm when a check flips.
- DNSSEC if you control the registrar — protects against on-path resolver attacks.

## WAF

- AWS Managed Rules (Core, KnownBadInputs, AnonymousIPList) as a baseline; add Bot Control where bots cost real money.
- Rate-based rule on every public origin — minimum baseline against credential stuffing and scrape storms.
- Custom rules in count mode first, then enforce after seeing real traffic — `BLOCK`ing on day one breaks legit users.
- Logs to S3 / Kinesis Firehose for analysis; CloudWatch metrics for alerting.

## Cross-VPC / cross-account / hybrid

- Transit Gateway for >2 VPCs or where you'd otherwise build a peering mesh; centralized inspection VPC pattern when you need east-west control.
- VPC peering only for two stable VPCs with no transitive needs.
- PrivateLink (VPC endpoint services) to expose your service to other VPCs / accounts without peering — keeps the consumer's CIDR private from you.
- Direct Connect or Site-to-Site VPN for on-prem; transit gateway terminates either.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| One huge VPC for all environments | Blast radius = everything. Multi-account, even within one org. |
| `0.0.0.0/0` on a DB SG "just temporarily" | Never gets reverted. Use SSM port forward. |
| Public S3 bucket for static site | One bad copy-paste = exposure. CloudFront + OAC. |
| Default VPC for production | Predictable CIDR, predictable IGW, no IPv6, default NACL. Delete or ignore. |
| Lambda in a VPC for "security" with no private resources | Cold-start tax for no benefit. Only VPC-attach when you need it. |
| NAT in one AZ for cost | The AZ goes down, your service goes with it. |
| WAF rule changes in `BLOCK` mode straight to prod | Bricks real users. Always `COUNT` → review → enforce. |

## Security defaults

- VPC Flow Logs on.
- GuardDuty on at the org level.
- Security Hub aggregated to a security account.
- Reachability Analyzer for ad-hoc "can A actually reach B" questions; Network Access Analyzer for posture audits.
- Block Public Access (S3 account-wide).
- No long-lived NAT-less paths that bypass logging.

## Observability defaults

- ALB / NLB access logs to S3.
- VPC Flow Logs to S3 with Athena pre-set on the bucket.
- API Gateway execution + access logs; correlated request ID across hops.
- CloudFront real-time logs for security-critical surfaces; standard logs to S3 for cost-bounded analysis.
- Alarms on `HealthyHostCount`, target `4xx`/`5xx` rates, NAT bandwidth, and WAF block rate.

## Cost considerations

- Cross-AZ traffic costs money — bias services toward AZ-locality where it doesn't hurt availability.
- Public IPv4 charges ~$3.60/mo per IP — switch to IPv6 / NAT-less where possible.
- NAT gateway data-processing is meaningful at scale; VPC endpoints often cheaper.
- CloudFront tiered pricing means moving from origin to edge for repeat traffic pays back fast for media-heavy sites.
- WAF charges per request — keep rule count tight; combine into rule groups.

## IaC hints

- CDK: `aws-cdk-lib/aws-ec2`'s `Vpc` construct's defaults are sane; override `natGateways: <one per AZ>` and `flowLogs`.
- Terraform: `terraform-aws-modules/vpc` is the de-facto module; pin a version.
- For multi-account org-wide networking, AWS Cloud WAN or Network Manager — IaC them, don't click.

## Verification checklist

- [ ] Subnet layout has public / private / isolated tiers, ≥ 3 AZs.
- [ ] No `0.0.0.0/0` inbound on any non-load-balancer SG.
- [ ] Database / cache SGs reference app SGs by ID, not CIDR.
- [ ] Flow Logs + ALB / API GW access logs enabled and shipped.
- [ ] WAF in front of every public origin; rate limit present.
- [ ] CloudFront in front of all origin S3 sites; OAC, not public.
- [ ] No IPv4-only assumptions in IaC if budgets care about public-IPv4 charges.
- [ ] Reachability Analyzer used to verify intended paths before launch.
