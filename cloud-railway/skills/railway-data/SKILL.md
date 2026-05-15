---
name: railway-data
description: Design or audit Railway data management — Database Plugins (Postgres, MySQL, Redis, MongoDB), seeding strategies, connection strings via Reference Variables, backups and restore, scaling Plugins, and when to migrate off Plugins to external managed databases. Use when provisioning a Plugin, wiring a connection string, designing a seed/migration workflow, or assessing whether a Plugin is the right long-term choice.
---

# Railway Data

## When to use

- Provisioning a Railway Database Plugin (Postgres, MySQL, Redis, or MongoDB).
- Wiring a connection string to a service using Reference Variables.
- Designing a database migration or seed workflow for Railway.
- Setting up backup and restore for Plugin data.
- Evaluating whether a Railway Plugin is the right choice for a given workload vs an external managed DB.
- Scaling a Plugin (vertical size changes) or understanding Plugin limits.

## Plugin decision tree

| Need | Plugin | Notes |
| --- | --- | --- |
| Relational, ACID, SQL | **Postgres** | First choice for new projects. Managed Postgres ≥ 15. |
| Relational, MySQL-compatible | **MySQL** | Use when the app or ORMs require MySQL specifically. |
| Cache, pub/sub, queues | **Redis** | Redis OSS; good for session storage, task queues, short-lived data. |
| Document store | **MongoDB** | Use when schema flexibility is a hard requirement. |
| Anything beyond these four | External provider | Railway Plugins cover these four engines only. For ElasticSearch, Cassandra, ClickHouse, etc., use a managed provider or self-host as a Railway Service with a Volume. |

## When Railway Plugins are the right call

- **Early-stage product**: zero-config provisioning, no account setup at another provider, co-located with app services.
- **Internal tools and hobby projects**: low-traffic workloads where Plugin limits don't bind.
- **Prototyping**: spin up a Postgres Plugin in seconds; migrate later.
- **Preview environments**: ephemeral databases per PR that disappear when the branch is merged.

## Plugin inflection points — when to migrate off

Railway Database Plugins are **not** a drop-in replacement for a dedicated managed database service for serious production workloads. Migrate when:

| Signal | Recommended alternative |
| --- | --- |
| > 10 GB storage and growing fast | Neon, Supabase, PlanetScale, Aiven |
| Need PITR (point-in-time recovery) | Neon Postgres, Supabase, Aiven |
| Multi-region read replicas | Neon branching, PlanetScale read replicas |
| SOC 2 / HIPAA / PCI compliance requirement | Managed provider with formal compliance certification |
| High connection concurrency (> 100 simultaneous) | Add PgBouncer (as a Railway Service) or move to Neon (built-in pooling) |
| Need read replicas for analytics queries | External managed Postgres with replica routing |
| Redis Cluster mode for horizontal sharding | Upstash Redis or Aiven for Redis |

## Reference Variables — the right way to wire connection strings

Never hardcode a Plugin connection string. Use Railway Reference Variables to inject them at runtime:

```text
DATABASE_URL=${{Postgres.DATABASE_URL}}
REDIS_URL=${{Redis.REDIS_URL}}
```

This syntax resolves at deploy time, environment-specifically, and rotates automatically if the Plugin is re-created. Set these in the dependent service's variable panel.

Full reference variable syntax:

```text
${{<ServiceName>.<VARIABLE_NAME>}}
```

- `ServiceName` is the Railway service name (case-sensitive, matches the dashboard label).
- Works across all services within the same Railway environment.
- Does NOT work cross-environment or cross-project — each environment has its own Plugin instance with its own credentials.

## Seeding and migrations

Run migrations as a one-shot Railway service or via the deploy command of the app service:

**Option A — Start command migration (simple):**

```json
{
  "deploy": {
    "startCommand": "npm run migrate && node server.js"
  }
}
```

Risk: if the migration fails, the server never starts and Railway retries the whole container. Use only for idempotent, fast migrations.

**Option B — Separate migration service (recommended for production):**

Create a Railway Service with:

```json
{
  "deploy": {
    "startCommand": "npm run migrate",
    "restartPolicyType": "NEVER"
  }
}
```

Set this service to run before the app service using Railway's service ordering (available in the dashboard). Delete or disable the migration service after it completes; a `NEVER` restart policy prevents it from re-running.

**Option C — Railway CLI one-off:**

```bash
railway run --service my-app -- npm run migrate
```

Useful for local development or one-time prod fixes. The command runs in Railway's environment with all variables resolved.

## Backups

Railway Plugins do not provide automated scheduled backups out of the box (as of 2026-05). You are responsible for backup strategy:

**Postgres:**

```bash
# Export via Railway CLI
railway run --service postgres -- pg_dump $DATABASE_URL > backup.sql

# Or from a Railway cron service
pg_dump $DATABASE_URL | gzip | aws s3 cp - s3://my-backups/$(date +%Y%m%d).sql.gz
```

**Redis:**

```bash
railway run --service redis -- redis-cli -u $REDIS_URL BGSAVE
# Then copy RDB file — limited usefulness without Volume access
```

For Redis, consider using Redis as a cache only (acceptable data loss); if durability is required, use an external Redis with managed backup (Upstash, Aiven).

**Restore:**

```bash
psql $DATABASE_URL < backup.sql
```

Test restores on a staging environment before you need them in production. Untested backups are wishes.

## Scaling Plugins

Railway Plugins scale vertically via the dashboard — you select a plan tier that changes the vCPU and memory allocated to the Plugin container.

- Horizontal scaling (multi-node) is **not available** for Railway Plugins.
- For Postgres, add a PgBouncer Railway Service in front of the Plugin to handle connection pooling before vertical scaling becomes necessary.
- Monitor Plugin resource usage via the Railway dashboard metrics (CPU, memory, disk).
- If disk fills up, Railway will mark the Plugin as degraded. Set a disk usage alarm via an external monitoring drain.

## Anti-patterns

| Anti-pattern | What goes wrong |
| --- | --- |
| Hardcoded connection string in a Variable | If the Plugin is re-created (e.g., after a restore), the URL changes and all services break. Use Reference Variables. |
| Running migrations in `ALWAYS` restart policy | Migration script runs on every container start, corrupting state. Use `NEVER`. |
| Using a Plugin for primary data with no backup | Railway does not manage backups; a Plugin failure is permanent data loss. |
| Sharing one Plugin across dev and prod environments | Schema changes in dev break prod. Each environment gets its own Plugin instance. |
| Skipping PgBouncer for a connection-heavy app | Plugin Postgres has a connection limit; exceeding it causes `FATAL: sorry, too many clients`. |
| Storing secrets in a shared environment variable instead of Reference Variables | Leaked connection strings if a service is cloned or a new team member gets viewer access. |

## Security defaults

- Plugins are network-private by default — accessible only within the Railway project.
- Never expose a Plugin's TCP port publicly (Railway lets you add a public TCP proxy — do not use this for databases in production; use it only for short-lived debugging).
- Rotate Plugin credentials by re-creating the Plugin on a maintenance window; Reference Variables update automatically.
- Restrict team member roles: only owners and admins can view Plugin connection strings in the dashboard.
- Use a dedicated Railway environment per stage (dev, staging, production) — each with its own Plugin, so staging data never touches production.

## Observability defaults

- Plugin CPU, memory, and disk graphs are available in the Railway dashboard.
- Export Plugin logs to a drain (Datadog, Better Stack) via the project observability settings.
- For Postgres: enable `pg_stat_statements` extension and query the view periodically for slow query identification.
- Set an external alert on disk usage (> 80% of Plugin plan storage limit) so you are not caught off guard.

## Cost considerations

- Railway Database Plugins are billed on the same per-second CPU and memory model as services — they are not free.
- Each Plugin instance (one per environment) accrues usage independently. Preview environments with Plugins incur charges until the environment is deleted.
- Right-size Plugin plan tiers — don't provision a large Plugin for a small app; downgrade if metrics show low utilization.
- Consider whether an external Postgres with a free or cheap tier (Neon free tier, Supabase free tier) is cheaper for low-traffic projects than a Railway Plugin.

## Verification checklist

Before declaring a data setup complete:

- [ ] Plugin type matches the workload's actual requirements (relational, cache, document).
- [ ] Connection strings wired via Reference Variables, not hardcoded.
- [ ] Migrations are idempotent and run via a `NEVER`-restart service or `railway run`.
- [ ] Backup strategy exists and has been tested (restore on staging).
- [ ] Plugin is not publicly exposed via TCP proxy.
- [ ] One Plugin per environment (dev and production not sharing).
- [ ] Connection pooling (PgBouncer) in place for Postgres services with > 20 concurrent connections.
- [ ] Disk usage alerting is set up via external drain or monitoring.
- [ ] Assessed whether Plugin will meet the workload at 6-month and 12-month growth; migration plan documented if not.
