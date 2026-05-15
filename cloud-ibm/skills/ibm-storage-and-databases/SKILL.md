---
name: ibm-storage-and-databases
description: Design or audit IBM Cloud storage and database tiers — Cloud Object Storage, Block/File Storage for VPC, Cloudant, Db2 on Cloud, Databases for PostgreSQL / Redis / MongoDB / Elasticsearch / etcd / RabbitMQ / MySQL, Hyper Protect DBaaS. Use when picking a data store, modeling access patterns, sizing, securing, or configuring backups.
---

# IBM Cloud Storage and Databases

## When to use

- Choosing between object, block, file, relational, NoSQL, and in-memory storage on IBM Cloud.
- Designing Cloud Object Storage bucket lifecycle, resilience tier, and encryption posture.
- Selecting a managed database from IBM Cloud Databases and sizing it.
- Deciding when Hyper Protect DBaaS (FIPS 140-2 Level 4) is required vs Key Protect-encrypted standard managed DBs.
- Auditing data-at-rest encryption, backups, retention, and access control.

## Decision tree

| Need | Service |
| --- | --- |
| Object storage for blobs, backups, data lake, static assets | Cloud Object Storage (COS) |
| Block storage attached to a VPC VSI | Block Storage for VPC |
| Shared POSIX-compatible filesystem across VPC compute | File Storage for VPC (NFS v4.1) |
| ACID relational, joins, OLTP | IBM Cloud Databases for PostgreSQL or MySQL |
| NoSQL document / JSON, CouchDB-compatible API | Cloudant |
| Single-digit-ms key-value cache or pub/sub | IBM Cloud Databases for Redis |
| Full-text search and analytics | IBM Cloud Databases for Elasticsearch |
| Enterprise relational (Db2 compatibility, warehousing) | Db2 on Cloud or Db2 Warehouse on Cloud |
| FIPS 140-2 Level 4 regulated database | Hyper Protect DBaaS (MongoDB or PostgreSQL) |
| etcd for Kubernetes backing store or service discovery | IBM Cloud Databases for etcd |
| Message queue with AMQP semantics | IBM Cloud Databases for RabbitMQ |

## Cloud Object Storage (COS)

### Storage classes

| Class | Use |
| --- | --- |
| Smart Tier | Default for buckets with unpredictable access — auto-transitions between tiers; no retrieval fee. |
| Standard | Frequently accessed data; lowest retrieval latency. |
| Vault | Data accessed less than once a month. |
| Cold Vault | Archival; accessed rarely; highest retrieval latency. |
| Flex | Workloads with predictable but low-frequency access (batch analytics, backups). |

### Resilience tiers

| Tier | When |
| --- | --- |
| Cross-Region | Maximum availability across three geographically separated regions (e.g., `us-geo`). Use for DR-critical data that must survive a full regional event. |
| Regional | Data replicated within one region across multiple data centers. Default for most production workloads. |
| Single Data Center | Lower cost; no cross-data-center replication. Development and non-critical data only. |

### Defaults

- Encryption: COS encrypts all data at rest by default with IBM-managed keys. For regulated workloads, bring a customer root key from **Key Protect** (BYOK) or **Hyper Protect Crypto Services** (KYOK / FIPS 140-2 L4).
- Public access: disable public access on all buckets by default. Serve content via **Cloud Internet Services** or a VPC Load Balancer with a COS private endpoint.
- Versioning: on for any bucket holding state, source artifacts, or regulated data.
- Object lifecycle: configure expiration and transition rules — don't accumulate indefinitely. Example: transition to Vault at 30 d, Cold Vault at 90 d, expire at 365 d for audit logs.
- Immutability: Object Lock (WORM) for compliance / ransomware-protection use cases.
- Replication: configure COS bucket replication for cross-region DR requirements.
- Private endpoints: always use private endpoints (`s3.private.<region>.cloud.ibm.com`) from VPC workloads to keep traffic off the public internet.
- Activity Tracker events: enable COS management and data events for compliance-relevant buckets.

## Block Storage for VPC

- Volume profile: `general-purpose` (3 IOPS/GB, up to 16,000 IOPS) for most workloads; `5iops-tier` (5 IOPS/GB) for databases and high-throughput apps; `10iops-tier` (10 IOPS/GB) for latency-sensitive database primaries; `custom` when requirements don't match a tier.
- Encryption: Key Protect or Hyper Protect Crypto Services root key for customer-managed encryption — never IBM-managed key for regulated data.
- Detach data volumes from instance lifecycle: boot volume for OS, separate data volume for persistent state — makes the instance disposable.
- Snapshots: automate block storage snapshots for point-in-time recovery. Retain snapshots in a separate Resource Group.
- Cross-regional snapshots: copy snapshots to another region for DR.

## File Storage for VPC

- NFS v4.1 file shares attached to multiple VPC VSIs simultaneously — useful for shared config, CMS assets, or legacy app data that requires POSIX semantics.
- Profile: `dp2` (defined performance, up to 96,000 IOPS) for high-throughput shared workloads.
- Encryption: customer-managed root key (Key Protect or HPCS) mandatory for production.
- Mount helper: use `ibmcloud is share-mount-targets` to create mount targets in the VPC; mount via the private endpoint DNS name.
- Replication: File Storage for VPC supports replication to another zone in the same region for HA.

## IBM Cloud Databases (ICD)

IBM Cloud Databases is the family of fully managed open-source databases: PostgreSQL, MySQL, Redis, MongoDB, Elasticsearch, etcd, RabbitMQ.

### Defaults for all ICD services

- Plan: `Standard` minimum; `Enterprise` for single-tenant dedicated hardware (HIPAA, regulated workloads).
- Encryption: all ICD instances encrypt at rest with IBM-managed keys by default. Specify a Key Protect root key CRN at provisioning time for BYOK.
- Private endpoints: always connect via private service endpoints from VPC workloads. Disable public endpoints after provisioning if not needed.
- Backups: ICD takes daily automated backups with 30-day retention for Standard plan. PITR on for PostgreSQL and MySQL.
- TLS: enforced for all connections; certificate available from the service credentials.
- Admin passwords: rotate immediately after provisioning; store in IBM Cloud Secrets Manager.
- Scaling: scale memory, disk, and CPU independently in ICD — set autoscaling policies to trigger on disk usage > 80% and memory usage > 90%.

### ICD for PostgreSQL specifics

- Version: pin to a supported major version; major upgrades require a restore-from-backup migration path.
- Connection pooling: use PgBouncer sidecar or IBM Cloud Databases connection string with `?sslmode=verify-full`.
- Read replicas: available in `Standard` plan; use for analytics offload or geographic distribution.
- Extensions: most standard extensions available; `pg_stat_statements` and `pgcrypto` are common production additions.

### ICD for Redis specifics

- Eviction: `allkeys-lru` for general-purpose cache; `noeviction` for session storage or queues where data loss = correctness bug.
- Cluster mode: Standard plan uses a single replica pair; Enterprise plan gives cluster mode for horizontal scale.
- TLS: mandatory; use `rediss://` scheme in connection strings.

## Cloudant

Cloudant is IBM Cloud's managed Apache CouchDB-derived NoSQL service — document-oriented, JSON-native, HTTP API, conflict resolution built in.

- Use for: mobile sync, geographically distributed writes, IoT telemetry, content management, CouchDB-compatible migrations.
- Pricing model: `Standard` (provisioned throughput — reads, writes, queries per second) or `Lite` (free tier, dev only).
- Throughput: set `targetThroughput` for reads, writes, and global queries — under-provisioning throttles with 429 responses.
- Replication: Cloudant supports continuous replication for active-active / active-passive multi-region setups.
- Design documents: define indices via `_design` documents — secondary indices are the access path for queries; missing indices cause expensive `_all_docs` scans.
- Authentication: IAM-based authentication (preferred) or Cloudant legacy credentials. Always use IAM with a Service ID or Trusted Profile.
- Encryption: at rest with Key Protect BYOK; in transit via HTTPS only.

## Db2 on Cloud

Enterprise-grade relational database, Db2 SQL-compatible. Primary use cases: lift-and-shift of Db2 workloads, SAP connectivity, analytics federation.

- Plan: `Standard` (shared multi-tenant) or `Enterprise` (single-tenant, dedicated). Enterprise required for HIPAA or FedRAMP-regulated workloads.
- High availability: `Enterprise` plan includes high-availability pairs across zones.
- Encryption: IBM-managed by default; BYOK via Key Protect for Enterprise plan.
- Backup: automated daily backups, 14-day retention on Standard; configurable on Enterprise.

## Hyper Protect DBaaS

Hyper Protect DBaaS provides **FIPS 140-2 Level 4** certified hardware security modules for database key management — the highest hardware assurance available on a public cloud. Use when regulatory requirements demand KYOK (Keep Your Own Key) for the database encryption master key, and when the HSM root of trust must be physically tamper-evident.

- Supports: MongoDB and PostgreSQL.
- Regions: available in `us-south`, `us-east`, `eu-de` (Financial Services-validated).
- Operator console: protected by Hyper Protect — even IBM cannot access the keys or plaintext data.
- Choose Hyper Protect DBaaS when: FedRAMP High, EU data sovereignty with hardware guarantee, financial services workloads requiring key custody proof.
- KYOK: the customer holds the master key in an HPCS instance; Hyper Protect DBaaS wraps database encryption keys with it. IBM has zero access to the plaintext key.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| COS bucket with public access enabled | One misconfiguration = data exposure. Always private + CIS / Load Balancer front. |
| ICD instance with public endpoints left open after provisioning | Unnecessary attack surface. Disable public endpoint; use private only. |
| Cloudant without defined secondary indices | Queries fall back to `_all_docs` scans; performance collapses at scale. |
| Block volume without snapshot policy | No point-in-time recovery. Data volume corruption = total loss. |
| ICD admin credentials not rotated post-provisioning | Default credentials are long-lived. Rotate immediately; store in Secrets Manager. |
| Sharing a COS HMAC key across multiple services | Key rotation affects all consumers. Use separate Service ID credentials per service. |
| ICD for PostgreSQL without PITR enabled | PITR requires `Standard` plan — confirm it's on at provisioning. |
| Hyper Protect DBaaS when Key Protect BYOK is sufficient | HPCS + HPDBAS is operationally heavier. Match assurance level to actual requirement. |

## Security defaults

- All data at rest encrypted: IBM-managed key minimum; Key Protect BYOK for production; HPCS KYOK for regulated / financial services.
- Private endpoints only for VPC-to-database traffic — no data traverses the public internet.
- IAM Service IDs or Trusted Profiles with least-privilege roles (`Reader`, `Writer`, `Manager`) for database access — never Account Admin.
- COS bucket policies restrict `s3:GetObject` / `s3:PutObject` to specific Service IDs; no wildcard `*` principals.
- TLS enforced in transit for all database connections (`sslmode=verify-full` for PostgreSQL; `rediss://` for Redis; HTTPS for Cloudant and COS).
- Activity Tracker events for all ICD and COS management operations.
- Secrets Manager for all database credentials; rotate on a defined schedule.

## Observability defaults

- IBM Cloud Monitoring (Sysdig): platform metrics for ICD (connections, disk usage, memory, replication lag), COS (request rates, error rates), Block/File Storage (IOPS, throughput).
- IBM Cloud Logs: application-level database query logs for slow-query detection; ICD provides log forwarding to IBM Cloud Logs.
- Activity Tracker: management-plane events for all resource creates, deletes, and key rotations.
- Alerts: disk usage > 80%, connection count approaching limit, replication lag > threshold, backup failure.

## Cost considerations

- COS Smart Tier: no retrieval fee and auto-tiering make it the lowest-risk default for buckets with uncertain access patterns. Standard class only when you're certain of frequent access.
- ICD: scale disk, memory, and CPU independently — don't over-provision all three uniformly. Disk is typically the binding constraint for databases.
- IBM Cloud Subscriptions apply to ICD: commit monthly spend for 10–30% discounts vs on-demand.
- Cloudant throughput: under-provision and monitor 429 response rates; scale up only when throttling is observed. Over-provisioning throughput is expensive.
- Block Storage IOPS tiers: `general-purpose` (3 IOPS/GB) handles most workloads; upgrade to `5iops-tier` only when measured IOPS saturation occurs.
- Cross-region COS replication: egress charges apply per GB replicated. Evaluate whether Cross-Region resilience tier (built-in) meets DR requirements instead.

## IaC hints

- Terraform resources: `ibm_resource_instance` (COS, Cloudant, ICD instances), `ibm_cos_bucket`, `ibm_database` (ICD).
- COS: `ibm_cos_bucket` with `key_protect_key_crn` or `kms_key_crn` for BYOK.
- ICD: `ibm_database` resource with `key_protect_key_crn` at provisioning; `auto_scaling` block for disk / memory policies.
- Block Storage: `ibm_is_volume` with `encryption_key` set to Key Protect key CRN.
- Stateful resources: use `lifecycle { prevent_destroy = true }` for production ICD instances and COS buckets holding live data.
- IaC state: keep database resource state in a separate Terraform workspace from compute to prevent accidental co-destruction.

## Verification checklist

- [ ] Storage class and resilience tier chosen deliberately (COS Smart Tier unless access pattern is known).
- [ ] Customer-managed encryption key set at provisioning time (cannot be added post-creation for some ICD services).
- [ ] Public endpoints disabled for all ICD instances in production.
- [ ] Private endpoint DNS configured and tested from VPC.
- [ ] Backup retention matches recovery objectives; restore drill completed at least once.
- [ ] PITR confirmed on for PostgreSQL and MySQL ICD instances.
- [ ] IAM roles scoped to minimum: Reader / Writer / Manager as needed.
- [ ] Secrets Manager holds all credentials; rotation schedule defined.
- [ ] IBM Cloud Monitoring alerts on disk, connections, and backup status.
- [ ] Deletion protection (`prevent_destroy`) on all production stateful resources.
