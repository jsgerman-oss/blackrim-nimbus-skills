---
name: railway-networking
description: Design or audit Railway networking — service-to-service communication via private domains (`<service>.railway.internal`), public domains with automatic TLS, custom domains, port detection from `$PORT`, TCP proxy for non-HTTP services, and sticky-session considerations. Use when connecting services internally, exposing a service to the internet, setting up a custom domain, or debugging connectivity.
---

# Railway Networking

## When to use

- Connecting two Railway Services to each other without going through the public internet.
- Exposing an HTTP service to users with a Railway-managed domain or a custom domain.
- Configuring a non-HTTP service (raw TCP, gRPC, database proxy) via Railway's TCP proxy.
- Debugging why a service can't reach another service.
- Setting up TLS for a production domain.
- Understanding how port detection works and what `$PORT` means.

## Private networking — service-to-service

Railway services in the same project and same environment can reach each other over a private network using the internal domain pattern:

```text
http://<service-name>.railway.internal:<port>
```

- `<service-name>` is the Railway service name, lowercase, spaces replaced by hyphens.
- `<port>` is the port the target service listens on (the internal port, not the public-facing port).
- Private traffic does NOT leave Railway's infrastructure — it stays on the internal network.
- This is the correct way to connect an API service to a backend service, or an app to its database sidecar.

Example: an API calling a background worker:

```text
WORKER_URL=http://background-worker.railway.internal:8080
```

Use Reference Variables to avoid hardcoding the service name:

```text
WORKER_URL=http://${{background-worker.RAILWAY_PRIVATE_DOMAIN}}:8080
```

`RAILWAY_PRIVATE_DOMAIN` is automatically injected into every service and resolves to `<service-name>.railway.internal`.

## Port detection and `$PORT`

Railway **automatically assigns a `$PORT` environment variable** to every service. Your app must bind to `$PORT`, not a hardcoded port number.

```javascript
// Node.js
const port = process.env.PORT || 3000;
app.listen(port);
```

```python
# Python / Flask
port = int(os.environ.get("PORT", 8080))
app.run(host="0.0.0.0", port=port)
```

```go
// Go
port := os.Getenv("PORT")
if port == "" { port = "8080" }
http.ListenAndServe(":"+port, nil)
```

- Railway detects the port from `$PORT` automatically and routes public traffic to it.
- If your app ignores `$PORT` and binds to a fixed port, Railway cannot route public traffic to the service (the health check will fail).
- For private network calls from other services, use the internal port (the one you bind to).

## Public domains and TLS

Railway auto-generates a public HTTPS domain for every service that exposes an HTTP port:

```text
https://<random-slug>.up.railway.app
```

- TLS is managed automatically by Railway — no certificate provisioning needed.
- The auto-generated domain is suitable for development and internal testing.
- For production, use a custom domain.

### Custom domains

1. Add the custom domain in the Railway dashboard under the service's "Settings" → "Domains".
2. Railway generates a `CNAME` target.
3. Create a `CNAME` record at your DNS provider pointing to Railway's `CNAME` target.
4. Railway provisions a Let's Encrypt certificate automatically once DNS propagates.

Production domain checklist:

- Use a subdomain (`api.example.com`), not the apex (`example.com`) — apex CNAMEs are not universally supported and break with some DNS providers. If you must use an apex domain, use an ALIAS / ANAME record if your DNS provider supports it.
- TLS is automatic and renews automatically. No action needed.
- Remove the auto-generated `*.up.railway.app` domain from production services — it's an extra exposure surface that bypasses your custom domain's DNS controls.

## TCP proxy (non-HTTP services)

Railway's public proxy is HTTP/HTTPS by default. For non-HTTP services (raw TCP, gRPC without HTTP/2 detection, database proxy), enable the TCP proxy:

- Add a TCP proxy in the service's "Settings" → "Networking" → "TCP Proxy".
- Railway assigns a public `<random>.railway.app:<port>` address.
- Use case: exposing a Postgres sidecar or a game server to external clients.

Security note: TCP proxies bypass HTTP-level protections (no rate limiting, no WAF). Only enable for services that implement their own authentication and connection security. Never use the TCP proxy to expose a raw database to the public internet in production.

## Sticky sessions

Railway does not support sticky sessions. The internal load balancer distributes requests across replicas without affinity.

Design implications:

- Stateless services work well; requests may land on any replica.
- Session state must live in a shared store (Redis Plugin, external Redis) — never in process memory if you run multiple replicas.
- WebSocket connections will be dropped on deploy or replica cycling. Implement reconnect logic on the client.
- If you genuinely need sticky sessions (e.g., for a stateful real-time protocol), Railway is not the right platform — consider Fly.io (which supports sticky routing) or a VM-based host.

## Service ordering and startup dependencies

Railway deploys services concurrently by default. If service B depends on service A being healthy first (e.g., a migration service before the web server), configure service ordering in the Railway dashboard ("Settings" → "Service Dependencies").

- Ordering is best-effort — Railway waits for the health check of the upstream service before starting the dependent.
- If you don't use health checks, ordering has no meaningful effect.
- For migration-then-web patterns, a health check on the migration service (even a simple exit 0) signals Railway that it completed.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Hardcoding port numbers instead of `$PORT` | Service fails to receive public traffic; health check fails; deploy appears broken. |
| Using public domains for internal service calls | Traffic exits Railway's network, incurs latency, and bypasses private network. Use `.railway.internal`. |
| Exposing a database via TCP proxy permanently | Public database with no IP allowlist is a breach waiting to happen. Use private networking. |
| Using apex domain with a CNAME record | DNS misconfiguration; apex domains require ALIAS/ANAME support. Use a subdomain. |
| Assuming sticky sessions without configuring them | Session state lost between requests; use Redis for shared session storage. |
| Multiple replicas with in-process websocket state | Clients on different replicas can't communicate. Use a pub/sub broker (Redis) for WS fan-out. |

## Security defaults

- Private networking (`.railway.internal`) is encrypted in transit within Railway's infrastructure.
- Public HTTPS domains terminate TLS at Railway's edge with a valid certificate.
- Prefer private networking for all internal calls — reduces public exposure surface.
- Remove unused public domains from services (especially `*.up.railway.app` from production services that have a custom domain).
- TCP proxy: enabled only when genuinely necessary; never for raw database exposure.
- Custom domain TLS uses Let's Encrypt certificates with automatic renewal — verify in the dashboard that the certificate is valid before launch.

## Observability defaults

- HTTP access logs are available per service in the Railway dashboard.
- Network egress metrics (bytes sent/received) visible in the service metrics panel.
- For private network debugging: add a temporary log line in both caller and callee to verify the connection reaches the target; remove before production.
- Check `RAILWAY_PRIVATE_DOMAIN` env var in the target service's variable panel to confirm the internal address.

## Cost considerations

- Private network traffic (`.railway.internal`) does not count toward external egress — use it for all internal calls.
- Custom domain TLS provisioning is free.
- TCP proxy connections count toward egress billing if traffic flows to the internet.
- Ingress from the internet is free; egress to the internet is billed. Minimize unnecessary public-facing data transfers.

## IaC hints

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "deploy": {
    "healthcheckPath": "/health"
  }
}
```

Reference Variables for private networking:

```text
BACKEND_URL=http://${{backend-service.RAILWAY_PRIVATE_DOMAIN}}:${{backend-service.PORT}}
```

Custom domain configuration cannot be scripted via `railway.json` — it is dashboard-only or via the Railway API.

## Verification checklist

Before declaring a networking configuration complete:

- [ ] App binds to `$PORT` (not a hardcoded port number).
- [ ] Internal service calls use `.railway.internal` addresses, not public URLs.
- [ ] Production custom domain is configured with a valid CNAME and TLS certificate.
- [ ] Auto-generated `*.up.railway.app` domain removed from production services that have a custom domain.
- [ ] TCP proxy enabled only where necessary and only for authenticated services.
- [ ] Session state lives in Redis (or equivalent shared store) if running multiple replicas.
- [ ] WebSocket clients implement reconnect logic (Railway redeploys drop connections).
- [ ] Service dependency ordering configured for migration-before-app patterns.
