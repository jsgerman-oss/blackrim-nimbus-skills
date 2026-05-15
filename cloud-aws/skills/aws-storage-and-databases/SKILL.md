---
name: aws-storage-and-databases
description: Design or audit AWS storage and database tiers — S3, EBS, EFS, RDS / Aurora, DynamoDB, ElastiCache, OpenSearch, Redshift. Use when picking a data store, modeling access patterns, sizing, securing, or backing up data.
---

# AWS Storage and Databases

## When to use

- Choosing between relational, document, key-value, search, cache, and object storage.
- Designing DynamoDB partition / sort keys and GSIs from access patterns.
- Sizing an RDS / Aurora cluster and choosing a failover strategy.
- Hardening data-at-rest encryption, backups, and PITR.
- Auditing data egress, retention, lifecycle, and replication.

## Decision tree

| Need | Service |
| --- | --- |
| Object storage for blobs, backups, data lake, static assets | S3 |
| Block storage attached to an instance | EBS |
| Shared POSIX filesystem across compute | EFS (general) or FSx (Lustre / NetApp / Windows) |
| ACID, relational, joins, OLTP | RDS (Postgres / MySQL / MariaDB) or Aurora |
| Single-digit-ms key-value or document with known access patterns | DynamoDB |
| Sub-ms cache or pub/sub | ElastiCache (Redis / Valkey) or MemoryDB |
| Full-text / log search | OpenSearch |
| Petabyte analytics | Redshift, Athena (S3 + Glue), or Spark on EMR |
| Graph | Neptune |
| Time series | Timestream |

## S3 defaults

- Encryption: SSE-S3 minimum; SSE-KMS with a CMK for any data subject to access-audit requirements.
- Public access: **Block Public Access** on at the account level — use CloudFront + OAC for serving.
- Versioning: on for any bucket holding state, source artifacts, or backups.
- Lifecycle: transition to Standard-IA at 30 d, Glacier IR / Flexible at 90 d, Deep Archive at 365 d — tune to access reality.
- Object Lock: on for compliance / ransomware-recovery workloads.
- Replication (CRR / SRR): for DR, with replica encryption keys in the destination region.
- Notifications: `s3:ObjectCreated:*` → EventBridge for downstream pipelines, not legacy direct-to-Lambda.

## RDS / Aurora defaults

- Engine: prefer Aurora over plain RDS for Postgres / MySQL when you want fast failover, storage autoscaling, and read replicas across AZs.
- Multi-AZ: on for prod. Aurora replicates by default across 3 AZs; RDS Multi-AZ is a separate flag.
- Backups: 7 d retention minimum; 30 d for prod; longer if regulated. PITR on.
- Parameter group: never use default. Pin `rds.force_ssl=1`, `log_min_duration_statement=500`, `shared_preload_libraries=pg_stat_statements`.
- Encryption: KMS encrypted at rest; force `rds.force_ssl` for in-transit.
- Performance Insights: on (7 d free, 731 d retention is paid but cheap relative to debugging without it).
- Maintenance window: outside business hours; pin minor version updates to a known cadence.

## DynamoDB defaults

- Capacity: on-demand for unknown / spiky workloads; provisioned with autoscaling once steady-state is known (~30% cheaper).
- Keys: design from access patterns first, table second. Sketch all queries, then derive PK / SK / GSIs.
- Single-table design: yes for tightly-coupled bounded contexts; no when domains barely share queries.
- Streams: on if anything downstream cares about change events (search index, audit log, CDC).
- TTL: on for ephemeral data (sessions, idempotency keys) — saves storage and write amplification.
- Backups: PITR on; on-demand backup for releases and pre-migration snapshots.
- Global tables: only when active-active multi-region is a hard requirement — eventual consistency surprises are real.

## ElastiCache / MemoryDB defaults

- Engine: Valkey (open-source fork) or Redis OSS — Redis Enterprise license is rarely needed.
- Auth: AUTH token + in-transit TLS for any cluster reachable from app subnets.
- Encryption at rest: on.
- Cluster mode: enabled for any non-trivial cache to allow horizontal scale and online resharding.
- Eviction: `allkeys-lru` for general cache, `noeviction` for queues / sessions where loss = correctness bug.
- Multi-AZ replication groups for any workload where a stampede on cold cache hurts.

## OpenSearch defaults

- Domain: use OpenSearch Serverless for unpredictable usage; managed domains for predictable, large workloads.
- Dedicated master nodes: 3 odd-count for any prod cluster ≥ 3 data nodes.
- Encryption: at rest + node-to-node + HTTPS-only.
- Snapshots: automated daily to an S3 bucket in a separate account if regulated.
- Index lifecycle: ISM policies to roll over and warm-tier large indices.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| S3 bucket policy `*` to allow CloudFront | Hides a public-access bug behind two systems. Use OAC with a scoped principal. |
| RDS in a public subnet | One SG mis-edit and you're on Shodan. Private subnets, period. |
| DynamoDB modeled like a SQL table | Hot partitions, scans, fees. Model from access patterns. |
| ElastiCache without auth token | Cache poisoning becomes RCE-adjacent if values feed eval. |
| OpenSearch single-node "for cost" | Reindex storm = total outage. Use serverless or properly clustered. |
| Aurora Serverless v1 still in prod | EOL'd. Migrate to v2. |
| Snapshots without restore drills | Untested backups are wishes. Quarterly restore. |

## Security defaults

- All data-at-rest encrypted; KMS CMKs (not AWS-managed) for regulated data so you can revoke or audit per-key.
- Field-level encryption / tokenization for PII before storage where possible (CSE before S3 put, app-side encrypt before DynamoDB put).
- VPC endpoints (Gateway for S3 / DynamoDB; Interface for the rest) so data plane traffic stays off the public internet.
- IAM conditions: `aws:SecureTransport`, `aws:SourceVpc`, `s3:x-amz-server-side-encryption` to enforce posture by policy, not goodwill.
- Macie for S3 sensitive-data scanning if you have PII / PHI buckets.

## Observability defaults

- Database: slow-query logs + Performance Insights + an alarm on `DatabaseConnections`, `FreeableMemory`, `ReadIOPS` / `WriteIOPS`, `BurstBalance` (gp2) or `BurstCreditBalance` (RDS).
- DynamoDB: alarm on `ThrottledRequests`, `SystemErrors`, `UserErrors > baseline`, and consumed-capacity ratio for provisioned tables.
- S3: server-access logs to a logs bucket, plus CloudTrail data events for any bucket that matters for compliance.
- ElastiCache: `Evictions`, `CurrConnections`, `CPUUtilization`, `EngineCPUUtilization` (different for Redis vs node CPU).

## Cost considerations

- S3 Intelligent-Tiering for buckets where access is unpredictable; pure lifecycle rules for predictable cold data.
- Aurora I/O-Optimized vs Standard: cross over at ~25% of cluster cost going to I/O — calculate before picking.
- DynamoDB: GSIs are full table replicas — every GSI doubles write cost. Audit unused GSIs quarterly.
- RDS: reserved instances for steady-state baseline; on-demand for headroom.
- OpenSearch UltraWarm / cold storage for log retention > 30 d.
- S3 Requester Pays for large public-data buckets where you don't want to absorb egress.

## IaC hints

- CDK: `aws-cdk-lib/aws-s3`, `aws-cdk-lib/aws-rds`, `aws-cdk-lib/aws-dynamodb`. Use `RemovalPolicy.RETAIN` for any stateful resource in prod.
- Terraform: `terraform-aws-modules/s3-bucket`, `terraform-aws-modules/rds`, `terraform-aws-modules/dynamodb-table`. State for stateful resources in a separate workspace from compute.
- Always set deletion protection on RDS / Aurora / DynamoDB prod tables in IaC, not via console.

## Verification checklist

- [ ] Access patterns enumerated before schema chosen.
- [ ] Encryption at rest + in transit on every store.
- [ ] No public network exposure for databases or caches.
- [ ] Backup retention matches recovery objectives; restore drill done at least once.
- [ ] PITR / point-in-time recovery on where the engine supports it.
- [ ] IAM scoped to specific tables / buckets / keys; no `*` resources.
- [ ] Monitoring + alarms on the failure modes that actually wake people.
- [ ] Lifecycle / TTL configured so old data doesn't accumulate forever.
