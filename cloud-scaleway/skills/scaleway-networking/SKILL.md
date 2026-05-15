---
name: scaleway-networking
description: Design or audit Scaleway networking — VPC (with Private Networks per region), Public Gateways (egress + NAT), Load Balancers, Edge Services (CDN), Domains / DNS, IPv4 / IPv6 pools, Reserved IPs. Use when standing up a new VPC, exposing a service, hardening edge, or tracking down NAT / egress data costs.
---

# Scaleway Networking

## When to use

- Designing a VPC and Private Networks for an account or workload.
- Exposing an internal service to the internet via a Load Balancer or Edge Services.
- Configuring a Public Gateway for controlled egress and NAT.
- Managing DNS zones or Reserved IPs for stable endpoints.
- Auditing network exposure, IP allocation, and egress cost.
- Connecting Kapsule nodes or Managed Databases to application instances via Private Networks.

## VPC and Private Networks — the baseline

Scaleway VPCs group Private Networks under a single routing domain. Each Private Network is a Layer 2 broadcast domain within a region.

- One VPC per major environment (dev / stage / prod) or per team if you want strong blast-radius separation.
- Private Networks: create one per workload tier — e.g., `app-net`, `db-net`. Resources in the same Private Network can reach each other by private IP without Public Gateway overhead.
- CIDR planning: choose non-overlapping RFC 1918 CIDRs per Private Network. `/22` is a reasonable default (1022 usable hosts). Reserve room to grow.
- VPC routing: Scaleway VPC supports inter-Private-Network routing within the same VPC — resources on different Private Networks in the same VPC can communicate if routes are configured.
- IPv4 + IPv6: assign IPv6 prefixes to Private Networks when possible. Scaleway charges for public IPv4 — reducing reliance on public IPv4 reduces cost.
- Managed resources (Managed Database, Redis Cluster, Kapsule nodes) attach to Private Networks directly — prefer this over public IP exposure.

## Public Gateway

A Public Gateway provides NAT and egress for resources in a Private Network that need to reach the internet but should not have a public IP.

- One Public Gateway per environment; attach multiple Private Networks to the same gateway where traffic volumes allow.
- NAT: stateful masquerade NAT (instances share one public IP). Configure per-port DNAT (port forwarding) only for specific inbound services — never expose a full instance to the internet through DNAT.
- SSH bastion: a Public Gateway can forward SSH to private instances via DNAT — combine with IP allowlisting to restrict access to known management ranges.
- Bandwidth: Public Gateway bandwidth is tier-based. Check the tier limit and upgrade before a launch with expected spikes.
- Cost: billed by tier + data processed. Minimize egress through the gateway by routing traffic via Scaleway Private Networks where possible (e.g., Instance → Managed Database over the Private Network, not via the internet).
- Do not attach a Public Gateway to a Private Network that contains internet-facing Load Balancers — use separate Private Networks for inbound vs egress paths.

## Load Balancers

| Use case | Configuration |
| --- | --- |
| HTTPS service, host / path-based routing | Load Balancer with HTTPS frontend, HTTP backend, ACL rules |
| TLS passthrough to backend | TCP frontend with TLS passthrough |
| Internal service-to-service | Load Balancer with a private IP only (no public IP) |
| High-availability Kapsule ingress | Kapsule-managed Load Balancer via `LoadBalancer` Service type |

Defaults:

- HTTPS frontend: HTTP→HTTPS redirect listener, TLS 1.2 minimum, TLS 1.3 preferred.
- Certificate: attach a Let's Encrypt certificate managed by Scaleway, or upload your own via Secret Manager.
- Sticky sessions: off by default; enable only when the application requires session affinity (prefer stateless design instead).
- Health checks: configure TCP or HTTP health checks on every backend server. Unhealthy threshold: 2 consecutive failures. Healthy threshold: 2 successes.
- Deletion protection: enable in IaC for production Load Balancers to prevent accidental teardown.
- Private backend: Load Balancer frontend can be public while backends are Private Network IPs — never expose backends directly.
- Access logs: enable and ship to Object Storage for security review and cost analysis.

## Edge Services (CDN)

Scaleway Edge Services is a CDN layer in front of Object Storage origins (and, for supported configurations, Load Balancer origins).

- Use for: static site hosting, media delivery, large-asset distribution, offloading Object Storage egress costs.
- Cache behavior: set explicit `Cache-Control` headers on origin objects — Edge Services honors them. Default TTL when no header is set can lead to stale content surprises.
- Custom domain: always configure a custom domain + TLS certificate via Edge Services. Do not serve production traffic from the raw `*.s3.fr-par.scw.cloud` endpoint.
- Security headers: inject `Strict-Transport-Security`, `X-Content-Type-Options`, `Referrer-Policy` at the CDN layer so they are present even if the origin omits them.
- Geo-restrictions: available for compliance or licensing needs (regional content blocking).
- Origin shield: not available in all tiers — check current documentation before designing a caching architecture that depends on it.

## Domains and DNS

- Scaleway Domains manages domain registration and DNS hosting on the same console/API as the rest of the Scaleway estate.
- External domains: point NS records to Scaleway nameservers to manage DNS via `scw` CLI or Terraform.
- Record types: A, AAAA, CNAME, MX, TXT, SRV. ALIAS records supported for apex domains pointing to Load Balancers.
- TTL: default is 3600 s; lower to 300 s during a migration, then restore to reduce resolver cache miss overhead.
- DNSSEC: available for Scaleway-registered domains — enable for domains that are high-value targets.
- DNS failover: Scaleway does not provide health-check-based DNS failover natively. For multi-region failover, combine Scaleway DNS with a third-party DNS health-check service, or use a Load Balancer with cross-region backends where supported.

## Reserved IPs and Flexible IPs

- Reserved IPs (flexible IPs): public IPv4 or IPv6 addresses you allocate independently and attach to Instances, Load Balancers, or Public Gateways.
- Use for: endpoints that must remain stable across Instance replacements (blue/green deploy, failover).
- Release unused reserved IPs promptly — Scaleway charges per allocated IP even when unattached.
- IPv6: prefer IPv6 flexible IPs for new services where client IPv6 support is not a blocker. Reduces public IPv4 spend.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Instance with a public IP and no firewall / SG | Every port is internet-accessible. Use Private Networks + Public Gateway or Load Balancer. |
| Managed Database accessible on a public IP | One credential leak = direct internet access to production data. Private Network only. |
| All resources in a single Private Network flat topology | East-west movement is unconstrained. Segment into app / db / mgmt networks. |
| Single Public Gateway for dev and prod traffic | Dev misconfiguration can affect prod egress path. Separate per environment. |
| Large private CIDR overlapping future VPC peering | Impossible to route. Plan CIDRs before provisioning. |
| Kapsule LoadBalancer Service without annotation | No control over public vs private IP, TLS, or annotation-based features. |
| Serving production traffic from a raw S3 endpoint | No TLS certificate control, no CDN, potential egress cost surprise. Use Edge Services. |
| Reserved IPs left unattached | Billed even when idle. Audit and release unused IPs monthly. |

## Security defaults

- Private Networks for all backend-to-backend traffic — no cleartext communication over public IPs between application tiers.
- Public Gateway with IP allowlist for SSH DNAT — restrict management access to known CIDR ranges.
- Load Balancer: HTTPS-only frontends; backend health checks on a dedicated health path, not a path that also serves data.
- Edge Services: TLS on all custom domains; security headers injected at the CDN layer.
- DNS: DNSSEC on for high-value domains; MX + SPF + DMARC records for any domain that sends email.
- IP allocation: minimize public IP surface. Every public IP in use should have a documented justification.
- Audit Trail: network mutations (creating/deleting Load Balancers, modifying Security Groups) are logged in Scaleway Audit Trail — review after any incident.

## Observability defaults

- Load Balancer: access logs to Object Storage; Cockpit metrics for request rate, latency, error rate, healthy backend count.
- Public Gateway: bandwidth metrics via Cockpit; alert on egress approaching tier limit.
- Edge Services: cache hit rate, origin request rate, error rate via Cockpit.
- DNS: monitor record change events via Audit Trail.
- Wire Cockpit alerts on: Load Balancer backend health check failure, Public Gateway bandwidth spike, Edge Services origin error spike.

## Cost considerations

- Public IPv4 addresses are billed per hour — consolidate behind Load Balancers rather than per-instance flexible IPs.
- Public Gateway data processing billed per GB. Route traffic via Private Networks to avoid unnecessary gateway egress.
- Edge Services CDN reduces egress from Object Storage — for large-asset workloads, CDN costs less than direct S3 egress.
- Load Balancer billed per hour by size + bandwidth. Right-size; downgrade tiers for non-prod.
- DNS: Scaleway-hosted zones billed per zone + per query volume — cheap but not zero.

## IaC hints

- Terraform `scaleway/scaleway` ≥ 2.45: `scaleway_vpc`, `scaleway_vpc_private_network`, `scaleway_vpc_public_gateway`, `scaleway_vpc_gateway_network`, `scaleway_lb`, `scaleway_lb_frontend`, `scaleway_lb_backend`, `scaleway_domain_zone`, `scaleway_domain_record`, `scaleway_flexible_ip`.
- Private Network attachment to Instance: `scaleway_instance_private_nic` resource; to Kapsule: set `private_network_id` in `scaleway_k8s_cluster`.
- For Kapsule, the Load Balancer provisioned by a Kubernetes `LoadBalancer` Service is managed by the cloud-controller-manager — do not manage it via Terraform in the same plan.
- Public Gateway DHCP: configure `scaleway_vpc_gateway_network` with `dhcp` for automatic IP assignment to Private Network members — avoids manual static IP management.

## Verification checklist

- [ ] Private Networks created and attached to all backend resources (databases, caches, app nodes).
- [ ] No Managed Database or cache instance accessible via public IP.
- [ ] Load Balancer frontends are HTTPS-only; HTTP→HTTPS redirect configured.
- [ ] Public Gateway (if used) has IP allowlist on DNAT rules.
- [ ] Reserved IPs accounted for; no orphaned unattached IPs.
- [ ] Edge Services CDN in front of any Object Storage origin serving public traffic.
- [ ] DNS DNSSEC enabled for high-value domains.
- [ ] Cockpit alerts on Load Balancer backend health and Public Gateway bandwidth.
- [ ] CIDRs planned across Private Networks with room to grow; no overlapping ranges.
