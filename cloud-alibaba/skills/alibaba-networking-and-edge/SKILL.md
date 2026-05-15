---
name: alibaba-networking-and-edge
description: Design or audit Alibaba Cloud networking — VPC, VSwitch, route tables, Security Groups, ENI, SLB/ALB/NLB, NAT Gateway, EIP, CEN (cross-region), CDN, DCDN, Anti-DDoS Pro/Premium, WAF, IPv6 Gateway. Use when standing up a new VPC, exposing a service, connecting regions, or hardening edge.
---

# Alibaba Networking and Edge

## When to use

- Designing a new VPC or extending an existing one into additional zones.
- Exposing an internal service to the internet or to another VPC / region.
- Connecting multiple VPCs across regions or to on-premises with CEN.
- Tuning TLS, WAF, CDN, or DDoS posture at the edge.
- Auditing east-west Security Group rules for over-permissive access.
- Tracking down NAT Gateway data-processing charges or cross-zone traffic costs.

## VPC layout — the production default

- One VPC per environment per region (dev / stage / prod). A single account typically holds the China-region VPC and a separate account holds the International-region VPC — they cannot be peered or joined in the same CEN across the China/International boundary.
- CIDR: `/16` per VPC; `/19` or `/20` per VSwitch. Leave non-overlapping address space for future CEN attachment.
- VSwitches per zone, across at least **2 availability zones** (3 where the region supports it):
  - `public` zone VSwitches — only for ALB / NLB / NAT Gateway.
  - `private` zone VSwitches — application compute (ECS, ACK pods, FC VPC mode).
  - `isolated` zone VSwitches — databases, internal-only services (RDS, Redis, PolarDB).
- IPv6: enable at VPC creation if any international-facing service or IPv6-mandated workload is planned. Retrofitting IPv6 to an existing VPC is possible but disruptive.
- VPC Flow Log: enable for all production VPCs; ship to SLS (Simple Log Service) for query. At minimum capture `REJECT` flows; enable `ALL` for forensics-ready accounts.

## VSwitch and Security Group discipline

- Security Groups: stateful; the primary east-west control. Reference groups by Group ID in inbound rules (`sg-app-tier` → `sg-db-tier:3306`); never use raw CIDR for intra-VPC references.
- An ENI (Elastic Network Interface) can hold up to 5 Security Groups. Bind roles precisely (web, app, db, cache) rather than one catch-all group.
- **No `0.0.0.0/0` inbound** on any Security Group protecting a database, cache, or application instance.
- **No `0.0.0.0/0` inbound on port 22**: use Cloud Assistant for shell access; disable SSH inbound entirely.
- Route tables: one custom route table per subnet tier; avoid the default route table for anything other than the public VSwitch tier.

## NAT and egress

- One **Enhanced NAT Gateway** per VSwitch availability zone for high-availability egress. Cross-zone NAT is both a latency and cost trap.
- For traffic to Alibaba Cloud services (OSS, RDS, Redis internal endpoints), configure **VPC private endpoints** — traffic stays on the backbone, no NAT charges, lower latency.
- For controlled internet egress, deploy a **Cloud Firewall** managed egress policy or a dedicated NAT Gateway per environment. Never share a NAT Gateway between prod and dev.
- EIP (Elastic IP) for NAT Gateway: allocate at least 2 EIPs per NAT Gateway for bandwidth redundancy.

## Load balancing

| Use case | Pick |
| --- | --- |
| HTTPS service, host/path-based routing, L7 features | ALB (Application Load Balancer) |
| TLS passthrough, UDP, extreme TPS, static IP | NLB (Network Load Balancer) — L4 |
| Legacy workloads, existing SLB dependency | SLB (Classic / Server Load Balancer) — migrate to ALB/NLB for new work |
| Global acceleration for APAC users | Alibaba Cloud Global Accelerator (GA) in front of ALB / NLB |
| Internal service-to-service | Internal ALB or NLB with private VSwitch zone |

**ALB defaults:**

- HTTP → HTTPS redirect listener (80 → 443).
- TLS policy: `TLSCipherPolicy_1_3` preferred; minimum `TLSCipherPolicy_1_2_Strict`.
- Access log: ship ALB access logs to SLS or OSS; at minimum OSS for cost-bound analysis.
- Deletion protection: on.
- Health check: protocol matches backend (HTTP for apps, TCP for raw services); grace period ≥ 30 s.
- WAF attachment: associate Alibaba Cloud WAF with the ALB listener for any public-facing HTTPS service.

## NAT Gateway

- **Enhanced NAT Gateway** (2020+) for new deployments; classic NAT is deprecated.
- Bandwidth package: allocate per-EIP bandwidth; size to 90th-percentile burst, not average.
- SNAT and DNAT: separate SNAT entry per application tier rather than one wildcard rule — easier to audit.
- Idle timeout: default 900 s; reduce for services with many short-lived connections to avoid SNAT port exhaustion.

## CEN (Cloud Enterprise Network) — cross-region connectivity

- CEN is Alibaba's Transit-Gateway equivalent, with a backbone spanning all Alibaba regions.
- Attach VPCs in multiple regions to a CEN instance to route traffic over the backbone — lower latency and jitter than public internet.
- **China ↔ International**: CEN can connect China and International VPCs, but cross-border data transfer still requires a CAC security assessment for regulated data. Verify compliance before routing production data cross-border via CEN.
- Bandwidth package: purchase a CEN bandwidth package per region pair for guaranteed throughput. Without a package, cross-region traffic is best-effort.
- Route policy: define prefix filters and route policies to limit which routes are advertised across regions; prevent accidental flattening of trust boundaries.
- VPN Gateway: site-to-site IPsec VPN or Smart Access Gateway (SAG) for hybrid cloud; attach to CEN for transitive on-prem routing.

## CDN and DCDN

- **CDN**: cache-heavy static assets (images, CSS, JS, media). Origin should be OSS internal endpoint; sign URLs for private content.
- **DCDN (Dynamic CDN)**: dynamic + static content on the same distribution; better for web applications mixing cacheable and uncacheable routes.
- HTTPS: enforce HTTPS-only; redirect HTTP to HTTPS at the CDN edge node.
- Origin protocol: HTTPS between edge and origin for end-to-end encryption.
- WAF integration: Alibaba Cloud WAF can be attached to CDN / DCDN for DDoS and application-layer protection.
- ICP filing: serving content from Chinese CDN nodes to mainland China audiences requires an ICP Bei'an. International CDN nodes do not require ICP.

## Anti-DDoS and WAF

### Anti-DDoS Pro (China) / Anti-DDoS Premium (International)

- Anti-DDoS Pro / Premium proxies traffic through scrubbing centers; traffic is cleaned before forwarding to the origin.
- Use for workloads with public domain exposure that have been or are likely to be targeted.
- Business Edition includes CC (Challenge Collapsar) protection and HTTP flood mitigation.
- Combine with CDN / DCDN: CDN absorbs cache-hit traffic; Anti-DDoS handles volumetric attacks at scrubbing capacity.
- Origin address: configure your ALB or ECS IP as the Anti-DDoS back-to-origin address; restrict ALB / SG inbound to Anti-DDoS forwarding IP ranges only.

### WAF (Web Application Firewall)

- Attach to ALB listener or CDN distribution.
- Enable Alibaba Cloud Managed Rule Groups (basic protection, known-bad inputs, scanner IPs, IP reputation).
- Rate limiting: configure a rate rule on every public API path; 100 req/5 min per IP as a starting baseline.
- Custom rules: start in **detection** mode; promote to **blocking** after reviewing real-traffic reports to avoid false positives.
- Bot management: enable for any login / registration / search endpoint exposed to public.
- WAF logs to SLS: enable full request log for any PCI / compliance scope; sampled log for cost-bounded environments.

## IPv6 Gateway

- Enable at VPC creation; allocate IPv6 CIDRs per VSwitch.
- For internet-facing services, associate EIPv6 with the ALB or ENI.
- For egress-only IPv6 (no inbound): configure an **Egress-Only Internet Gateway** at the VPC level.
- Security Group rules for IPv6 (`::` / `::/0`) are separate from IPv4 rules — audit both dimensions.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Single AZ placement for all VSwitches | AZ outage takes the entire environment. Always multi-zone. |
| `0.0.0.0/0` inbound on a database Security Group | Direct internet exposure; one public ECS compromise leads to database access. |
| Classic SLB for new services | Classic SLB lacks SNI, HTTP/2, gRPC, advanced routing; ALB is the successor. |
| Shared NAT Gateway between prod and dev | Dev runaway process saturates NAT bandwidth; prod drops packets. |
| CEN cross-border without CAC assessment | Potentially violates PIPL / DSL; regulatory penalty risk for China operations. |
| CDN without ICP for China region audiences | CDN nodes in mainland China require ICP Bei'an; traffic may be blocked by ISPs. |
| VPC Flow Log with no retention policy | SLS and OSS logs accumulate indefinitely; apply SLS log store TTL and OSS lifecycle. |
| WAF blocking rules enabled without detection-mode review | Legitimate requests blocked on day one; customer-facing outage. Count → review → enforce. |

## Security defaults

- VPC Flow Logs on for all production VPCs; ship to SLS.
- Cloud Firewall enabled at account level; internet traffic policy set to `default-deny` except declared services.
- Security Group rule review: no `0.0.0.0/0` inbound except on ALB / NLB listener SGs.
- ALB: TLS 1.2+ enforced; HTTP-to-HTTPS redirect on.
- WAF attached to every public ALB; managed rule groups active.
- Anti-DDoS Pro / Premium enabled for any domain under active or anticipated volumetric attack.
- SSH (port 22) inbound: closed on all Security Groups; Cloud Assistant for interactive access.
- Outbound Security Group: default-deny; explicitly allow egress to known destinations (OSS endpoint, NTP, HTTPS).

## Observability defaults

- ALB: access log to SLS; alarms on `HealthyServerCount`, `5xx` rate, and `RequestCount` drop.
- NAT Gateway: alarm on `BandwidthUsage` nearing cap; `SnatConnections` for port exhaustion signal.
- CEN: cross-region bandwidth utilization alarm.
- WAF: alarm on block rate spike (potential attack) and allow rate spike (potential bypass).
- Anti-DDoS: alert on scrubbing activation, traffic volume threshold.
- VPC Flow Log: SLS alert on `REJECT` volume spike (lateral movement or misconfigured SG).

## Cost considerations

- **NAT Gateway data processing**: charged per GB; VPC private endpoints for OSS, RDS, Redis etc. bypass NAT — implement from day one.
- **EIP charges**: billed per hour when allocated even if unattached; release unused EIPs immediately.
- **CEN bandwidth packages**: cross-region bandwidth is expensive; audit which traffic must traverse CEN vs which can use OSS cross-region replication or CDN edge nodes.
- **CDN vs origin**: serving through CDN is cheaper than direct OSS egress for repeated assets; break-even is typically > 100 GB/month per asset set.
- **ALB vs SLB pricing**: ALB uses an LCU (Load Capacity Unit) model; benchmark expected TPS and rule complexity to compare against SLB bandwidth billing.
- **Anti-DDoS Pro**: instance cost + bandwidth overage; size cleaning bandwidth to your 90th-percentile legitimate traffic peak to avoid overage charges under attack.

## IaC hints

- Terraform: `alicloud_vpc`, `alicloud_vswitch`, `alicloud_security_group`, `alicloud_security_group_rule`, `alicloud_nat_gateway`, `alicloud_eip`, `alicloud_alb_load_balancer`, `alicloud_nlb_load_balancer`, `alicloud_cen_instance`, `alicloud_cdn_domain`. Provider ≥ 1.220.
- Pin VSwitches to explicit zone IDs (`zone_id`), not availability zone aliases that may resolve differently across API versions.
- CEN attachment: `alicloud_cen_instance_attachment` + `alicloud_cen_bandwidth_package` + `alicloud_cen_bandwidth_package_attachment`.
- For WAF: `alicloud_waf_domain` (or the newer `alicloud_wafv3_*` resources for WAF 3.0).

## Verification checklist

- [ ] VSwitch layout has public / private / isolated tiers, ≥ 2 zones.
- [ ] No `0.0.0.0/0` inbound on any non-load-balancer Security Group.
- [ ] Database / cache SGs reference application SGs by group ID, not CIDR.
- [ ] VPC Flow Logs enabled and shipped to SLS with bounded retention.
- [ ] WAF attached to every public ALB; rate rule configured.
- [ ] ALB TLS policy ≥ TLSCipherPolicy_1_2_Strict; HTTP redirect on.
- [ ] NAT Gateway per AZ; VPC private endpoints configured for Alibaba Cloud services.
- [ ] CEN cross-border compliance status confirmed before routing regulated data.
- [ ] CDN / DCDN ICP filing status confirmed for China-region audiences.
- [ ] IPv6 Security Group rules audited if IPv6 enabled on VPC.
