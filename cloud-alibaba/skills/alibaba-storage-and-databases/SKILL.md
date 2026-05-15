---
name: alibaba-storage-and-databases
description: Design or audit Alibaba Cloud storage and database tiers — OSS, EBS cloud disks, NAS, RDS (MySQL/Postgres/SQL Server/MariaDB), PolarDB, ApsaraDB for MongoDB / Redis, Lindorm, AnalyticDB. Use when picking a data store, modeling access patterns, sizing, securing, or configuring lifecycle and backup.
---

# Alibaba Storage and Databases

## When to use

- Choosing between relational, document, key-value, wide-column, analytics, and object storage.
- Designing OSS lifecycle rules, cross-region replication, or bucket-level access policy.
- Sizing an RDS or PolarDB cluster, picking a failover strategy, or enabling PITR.
- Selecting between PolarDB and RDS for a new relational workload.
- Hardening encryption, backups, and replication on any data store.
- Auditing data egress, retention, and residency requirements for China-region compliance.

## Decision tree

| Need | Service |
| --- | --- |
| Object storage for blobs, backups, data lake, static assets | OSS |
| Block storage attached to an ECS instance | EBS (cloud disk) |
| Shared POSIX filesystem across compute | Apsara File Storage NAS (standard or extreme) |
| High-throughput parallel filesystem (HPC) | Apsara File Storage CPFS |
| ACID relational OLTP, well-known engine | RDS (MySQL / Postgres / SQL Server / MariaDB) |
| Cloud-native relational, fast failover, scale-out reads, up to 100 TB | PolarDB (MySQL / Postgres / Oracle-compat) |
| Single-digit-ms document or key-value | ApsaraDB for MongoDB |
| Sub-ms cache or pub/sub, sorted sets | ApsaraDB for Redis |
| Wide-column, time series, full-text, hybrid | Lindorm (HBase-compatible + extensions) |
| Petabyte MPP analytics, SQL at scale | AnalyticDB for MySQL or AnalyticDB for PostgreSQL |

## OSS defaults

- Storage class: **Standard** for hot data; **Infrequent Access (IA)** after 30 d; **Archive** after 90 d; **Cold Archive** after 365 d. Set lifecycle rules from day one.
- Encryption: **SSE-OSS** (server-managed) minimum; **SSE-KMS** with a CMK for any data subject to access-audit, compliance, or residency requirements. **SSE-C** (customer-provided key) only when you control key material in-process.
- Block Public Access (BPA): **on at the bucket level by default**. Never expose a bucket publicly to serve content — use CDN + private origin with a signed URL or RAM STS token.
- Versioning: on for any bucket holding state, source artifacts, or backups.
- Cross-region replication: for DR or data-residency purposes; note China ↔ International replication is **not available** — both buckets must be in the same account type (China or International).
- Object Lock (WORM): on for compliance / ransomware-recovery buckets.
- Transfer Acceleration: available for OSS uploads/downloads from external networks; billed separately.
- Notifications: `PutObject` / `DeleteObject` events → EventBridge or MNS for downstream pipelines.
- Access logs: enable OSS access logging to a separate log bucket; set lifecycle on the log bucket.

## EBS cloud disk defaults

- Disk type: **ESSD PL1** as the general-purpose default (3000 IOPS/GB up to a cap, lower cost than PL2/PL3). **ESSD AutoPL** for workloads with variable peak I/O — auto-scales IOPS within a range.
  - PL0: dev/test, lower IOPS ceiling, cheapest.
  - PL1: production general-purpose OLTP.
  - PL2: databases with sustained high throughput; higher provisioned IOPS.
  - PL3: latency-critical, highest IOPS tier (max 1M IOPS on large disks).
- Encryption: enable at disk creation; KMS CMK for regulated workloads.
- Snapshots: automated snapshot policy at least daily; retain 7 d minimum, 30 d for production.
- Separate root disk from data disk: root disk size for OS + logs only; data on a dedicated attached disk so the root stays replaceable.
- Disk resizing: online expansion supported for ESSD; no downtime for capacity increase.

## RDS defaults

- Preferred engine: **PolarDB** (see below) for most new MySQL/Postgres workloads. Use RDS when licensing (SQL Server, MariaDB) or operator preference favors vanilla engine.
- High-availability: **High-availability Edition** (two-node, standby in same zone or cross-zone) for all production workloads. Three-zone HA for stricter RPO.
- Backups: 7 d retention minimum; 30 d for production; log backup retention to enable PITR. Enable automated backup during the maintenance window.
- SSL/TLS: force SSL on (`require_secure_transport = ON` for MySQL; `ssl = on` for Postgres).
- Parameter group: create a custom parameter group; pin `slow_query_log=ON`, `long_query_time=1`, `max_connections` tuned to instance class.
- Encryption at rest: KMS CMK.
- Database Proxy: use RDS Proxy for read/write splitting and connection pooling; reduces connection overhead on large ECS fleets.
- Maintenance window: schedule outside business hours; test minor version upgrades in staging first.

## PolarDB defaults

PolarDB is the preferred choice for new MySQL and Postgres workloads. It is Alibaba's cloud-native engine, sharing storage across a writer + up to 15 read nodes.

- Edition: **PolarDB Enterprise** for production (SLA, parallel query, HTAP). **PolarDB Standard** for dev/staging.
- Storage: shared pool auto-grows to 100 TB; no manual resize step.
- Read nodes: add read nodes independently from write scaling.
- Failover: ~30 s automatic failover (vs minutes for RDS); no shared-nothing architecture means the new writer has all data immediately.
- PITR: down to seconds; enable log backup to OSS.
- SQL acceleration: enable **Parallel Query** for analytical queries on the same cluster (HTAP lite); for heavy analytics keep a separate AnalyticDB.
- Global Database Network (GDN): active-active cross-region replication for PolarDB MySQL. Note: China ↔ International regions cannot join the same GDN.

## ApsaraDB for MongoDB defaults

- Architecture: **Replica Set** (3-node) for most workloads; **Sharded Cluster** only when data volume > 1 TB or write throughput exceeds RS limits.
- Storage engine: WiredTiger (default, always use).
- SSL: enforce TLS (`net.tls.mode = requireTLS`).
- Auth: SCRAM-SHA-256; disable anonymous access.
- Encryption at rest: KMS CMK.
- Backups: automated daily; 7 d retention; enable log backup for PITR.
- Connection string: use the VPC private endpoint; never expose MongoDB ports publicly.

## ApsaraDB for Redis defaults

- Architecture: **Standard (master-replica)** for simple cache and pub/sub; **Cluster Edition** for throughput > 100K QPS or dataset > 64 GB.
- Version: Redis 7.x preferred; pin the major version.
- Auth: set a strong password (`requirepass`); enable TLS in transit.
- Encryption at rest: on.
- Eviction: `allkeys-lru` for pure cache; `noeviction` for queue / session workloads where loss = bug.
- Persistence: RDB + AOF for workloads where Redis is primary storage; RDB-only for pure cache (faster restart).
- Backups: daily automated backup + manual snapshot before any major change.

## Lindorm defaults

- Use cases: IoT time-series, log ingestion, user-behavior data, wide-column hybrid.
- Engines: Wide Table (HBase-compatible), Time Series (Prometheus-compatible), Search (Lucene-based full-text), File.
- Write path: direct SDK or Kafka-sourced ingestion via Lindorm Streams; align batch size to TTL and compaction strategy.
- TTL: set at the column-family or table level for time-series data; avoid unbounded growth.
- Encryption: on; KMS CMK for regulated data.

## AnalyticDB defaults

- AnalyticDB for MySQL: OLAP-optimized; columnar storage; strong for reporting on hundreds of billions of rows.
- AnalyticDB for PostgreSQL: Greenplum-compatible MPP; better for teams with Postgres skills or complex SQL.
- Node sizing: Elastic mode (auto-scale storage, pay per compute hour) for unpredictable workloads; Reserved mode for predictable steady-state.
- Data ingestion: DataWorks / DTS for bulk load; OSS external tables for Athena-like on-demand queries without copying.
- Partition: mandatory for large tables; always partition on a time or categorical column.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| OSS bucket with public read ACL | One mis-configuration exposes all objects globally. Use CDN with signed-URL or STS tokens. |
| RDS in a public VSwitch | Direct internet exposure of the database port; private VSwitch + Security Group only. |
| PolarDB in a shared account with dev users | Dev users with RDS permissions can read prod data. Separate account or at minimum separate RAM policies. |
| Redis without TLS and password | Cache poisoning is exploitable if cache values feed execution paths. |
| MongoDB Sharded Cluster below 1 TB | Operational complexity without need; chunk rebalancing blocks CPU under heavy write load. |
| ESSD PL3 "for performance" without measuring | PL3 costs ~4× PL1; measure actual IOPS and latency before committing. |
| OSS lifecycle rules never set | Cold data stays in Standard tier indefinitely, silently accumulating cost. |
| Cross-region replication China ↔ International | Not supported; attempting it will fail or require application-level dual-write. |

## Security defaults

- All data-at-rest encrypted; KMS CMK (not service-managed key) for any regulated, PII-containing, or audit-required store.
- VPC endpoints (internal OSS endpoint, RDS internal endpoint, etc.) to keep data-plane traffic on the Alibaba backbone — never through NAT.
- Security Group: database SGs reference application SGs by group ID; never `0.0.0.0/0` on any DB/cache port.
- SDDP (Sensitive Data Discovery and Protection): scan OSS buckets and RDS instances holding PII; classify findings before designing access policy.
- OSS BPA (Block Public Access): on at bucket creation; review off before any public-access exception.
- Backup encryption: snapshots and backup files inherit disk/DB encryption; verify backup restoration returns encrypted data.
- China data-residency: data stored in `cn-*` regions cannot be replicated to International regions without a CAC cross-border data-transfer assessment; plan accordingly.

## Observability defaults

- RDS / PolarDB: CloudMonitor alarms on `ConnectionsUsed`, `CPUUsage`, `IOPS`, `DiskUsage`, `ReplicationDelay`. Enable slow-query log.
- Redis: alarms on `UsedMemory`, `CommandLatency`, `Evictions`, `ConnectionsRejected`.
- OSS: SLS or CloudMonitor for request count, error rate, bandwidth, and storage size per bucket.
- AnalyticDB: query duration P99 and concurrent query queue depth.
- Lindorm: write latency and compaction queue depth.

## Cost considerations

- **OSS storage tiers matter**: Standard → IA saves ~45%; Archive saves ~80%. Automate with lifecycle rules.
- **ESSD AutoPL** for variable workloads can significantly reduce over-provisioning vs fixed PL2/PL3.
- **PolarDB compute billing**: Elastic mode charges per hour when active; Serverless mode (Postgres only) scales to zero for dev environments.
- **AnalyticDB Elastic mode**: pause the cluster outside business hours for batch-reporting workloads.
- **Redis Cluster Edition**: only when you actually need it; Standard mode is cheaper for < 100K QPS.
- **RDS Reserved Instances**: buy after 30+ days of stable usage to ensure correct instance class selection.
- **OSS CDN origin**: serving through CDN reduces OSS egress charges; origin traffic through internal endpoint avoids NAT fees.

## IaC hints

- Terraform: `alicloud_oss_bucket`, `alicloud_db_instance` (RDS), `alicloud_polardb_cluster`, `alicloud_mongodb_instance`, `alicloud_kvstore_instance` (Redis), `alicloud_lindorm_instance`, `alicloud_analyticdb_postgresql_instance`. Provider ≥ 1.220.
- Set `deletion_protection = true` / `deletion_protection_enabled = true` on all production data stores.
- OSS bucket lifecycle in `alicloud_oss_bucket_object_acl` + `alicloud_oss_bucket_lifecycle` resources; manage in the same workspace as the bucket.
- State for stateful resources in a separate Terraform workspace or ROS stack from compute.

## Verification checklist

- [ ] Access patterns enumerated before data store chosen; OSS vs database boundary explicit.
- [ ] Encryption at rest (KMS CMK) on every store; in-transit TLS enforced.
- [ ] No data store directly reachable from public internet (VPC + Security Group; no public endpoint).
- [ ] Backup retention ≥ 7 d; PITR on for RDS/PolarDB.
- [ ] Restore drill done at least once before production traffic.
- [ ] Lifecycle / TTL rules configured; no unbounded data accumulation.
- [ ] SDDP scan run or scheduled for PII-adjacent buckets and tables.
- [ ] China ↔ International replication constraint acknowledged in design.
- [ ] Deletion protection on in IaC for every production data store.
- [ ] Cost tier (OSS storage class, ESSD level, RDS edition) justified by measured I/O profile.
