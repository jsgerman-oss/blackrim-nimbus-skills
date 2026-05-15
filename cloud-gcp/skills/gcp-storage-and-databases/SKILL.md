---
name: gcp-storage-and-databases
description: Design or audit GCP storage and database tiers — Cloud Storage, Persistent Disk, Cloud SQL, AlloyDB, Spanner, Firestore, Memorystore, BigQuery. Use when picking a data store, modeling access patterns, sizing capacity, securing data, or configuring lifecycle and backups.
---

# GCP Storage and Databases

## When to use

- Choosing between object storage, block storage, relational, document, key-value, and analytics stores.
- Designing Firestore document models or Spanner schema from access patterns.
- Sizing a Cloud SQL or AlloyDB instance and selecting a high-availability configuration.
- Hardening encryption at rest, automated backups, and point-in-time recovery.
- Auditing data egress, retention lifecycle, and replication topology.
- Evaluating BigQuery slot reservations versus on-demand pricing.

## Decision tree

| Need | Service |
| --- | --- |
| Object storage — blobs, backups, data lake, static assets | Cloud Storage |
| Block storage attached to a VM or GKE node | Persistent Disk (or Hyperdisk for high-IOPS) |
| ACID relational OLTP, PostgreSQL or MySQL compatible | Cloud SQL (smaller scale) or AlloyDB (PostgreSQL, higher performance) |
| Horizontally scalable relational with global distribution | Spanner |
| Document store, flexible schema, mobile/web SDK | Firestore (native mode) |
| Legacy Datastore workload in migration | Firestore in Datastore mode (transition, not greenfield) |
| Low-latency cache or pub/sub | Memorystore for Redis / Valkey / Memcached |
| Petabyte analytics, ad-hoc SQL, columnar | BigQuery |
| Time-series metrics | Cloud Monitoring (built-in) or BigQuery + Bigtable for high-write time-series |

## Cloud Storage defaults

- Encryption: Google-managed encryption is always on; use **CMEK** with a Cloud KMS key for any bucket holding regulated or sensitive data.
- Public access prevention: set `public_access_prevention = enforced` at the bucket level; set the org policy `constraints/storage.publicAccessPrevention` at the org level. Serve public content via Cloud CDN + a signed URL or a dedicated bucket with explicit IAM, never `allUsers`.
- Location: single-region for lowest latency + lowest egress cost; dual-region for near-seamless failover within a geography; multi-region for globally distributed reads.
- Storage class: Standard for active data; Nearline (access < once per 30 d); Coldline (< once per 90 d); Archive (< once per year). Use Object Lifecycle Management rules to automate transitions.
- Versioning: on for any bucket holding state, source artifacts, or customer-uploaded content.
- Object retention and holds: use `retention_policy` or Object Holds for compliance workloads (WORM).
- Notifications: Pub/Sub notifications via `google_storage_notification` for downstream pipeline triggers — prefer Eventarc for Cloud Run / Cloud Functions integration.
- Uniform bucket-level access: enabled on all buckets. Legacy per-object ACLs are a footgun.

## Cloud SQL defaults

- Engine: PostgreSQL preferred for new work; MySQL if the application stack mandates it.
- High availability: `REGIONAL` availability type — synchronous replication across zones, automatic failover. `ZONAL` only for dev/test.
- Instance tier: `db-custom-<cpu>-<memory>` for precise sizing. Start with the sizing guide and adjust based on Cloud SQL Recommender output.
- Backups: automated daily backups, 7-day retention minimum in prod, 30 days for regulated workloads; point-in-time recovery enabled.
- Disk: SSD (`PD_SSD`), with storage auto-increase enabled. Never let the disk fill — Cloud SQL stops accepting writes when full.
- SSL/TLS: `require_ssl = true` in the database flags. Use `pg_tls_min_protocol_version = TLSv1.2` minimum.
- Flags: pin `log_min_duration_statement=500` for slow-query detection; `pgaudit` for audit logging; `cloudsql.enable_pgaudit=on`.
- Private IP only: disable the public IP; access via Cloud SQL Auth Proxy from applications or Cloud SQL connector libraries. Direct IP access is not acceptable for prod.
- Deletion protection: `deletion_protection = true` in Terraform; remove only when intentionally destroying.

## AlloyDB defaults

- Use AlloyDB over Cloud SQL when you need higher PostgreSQL performance (OLTP-heavy, read-heavy with replicas, or ML-embedded queries via AlloyDB Omni).
- Primary + at least one read pool for any prod workload that needs read scale-out.
- Private IP exclusively — AlloyDB does not support public IP connectivity.
- Automated backups: continuous backup enabled; point-in-time recovery to any second within the retention window.
- CMEK: encrypt at rest with a Cloud KMS key.

## Spanner defaults

- Instance configuration: regional for lowest latency if your users are in one region; multi-region for global active-active.
- Processing units: start with 100 PU (1 node = 1000 PU); scale up incrementally and watch CPU utilization (< 65% for reads, < 45% for writes in multi-region).
- Schema: interleaved tables for parent-child access patterns; avoid hotspot key ranges (UUIDs are fine; monotonic integer PKs are not).
- Backups: scheduled backups via `google_spanner_backup_schedule`; retain beyond your RTO window.
- CMEK: encrypt at rest with a Cloud KMS key in each Spanner region.

## Firestore defaults

- Native mode for all new workloads — native mode supports all current features and the mobile/web SDKs.
- Datastore mode only when migrating a legacy Datastore application; plan a migration to native mode eventually.
- Security rules: write explicit rules for every collection; never leave `allow read, write: if true` in any environment.
- Composite indexes: define via `firestore.indexes.json` in IaC — missing indexes cause fallback scans that are expensive and slow.
- TTL fields: use TTL policies to automatically delete old documents (sessions, ephemeral events).
- Export: scheduled exports to Cloud Storage for backup and BigQuery import.

## Memorystore defaults

- Engine: Redis or Valkey (the open-source successor) for cache and pub/sub; Memcached for pure cache when you don't need persistence or replication.
- AUTH string: mandatory for any Memorystore Redis instance reachable from application VPCs.
- In-transit encryption: `transit_encryption_mode = "SERVER_AUTHENTICATION"` — TLS required.
- At-rest encryption: CMEK for regulated workloads.
- High-availability: `STANDARD_HA` tier for any prod cache (synchronous replica in a second zone).
- Eviction policy: `allkeys-lru` for general cache; `noeviction` for queues or sessions where eviction = data loss.
- No public IP: Memorystore instances are private (VPC only) by design. Access from Serverless VPC Access connector or Direct VPC Egress from Cloud Run.

## BigQuery defaults

- Data location: choose a region that collocates with the data source to minimize egress; US multi-region or EU multi-region for global analytics queries.
- Partitioning: partition every large table by a date/timestamp column or integer range. Required for cost-controlled queries.
- Clustering: cluster on the columns most commonly used in `WHERE` and `GROUP BY` after the partition column. Reduces bytes scanned.
- Slot reservations: use reservations + assignments (pay-per-slot) rather than on-demand once your usage is predictable. Flex Slots for burst capacity.
- Column-level security: apply policy tags (Data Catalog) for PII / regulated columns; enforce via IAM.
- Row-level access policies: use authorized views or row access policies rather than duplicating tables per user group.
- Storage: active storage is included; long-term storage pricing kicks in after 90 days with no modification — a cost-saving reason not to mutate historical tables.
- Authorized datasets: for sharing across projects without data copies, use dataset-level IAM rather than project-level.
- Exports for archival: use scheduled exports to Cloud Storage (Parquet, ORC) for data older than your analysis window.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Cloud Storage bucket with `allUsers` IAM binding | Public data breach. Use CDN signed URLs or public-access-prevention. |
| Cloud SQL with public IP and no SSL requirement | One misconfigured firewall rule away from exposure. Private IP + Auth Proxy. |
| Firestore rules `allow read, write: if true` deployed to prod | Any authenticated (or unauthenticated) user owns your database. |
| BigQuery queries with no partition filter on a 10 TB table | Full table scans = large bills. Enforce partition filters via table settings. |
| Spanner with monotonic integer primary keys | Write hotspot on one server split. Use UUIDs or hash prefixes. |
| Memorystore without AUTH string | Any process in the VPC can write arbitrary cache entries. |
| Automated Cloud SQL backups disabled "to save money" | The backup cost is trivial; the recovery cost of having none is catastrophic. |
| BigQuery on-demand pricing with uncontrolled query patterns | One runaway query from a junior analyst can cost hundreds of dollars. Use slot reservations and quotas. |

## Security defaults

- All data at rest encrypted; use CMEK (Cloud KMS CMK) for any data subject to audit, revocation, or per-tenant key requirements.
- Cloud Storage: uniform bucket-level access, public access prevention, no legacy ACLs.
- VPC Service Controls perimeter around Cloud Storage, BigQuery, and Cloud SQL for regulated data — prevents data exfil even from compromised service accounts.
- IAM conditions on sensitive storage resources (restrict to specific projects, service accounts, or time windows).
- Cloud SQL Auth Proxy or Cloud SQL connector library for all application connections — no direct database port exposure.
- BigQuery: column-level policy tags for PII; audit logs of `bigquery.tables.getData` events via Cloud Audit Logs.

## Observability defaults

- Cloud SQL: Cloud SQL Insights for query performance; alerts on `disk_utilization > 80%`, `cpu_utilization > 80%`, `memory_utilization > 90%`, and failed connections.
- BigQuery: slot utilization dashboard; alert when query queue depth is non-zero during business hours (signals slot exhaustion).
- Cloud Storage: log all object-level operations to Cloud Logging for compliance buckets; alert on unexpected object deletions.
- Memorystore: alerts on `memory_usage_ratio > 0.8`, `blocked_clients > 0`, and `connected_clients` approaching the limit.
- Spanner: CPU utilization alerts per the scaling thresholds above; alert on transaction abort rate spikes.

## Cost considerations

- Cloud Storage egress within a region is free; cross-region and internet egress costs money. Prefer same-region access; use CDN for public content to avoid origin egress.
- Cloud SQL: committed use discounts for steady-state instances; read replicas add full instance cost — use them only where read scale is needed.
- BigQuery: on-demand billing by bytes scanned; slot reservations are cheaper above a predictable usage threshold. Partition pruning and clustering are the cheapest performance improvements.
- Memorystore: billed per GB allocated, not per GB used. Right-size by measuring actual memory usage with `INFO memory`.
- Spanner: billed per processing unit-hour — scale down unused Spanner instances in non-prod environments aggressively.
- Persistent Disk: unused PDs attached to stopped VMs still incur storage charges. Snapshot and delete, then recreate on demand.

## IaC hints

- Terraform: `google_storage_bucket`, `google_sql_database_instance`, `google_alloydb_cluster`, `google_spanner_instance`, `google_firestore_database`, `google_redis_instance`, `google_bigquery_dataset` + `google_bigquery_table`.
- Use `lifecycle { prevent_destroy = true }` on any stateful resource in prod environments.
- Separate Terraform workspaces (or state files) for storage resources from compute resources — databases outlive compute and should never be caught in a broad destroy.
- CMEK binding: `google_kms_crypto_key_iam_binding` granting `roles/cloudkms.cryptoKeyEncrypterDecrypter` to the relevant GCP service agent (e.g., `serviceAccount:service-<project_number>@gs-project-accounts.iam.gserviceaccount.com`).

## Verification checklist

- [ ] Access patterns enumerated before schema or store was chosen.
- [ ] Encryption at rest and in transit on every data store; CMEK applied where data sensitivity requires it.
- [ ] No public IP or public bucket exposure without explicit business justification.
- [ ] Backup retention matches RTO/RPO; a restore drill has been performed.
- [ ] PITR or continuous backup enabled on transactional databases.
- [ ] IAM scoped to specific datasets, tables, buckets, or instances — no project-level editor bindings.
- [ ] Object Lifecycle Management or TTL configured; old data does not accumulate indefinitely.
- [ ] Monitoring and alerting covering the failure modes that matter most per data store type.
