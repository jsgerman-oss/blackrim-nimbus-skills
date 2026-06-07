<div align="center">

# blackrim-nimbus-skills

**A Claude Code plugin marketplace for cloud-development workflows.**
Production-grade defaults, validated by schema, across **19 cloud providers**.

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg?style=flat-square)](LICENSE)
[![Node ≥ 18](https://img.shields.io/badge/node-%E2%89%A518-brightgreen.svg?style=flat-square)](package.json)
[![Plugins: 19](https://img.shields.io/badge/plugins-19-blueviolet.svg?style=flat-square)](#the-matrix)
[![Validator rules: 28](https://img.shields.io/badge/rules-28-orange.svg?style=flat-square)](#whats-in-the-validator)
[![Claude Code compatible](https://img.shields.io/badge/Claude%20Code-compatible-7c3aed.svg?style=flat-square)](https://claude.com/claude-code)
[![Validate](https://img.shields.io/github/actions/workflow/status/jsgerman-oss/blackrim-nimbus-skills/validate.yml?branch=main&style=flat-square&label=validate)](.github/workflows/validate.yml)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-success.svg?style=flat-square)](CONTRIBUTING.md)

[Quick start](#-quick-start) · [The matrix](#-the-matrix) · [Pick a provider](#-pick-a-provider) · [Plugin anatomy](#-plugin-anatomy) · [Validator](#-whats-in-the-validator) · [Contributing](CONTRIBUTING.md)

</div>

---

## What this is

A curated marketplace of **19 Claude Code plugins**, one per cloud, each shipping:

| Component       | Count | What it does                                                        |
| --------------- | ----- | ------------------------------------------------------------------- |
| Domain skills   | 6     | Auto-fire by description match; cover compute → IaC for that cloud  |
| SME sub-agents  | 2     | `<provider>-architect` (well-architected review) + `-security-reviewer` (audit) |
| Slash commands  | 1+    | `/<provider>-scaffold-iac` and platform-specific scaffolds          |

Every plugin is **schema-validated**, follows a **canonical structure** enforced by CI, and bakes in **production-grade defaults**: encryption-at-rest, least-privilege identity, private-by-default networking, observability before launch, cost flagged at decision time.

> **Why use this?** You want Claude Code to be opinionated and right about cloud choices, not generic. The skills are scoped tightly enough to fire only when relevant, deep enough to actually help, and consistent enough across providers that switching clouds doesn't break your muscle memory.

## 🚀 Quick start

From any Claude Code session:

```text
/plugin marketplace add /absolute/path/to/blackrim-nimbus-skills
/plugin install cloud-aws@blackrim-cloud-toolkits
```

That's it. The next time you ask Claude something compute-shaped on AWS — *"should this be a Lambda or an ECS task?"* — the `aws-compute` skill auto-fires with a decision tree, defaults, and anti-patterns.

Install multiple plugins side-by-side:

```text
/plugin install cloud-aws@blackrim-cloud-toolkits
/plugin install cloud-cloudflare@blackrim-cloud-toolkits
/plugin install cloud-supabase@blackrim-cloud-toolkits
```

### Try the sub-agents

```text
Use the aws-architect agent to review my CDK stack against the Well-Architected pillars.
```

```text
Use the cf-security-reviewer agent to audit my wrangler.toml + Workers code for exposure.
```

### Try the slash commands

```text
/aws-scaffold-iac a multi-AZ web service with a Postgres backend and CloudFront in front
```

## 🗺️ The matrix

### Hyperscalers

| Plugin           | Best for                                          | Coverage |
| ---------------- | ------------------------------------------------- | -------- |
| `cloud-aws`      | Greenfield US/EU startup, AWS-native              | Lambda, ECS, EKS, EC2, S3, RDS / Aurora, DynamoDB, VPC, ALB / CloudFront, IAM, KMS, Secrets Manager, GuardDuty, CloudWatch / X-Ray, CDK / Terraform / SAM. |
| `cloud-gcp`      | GKE / Vertex AI / BigQuery / data-heavy stacks    | Cloud Run, GKE, Cloud Functions Gen 2, Compute Engine, GCS, Cloud SQL / AlloyDB / Spanner / Firestore / BigQuery, Cloud LB / Cloud CDN / Cloud Armor, Cloud IAM + Workload Identity, KMS, Cloud Monitoring / Logging / Trace, Terraform / Config Connector. |
| `cloud-azure`    | Enterprise, FedRAMP, financial services           | Functions, AKS, Container Apps, App Service, VMs, Blob / Azure SQL / Cosmos DB, VNet / Application Gateway / Front Door / APIM, Entra ID + Managed Identity, Key Vault, Defender for Cloud, Azure Monitor + App Insights, Bicep / Terraform. |
| `cloud-oci`      | Oracle workloads + Autonomous Database            | Compute, OKE, Functions, Object Storage, Autonomous Database, MySQL HeatWave, VCN / Load Balancer / WAF, OCI IAM + Resource Principal, Vault KMS, Cloud Guard, Security Zones, Monitoring + APM, Terraform / Resource Manager. |
| `cloud-ibm`      | FIPS 140-2 L4 (Hyper Protect), regulated workloads | VPC VSIs, Code Engine, IKS / ROKS, COS, Cloudant, Db2 on Cloud, Hyper Protect, IBM Cloud IAM + Trusted Profiles, Key Protect + HPCS, Activity Tracker, Sysdig + LogDNA, Terraform / Schematics. |
| `cloud-alibaba`  | APAC + China-region presence (MLPS, ICP)          | ECS, ACK, Function Compute, OSS, RDS / PolarDB, VPC, SLB / ALB / NLB, CDN / DCDN, RAM + STS, KMS, Anti-DDoS + WAF + Security Center, CloudMonitor + SLS, Terraform / ROS. China + International account separation. |
| `cloud-tencent`  | China-region with EdgeOne CDN                     | CVM, TKE, SCF, COS, CDB / TDSQL, VPC / CLB, CDN + EdgeOne, CAM, KMS, CloudAudit, Cloud Monitor + CLS, Terraform / TIC. |

### Edge · Zero Trust · Frontend

| Plugin             | Best for                                       | Coverage |
| ------------------ | ---------------------------------------------- | -------- |
| `cloud-cloudflare` | Edge-first, low egress, ZTNA, Workers stack    | Workers, Durable Objects, Pages Functions, Workers AI, Workflows, R2, D1, KV, Queues, Hyperdrive, Vectorize, DNS / CDN / LB, Argo, Tunnel, Access (ZTNA), Gateway, WAF, Bot Management, DDoS, Page Shield, Analytics Engine, Logpush, Wrangler + Terraform v5. |
| `cloud-vercel`     | Next.js / SvelteKit / Astro production         | Production / Preview / Branch deploys, Edge Functions, Edge Middleware, Serverless Functions, ISR, Image Optimization, Cron, Vercel KV / Postgres / Blob, Edge Config, Deployment Protection, WAF + Attack Challenge, Web Analytics, Speed Insights, Logs Drains, Spend Management. |
| `cloud-netlify`    | JAMstack with build pipelines + Deploy Previews | Build pipelines, Deploy Previews, Edge Functions (Deno), Background + Scheduled Functions, Blobs, Forms, Identity, Visitor Access, security headers via `_headers`, Logs Drains, build minutes / bandwidth pricing. |

### Modern PaaS · Dev-first · BaaS

| Plugin           | Best for                                        | Coverage |
| ---------------- | ----------------------------------------------- | -------- |
| `cloud-fly`      | Global Docker fleet, multi-region default       | Fly Machines (Firecracker VMs), Apps, scale-to-zero, anycast routing, 6PN private mesh, Flycast, Volumes (AZ-local), Fly Postgres, Redis (Upstash), Tigris (S3-compat), LiteFS, `flyctl` + GitHub Actions. |
| `cloud-render`   | Heroku replacement with SOC 2 posture           | Web Services, Private Services, Background Workers, Cron Jobs, Static Sites, Managed Postgres (HA + PITR), Managed Redis, Persistent Disks, Blueprints (`render.yaml`), PR Previews. |
| `cloud-railway`  | Fast-onboarding PaaS with usage billing         | Services, Volumes, Database Plugins (Postgres / MySQL / Mongo / Redis), Reference Variables, Service Tokens, Templates, preview environments. |
| `cloud-supabase` | Postgres + Auth + Storage as managed BaaS       | Postgres + **RLS-first** security, Auth (email / OAuth / magic link / MFA + passkeys), Storage with RLS, Realtime (WAL + Broadcast + Presence), Edge Functions (Deno), pgvector, Supabase CLI + branching + GitHub Actions. |

### VPS · Regional · Cost-leader

| Plugin              | Best for                                     | Coverage |
| ------------------- | -------------------------------------------- | -------- |
| `cloud-digitalocean`| Predictable pricing, App Platform onboarding | Droplets, App Platform, DOKS, Spaces, Volumes, Managed Databases, VPC, Load Balancer, Reserved IPs, Cloud Firewall, doctl + Terraform + App Spec YAML. |
| `cloud-hetzner`     | EU data residency, budget servers + dedicated | Hetzner Cloud servers (CX / CPX / CCX / CAX ARM), Robot dedicated, Volumes, Storage Box, Private Networks, Load Balancer, Cloud Firewalls, hcloud-cli + Terraform + Ansible. Honest about no native managed DB. |
| `cloud-linode`      | Akamai-backed VPS with global presence       | Compute Instances, LKE, Object Storage, Volumes, Managed Databases, NodeBalancer, VLAN + VPC, Cloud Firewall, `linode-cli` + Terraform + Ansible. |
| `cloud-vultr`       | High-frequency / AMD / Bare Metal / GPU      | Cloud Compute (Regular / High Performance / High Frequency / AMD / Intel), Bare Metal, Cloud GPU, VKE, Object Storage, Managed Databases, VPC 2.0, Load Balancers, Reserved IPs, Firewall Groups, vultr-cli + Terraform + Packer. |
| `cloud-scaleway`    | EU-strong, Serverless Containers + Kapsule   | Instances, Elastic Metal, Serverless Containers / Jobs / Functions, Kapsule (Kubernetes — Kosmos for hybrid), Object Storage, Managed Databases, Serverless SQL, Scaleway IAM + Secret Manager + Key Manager, Cockpit (managed Grafana), `scw` + Terraform. |

## 🎯 Pick a provider

| If you're…                                                   | Reach for                                                      |
| ------------------------------------------------------------ | -------------------------------------------------------------- |
| A greenfield startup, AWS-native, want one IaC               | `cloud-aws` + CDK or Terraform                                 |
| GKE / Vertex-heavy ML stack                                  | `cloud-gcp`                                                    |
| Enterprise / regulated (FedRAMP, financial, FIPS 140-2 L4)   | `cloud-azure` or `cloud-ibm` (Hyper Protect)                   |
| Edge-first, low egress, Workers-friendly                     | `cloud-cloudflare`                                             |
| Next.js / SvelteKit / Astro frontend                         | `cloud-vercel` or `cloud-netlify`                              |
| Postgres + Auth + Storage as a managed BaaS                  | `cloud-supabase`                                               |
| Global Docker fleet, multi-region by default                 | `cloud-fly`                                                    |
| Heroku-replacement, fast onboarding                          | `cloud-render` or `cloud-railway`                              |
| Budget-conscious / EU data residency                         | `cloud-hetzner` or `cloud-scaleway`                            |
| APAC / China-region presence                                 | `cloud-alibaba` or `cloud-tencent`                             |
| Oracle workloads + Autonomous Database                       | `cloud-oci`                                                    |

## 🧩 Plugin anatomy

Every plugin follows the same shape. Predictable layout, predictable surface area.

```
cloud-<provider>/
├── .claude-plugin/
│   └── plugin.json                              # manifest (name, prefix, keywords, ...)
├── README.md                                    # has a managed "What's inside" region
├── skills/
│   ├── <prefix>-compute/SKILL.md                # runtime selection + sizing
│   ├── <prefix>-storage-and-databases/SKILL.md  # data tier decisions
│   ├── <prefix>-networking-and-edge/SKILL.md    # VPC / LB / DNS / WAF / CDN
│   ├── <prefix>-identity-and-security/SKILL.md  # IAM, KMS, secrets, audit
│   ├── <prefix>-observability-and-cost/SKILL.md # metrics, logs, traces, FinOps
│   └── <prefix>-iac-and-deployment/SKILL.md     # IaC tool selection + CI/CD
├── agents/
│   ├── <prefix>-architect.md                    # well-architected reviewer
│   └── <prefix>-security-reviewer.md            # security audit
└── commands/
    └── <prefix>-scaffold-iac.md                 # IaC project scaffold
```

> **Note on `<prefix>`** — usually matches the provider name (`aws-`, `gcp-`), but some diverge: Cloudflare uses `cf-`, DigitalOcean uses `do-`. The plugin's prefix is declared in `plugin.json`.

For platforms whose shape diverges from generic IaaS (Cloudflare's Zero Trust, Vercel's edge runtime, Supabase's Postgres+Auth model, Fly's Firecracker fleet), the six-slot template flexes — e.g. `cf-workers-and-compute`, `supabase-auth`, `vercel-frontend-platform`.

## 📖 Skill anatomy

Each `SKILL.md` follows a consistent shape so Claude knows what to expect and contributors know what to write:

```markdown
---
name: <skill-slug>
description: <when to use this skill — fires on description match>
---

# <Skill Title>

## When to use
- Concrete triggering conditions

## Decision tree / Defaults
Per-service production-grade defaults or a decision tree.

## Anti-patterns
| Anti-pattern | What goes wrong |
| --- | --- |
| ... | ... |

## Security defaults
## Observability defaults
## Cost considerations
## IaC hints

## Verification checklist
- [ ] Items that gate "done"
```

The **Verification checklist** is the load-bearing section — it's what gates "is this work actually finished?" The validator enforces it; downstream tooling can parse it via `npm run checklist <plugin>`.

## 🧪 What's in the validator

Every plugin and every file is checked by a **declarative rule registry** at `bin/lib/rules.js`. Run `npm run rules` to print the live list (29 rules across 5 scopes).

| Scope          | What it checks                                                                |
| -------------- | ----------------------------------------------------------------------------- |
| `marketplace`  | JSON schema, plugin references resolve, `marketplace.json` + the pack's `providers.json` in sync |
| `plugin`       | `plugin.json` schema, name matches dir, ≥5 skills, has both agents, has command, README managed-region in sync |
| `skill`        | Frontmatter parses, name matches slug, description ≥20 chars, `## Verification checklist` with `- [ ]` items |
| `agent`        | Frontmatter parses, role-correct tools (architect adds `WebFetch`, security-reviewer adds `Bash`), `model: sonnet`, canonical body sections present |
| `command`      | Frontmatter parses, filename starts with prefix, `description` + `argument-hint` present                       |

**Architect agents** must contain: `## Inputs you expect`, `## Review process`, `## Output format`, `## Rules of engagement`.
**Security-reviewer agents** must contain: `## Inputs`, `## Review scope — what you check`, `## Output`, `## Rules of engagement`.

CI runs `npm run check` + `npm run regen` + asserts no diff on every push and PR. Drift is caught before it lands.

## 🛠️ Development

Requires Node ≥ 18.

```sh
# Setup
git clone https://github.com/jsgerman-oss/blackrim-nimbus-skills.git
cd blackrim-nimbus-skills
npm install

# Validate
npm run check                                # run all 29 rules
npm run check -- --rule plugin-schema        # one rule
npm run check -- --skip skill-checklist-min-items  # skip one
npm run check -- --json                      # machine-readable output

# Inspect
npm run rules                                # list all rules (text)
npm run rules -- --md                        # markdown table
npm run rules -- --json                      # JSON
npm run checklist cloud-aws                  # all checklists in a plugin
npm run checklist cloud-aws aws-compute --json   # JSON for one skill

# Regenerate derived files (run after adding skills/agents/commands or a provider)
npm run regen                                # marketplace.json + plugin READMEs + pack provider index
npm run regen:marketplace                    # marketplace.json only
npm run regen:plugin-readmes                 # plugin README "What's inside" regions only
npm run regen:pack-providers                 # pack/nimbus/providers.json only
```

### Adding a new plugin

1. Create the directory: `mkdir -p cloud-<provider>/{.claude-plugin,skills,agents,commands}`
2. Write `plugin.json` (don't forget `prefix`).
3. Write 5+ skills, two agents (`<prefix>-architect.md`, `<prefix>-security-reviewer.md`), one command.
4. `npm run regen` to update `marketplace.json` and your README's managed region.
5. `npm run check` to validate.
6. Open a PR.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full file-shape conventions.

## 🎨 Design principles

1. **Defaults are production-grade, not demo-grade.** Encryption-at-rest on by default. Private subnets unless public is explicitly required. Least-privilege identity scoped to specific resources, never `*`.
2. **Cost is a first-class concern.** Every skill flags cost-amplifying choices (NAT, cross-AZ, idle baselines, infinite log retention) at decision time, not in post-mortem.
3. **Observability before launch.** No workload ships without metrics, logs, traces, and at least one alarm wired to a real notification channel.
4. **IaC over console.** Console steps appear only as bootstrap (account hardening). Everything else is code.
5. **Well-architected as a checklist, not a vibe.** The architect agent maps findings to specific pillar best practices and rates severity.
6. **Honest about limits.** When a provider lacks a feature — fine-grained tokens, managed databases, anycast LB, fully-managed Postgres — the skill says so out loud rather than papering over it.
7. **Schema-validated.** Conventions are enforced by code (`bin/lib/rules.js`), not by reviewer attention.

## 💡 Worked example

Suppose you're building a multi-region API on Fly.io with Supabase as the data tier. You'd install:

```text
/plugin install cloud-fly@blackrim-cloud-toolkits
/plugin install cloud-supabase@blackrim-cloud-toolkits
```

Then in your session, the skills fire automatically as you discuss your design:

- *"Should I run this in 2 or 6 regions on Fly?"* → `fly-machines-and-apps` skill fires; decision tree on placement vs LiteFS replication.
- *"How do I scope RLS so user A can't read user B's rows?"* → `supabase-postgres-and-rls` skill fires; RLS policy templates.
- *"Audit my supabase RLS setup before launch."* → invoke the `supabase-security-reviewer` agent.
- *"Scaffold the fly.toml for this service."* → `/fly-scaffold-app` slash command.

The cross-plugin story is consistent: every plugin's architect agent uses the same six-step review process; every security-reviewer uses the same four canonical sections; every skill ends with a parseable checklist.

## 🤝 Contributing

Contributions are welcome — new providers, deeper skills, refined defaults. See [CONTRIBUTING.md](CONTRIBUTING.md) for:

- File-shape conventions (the canonical 6-skill + 2-agent + 1-command layout)
- Skill anatomy and the verification-checklist contract
- The 28-rule validator and how to add a new rule
- PR checklist

Before opening a PR, run:

```sh
npm run check && npm run regen
```

…and ensure your diff is clean.

## 📜 License

[MIT](LICENSE) — Copyright © 2026 Blackrim.dev.

Pull requests, issues, and feature requests are welcome. The full validator output, schema definitions, and rule registry are all open to inspection so you can verify the production-grade-defaults claim isn't marketing.

---

<div align="center">

Built with [Claude Code](https://claude.com/claude-code) · Validated by `bin/check-plugins` · 19 providers, one consistent shape

</div>
