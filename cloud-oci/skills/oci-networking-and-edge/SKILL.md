---
name: oci-networking-and-edge
description: Design or audit OCI networking — VCN, subnets, route tables, security lists, Network Security Groups (NSGs), Load Balancer (LBaaS L7 vs Network LB), WAF, DNS Traffic Steering, FastConnect, Site-to-Site VPN, Service Gateway, IPv6. Use when standing up a new VCN, exposing a service, controlling east-west traffic, or hardening edge access.
---

# OCI Networking and Edge

## When to use

- Designing a VCN for a new workload or environment.
- Deciding how to expose an application to the internet or to other VCNs.
- Tuning load balancing, TLS policy, or WAF posture.
- Establishing private connectivity to on-premises via FastConnect or VPN.
- Auditing Security Lists and NSGs for overly permissive rules.
- Diagnosing unexpected traffic paths or missing Service Gateway routes.

## VCN layout — the structured default

- One VCN per environment (dev / staging / prod) within its own compartment. Accounts (tenancies) are OCI's hardest blast-radius boundary — if you have compliance pressure, use a separate tenancy per environment.
- CIDR: `/16` per VCN. Regional subnets preferred over AD-specific subnets — OCI regional subnets span all Availability Domains in the region and simplify layout.
- Subnet tiers per VCN:
  - **Public subnet** (`/24` or `/26`): route table has an Internet Gateway entry. Only load balancers and bastion hosts reside here; no application or database instances.
  - **Private subnet** (`/22` or `/20`): route table uses a NAT Gateway for outbound internet. Application workloads (Compute, OKE nodes, Functions).
  - **Database subnet** (`/24`): no route to the internet — route table is empty or contains only a Service Gateway. All database services (ATP private endpoint, MySQL, Block Volume-backed DBs) go here.
- IPv6: enable a `/56` OCI-assigned IPv6 CIDR on every VCN at creation — retrofitting IPv6 later is more disruptive. Dual-stack addressing eliminates public IPv4 charges for workloads that can serve IPv6 clients directly.
- VCN flow logs: enable for every subnet in production. Flow logs ship to OCI Logging and are the basis for security forensics and cost audit (cross-AD traffic).

## Security Lists vs Network Security Groups

- **Security Lists** apply to every VNIC in the subnet — use them for subnet-level defaults that apply uniformly (e.g., allow egress on port 443 from private subnets to the Service Gateway CIDR).
- **Network Security Groups (NSGs)** apply at the VNIC level and can reference other NSGs as sources — use NSGs for application-tier controls where you want `nsg-app` to reach `nsg-db:1521` without managing CIDRs.
- Default rule: stateful egress-all in security lists. Restrict it to the minimum required egress CIDRs or replace with NSG rules per workload.
- Hard rule: no `0.0.0.0/0` ingress on a database or cache security list or NSG. Databases live in the database subnet with no IGW route — verify both the routing and the security rule layer.
- Prefer NSGs for all production workloads; security lists are for coarse subnet-boundary defaults and not the primary control.

## NAT and egress

- One NAT Gateway per region per VCN; it is highly available without additional configuration.
- For outbound traffic to OCI services (Object Storage, Autonomous Database, Logging, etc.), always add a **Service Gateway** route that bypasses the NAT Gateway — traffic stays on the OCI backbone, incurs no NAT bandwidth charges, and avoids the internet entirely.
- For controlled internet egress from workloads, route through a NAT Gateway. For more granular filtering (URL-based egress control), place a Network Virtual Appliance (NVA) in a transit VCN with DRG route distribution.

## Load balancing

| Use case | Pick |
| --- | --- |
| HTTPS service, host/path routing, SSL termination, WebSocket | Load Balancer (LBaaS) — flexible shape, Layer 7 |
| TCP passthrough, UDP, static IP needed, very high TPS | Network Load Balancer (NLB) — Layer 4, static IPs |
| Internal service-to-service without public IP | Internal Load Balancer on a private subnet |

Load Balancer (LBaaS) defaults:
- Flexible shape — set minimum and maximum bandwidth rather than picking a fixed shape.
- Listener: HTTPS (port 443) with TLS policy `oci-tls-1-3` and an OCI Certificate Service certificate. HTTP listeners on port 80 should redirect to HTTPS — add a redirect rule set on the backend set.
- Backend set: health check on the application's `/health` or equivalent path, not the root.
- Security list / NSG: allow 443 inbound from `0.0.0.0/0` and `::/0` (IPv6) on the LB subnet; allow the backend port inbound from the LB subnet CIDR on the application subnet.
- Access logs and error logs to OCI Logging via a log group in the same compartment.

## Web Application Firewall

- Enable WAF on the Load Balancer (inline WAF, no DNS change required) or via WAF Policy attached to a public Load Balancer or Edge WAF for globally distributed protection.
- Baseline protection: enable the OCI-managed rule set (protection rules for OWASP Top 10 categories). Start rules in `detect` mode; review findings in the WAF log for one week before switching to `block`.
- Rate limiting: add a rate limiting rule scoped to the client IP; a default of 1000 requests per minute per IP is a reasonable starting point for most APIs — tune based on your traffic profile.
- WAF logs to OCI Logging; alarm on block event rate spike (signals a credential-stuffing or scrape attack).

## DNS and Traffic Steering

- **OCI DNS (authoritative):** create a public zone for your domain. Use zone management for all production DNS — no console-only edits.
- **Traffic steering policies:** use latency-based or geolocation steering when serving from multiple OCI regions. Health-check-based failover policies automate regional failover when the primary endpoint fails.
- Private DNS: OCI private zones resolve within the VCN without leaving the OCI backbone — use private zones for internal service discovery instead of hardcoded IP addresses.
- Custom resolvers: when your on-premises DNS needs to resolve OCI private zone names (or vice versa), use an OCI DNS resolver with forwarder and listener endpoints — no self-managed BIND instances.

## FastConnect and Site-to-Site VPN

- **FastConnect:** dedicated private connectivity from on-premises to OCI. Use when you need > 1 Gbps, consistent latency, or regulatory mandates for private connectivity. FastConnect is Layer 2; you provision a virtual circuit over a provider or colocation cross-connect.
- **Site-to-Site VPN:** IPsec VPN over the internet. Suitable for lower-bandwidth or secondary-path connectivity. Use IKEv2, BGP routing, and redundant tunnels (two tunnels per CPE per connectivity standard).
- Dynamic Routing Gateway (DRG): the hub for all VCN-to-VCN, VCN-to-on-premises, and VCN-to-FastConnect attachments. One DRG per region is the standard layout; DRG route tables control which attachments can reach each other.
- Local Peering Gateway (LPG): for same-region VCN-to-VCN peering where DRG is not yet deployed. LPG is simpler but non-transitive; use DRG with route distribution for any mesh that might grow beyond two VCNs.

## Service Gateway

- Add a Service Gateway to every VCN's private and database subnet route tables. Route the `All <region> Services in Oracle Services Network` CIDR label to the Service Gateway.
- This covers Object Storage, Autonomous Database, Logging, Monitoring, OCI Vault, and most OCI control-plane APIs without traversing the NAT Gateway or the internet.
- Service Gateway supports intra-VCN traffic toward OCI services only — it is not a path to the internet.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Databases in the public subnet | One missing security list rule = internet-reachable database. Database subnet has no IGW route by design. |
| Security Lists as the only control layer | Security Lists are applied uniformly — you cannot vary rules by workload within a subnet. NSGs are the right tool for application-tier differentiation. |
| No Service Gateway, all egress via NAT | NAT Gateway charges for data processing. Service Gateway routes OCI API traffic for free. |
| `0.0.0.0/0` on a database NSG ingress | There is no justified case for this. Scope to the application subnet CIDR or the NSG of the app tier. |
| Single HTTPS listener serving multiple tenants without SNI-based routing | All tenants share a TLS certificate. Use hostname-based routing rules and upload separate certificates per hostname. |
| WAF rules deployed in `block` mode with no detection window first | The first deployment blocks legitimate traffic from unusual user agents or content types. Detect → tune → block. |
| No VCN flow logs | Forensics and cost audit (cross-AD traffic) become impossible after an incident. |

## Security defaults

- VCN flow logs on for all production subnets.
- Service Gateway in every private subnet route table — all OCI API traffic off the NAT path.
- NSGs for all application-tier ingress/egress; Security Lists used only for subnet-wide baseline defaults.
- No public IP on any database VNIC — private endpoint only.
- WAF in detect mode before launch; block mode within 2 weeks of stable traffic.
- Cloud Guard networking detector recipe active — surfaces open security list rules, publicly-accessible load balancers without WAF, and missing flow logs.

## Observability defaults

- Load Balancer access logs and error logs to OCI Logging.
- VCN flow logs to a dedicated log group; retention ≥ 90 days for security-relevant analysis.
- DNS query logs from the private resolver for internal service resolution troubleshooting.
- Alarms on LB `ActiveConnections`, `ResponseErrors`, and backend health check failure count.
- WAF alarm on `BlockedRequests` spike above baseline.

## Cost considerations

- OCI does not charge per-hour for public IP addresses the way some other clouds do — but you still pay for inbound and outbound data transfer beyond the free monthly allowance.
- Cross-AD (cross-Availability Domain) data transfer within a region is billable; minimize synchronous cross-AD calls for high-throughput paths by placing co-dependent services in the same AD where HA allows it.
- Service Gateway routes to OCI services incur no data-processing charge — always prefer it over NAT Gateway for OCI service API traffic.
- Load Balancer bandwidth charges are based on the flexible shape minimum × hours plus data processed above the minimum. Right-size the minimum bandwidth; burst is included.
- FastConnect port charges are monthly; model utilization before committing to a dedicated port speed.

## IaC hints

- Terraform: `oci_core_vcn`, `oci_core_subnet`, `oci_core_internet_gateway`, `oci_core_nat_gateway`, `oci_core_service_gateway`, `oci_core_drg`, `oci_core_route_table`, `oci_core_security_list`, `oci_core_network_security_group`, `oci_load_balancer_load_balancer`.
- Separate route tables for public, private, and database subnets — never share a route table across tiers.
- NSG rules managed as `oci_core_network_security_group_security_rule` resources; one Terraform file per NSG to keep rules navigable.
- DRG route distributions and route tables are resources separate from the DRG itself — plan their lifecycle carefully when adding new attachments.

## Verification checklist

- [ ] VCN CIDR sized with room for growth; subnets sized for the maximum expected VNIC count in that tier.
- [ ] Public subnets host only load balancers and bastion hosts.
- [ ] Database subnets have no Internet Gateway or NAT Gateway route.
- [ ] Service Gateway in the route table for every private and database subnet.
- [ ] NSGs are the primary per-workload control; Security Lists set only baseline defaults.
- [ ] No `0.0.0.0/0` inbound on database or cache NSGs.
- [ ] VCN flow logs enabled and shipping to a log group with bounded retention.
- [ ] WAF policy active on every public Load Balancer; rate limiting rule present.
- [ ] DRG route tables explicitly grant only intended inter-VCN paths.
- [ ] DNS is authoritative via OCI DNS zones, not manual record management.
