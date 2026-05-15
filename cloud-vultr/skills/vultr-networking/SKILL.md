---
name: vultr-networking
description: Design or audit Vultr networking — VPC 2.0 (modern regional software-defined network), Load Balancers (regional), Reserved IPs, Firewall Groups (account-wide policy sets), DDoS Protection (paid add-on per region), DNS, IPv6. Use when designing network topology, exposing a service publicly, hardening edge, or auditing connectivity between instances.
---

# Vultr Networking

## When to use

- Designing a VPC 2.0 network for a new workload or environment.
- Exposing an internal service to the internet via a Load Balancer.
- Assigning and managing Reserved IPs for high-availability failover.
- Writing Firewall Group rules to harden a tier of instances.
- Enabling and verifying DDoS Protection on a public-facing service.
- Setting up DNS zones and records for a domain hosted on Vultr.
- Understanding IPv6 assignment and dual-stack configuration.

## VPC 2.0 — the right default

**Always use VPC 2.0, not the legacy VPC.** VPC 2.0 is Vultr's modern, fully software-defined regional network. Legacy VPCs are deprecated. The two are not compatible — do not mix them.

Key VPC 2.0 properties:
- Regional scope — a VPC 2.0 network exists within one region.
- Instances can have both a public IP and a private VPC IP. Remove the public IP from back-of-house instances that do not need public reachability.
- Multiple VPC 2.0 networks per region per account — isolate environments (dev / stage / prod) by network.
- No native peering between VPC 2.0 networks. If two VPCs need to communicate, use a transit instance (routed VPN or WireGuard gateway) or consolidate into one VPC with subnet-level isolation.
- No managed NAT Gateway — instances that need outbound-only internet access require a NAT instance running on a public IP or use their own public IP.

### VPC 2.0 design defaults

- One VPC per environment per region (dev, stage, prod) — or per bounded context if blast radius requires it.
- CIDR: use RFC 1918 space (`10.x.0.0/16`, `172.16.x.0/16`, `192.168.x.0/16`). `/16` or `/24` per VPC. Do not overlap CIDRs between VPCs you intend to bridge.
- Back-of-house instances (application servers, databases, cache): VPC-only IP; disable public IP. They communicate with the internet indirectly through the Load Balancer or NAT instance.
- Edge instances (Load Balancers, NAT gateway instances): public IP + VPC IP.
- VPC IP assignment: static (assign at provision; specify in Terraform) is preferable to DHCP for production instances — avoids IP churn on restart.

## Firewall Groups

Firewall Groups are account-wide, reusable rule sets applied to one or more instances. This is Vultr's primary network access control mechanism.

- **Default posture: deny all inbound, allow all outbound.** Build explicit allow rules for every inbound port your instances must accept.
- A Firewall Group has an ordered list of inbound and outbound rules. Rules are evaluated top-to-bottom; the first match wins.
- One Firewall Group can be attached to many instances, and an instance can be attached to at most one Firewall Group. Design groups by tier: `fg-web`, `fg-app`, `fg-db`.
- **Source IPs:** Restrict inbound rules by source CIDR where possible. For instance-to-instance traffic within VPC 2.0, use the VPC CIDR as the source rather than `0.0.0.0/0`.
- Firewall Groups operate at the edge of the Vultr hypervisor — they are not iptables or OS-level rules. Do not remove OS-level firewall (`ufw`, `iptables`) — layer-in-depth.
- Common tier rules:
  - `fg-web`: inbound 443 from `0.0.0.0/0`, inbound 80 from `0.0.0.0/0` (for HTTPS redirect), inbound 22 from management CIDR only.
  - `fg-app`: inbound 8080 (or app port) from VPC CIDR only, inbound 22 from management CIDR only.
  - `fg-db`: inbound 5432 / 3306 / 6379 from VPC CIDR only, no SSH from public.

## Load Balancers

- Vultr Load Balancers are regional (single-region, single-AZ). They do not provide multi-region failover — design for regional fault tolerance via DNS failover or global load balancing (e.g., Cloudflare) if cross-region HA is required.
- **TLS termination:** Terminate TLS at the Load Balancer. Upload certificates via the Vultr API or Let's Encrypt automation (Certbot or `cert-manager` in VKE). Never expose unencrypted HTTP on the public internet for production services.
- **Health checks:** Configure health checks for every backend. The Load Balancer will remove unhealthy instances from the pool within the health check interval — production instances without a health check path will be incorrectly marked healthy even when the app is down.
- **Sticky sessions:** Off by default. Enable only when your application has server-side session state that cannot be externalized to Redis or a database.
- **Forwarding rules:** Be explicit — forward `80 → 80` and `443 → 443` (or `443 → your app port`). Do not leave default rules that expose unexpected ports.
- **Backend ports:** Backends register on the VPC private IP, not the public IP. Ensure Firewall Group rules permit the Load Balancer's health check source IP (the VPC CIDR) on the backend port.
- **IPv6 on the Load Balancer:** Available in most regions. Enable to support IPv6 clients without changing backend instances.

## Reserved IPs

- A Reserved IP is a static public IP address that can be moved between instances — use for high-availability failover patterns (primary/standby) or when an IP address must not change across instance replacements.
- Reserved IPs are region-specific. An IP in `ewr` cannot be moved to `ord`.
- Assigning a Reserved IP to an instance removes the instance's auto-assigned public IP. The Reserved IP replaces it.
- Failover: reassign the Reserved IP from the failed instance to a standby via `vultr-cli reserved-ip attach --id <ip-id> --instance-id <standby-id>`. This is a control-plane operation; DNS propagation delay is not involved if clients point to the IP directly.
- **Terraform:** Manage Reserved IPs with `vultr_reserved_ip` and `vultr_reserved_ip_assign`. Use a `null_resource` with a lifecycle dependency to control assignment order.

## DDoS Protection

- DDoS Protection is a paid add-on per region. It is available in most major Vultr regions but not all — verify before designing a DDoS-protected architecture for a specific region.
- Enable DDoS Protection on every public-facing production instance or Load Balancer IP. The cost (~$10/mo per IP at time of writing) is negligible relative to the cost of a successful volumetric attack.
- DDoS Protection operates at the network edge before traffic reaches your instance. It does not protect against application-layer (L7) attacks. For L7 protection, use a WAF upstream (Cloudflare WAF, or deploy ModSecurity on the instance).
- Enable via `vultr-cli instance update --ddos-protection=true --id <id>` or Terraform `ddos_protection_enabled = true` on `vultr_instance`.
- DDoS Protection cannot be enabled on instances that do not have a public IP — it is a public-facing service only.

## DNS

- Vultr DNS hosting is free for domains whose nameservers point to Vultr. Supports A, AAAA, CNAME, MX, TXT, SRV, CAA records.
- For production workloads, prefer DNS hosting at Cloudflare or Route 53 unless you have a strong reason to consolidate under Vultr. Vultr DNS has no health-check-based failover (no equivalent to Route 53 Health Checks or Cloudflare Load Balancing).
- TTL: set low (60–300 s) for records you may need to update during incidents; set high (3600 s+) for stable records (MX, SPF, DKIM) to reduce lookup volume.
- SPF, DKIM, DMARC: always configure for any domain used to send email, even transactional email. Vultr DNS supports the TXT records required.

## IPv6

- IPv6 addresses are free on Vultr Cloud Compute instances in supported regions. Enable dual-stack by default.
- IPv6 addresses are assigned from a `/64` prefix per instance — more than enough for a single host.
- Firewall Groups apply to both IPv4 and IPv6 traffic. Verify that your inbound rules cover both address families if you accept IPv6 connections (e.g., add an inbound rule with source `::0/0` as well as `0.0.0.0/0` for public-facing ports).
- If you operate a dual-stack Load Balancer or public instance, test reachability from an IPv6-only client before launch.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Using legacy VPC instead of VPC 2.0 | Legacy VPC is deprecated; limited functionality and no long-term support path. |
| No Firewall Group on a new instance | Default posture is open to the internet. Attach a group at provision time. |
| SSH open to `0.0.0.0/0` in Firewall Group | Mass-scanned within minutes. Restrict to management CIDR or a jump host VPC IP. |
| Public IP on a database or cache instance | Direct reachability from the internet for a service that should never be public. Remove the public IP; use VPC private IP. |
| Load Balancer without health checks | Down instances remain in the pool. Users see errors rather than the LB routing around the failure. |
| DDoS Protection disabled on a public service | Exposed to volumetric attacks that saturate the link before your application can respond. |
| DNS failover via manual IP swap | Under pressure, manual DNS changes take minutes and then propagate for TTL duration. Use Reserved IPs for programmatic failover. |
| VPC CIDRs that overlap between environments you intend to bridge | If you ever add a transit instance between environments, overlapping CIDRs cause routing failures. Plan non-overlapping CIDRs from day one. |

## Security defaults

- Every instance: Firewall Group attached at provision time, not after.
- Public IP removed from any instance that does not need to accept public connections.
- SSH inbound restricted to a named management CIDR or VPC CIDR (not `0.0.0.0/0`).
- DDoS Protection enabled on all public-facing instances and Load Balancer IPs.
- TLS termination at the Load Balancer with a valid certificate; HTTP redirected to HTTPS.
- No plaintext protocols (HTTP, MySQL on 3306 to public internet) on public IPs.

## Observability defaults

- Load Balancer metrics (requests/sec, backend health, 4xx/5xx rates) available in the Vultr control panel; export via Vultr API for external aggregation.
- Instance network bandwidth visible via Vultr Metrics (bytes in/out per interface). Alert on sustained near-100% of the plan's bandwidth allocation.
- Firewall Group block events: Vultr does not provide per-rule hit counters as of 2026-05 — consider OS-level logging (`ufw logging on`) as a complement.
- DNS: Vultr DNS does not provide query logging. If query-level observability is required, use an external DNS provider with logging capabilities.

## Cost considerations

- **VPC 2.0:** Free. No charge for VPC creation or private IP traffic between instances in the same VPC.
- **Load Balancers:** Billed per hour with a monthly cap (starting around $10/mo for the smallest LB). Each LB is a separate charge.
- **Reserved IPs:** Small monthly charge per IP (~$3/mo) while reserved and not attached; free when attached to a running instance.
- **DDoS Protection:** Per IP, per region, per month. Verify current pricing on the Vultr billing page.
- **DNS:** Free for all zones and records under Vultr's nameservers.
- **Bandwidth:** VPC-internal (private IP to private IP within the same VPC) traffic is free. Public-IP traffic counts against the account bandwidth pool. Design intra-tier communication over private VPC IPs to preserve bandwidth pool for external traffic.

## IaC hints

- Terraform resources: `vultr_vpc2` (VPC 2.0), `vultr_load_balancer`, `vultr_reserved_ip`, `vultr_reserved_ip_assign`, `vultr_firewall_group`, `vultr_firewall_rule`, `vultr_dns_domain`, `vultr_dns_record`.
- Attach a Firewall Group to an instance via `firewall_group_id` on `vultr_instance` — provision together to avoid a window of exposure.
- Enable DDoS Protection on an instance via `ddos_protection = true` on `vultr_instance`.
- For Load Balancer SSL, use `vultr_ssl` resource to upload the certificate, then reference by ID in the LB `ssl` block.
- VPC 2.0 network attachment on an instance: `vpc2_ids = [vultr_vpc2.main.id]` on `vultr_instance`. Multiple VPCs can be attached to one instance if needed.

## Verification checklist

- [ ] All instances on VPC 2.0 (no legacy VPC).
- [ ] Public IP present only on instances that accept public traffic; back-of-house instances have VPC-only IP.
- [ ] Firewall Group with default-deny inbound attached on every instance at provision time.
- [ ] SSH inbound restricted to a management CIDR (not `0.0.0.0/0`).
- [ ] Load Balancer health checks configured; backend pool tested by stopping one instance.
- [ ] TLS certificate on Load Balancer; HTTP redirected to HTTPS.
- [ ] DDoS Protection enabled on all public-facing IPs.
- [ ] IPv6 enabled; Firewall Group rules cover both `0.0.0.0/0` and `::0/0` for public ports.
- [ ] VPC CIDRs non-overlapping across environments.
- [ ] DNS records have appropriate TTLs; SPF/DKIM/DMARC configured if sending email.
