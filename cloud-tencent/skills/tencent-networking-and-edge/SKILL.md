---
name: tencent-networking-and-edge
description: Design or audit Tencent Cloud networking and edge — VPC, subnets, route tables, CLB (Classic + Application L4/L7), NAT Gateway, EIP, DNSPod, CDN, EdgeOne (CDN + WAF + DDoS + Workers), Anti-DDoS (Basic / Advanced / Pro), WAF, VPN Connections, Direct Connect, Cloud Connect Network (CCN). Use when standing up a new VPC, exposing a service publicly, or hardening edge posture.
---

# Tencent Networking and Edge

## When to use

- Designing a new VPC for a region or workload.
- Exposing an internal service to the internet via CLB or EdgeOne.
- Configuring DNS for a China domain (ICP required) or an International domain.
- Tuning TLS, WAF, or DDoS posture at the edge.
- Auditing east-west connectivity (VPC peering, CCN, VPN, Direct Connect).
- Tracking down NAT data charges or cross-AZ traffic costs.

## VPC layout — the production default

- One VPC per environment (dev / staging / prod) with non-overlapping CIDRs. Multi-account per environment is the correct blast-radius boundary for regulated workloads.
- CIDR: `/16` per VPC. `/20` or `/21` per subnet — leave room for expansion.
- Subnets per AZ across at least **two AZs** in the region (Tencent Cloud regions typically have 3–6 AZs):
  - `public` (with `Route: 0.0.0.0/0 → NAT Gateway` or directly routed for CLB) — only for load balancers and NAT gateways.
  - `private` (routed through NAT) — application CVM, TKE node pools, SCF (when VPC-attached).
  - `isolated` (no default route out) — databases, CDB, Redis, CFS.
- VPC Flow Logs to CLS for security baseline (at minimum REJECTED traffic). Enable ALL-traffic logging for forensics-ready production accounts.

## Subnet, Security Group, and route discipline

- Security Groups (SG): stateful. Use SG references in rules (`sg-app` can reach `sg-db` on port 3306), not raw CIDR for intra-VPC traffic.
- Never `0.0.0.0/0` inbound on a database or cache SG.
- No `0.0.0.0/0` inbound on port 22 (SSH) or 3389 (RDP). Use **Tencent OrcaAgent** (SSM-equivalent) or VPN for remote access.
- Route tables: each subnet tier gets its own route table. Private subnets route to the NAT Gateway; isolated subnets have no default route.

## NAT and egress

- Deploy **one NAT Gateway per AZ** for high availability. Routing across AZs through a single NAT Gateway is a hidden single point of failure and adds cross-AZ traffic cost.
- For high-volume egress to Tencent Cloud APIs, prefer **VPC Endpoint** (Private Connect / PrivateLink) to keep traffic off NAT and on the internal backbone.
- For controlled internet egress with inspection (egress firewall), combine NAT Gateway with **Cloud Firewall** in egress mode — FQDN-based allow-lists for strict environments.

## CLB (Cloud Load Balancer)

| Use case | CLB type |
| --- | --- |
| HTTP/HTTPS with host- / path-based routing, SNI | Application CLB (Layer 7) |
| TCP/UDP with low latency or static IP requirement | Classic CLB (Layer 4) |
| Internal service-to-service, microservice mesh | Internal CLB (Application or Classic, internal scheme) |
| Cross-region load balancing | Anycast EIP + Application CLB in multiple regions |

Application CLB defaults:
- HTTP → HTTPS redirect listener. Never serve production traffic on plain HTTP.
- TLS: minimum TLS 1.2; prefer the "High Security" cipher policy (excludes RC4, DES, weak DHE).
- Access logs: to CLS for security analysis and SLA reporting.
- Health checks: configure at the listener level to reflect real application readiness, not just TCP connectivity.
- Deletion protection: enable on prod CLBs to prevent accidental deletion via console or automation.
- **CLB direct pod binding (EKS / TKE VPC-CNI):** pods registered directly as CLB backends — bypasses node-port overhead and reduces latency.

## EIP (Elastic IP)

- Allocate EIPs in IaC, not via console, so they survive instance termination as a named resource.
- Bandwidth billing: choose by-bandwidth for steady predictable egress; by-traffic for bursty or idle-heavy workloads.
- BGP EIPs for most regions. Anycast EIP available for multi-region load balancing.
- **China accounts**: public EIPs on internet-facing CLBs require ICP filing for the domain pointing at them.

## DNS — DNSPod

- DNSPod is Tencent's DNS service, available as both a free tier (via `dnspod.cn`) and as part of Tencent Cloud DNS (`cloud.tencent.com/product/dns`).
- For China domains: ICP filing is a prerequisite for any DNS record pointing to a public IP on a China-region resource.
- Record types: A, AAAA, CNAME, MX, TXT (for SPF/DKIM/DMARC), SRV, CAA. Use CAA records to restrict which CAs can issue for your domains.
- Load balancing at DNS level: weighted records, geographic routing, and health-check-based failover are available on paid DNSPod tiers.
- TTL: set 600 s (10 min) for most records during steady state; lower to 60 s before planned DNS changes, then restore.
- DNSSEC: available on paid DNSPod plans — enable for any high-value domain to protect against on-path resolver attacks.

## CDN

- Use Tencent CDN for caching and acceleration of static assets and media. Nodes are dense in mainland China — advantageous for China-targeted applications.
- Origin: point to a private CLB or COS bucket (via COS static hosting), not to bare CVM IPs.
- HTTPS: enforce HTTPS-only; configure HSTS headers at the CDN edge.
- Cache rules: explicit cache-control policies per file extension / path; do not rely on upstream cache headers alone.
- WAF integration: CDN does not natively include WAF — for WAF on CDN-fronted traffic, use **EdgeOne** instead of plain CDN.
- **China CDN** requires ICP filing for the accelerated domain. Without ICP, mainland China nodes will not serve traffic.

## EdgeOne — modern edge platform

EdgeOne replaces the older CDN + WAF patchwork with an integrated platform: CDN, Layer 7 WAF, DDoS mitigation, Bot Management, and serverless **Edge Functions** (JavaScript / WASM Workers).

- **When to prefer EdgeOne over CDN + WAF separately:** any public-facing web application, API gateway edge, or site where WAF and acceleration must share the same edge node for lowest latency.
- WAF: managed rule sets (OWASP Top 10, Bot signatures, IP reputation) + custom rules. Add rate-based rules as a baseline against credential stuffing and scraping.
- DDoS: EdgeOne provides L3/L4/L7 DDoS mitigation at the edge. Basic mitigation is included; Advanced protection levels are configurable based on traffic profile.
- Edge Functions: JavaScript / WASM Workers executed at the PoP. Use for header manipulation, A/B routing, auth at the edge, request rewriting. Not a replacement for SCF — limited CPU/memory budget per invocation.
- **China EdgeOne**: mainland China acceleration via EdgeOne also requires ICP filing on the accelerated domain.

## Anti-DDoS (Basic / Advanced / Pro)

- **Anti-DDoS Basic**: included with every Tencent Cloud account. Provides shared DDoS mitigation on public IPs. Suitable for low-risk services.
- **Anti-DDoS Advanced (Dayu)**: dedicated mitigation bandwidth (10–300 Gbps), scrubbing centers, BGP high-protection IPs. Use for internet-facing game servers, financial APIs, or any service that has been targeted historically.
- **Anti-DDoS Pro**: applies protection to existing public IPs without changing IP. Suitable for protecting CLB EIPs and CVM instances in-place.
- Routing: in an attack, traffic is pulled to Tencent's scrubbing center, cleaned, and forwarded to origin. Configure origin IP whitelisting to only accept traffic from Tencent scrubbing center CIDR ranges.

## WAF (Cloud WAF)

- Modes: **observation mode** first — let WAF log without blocking for at least 48 hours on real traffic. Switch to enforcement mode only after reviewing false positives.
- Managed rules: OWASP Top 10, CVE-based virtual patching, bot signatures.
- Custom rules: IP allow/block, rate limiting, regex match on request fields.
- Integration: WAF can front a CLB (in CLB mode) or operate in CNAME mode (DNS redirect). CLB mode is preferred for lower-latency inspection.

## Cross-VPC / cross-account / hybrid connectivity

- **Cloud Connect Network (CCN)**: Tencent's hub-and-spoke private WAN. Attach multiple VPCs (across regions and accounts) to a CCN instance. CCN handles routing between attached VPCs without explicit peering. Use for ≥ 3 VPCs or any multi-region topology.
- **VPC Peering**: point-to-point. Use for exactly two VPCs with stable, no-transitive requirements. Non-overlapping CIDRs required.
- **VPN Connections**: site-to-site IPsec VPN to on-premises. Use Tencent's VPN Gateway; supports IKEv1 and IKEv2.
- **Direct Connect**: dedicated private link between a Tencent Cloud region and an on-premises data center or colocation facility. Use when VPN latency or bandwidth is insufficient. Attach to CCN for multi-region connectivity without additional tunnels.
- **Private Connect** (PrivateLink equivalent): expose a CLB-backed service to another VPC without VPC peering. Consumer VPC gets a private endpoint; traffic stays on the Tencent backbone; provider's VPC CIDR is not exposed.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Single NAT Gateway for all AZs | AZ outage kills all outbound connectivity. One NAT per AZ minimum. |
| Database SG with `0.0.0.0/0` "temporarily" | Never reverted. Port 3306 or 6379 exposed to the internet. |
| Public COS bucket serving web assets without CDN | No edge caching, direct cross-region egress costs, and one ACL mistake exposes everything. |
| Default VPC for production workloads | Predictable CIDR, default security group allows all intra-VPC, no isolation. Create a purpose-built VPC. |
| CDN without HTTPS enforcement | Users hit plain HTTP; MITM on caffeine-shop WiFi. HTTPS-only, HSTS. |
| WAF immediately in block mode | First week of block mode breaks real users. Count mode first, then enforce. |
| VPC peering mesh for >3 VPCs | O(n²) peering relationships; routing becomes unmanageable. Use CCN. |
| Hard-coded CVM public IP in firewall rules | IPs change on stop/start unless an EIP is allocated. Allocate EIPs for fixed references. |

## Security defaults

- VPC Flow Logs on to CLS.
- Cloud Firewall in monitoring mode at minimum; egress filtering for any environment that handles sensitive data.
- All CLBs: HTTPS-only; no TLS 1.0 / 1.1; WAF fronted or EdgeOne used for public-facing services.
- Block all public access on COS by default — serve content through CDN / EdgeOne.
- No inbound `0.0.0.0/0` on any SG except CLB listeners on port 80/443.
- Anti-DDoS Advanced for any internet-facing game or financial API with a known threat history.

## Observability defaults

- CLB access logs to CLS.
- VPC Flow Logs to CLS (REJECT tier at minimum; ALL for forensics).
- DNSPod health checks wired to an alert channel — catch DNS-level outages before users do.
- Cloud Monitor alarms on CLB `Unhealthy Host Count > 0`, `4xx rate`, `5xx rate`, NAT Gateway bandwidth utilization > 80%.
- EdgeOne / WAF: block event rate and top blocked IPs to a CLS dashboard; alert on sudden spikes.

## Cost considerations

- NAT Gateway: charges per hour + per GB of data processed. VPC endpoints eliminate NAT charges for Tencent Cloud API traffic.
- CLB: charges per hour (Application CLB) + per LCU (Load Capacity Unit) based on connections, bandwidth, and requests. Avoid over-provisioning CLB capacity configurations.
- EIP: idle EIPs (not attached to a running resource) incur an idle fee. Release unneeded EIPs.
- CDN: charged per GB of egress from edge nodes. China-region CDN traffic is billed separately from International. Minimize origin pull by maximizing cache hit rate.
- EdgeOne: flat subscription + per-request fees for edge functions. Evaluate against CDN + WAF + DDoS costs combined.
- Direct Connect: billed on port capacity + data transfer. Size the port to actual sustained bandwidth, not theoretical peak.

## IaC hints

- Terraform resources: `tencentcloud_vpc`, `tencentcloud_subnet`, `tencentcloud_route_table`, `tencentcloud_nat_gateway`, `tencentcloud_clb_instance`, `tencentcloud_eip`, `tencentcloud_ccn`.
- For CCN: `tencentcloud_ccn` + `tencentcloud_ccn_attachment` per VPC / VPN / Direct Connect instance.
- For Private Connect: `tencentcloud_vpc_end_point_service` + `tencentcloud_vpc_end_point`.
- For WAF: `tencentcloud_waf_domain` + `tencentcloud_waf_custom_rule`.
- Tag all networking resources with `Environment`, `Owner`, `CostCenter` — network resources outlive applications and become orphaned without ownership metadata.

## Verification checklist

- [ ] VPC CIDR does not overlap with on-premises or peer VPCs.
- [ ] Subnet tiers: public (LBs only), private (app), isolated (data) across ≥ 2 AZs.
- [ ] One NAT Gateway per AZ for production.
- [ ] No `0.0.0.0/0` inbound on any SG except CLB port 80 / 443.
- [ ] Database and cache SGs reference app SGs by ID, not CIDR.
- [ ] VPC Flow Logs enabled and shipped to CLS.
- [ ] WAF in observation mode before enforcement; rate-limit rules present.
- [ ] CDN / EdgeOne enforcing HTTPS-only; HSTS header set.
- [ ] For China accounts: ICP filing confirmed before any public DNS record or EIP goes live.
- [ ] CCN used instead of peering mesh when ≥ 3 VPCs are connected.
