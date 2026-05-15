---
name: vultr-storage-and-databases
description: Design or audit Vultr storage and database tiers — Block Storage (HDD vs NVMe), Object Storage (S3-compatible), Backups, Managed Databases (Postgres, MySQL, Redis/Valkey, Kafka) with HA tiers and replicas, and restore drills. Use when picking a data store, sizing, securing, setting up replication, or running a backup restore drill.
---

# Vultr Storage and Databases

## When to use

- Choosing between Block Storage, Object Storage, or a Managed Database for a workload.
- Sizing a Managed Database cluster (plan, replica count, HA tier).
- Enabling and testing automated Backups on a Cloud Compute instance.
- Designing an Object Storage access control or lifecycle policy.
- Restoring from a snapshot or database backup — planned or incident-driven.

## Decision tree

| Need | Vultr service |
| --- | --- |
| Block device attached to one instance (database disk, large files) | Block Storage (NVMe) |
| Blobs, backups, static assets, data lake, S3-compatible workloads | Object Storage |
| Automated point-in-time recovery for a Cloud Compute instance | Backups (instance feature) |
| Managed relational — Postgres or MySQL, ACID, OLTP | Managed Database — Postgres or MySQL |
| Managed key-value cache or pub/sub | Managed Database — Redis / Valkey |
| Managed Kafka streams | Managed Database — Kafka |
| Full-text search or log analytics | Self-hosted OpenSearch/Elasticsearch on Block Storage |
| Petabyte analytics or columnar store | Self-hosted (Vultr has no managed analytics offering) |

**Important limitation:** Vultr does not offer a managed graph database, time-series database, or managed search service. Workloads requiring these must self-host on Cloud Compute with Block Storage.

## Block Storage defaults

- **Type:** NVMe (SSD) for any workload where latency matters. HDD block storage is cheaper but suitable only for archival mounts (cold backups staged for upload, bulk dataset scratch space).
- **Attach region:** Block Storage is single-region and single-instance. It cannot be simultaneously attached to two instances or moved between regions without a data copy.
- **Filesystem:** `ext4` or `xfs`; format on first attach via startup script or manual step. Do not assume the block device is formatted on provision.
- **Mount persistence:** Add to `/etc/fstab` with `nofail` so the instance boots if the volume is temporarily unavailable during maintenance.
- **Encryption:** Block Storage does not offer managed encryption-at-rest as of 2026-05. For sensitive data, use LUKS encryption at the OS layer before mounting, or rely on Object Storage with server-side encryption.
- **Resize:** Block Storage volumes can be expanded online (no detach required). Shrinking is not supported — size up conservatively and expand as needed.
- **Backup:** Block Storage volumes are not included in instance Backups. Snapshot the instance (which includes attached block volumes) or run OS-level backups (rsync, pg_dump, restic) to Object Storage.

## Object Storage defaults

- **S3-compatible API:** Vultr Object Storage is S3-compatible. Any SDK or tool that supports S3 with a custom endpoint works (AWS SDK, s3cmd, rclone, MinIO client).
- **Endpoint:** Each cluster has a regional endpoint (e.g., `ewr1.vultrobjects.com`). Specify the endpoint explicitly in every client — do not assume AWS defaults.
- **Access control:** Object Storage uses canned ACLs (`private`, `public-read`, `authenticated-read`) and bucket policies. Default all buckets to `private`. Grant public-read only on buckets that intentionally serve public content.
- **Server-side encryption:** Enabled by default (AES-256 managed keys). As of 2026-05, customer-managed keys are not supported. For regulated data requiring key custody, encrypt client-side before upload.
- **Versioning:** Enable on buckets holding application state, code artifacts, or backups — protects against accidental deletes and overwrites.
- **Lifecycle rules:** Configure expiration policies for temporary data, old backup generations, and log archives. Vultr Object Storage supports S3-compatible lifecycle rules via the API or s3cmd.
- **Multi-region replication:** Vultr Object Storage does not support cross-region replication as of 2026-05. For disaster recovery, copy critical objects to a second cluster in a different region using rclone or a scheduled sync job.
- **CORS:** Configure CORS policies on buckets serving browser-direct uploads or frontend assets. Default is no CORS — browsers will block requests without it.

## Backups (instance-level)

- Enable Backups on every stateful Cloud Compute or Bare Metal instance. Vultr Backups create daily snapshots and retain up to five recovery points.
- Backups are stored in a different availability zone but the same region — not a DR solution for regional outages.
- Test restore at least once before you need it. Restore via the Vultr control panel or `vultr-cli backup restore --id <backup-id> --instance-id <id>` to a new instance (does not overwrite the running instance).
- **Backup window:** Vultr picks a backup window automatically. You cannot pin an exact time; schedule application-level maintenance windows to avoid backup/write conflicts on databases.
- **Backup vs Snapshot:** Automated Backups retain five points with no manual intervention. Manual Snapshots are single-point captures you initiate; unlimited but billed per GB.

## Managed Databases

### Postgres

- **Plan selection:** Vultr Managed Database plans are named `vultr-dbaas-*`. Plans vary by vCPU, RAM, and disk — scale up rather than adding read replicas for write-heavy workloads.
- **High availability:** HA mode adds a standby replica in the same region with automatic failover. Enable HA for every production Postgres database. Non-HA clusters have a maintenance window downtime of several minutes.
- **Read replicas:** Add up to five read replicas per cluster. Replicas are in the same region as the primary. Cross-region replicas are not supported as of 2026-05.
- **Connection pooling:** Vultr Managed Postgres ships with PgBouncer pre-configured. Use the pooler connection string (port 5432 connection pool) rather than connecting directly to Postgres (port 5433) for application connections. Reserve direct connections for administrative use.
- **SSL:** Always enabled; do not disable SSL on the connection string. Use `sslmode=require` at minimum, `sslmode=verify-full` for regulated workloads.
- **Extensions:** A curated set of extensions is supported (uuid-ossp, pg_stat_statements, postgis, etc.). Verify the extension list in the Vultr docs for the specific Postgres version before relying on one.
- **Backups:** Automated daily backups with PITR retention (configurable, default 7 days). Restore via control panel or API — creates a new cluster.

### MySQL

- Same HA, read replica, and SSL defaults as Postgres apply.
- Connection via ProxySQL pooler included. Use the ProxySQL port for application connections.
- Enforce `sql_mode=STRICT_TRANS_TABLES` — Vultr's default is reasonable but verify after creation.
- Do not use MySQL for new workloads if the team is comfortable with Postgres; Postgres is the stronger option for OLTP, JSONB workloads, and extension ecosystem.

### Redis / Valkey

- Vultr Managed Database Redis clusters use Valkey (the open-source Redis fork) on newer plans. Verify the engine version via `vultr-cli database list`.
- **Auth:** Managed Redis clusters require an `AUTH` password. The password is available via the Vultr API or control panel. Never connect without auth.
- **TLS:** Always use the TLS endpoint; Vultr provides both plain and TLS ports, but only the TLS port should be used in production.
- **Persistence:** Managed Redis clusters have persistence enabled (RDB snapshots). AOF is not configurable by the user.
- **Eviction policy:** The default is `noeviction`. For a pure cache, change to `allkeys-lru` — otherwise the cluster returns errors when memory fills rather than evicting old keys.
- **Replication:** Managed Redis includes a standby replica for HA clusters. Single-node Redis clusters have no failover path.

### Kafka

- Vultr Managed Kafka is based on Apache Kafka. As of 2026-05, it is available in select regions — verify before designing a Kafka-dependent architecture for a specific region.
- **Topics:** Create topics via the Vultr API or control panel. Replication factor of 3 is the default for HA clusters; do not reduce below 2 in production.
- **ACLs:** Managed Kafka supports SASL/SCRAM authentication. Create per-service credentials — do not share a single set of credentials across producers and consumers.
- **Schema Registry:** Vultr Managed Kafka does not include a managed Schema Registry as of 2026-05. Run Schema Registry on a Cloud Compute instance or use Confluent Schema Registry as a managed service separately.
- **Monitoring:** Expose Kafka JMX metrics to a Prometheus exporter running on a dedicated instance; Vultr does not expose Kafka metrics through its built-in metrics system.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| HDD Block Storage for a production database | Disk I/O latency is 10–50× higher than NVMe. Queries stall. Use NVMe for anything with IOPS requirements. |
| Object Storage bucket with public-read by default | Any key you write is publicly readable. Start private; grant public access explicitly per object or prefix. |
| Managed Database without HA for production | Single-node Postgres / MySQL has minutes of downtime during Vultr maintenance windows. Always use HA in prod. |
| Connecting to Managed Postgres directly (port 5433) from the app | Exhausts Postgres max_connections fast. Use the PgBouncer pooler endpoint instead. |
| Redis with `noeviction` and no monitoring | Memory fills, Redis returns `OOM` errors, your app fails with cryptic cache errors. Set eviction policy; alert on used memory %. |
| Backups untested | Untested backups are wishes. Run a restore drill before you need one in production. |
| Cross-region DR via manual sync | Manual sync breaks under incident pressure. Automate the rclone sync or accept that Object Storage is single-region with no DR. |
| Block Storage on HDD for Object Storage staging | If you are staging data before uploading to Object Storage, use a local NVMe volume or RAM-backed tmpfs for speed. |

## Security defaults

- Object Storage: all buckets `private`; no public-read unless deliberately serving public content. Rotate access keys (S3 key/secret) quarterly.
- Block Storage with sensitive data: LUKS full-disk encryption at the OS layer. Document the decryption key in a secrets store — not in the startup script.
- Managed Databases: connect only over TLS/SSL; reject plaintext connections at the client configuration level. Store the database password in a secrets manager, not in environment variables baked at deploy time.
- Managed Database credentials: create a per-application database user with minimal privilege (SELECT / INSERT / UPDATE for the application schema; no DDL access in prod). Use the `postgres` / `root` superuser only for administrative operations.
- Backups: Vultr Backup restores can target any instance in the same account — limit control panel access (use 2FA + sub-accounts if available) to prevent unauthorized restores.

## Observability defaults

- Managed Databases: built-in metrics (connections, query latency, storage used, replication lag) are visible in the Vultr control panel and via the API. Set up Alerts on storage fullness (> 80%) and replication lag.
- Block Storage: monitor from the OS (iostat, df); wire to Prometheus node exporter.
- Object Storage: no built-in access logs from Vultr. Enable S3-compatible server access logging to a separate bucket (or ship to a log aggregator via rclone) if you need an access audit trail.
- Backup status: `vultr-cli backup list` or poll the API on a schedule; alert if backups haven't run in 25+ hours.

## Cost considerations

- **Block Storage:** billed per GB per month. NVMe is priced higher than HDD but the I/O performance difference is substantial — default to NVMe.
- **Object Storage:** Vultr includes a monthly storage and egress allotment per cluster ($5/mo for the smallest cluster). Overage is charged per GB. Egress pricing varies slightly by region.
- **Managed Databases:** monthly flat rate per plan. Unlike compute, Managed Database plans do not have per-hour billing caps that differ from the monthly rate — they are purely monthly. Budget accordingly.
- **Backups:** Instance Backups are included at 20% of the instance cost. Manual Snapshots are billed per GB of disk used, regardless of data sparsity.
- **Bandwidth:** Managed Databases do not consume from the instance bandwidth pool — database connections are internal Vultr network. Egress from Object Storage to external clients counts against the Object Storage egress allotment.

## IaC hints

- Terraform resources: `vultr_block_storage`, `vultr_object_storage`, `vultr_database` (covers Postgres, MySQL, Redis, Kafka).
- Use `data "vultr_database_plan"` to enumerate valid Managed Database plans for a given database type and region.
- Object Storage credentials (access key / secret) are created via `vultr_object_storage` resource; retrieve the key and secret from the resource output and store in a secrets manager.
- Block Storage attachment: `vultr_block_storage_attach` resource manages the attach/detach lifecycle separately from the volume creation. This allows re-attaching a volume to a replacement instance after a rebuild.
- Database restore: Vultr does not expose a Terraform resource for triggering a restore — use the `vultr-cli` or Vultr API in a `null_resource` provisioner if restore automation is needed in IaC.

## Verification checklist

- [ ] Storage type chosen from access pattern and I/O requirements (NVMe vs HDD vs Object).
- [ ] Object Storage buckets created with `private` ACL; public-read granted only where explicitly needed.
- [ ] Managed Databases use HA mode in production; single-node only for dev/test with documented risk acceptance.
- [ ] SSL/TLS enforced on all database connections; plain connections rejected at the client.
- [ ] Per-application database user with minimal privilege; superuser not used by the application.
- [ ] Backups enabled on stateful instances; restore drilled at least once.
- [ ] Object Storage lifecycle rules configured for expiring temporary data.
- [ ] Monitoring on storage fullness, replication lag, and connection counts.
- [ ] Redis eviction policy set appropriately for the use case (cache vs session/queue).
- [ ] Block Storage on NVMe; LUKS encryption in place for sensitive data if required.
