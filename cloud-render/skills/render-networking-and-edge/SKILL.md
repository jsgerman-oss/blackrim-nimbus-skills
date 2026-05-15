---
name: render-networking-and-edge
description: Design or audit Render networking and edge — custom domains with automatic TLS, Private Services mesh, HTTP/2, IP allowlists, DDoS posture, regional placement, and HTTPS enforcement. Use when exposing a service, connecting services internally, restricting access, or reviewing edge security.
---

# Render Networking and Edge

## When to use

- Adding a custom domain to a Web Service or Static Site.
- Wiring services together without public internet exposure (Private Services).
- Enabling IP allowlists for a production service.
- Reviewing TLS configuration, HTTPS enforcement, or DDoS posture.
- Choosing which Render region to deploy a service.
- Understanding Render's networking model before a security audit.

## Custom domains and automatic TLS

Render provisions TLS certificates automatically for all custom domains via Let's Encrypt. The process:

1. Add the domain in the Render dashboard or `render.yaml`.
2. Create a CNAME record pointing to Render's load balancer hostname (`<service>.onrender.com`).
3. Render issues and renews the certificate automatically; no manual renewal.
4. HTTPS is the only supported protocol on custom domains — HTTP redirects to HTTPS automatically.

**Apex (root) domains**: Render provides a load balancer IP for A-record configuration so apex domains (e.g. `example.com`) work. Using the IP requires a DNS provider that supports `ALIAS` / `ANAME` records for apex domains (Cloudflare, AWS Route 53). Standard CNAME records cannot be used at the apex.

**DNSSEC**: DNSSEC for your domain is configured at your DNS registrar or DNS provider — Render does not manage it. Enable DNSSEC on production domains at the registrar level to protect against on-path DNS attacks.

**Wildcard domains**: Render supports wildcard custom domains (e.g. `*.example.com`) on Pro plans and above.

## Private Services — the internal mesh

Private Services communicate over Render's internal network. Within the same team and region, services reach each other by name:

```
http://<service-name>:<port>
```

No public DNS entry is created. No public IP is allocated. Traffic does not leave Render's network.

**When to use Private Services:**

- Any HTTP service that is only called by other Render services (internal APIs, gRPC backends, admin panels, microservice backends).
- Any service where exposure to the public internet would create unnecessary attack surface.

**Private Service limitations:**

- Private Services are single-region. Cross-region service-to-service calls go over the public internet (point a Web Service's outbound request at the other region's Web Service URL) — design accordingly.
- Private Services are not reachable from outside Render without a public Web Service proxy in front.
- Service discovery is by name, not by IP — names are stable; IPs are not.

## Native HTTP/2

Render's load balancer terminates TLS and supports HTTP/2 by default on all Web Services and Static Sites. No configuration is required. HTTP/2 multiplexing benefits browser-to-service traffic on TLS-enabled connections.

## IP allowlists

IP allowlists restrict inbound traffic to your service to specific CIDR ranges. Available on Pro plan and above.

**Defaults for production use:**

- Enable IP allowlists on any admin or internal-facing Web Service that cannot be converted to a Private Service.
- When an IP allowlist is active, Render drops requests from unlisted IPs at the load balancer before they reach your service.
- Maintain the allowlist as IaC in `render.yaml` or a tracked configuration document — ad-hoc dashboard edits drift.

**Limitation:** IP allowlists apply to the public endpoint of a Web Service. They do not apply to Private Services (which have no public endpoint). If a workload should only be accessed by other Render services, use Private Service; IP allowlist is for restricting which public IPs can reach a Web Service.

## DDoS and WAF posture

Render provides DDoS mitigation at the network layer (L3/L4) for all services as a platform default — no configuration is required. This covers volumetric attacks.

For L7 (application-layer) protection and WAF capabilities:

- Render does not include a native WAF as of 2026-05.
- Place Cloudflare (or another WAF provider) in front of your Render services for WAF, rate limiting, bot protection, and geo-blocking.
- When using Cloudflare in proxy mode, configure IP allowlists on the Render service to accept traffic only from [Cloudflare's IP ranges](https://www.cloudflare.com/ips/) — prevents attackers from bypassing Cloudflare by targeting the Render origin directly.

## Geographic footprint — regions

Render regions as of 2026-05:

| Region | Code | Notes |
| --- | --- | --- |
| Oregon (US West) | `oregon` | Most feature-complete; default for new teams |
| Ohio (US East) | `ohio` | Good for US East Coast-heavy traffic |
| Frankfurt (EU) | `frankfurt` | EU data residency; GDPR-friendly |
| Singapore | `singapore` | Asia-Pacific |

**Region considerations:**

- All services in a team can span regions but Private Service discovery is region-scoped — services in different regions cannot use the Private Service mesh; they must communicate over public Web Service URLs.
- Place services in the same region as their databases to minimize latency and avoid inter-region data transfer.
- Render does not provide automatic geo-routing or multi-region load balancing — this requires an external DNS provider with latency-based routing (Cloudflare, Route 53).
- If EU data residency is required, deploy all services and databases in `frankfurt` and ensure no cross-region replication to US regions.

## HTTPS enforcement

- Render redirects HTTP to HTTPS on all custom domains and `onrender.com` domains.
- No configuration is required; it is not opt-out.
- HSTS (HTTP Strict Transport Security) headers should be set by your application or, if using Cloudflare in front of Render, by the Cloudflare response headers configuration.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Using a Web Service for an internal API instead of Private Service | Unnecessary public exposure; paying for public ingress that shouldn't exist. |
| No IP allowlist on an admin Web Service | Admin surfaces publicly accessible; any credential leak = access. Use Private Service or IP allowlist. |
| Missing DNSSEC on production domain | On-path DNS attacks can redirect your domain. Enable at the registrar. |
| Bypassing Cloudflare by not allowlisting Cloudflare IPs on Render | WAF can be bypassed by hitting the Render origin IP directly. Lock down with Cloudflare IP allowlist. |
| Cross-region service-to-service via Private Service name | Cross-region Private Service calls fail silently or with confusing DNS errors. Use public Web Service URLs for cross-region. |
| Serving apex domain via CNAME | CNAMEs at the apex break RFC 1034; DNS behavior is undefined. Use ALIAS/ANAME or a DNS provider that supports it. |
| Wildcard certificate on a Starter plan | Wildcard domains require Pro plan; provisioning will fail silently. |

## Security defaults

- HTTPS-only: enforced by the platform; no opt-out needed.
- Internal traffic: use Private Services for all service-to-service communication where external access is not required.
- IP allowlists: enable on any Web Service admin surface or internal-facing endpoint that cannot be a Private Service (Pro plan required).
- WAF: place Cloudflare or an equivalent provider in front for L7 protection; lock down Render origin to Cloudflare IPs via IP allowlist.
- DNSSEC: configure at the registrar for all production domains.
- TLS: automatic certificate management; no manual certificate uploads required.

## Observability defaults

- Render logs include request metadata (status code, latency, IP) for Web Services — enable log streaming to Datadog / Logtail for retention and search.
- Monitor 4xx / 5xx rates per service in the Render dashboard; configure an alert when error rates spike.
- For detailed edge metrics (geo distribution, bot traffic, TLS handshake errors), route traffic through Cloudflare and use its analytics dashboard.

## Cost considerations

- Custom domains: no additional charge.
- IP allowlists: included in Pro plan and above.
- Private Service traffic: no explicit intra-team network charge; behaves like localhost traffic in billing terms.
- Cross-region Web Service calls: subject to normal outbound network rates.
- Cloudflare proxy in front of Render: Cloudflare's free tier is sufficient for basic WAF and DDoS; paid plans add bot management, advanced WAF, and analytics.

## IaC hints

- Custom domains are declared under `domains:` in the service stanza of `render.yaml`.
- `type: pserv` in `render.yaml` creates a Private Service.
- Region is set at the service level with `region:` — all databases used by the service should match the same region.
- IP allowlists are configured in the dashboard (no current `render.yaml` field for allowlists as of 2026-05 — track the Render changelog for Blueprint support).

## Verification checklist

- [ ] All inter-service communication uses Private Services where the caller is on Render.
- [ ] Custom domains use CNAME (or ALIAS for apex) pointing to the Render load balancer.
- [ ] DNSSEC enabled at the registrar for all production domains.
- [ ] Admin surfaces protected by IP allowlist (Pro+) or converted to Private Services.
- [ ] WAF in place (Cloudflare or equivalent) for any public-facing service with user-generated traffic.
- [ ] Cloudflare IP allowlist configured on Render if Cloudflare proxy is in use (to prevent origin bypass).
- [ ] All services and their databases are in the same region.
- [ ] HSTS header set by application or Cloudflare response rules.
