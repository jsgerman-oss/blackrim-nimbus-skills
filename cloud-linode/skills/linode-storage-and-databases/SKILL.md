---
name: linode-storage-and-databases
description: Design or audit Linode storage and database tiers — Block Storage Volumes, Object Storage, Backups, Managed Databases (Postgres / MySQL), and custom Images. Use when choosing a data store, modeling lifecycle and access patterns, sizing capacity, securing data, or planning recovery.
---

# Linode Storage and Databases

## When to use

- Choosing between Block Storage, Object Storage, and Managed Databases for a new workload.
- Designing backup and disaster-recovery strategy for a Linode environment.
- Sizing and configuring a Managed Database cluster (Postgres or MySQL).
- Auditing encryption, access controls, and retention for storage resources.
- Planning a recovery drill or verifying backup completeness.
- Migrating data from another provider to Linode storage.

## Decision tree

| Need | Service |
| --- | --- |
| Persistent block device attached to one instance | Block Storage Volume |
| Unstructured blobs, backups, static assets, data lake | Object Storage (S3-compatible) |
| Built-in full-system snapshots for a Compute Instance | Linode Backups |
| Relational ACID data store with HA, managed patching | Managed Database (Postgres or MySQL) |
| Custom base image to clone multiple instances | Linode Images |
| Shared POSIX filesystem across multiple instances | Not native to Linode — use NFS on a dedicated instance or a distributed filesystem. Linode has no equivalent of AWS EFS. |
| In-memory cache | Self-managed Redis/Valkey or Memcached on a Compute Instance. No managed cache service. |
| Full-text search | Self-managed OpenSearch or Elasticsearch on a Compute Instance. No managed offering. |

**Important limit:** Linode's managed storage surface is smaller than AWS. There is no equivalent of DynamoDB, Redshift, ElastiCache, or OpenSearch as a managed service. For any of those patterns, plan to run self-managed software on Compute Instances.

## Block Storage Volumes

- **Scope:** per-region. A Volume attaches to one instance in the same region; it cannot be attached to an instance in a different region.
- **Size:** 10 GB minimum; up to 10 TB per Volume; extendable online (filesystem resize is manual).
- **Attachment:** a Volume can only attach to one instance at a time. Detach before attaching elsewhere. Detaching while mounted without unmounting first can corrupt the filesystem.
- **Filesystem:** format as ext4 for general use. XFS is an option for large files / databases.
- **Encryption:** Volumes are encrypted at rest by default on the Linode infrastructure. You cannot supply your own encryption key — encryption is managed by Linode. For sensitive workloads requiring key control, use LUKS inside the Volume.
- **Performance:** NVMe-backed in most regions. I/O performance scales with Volume size — larger Volumes get higher IOPS. Check current IOPS specs per region.
- **Backups:** Linode Backups covers the instance root disk but does NOT automatically back up attached Volumes. Back up Volume data separately (snapshot via Linode snapshot API, rsync to Object Storage, or application-level backup).
- **Lifecycle:** Volumes persist independently of the instance. Deleting an instance does not delete an attached Volume (unless explicitly deleted). Volumes accrue charges while they exist regardless of attachment state.

## Object Storage

- **Compatibility:** S3-compatible API. Existing tools (boto3, s3cmd, MinIO client, rclone, aws-cli with endpoint override) work without code changes.
- **Scope:** per-region. Each region has its own endpoint (`<region>.linodeobjects.com`). There is no automatic cross-region replication; replicate manually with rclone or similar tools.
- **Access control:** Bucket-level ACL and bucket policies (subset of S3 policy syntax). Default buckets are private. Do not set a bucket to public-read unless you explicitly intend to serve public content.
- **Access keys:** Object Storage uses dedicated access keys (not Personal Access Tokens). Generate per-application keys with the minimum required scope. Rotate on a schedule.
- **TLS:** HTTPS-only. Plain HTTP is not supported.
- **CORS:** Configure per-bucket CORS if your frontend reads directly from Object Storage. Restrict `AllowedOrigins` to your domain, not `*`.
- **Static site hosting:** supported. Enable static website on the bucket. Use Akamai CDN (separately licensed) or a CloudFront-equivalent proxy in front for HTTPS with a custom domain + caching.
- **Versioning:** not natively supported on Linode Object Storage (unlike S3). If you need versioning, implement at the application layer or use a versioned naming convention.
- **Lifecycle rules:** limited lifecycle support (expiry rules). Not all S3 lifecycle actions are supported — verify the current feature matrix before relying on them.
- **Transfer:** Object Storage egress counts toward the regional transfer pool. Large-scale egress can exhaust the pool quickly — budget and monitor.

## Linode Backups

- **What it covers:** the Compute Instance's root disk and any additional disks in the instance's disk set. Does NOT cover attached Block Storage Volumes.
- **Schedule:** automatic daily, weekly, and biweekly snapshots retained per the plan (3 automatic + 1 manual slot). Not configurable to a finer schedule.
- **Manual snapshot:** one manual backup slot. Use it before major changes (OS upgrade, application migration).
- **Restore:** restore to the same or a different instance in the same region. Cross-region restore requires creating an Image from the backup, then deploying the Image in the target region.
- **Retention:** automatic backups rotate on the schedule. Manual snapshots persist until explicitly deleted.
- **Cost:** approximately 20% of the instance monthly price per instance. Budget for every stateful instance.
- **Not a substitute for application-level backups.** Linode Backups restore the full disk; they do not provide point-in-time database recovery. For databases, use `pg_dump`, `mysqldump`, or WAL archiving to Object Storage in addition to Linode Backups.

## Managed Databases

- **Engines:** PostgreSQL and MySQL. Check the current version matrix at deploy time — Linode tracks upstream but does not always offer the latest patch immediately.
- **Plans:** shared CPU and dedicated CPU plans. Dedicated CPU plans are strongly recommended for production — shared CPU introduces latency variability.
- **HA:** enable the High Availability (multi-node) configuration for any production database. This provisions a primary node + standby replica(s) with automatic failover. Single-node clusters are a SPOF.
- **Replicas:** HA plans include read replicas. The read replica connection string is separate from the primary — direct read-heavy queries to the read replica.
- **Scaling:** Managed Database plans are resized manually (select a larger plan; Linode migrates the data). There is no autoscaling. Right-size at provisioning and plan for manual upgrades.
- **Backups:** automatic daily backups are included. Manual backups available. Point-in-time recovery is supported for PostgreSQL (via WAL archiving managed by Linode); check current MySQL PITR support.
- **Access control:** connections are whitelisted by IP. Only whitelist the CIDRs of your application instances — not `0.0.0.0/0`. Linode Managed Databases do not have public endpoints by default; they are accessed via private IP in the same region.
- **Credentials:** the initial `root`/`linroot` password is set at cluster creation. Create named application users with minimal grants immediately after provisioning.
- **TLS:** all Managed Database connections require TLS. Linode provides the CA certificate for your cluster; validate it in your connection string (`ssl_ca=...`).
- **Limitations vs managed offerings at other providers:** No equivalent of Aurora auto-storage-scaling, no built-in read-through caching, no serverless tier, fewer engine version choices. Plan migrations further ahead.

## Linode Images

- **Purpose:** create a custom root disk image from a Compute Instance (or import a raw image) to use as a base for new deployments.
- **Size limit:** 6 GB (compressed) per Image. Keep images lean — install only the base OS and common tools; leave application deployment to cloud-init or Ansible.
- **Region:** Images are region-scoped but can be replicated to other regions via the Images API.
- **Use case:** golden image for a fleet of identical instances. Prefer cloud-init / Ansible for configuration management over baking application state into an image.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Relying on Linode Backups for database recovery | Backups are disk-level snapshots; they provide no PITR. Use application-level backup tools for databases. |
| Object Storage bucket set to public-read "for convenience" | Any object URL is publicly accessible; no auth required. Private by default, always. |
| Attaching a Block Storage Volume across regions | Volumes are regional; this is not supported. Cross-region data requires Object Storage + rclone or application-level replication. |
| Single-node Managed Database in production | One node = one point of failure and no failover. Enable HA for prod. |
| Whitelisting `0.0.0.0/0` for Managed Database access | Public database exposure. Whitelist only the application instance CIDRs. |
| Not verifying S3 lifecycle feature compatibility | Some S3 lifecycle actions are unsupported on Linode Object Storage; verify before designing on them. |
| Block Storage Volume left attached to a deleted instance | Volumes persist and bill. Audit and delete orphaned Volumes regularly. |
| Assuming Volumes are included in Linode Backups | They are not. Block Storage requires a separate backup strategy. |

## Security defaults

- Object Storage: buckets private by default; access via IAM-scoped Object Storage keys, not account-level tokens where possible. Enable TLS-only access (it is the only option). Restrict CORS origins.
- Managed Databases: TLS required; CA cert validated in connection string. Application users with minimal grants (`SELECT`, `INSERT`, `UPDATE`, `DELETE` on specific schemas — not `GRANT ALL`). IP whitelist contains only application instance private IPs.
- Block Storage: encrypt sensitive data at the application layer or with LUKS inside the Volume when key-controlled encryption is required.
- Backups: the manual backup slot should be used before any major change. Automated backup retention reviewed and understood.

## Observability defaults

- Managed Database: Cloud Manager shows CPU, memory, disk, and connections for the cluster. Set up an external alert on slow query rates and connection count approaching the plan's limit.
- Object Storage: no native access logging in Cloud Manager — send logs to an external monitoring tool or parse S3-compatible access logs (enable per-bucket if your workflow requires audit trails).
- Block Storage: monitor disk utilization from inside the instance (`df -h`, Longview disk metrics). Cloud Manager does not expose Volume-level I/O metrics.
- Backups: verify backup presence in Cloud Manager after enabling. Schedule a quarterly restore drill — untested backups cannot be trusted.

## Cost considerations

- Block Storage: billed per GB-month. Volumes that exist but are not attached still bill. Audit orphaned Volumes monthly.
- Object Storage: billed per GB stored + per-request + egress. Egress counts against the regional transfer pool. High-egress workloads (media delivery, large artifact downloads) will consume the pool quickly.
- Managed Databases: plan-based pricing includes storage up to the plan limit; storage overages apply. HA plans cost more than single-node — budget appropriately.
- Backups: ~20% of instance price per instance per month. Non-optional for production.
- Images: billed per GB stored. Keep images small; delete stale Images.

## IaC hints

- Terraform `linode_volume` for Block Storage; `linode_object_storage_bucket` and `linode_object_storage_key` for Object Storage.
- Terraform `linode_database_postgresql` and `linode_database_mysql` for Managed Databases. Set `cluster_size >= 3` for HA; `engine_config.innodb_flush_log_at_trx_commit = 1` for MySQL durability.
- Backups: `linode_instance.backups_enabled = true` in Terraform. Cannot control backup schedule via Terraform.
- Set `prevent_destroy = true` in Terraform `lifecycle` blocks for Managed Databases and production Volumes.
- For Object Storage access key rotation: create new key, update application secret, verify connectivity, then revoke old key — in that order.

## Verification checklist

- [ ] Backup strategy covers both Linode Backups (disk-level) and application-level database backups.
- [ ] Object Storage buckets are private by default; CORS restricted to known origins.
- [ ] Managed Database in HA mode for production; read replicas used for read-heavy queries.
- [ ] Database access whitelisted to application instance private IPs only; TLS verified.
- [ ] Block Storage Volumes tagged and inventoried; orphaned Volumes removed.
- [ ] Restore drill completed at least once; restore time measured against RTO.
- [ ] Egress / transfer pool budget reviewed against expected storage access patterns.
- [ ] `prevent_destroy` set on stateful IaC resources.
