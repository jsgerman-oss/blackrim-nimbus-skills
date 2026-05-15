---
name: fly-machines-and-apps
description: Design, size, or operate Fly Machines and Apps — Firecracker VMs, auto-start/stop, scale-to-zero, machine sizes, placement across regions, rolling vs immediate deploys, releases, fly-replay routing. Use when picking a machine size, configuring multi-region, reviewing a deployment strategy, or auditing scale-to-zero correctness.
---

# Fly Machines and Apps

## When to use

- Choosing a machine size for a new workload (CPU, memory, GPU).
- Configuring auto-start / auto-stop for scale-to-zero behavior.
- Designing a multi-region placement strategy with latency budgets.
- Reviewing or writing a `fly.toml` services block.
- Deciding between immediate, rolling, blue-green, or canary deploys.
- Debugging a release or rollback failure.
- Using `fly-replay` to route requests to a specific region or machine.

## Core concepts

### Machines — the primary primitive

A **Fly Machine** is a Firecracker microVM. It is the unit of compute on Fly. Unlike container schedulers, Fly runs one Machine per Firecracker VM — there is no pod / task abstraction layered on top. Machines start in milliseconds (not seconds), and Fly bills by the millisecond of runtime.

A **Fly App** is a logical grouping of Machines that share a name, network identity, and `fly.toml` configuration. An App can contain Machines of different sizes in different regions — they share nothing except the App namespace and the private 6PN network.

### Auto-start / auto-stop (scale-to-zero)

`auto_stop_machines = "stop"` halts a Machine when it has no active connections. `auto_start_machines = true` starts it when an incoming request arrives. The Fly Proxy holds the inbound connection while the Machine boots (typically 300–800 ms for a pre-built image). Design accordingly:

- **Idempotent request handling is mandatory.** The proxy may route a request to a machine mid-boot; ensure your startup path completes before accepting traffic.
- **Health checks gate readiness.** Define `[[services.http_checks]]` or TCP checks so Fly Proxy only routes after the Machine is truly ready.
- **Cold-start budget.** For user-facing latency budgets under 1 s, test cold-start with a real image, not `docker pull` time. Images pre-pulled from Fly's depot (layer caching) start faster.
- **`min_machines_running`.** Set to 1 if you cannot tolerate cold starts. The cost of one stopped machine is zero; the cost of one `min_machines_running = 1` machine is the per-hour rate.

`auto_stop_machines = "suspend"` preserves machine memory at a small charge — useful when re-initialization is expensive but cost matters.

## Machine sizes

Fly offers three families. Pick the smallest that meets your p95 CPU and RSS benchmarks under load.

### Shared CPU (`shared-cpu-Nx`)

| Size | vCPU | RAM |
| --- | --- | --- |
| `shared-cpu-1x` | 1 shared | 256 MB |
| `shared-cpu-2x` | 2 shared | 512 MB |
| `shared-cpu-4x` | 4 shared | 1 GB |
| `shared-cpu-8x` | 8 shared | 2 GB |

"Shared" means vCPU time is burst-based. Best for: web apps with spare capacity, background workers, APIs with moderate throughput.

### Performance CPU (`performance-Nx`)

Dedicated vCPU. No noisy-neighbor burst ceiling.

| Size | vCPU | RAM |
| --- | --- | --- |
| `performance-1x` | 1 dedicated | 2 GB |
| `performance-2x` | 2 dedicated | 4 GB |
| `performance-4x` | 4 dedicated | 8 GB |
| `performance-8x` | 8 dedicated | 16 GB |
| `performance-16x` | 16 dedicated | 32 GB |

Best for: databases, compute-intensive workloads, LLM inference sidecar.

### GPU machines

`a10g`, `l40s`, `a100-80gb` sizes for ML inference, rendering, video encoding. GPU machines run in specific regions — verify availability before designing around one. GPU machines do not scale to zero; plan for idle charges.

### Memory overrides

RAM is configurable independently of the CPU class in most sizes via `fly machine update --vm-memory`. Over-provisioning RAM is often cheaper than the next CPU tier.

## Region placement

Fly operates 30+ regions. Placement decisions:

1. **Pick primary regions near your users.** `flyctl regions list` shows available regions with current availability. Use latency tools (`fly ping`, browser-level timing) to validate.
2. **Replicate for availability, not just latency.** Two machines in two regions costs more; one machine per region with `min_machines_running = 1` is the minimum HA posture.
3. **Data locality.** If you have a Fly Volume or Fly Postgres in `iad`, route writes there. `fly-replay` lets the app instruct the proxy to replay a request at a specific region: `fly-replay: region=iad`.
4. **`auto_start_machines` across regions.** Each region can have stopped machines that auto-start on traffic — global coverage with zero idle cost where load is absent.

## Deployments

### Deploy strategies

| Strategy | `fly.toml` / CLI | Behavior |
| --- | --- | --- |
| `immediate` | `strategy = "immediate"` | Replace all machines simultaneously. Zero old machines remain. Fastest; causes brief downtime if health checks fail. |
| `rolling` | `strategy = "rolling"` | Replace machines one at a time. Default. Safe for stateless services. |
| `bluegreen` | `strategy = "bluegreen"` | Start a complete new set of machines, shift traffic, then stop the old set. Zero-downtime, higher peak cost. |
| `canary` | `strategy = "canary"` | Deploy to one machine first; on health check pass, roll out the rest. Good for catching startup regressions. |

Default for `fly deploy` is `rolling`. Set via `[deploy] strategy = "bluegreen"` in `fly.toml` or `--strategy` flag.

### Releases and rollback

Every `fly deploy` creates a release. List with `fly releases`. Roll back with `fly deploy --image <image-ref>` or `fly releases rollback <version>`. Releases are numbered sequentially per app. Always pin images by digest (`registry.fly.io/myapp:sha-abc123`) in production, never `:latest`.

### `fly-replay` header

Your app can set a `fly-replay: region=iad` response header to instruct the Fly Proxy to replay the request at the `iad` region (or a specific Machine with `instance=<id>`). Use this for:

- Write routing to a primary-region Postgres.
- Stickiness for stateful WebSocket connections.
- Forcing a specific machine for debugging.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| `min_machines_running = 0` with no cold-start budget | User-visible latency spikes on first hit after idle. Set budget or keep 1 warm. |
| Deploying with `strategy = "immediate"` for stateful services | All machines restart simultaneously; brief total unavailability if new image takes time to become healthy. |
| Image tagged `:latest` in production | Rollback is archaeology. Tag with git SHA. |
| GPU machine left running idle | No scale-to-zero for GPU; idle costs accumulate. Set up explicit `fly machine stop` in CI or use on-demand launch scripts. |
| One machine, one region for a production service | Single point of failure. Use at least two regions with `min_machines_running = 1` each. |
| Over-allocating CPU for a memory-bound workload | `shared-cpu-1x` with extra memory is cheaper than `performance-1x` if the workload is I/O-bound. Benchmark before picking. |
| Not configuring health checks | Fly Proxy routes to machines that haven't completed initialization. Define HTTP or TCP checks with appropriate `interval` and `timeout`. |

## Security defaults

- Run containers as non-root. `USER 1000` in Dockerfile; Fly does not strip root but it's your layer.
- Do not bake secrets into Docker images — use `fly secrets` (injected as env at runtime).
- Internal-only services: no `[[services]]` block and no public IP. Use Flycast + 6PN for service-to-service calls.
- Limit `fly ssh` access. `fly ssh` gives shell access to live machines — restrict who holds org-level tokens.

## Observability defaults

- Wire the `/healthz` or equivalent to your `[[services.http_checks]]`. Fly Proxy reports machine health; Grafana dashboards reflect it.
- Emit structured logs to stdout/stderr — they appear in `fly logs` and can be shipped to external NATS or syslog targets.
- Machine restart counts are available in Fly metrics — alarm on high restart rates, which signal crash loops.

## Cost considerations

- Machine billing is per-second of runtime (rounded to nearest second), not per-hour reservation.
- A stopped machine (`auto_stop_machines = "stop"`) costs nothing until the next start.
- Volume storage (GB-month) and snapshots accrue continuously regardless of machine state.
- Anycast network egress has per-region pricing — egress from `ams` differs from `iad`. Check Fly pricing page for current rates.
- To estimate costs: `machine_hours * machine_hourly_rate + volume_gb * volume_gb_rate + egress_gb * egress_rate`.

## IaC hints

- `fly.toml` is the primary configuration surface. Version-control it; do not edit via console.
- Pulumi `flyio/fly` provider (community) supports Apps, Machines, Volumes, Postgres — verify provider version against current Fly API.
- `flyctl` has a `--json` flag on most commands for scripted automation.
- Machine API (`https://api.machines.dev`) supports direct REST calls for advanced orchestration (e.g., ephemeral machines, on-demand launch).

## Verification checklist

Before declaring a Machines / Apps design complete:

- [ ] Machine size justified against CPU and memory benchmarks, not guessed.
- [ ] `auto_stop_machines` setting matches the workload's cold-start tolerance.
- [ ] Health checks defined with appropriate timeout and interval.
- [ ] Deploy strategy matches the workload's state and downtime budget.
- [ ] Multi-region placement designed with data locality in mind (`fly-replay` for write routing if applicable).
- [ ] Images tagged by git SHA, not `:latest`.
- [ ] At least one region has `min_machines_running = 1` for any user-facing service.
- [ ] Rollback procedure verified: `fly releases rollback` tested at least once.
