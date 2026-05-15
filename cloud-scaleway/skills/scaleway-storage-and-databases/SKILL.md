---
name: scaleway-storage-and-databases
description: Design or audit Scaleway storage and database tiers — Object Storage (S3-compatible, Standard / Glacier), Block Storage (SBS 5K / 15K IOPS), Managed Databases (Postgres, MySQL), Serverless SQL (scale-to-zero Postgres), Managed Document Database (MongoDB-compat), Redis Cluster, IoT Hub. Use when picking a data store, modeling access patterns, sizing, securing, or backing up data.
---

# Scaleway Storage and Databases

## When to use

- Choosing between object, block, relational, document, key-value, and IoT storage on Scaleway.
- Designing Managed Database HA replicas and PITR configuration.
- Sizing a Serverless SQL database and understanding scale-to-zero cost behavior.
- Hardening data-at-rest encryption, backups, and access controls.
- Auditing data egress, retention, lifecycle, and replication across Scaleway regions.

## Decision tree

| Need | Service |
| --- | --- |
| Object storage for blobs, backups, data lake, static assets | Object Storage (S3-compatible) |
| Block storage attached to an Instance or Kapsule pod | Block Storage (SBS) — 5K or 15K IOPS |
| ACID, relational, OLTP — Postgres or MySQL | Managed Database for PostgreSQL / MySQL |
| Relational, scale-to-zero, serverless billing | Serverless SQL Database (Postgres-compatible) |
| Document / JSON, flexible schema | Managed Document Database (MongoDB-compatible) |
| Sub-ms cache, pub/sub, queues | Redis Cluster |
| IoT device data ingestion and routing | IoT Hub |

## Object Storage defaults

- Encryption: server-side encryption on by default (Scaleway-managed keys). For regulated data, enable customer-managed keys via Key Manager (CMEK).
- Public access: bucket policies default to private. Expose objects publicly only via presigned URLs or a Scaleway Edge Services (CDN) distribution — not bucket-level public ACLs.
- Versioning: on for any bucket holding state, source artifacts, or backup objects.
- Lifecycle rules: transition to Glacier storage class at 90 d for infrequently accessed data; delete expired objects rather than letting the bucket grow unbounded.
- S3 compatibility: Scaleway Object Storage is S3-compatible. Use `s3cmd`, `rclone`, `aws-cli` with a custom endpoint (`s3.fr-par.scw.cloud`, `s3.nl-ams.scw.cloud`, `s3.pl-waw.scw.cloud`).
- Cross-region replication: manual (rclone sync or custom sync job) — Scaleway does not offer native CRR. Plan DR replication explicitly.
- ACL: prefer bucket policies over ACLs; ACLs are legacy.
- Notifications: not natively supported via S3 event notifications — use webhooks or a polling job for downstream pipeline triggers.

## Block Storage (SBS) defaults

- IOPS tier: SBS 5K for standard workloads (databases, OS volumes); SBS 15K for latency-sensitive databases (Postgres OLTP, Redis persistence). Do not use SBS 5K for production databases with write-intensive workloads.
- Minimum 1 GB; size conservatively and snapshot before resizing.
- Encryption: block volumes are encrypted at rest with Scaleway-managed keys. CMEK via Key Manager available — use for regulated workloads.
- Snapshots: create a snapshot before any risky operation (resize, migration). Snapshots are region-local — copy to a separate region manually for DR.
- Attachment: one block volume per Instance at a time. For shared access, use Object Storage or a Managed Database.
- Root volumes: prefer Local Storage (NVMe directly on the hypervisor) for OS + ephemeral; attach SBS for data that must survive an Instance replacement.

## Managed Database (Postgres / MySQL) defaults

- Engine: PostgreSQL 16 for new workloads. MySQL 8 if you have an existing MySQL application; avoid migrating to MySQL if starting fresh.
- HA: enable High Availability (standby replica) for production. Failover is automatic; plan a ~30 s connection reset window during failover.
- Backups: daily automated backups with 7-day retention minimum; 30 days for production. Enable PITR (point-in-time recovery) — it's essential for accidental-delete recovery.
- Maintenance window: schedule outside business hours; pin to a known day/time in IaC to avoid surprise restarts.
- Encryption: at rest and in transit. TLS required for all connections; Scaleway issues certificates per instance — pin the CA.
- Extensions: enable needed Postgres extensions (e.g., `pg_stat_statements`, `uuid-ossp`, `pgvector`) at provision time; extensions cannot be freely added post-creation without a restart window.
- Connection pooling: use PgBouncer or Scaleway's built-in connection pooler for Postgres under high-concurrency app connections. Direct connections exhaust `max_connections` quickly.
- Node type: `DB-DEV-S` for non-prod; `DB-GP-M` or higher for production. Never use DEV tier for production — it shares underlying compute.

## Serverless SQL Database defaults

- Billing: per vCPU-hour consumed, not per provisioned node. Scales to zero when idle — cost is $0 during quiet periods.
- Compatible with: standard Postgres wire protocol and most Postgres drivers.
- Limitations: no superuser, no COPY FROM local file, no custom extensions (subset of standard extensions available). Confirm compatibility before migrating a legacy Postgres workload.
- Connection: use the Scaleway-provided endpoint; connection pooling is built in.
- Use case: dev/staging databases, low-traffic production APIs with irregular usage patterns, feature branch databases.
- Not suitable for: high-write OLTP under constant load (use Managed Database), workloads that need custom extensions.

## Managed Document Database (MongoDB-compatible) defaults

- Protocol: MongoDB wire protocol compatible — works with the official MongoDB drivers.
- Encryption: at rest and in transit.
- HA: enable replica set mode for production — provides a secondary for failover.
- Backups and PITR: daily backups; PITR on for production.
- Use case: flexible document storage, content management, event sourcing, product catalogs with variable schema.

## Redis Cluster defaults

- Mode: cluster mode for production — horizontal sharding and online reshard. Standalone only for dev/test.
- Version: Redis 7.x on new clusters.
- AUTH: enable authentication (password) for every cluster accessible from application subnets.
- TLS: in-transit encryption mandatory for any cluster outside a tightly controlled Private Network.
- Encryption at rest: on.
- Eviction: `allkeys-lru` for general cache; `noeviction` for queues, session stores, or anywhere eviction = correctness bug.
- Persistence: `appendonly yes` (AOF) for workloads where losing recent writes is unacceptable; RDB snapshots for pure cache workloads.
- Multi-AZ: Redis Cluster on Scaleway replicates shards across AZs — verify the cluster topology reflects your HA requirement.

## IoT Hub defaults

- Routes: define explicit routes from device MQTT topics to downstream consumers (Object Storage, REST callbacks). Avoid "catch-all" routes that write everything to Object Storage indefinitely.
- Authentication: per-device certificates or token authentication. Never use a shared secret across all devices.
- Retention: plan message retention window; IoT Hub is a routing fabric, not a long-term store — route to Object Storage or a database for persistence.
- TLS: all device connections over TLS. Reject plain-text connections in Hub configuration.
- Use case: telemetry ingestion, remote commands, OTA updates for embedded devices.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Object Storage bucket with public read ACL | One misconfigured object = public data. Use presigned URLs or Edge Services. |
| Managed Database in a public subnet without IP allowlist | Open to the internet. Use Private Networks + IP allowlist restricted to app instances. |
| SBS 5K block volume for write-intensive Postgres | IOPS exhaustion under load; use SBS 15K or Managed Database. |
| Serverless SQL for high-write production OLTP | Cold-start latency and IOPS limits hurt under constant write load. |
| Redis without AUTH token | Cache poisoning or unintended data access trivial from any host in the network. |
| No PITR on production databases | Accidental delete = full restore from daily backup (hours of data loss). PITR on. |
| Snapshots without restore drills | Untested backups are wishes. Test quarterly. |
| Unbounded Object Storage lifecycle (no Glacier / delete rules) | Bill grows silently. Define lifecycle rules at bucket creation. |

## Security defaults

- All data at rest encrypted; use Key Manager (KMS) CMEK for regulated workloads (GDPR, HDS) so encryption keys are customer-controlled and auditable.
- Object Storage: bucket policies restrict access to specific IAM Applications (service accounts) in the same Project. Never `*` as a Principal.
- Managed Databases: accessible only from Private Network peers or specific allowlisted IP ranges — not public internet by default.
- Redis Cluster: AUTH + TLS mandatory; not accessible from outside Private Networks without explicit justification.
- Scaleway IAM: each application (service) gets its own IAM Application with a scoped Policy limited to the exact buckets, databases, or storage resources it needs.
- No hardcoded credentials in application code or IaC. Reference Secret Manager secrets at runtime.

## Observability defaults

- Managed Database: enable slow-query logging; monitor connections, CPU, free storage, and replication lag via Cockpit.
- Serverless SQL: monitor query duration and connection count via Cockpit metrics.
- Object Storage: enable access logs to a separate logging bucket; review for unexpected access patterns.
- Redis Cluster: monitor `evicted_keys`, `connected_clients`, `used_memory`, `rdb_last_bgsave_status` via Cockpit.
- IoT Hub: monitor message throughput and error rate per route.
- Wire Cockpit alerts on: Managed Database failover events, disk usage > 75%, Redis eviction rate spike, Object Storage bucket size anomaly.

## Cost considerations

- Object Storage: Standard class is billed per GB stored and per GB egressed to the internet. Glacier class (cold) is cheaper per-GB for rarely accessed data — lifecycle-tier appropriately.
- Managed Database: billed per node-hour. Standby replica doubles the node count. Right-size the node type before committing.
- Serverless SQL: $0 when idle. Cost scales with actual query load. Best value for bursty or developer workloads.
- SBS: billed per GB provisioned, not used. Snapshot storage billed separately. Purge unused volumes and old snapshots.
- Redis Cluster: billed per node-hour. Cluster mode adds replica nodes. Size conservatively; scaling down requires re-sharding.
- Egress from Scaleway to the internet is billed; traffic between resources within the same region over Private Networks is free. Minimize cross-internet hops.

## IaC hints

- Terraform `scaleway/scaleway` ≥ 2.45: `scaleway_object_bucket`, `scaleway_rdb_instance` (Managed Database), `scaleway_redis_cluster`, `scaleway_documentdb_instance`, `scaleway_mnq_sqs_*` (not IoT Hub — use `scaleway_iot_*`).
- `scaleway_rdb_instance` deletion protection: set `deletion_protection = true` for production databases; requires explicit removal to destroy.
- Bucket policies: use `scaleway_object_bucket_policy` resource — JSON policy similar to AWS S3 bucket policy format.
- Serverless SQL: managed via the Scaleway console or CLI (Terraform support is limited as of 2026-Q2 — verify current provider docs).
- State for stateful resources (databases, buckets) in a separate Terraform workspace from compute stacks to prevent accidental destruction.

## Verification checklist

- [ ] Access patterns enumerated before data store chosen.
- [ ] Encryption at rest and in transit on every store; CMEK via Key Manager for regulated data.
- [ ] No public network exposure for databases, caches, or block volumes.
- [ ] Backup retention matches RTO/RPO; PITR on for Managed Database.
- [ ] Restore drill documented and executed at least once.
- [ ] IAM Application scoped to specific resources; no wildcard Principal on bucket policies.
- [ ] Object Storage lifecycle rules defined; no unbounded growth.
- [ ] Cockpit alerts wired for disk usage, connection count, and failover events.
- [ ] Deletion protection set on production Managed Database in IaC.
