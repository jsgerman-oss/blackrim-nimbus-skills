---
name: azure-storage-and-databases
description: Design or audit Azure storage and database tiers — Blob Storage, ADLS Gen2, Azure Files, Azure SQL DB, Cosmos DB, PostgreSQL / MySQL Flexible Server, Azure Cache for Redis Enterprise, Synapse Analytics. Use when picking a data store, modeling access patterns, sizing, securing, or backing up data.
---

# Azure Storage and Databases

## When to use

- Choosing between relational, document, key-value, analytical, and object storage on Azure.
- Modeling Cosmos DB partition keys and indexing policies from access patterns.
- Sizing an Azure SQL DB or Cosmos DB tier and selecting a failover strategy.
- Hardening data-at-rest encryption, backups, and point-in-time restore.
- Auditing data egress, lifecycle policies, retention windows, and geo-replication.

## Decision tree

| Need | Service |
| --- | --- |
| Object storage for blobs, backups, data lake, static assets | Azure Blob Storage |
| Hierarchical namespace for big-data analytics pipelines | Azure Data Lake Storage Gen2 (Blob + HNS enabled) |
| Shared POSIX / SMB filesystem across compute | Azure Files (Premium for IOPS-sensitive) |
| ACID, relational, joins, OLTP | Azure SQL Database (Hyperscale for > 4 TB or unpredictable IOPS; serverless for dev/test) |
| Single-digit-ms NoSQL with known partition key | Cosmos DB NoSQL API |
| MongoDB-compatible document store | Cosmos DB for MongoDB (vCore mode for larger workloads) |
| Cassandra-compatible wide-column | Cosmos DB for Apache Cassandra |
| Open-source PostgreSQL OLTP | Azure Database for PostgreSQL Flexible Server |
| Open-source MySQL OLTP | Azure Database for MySQL Flexible Server |
| Sub-ms cache, sessions, leaderboards, queues | Azure Cache for Redis Enterprise |
| Petabyte analytics, data warehouse | Azure Synapse Analytics (dedicated SQL pool or serverless) |

## Blob Storage defaults

- Access tier: **Hot** for frequently accessed data, **Cool** for > 30-day-old infrequent data, **Cold** for > 90-day, **Archive** for > 180-day compliance retention. Use lifecycle management rules to automate transitions.
- Encryption: Microsoft-managed keys by default; migrate to **customer-managed keys (CMK) stored in Key Vault** for any data subject to access-audit or revocation requirements.
- Public access: disable `allowBlobPublicAccess` at the storage account level. Serve static content via Azure Front Door or CDN with an origin pointing to the private endpoint — not a public blob container.
- Versioning: enable for any bucket holding state, source artifacts, configuration, or backups.
- Soft delete: blob-level soft delete (7-day minimum) plus container-level soft delete for accidental deletion recovery.
- Shared key: set `allowSharedKeyAccess: false`; access via Managed Identity + Azure RBAC (Storage Blob Data Contributor / Reader roles scoped to the container, not the account).
- ADLS Gen2: enable hierarchical namespace (`isHnsEnabled: true`) at creation — it cannot be enabled post-creation. Use ACLs at the directory level for fine-grained data lake access control; RBAC at the account level for admin operations.

## Azure SQL Database defaults

- Tier: **General Purpose** for most OLTP; **Business Critical** for read replica, local SSD, and ~99.99% SLA; **Hyperscale** when database exceeds 4 TB or IOPS requirements are unpredictable.
- Serverless: appropriate for development and intermittent workloads — auto-pause after idle period, per-vCore billing. Not for production latency-sensitive paths.
- High availability: Availability Zone-redundant deployment for Business Critical and Hyperscale tiers; General Purpose with zone-redundancy preview for cross-AZ SLA.
- Backups: automatic full / differential / log backups with 7-day PITR minimum; 35-day retention for regulated workloads. Long-term retention (LTR) to Blob Storage for compliance.
- Encryption: Transparent Data Encryption (TDE) with CMK in Key Vault (Bring Your Own Key). Enforce TLS 1.2 minimum for transport; set `minimalTlsVersion: '1.2'`.
- Auditing: enable SQL auditing to a Log Analytics workspace; alert on failed logins and privileged operations.
- Microsoft Defender for SQL: on for Advanced Threat Protection — surfaces SQL injection attempts and anomalous access.
- Connection: Managed Identity-based authentication via Azure AD (Entra ID); disable SQL authentication for human access. Allow SQL auth only for legacy application migration paths with a documented exception.

## Cosmos DB defaults

- Consistency: **Session** consistency as the default — matches most OLTP expectations and costs significantly less than Strong. Use Bounded Staleness only for specific cross-region read requirements.
- Partition key: design from access patterns first. Hot-partition detection is available in Azure Monitor; instrument from day one.
- Throughput: **Autoscale** provisioned throughput for unpredictable workloads; manual RU/s for steady predictable traffic (~20% cheaper). Serverless for truly sporadic dev/test usage.
- Multi-region writes: only when active-active multi-region is a hard requirement — conflicts are real and require resolution logic.
- Indexing: exclude paths you never query (`"path": "/*", "kind": "None"` in the exclusion list) to reduce write amplification.
- Backups: periodic backup mode (minimum); **continuous backup mode** (7 or 30 days) for PITR on any production container.
- Private endpoint: mandatory for any production Cosmos DB account; disable public network access.
- CMK: enable Cosmos DB CMK encryption via Key Vault for regulated data — set at account creation.

## PostgreSQL / MySQL Flexible Server defaults

- High availability: **Zone-redundant HA** with a standby replica in a different AZ for production. Failover is automatic and typically under 60 seconds.
- Authentication: Entra ID (Azure AD) authentication enabled; disable local `postgres` password auth for human access. Application service accounts use Managed Identity + the `pg_aad` or `aad_auth` plugin.
- Backups: 7-day PITR minimum; 35 days for regulated. Geo-redundant backup storage for any workload with an RPO requiring regional DR.
- Firewall: private access (VNet integration) for production — no public endpoint. Deny all public IPs at the Flexible Server firewall if public endpoint is accidentally enabled.
- TLS: enforce `require_secure_transport = ON`; set `ssl_min_protocol_version = TLSv1.2`.
- Maintenance window: explicit off-peak window; pin minor version cadence to a known schedule.
- Extensions: allowlist via the `azure.extensions` parameter; not all PostgreSQL extensions are permitted on Flexible Server.

## Azure Cache for Redis Enterprise defaults

- Tier: **Enterprise** (Redis Stack) for advanced data structures (JSON, Search, TimeSeries); **Enterprise Flash** for large working sets that tolerate slightly higher latency.
- Authentication: Entra ID-based auth for Azure Cache for Redis (preview GA as of 2025); fall back to access-key auth with rotation policy if RBAC not yet supported for your SDK.
- TLS: enforce `minimumTlsVersion: '1.2'`; disable non-TLS port (6379).
- Eviction: `allkeys-lru` for general caches; `noeviction` for queues or session stores where silent data loss is a correctness bug.
- Geo-replication: active geo-replication (Enterprise tier) for global low-latency reads and regional DR; passive geo-replication for Basic / Standard / Premium tiers.
- Persistence: RDB or AOF for workloads where cache loss matters; skip for pure cache layers that can rebuild from the backing store.

## Synapse Analytics defaults

- SQL pool: dedicated for consistent, predictable analytical workloads; serverless for pay-per-query ad-hoc analytics over ADLS Gen2 data.
- Workspace identity: Managed Identity for the Synapse workspace to access ADLS Gen2; no storage account keys in notebooks or pipelines.
- Encryption: workspace-level CMK in Key Vault (set at workspace creation — immutable afterward for dedicated SQL pool).
- Firewall: disable public network access; connect via managed private endpoint from the Synapse workspace.
- Pause dedicated SQL pool: scheduled pause during non-business hours for dev environments; a paused pool still incurs storage costs.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Blob storage with public access enabled | One misconfigured container policy = public data exposure. Disable at the account level. |
| Azure SQL with SQL-auth-only and shared `sa` password | No audit trail per user, rotation risk, credential-sharing blast radius. Use Entra ID auth. |
| Cosmos DB with a hot partition key (e.g., `userId` at high cardinality) | Throughput throttling limited to one logical partition. Model partition key to spread writes. |
| PostgreSQL in a public subnet with firewall open to `0.0.0.0/0` | One SG slip = exposed database. Private endpoint, always. |
| Redis without TLS | Cache poisoning becomes a correctness or integrity risk for any consumer. |
| Cosmos DB Strong consistency everywhere | 2× the RU cost and double the latency. Use Session unless you provably need Strong. |
| ADLS Gen2 without HNS enabled | Cannot use directory-level ACLs or rename-as-atomic-operation. Cannot enable post-creation. |
| Synapse dedicated SQL pool left running idle overnight | 730 DWU-hours/night is a meaningful line item. Schedule pause. |

## Security defaults

- All data at rest encrypted; CMKs in Key Vault for any data under access-audit, compliance, or revocation requirements.
- Private endpoints for every PaaS data service in production; `publicNetworkAccess: 'Disabled'` in Bicep / Terraform.
- Managed Identity for all application-to-data access; connection strings are a last resort for legacy code with documented exceptions.
- Microsoft Defender for SQL / Defender for Storage on for threat detection and anomalous-access alerting.
- Soft delete and versioning on Blob Storage so ransomware or accidental deletions are recoverable.
- Entra ID (Azure AD) authentication as the primary auth method for SQL, Cosmos DB, and Redis where supported.

## Observability defaults

- Azure SQL: Query Performance Insight + Intelligent Performance Recommendations in Defender for SQL; alerts on `dtu_consumption_percent`, `connection_failed`, `deadlock`.
- Cosmos DB: alert on `NormalizedRUConsumption > 80%`, `ServerSideLatency > threshold`, and `TotalRequests` with `statusCode = 429` (throttled).
- Blob Storage: Storage Analytics logs to a separate log storage account; alerts on `Availability < 99.9%`, `AverageE2ELatency`.
- Redis Enterprise: alert on `UsedMemory / MaxMemory > 80%`, `CacheHits / (CacheHits + CacheMisses) < 80%`, `ConnectedClients` spikes.
- PostgreSQL / MySQL: slow-query log (`log_min_duration_statement = 1000`), `connections_used / max_connections > 80%`, replication lag for HA standbys.

## Cost considerations

- Blob lifecycle rules eliminate the most common cost accumulation; review rules quarterly as access patterns change.
- Cosmos DB autoscale vs manual provisioned: autoscale adds a 50% premium over the max RU/s; break even when peak:average ratio is > 2:1.
- Azure SQL Hyperscale costs more per vCore than General Purpose but eliminates IOPS and size limits — calculate before assuming it's cheaper.
- Synapse dedicated SQL pool: 1 DW100c = $1.51/hr; every tier doubles. Pause aggressively for dev; commit to reserved capacity only after 30 days of stable DWU measurement.
- Redis Enterprise tier is priced per OSS shard; model shard count from dataset size and throughput before selecting Enterprise Flash.
- ADLS Gen2 read/write operations are priced per 10K operations — bulk loader patterns (single large write vs many small) dramatically affect cost.

## IaC hints

- Bicep: `Microsoft.Storage/storageAccounts` with `kind: 'StorageV2'` and `isHnsEnabled: true` for ADLS Gen2; `Microsoft.DocumentDB/databaseAccounts` for Cosmos DB; `Microsoft.DBforPostgreSQL/flexibleServers` for PostgreSQL.
- Terraform: `azurerm_storage_account`, `azurerm_cosmosdb_account`, `azurerm_postgresql_flexible_server`, `azurerm_redis_cache`. Use `azurerm_private_endpoint` for every data resource in production.
- Stateful resources (Azure SQL, Cosmos DB, storage accounts) belong in a separate Bicep module or Terraform workspace from compute, with `lock` resources (`Microsoft.Authorization/locks` kind `CanNotDelete`) on production instances.
- CMK setup requires Key Vault to be deployed and the storage/database Managed Identity granted `Key Vault Crypto Service Encryption User` role before the storage account is created — sequence this in your deployment pipeline.

## Verification checklist

- [ ] Data store selected from access-pattern analysis, not recency bias.
- [ ] Encryption at rest with CMK for regulated data; verified in portal under Encryption blade.
- [ ] No public network access for any production database or storage account.
- [ ] Backup retention and PITR window meet RPO requirements; restore drill completed.
- [ ] Managed Identity used for all application connections; connection string auth documented as exception if present.
- [ ] Soft delete / versioning on blob storage; continuous backup on Cosmos DB production containers.
- [ ] Private endpoints validated (can the app reach the resource via private IP only?).
- [ ] Monitoring alerts cover the top failure modes; action group routes to a real channel.
- [ ] Lifecycle / TTL policies configured; old data does not accumulate indefinitely.
