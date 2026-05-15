---
name: fly-networking-and-edge
description: Design or audit Fly.io networking — anycast IPv4/IPv6, the 6PN WireGuard private network, Flycast for private anycast routing, fly.toml services, TCP/HTTP/TLS handlers, dedicated IPs, WireGuard peer tunnels. Use when exposing a service, designing service-to-service communication, configuring TLS termination, or auditing network exposure.
---

# Fly Networking and Edge

## When to use

- Standing up a new Fly App and deciding whether it needs a public IP.
- Designing service-to-service communication within a Fly organization.
- Configuring TLS, HTTP → HTTPS redirect, or custom TLS passthrough.
- Assigning or removing dedicated IPv4 addresses (cost consideration).
- Using WireGuard to tunnel from a developer machine or external network into 6PN.
- Auditing which machines have public exposure.

## Anycast routing — how Fly's edge works

Fly operates a global anycast network. A DNS name like `myapp.fly.dev` resolves to an anycast IP that routes the connection to the nearest Fly point-of-presence (PoP), where the Fly Proxy accepts the connection and forwards it to the appropriate Machine.

Key implications:

- **No single origin IP.** The same request from different geolocations enters Fly at different PoPs; there is no single "server IP" to allowlist.
- **IPv6 by default, shared IPv4 by default.** Fly provides a shared anycast IPv4 and a dedicated anycast IPv6 for every App automatically. Dedicated IPv4 costs $2/mo.
- **TLS is terminated at the Fly Proxy.** The proxy terminates TLS on behalf of your app unless you configure TLS passthrough (`tls_options` in `fly.toml`).

## IP address model

| Type | Default? | Cost | Use when |
| --- | --- | --- | --- |
| Shared IPv4 (anycast) | Yes | Free | Most apps — the Fly Proxy routes by SNI. |
| Dedicated IPv4 (anycast) | No | ~$2/mo | You need a stable public IP for allowlisting, or run non-HTTP protocols that can't share. |
| Shared IPv6 (anycast) | Yes | Free | Modern clients; HTTP/3 (QUIC). |
| Private (6PN) | Always | Free | Intra-org service-to-service communication. |

Add a dedicated IP: `fly ips allocate-v4`. Remove: `fly ips release <ip>`.

For cost discipline: audit shared-IP sufficiency before allocating dedicated IPs. Most web apps do not need a dedicated IPv4.

## 6PN — the private network

Every Fly organization has a **6PN** (private WireGuard mesh). Every Machine in the org gets a stable private IPv6 address on the `fdaa::/8` range. Machines in the same org can reach each other by DNS name or by the raw 6PN address without traversing the public internet.

6PN DNS naming convention:

```
<app-name>.internal          → resolves to all machines in the app (round-robin)
<machine-id>.<app-name>.internal → resolves to a specific machine
top6.nearest.of.<app-name>.internal → nearest 6 machines (lowest latency)
```

Use 6PN for: database connections, inter-service API calls, admin endpoints, anything that does not need public exposure.

## Flycast — private anycast within an org

Flycast is Fly's **private anycast** for internal services. It lets you reach a multi-machine Fly App from within the 6PN without exposing a public IP, with full load balancing across machines.

Enable Flycast:

```bash
fly ips allocate-v6 --private   # Allocate a Flycast address
```

In `fly.toml`, configure an `[[internal_port]]` service (no public handler). Flycast routes connections from within the org to that internal port, load-balanced across healthy machines.

When to use Flycast vs raw 6PN DNS:

- **Flycast**: you want load balancing and health-checked routing across machines without a public IP.
- **Raw 6PN**: you want to reach a specific machine by its stable address (e.g., Postgres primary by machine ID).

## `fly.toml` services — HTTP and TCP

The `[[services]]` block in `fly.toml` defines how Fly Proxy exposes your app.

### HTTPS service (standard web app)

```toml
[[services]]
  internal_port = 8080
  protocol = "tcp"

  [[services.ports]]
    port = 80
    handlers = ["http"]
    force_https = true    # Redirect HTTP → HTTPS

  [[services.ports]]
    port = 443
    handlers = ["tls", "http"]

  [[services.http_checks]]
    interval = "10s"
    timeout = "2s"
    grace_period = "5s"
    method = "GET"
    path = "/healthz"
    protocol = "http"
```

### TLS passthrough (raw TCP with TLS to the app)

```toml
[[services.ports]]
  port = 443
  handlers = ["tls"]
  [services.ports.tls_options]
    alpn = ["h2", "http/1.1"]
    default_self_signed = false
```

Use TLS passthrough when: you need mTLS, you run a protocol other than HTTP/HTTPS, or you want to terminate TLS inside the app process.

### TCP service (non-HTTP protocol)

```toml
[[services]]
  internal_port = 5432
  protocol = "tcp"

  [[services.ports]]
    port = 5432
    handlers = []     # No proxy-level handler; raw TCP
```

For databases, prefer **no public `[[services]]` block** — use 6PN instead.

## TLS certificate management

- **Default:** Fly issues and renews Let's Encrypt certificates automatically for `*.fly.dev` domains and any custom domain you add via `fly certs add`.
- **Custom domains:** point your DNS CNAME to `<app>.fly.dev`; Fly provisions the cert automatically.
- **Certificate issuance time:** DNS-01 challenge; new certs take 30–90 s. Do not deploy a new custom domain immediately before a high-traffic event.
- **mTLS:** not handled by Fly Proxy; terminate in-app or use a sidecar (e.g., Envoy) if needed.

## WireGuard tunnels — developer / external access

Fly exposes WireGuard tunnel configuration for direct access to 6PN from outside Fly:

```bash
fly wireguard create [org] [region] [name]   # Generate a peer config
# Copy the WireGuard config to your local /etc/wireguard/fly.conf
wg-quick up fly                              # Connect
```

Once connected, `<app>.internal` resolves from your machine into the 6PN.

Use cases:

- Developer access to a private Postgres or Redis.
- Running `psql` locally against a Fly Postgres instance without exposing a public IP.
- CI access to internal services for integration tests.

Do not leave WireGuard peers active indefinitely. Generate per-developer, revoke on offboarding (`fly wireguard remove`).

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Dedicated IPv4 for every app "just in case" | $2/mo per IP adds up; shared IPv4 with SNI routing works for 90% of HTTP apps. |
| Public `[[services]]` on a database app | Postgres or Redis exposed to the internet; one credential leak = breach. Use 6PN only. |
| No `force_https = true` on HTTP ports | HTTP requests served in plaintext to anyone on the path. |
| Leaving development WireGuard peers active forever | Revoked employees retain network access. Rotate peers on offboarding. |
| Relying on `<app>.internal` without understanding round-robin | `<app>.internal` round-robins all machines; writes to a replica hit a wrong node. Use machine-specific addresses or Flycast for predictable routing. |
| TLS passthrough when Fly managed certs would work | Managed certs auto-renew; DIY TLS creates cert-expiry incidents. |
| HTTP-only health checks on a TLS-passthrough service | Fly Proxy checks HTTP internally; if your app only speaks TLS, configure a TCP check instead. |

## Security defaults

- All public services: `force_https = true` on port 80.
- No public `[[services]]` on internal services — 6PN or Flycast only.
- TLS: Fly Proxy defaults to modern TLS (TLS 1.2 minimum). For TLS 1.3-only, set `[services.ports.tls_options] versions = ["TLSv1.3"]`.
- HTTP → HTTPS redirect is not automatic without `force_https = true`. Explicitly set it.
- Review `fly ips list` quarterly; release unused dedicated IPs.
- WireGuard peer configs contain private keys — store them as secrets, not in version control.

## Observability defaults

- `fly logs` streams structured log output from all machines in an app. Route to an external NATS subscriber or log shipper for retention.
- Fly Proxy access logs (connection counts, 5xx rates) are available in Fly's built-in Grafana dashboard.
- Alarm on: 5xx response rate from the proxy, health check failure rate, connection saturation per machine.
- For custom networking metrics (TCP retransmits, latency percentiles), run a metrics sidecar inside the machine and ship to your external observability stack.

## Cost considerations

- Shared IPv4 + IPv6: free. Dedicated IPv4: ~$2/mo per IP.
- Anycast network egress is billed per GB, with rates that vary by region pair. Inter-org 6PN traffic does not incur egress — it stays on the Fly backbone.
- WireGuard tunnel does not incur a separate cost beyond normal egress.
- HTTP/3 (QUIC) on IPv6 reduces connection overhead for mobile and high-latency clients; Fly's anycast supports it where client networks allow.

## IaC hints

- `fly.toml` `[[services]]` and `[[services.ports]]` are the primary networking configuration surface.
- IP allocation is imperative (`fly ips allocate-v4`); record allocated IPs in your deployment runbook.
- Pulumi `flyio/fly` provider has limited support for IP allocation as of 2025 — fallback to `fly` CLI in provisioning scripts.
- WireGuard peer configs can be generated in CI and stored as secrets for automated tunnel setup.

## Verification checklist

- [ ] Every public service has `force_https = true` on port 80.
- [ ] Internal services have no public `[[services]]` block — accessible only via 6PN or Flycast.
- [ ] TLS certificate issued and valid before traffic goes live (`fly certs check`).
- [ ] No dedicated IPv4s allocated without a specific need documented.
- [ ] WireGuard peer list reviewed; stale peers removed.
- [ ] Health checks configured on every public service with a realistic `grace_period`.
- [ ] Egress cost estimated for expected traffic volumes.
- [ ] `fly ips list` reviewed for unexpected public allocations.
