---
name: oci-storage-and-databases
description: Design or audit OCI storage and database tiers — Object Storage (Standard, Infrequent Access, Archive), Block Volumes, Autonomous Database (ATP, ADW, AJD), MySQL HeatWave, NoSQL Database, File Storage Service, Exadata Cloud Service. Use when picking a data store, modeling access patterns, sizing, securing, or configuring lifecycle and backup policies.
---

# OCI Storage and Databases

## When to use

- Choosing between relational, document, key-value, object, block, and file storage.
- Sizing an Autonomous Database instance or deciding between serverless and dedicated infrastructure.
- Designing Object Storage lifecycle rules, retention locks, and cross-region replication.
- Hardening encryption, backups, and access policy for any data tier.
- Auditing egress paths, retention, and replication for compliance or cost.

## Decision tree

| Need | Service |
| --- | --- |
| Object storage — blobs, data lake, backups, static assets | Object Storage (Standard tier) |
| Infrequently accessed objects, cost-optimized at-rest | Object Storage — Infrequent Access tier |
| Long-term retention, compliance archives | Object Storage — Archive tier |
| Block storage attached to Compute or OKE node | Block Volume |
| POSIX shared filesystem across Compute instances | File Storage Service (FSS) |
| OLTP — Postgres/Oracle-compatible, managed | Autonomous Transaction Processing (ATP) |
| Analytics / data warehouse | Autonomous Data Warehouse (ADW) |
| JSON document workloads with Oracle-compatible SODA API | Autonomous JSON Database (AJD) |
| MySQL with in-memory analytics, zero-ETL HeatWave ML | MySQL HeatWave |
| Key-value / NoSQL, predictable latency, flexible schema | OCI NoSQL Database |
| Enterprise Oracle workloads, highest performance, dedicated infra | Exadata Cloud Service (ExaCS) |

## Object Storage defaults

- Bucket namespace is per-tenancy, automatically scoped. Object names are the only thing you control — use a prefix hierarchy like `<env>/<service>/<date>/`.
- Encryption: all objects encrypted at rest by Oracle-managed keys by default. Switch to a customer-managed Vault key for any bucket holding regulated or sensitive data — the per-bucket setting in the console or Terraform `kms_key_id`.
- Public access: disabled at bucket creation. Never enable object-level public access unless the content is genuinely meant for anonymous download; serve static assets via a CDN pre-authenticated request (PAR) or OCI CDN instead.
- Versioning: enable for any bucket that holds state, release artifacts, or backups. Versioning is per-bucket and irreversible once enabled.
- Lifecycle: configure a lifecycle rule to transition objects to Infrequent Access at 30 days and Archive at 90 days for workloads with cold-access patterns. Archive objects have a minimum storage duration of 90 days; model this in your cost projections.
- Retention rules: use time-based or event-based retention locks for compliance workloads. Locked retention rules cannot be shortened or deleted — test in a non-production bucket first.
- Replication: Object Storage replication copies to a destination bucket in another region asynchronously. Enable for DR scenarios; be aware replication adds egress transfer cost.
- Events: emit bucket and object events to OCI Events Service → trigger Functions or Notifications for pipeline orchestration.

## Block Volume defaults

- Performance tiers: Higher Performance (80 IOPS/GB, 15 MB/s/GB throughput) for databases; Balanced (60 IOPS/GB) for general workloads; Lower Cost (2 IOPS/GB) for bulk storage. Ultra High Performance (120 IOPS/GB) is available for dedicated attachment.
- Encryption: customer-managed Vault key on every production volume. The `kms_key_id` Terraform attribute covers both boot and data volumes.
- Backups: enable scheduled Block Volume backups (daily incremental, weekly and monthly full). For databases on Block Volume, coordinate backup windows with the DB engine.
- Cross-region replication: Block Volume cross-region replication is async and supports DR failover without manual snapshot copy. Enable for any volume holding persistent database state.
- Attachment: paravirtualized for most VM workloads; iSCSI attachment for Bare Metal and latency-sensitive workloads. Never share a Block Volume across multiple Compute instances simultaneously — use File Storage for shared access.

## Autonomous Database defaults

- Deployment model: **Serverless** (shared infrastructure) for development and workloads with variable demand. **Dedicated** Exadata infrastructure when you need tenant isolation, custom maintenance windows, or guaranteed IOPS for SLA commitments.
- Workload type: ATP for OLTP, ADW for analytics/DW, AJD for JSON document access. The workload type sets the optimizer defaults and pre-tuned resource allocation — pick the right one at creation; conversion requires a new database.
- OCPU / storage scaling: serverless ATP/ADW scale OCPUs and storage independently on demand. Enable auto-scaling to let the database expand up to 3× the provisioned OCPU count during peak load.
- Encryption: customer-managed Vault key (Bring Your Own Key — BYOK) for any ATP/ADW instance holding regulated data. Oracle TDE encrypts tablespaces; your Vault key wraps the TDE master key.
- Private endpoint: always use a private endpoint (private IP within your VCN subnet) for ATP/ADW in production. Public endpoints are development-only.
- Network access control list: scope the ACL to the CIDR blocks or VCN OCIDs of your application layer — deny all other origins even on private endpoints.
- Backups: automated daily backups with 60-day retention for ATP/ADW. Supplementary manual backups before schema migrations or data loads.
- Data Safe: register every ATP/ADW instance with OCI Data Safe to enable security assessment, user assessment, data masking, and activity auditing.

## MySQL HeatWave defaults

- HeatWave cluster: a MySQL HeatWave instance is a standard MySQL DB system; the HeatWave in-memory analytics cluster is an add-on that you enable separately. Enable the cluster only when you have analytics queries that benefit — it carries additional hourly cost.
- Shape: `MySQL.HeatWave.VM.Standard` for the DB system; HeatWave cluster shape is fixed (`HeatWave.512GB`). Provision the right number of HeatWave nodes for your data size.
- HA: enable MySQL High Availability (3-node group replication, standby is automatic failover) for production.
- Private access: MySQL DB system is always in a private subnet — no public IP.
- Encryption: customer-managed Vault key on the underlying Block Volume backing MySQL data.
- Backups: daily automatic backup enabled, 35-day retention.

## OCI NoSQL Database defaults

- Capacity mode: **On-Demand** for unpredictable or development workloads. **Provisioned** with explicit read/write unit allocation for steady-state production — provisioned is 30–50% cheaper at stable throughput.
- Table design: define composite primary keys carefully — full scan requires a secondary index. Schema is flexible but key cardinality determines throughput distribution.
- Encryption: customer-managed Vault key per table if the data is regulated.
- TTL: configure row TTL for ephemeral data (sessions, transient workflow state) to avoid accumulation.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Object Storage bucket with public access "temporarily" | Never gets reverted. Use PAR with expiry or OCI CDN for public-facing content. |
| Autonomous Database on a public endpoint | One mis-configured ACL = the database is internet-reachable. Private endpoint always. |
| Block Volume with Oracle-managed keys only | You cannot revoke access or audit key usage per-volume. Use customer-managed Vault keys for sensitive data. |
| MySQL HeatWave cluster left running with no analytics workload | HeatWave cluster billing is continuous — stop the cluster when not running analytics. |
| NoSQL provisioned capacity sized to average, not peak | Requests over provisioned units are throttled; NoSQL has no autoscaling — size for burst or use On-Demand mode. |
| Archive tier without modeling the retrieval cost | Archive-to-Standard restore is billable per-GB. Unexpected restores can cost more than the storage savings. |
| Autonomous Database without Data Safe | No visibility into privileged user activity, sensitive data exposure, or misconfiguration findings. |
| Backups without restore drills | An untested backup is a backup you don't have. Quarterly restore drill. |

## Security defaults

- Every storage resource uses a customer-managed Vault key — not Oracle-managed or service-managed keys — for any production or regulated data.
- Object Storage bucket policies restrict access by compartment and authenticated principal; no anonymous or `Allow {objectstorage-namespaces} to manage objects in tenancy` policies except in explicitly designated public compartments.
- Autonomous Database instances registered with Data Safe; privileged access reviews run quarterly.
- Block Volume cross-region replication destination compartment is locked to the DR tenancy team, not shared with the source compartment's operators.
- File Storage NFS exports allow the minimum source CIDR; mount target security list rules restrict access to the application subnet only.
- Object Storage pre-authenticated requests have an explicit expiry — never generate no-expiry PARs.

## Observability defaults

- Object Storage: emit usage metrics (bytes stored, requests) to OCI Monitoring; alarm on storage growth rate to detect runaway accumulation.
- Block Volume: IOPS, throughput, and latency metrics are automatically emitted; set alarms on `VolumeReadLatency` and `VolumeWriteLatency` exceeding SLA thresholds.
- Autonomous Database: Database Management is enabled by default; surface Performance Hub, SQL Monitoring, and AWR data for diagnosis.
- MySQL HeatWave: `mysql_metric` dimensions in OCI Monitoring; alarm on replication lag and connection count.
- NoSQL: alarm on throttled request rate; it signals that provisioned capacity needs adjustment.

## Cost considerations

- Object Storage Standard tier has no minimum retention; Infrequent Access has a 31-day minimum; Archive has a 90-day minimum. Model access patterns before tiering.
- Autonomous Database serverless charges per OCPU-hour; pause the database when idle in non-production environments.
- Block Volume cross-region replication adds per-GB replication transfer cost — evaluate against the RPO requirement.
- HeatWave cluster is separate billing from the MySQL DB system — run analytics queries in batch windows, then suspend the cluster outside those windows.
- File Storage charges per GB provisioned; clean up stale snapshots — they count toward billed capacity.

## IaC hints

- Terraform resources: `oci_objectstorage_bucket`, `oci_core_volume`, `oci_database_autonomous_database`, `oci_mysql_mysql_db_system`, `oci_nosql_table`, `oci_file_storage_file_system`.
- Set `prevent_destroy = true` in a `lifecycle` block on every stateful production resource.
- Object Storage lifecycle rules are managed via `oci_objectstorage_object_lifecycle_policy` — keep them in the same Terraform workspace as the bucket definition.
- Autonomous Database BYOK: supply `kms_key_id` and `vault_id` at creation time; key rotation is managed in the Vault service.

## Verification checklist

- [ ] Data store chosen from the decision tree, not convenience.
- [ ] Customer-managed Vault key configured for every regulated or production store.
- [ ] No public Object Storage bucket; no public Autonomous Database endpoint.
- [ ] Backup retention matches RTO/RPO targets; at least one restore drill documented.
- [ ] Lifecycle or TTL policies prevent unbounded data accumulation.
- [ ] Data Safe active on Autonomous Database instances.
- [ ] Alarms cover the failure modes that wake people up (storage full, latency spike, throttled requests).
- [ ] Access policies scoped to the minimum necessary compartments and principals.
