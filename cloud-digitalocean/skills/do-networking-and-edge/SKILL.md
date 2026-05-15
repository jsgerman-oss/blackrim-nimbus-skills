---
name: do-networking-and-edge
description: Design or audit DigitalOcean networking — VPC (per-region, multi-VPC patterns), Load Balancer (regional, global), Floating / Reserved IPs, DNS (PowerDNS-based), Cloud Firewall, Spaces CDN, and PTR records. Use when standing up a new VPC, exposing a service, hardening edge, or auditing east-west connectivity.
---

# DigitalOcean Networking and Edge

## When to use

- Designing a VPC for a new environment or migrating resources into private networking.
- Exposing a service to the internet via a Load Balancer.
- Setting up Floating IPs or Reserved IPs for failover or static entry points.
- Managing DNS zones and records for a domain.
- Writing or auditing Cloud Firewall rules.
- Routing traffic through Spaces CDN for static assets.
- Configuring PTR (reverse DNS) records for mail servers or compliance requirements.

## VPC layout — the default

DigitalOcean VPCs are per-region, not global. Every datacenter region has its own VPC namespace.

- **One VPC per environment per region.** Dev, stage, and prod each get their own VPC. Resources in the same VPC share a private RFC-1918 network; traffic between VPCs or regions is over the public internet unless you use a private tunnel (WireGuard, Tailscale, or a Droplet-based VPN).
- **Default VPC:** every new DigitalOcean account and project has a default VPC per region. Do not use the default VPC for production — you have no control over its CIDR and cannot rename or segment it meaningfully.
- **CIDR planning:** choose a `/20` or `/16` range that does not overlap with other VPCs you will ever need to peer or tunnel. Common picks: `10.10.0.0/16` (prod), `10.20.0.0/16` (stage), `10.30.0.0/16` (dev) — adjust to your broader network plan.
- **Multi-VPC:** DigitalOcean does not offer VPC peering as a first-party feature (as of 2026). Cross-VPC connectivity requires a Droplet-based VPN or overlay network (WireGuard, Tailscale). Account for this latency and operational overhead before designing a multi-VPC topology.
- **Resource placement:** always specify the VPC UUID when creating Droplets, Managed Databases, and DOKS clusters. Resources without an explicit VPC land in the default VPC.

## Cloud Firewall

DigitalOcean Cloud Firewall is stateful and applied at the hypervisor layer — it sits between the internet and the Droplet, before any in-guest firewall.

- **Default deny inbound.** Your Cloud Firewall rules should enumerate only what is explicitly allowed.
- **Tag-based rules:** apply firewalls to Droplet tags rather than individual Droplet UUIDs. When you scale horizontally, new Droplets inherit the firewall automatically if tagged correctly.
- **Source restrictions:** on the database tier, allow inbound from the application tier's tag only — never from `0.0.0.0/0` or `::/0`.
- **Allow-list your NAT / egress IPs:** if your application calls external APIs that allow-list by IP, use a Floating IP on a NAT Droplet and restrict outbound egress to a single egress point.
- **Avoid SSH from `0.0.0.0/0`:** restrict port 22 to your office CIDR, a bastion Droplet tag, or disable SSH entirely in favor of the DigitalOcean Droplet Console (in-browser terminal, no SSH port required).
- **ICMP:** allow ICMP from trusted sources for network debugging. Blocking all ICMP silently breaks path MTU discovery.
- **Outbound rules:** by default, all outbound traffic is allowed. Restrict outbound to specific destinations if your compliance posture requires egress control.

## Load Balancer

| Use case | Configuration |
| --- | --- |
| HTTPS service behind custom domain | HTTP → HTTPS redirect on port 80; TLS termination on port 443 with a Let's Encrypt or custom cert |
| TLS passthrough (custom TLS to Droplets) | TCP mode on port 443; health check on TCP |
| Internal service between Droplets | VPC-only Load Balancer (no public IP) |
| DOKS ingress entry point | One Load Balancer provisioned by a `Service` of type `LoadBalancer` |

- **HTTPS redirect:** always redirect HTTP → HTTPS at the Load Balancer. Do not let unencrypted traffic reach application Droplets.
- **Health checks:** set the health check path to a shallow endpoint that returns `200 OK` only when the application is genuinely ready (not just the process running). Set `check_interval_seconds` to 10 and `unhealthy_threshold` to 3 — the defaults are too slow to remove a bad backend quickly.
- **Sticky sessions:** off by default, and should stay off for stateless services. Enable only when session state is genuinely server-local and cannot be externalized.
- **Proxy protocol:** enable if your application needs to see the real client IP; requires application-side Proxy Protocol parsing.
- **Global Load Balancer:** DigitalOcean's Global Load Balancer routes across regions using Anycast. Use for latency-sensitive global services; understand that it adds a managed layer between your regional clusters and the internet.
- **One LB per workload, not per service:** avoid provisioning a Load Balancer per microservice. Route HTTP traffic by path/host via an nginx or Traefik ingress controller behind a single LB; use separate LBs only for truly distinct entry points (e.g. one for public HTTP, one for internal gRPC).

## Floating IPs and Reserved IPs

- **Floating IPs** are now called **Reserved IPs** in the DigitalOcean Control Panel (the two terms are used interchangeably in older docs).
- Reserved IPs are static public IPv4 addresses that can be reassigned between Droplets in the same datacenter, typically within seconds via the API.
- **Use cases:** primary-standby failover where the primary's IP must survive a failover; stable egress IP for external allow-listing; entry point for a custom load-balancing tier.
- **Cost:** Reserved IPs in use are free. Unassigned Reserved IPs cost $0.006 / hour — delete them when not in use.
- **Assignment automation:** use the DigitalOcean API or Droplet user-data to assign a Reserved IP during Droplet boot for self-managed HA. For DOKS, prefer a DigitalOcean Load Balancer over a Reserved IP for ingress.

## DNS

DigitalOcean DNS is powered by PowerDNS and is globally distributed. It is not a premium DNS product — it lacks advanced features like weighted routing, latency-based routing, or health-check-based failover.

- **Zone management:** import your domain into DigitalOcean DNS only if you are comfortable with its limitations. For complex routing logic, use Cloudflare or Route 53 as the authoritative DNS provider and point records at DigitalOcean Load Balancers.
- **TTL discipline:** set long TTLs (3600 s or higher) for stable records; shorten TTLs to 60 s before a planned migration, then restore after.
- **PTR records (reverse DNS):** set PTR records for all Droplets that send email or appear in server-identifying contexts (SSH banners, TLS common names). DigitalOcean lets you set the PTR record via the Droplet's hostname field in the Control Panel or API.
- **DNSSEC:** DigitalOcean DNS supports DNSSEC signing for domains it manages. Enable it for any domain where you need DNS integrity guarantees.
- **Wildcard records:** use sparingly and only for environments you fully control. A wildcard A record on a domain makes every subdomain resolve to the same IP, which can surprise you during penetration tests.

## Spaces CDN

- **Enable CDN on any Spaces bucket serving end-user assets.** CDN egress is cheaper than origin egress and adds global PoP distribution.
- **Custom subdomain:** Spaces CDN supports a custom subdomain (e.g. `assets.example.com`) via a CNAME record. Configure this before launch; CDN subdomains are part of URLs embedded in frontend code.
- **Cache-Control headers:** set long `max-age` values on immutable assets (versioned CSS/JS) and short or no cache on dynamic content. The CDN respects the origin's `Cache-Control` headers.
- **CDN invalidation:** Spaces CDN does not support API-based cache invalidation as of 2026. Use versioned filenames (content hash in filename) so you never need to invalidate.
- **Access:** a CDN endpoint on a private bucket still serves objects publicly via the CDN URL. Treat a CDN-enabled bucket as effectively public for the paths the CDN covers.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Using the default VPC for production | No meaningful segmentation; CIDR overlaps are common; no naming control. |
| Cloud Firewall rules targeting individual Droplet IPs instead of tags | Breaks on horizontal scale; new Droplets are unprotected until manually added. |
| SSH open to `0.0.0.0/0` | One compromised credential = full Droplet access. Restrict to known CIDRs or use console. |
| Load Balancer health check on `/` returning any non-500 | Passes even when the app is degraded. Use a real readiness endpoint. |
| Reserved IP left unassigned | Costs $0.006 / hour for nothing. Delete unused Reserved IPs. |
| Spaces CDN with long `max-age` on mutable filenames | Stale assets cached at edge; `Cache-Control: no-cache` or content-hash filenames are the fix. |
| Multi-VPC cross-region private connectivity without a VPN | Traffic routes over the public internet; no encryption, no private path. |

## Security defaults

- Cloud Firewall on every Droplet, even inside a VPC — defense in depth against lateral movement if one instance is compromised.
- No `0.0.0.0/0` inbound except on ports 80 and 443 for public-facing load balancers.
- SSH (port 22) not exposed to the internet on any production Droplet; use DigitalOcean console or a VPN-gated bastion.
- All Load Balancer HTTPS listeners use TLS 1.2 minimum; prefer TLS 1.3 where supported by your client base.
- Enable HSTS on the Load Balancer response headers for any HTTPS service.
- VPC Flow Logs: DigitalOcean does not offer native VPC flow logging (as of 2026). Use in-guest packet capture or a third-party network monitoring agent for forensic capability.

## Observability defaults

- Load Balancer metrics are available in the DigitalOcean monitoring dashboard: request rate, backend health, active connections. Wire LB backend health checks to an alert policy.
- DNS: monitor the resolution of your external domains from multiple regions using an external uptime service (Better Uptime, StatusPage.io, or a Prometheus blackbox exporter).
- Alert on Reserved IP reassignment events (available via DigitalOcean API event feeds) to detect unexpected failovers.
- CDN: Spaces CDN does not expose per-request logs. Monitor Spaces bucket access logs for origin hit patterns.

## Cost considerations

- **Load Balancer:** $12 / month per regional LB (1 shared vCPU, 10k concurrent connections). Global Load Balancer pricing is higher; check the current rate before committing.
- **Reserved IPs:** free when assigned, $0.006 / hour when unassigned (~$4.30 / month idle). Delete unassigned IPs.
- **DNS:** free for up to 50 domains and unlimited records.
- **Spaces CDN:** CDN egress is included in the Spaces bandwidth allowance ($0.01 / GB after the free tier). Origin egress is the same rate.
- **Data transfer between Droplets in the same datacenter:** free on the private network. Use VPC-internal addresses for all inter-service traffic.
- **Cross-datacenter bandwidth:** billed at public egress rates. Minimize cross-DC traffic; colocate tightly-coupled services.

## IaC hints

- Terraform resources: `digitalocean_vpc`, `digitalocean_firewall`, `digitalocean_loadbalancer`, `digitalocean_reserved_ip`, `digitalocean_domain`, `digitalocean_record`, `digitalocean_cdn`.
- Always set `vpc_uuid` on Droplets, DOKS clusters, and database clusters — do not accept the default.
- `digitalocean_firewall` supports `inbound_rule` and `outbound_rule` blocks; use `tags` as `sources` / `destinations`, not raw Droplet IDs.
- For Load Balancers fronting DOKS, configure via Kubernetes `Service` annotations (`service.beta.kubernetes.io/do-loadbalancer-*`) rather than a separate Terraform resource — the two approaches conflict.

## Verification checklist

- [ ] Production resources are in a named VPC, not the default VPC.
- [ ] VPC CIDR does not overlap with any networks that need to tunnel or peer.
- [ ] Cloud Firewall applied to all Droplets; rules use tags, not individual IPs.
- [ ] No `0.0.0.0/0` inbound on any port except 80/443 on public-facing LBs.
- [ ] SSH not exposed to the internet on production Droplets.
- [ ] Load Balancer uses HTTPS with a valid cert; HTTP → HTTPS redirect active.
- [ ] Health check configured on a real readiness endpoint, not just `/`.
- [ ] Reserved IPs: none unassigned for more than 24 hours.
- [ ] DNS TTLs appropriate; PTR records set for mail-sending Droplets.
- [ ] Spaces CDN enabled for asset-serving buckets; versioned filenames used.
