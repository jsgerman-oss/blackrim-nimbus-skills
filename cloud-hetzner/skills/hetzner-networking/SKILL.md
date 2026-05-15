---
name: hetzner-networking
description: Design or audit Hetzner networking — Private Networks (Cloud), Load Balancers (LB11 / LB21 / LB31), Floating IPs, Cloud Firewalls, vSwitch for Robot dedicated, dual-stack IPv4/IPv6 and the IPv4 cost surcharge, Reverse DNS (PTR), location vs network zone semantics. Use when standing up inter-server networking, exposing a service, or hardening network posture.
---

# Hetzner Networking

## When to use

- Designing a Private Network for inter-server communication on Hetzner Cloud.
- Choosing and configuring a Cloud Load Balancer.
- Evaluating Floating IPs vs load-balanced routing for failover.
- Setting up Cloud Firewalls for inbound traffic control.
- Connecting Robot dedicated servers to Cloud servers via vSwitch.
- Planning dual-stack (IPv4 + IPv6) deployments and managing IPv4 cost.
- Configuring Reverse DNS (PTR) records for mail servers or compliance.
- Understanding location vs network zone boundaries for Private Networks.

## Private Networks

Hetzner Cloud Private Networks provide RFC 1918 Layer 3 networking between servers in the same **network zone** — not just the same location.

Network zones and their locations:

| Zone | Locations |
| --- | --- |
| `eu-central` | `nbg1`, `fsn1`, `hel1` |
| `us-east` | `ash` |
| `us-west` | `hil` |
| `ap-southeast` | `sin` |

Key properties:

- A Private Network belongs to one zone. A server in `nbg1` and a server in `hel1` can share the same Private Network (both in `eu-central`).
- CIDR: user-defined RFC 1918 range (e.g., `10.0.0.0/8`, `172.16.0.0/12`). Plan subnets per location within the zone.
- Each server can attach to multiple Private Networks. Limit: 5 networks per server (as of 2026-05).
- Traffic between servers on the same Private Network is **not billed** — only public egress counts against your traffic allowance.
- No encryption in transit on Private Networks by default. Apply TLS at the application layer for sensitive data flows.

Subnet design example for a multi-location EU zone:

```
10.0.0.0/8       (Private Network CIDR)
  10.0.1.0/24    (nbg1 — web tier)
  10.0.2.0/24    (nbg1 — app tier)
  10.0.3.0/24    (nbg1 — data tier)
  10.1.1.0/24    (hel1 — web tier, replicas)
  10.1.2.0/24    (hel1 — app tier)
```

```hcl
resource "hcloud_network" "main" {
  name     = "main"
  ip_range = "10.0.0.0/8"
}

resource "hcloud_network_subnet" "app_nbg1" {
  network_id   = hcloud_network.main.id
  type         = "cloud"
  network_zone = "eu-central"
  ip_range     = "10.0.2.0/24"
}
```

## Load Balancers

Hetzner Cloud Load Balancers are regional services (location-scoped, not zone-scoped). They support HTTP, HTTPS, and raw TCP protocols.

| Type | Max targets | Max connections | Included traffic |
| --- | --- | --- | --- |
| LB11 | 25 | 10,000 | 5 TB/mo |
| LB21 | 100 | 25,000 | 20 TB/mo |
| LB31 | 500 | 100,000 | 100 TB/mo |

(Prices and specs as of 2026-05; verify at hetzner.com/cloud/load-balancers.)

Key capabilities:

- **HTTP / HTTPS routing**: host- and path-based rules, HTTP→HTTPS redirect, Let's Encrypt certificate issuance (Hetzner manages renewal).
- **Sticky sessions**: cookie-based.
- **Health checks**: HTTP, HTTPS, or TCP; configurable interval and threshold.
- **Private Network attachment**: load balancer reaches targets over Private Network — no public egress between LB and backend.
- **Proxy Protocol**: pass client IP to backends that speak Proxy Protocol.
- **Algorithm**: round-robin or least-connections.

Important limitations Hetzner LBs do not offer:

- No anycast / global load balancing. The LB is in one location; global distribution requires Cloudflare or an equivalent.
- No WAF functionality. Put Cloudflare or Hetzner's own Firewall-for-Webspaces (if you use Webspaces) in front for application-layer filtering.
- No layer-7 traffic weighting for blue/green canary at the LB level — implement at the application (feature flags, Nginx upstream weights).

```hcl
resource "hcloud_load_balancer" "web" {
  name               = "web-lb"
  load_balancer_type = "lb11"
  location           = "nbg1"
}

resource "hcloud_load_balancer_network" "web" {
  load_balancer_id = hcloud_load_balancer.web.id
  network_id       = hcloud_network.main.id
  ip               = "10.0.1.2"
}

resource "hcloud_load_balancer_service" "https" {
  load_balancer_id = hcloud_load_balancer.web.id
  protocol         = "https"
  listen_port      = 443
  destination_port = 8080

  http {
    redirect_http = true
    certificates  = [hcloud_managed_certificate.main.id]
  }

  health_check {
    protocol = "http"
    port     = 8080
    interval = 10
    timeout  = 5
    retries  = 3
    http {
      path         = "/health"
      status_codes = ["200"]
    }
  }
}
```

## Floating IPs

A Floating IP is a static public IP address that can be remapped between servers in the same location within seconds via the API.

Use cases:

- Failover without DNS TTL propagation delay — switch the Floating IP to the standby server after a primary failure.
- Shared inbound IP for a pool of servers running a custom routing layer (Keepalived, Corosync).

Limitations:

- Location-scoped — a Floating IP in `nbg1` cannot be assigned to a server in `hel1`.
- IPv4 Floating IPs are billed at €1.19/mo when unassigned; €0.00 extra when assigned (the server's base IPv4 cost applies).
- IPv6 Floating IPs are available and cheaper.
- For most public-facing services, a Load Balancer is a better choice than a Floating IP — LBs provide health checks, connection distribution, and Let's Encrypt integration.

## Cloud Firewalls

Hetzner Cloud Firewalls are stateful packet filters applied at the hypervisor level — before traffic reaches the server's NIC. They are separate from the OS firewall (iptables / nftables) and are managed via the hcloud API.

Firewall rules are **allowlist-only**. There is no explicit deny rule — all traffic not matched by an allow rule is dropped.

Default posture: a new server with no Cloud Firewall applied has **all ports open** from the public internet. Apply a Cloud Firewall at server creation, not after.

Supported protocols: TCP, UDP, ICMP, GRE, ESP.

Directions: `in` (inbound to server) and `out` (outbound from server). Both must be configured; omitting outbound rules blocks all egress.

Typical baseline:

```hcl
resource "hcloud_firewall" "web" {
  name = "web"

  rule {
    direction = "in"
    protocol  = "tcp"
    port      = "80"
    source_ips = ["0.0.0.0/0", "::/0"]
  }

  rule {
    direction = "in"
    protocol  = "tcp"
    port      = "443"
    source_ips = ["0.0.0.0/0", "::/0"]
  }

  rule {
    direction = "in"
    protocol  = "tcp"
    port      = "22"
    source_ips = ["<your-cidr>/32"]  # management IP only
  }

  rule {
    direction  = "out"
    protocol   = "tcp"
    port       = "any"
    destination_ips = ["0.0.0.0/0", "::/0"]
  }

  rule {
    direction  = "out"
    protocol   = "udp"
    port       = "53"
    destination_ips = ["0.0.0.0/0", "::/0"]
  }

  rule {
    direction  = "out"
    protocol   = "icmp"
    destination_ips = ["0.0.0.0/0", "::/0"]
  }
}

resource "hcloud_firewall_attachment" "web" {
  firewall_id = hcloud_firewall.web.id
  server_ids  = [hcloud_server.web.id]
}
```

## vSwitch (Robot dedicated servers)

vSwitch connects Robot dedicated servers via a VLAN in Hetzner's private backbone — analogous to a Cloud Private Network but for dedicated hardware.

- Free; no traffic charges within the vSwitch.
- Operates as a VLAN-tagged Ethernet segment; you configure the VLAN ID on each server's NIC.
- A vSwitch can bridge to a Hetzner Cloud Private Network, enabling Cloud servers and Robot servers to communicate on the same Layer 3 segment.

Bridging vSwitch and Cloud Private Network:

1. Create a vSwitch in the Robot panel.
2. Assign Robot servers to the vSwitch with their chosen VLAN.
3. In Hetzner Cloud, create a Private Network subnet of type `vswitch` with the vSwitch ID — this attaches the Cloud network to the vSwitch VLAN.
4. Assign Cloud servers and Robot servers the same RFC 1918 subnet range; configure static IPs or use your own DHCP.

## IPv4 / IPv6 and cost discipline

Hetzner charges **€0.001/hr (~€0.72/mo) per public IPv4 address** assigned to a Cloud server. This includes the primary IPv4 assigned at server creation.

Strategies to reduce IPv4 spend:

- Create servers with `public_net { ipv4_enabled = false }` in Terraform if they only need Private Network access and you have NAT or a gateway.
- Use a single Load Balancer's IPv4 (included in LB pricing) instead of per-server public IPs for a fleet of backend servers.
- Use IPv6 for public-facing services where client support allows. Hetzner assigns a `/64` IPv6 prefix per server; no surcharge.
- Floating IPs are charged only when unassigned — assign them to a server immediately after creation.

Dual-stack configuration via cloud-init:

```yaml
#cloud-config
network:
  version: 2
  ethernets:
    eth0:
      dhcp4: true
      dhcp6: true
```

## Reverse DNS (PTR)

Hetzner supports PTR records for both Cloud server public IPs and Robot dedicated server IPs, configured via the respective API.

Cloud:

```bash
hcloud server set-rdns --hostname mail.example.com <server-id>
```

Robot: PTR records are managed in the Robot panel under "IPs" or via the Robot API (`POST /rdns/<ip>`).

Requirements for mail servers: FCrDNS (forward-confirmed reverse DNS) is mandatory for SMTP deliverability. The PTR record must match the hostname the mail server presents in EHLO, and that hostname must resolve back to the IP.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| No Cloud Firewall on a new server | Default open-all means your server is immediately scanning fodder. Apply at creation, not after provisioning. |
| Public IP on every backend server | €0.72/mo × 50 servers = €36/mo extra, plus unnecessary attack surface. Route backend traffic through Private Network. |
| Floating IP as the primary HA mechanism without a health check | No health check means failed servers keep the IP until you manually failover. Use a Load Balancer with health checks instead. |
| vSwitch VLAN ID collision with Hetzner's own tags | Hetzner reserves certain VLAN IDs. Use IDs in the 4000–4050 range unless documentation confirms otherwise. |
| No outbound Cloud Firewall rules | Silently blocks all egress, including DNS and package updates. Always define outbound rules explicitly. |
| Large CIDR on Private Network with no subnet planning | Running out of IP space mid-growth is painful; plan subnets per location and service tier from day one. |
| IPv6-only without client compatibility check | Some corporate networks and legacy clients still lack IPv6 routes. Validate before removing IPv4. |

## Security defaults

- Apply a Cloud Firewall to every server at creation time with deny-by-default inbound posture.
- SSH access: restrict inbound port 22 to a known management CIDR or a bastion server's Private Network IP; never `0.0.0.0/0`.
- Inter-server traffic on Private Network: use application-layer TLS; do not assume Private Network equals trusted network.
- vSwitch: treat the vSwitch segment as a Layer 2 trust boundary; authenticate application connections rather than relying on VLAN isolation alone.
- Load Balancer: enable HTTPS-only; reject HTTP on port 80 or redirect to HTTPS; use Let's Encrypt certificates managed by Hetzner.

## Observability defaults

- Hetzner Cloud does not provide flow-log-style network monitoring. Monitor inbound connection rates and bandwidth via your external observability stack.
- Load Balancer metrics (requests/s, active connections, response codes) are available via the hcloud API Metrics endpoint and via the Hetzner Cloud panel.
- Alert on Load Balancer health check failures — a target marked unhealthy should page the on-call.
- For public servers, deploy Fail2Ban or CrowdSec as a rate-limiting complement to the Cloud Firewall.

## Cost considerations

- Private Network traffic between Hetzner Cloud servers is free — route all inter-service traffic through the Private Network.
- Load Balancer included traffic is generous (5 TB for LB11); overages charged at standard egress rates. Monitor with your observability stack.
- Floating IPs: €1.19/mo when unassigned; assign immediately after provisioning and release promptly when no longer needed.
- IPv4 surcharge is real at scale. Design for minimal public IPv4 from the start; retrofitting is harder.
- Traffic between Hetzner network zones (e.g., `eu-central` to `us-east`) goes over the public internet unless you have a dedicated cross-zone interconnect — it counts against traffic allowances.

## IaC hints

- Terraform: `hcloud_network`, `hcloud_network_subnet`, `hcloud_server_network`, `hcloud_load_balancer`, `hcloud_load_balancer_network`, `hcloud_load_balancer_service`, `hcloud_load_balancer_target`, `hcloud_firewall`, `hcloud_firewall_attachment`, `hcloud_floating_ip`, `hcloud_floating_ip_assignment`, `hcloud_rdns`.
- Provider version: `hetznercloud/hcloud` ≥ 1.48 for full Load Balancer and Firewall features.
- Ansible: `hetzner.hcloud.hcloud_network`, `hetzner.hcloud.hcloud_load_balancer`, `hetzner.hcloud.hcloud_firewall`.

## Verification checklist

- [ ] Cloud Firewall applied to every server at provisioning time; default-deny inbound; explicit outbound rules.
- [ ] SSH restricted to management CIDR or bastion; no `0.0.0.0/0` on port 22.
- [ ] Backend servers use Private Network for inter-service traffic; public IPs suppressed where not needed.
- [ ] Load Balancer configured with health checks; HTTPS redirect on port 80; managed certificate.
- [ ] Private Network CIDR planned with subnet-per-tier and per-location structure.
- [ ] IPv4 count minimized; IPv6 dual-stack enabled where possible.
- [ ] PTR records set for any server running a mail transfer agent.
- [ ] vSwitch VLAN isolation verified if Robot servers are in scope.
- [ ] No inbound port open without a documented justification.
