---
name: hetzner-storage-and-databases
description: Design or audit Hetzner storage and database options — Cloud Volumes, Backups, Snapshots, Storage Box (SFTP / SMB / WebDAV / object), and how to pair with external managed databases. Use when picking a storage tier, sizing volumes, configuring retention, or selecting a managed database provider to run alongside Hetzner compute.
---

# Hetzner Storage and Databases

## When to use

- Choosing a storage tier for a Hetzner-hosted workload.
- Sizing and attaching Cloud Volumes to production servers.
- Designing a backup retention and recovery strategy.
- Evaluating Storage Box for off-server backups or shared assets.
- Selecting an external managed database provider to complement Hetzner compute.
- Auditing data-at-rest protection, lifecycle, and cross-location durability.

## Critical limitation: no native managed databases

**Hetzner does not offer managed Postgres, MySQL, Redis, or any other managed database service.** Unlike AWS RDS, Google Cloud SQL, or DigitalOcean Managed Databases, there is no Hetzner-native service that handles patching, failover, backups, or connection pooling for a relational or document store.

Your options:

| Approach | Trade-off |
| --- | --- |
| External managed DB (Crunchy Bridge, Neon, Aiven, PlanetScale) | You pay the managed service premium; you get patching, HA, PITR. |
| Self-hosted on Hetzner CCX dedicated vCPU servers | Full cost control; you own replication, backups, failover, upgrades. |
| Hybrid: Hetzner compute + Hetzner Storage Box for WAL archiving | Reduces managed-service cost for Postgres; still requires operational skill. |

Skills in this plugin surface this choice at every relevant decision point.

## Storage options

### Cloud Volumes

Block storage attached to a single Cloud server over the network. Hetzner implements volumes on Ceph-backed distributed storage within the same network zone.

Characteristics:

- Sizes: 10 GB to 10240 GB per volume; billed at €0.052/GB/mo.
- Attachment: one server at a time; format as ext4 or XFS.
- Cross-AZ semantics: volumes are **location-scoped** (e.g., `nbg1`). A volume cannot be attached to a server in a different location. To move data cross-location, take a snapshot, download, and restore.
- No cross-region attach. Hetzner does not offer global block storage.
- Performance: adequate for most application workloads; not optimized for high-IOPS database primaries on demanding workloads. For high-IOPS database use, prefer CCX dedicated servers with locally attached NVMe (Robot AX / EX) or co-locate the database on the server's local disk and rely on replication for durability.
- Resize online (expand only); shrinking requires unmount, resize2fs, and repartition.

```hcl
resource "hcloud_volume" "data" {
  name      = "data-vol"
  size      = 100
  server_id = hcloud_server.app.id
  automount = true
  format    = "ext4"
  location  = "nbg1"
}
```

### Backups (automated)

Automated daily snapshots of the entire server disk, managed by Hetzner.

- Cost: 20% of the server's hourly price (added to the server cost).
- Retention: 7 backup slots. Hetzner rotates on a weekly cycle — one backup per day of the week; oldest slot replaced each day.
- Location: same as the server. No cross-location backup.
- Enable with: `hcloud server enable-backup <server-id>` or `backup = true` in Terraform `hcloud_server`.
- Restore: creates a new server or restores in-place from the backup image.

Backups are not a substitute for application-level backups of individual databases. A backup captures the disk at a point in time; a PostgreSQL WAL-archived base backup gives you PITR. Use both.

### Snapshots (on-demand)

On-demand disk images of a server, stored in the same location.

- Cost: €0.01/GB/mo based on compressed image size.
- No automatic rotation; you must manage snapshot lifecycle in IaC or a cron.
- Use cases: pre-deploy checkpoint, golden server image for reprovisioning, migration source.
- Create with: `hcloud server create-image --type snapshot` after powering off the server (or from a running server — consistency not guaranteed for databases without `FLUSH TABLES WITH READ LOCK` or equivalent).

### Storage Box

Network-attached storage accessible over SFTP, SCP, Samba (SMB), WebDAV, Rsync, Borg, and Restic. **Not an S3-compatible object store** (no HTTP REST API, no presigned URLs). Positioned as a backup and file-share target, not a CDN origin or application blob store.

| Tier | Capacity | Price |
| --- | --- | --- |
| BX11 | 100 GB | ~€3.45/mo |
| BX31 | 500 GB | ~€8.90/mo |
| BX41 | 2 TB | ~€17.90/mo |
| BX61 | 5 TB | ~€34.90/mo |
| BX91 | 20 TB | ~€69.90/mo |

(Prices as of 2026-05; verify at hetzner.com/storage/storage-box.)

Billing model: flat monthly; no per-request or per-GB-egress fees from Storage Box to Hetzner servers within the same network (egress to the public internet is counted against your server's traffic allowance).

Use cases for Storage Box:

- Off-server PostgreSQL base backups and WAL segments (via `pgbackrest` or `wal-g`).
- Borg / Restic encrypted backup targets.
- Shared file assets accessed by multiple servers via SMB.
- Robot dedicated server backup destination when local disks are the primary storage.

Subaccount support: each Storage Box can have up to 200 subaccounts with separate credentials and directory scopes — useful for multi-tenant or per-service backup isolation.

## External managed database providers

When you need managed Postgres, MySQL, or Redis alongside Hetzner compute:

| Provider | Database(s) | Notes |
| --- | --- | --- |
| **Crunchy Bridge** | Postgres | Enterprise Postgres, EU data residency, PITR, HA included |
| **Neon** | Postgres (serverless) | Branch-per-PR workflow, autoscaling, generous free tier |
| **Aiven** | Postgres, MySQL, Redis, OpenSearch, Kafka | Multi-cloud, strong EU SLAs, VPC-peering-like trusted source IP |
| **PlanetScale** | MySQL-compatible | Branching schema changes, no foreign key enforced (Vitess) |
| **Supabase** | Postgres + Auth + Storage | BaaS platform; self-hostable for data sovereignty |

Connectivity from Hetzner compute to managed providers: use the provider's trusted-IP allowlist or VPN tunnel. Do not expose the database port to the public internet from either side.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Cloud Volume as sole database durability layer | Volume lives in one location; no replication. A location failure loses the volume. Use replication (streaming, logical) to a second server. |
| Backups enabled but never restore-tested | You discover the backup is unrecoverable during the incident. Restore drill quarterly. |
| Storage Box as an S3 replacement for app-served assets | No presigned URLs, no CDN integration, no HTTP GET endpoint. Use Cloudflare R2 or Backblaze B2 for object storage. |
| Relying on Hetzner backups alone for a database | Daily disk snapshot with no PITR = up to 23-hour data loss window. Add WAL archiving for Postgres, binlog archiving for MySQL. |
| Snapshot of a running database without a quiesce step | Disk snapshot during a write = torn page. For InnoDB / Postgres: `FLUSH TABLES WITH READ LOCK` or `pg_start_backup()` + stop replication lag before snapping. |
| Accumulating stale snapshots | €0.01/GB/mo adds up. A 100 GB snapshot after compression is typically ~30 GB = €0.30/mo × many = meaningful. Prune in IaC. |

## Security defaults

- Encrypt database backups before shipping to Storage Box; Borg and Restic both provide client-side encryption.
- Storage Box credentials (SFTP key or password) should be per-service subaccounts, not the root account.
- Cloud Volumes do not have at-rest encryption by default. For sensitive data, use LUKS on the volume before mounting: `cryptsetup luksFormat /dev/disk/by-id/<vol>`.
- WAL archive files should be encrypted at the application level (pgbackrest encryption, wal-g server-side SSE) before upload to Storage Box.
- Do not store database root credentials in cloud-init user_data or unencrypted environment files.

## Observability defaults

- Monitor volume disk usage; Hetzner does not alert on volume space. Add a disk-full alert in your external monitoring platform targeting the mount point.
- Track backup completion via the hcloud API (`hcloud server list-backups`) or export this check to a simple cron + alerting webhook.
- For external managed databases, use the provider's built-in monitoring plus a slow-query alert to your observability platform.
- Storage Box: monitor free space via SFTP or SMB `df`; alert before 85% capacity.

## Cost considerations

- Cloud Volumes at €0.052/GB/mo are significantly cheaper than AWS EBS (gp3 ~$0.08/GB/mo) and comparable to DigitalOcean Block Storage.
- Storage Box bulk tiers are cost-competitive for large backup archives; BX91 at 20 TB for ~€69.90/mo is hard to beat for cold backup storage.
- Self-hosted Postgres on a CCX13 (2 dedicated vCPU, 8 GB, ~€9.90/mo) + Storage Box WAL archiving + streaming replication to a secondary CCX13 costs less than most managed Postgres tiers at the same specs.
- Egress from Storage Box to Hetzner servers is free within the same network; egress to the internet counts against your server's traffic allowance.

## IaC hints

- Terraform: `hcloud_volume`, `hcloud_volume_attachment`. Set `automount = true` and `format = "ext4"` for new volumes; use `delete_protection = true` for production data volumes.
- Ansible: `hetzner.hcloud.hcloud_volume` for provisioning; `community.general.filesystem` + `ansible.posix.mount` for formatting and mounting.
- Storage Box: not managed by `hcloud` Terraform provider — use SSH key management via the Robot API or Hetzner panel.
- LUKS encryption: provision via cloud-init or Ansible `community.crypto.luks_device` module before the application boots.

## Verification checklist

- [ ] Cloud Volume has `delete_protection` enabled for production data.
- [ ] Automated backup enabled on every server with a stateful workload.
- [ ] Backup restore tested; restore procedure documented.
- [ ] PITR strategy documented for relational databases — WAL archiving enabled and tested.
- [ ] Storage Box credentials are subaccount-scoped; root account key not used in automation.
- [ ] Sensitive volumes encrypted with LUKS or application-level encryption.
- [ ] Snapshot lifecycle managed in IaC; stale snapshots pruned.
- [ ] External managed database (or self-hosted replication topology) chosen and justified against cost and operational model.
- [ ] Disk-space alert configured on all mounted volumes.
