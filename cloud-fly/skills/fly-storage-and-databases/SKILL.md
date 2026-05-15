---
name: fly-storage-and-databases
description: Design or audit storage and databases on Fly.io — Fly Volumes (AZ-local block storage), Fly Postgres (self-managed on Machines), Fly Redis (Upstash-backed), Tigris (S3-compatible object storage), LiteFS (SQLite replication). Use when choosing a data store, modeling replication, configuring backups, or planning a restore drill.
---

# Fly Storage and Databases

## When to use

- Choosing between Fly Volumes, Fly Postgres, Redis, Tigris, or LiteFS for a new workload.
- Designing data replication for a stateful service that spans regions.
- Configuring snapshot schedules and backup-restore drills.
- Auditing data availability posture for a Fly-hosted production service.
- Migrating from a managed database (RDS, Cloud SQL) to Fly Postgres.

## Fundamental constraint: volumes are AZ-local

This is the most important fact in Fly storage design. **A Fly Volume is attached to exactly one machine in exactly one region.** It does not replicate automatically. It does not fail over automatically. If the machine or the host node fails, data on the volume is inaccessible until Fly restores the node.

Implication: every stateful workload on Fly must implement replication at the application layer, or accept the single-point-of-failure risk explicitly. There is no equivalent of an EBS Multi-Attach or an RDS Multi-AZ standby that switches transparently on failure.

## Decision tree

| Need | Solution |
| --- | --- |
| Relational OLTP, PostgreSQL-compatible | Fly Postgres (managed-by-you — see below) |
| Low-latency key-value or pub/sub | Fly Redis (Upstash, fully managed, consumption-billed) |
| S3-compatible object storage | Tigris (Fly-native, globally available, S3 API) |
| SQLite for edge-local reads / global replication | LiteFS |
| Local block storage for a stateful service | Fly Volumes (AZ-local; application replication required) |
| External managed DB (PlanetScale, Neon, Supabase) | Wire over private 6PN or internet; no volume needed |

## Fly Postgres — managed-by-you

**Critical distinction:** Fly Postgres is **not** a managed database equivalent to RDS or Cloud SQL. Fly provides the tooling (`fly postgres create`, `fly postgres connect`, HA cluster with replication) but you own:

- **Major version upgrades** — run `fly postgres update` yourself; breaking changes are yours to manage.
- **Failover configuration** — Fly Postgres uses `repmgr` / `patroni`-style HA. In a multi-node cluster, a standby can promote, but you must configure the cluster correctly. Single-node Fly Postgres has no automatic failover.
- **Backup schedule and retention** — Fly takes daily snapshots of Postgres volumes. For PITR, run `pgBackRest` or `wal-g` yourself with a Tigris (or external S3) backend.
- **Connection pooling** — Add PgBouncer as a sidecar or a separate Fly Machine. Fly Postgres does not include a built-in pooler.
- **Extensions** — Install Postgres extensions yourself in the Dockerfile or via `fly postgres shell`.

### Fly Postgres HA configuration

A production Fly Postgres cluster should have:

1. **Primary machine** with a Fly Volume.
2. **At least one replica** in a different region, streaming WAL from the primary.
3. **`fly-replay` for write routing** — your application (or PgBouncer) detects that it is on a replica and emits `fly-replay: region=<primary-region>` to route writes correctly. The Fly PostgreSQL proxy handles this for `fly postgres connect`; your app must implement it for direct connections.

Single-node Fly Postgres is acceptable for dev / staging but is a SPOF for production.

### Postgres defaults

- Enable SSL for all connections (`sslmode=require` or `verify-full`).
- Set `log_min_duration_statement = 200` (ms) to catch slow queries.
- Run `pg_stat_statements` for query performance monitoring.
- Schedule full backups to Tigris nightly. Test restores quarterly.
- Use dedicated app-specific Postgres users with schema-scoped privileges — not the default `postgres` superuser.
- Connection string: store in `fly secrets` — never baked into the image or fly.toml.

## Fly Volumes

Volumes are Fly's block-storage primitive. They are attached to a single machine in a single region.

### Volume defaults

- Create with `fly volumes create <name> --size <gb> --region <region>`.
- Mount in `fly.toml` under `[mounts]`.
- Snapshots: Fly takes automatic daily snapshots. For more frequent snapshots, write a cron job inside the machine or use `fly volumes snapshots create` via API.
- Resize with `fly volumes extend` (grow only; shrink is not supported).
- For replication across regions: use LiteFS (SQLite), Postgres streaming replication, or application-level replication. Do not rely on Fly to replicate volumes.

### Volume sizing

- Start with the minimum needed + 50% headroom.
- Volumes have no burst I/O; provision actual expected IOPS workload.
- Volume data persists across machine restarts and deploys. Volume is tied to the machine, not the release.

## Fly Redis (Upstash)

Fly Redis is powered by Upstash, a serverless Redis service. It is **fully managed** — no machines to run, no volumes to maintain. Create with `fly redis create`.

### Redis defaults

- Use for caching, sessions, rate limiting, pub/sub, job queues.
- TLS is on by default (Upstash enforces it).
- Persistence: Upstash offers AOF persistence (optional). For critical data, enable it; for pure cache, disable to reduce latency.
- Multiple databases per cluster via index (e.g., `redis://...?db=1`).
- Not a Volumes-based service — it is independently available; machine restarts do not affect it.
- Cost: consumption-billed (commands + bandwidth), no idle charge.

## Tigris — S3-compatible object storage

Tigris is Fly's globally distributed, S3-compatible object storage service. It is the recommended blob store for Fly-hosted applications.

### Tigris defaults

- Create a bucket: `fly storage create`. Access via standard `aws s3` CLI or any S3-compatible SDK by setting `endpoint_url`.
- Globally available: reads are served from the nearest Tigris edge; writes propagate globally.
- Authentication: Tigris credentials are injected by Fly as `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `BUCKET_NAME`, `AWS_ENDPOINT_URL_S3` environment variables when you attach the bucket to an app via `fly storage create --app`.
- Versioning: enable for any bucket holding state or user uploads (`aws s3api put-bucket-versioning`).
- Lifecycle: configure expiration for temporary uploads, log archives.
- Public access: Tigris supports public buckets for serving static assets. Use sparingly; default to private + presigned URLs.
- Not a CDN replacement — for high-volume asset serving, put a CDN in front.

### S3 SDK configuration for Tigris

```python
import boto3
import os

s3 = boto3.client(
    "s3",
    endpoint_url=os.environ["AWS_ENDPOINT_URL_S3"],
    aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
    region_name="auto",
)
```

## LiteFS — SQLite replication

LiteFS is an open-source FUSE filesystem that replicates SQLite databases across machines using a write-ahead log. It is the recommended approach for edge-local SQLite with global consistency.

### LiteFS architecture

- **Primary node:** the one machine designated as primary; all writes go here.
- **Replica nodes:** read from the LiteFS replica stream; reads are served locally (low latency); writes are forwarded to primary or rejected (depending on config).
- `fly-replay` integration: configure LiteFS to emit `fly-replay: region=<primary-region>` when a write hits a replica, so Fly Proxy reroutes to primary.

### LiteFS defaults

- Run LiteFS as a process in your machine's `CMD` via `litefs mount` wrapping your application.
- Configure primary election via Consul on Fly (LiteFS supports Consul and etcd for primary lease).
- Store WAL segments on Tigris for disaster recovery (`litefs export` for snapshots).
- Test failover: stop the primary machine and confirm a replica promotes cleanly.
- Not a replacement for Postgres — SQLite-on-LiteFS is best for read-heavy, edge-local workloads with occasional writes.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Single-node Fly Postgres in production | One machine or node failure = database down, no automatic failover. |
| Relying on Fly volume HA | Volumes do not replicate. The volume's machine is a SPOF. |
| Fly Postgres superuser connection string in app env | App bug = DROP TABLE risk. Use a restricted schema-scoped user. |
| No Postgres backup other than Fly daily snapshots | Daily snapshots give rough PITR; you need WAL archiving for precise PITR. |
| Tigris public bucket for sensitive uploads | One misconfigured ACL = public data. Default private; presigned URLs for access. |
| LiteFS without Consul / primary lease | Split-brain: two replicas both think they are primary. |
| Over-provisioning volumes without monitoring fill | Volume fills silently; machine crashes. Monitor disk-free in Fly metrics. |
| Skipping restore drills | An untested backup is a false sense of security. Drill quarterly. |

## Security defaults

- All database connections (Postgres, Redis) over TLS.
- Postgres connection string in `fly secrets` — never in `fly.toml` plaintext.
- Restrict Fly Postgres to the 6PN private network — no public IP on the Postgres app unless you have a specific reason.
- Tigris: use IAM-scoped credentials injected by Fly; do not store Tigris credentials in source code.
- Volume snapshots are encrypted at rest by Fly.

## Observability defaults

- Monitor Postgres: `pg_stat_activity` (active connections), replication lag on standbys, `pg_stat_bgwriter` (I/O pressure), long-running transactions.
- Volume fill: emit disk-free metric from inside the machine to Fly's metrics endpoint or an external exporter.
- LiteFS: monitor replication lag from primary to replicas; alert when lag exceeds your RPO.
- Tigris: enable server-side access logs; ship to an external SIEM for compliance.

## Cost considerations

- Fly Volumes: billed by GB-month provisioned, regardless of fill. Do not over-provision; resize up when needed.
- Fly Postgres: each Postgres machine is a standard Fly Machine — billed by the second of runtime plus the volumes attached.
- Fly Redis (Upstash): consumption-billed (commands + bandwidth). Cheap for low traffic; can be significant for high-frequency cache patterns. Set maxmemory-policy appropriately to bound size.
- Tigris: billed by GB stored, operations, and egress. Read-heavy object serving stays cheap; large egress from outside Fly incurs transfer fees.
- Volume snapshots: stored in Fly's blob store; small cost per snapshot retained.

## IaC hints

- `fly.toml` `[mounts]` block defines volume attachment for the app.
- Fly Postgres created via `fly postgres create --name <name> --region <region> --vm-size <size> --volume-size <gb>`.
- Tigris created via `fly storage create --name <name> --app <app>`.
- Pulumi `flyio/fly` provider supports Volume resources; Postgres and Tigris resources may require `fly` CLI wrappers in provisioning scripts.

## Verification checklist

- [ ] Each stateful service has an explicit replication plan — not relying on volume HA.
- [ ] Fly Postgres has at least one replica in a different region for production.
- [ ] Postgres connection uses a least-privilege app user, not superuser.
- [ ] Backup schedule confirmed (WAL archiving or daily snapshots); restore drill date set.
- [ ] Tigris bucket versioning on for any bucket holding user data or state.
- [ ] LiteFS primary lease via Consul configured; split-brain scenario tested.
- [ ] All database credentials in `fly secrets`.
- [ ] Volume fill monitoring wired to an alert.
- [ ] Restore drill completed successfully for every database in production.
