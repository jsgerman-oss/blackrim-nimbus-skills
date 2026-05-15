---
name: render-services
description: Choose, design, or harden Render compute — Web Services (autoscale, zero-downtime deploys, custom domains, health checks), Private Services (internal-only), Background Workers, Cron Jobs, Static Sites, image-based vs runtime builds, service plans. Use when picking a service type, sizing a plan, configuring autoscaling, or reviewing a service architecture for cost and availability.
---

# Render Services

## When to use

- Choosing a Render service type for a new workload (Web Service vs Worker vs Cron vs Static Site).
- Configuring autoscaling thresholds or replica counts.
- Tuning health checks for zero-downtime deploys.
- Deciding between `runtime: docker` (Dockerfile build) and image-based deploys (pre-built registry image).
- Reviewing a service's plan tier against its actual traffic and cost.
- Understanding free-tier sleep semantics and when to upgrade.

## Decision tree

1. **Serves HTTP/HTTPS externally to users** → Web Service.
2. **Serves HTTP but only called by other Render services** → Private Service (stays on the internal mesh; no public URL).
3. **Long-running process, no HTTP listener** → Background Worker.
4. **Runs on a schedule, not triggered by traffic** → Cron Job.
5. **Pure frontend (HTML/CSS/JS), no server-side rendering** → Static Site (free, CDN-backed, no server to run).
6. **Complex build pipeline, multi-stage Docker, custom base image** → image-based deploy via a registry (Docker Hub, GHCR, AWS ECR); point Render at the pre-built image tag.

## Service types — details

### Web Service

The primary unit for HTTP workloads. Render runs your app, fronts it with its own TLS-terminating load balancer, and gives you a `<name>.onrender.com` URL. Key characteristics:

- **Custom domains**: point your DNS CNAME at Render's load balancer; TLS is provisioned automatically via Let's Encrypt, renewed automatically.
- **Autoscaling** (Standard plan and above): configure `minInstances` and `maxInstances`; scale-out triggers on CPU or memory utilization. Scale-in is conservative (avoids flapping). Free and Starter plans are single-instance only.
- **Zero-downtime deploys**: new instance starts, passes health checks, then receives traffic; old instance drained. Health check URL and timeout are configurable — always set them explicitly.
- **Health checks**: define `healthCheckPath` (e.g. `/health`). Render will not cut traffic to a new instance until this path returns 2xx. A missing or slow health check endpoint means every deploy risks dropped traffic.
- **Pull Request Previews**: with the `previews:` block in `render.yaml`, each PR gets its own ephemeral environment. PRs build against your Blueprint configuration.

### Private Service

Same as Web Service minus the public internet exposure. Accessible only to other services in the same Render team and region via `http://<service-name>:<port>`. Use this for any service that should not be reachable from outside your team's environment — internal APIs, gRPC backends, admin services.

- No public URL, no public DNS entry.
- Traffic stays on Render's internal network — lower latency, no egress billing for intra-team calls.
- Still gets health checks and zero-downtime deploys.

### Background Worker

A process that runs continuously without an HTTP listener. Common uses: queue consumers (Sidekiq, Celery, BullMQ), data pipelines, WebSocket event processors.

- No inbound traffic; no health check URL.
- Render monitors process exit — restarts automatically on crash.
- Shares the same plan tiers as Web Services.
- Single-instance only on free / Starter. For parallelism across multiple workers, use multiple service instances or horizontal replicas (Standard+).

### Cron Job

Runs a command on a schedule (cron expression). Render starts a container, runs the command, then shuts it down.

- Charged per second of runtime, not by idle time.
- Billed at the plan tier's per-instance price for the duration of the run.
- Not suitable for long-running work — consider a Background Worker that reads from a scheduler queue instead if jobs run > 10 minutes regularly.

### Static Site

Deploys a built artifact (HTML/CSS/JS) to Render's CDN. Build command runs once; output directory is served globally.

- Free, no plan required.
- Not suitable for SSR, API routes, or any server-side logic — use a Web Service instead (or a hybrid framework that pre-renders).
- Built on every push to the configured branch.

## Runtime: docker vs image-based deploy

| Mode | How it works | When to use |
| --- | --- | --- |
| `runtime: docker` | Render builds your Dockerfile at deploy time | Team controls the Dockerfile; builds are simple enough to run on Render's build machines |
| Registry image | Point Render at `image.url:tag` in `render.yaml` or the dashboard | Complex builds (cross-compile, multi-platform), external CI already builds the image, strict supply-chain control |

For image-based deploys, use an immutable image tag (git SHA or semver) — never `latest`. Render will not re-pull `:latest` unless you trigger a new deploy, and it's impossible to know what's running.

## Service plans

| Plan | Instances | Autoscale | CPU | Memory | Use for |
| --- | --- | --- | --- | --- | --- |
| Free | 1 | No | Shared | 512 MB | Hobby / proof-of-concept |
| Starter | 1 | No | 0.5 CPU | 512 MB | Low-traffic production |
| Standard | 1–N | Yes | 1 CPU | 2 GB | General production |
| Pro | 1–N | Yes | 2 CPU | 4 GB | Higher-throughput services |
| Pro Plus | 1–N | Yes | 4 CPU | 8 GB | CPU / memory-intensive services |
| Pro Max | 1–N | Yes | 8 CPU | 16 GB | Large monoliths, ML inference |

**Free tier sleep semantics**: Free Web Services spin down after 15 minutes without traffic. The next request wakes the instance; cold start typically takes 30–60 seconds. This is unsuitable for any production surface where availability matters. Move to Starter ($7/mo as of 2026-05) to eliminate sleep.

## Defaults

- Set `healthCheckPath` on every Web Service — never leave it unset.
- Set `autoscaling.minInstances >= 1` on Standard+ plans to avoid scale-to-zero.
- Use `buildCommand` and `startCommand` explicitly rather than relying on Render's runtime detection — detection can surprise you after a dependency change.
- Pin `dockerfilePath` if your Dockerfile is not at the repo root.
- Set `numInstances` or autoscaling bounds in `render.yaml` (Blueprint), not via the dashboard, so deploys don't reset them.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Free plan for a production Web Service | Service sleeps after inactivity; 30–60s cold starts hit your users. Upgrade to Starter+. |
| Missing `healthCheckPath` | Render routes traffic to the new instance before it is ready; requests fail during every deploy. |
| Using a Web Service for an internal API | Internal API is publicly accessible; you're paying for public ingress you don't need. Use Private Service. |
| `:latest` image tag on an image-based deploy | No audit trail; impossible to roll back a known-good image. Pin to a git SHA. |
| Long-running jobs in a Cron Job | Jobs that run > 10 min are prone to timeout and double-execution on retries. Use a queue + Background Worker. |
| Storing secrets in `render.yaml` plaintext `value:` | Secrets end up in source control. Use `fromGroup:` (Environment Group) or `secretFiles:`. |
| Single Background Worker instance for queue consumers | One crash = zero throughput. Use replicas (Standard+) or multiple worker services for redundancy. |

## Security defaults

- Web Services: TLS is automatic on all `onrender.com` and custom domains — HTTP is redirected to HTTPS. No opt-out is needed.
- Secrets via Environment Groups (`fromGroup:`) or `secretFiles:` — never `value: "my-secret"` in `render.yaml`.
- Internal APIs and admin surfaces: Private Services, not Web Services.
- For additional access restriction, IP allowlists are available on Pro and above plans.

## Observability defaults

- Render provides per-service CPU, memory, request rate, and response time metrics in the dashboard.
- Enable log streaming to Datadog, New Relic, or Logtail for searchable, retained logs beyond Render's rolling window.
- Monitor service health with an external uptime check (e.g., BetterUptime, Checkly) — Render's internal health checks are for deploy gates, not ongoing monitoring.

## Cost considerations

- Standard plan charges per-instance-hour; autoscaling can increase your bill if you don't set `maxInstances`.
- Background Workers on free tier will be killed (not just slept); for any persistent consumer, use Starter or above.
- Cron Jobs are charged for actual runtime — an hourly cron that takes 10 minutes is cheaper than a Background Worker that polls.
- Review plan utilization monthly; CPU-constrained services (< 10% idle CPU) should upgrade; memory-constrained services should first check for leaks before upgrading.

## IaC hints

- Declare every service in `render.yaml` — the Blueprint is the source of truth.
- `autoscaling:` block in the service stanza controls min/max/target.
- `healthCheckPath:` lives directly under the service definition, not in `envVars`.
- Use `branch:` per environment when running multiple environments from the same repo.

## Verification checklist

- [ ] Service type justified against the decision tree (not "Web Service by default" for an internal process).
- [ ] `healthCheckPath` set and endpoint returns 2xx within `healthCheckTimeout` seconds.
- [ ] Free tier eliminated for any production surface.
- [ ] Autoscaling bounds set in Blueprint; `maxInstances` is explicit.
- [ ] No secrets in `render.yaml` plaintext `value:` fields.
- [ ] Image-based deploys use pinned tags, not `:latest`.
- [ ] Internal services are Private Services, not public Web Services.
- [ ] At least one external uptime monitor on every user-facing Web Service.
