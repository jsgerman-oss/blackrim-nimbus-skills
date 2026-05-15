---
name: railway-services
description: Design, configure, or audit Railway Services — build source selection (Git repo / Dockerfile / pre-built image), Nixpacks auto-detect vs custom Dockerfile, build and start command overrides, restart policy, health checks, replicas (Pro plan), Volumes for persistent disk, and resource limits (vCPU + memory). Use when adding a new service, tuning build behavior, configuring persistent storage, or right-sizing resources.
---

# Railway Services

## When to use

- Adding a new service to a Railway project from a Git repo, Dockerfile, or container image.
- Deciding between Nixpacks auto-detection and a custom Dockerfile.
- Configuring health checks, restart policies, or replica counts.
- Mounting a Volume for persistent data (uploads, SQLite, local caches).
- Setting vCPU and memory resource limits to control costs and prevent noisy-neighbor issues.
- Reviewing why a build or deploy is failing.

## Build source decision tree

1. **Git repo, well-known language or framework** (Node, Python, Go, Ruby, Java, Rust, PHP, Elixir, etc.) — let **Nixpacks** auto-detect. Zero config, fast iteration. Override the detected buildpack only when detection is wrong.
2. **Git repo with specific OS dependencies, multi-stage build, or non-standard runtime** — **Dockerfile** at repo root (or the path specified in service settings). Use multi-stage builds to keep final images small.
3. **Pre-built container image** (Docker Hub, GHCR, ECR) — **Docker image** source. Pin an explicit tag; never `latest` in production.
4. **Monorepo with multiple services** — configure the **root directory** per service so Railway scopes the build context correctly. Each service gets its own Railway service entity.

## Nixpacks defaults and overrides

Nixpacks reads your repo and picks build packs automatically. Common overrides:

```toml
# railway.toml — service-level config
[build]
builder = "nixpacks"
buildCommand = "npm run build"

[deploy]
startCommand = "node dist/server.js"
```

- `nixpacks.toml` in the repo root controls phases (`setup`, `install`, `build`, `start`) and apt packages.
- Pin the Node / Python / Go version via `.node-version`, `.python-version`, or `go.mod` — Nixpacks reads all of them.
- Add a `Procfile` (`web: node server.js`) as an alternative to `startCommand` for Heroku-familiar repos.

## Health checks

Every production service must have a health check. Without one, Railway marks a deploy as healthy the moment the container starts, before it can actually serve traffic.

```json
{
  "deploy": {
    "healthcheckPath": "/health",
    "healthcheckTimeout": 300
  }
}
```

- `healthcheckPath`: an HTTP GET endpoint that returns 2xx when the service is ready. Keep the handler lightweight — no DB queries.
- `healthcheckTimeout`: seconds Railway waits for the first 2xx before marking the deploy failed. 300 s is a safe default for JVM / .NET services; trim to 60 s for Go / Node.
- For non-HTTP services (workers, queues), Railway cannot HTTP-probe — omit the path and rely on restart policy instead.

## Restart policy

| Policy | When to use |
| --- | --- |
| `ON_FAILURE` | Stateless services that should restart automatically on crash, but not on deliberate `railway down`. Default. |
| `ALWAYS` | Background workers where any exit (including clean exit 0) should restart. |
| `NEVER` | One-shot jobs (migrations, seed scripts) that must not loop. |

Set in `railway.json`:

```json
{
  "deploy": {
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

## Replicas (Pro plan)

Horizontal scaling within a single Railway environment. Replicas are stateless copies of the service behind Railway's internal load balancer.

- Minimum: 1. Maximum: depends on plan.
- All replicas share the same environment variables and Volumes are NOT shared across replicas — they each get their own Volume mount. Design services to be stateless; move shared state to a database or Redis Plugin.
- Set in `railway.json` or via the dashboard. There is no autoscaling knob — you set a fixed replica count.
- Inflection point: if you need dynamic autoscaling based on load, Railway is not the right host — consider a container platform (Fly, ECS, Cloud Run).

## Volumes (persistent disk)

Volumes provide a persistent filesystem mount that survives deploys and restarts. Use for:

- User upload staging before S3/R2 transfer.
- SQLite databases for low-write workloads (hobby / internal tools).
- Build caches that are expensive to regenerate.

```json
{
  "deploy": {
    "volume": {
      "mountPath": "/data"
    }
  }
}
```

Constraints:

- One Volume per service.
- Volumes are not replicated across Railway's infrastructure — data loss on hardware failure is possible. Do not store critical production data without a backup strategy.
- Volumes do not span replicas — each replica instance gets its own Volume.
- Size is configured in the Railway dashboard; billed per GB per month.

## Resource limits

Railway bills on actual CPU-seconds and memory-seconds used (per-second granularity). Setting limits prevents cost runaway and protects neighbors on shared infrastructure.

| Setting | Default | Notes |
| --- | --- | --- |
| vCPU | 8 vCPU | Burst limit, not a guarantee. Shared infrastructure. |
| Memory | 8 GB | Hard limit; OOM kills the container. |

Set in the Railway dashboard per service (no `railway.json` knob as of 2026-05). Start conservatively:

- Web services: 0.5–1 vCPU, 512 MB–1 GB.
- Workers: 1–2 vCPU, 256 MB–512 MB.
- Data-heavy jobs: profile actual usage; bump as needed.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| No health check on an HTTP service | Railway serves traffic to a booting container; users see errors during slow cold starts. |
| `restart: ALWAYS` on a migration service | Migration runs repeatedly, corrupting state or failing on second run. Use `NEVER`. |
| Storing primary DB data in a Volume | No HA, no managed backups, possible data loss on infra failure. Use a Plugin or external managed DB. |
| Pinning `latest` image tag | Uncontrolled upstream changes break deploys silently. Always pin a digest or explicit tag. |
| Over-provisioning "to be safe" | Railway bills on usage, but idle high-limit services on paid plans still count toward seat quotas and usage floors. Right-size. |
| Single replica for a stateful service sharing Volume | Multiple replicas each get their own Volume, breaking the shared-state assumption. Design stateless or use one replica. |

## Security defaults

- Container image pulled fresh on every deploy — no stale layer surprises, but ensure images are from trusted registries.
- Build logs are visible to all project members; avoid printing secrets in build commands.
- Prefer Nixpacks or Dockerfile over shell scripts in `buildCommand` that curl-pipe-bash external scripts.
- Set resource limits so a runaway process cannot starve other services on the shared host.

## Observability defaults

- Build and deploy logs stream live in the Railway dashboard under each service.
- `railway logs` (CLI) for historical log access and filtering.
- Add structured logging to your app (`JSON lines`, not printf) so Railway's log drain (Datadog, Better Stack, Logflare) can parse fields.
- Metrics (CPU, memory, network) are visible in the Railway dashboard; see `railway-observability-and-cost` for drain configuration.

## Cost considerations

- Railway charges **per-second CPU and memory**. A crashed service that restart-loops spends CPU even if it never handles a request.
- Set `restartPolicyMaxRetries` to cap runaway restart loops.
- Nixpacks builds are fast and cacheable — faster builds = shorter build minutes used.
- Volumes are charged per GB-month. Remove orphaned Volumes after deleting a service.
- Pro plan replicas multiply costs linearly: 3 replicas × resource usage = 3× bill.

## IaC hints

`railway.json` (project-wide) and `railway.toml` (service-level, checked into repo) are the two config layers:

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "node server.js",
    "healthcheckPath": "/health",
    "healthcheckTimeout": 60,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

Use `railway up --detach` in CI for non-blocking deploys; `railway status` to poll completion.

## Verification checklist

Before declaring a service configuration complete:

- [ ] Build source is correct (Nixpacks, Dockerfile, or image) and version is pinned.
- [ ] Health check path is configured and returns 2xx when the service is genuinely ready.
- [ ] Restart policy is `ON_FAILURE` for services, `NEVER` for one-shot jobs.
- [ ] Volume is present only if the service genuinely needs persistent local disk; critical data has a backup strategy.
- [ ] Resource limits are set in the dashboard; right-sized by profiling, not guesswork.
- [ ] Replicas are 1 unless the service is stateless and load justifies more.
- [ ] No secrets printed in build or start commands.
- [ ] At least one log line emitted on healthy startup (confirms service reached readiness).
