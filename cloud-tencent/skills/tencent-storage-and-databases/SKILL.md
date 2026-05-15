---
name: tencent-storage-and-databases
description: Design or audit Tencent Cloud storage and database tiers — COS object storage, CBS block storage, CFS file storage, CDB MySQL, TDSQL (distributed SQL), MariaDB, DocumentDB (MongoDB-compatible), Redis, ClickHouse, Tendis, HBase, SQL Server. Use when picking a data store, modeling access patterns, sizing, securing, or designing backup and replication.
---

# Tencent Storage and Databases

## When to use

- Choosing between object, block, file, relational, document, key-value, time-series, and columnar storage.
- Designing COS bucket lifecycle, CRR, and access control.
- Sizing a CDB or TDSQL cluster and choosing a failover strategy.
- Hardening data-at-rest encryption, backup retention, and PITR.
- Auditing data egress, lifecycle, cross-border transfer, and replication topology.

## Decision tree

| Need | Service |
| --- | --- |
| Object storage — files, backups, static assets, data lake | COS (Cloud Object Storage) |
| Block storage attached to a CVM or TKE pod | CBS (Cloud Block Storage) |
| Shared POSIX filesystem across multiple CVM / TKE nodes | CFS (Cloud File Storage) |
| ACID relational, MySQL-compatible OLTP | CDB for MySQL |
| High-availability, distributed MySQL / PostgreSQL | TDSQL-C (Aurora-style) or TDSQL (sharding) |
| MariaDB-compatible relational | TencentDB for MariaDB |
| MongoDB-compatible document store | TencentDB DocumentDB |
| Sub-millisecond cache or pub/sub | TencentDB for Redis |
| Real-time analytics, log aggregation, columnar OLAP | TencentDB for ClickHouse |
| Redis-compatible persistent KV (offline-safe) | Tendis |
| HBase-style wide-column NoSQL | TencentDB for HBase |
| SQL Server (Windows workloads, .NET) | TencentDB for SQL Server |

## COS (Cloud Object Storage) defaults

- Storage classes: **Standard** (frequent access), **Standard IA** (infrequent, min 30-day charge), **Archive** (min 90-day, retrieval delay), **Deep Archive** (min 180-day, retrieval delay). Choose by access frequency.
- Encryption: SSE-COS (AES-256, platform-managed) as the minimum; **SSE-KMS** with a customer-managed CMK for data subject to compliance audit or revocation requirements.
- Public access: **Block all public access** at the bucket level and at the account level via a bucket policy default-deny. Serve public assets through CDN or COS signed URLs, not direct public buckets.
- Versioning: enable on any bucket holding application state, backups, or source artifacts.
- Lifecycle: configure explicit rules — transition to Standard IA at 30 days, Archive at 90 days, Deep Archive at 365 days; delete expired versions after a retention window.
- Cross-Region Replication (CRR): for DR or latency optimization. Replication is asynchronous; factor RPO accordingly. Replicate KMS keys (or use the same CMK if cross-region keys are configured) so replicated objects remain decryptable.
- Event notifications: COS events → SCF or CKafka for downstream pipeline triggers.
- **China data residency**: data stored in China-region COS buckets subject to CAC cross-border transfer rules if egressed internationally. Confirm legal basis before configuring CRR from China to International regions.

## CBS (Cloud Block Storage) defaults

- Volume types:
  - `CLOUD_PREMIUM` (HDD-backed, throughput-balanced): cost-effective for logs, sequential I/O.
  - `CLOUD_SSD`: general databases, transactional workloads.
  - `CLOUD_HSSD` (Enhanced SSD): high-IOPS databases, Redis persistence volumes.
  - `CLOUD_TREMENDOUS_SSD` (Tremendous SSD): ultra-low latency I/O, NVMe-class performance — use for latency-sensitive OLTP.
- Encryption: AES-256 at rest enabled via KMS CMK on every production volume.
- Snapshots: automated snapshot policy on all stateful volumes. At minimum daily snapshots, 7-day retention; 30-day for production databases.
- Elastic volumes: CBS volumes can be expanded online without detaching. Set up an alert at 80% utilization to trigger expansion before the disk fills.
- One data volume, separate from the OS root volume: keep the root volume disposable so CVM can be replaced without data risk.

## CFS (Cloud File Storage) defaults

- Performance tier: **Standard** for shared documents and logs; **High Performance** for latency-sensitive workloads (databases reading from CFS are rarely a good idea — use CBS instead).
- Access control: VPC-based mount access; restrict the security group to the subnets that legitimately need the share.
- Encryption: CFS Standard encrypts at rest with a Tencent-managed key. For compliance, use CFS with KMS-integrated encryption.
- Snapshots: available for CFS Standard; schedule them for any share holding stateful data.

## CDB for MySQL defaults

- Engine version: MySQL 8.0 (latest stable as of 2026).
- High availability: **High Availability edition** (one primary + one standby in the same AZ, synchronous replication) for production. **Finance edition** (one primary + two standbys across two AZs) for regulated or RPO-zero workloads.
- Backups: 7-day automatic backup minimum; 30-day for production; enable **log backup** for PITR. Backups stored encrypted in COS.
- Parameter group: never use the default. Pin `require_secure_transport=ON`, `slow_query_log=ON`, `long_query_time=0.5`, `innodb_buffer_pool_size` sized to 70–80% of instance RAM.
- Encryption: KMS CMK encryption for instance storage.
- Proxy: use **CDB Proxy** (read-write splitting proxy) for read-heavy workloads to offload replicas transparently.
- Maintenance window: outside business hours; pin to a known cadence for minor version updates.

## TDSQL-C (cloud-native distributed SQL) defaults

- Compatible with MySQL 8.0 and PostgreSQL 14. TDSQL-C is Tencent's Aurora-equivalent: storage is decoupled from compute, auto-scales, 6-copy Raft across multiple AZs.
- Use TDSQL-C when you need: fast read replica scaling, storage auto-scaling beyond CDB's limits, or sub-minute failover RTO.
- Serverless TDSQL-C: scales compute to zero — ideal for dev / staging and bursty applications. Not suitable for latency-sensitive production paths (cold-start on compute scale-up).
- Backups: automated snapshots + continuous log shipping for PITR to any second within the retention window (up to 7 days standard, configurable).

## TencentDB for Redis defaults

- Edition: **Memory Edition (cluster mode)** for production — automatic sharding, online scaling, cross-AZ replication. **Memory Edition (standard mode)** only for dev or small caches.
- Auth: **password authentication** mandatory. VPC-only; Redis should never have a public endpoint.
- Encryption: TLS in-transit for Redis 6.0+ instances. At-rest encryption via the underlying CBS KMS CMK.
- Eviction: `allkeys-lru` for general caches; `noeviction` for queues or sessions where data loss is a correctness bug.
- Persistence: AOF + RDB for any Redis used as a durable store. AOF `appendfsync everysec` for the safety/performance balance.
- Replication: at least one replica across a different AZ for any production cache.

## DocumentDB (MongoDB-compatible) defaults

- Version: compatible with MongoDB 4.0 (verify current compat matrix at Tencent docs before pinning).
- High availability: replica set mode with 3 nodes across multiple AZs.
- Encryption: KMS CMK at rest; TLS in-transit (require `tls=true` in connection strings).
- Oplog retention: at minimum 24 hours for CDC consumers; 72 hours for operational resilience.
- Indexes: audit unindexed queries before go-live. DocumentDB does not auto-index `_id` on all subfields.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| COS bucket policy allowing public-read without intent | One misconfigured ACL and you're serving PII to the open internet. Default-deny; use signed URLs. |
| CDB in a public subnet | Port 3306 on Shodan within hours. Private subnets, VPC-only, always. |
| CBS volume type `CLOUD_PREMIUM` for an OLTP database | Throughput ceiling triggers I/O queuing under load. Size to actual IOPS requirement. |
| Redis without auth token, in a shared subnet | Any pod in the subnet can read all cache data. Auth + VPC isolation. |
| TDSQL-C Serverless for latency-sensitive prod paths | Compute cold-start adds 5–30 s to first query after idle. Use provisioned for prod. |
| CRR from China to International without legal review | CAC cross-border data transfer rules apply; non-compliance is a regulatory risk. |
| COS without lifecycle rules | Storage accumulates indefinitely; costs compound. Define lifecycle before data lands. |
| Snapshots without restore drills | Untested backups are assumptions. Drill at least quarterly. |

## Security defaults

- All data at rest encrypted: CBS volumes with KMS CMK, COS buckets with SSE-KMS, CDB instances with CMK.
- VPC-only access for all databases and caches — no public endpoints.
- COS bucket policies: explicit default-deny; grant access only to specific CAM roles and service principals.
- For regulated data (PII, financial): consider application-layer encryption before writing to COS or CDB, so Tencent's own operators cannot read plaintext.
- COS: enable **access logging** to a separate logging bucket; enable **CloudAudit data events** for any bucket holding regulated data.
- China data residency: document which COS buckets hold data subject to CAC regulation. Do not configure CRR to non-China regions without completing the cross-border security assessment.

## Observability defaults

- CDB: enable **Slow Query Log** to CLS, alarm on `Threads_running` spike, `QPS` drop, `Buffer Pool Hit Rate` below 95%.
- CBS: alarm on volume throughput > 80% of spec, IOPS > 80% of provisioned IOPS.
- Redis: alarm on `Evictions > 0` for noeviction policy, `Connected Clients` approaching limit, `Memory Usage %`.
- COS: server-access logs to a logging bucket; CloudAudit data events on buckets with compliance requirements.
- TDSQL-C: Cloud Monitor monitors CPU, memory, storage, connections, and replication lag — set alarms on replication lag > 30 s.

## Cost considerations

- COS: Standard IA saves ~40% vs Standard for data accessed less than once per month, but charges a retrieval fee. Calculate break-even against actual access patterns before switching.
- CBS: `CLOUD_PREMIUM` is cheapest; `CLOUD_TREMENDOUS_SSD` is 4–6× more expensive. Only pay for Enhanced/Tremendous SSD where IOPS is measured and constrained.
- CDB reserved instances: 1-year reserved instances for any CDB running continuously. 30–50% discount vs on-demand.
- Redis: cluster mode allows horizontal scaling instead of vertical — often cheaper than buying the next size up.
- ClickHouse: cold/hot tiered storage via COS + CBS. Keep recent data on CBS; offload historical data to COS-backed cold storage.
- TDSQL-C Serverless: free when idle — great for dev/staging; set a max ACU limit to cap spend during unexpected load.

## IaC hints

- Terraform provider: `tencentcloudstack/tencentcloud` ≥ 1.81.
- Resources: `tencentcloud_cos_bucket` (COS), `tencentcloud_cbs_storage` (CBS), `tencentcloud_cfs_file_system` (CFS), `tencentcloud_mysql_instance` (CDB), `tencentcloud_cynosdb_cluster` (TDSQL-C), `tencentcloud_redis_instance`, `tencentcloud_mongodb_instance` (DocumentDB).
- Always set `force_delete = false` and use lifecycle `prevent_destroy = true` for production stateful resources.
- State for stateful data resources in a separate Terraform workspace from compute. Data resources outlive application versions.

## Verification checklist

- [ ] Data store type chosen based on access pattern, not familiarity.
- [ ] Encryption at rest (KMS CMK) on every storage resource.
- [ ] No public network exposure for databases or caches.
- [ ] Backup retention matches RTO / RPO; restore drill completed at least once.
- [ ] PITR enabled where the engine supports it (CDB, TDSQL-C).
- [ ] CAM access scoped to specific buckets / instances; no wildcard resource.
- [ ] Lifecycle / TTL / snapshot retention configured so old data doesn't accumulate forever.
- [ ] For China accounts: CRR cross-border transfer legal basis documented.
- [ ] Monitoring + alarms set on the failure modes that actually wake people up.
