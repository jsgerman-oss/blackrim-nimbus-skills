---
name: render-storage-and-databases
description: Design or audit Render storage and database tiers — Managed Postgres (HA + replicas + PITR), Managed Redis (Valkey), Persistent Disks (single-AZ). Use when choosing a data store, sizing a database, configuring backups, planning recovery drills, or understanding the single-AZ limitation of Persistent Disks.
---

# Render Storage and Databases

## When to use

- Choosing between Managed Postgres, Managed Redis, and Persistent Disks for a workload.
- Sizing a Managed Postgres instance and configuring HA and replicas.
- Planning a backup and recovery strategy on Render.
- Understanding the single-AZ constraint of Persistent Disks and its availability implications.
- Designing a disaster recovery drill for managed databases.

## Decision tree

| Need | Use |
| --- | --- |
| Relational ACID data, SQL, OLTP | Managed Postgres |
| Session cache, rate limiting, pub/sub, short-lived KV | Managed Redis (Valkey) |
| App-local filesystem state (uploads, SQLite, flat files) persisted across restarts | Persistent Disk (understand the single-AZ caveat) |
| Object storage for blobs, user uploads at scale | External provider (S3, R2, GCS) — Render has no managed object store |
| Analytics / OLAP / large aggregations | External provider (Snowflake, BigQuery, Redshift) — Render Postgres is not a data warehouse |

## Managed Postgres

Render's Managed Postgres is a fully hosted PostgreSQL service available in the same regions as your compute services.

### Plans and sizing

| Plan | vCPU | RAM | Storage | HA | Read Replicas |
| --- | --- | --- | --- | --- | --- |
| Free | Shared | 256 MB | 1 GB | No | No |
| Starter | 1 | 1 GB | 10 GB | No | No |
| Standard | 2 | 4 GB | 50 GB | Yes | Yes (up to 5) |
| Pro | 4 | 8 GB | 100 GB | Yes | Yes |
| Pro Plus | 8 | 16 GB | 200 GB | Yes | Yes |
| Pro Max | 16 | 32 GB | 500 GB | Yes | Yes |

**Free tier**: database is suspended after 90 days of no activity and permanently deleted after 90 days suspended. Never use free Postgres for production data.

### High availability

HA (Standard plan and above) means Render runs a primary instance plus a hot standby in the same region. Failover is automatic; your connection string does not change. Expect a brief interruption (typically < 30 seconds) during failover — clients should have retry logic with exponential backoff.

**Important**: HA is within a single region. It is not cross-region. If the Render region has an outage, HA does not help. For multi-region resilience, you must replicate to an external provider or accept the region as a single point of failure.

### Read replicas

Read replicas are synchronous streaming replicas of the primary. Connection strings for replicas are separate from the primary. Common pattern: write to primary connection string, read from replica connection string for analytics / reporting queries.

### Backups and PITR

- Automatic daily snapshots are included on all plans.
- **PITR** (Point-in-Time Recovery) is available on Standard plan and above. Retention window: 7 days.
- Snapshots are stored in Render's managed storage; you cannot access them directly.
- To validate backups, use Render's restore flow to spin up a new database from a snapshot — do this on a schedule (quarterly minimum for production).

### Connection discipline

- Use connection pooling (PgBouncer or application-level pooling, e.g., `pgpool`, SQLAlchemy's pool) to avoid exhausting Postgres connection limits.
- The internal connection string (from the same Render team/region) keeps traffic off the public internet. Always prefer `Internal Database URL` over `External Database URL` for application connections.
- Enable SSL (`sslmode=require`) on the external connection string — Render enforces TLS on external connections; the internal path is already encrypted.
- Rotate the database password by creating a new user; never embed the connection string in source control.

## Managed Redis (Valkey)

Render's Managed Redis runs Valkey (the open-source Redis fork). It is suitable for caching, session storage, rate limiting, and pub/sub.

### Key characteristics

- Single instance (no clustering) on all plan tiers as of 2026-05.
- Memory-only; persistence (AOF / RDB) available on paid plans.
- Accessible internally from the same Render team/region via the internal URL.
- TLS on the external connection string; internal connections are on the trusted Render network.

### Defaults

- Use the internal Redis URL for all application connections within the same Render team — keeps traffic private and avoids external TLS overhead.
- Enable persistence (RDB snapshots) if Redis holds data that would be expensive to regenerate on restart.
- Set `maxmemory-policy` explicitly: `allkeys-lru` for a pure cache, `noeviction` if Redis holds critical session state where loss = correctness bug.
- Size the plan so that your working set fits comfortably in memory with 30% headroom; evictions indicate the plan is too small.

## Persistent Disks

Persistent Disks attach a persistent filesystem volume to a Web Service or Background Worker. The disk survives restarts and deploys.

### Critical caveat: single-AZ

**Persistent Disks are single-AZ.** The disk is attached to one instance in one availability zone. This has two important implications:

1. **Services with a Persistent Disk cannot autoscale horizontally.** A single disk can only be mounted by one instance at a time. If you need multiple replicas, you cannot use a Persistent Disk.
2. **There is no automatic failover for the disk.** If the AZ has an outage, your service and its disk are both affected until the AZ recovers. This is a meaningful availability risk for any stateful workload.

### When Persistent Disks are appropriate

- Storing SQLite databases for workloads where single-instance is acceptable (e.g., internal tools, low-traffic apps).
- Storing uploaded files for a single-instance service before migrating to object storage.
- Caching large build artifacts that are expensive to regenerate.

### When NOT to use Persistent Disks

- Any workload that needs horizontal scaling (multiple replicas).
- Any stateful workload where availability is a hard requirement — the single-AZ risk is real.
- User-uploaded media at scale — use S3-compatible object storage (R2, S3, GCS) instead.

### Mount point and size

Configure the mount path and size in `render.yaml` or the dashboard. The disk is formatted on first attach; resizing requires a new disk creation and data migration (there is no live resize).

## Backups — the real posture

Render's managed database backups cover the managed Postgres service. Persistent Disks are NOT automatically backed up — any backup strategy for disk-attached data is your responsibility (application-level export, rsync off-disk via a Background Worker, etc.).

| Store | Automatic backup | PITR | Controlled by |
| --- | --- | --- | --- |
| Managed Postgres (Standard+) | Yes (daily) | Yes (7d) | Render |
| Managed Postgres (Starter) | Yes (daily) | No | Render |
| Managed Redis | RDB snapshots (paid) | No | Render |
| Persistent Disk | No | No | You |

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Free Postgres for production | Suspended after 90 days inactivity, then deleted. Use Starter or above. |
| External database URL for app connections | Traffic goes over the public internet; slower and higher egress cost. Use internal URL. |
| No connection pooling on Postgres | Connection limits exhausted under load; Postgres OOM-kills connections. Add PgBouncer or app-level pooling. |
| Persistent Disk on an autoscaled service | A second replica cannot mount the disk; deploy fails. Use object storage for shared state. |
| No PITR on production Postgres | Daily snapshot granularity means you can lose up to 24h of data. Standard plan for PITR. |
| Redis with `noeviction` and no size headroom | Redis hits the memory limit and starts returning errors, taking the app down. Monitor working set size. |
| Connection string in `render.yaml` plaintext | Credential in source control; anyone with repo read access has database access. Use Environment Groups. |
| Untested Postgres restore | Backup that has never been tested is a hypothesis, not a recovery plan. Run quarterly restore drills. |

## Security defaults

- Use internal connection strings for all intra-team service connections.
- Store connection strings in an Environment Group or Secret File — never inline in `render.yaml` or application code.
- Enable SSL on any external connection (`sslmode=require` for Postgres).
- Rotate database credentials on a schedule or after any team member departure.
- Do not share database access across environments (dev / staging / prod use separate databases).

## Observability defaults

- Monitor Postgres: CPU utilization, active connections, disk I/O, replication lag (for read replicas) via Render's built-in metrics.
- Monitor Redis: memory utilization, eviction rate, connected clients — high evictions signal undersized plan.
- Set up an external alert (via a Datadog integration, Logtail, or external monitoring) for high CPU or connection exhaustion on the database.
- Run a weekly `pg_stat_statements` query to surface slow queries; tune or add indexes proactively.

## Cost considerations

- Managed Postgres and Redis charge a flat monthly rate per plan, plus overage for storage above the plan limit.
- Persistent Disks charge per GB per month (approximately $0.25/GB/month as of 2026-05).
- Read replicas add the cost of an additional database instance at the same plan tier.
- HA doubles the compute cost of the primary (primary + standby). This is almost always worth it for production.
- External database URLs generate standard data egress charges; internal URLs do not.

## IaC hints

- Declare Postgres and Redis in the `databases:` stanza of `render.yaml`.
- Reference the database URL in services via `fromDatabase:` to avoid hardcoding connection strings.
- Persistent Disks are declared in the service's `disk:` block with `mountPath` and `sizeGB`.
- PITR is enabled by plan tier, not a configuration flag — choose Standard or above in `plan:`.

## Verification checklist

- [ ] Production Postgres is on Standard or above (HA + PITR enabled).
- [ ] Connection strings delivered via Environment Group or Secret File, not plaintext.
- [ ] Internal database URL used for application connections.
- [ ] Connection pooling configured; connection limit not exceeded under expected peak load.
- [ ] Postgres restore drill completed and documented (quarterly minimum).
- [ ] Redis memory headroom >= 30%; eviction policy explicitly set.
- [ ] Persistent Disks not attached to services that need horizontal scaling.
- [ ] Backup strategy for any Persistent Disk data is documented (Render does not back these up).
- [ ] Separate databases for dev, staging, and production.
