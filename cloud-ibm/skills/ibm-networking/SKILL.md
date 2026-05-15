---
name: ibm-networking
description: Design or audit IBM Cloud networking — VPC, subnets, Security Groups, ACLs, Public Gateways, Floating IPs, VPN-for-VPC, Transit Gateway, Direct Link, Cloud Internet Services, Private Path / Endpoint Gateways. Use when standing up a new VPC, connecting workloads, exposing services, or hardening network posture.
---

# IBM Cloud Networking

## When to use

- Designing a new VPC for a workload or environment.
- Connecting multiple VPCs or connecting IBM Cloud to on-premises networks.
- Exposing an internal service to the internet or to another VPC / account.
- Tuning TLS, WAF, and CDN posture at the edge via Cloud Internet Services.
- Auditing east-west connectivity (Transit Gateway, Direct Link, VPN, Endpoint Gateways).
- Tracking down NAT bandwidth costs or cross-zone data transfer charges.

## VPC layout — the default

IBM Cloud VPC uses a **zone-based** model: regions contain multiple zones (typically 3), each zone is an independent failure domain. Design for at least 2 zones in production; 3 for financial services or high-availability requirements.

- One VPC per environment (dev / stage / prod). Use separate IBM Cloud accounts for strong blast-radius isolation if compliance requires it.
- Address prefix: `/16` per VPC. Assign `/24` or `/20` per subnet — leave room for expansion. Address prefixes are per-zone.
- Subnets per zone:
  - `public-tier` (with Public Gateway) — only for inbound load balancers (VPC ALB).
  - `private-tier` (no Public Gateway, no Floating IP) — application workloads.
  - `data-tier` (no Public Gateway) — databases, caches, internal-only services.
- VPC Flow Logs: enable on every production VPC, shipping to a Cloud Object Storage bucket. Provides the audit trail for security analysis and network troubleshooting.
- Default Security Group: create and use workload-specific Security Groups immediately — never use the VPC default SG for production resources.

## Subnets, Security Groups, and ACLs

### Security Groups (stateful — primary control)

- Security Groups are stateful and resource-attached — the primary network control for IBM Cloud VPC.
- Reference Security Groups from Security Groups in rules: `sg-app-tier` can reach `sg-db-tier` on port 5432. Never use raw CIDR for intra-VPC communication.
- Default deny inbound. Only open ports that workloads actually need.
- No `0.0.0.0/0` inbound on any Security Group attached to a database, cache, or internal service.
- No `0.0.0.0/0` inbound port 22 (SSH). Use `ibmcloud is instance-console` or VPN-for-VPC for administrative access.
- Separate Security Group per tier (load balancer, application, database) — limits blast radius if one SG rule is misconfigured.

### Access Control Lists (stateless — secondary control)

- ACLs are stateless and subnet-attached. They add defense-in-depth for subnet-level controls.
- Keep ACLs simple — default allow for known-good traffic, explicit deny for known-bad CIDRs or ports.
- Complex ACL rules are easy to misconfigure (stateless means both inbound and outbound rules required for each flow). Use SGs as the primary enforcement mechanism.

### Public Gateway and Floating IPs

- Public Gateway: attached to a subnet, provides outbound internet access for all resources in the subnet. Use for `private-tier` subnets that need to download packages or call external APIs.
- One Public Gateway per zone — resources in different zones need their own gateway for HA.
- Floating IP: a single public IP assigned to one specific resource (VSI, VPC Load Balancer). Use only when you need a static inbound IP for a specific service.
- Never assign a Floating IP directly to a database or cache instance.

## VPC Load Balancer

| Use case | Pick |
| --- | --- |
| HTTPS service, host/path-based routing, WebSocket | VPC Application Load Balancer (ALB) |
| High-throughput TCP/UDP, static IP required, TLS passthrough | VPC Network Load Balancer (NLB) |
| Internal service-to-service (private-only) | Internal ALB or NLB with `private` type |
| Private Path cross-VPC service access | Private Path Network Load Balancer |

ALB defaults: HTTPS listener on port 443; HTTP listener redirects to HTTPS. TLS policy: `tls-1-2-2022` minimum (TLS 1.2 or 1.3). Back-end pools with health check configured on a non-default health path. Access logs shipped to COS.

## VPN-for-VPC

VPN-for-VPC provides IPsec site-to-site tunnels from your VPC to on-premises or to another VPC.

- Two VPN gateways for HA (one per zone in the VPC).
- IKEv2 with strong cipher profiles (`aes256` / `sha256` / DH group 14 or 19 minimum).
- Client-to-Site VPN for developer / admin access — not bastion hosts with open port 22.
- Use Transit Gateway for VPC-to-VPC connectivity at scale rather than chaining VPN tunnels.

## Transit Gateway

Transit Gateway connects multiple VPCs and optionally on-premises networks through a single hub — avoiding a full mesh of VPC peering connections.

- Global routing option: connects VPCs across regions.
- Local routing option: connects VPCs within the same region (lower latency, lower cost).
- Direct Link and VPN can terminate at Transit Gateway for a centralized hub-and-spoke model.
- Security: Transit Gateway is a routing plane — enforce Security Group rules at each VPC's resources to control east-west traffic between connected VPCs.
- Do not use Transit Gateway as a reason to loosen Security Group rules. Each VPC's security posture is independent.

## Direct Link

Direct Link provides dedicated, private, high-bandwidth connectivity between IBM Cloud and on-premises data centers or colocation facilities.

| Type | When |
| --- | --- |
| Direct Link Dedicated | Your own physical cross-connect to an IBM PoP; highest bandwidth, lowest latency. |
| Direct Link Connect | Through a network service provider (NSP) that already has a cross-connect to IBM; faster to provision. |
| Direct Link Exchange | Legacy; via a colocation exchange — largely superseded by Connect. |

- BGP configuration: set MED / local preference deliberately for failover; don't rely on default BGP behavior for HA.
- For HA: provision two Direct Link circuits from different providers or PoPs. VPN-for-VPC as backup.
- Direct Link does not encrypt traffic in transit — use application-layer TLS or IPsec overlay if the data requires encryption in transit over the physical link.

## Cloud Internet Services (CIS)

Cloud Internet Services is IBM Cloud's Cloudflare-powered edge — DNS, CDN, WAF, and DDoS protection for internet-facing workloads.

- DNS: authoritative DNS with 100% uptime SLA; DNSSEC supported.
- CDN / Cache: configure caching rules per content type; edge-cache static assets; bypass cache for authenticated API responses.
- WAF: IBM-managed OWASP ruleset as baseline. Add custom rules for application-specific patterns. Start in `Simulate` (log-only) mode before switching to `Block`.
- DDoS: always-on DDoS mitigation at the network and application layers — no configuration required.
- Rate limiting: configure per-URL rate limits against credential stuffing and scraping; set thresholds based on observed traffic patterns.
- TLS: enforce HTTPS-only (`Strict` TLS mode — origin must present a valid certificate). Minimum TLS 1.2; prefer TLS 1.3.
- Page rules / Transform rules: header injection for security headers (HSTS, CSP, X-Frame-Options) at the edge.
- Origin pull: CIS pulls from your VPC Load Balancer via a private Anycast connection when configured with a CIS-generated origin certificate — keeps origin private.

## Private Path and Endpoint Gateways

Endpoint Gateways (formerly VPE — VPC Service Endpoints) allow VPC workloads to consume IBM Cloud services (COS, ICD, Secrets Manager, Key Protect, etc.) over private IBM network — no public internet traversal, no NAT bandwidth charges.

- Create an Endpoint Gateway for every IBM Cloud service consumed from a VPC workload: COS, ICD, Secrets Manager, Key Protect, IAM, Container Registry.
- Endpoint Gateway IPs are in the VPC subnet you specify — configure Security Group rules to allow traffic from app subnets to the endpoint IPs.
- Private Path Network Load Balancer: expose your own service as a Private Path service, allowing other VPCs or accounts to consume it privately via a VPE — analogous to AWS PrivateLink.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Using the default VPC Security Group for production resources | Default SG is permissive; any new resource auto-joins it. Create workload-specific SGs. |
| Floating IP on a database VSI | Direct public IP on a database with a Security Group rule "temporarily" left open = exposure. Never. |
| Single-zone VPC for production | One zone failure takes down the workload. Multi-zone mandatory for HA. |
| No VPC Flow Logs | Network forensics and compliance audits become impossible without flow data. |
| Public Gateway on the data-tier subnet | Databases don't need outbound internet. Add Public Gateway only to private/app tier. |
| VPN-for-VPC with weak IKE policy (`aes128` / DH group 2) | Undersized cipher suite; exposed to downgrade attacks. |
| CIS WAF rules deployed to `Block` mode on day one | Blocks legitimate traffic. Always `Simulate` → review → `Block`. |
| Direct Link without backup VPN | Single circuit failure = complete connectivity loss. VPN-for-VPC as fallback mandatory. |

## Security defaults

- VPC Flow Logs on for every production VPC, shipping to a COS bucket with lifecycle policy.
- Security Groups deny-by-default inbound; open only specific ports to specific source SGs or CIDRs.
- No public endpoints (Floating IPs, Public Gateways) on database or cache subnets.
- Endpoint Gateways (VPE) for all IBM Cloud API calls from VPC workloads — keeps control-plane traffic private.
- CIS in front of every internet-facing origin; WAF OWASP baseline enabled; rate limiting configured.
- HTTPS-only at every layer — ALB listener, CIS TLS mode `Strict`, origin TLS.
- Direct Link traffic encrypted at application layer (TLS) — physical link is unencrypted by IBM Cloud.

## Observability defaults

- VPC Flow Logs to COS; retain 90 days minimum for security analysis.
- ALB access logs to COS; parse request rates, 4xx/5xx rates, backend health.
- CIS analytics: real-time traffic dashboard; alerts on WAF block rate spikes, DDoS mitigation events, origin error rate.
- IBM Cloud Monitoring alerts on: ALB `healthy_instances` falling below threshold, Public Gateway packet loss, VPN tunnel `Down` state.
- Activity Tracker: VPC resource creation/deletion events, Security Group rule changes, Direct Link configuration changes.

## Cost considerations

- Public Gateway data processing: outbound internet traffic through Public Gateway incurs data charges. Prefer Endpoint Gateways for IBM Cloud service calls — no data charge.
- Cross-zone traffic: traffic between zones within a VPC incurs data transfer charges. Place co-dependent services in the same zone where latency allows; use zone-local load balancer targets.
- CIS bandwidth: CIS caches reduce origin bandwidth costs significantly for static content — configure aggressive cache TTLs for assets.
- VPN-for-VPC: billed per gateway hour plus per-GB data processed.
- Direct Link: flat monthly port fee plus per-GB global egress (local routing: no data charges).
- Transit Gateway: per-gateway hour plus per-GB data processed. Use local routing when VPCs are in the same region to avoid global routing fees.

## IaC hints

- Terraform resources: `ibm_is_vpc`, `ibm_is_subnet`, `ibm_is_security_group`, `ibm_is_security_group_rule`, `ibm_is_public_gateway`, `ibm_is_floating_ip`, `ibm_is_lb` (VPC Load Balancer), `ibm_is_vpn_gateway`, `ibm_tg_gateway` (Transit Gateway), `ibm_dl_gateway` (Direct Link), `ibm_is_endpoint_gateway` (VPE).
- CIS: `ibm_cis` (instance), `ibm_cis_domain`, `ibm_cis_waf_rule`, `ibm_cis_rate_limit`.
- Subnet and address prefix: create address prefixes explicitly per zone rather than relying on default auto-prefix behavior.
- Security Group rules: reference Security Group IDs (not CIDRs) in `remote` field for intra-VPC rules.
- VPC Flow Logs: `ibm_is_flow_log` resource pointing to a COS bucket with an IAM authorization for the VPC to write logs.

## Verification checklist

- [ ] VPC has at least 2 zones (3 for production HA); subnets per zone per tier.
- [ ] No `0.0.0.0/0` inbound on any database or cache Security Group.
- [ ] No Floating IPs on database or cache instances.
- [ ] VPC Flow Logs enabled; COS destination bucket configured with lifecycle policy.
- [ ] ALB / NLB health checks configured on meaningful health endpoints.
- [ ] Endpoint Gateways created for COS, ICD, Secrets Manager, Key Protect, and Container Registry.
- [ ] CIS in front of all internet-facing origins; WAF enabled in Simulate mode before Block.
- [ ] TLS 1.2 minimum at every layer; HTTPS-only enforced.
- [ ] Direct Link has VPN-for-VPC backup; BGP failover tested.
- [ ] Transit Gateway routing tables reviewed — no unintended cross-VPC reachability.
