---
name: cf-networking-and-edge
description: Design or audit Cloudflare networking — DNS (authoritative), CDN cache rules, Load Balancing, Argo Smart Routing, Spectrum, Cloudflare Tunnel, Magic WAN / Magic Transit. Use when configuring DNS, tuning cache behaviour, exposing services, or connecting private infrastructure to Cloudflare's network.
---

# Cloudflare Networking and Edge

## When to use

- Setting up or migrating authoritative DNS to Cloudflare.
- Configuring CDN cache rules, transform rules, or purge strategies.
- Standing up load balancing with geo, latency, or weighted routing.
- Reducing origin latency with Argo Smart Routing.
- Exposing TCP/UDP services (beyond HTTP) via Spectrum.
- Securely connecting a private server or network to Cloudflare without opening inbound firewall rules (Cloudflare Tunnel).
- Connecting branch offices or cloud VPCs to Cloudflare's backbone (Magic WAN / Magic Transit).

## DNS (authoritative)

Cloudflare is the authoritative DNS resolver for zones it manages. DNS changes propagate globally within seconds.

### Defaults

- **Proxy status (orange cloud)**: enable for any A/AAAA/CNAME record you want behind Cloudflare's CDN, WAF, and DDoS protection. Leave unproxied (grey cloud) only for records that must resolve to the origin IP directly (mail servers, SFTP, internal tooling).
- **DNSSEC**: enable for every zone. Cloudflare manages signing automatically after you add the DS record to the registrar. DNSSEC prevents on-path resolver cache poisoning.
- **CAA records**: add CAA records specifying your CA to prevent misissued certificates (`issue`, `issuewild`, `iodef`).
- **TTL**: for proxied records, Cloudflare overrides TTL to 300 s regardless of your setting — that is intentional. For unproxied records, set TTL to 300 s during migrations; raise to 3600 s+ once stable.
- **API-managed DNS**: use Terraform (`cloudflare_record` resource) or Wrangler for DNS records that are part of a Worker deployment. Do not mix console clicks and IaC for the same zone.

## CDN — Cache Rules and Transform Rules

### Cache rules

- Cloudflare's **Cache Rules** (zone-level) replace the older Page Rules — use Cache Rules for all new configurations. Page Rules are a legacy feature and will be deprecated.
- Set cache eligibility explicitly per path: `cache everything` for static assets; `bypass cache` for authenticated API endpoints.
- **Edge cache TTL**: how long Cloudflare holds the response. Set via `Cache-Control: s-maxage=<seconds>` from origin, or override with a Cache Rule.
- **Browser cache TTL**: how long the client holds the response. Do not let Cloudflare's default override origin `Cache-Control` unless you have a specific reason.
- **Cache keys**: vary on headers (`Accept-Encoding`, `Accept-Language`) only if your origin actually serves different responses per header; unnecessary variation fragments the cache.

### Purging

- Purge by URL for targeted invalidation; purge by tag (Cache-Tag header) for grouped invalidation (requires Business or Enterprise plan).
- Purge via API or Wrangler: `wrangler pages deployment tail` triggers can automate post-deploy purges.
- Stale-while-revalidate: set `stale-while-revalidate` in `Cache-Control` to serve stale content while the cache refreshes — reduces origin load spikes on popular content.

### Transform Rules

- Rewrite URLs, add/modify request/response headers — all at the edge without changing origin code.
- Use Transform Rules to inject security headers (`Strict-Transport-Security`, `Content-Security-Policy`) globally across a zone instead of per-application.
- TLS: enforce HTTPS-only with an HTTPS redirect Rule (or zone-level "Always Use HTTPS" toggle). TLS Mode must be set to **Full (Strict)** — not Flexible (Flexible decrypts at Cloudflare but sends plain HTTP to origin, a false sense of security).

## Load Balancing

Cloudflare Load Balancing is DNS-based and/or proxy-based (for proxied records).

### Routing strategies

| Strategy | When to use |
| --- | --- |
| **Geographic (geo)** | Route users to the nearest origin region; useful for data residency. |
| **Latency** | Route to the fastest-responding origin (measured by Cloudflare health check latency). |
| **Weighted** | Split traffic by percentage — canary releases, A/B tests, gradual migrations. |
| **Random** | Simple round-robin across origins of equivalent capability. |
| **Failover** | Primary pool active; fallback pool used only when primary health checks fail. |

### Defaults

- Health checks: active (HTTP probe) on every origin; mark `critical` threshold = 1 unhealthy check. Passive health checks are less reliable for detecting origin degradation.
- Session affinity: off by default (stateless is preferred). Enable only if your origin holds session state locally — and even then, evaluate migrating session state to KV or D1.
- Multiple origins in a pool: distribute across two or more datacenters / cloud regions within the pool. The pool-level health check then governs failover to a secondary pool.
- Steering policy: use latency-based steering for user-facing services; geographic for compliance/data residency scenarios.

## Argo Smart Routing

Argo routes traffic over Cloudflare's backbone (avoiding the public internet) between Cloudflare PoPs and the origin. Reduces latency and improves reliability for uncached traffic.

- Enable at the zone level: dashboard > Traffic > Argo.
- Effective for dynamic / uncacheable responses where origin round-trip dominates.
- Cost: billed on bandwidth (per GB) beyond a free tier. Calculate benefit vs cost for low-traffic zones.
- Not a substitute for caching — maximize cache hit rate first; Argo improves the miss path.

## Spectrum

Spectrum proxies arbitrary TCP and UDP traffic (not just HTTP) through Cloudflare's DDoS protection and anycast network.

- Use cases: game servers, SSH, RDP, MQTT, custom TCP protocols.
- Each Spectrum application proxies a specific origin:port on a Cloudflare-assigned anycast IP.
- Spectrum does not provide WAF or caching — those are HTTP-only features. DDoS mitigation applies at the network layer.
- Magic Firewall can apply packet-level rules to Spectrum traffic on enterprise plans.

## Cloudflare Tunnel

Cloudflare Tunnel (`cloudflared`) creates an outbound-only encrypted tunnel from a private server to Cloudflare's network. No inbound firewall ports needed.

### Defaults

- Install `cloudflared` on the origin server; authenticate with `cloudflared tunnel login`.
- Create and route a tunnel: `cloudflared tunnel create <name>` → configure `config.yml` with ingress rules → `cloudflare tunnel route dns <name> <hostname>`.
- Run as a system service (`cloudflared service install`) for reliability.
- Replicate tunnel connectors (run `cloudflared` on two instances per tunnel) for high availability — Cloudflare routes around a failed connector automatically.
- For Kubernetes: use the official `cloudflared` Helm chart or the Cloudflare Kubernetes Operator.
- Access control: put Cloudflare Access in front of a Tunnel-exposed application to require identity verification before traffic reaches the origin.
- Do not expose tunnels publicly without Access unless the application has its own robust authentication.

## Magic WAN / Magic Transit

Enterprise-tier services for connecting branch networks, cloud VPCs, and data centers to Cloudflare's backbone.

- **Magic WAN**: SD-WAN functionality — route traffic from branch offices over GRE/IPsec tunnels to Cloudflare, then to destinations (internet via Gateway, or other connected networks).
- **Magic Transit**: BGP-announced prefix protection — Cloudflare announces your IP prefixes, scrubs traffic, and forwards clean traffic to your network over a GRE tunnel. Designed for DDoS-at-scale on infrastructure IPs (not HTTP-layer).
- Both require enterprise contracts and involve network-level configuration (BGP, GRE, IPsec). Covered here at an overview level; implementation requires Cloudflare solutions engineering engagement.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| TLS Mode = Flexible | Cloudflare-to-origin traffic is unencrypted. A network-level observer between Cloudflare and your origin sees plaintext. Use Full (Strict). |
| Grey-cloud (DNS-only) for user-facing web records | Exposes origin IP, bypasses WAF and DDoS protection. Proxy everything user-facing. |
| DNS TTL of 1 s on stable records | Hammers Cloudflare resolvers unnecessarily and can cause resolver throttling. Use 300 s minimum. |
| DNSSEC disabled | On-path resolver attacks (cache poisoning) become possible. Enable DNSSEC on every zone. |
| Cloudflare Tunnel with no Access policy in front | Any internet user who discovers the hostname can reach your internal service. |
| Load Balancer with no health checks | A dead origin continues to receive traffic. All origins must have active health checks. |
| Cache Rules that vary on `User-Agent` | Nearly unlimited cache variation, effectively disabling caching. Vary only on headers where origin truly differs. |
| Argo enabled on a fully cacheable static site | You pay Argo bandwidth costs on origin fetches for a site that should have near-100% cache hit rate. Cache first. |

## Security defaults

- DNSSEC on for every zone.
- CAA records present on every zone with a specified CA.
- TLS Mode = Full (Strict); HTTPS-only redirect on.
- Security headers injected via Transform Rules: `Strict-Transport-Security: max-age=31536000; includeSubDomains; preload`, `X-Frame-Options: SAMEORIGIN`, `X-Content-Type-Options: nosniff`.
- Minimum TLS version: 1.2 (1.3 preferred for new services).
- Always Use HTTPS: enabled zone-wide.
- Cloudflare Access in front of any Tunnel-exposed internal service.

## Observability defaults

- DNS analytics: monitor query volume and NXDOMAIN rate for unexpected spikes (potential DDoS or misconfiguration).
- Cache analytics: track cache hit ratio; alert if hit ratio drops below a baseline (indicates cache busting bug).
- Load Balancing: monitor pool health status; alert immediately when a pool's health drops below threshold.
- Argo: track latency improvement vs non-Argo baseline from the Traffic analytics page.
- Logpush: push HTTP request logs to R2 or a SIEM for full request-level visibility (includes cache status, WAF action, and origin response time).

## Cost considerations

- Load Balancing: billed per active health check and per pool. Consolidate health checks; remove unused pools.
- Argo Smart Routing: billed per GB of traffic that benefits from smart routing. Enable only where uncached dynamic traffic is significant.
- Spectrum: billed per GB of TCP/UDP traffic. Not cheap for high-bandwidth protocols; calculate break-even vs raw DDoS mitigation.
- Magic WAN / Magic Transit: enterprise pricing; requires separate contract.
- DNS (authoritative): included in all plans; no per-query charge.
- Cache: reducing origin traffic is the primary cost benefit — fewer origin requests means lower origin compute and egress costs.

## IaC hints

- Terraform `cloudflare/cloudflare` ≥ 5.x: `cloudflare_record` for DNS, `cloudflare_ruleset` for Cache Rules and Transform Rules (v5 replaced `cloudflare_page_rule`; do not use page rules in new IaC), `cloudflare_load_balancer` + `cloudflare_load_balancer_pool` + `cloudflare_load_balancer_monitor`, `cloudflare_argo` for Argo toggle.
- Cloudflare Tunnel: `cloudflare_tunnel` + `cloudflare_tunnel_config` + `cloudflare_tunnel_route` in Terraform; `cloudflared` binary deployed separately (Ansible, Helm, or systemd unit).
- DNSSEC: `cloudflare_zone_dnssec` resource; DS record must be added at the registrar outside Terraform.

## Verification checklist

- [ ] All user-facing DNS records are orange-cloud (proxied).
- [ ] DNSSEC enabled and DS record installed at the registrar.
- [ ] CAA records present specifying the permitted CA.
- [ ] TLS Mode = Full (Strict) on every zone.
- [ ] HTTPS redirect and minimum TLS 1.2 enforced.
- [ ] Security headers set via Transform Rules or origin application.
- [ ] Load Balancer pools have active health checks; failover tested.
- [ ] Cloudflare Tunnel connectors run on two instances for HA; Access policy in front.
- [ ] Cache hit ratio monitored; Cache Rules do not vary on high-cardinality headers.
- [ ] Logpush configured for HTTP request logs to R2 or SIEM.
