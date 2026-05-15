---
name: linode-networking
description: Design or audit Linode networking — VLAN (private L2), VPC (VPC + Subnets), NodeBalancer (L4/L7 load balancing), Cloud Firewall (stateful), Reserved IPs, IPv6. Use when standing up private networking, exposing a service, hardening edge, or auditing east-west connectivity.
---

# Linode Networking

## When to use

- Designing private connectivity between Linode instances in the same region.
- Exposing an internal service to the internet via NodeBalancer.
- Designing Cloud Firewall rules for an instance, NodeBalancer, or VPC.
- Evaluating VLAN vs VPC for an isolation requirement.
- Auditing public IP exposure and firewall posture.
- Understanding Linode's transfer pool model and egress costs.
- Planning IPv6 addressing or Reserved IP use.

## Networking primitives — what exists

Linode's networking surface is more constrained than AWS. Be explicit with users about what does and does not exist:

| Capability | Linode equivalent | Notes |
| --- | --- | --- |
| Private L2 segment | VLAN | Per-region; free; limited to 10 VLANs per region per account. |
| L3 private network with subnets and routing | VPC + Subnets | Newer feature; preferred over VLAN for new deployments. |
| Layer 4 TCP/UDP load balancer | NodeBalancer | Regional; no anycast / global load balancing. |
| Layer 7 HTTP(S) routing | NodeBalancer (HTTP mode) | Limited; not a full application delivery controller. |
| Stateful firewall | Cloud Firewall | Applied per-instance, per-NodeBalancer, or to a VPC. |
| DDoS protection | Akamai Shield (DDoS) | Included at network level; limited application-layer protection. |
| Static public IP | Reserved IP | Reserve an IP in a region; re-assign to instances. |
| BGP / direct network | Akamai Direct Connect | Enterprise add-on; not available via standard Cloud Manager. |
| Global CDN / anycast LB | Akamai CDN (separate product) | Not part of Linode Compute pricing; separate license. |
| DNS | Linode DNS Manager | Authoritative DNS; no health-check-based routing (no Route 53 equivalent). |

## VPC (preferred for new deployments)

- **Scope:** per-region. A VPC contains Subnets. Instances in a VPC can have an interface on the VPC subnet alongside their public interface.
- **Subnets:** define CIDR blocks within the VPC. Choose non-overlapping private address space (RFC 1918). Plan subnets by tier (application, database, management) from the start — subnet CIDRs cannot be changed after creation.
- **Routing:** VPC provides L3 routing between subnets within the same VPC. There is no transitive routing between VPCs or regions.
- **Internet egress:** VPC instances can have a public IP for egress. For instances that should be fully private, do not assign a public IP — egress through a NAT instance is manual (Linode has no managed NAT gateway equivalent). Use a Compute Instance as a NAT gateway if needed, or accept that private-only instances cannot reach the internet.
- **NodeBalancer in VPC:** NodeBalancers can be configured as the public entry point with backend nodes connected via the VPC.
- **Security:** VPC isolation prevents direct public routing to private subnets. Still attach a Cloud Firewall — VPC does not replace firewall rules.

## VLAN (legacy; prefer VPC for new work)

- **Scope:** per-region. A VLAN provides a private L2 broadcast domain. Instances on the same VLAN can communicate at L2 without any public routing.
- **Configuration:** each instance can have one VLAN interface (`eth1` or as configured). Assign a private IP address in the VLAN's address space manually or via cloud-init.
- **No routing between VLANs.** VLAN connectivity is limited to instances in the same VLAN within the same region.
- **When to still use VLAN:** existing deployments using VLAN; workloads that genuinely need L2 adjacency (some clustering software). Otherwise, use VPC.

## NodeBalancer

- **Scope:** per-region. A NodeBalancer load balances traffic to backend instances in the same region.
- **Protocols:** TCP (L4 passthrough), HTTP (L7 with health checks), and HTTPS (L7 with TLS termination at the NodeBalancer).
- **TLS termination:** upload your certificate to the NodeBalancer or reference a Linode-managed certificate. Terminate TLS at the NodeBalancer for HTTPS; backends can use plain HTTP or HTTPS on the private network.
- **Health checks:** configure per-port. For HTTP mode, set a health check path (`/healthz` or equivalent); do not leave health checks disabled in production.
- **Session affinity:** NodeBalancer supports sticky sessions (cookie-based or source IP). Use only when your application genuinely requires session state on a specific backend — prefer stateless application design.
- **Backend nodes:** add nodes by instance private IP. NodeBalancer communicates with backends over the private network; backends should not need a public IP if they are behind a NodeBalancer.
- **No global load balancing.** NodeBalancers are regional. There is no Linode equivalent of AWS Global Accelerator or Route 53 latency-based routing. Multi-region failover requires DNS-level switching (e.g., monitoring + DNS update).
- **Firewall:** attach a Cloud Firewall to the NodeBalancer. Allow inbound from the internet on the service port (80/443); restrict other ports.

## Cloud Firewall

- **Stateful:** tracks connection state. Inbound rules for new connections are sufficient; return traffic is automatically allowed.
- **Attachment:** applied to a Compute Instance, a NodeBalancer, or a VPC. A single firewall can be applied to multiple devices.
- **Default policy:** set inbound default policy to `DROP`. This means unmatched inbound traffic is silently discarded. Set outbound default to `ACCEPT` unless your policy requires egress restriction.
- **Rule ordering:** rules evaluate in order; first match wins. Place more-specific rules before broader rules.
- **Essential inbound rules for most instances:**
  - Allow TCP port 22 (SSH) from a restricted CIDR or known management IP range — not `0.0.0.0/0`.
  - Allow the application service port (e.g., 443) from `0.0.0.0/0` if it is a public-facing service.
  - Allow ICMP (type 8) from known monitoring sources.
- **NodeBalancer rules:** allow inbound 80/443 from `0.0.0.0/0`; restrict everything else.
- **VPC firewall:** controls traffic entering and leaving the VPC subnet. Instance-level firewalls still apply.
- **Limitation:** Cloud Firewall operates at the network edge (Linode's hypervisor layer). It is not a replacement for host-level iptables / nftables for defense-in-depth.

## IPv6

- Every Linode Compute Instance is allocated an IPv6 address from a `/64` prefix automatically. No configuration required.
- IPv6 traffic is subject to the same Cloud Firewall rules.
- Linode supports DHCPv6 and SLAAC. For static IPv6, use the assigned address.
- IPv6 does not count against the outbound transfer pool (as of current pricing — verify at deployment time, as billing rules can change).
- Not all regions support the same IPv6 feature set — verify regional capabilities.

## Reserved IPs

- Reserve a public IPv4 address in a region. The IP persists across instance deletions and can be re-assigned to a new instance.
- Use case: failover scenarios where DNS TTLs are too high to fail over quickly; canary / blue-green deploys that require the same IP.
- Cost: Reserved IPs have a small monthly charge when not attached to a running instance (check current pricing).

## BGP / Direct Connect

- Akamai Direct Connect (formerly Linode Interconnect) is an enterprise add-on for dedicated physical connections to Linode's network. Not available via standard Cloud Manager or self-service API. Contact Akamai sales.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| No Cloud Firewall on any instance | All ports on the public IP are accessible. Mandatory for every instance. |
| Cloud Firewall with `ACCEPT` as default inbound policy | Fails open on unmatched traffic. Default inbound should be `DROP`. |
| SSH open to `0.0.0.0/0` | Constant brute-force attempts. Restrict SSH to a known management CIDR. |
| NodeBalancer without health checks | Dead backends receive traffic. Enable health checks on every config. |
| Assuming VLAN replaces a firewall | VLAN provides L2 isolation only within the VLAN. Cloud Firewall is still required. |
| Expecting global anycast load balancing | Linode has no native anycast. Multi-region requires DNS failover or a separate CDN/proxy layer. |
| Using a public IP on database instances | Database instances should communicate via VPC or VLAN private IPs only. Never public. |
| One NodeBalancer per application service | Each `type: LoadBalancer` LKE service provisions a NodeBalancer. Use an ingress controller. |

## Security defaults

- All new instances: attach Cloud Firewall with default-deny inbound before the instance goes live.
- SSH: restrict to a specific management CIDR; do not allow `0.0.0.0/0`.
- Database and cache ports (5432, 3306, 6379, 27017, etc.): never in the Cloud Firewall allow list for inbound from the internet.
- NodeBalancer: HTTPS-only for external services; HTTP→HTTPS redirect at the NodeBalancer level.
- VPC: put application instances in VPC subnets; do not assign public IPs to backend instances behind a NodeBalancer.
- Akamai Shield provides volumetric DDoS scrubbing at the network layer. For application-layer protection, an additional WAF (Cloudflare, Fastly, or Akamai App & API Protector — separate license) is required.

## Observability defaults

- Cloud Manager: displays inbound/outbound network traffic per instance (last 24 h / 30 d). Not suitable for alerting.
- NodeBalancer: connection and traffic stats in Cloud Manager. Export to external monitoring for alerting on connection rate, error rate.
- VPC Flow Logs: Linode does not currently offer VPC Flow Logs. Implement packet capture (`tcpdump`) or application-level access logs as the forensics substitute.
- External monitoring: wire public endpoints to an uptime checker (Better Stack, UptimeRobot) for availability alerts.

## Cost considerations

- NodeBalancer: flat monthly fee per NodeBalancer plus a transfer component. Check current pricing. LKE `type: LoadBalancer` services each create one NodeBalancer.
- VPC: no additional cost. VPC is included in the platform pricing.
- VLAN: no additional cost.
- IPv6 egress: currently free (does not count against transfer pool). Verify at deployment time.
- Reserved IPs: small monthly fee when unattached.
- Egress to the internet and between regions counts against the regional transfer pool. Internal traffic within a VPC is free.

## IaC hints

- Terraform: `linode_vpc`, `linode_vpc_subnet`, `linode_nodebalancer`, `linode_nodebalancer_config`, `linode_nodebalancer_node`, `linode_firewall`, `linode_firewall_device`.
- For Cloud Firewall rules in Terraform: define `inbound` and `outbound` rule blocks; set `inbound_policy = "DROP"` and `outbound_policy = "ACCEPT"` as defaults.
- Reserve an IP with `linode_reserved_ip_address` (check provider version support).
- LKE ingress: deploy the nginx ingress controller via Helm; it creates one `type: LoadBalancer` service = one NodeBalancer.

## Verification checklist

- [ ] Every Compute Instance has a Cloud Firewall with default-deny inbound attached.
- [ ] SSH access restricted to a known management CIDR, not `0.0.0.0/0`.
- [ ] No database or cache ports exposed inbound to the internet.
- [ ] NodeBalancer health checks configured on all backends; HTTPS termination for public services.
- [ ] VPC subnets planned with room to grow; CIDR documented in IaC.
- [ ] Backend instances use private IP (VPC or VLAN) to communicate; public IPs disabled where not required.
- [ ] Transfer pool budget reviewed for expected egress volume.
- [ ] Multi-region failover strategy documented if high availability across regions is required.
