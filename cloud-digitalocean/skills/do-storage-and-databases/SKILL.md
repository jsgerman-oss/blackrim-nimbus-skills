---
name: do-storage-and-databases
description: Design or audit DigitalOcean storage and database tiers — Spaces (S3-compatible object storage), Volumes (block storage), Managed Databases (Postgres, MySQL, MongoDB, Redis, Kafka, OpenSearch), and Backups. Use when picking a data store, modeling access patterns, sizing, securing, or backing up data.
---

# DigitalOcean Storage and Databases

## When to use

- Choosing between object storage, block volumes, and a managed database engine.
- Sizing a Managed Database cluster and selecting a standby / high-availability plan.
- Hardening data-at-rest encryption, backups, and connection security.
- Auditing data egress, retention, snapshot lifecycle, and replication.
- Evaluating the tradeoff between a Managed Database and self-hosting on a Droplet.

## Decision tree

| Need | Service |
| --- | --- |
| Object storage for blobs, backups, static assets, data lake | Spaces |
| Block storage attached to a Droplet or DOKS node | Volumes |
| ACID relational, OLTP, joins, JSONB | Managed PostgreSQL |
| MySQL-compatible relational | Managed MySQL |
| Document store, flexible schema, horizontal scale | Managed MongoDB |
| Sub-ms key-value cache, pub/sub, session store | Managed Redis / Valkey |
| Event streaming, message queue | Managed Kafka |
| Full-text search, log analysis | Managed OpenSearch |
| Self-hosted, heavy customization, license control | Droplet (Memory-Optimized or Storage-Optimized) + manual ops |

## Spaces defaults

- **Bucket policy:** default to private. No public ACL unless the bucket exclusively serves public static assets. Use Spaces CDN + signed URLs for asset delivery rather than a public bucket.
- **Encryption:** Spaces encrypts data at rest with AES-256. There is no customer-managed key option as of 2026 — if key-level audit / revocation is required, encrypt objects client-side before upload.
- **Versioning:** enable on any bucket holding state, artifacts, or backups. Versioning is per-object and protects against accidental deletes.
- **Lifecycle rules:** expire non-current object versions after your retention window (e.g. 30 d for build artifacts, 90 d for application backups). Unmanaged non-current versions accumulate and bill silently.
- **CORS:** apply the narrowest CORS policy possible. Avoid `AllowedOrigins: ["*"]` on a bucket that holds anything other than fully public assets.
- **Access control:** use Spaces access keys scoped per application, not personal PAT credentials. Rotate keys on personnel change and on a 90-day schedule.
- **CDN:** enable Spaces CDN for any bucket serving end-user assets. CDN egress is cheaper than origin egress and reduces latency globally.

## Managed Database defaults

### PostgreSQL

- **Plan:** start with the smallest plan that fits the working set; scale vertically via resize — DigitalOcean Managed Postgres supports live resize with brief connection drain.
- **High availability:** enable standby nodes (adds one hot-standby for primary failover) for any production cluster. Failover is automatic, typically under 60 seconds.
- **Backups:** DigitalOcean takes daily backups with 7-day retention on all plans. For regulated data or frequent large transactions, use `pg_dump` to a Spaces bucket on a shorter schedule as a supplement.
- **Connection pooling:** enable PgBouncer via the managed connection pooler. Direct connections to Postgres are limited by `max_connections`; pooling prevents connection exhaustion under load.
- **Private networking:** place the database in a VPC. Use the VPC connection string, not the public connection string, from your application. Disable the public network interface unless you need it for one-off access.
- **SSL enforcement:** all managed databases enforce TLS in transit. The connection string includes `sslmode=require`. Do not downgrade to `sslmode=disable`.
- **Trusted sources:** restrict inbound connections to specific Droplet UUIDs, Kubernetes cluster IDs, or IP addresses via the trusted sources control. An open `0.0.0.0/0` trusted source is a critical exposure.

### MySQL

- Same HA, backup, and private networking defaults as PostgreSQL.
- Enable `require_secure_transport=ON` — it is on by default in managed MySQL, but verify after any config change.
- Connection pooler: use ProxySQL via the managed connection pooler for high-concurrency workloads.

### MongoDB

- Managed MongoDB uses replica sets; the number of nodes is your HA decision. A 3-node replica set is the minimum for automatic failover with a majority quorum.
- **Oplog:** the oplog retention window determines how long a secondary can lag before it must resync. Increase the oplog size if you have write-heavy workloads or expect prolonged secondary lag.
- **Atlas vs Managed MongoDB:** DigitalOcean Managed MongoDB covers standard replica-set use cases. If you need Atlas Search, Atlas Vector Search, or global multi-region write clusters, MongoDB Atlas is the honest recommendation.

### Redis

- **Plan:** Redis is single-threaded on writes; a larger instance means more memory, not more write throughput. Right-size on memory usage, not CPU.
- **Eviction policy:** `allkeys-lru` for general cache, `noeviction` for queues or session stores where silent eviction means data loss.
- **Persistence:** managed Redis on DigitalOcean enables RDB snapshots. AOF is not user-configurable in the managed offering. For workloads where Redis is the system of record (not a cache), evaluate whether the durability model fits.
- **No public interface:** Redis should never be publicly accessible. Use the VPC connection string exclusively.

### Kafka

- Managed Kafka uses a multi-broker cluster. Replication factor of at least 3 for production topics.
- **Topic configuration:** set `retention.ms` and `retention.bytes` explicitly per topic — the default retention is high and will fill disk if left unchecked.
- **TLS and SASL:** enabled by default on Managed Kafka. Use the provided SASL/SCRAM credentials; rotate them on a schedule.
- **Consumer groups:** monitor consumer lag per group. Unbounded lag means a consumer is not keeping up — alarm before the retention window expires and messages are lost.

### OpenSearch

- **Node count:** 3 nodes minimum for production to survive a quorum loss during a rolling upgrade.
- **Shard strategy:** too many shards are as harmful as too few — roughly 20–40 GB per primary shard is a reasonable starting target. Audit with `_cat/shards` before you have a performance problem.
- **Index lifecycle:** apply ISM (Index State Management) policies to roll over and expire old indices. Log indices without expiry fill storage on a predictable schedule.
- **Snapshots:** Managed OpenSearch takes daily automated snapshots to internal storage. For cross-region DR, configure a custom snapshot repository pointing at a Spaces bucket.

## Self-hosting on Droplets — honest tradeoffs

Managed databases carry a markup of roughly 2–3× compared to an equivalent self-hosted Droplet. The tradeoff:

| You get with Managed DB | You give up with Managed DB |
| --- | --- |
| Automated failover | Deep engine config access |
| Automated backups + PITR | Custom extensions (Postgres) |
| Automated minor-version upgrades | Choice of replication topology |
| Managed connection pooler | Cost efficiency at large scale |

Self-host when: you need extensions not available in managed Postgres, require a custom replication topology, or the scale makes the markup material. Self-host only if the team has genuine database operations expertise — failing to automate failover or backups on a self-hosted DB costs more than the managed markup.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Public Spaces bucket for anything non-trivially public | One bucket policy mistake exposes all objects. Default private + CDN. |
| Managed DB with a `0.0.0.0/0` trusted source | Exposes the database to the internet; the managed TLS and password are your only defense. |
| Redis with `noeviction` used as a pure cache | Cache fills, writes block, application stalls under load. Use `allkeys-lru` for caches. |
| No connection pooler on Postgres under load | Connection count exhaustion causes cascading failures. PgBouncer is free and included. |
| Volumes attached to a Droplet in a different datacenter | Volumes are datacenter-local; cross-DC attachment is not possible. Plan your topology. |
| MongoDB with a 2-node replica set | 2 nodes cannot form a majority quorum after one failure — you lose write availability. Use 3 nodes. |
| Spaces lifecycle rules never set | Non-current object versions accumulate at $0.02 / GB / month. Prune them. |

## Security defaults

- All Managed Database connection strings are TLS-encrypted; never accept `sslmode=disable`.
- Database credentials stored in an application secrets manager (e.g. Vault, AWS Secrets Manager, or DigitalOcean App Platform encrypted env vars), not in `.env` files or source code.
- Trusted sources restricted to the VPC-private IPs / Droplet UUIDs / DOKS cluster IDs that need access — not open to the internet.
- Spaces access keys: scoped per service, rotated on a schedule, stored in the same secrets manager as DB credentials.
- No public Spaces bucket unless it genuinely serves public-readable content; even then, restrict CORS and enable CDN.

## Observability defaults

- **Managed DB:** enable the DigitalOcean database alerts for CPU, memory, disk usage, and connection count. Wire them to a notification channel (email, Slack via webhook, PagerDuty).
- **Kafka:** monitor consumer group lag with `doctl databases kafka consumer-groups` or Kafka's own `__consumer_offsets` topic.
- **Spaces:** enable access logs (S3-compatible logging) for any bucket handling sensitive objects. Logs ship to a separate Spaces bucket.
- **Volumes:** monitor disk utilization on the Droplet; a 100%-full volume causes hard errors, not graceful degradation.
- **Query performance:** enable `pg_stat_statements` on Postgres (it is enabled by default on DigitalOcean managed Postgres) and review slow-query logs weekly.

## Cost considerations

- **Managed DB markup:** expect roughly 2–3× the raw Droplet cost for equivalent spec. Justified for teams without DBA expertise; questionable at large scale.
- **Spaces storage:** $0.02 / GB / month. Cheap, but orphaned objects and non-current versions accumulate — lifecycle rules are required.
- **Spaces CDN:** reduces origin egress, which is $0.01 / GB. Enable CDN for any asset-serving bucket.
- **Volumes:** $0.10 / GB / month for standard SSD. Resize up is live; resize down requires backup + restore.
- **Managed Redis:** billed on memory (plan size), not on operation count. Right-size on the actual dataset size, not peak possible usage.
- **Read replicas:** each read replica is a full additional cluster node, billed separately. Add replicas only when read traffic justifies the cost.

## IaC hints

- Terraform resources: `digitalocean_database_cluster`, `digitalocean_database_db`, `digitalocean_database_user`, `digitalocean_database_firewall`, `digitalocean_spaces_bucket`, `digitalocean_spaces_bucket_policy`, `digitalocean_volume`.
- Set `private_network_uuid` on every `digitalocean_database_cluster` to place it in the VPC — do not use the default (public) interface.
- Use `digitalocean_database_firewall` rules to restrict access to specific Droplet UUIDs or Kubernetes cluster UUIDs; manage them in Terraform, not the Control Panel.
- Spaces bucket ACL: set `acl = "private"` explicitly; do not rely on the default.
- Use `prevent_destroy = true` in Terraform for all stateful resources (databases, volumes, Spaces buckets holding backups).

## Verification checklist

- [ ] Storage tier chosen against the decision tree; managed vs self-hosted decision justified.
- [ ] All Managed Databases in a VPC; public interface disabled or restricted to specific IPs.
- [ ] Trusted sources list is explicit — no `0.0.0.0/0`.
- [ ] Connection pooler enabled for Postgres workloads under any concurrency.
- [ ] TLS enforced on all connections; `sslmode=require` (Postgres) or equivalent in use.
- [ ] Backup strategy documented; restore drill completed at least once.
- [ ] Spaces buckets default-private; lifecycle rules configured.
- [ ] Database credentials in a secrets manager; Spaces access keys rotated on schedule.
- [ ] Alert policies on database CPU, memory, disk, and connection count.
- [ ] `prevent_destroy = true` on all stateful Terraform resources.
