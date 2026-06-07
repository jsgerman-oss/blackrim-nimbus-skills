# Contributing to blackrim-nimbus-skills

Thanks for the interest. This is a Claude Code plugin marketplace for cloud-development workflows across 19+ providers. Contributions land most easily when they follow the conventions below.

## What lives where

```
.
├── .claude-plugin/marketplace.json   # marketplace index — derived from plugin.json files
├── schemas/
│   ├── marketplace.schema.json       # JSON schema for the index
│   └── plugin.schema.json            # JSON schema for plugin.json
├── bin/
│   ├── check-plugins                 # validator engine (iterates rule registry)
│   ├── regen-marketplace             # rebuild marketplace.json from plugin.json
│   ├── regen-plugin-readmes          # rebuild each plugin README's "What's inside" region
│   ├── regen-pack-providers          # rebuild pack/nimbus/providers.json from cloud-* manifests
│   ├── list-rules                    # print the validator rule registry
│   ├── list-checklist                # print verification checklists for a plugin
│   └── lib/
│       ├── rules.js                  # rule registry — the contract, in code
│       ├── marketplace.js            # plugin discovery + index projection
│       ├── providers.js              # pack provider-breadth index builder
│       ├── plugin-readme.js          # plugin README region builder
│       └── skill.js                  # frontmatter, section, checklist parsers
├── cloud-<provider>/                 # one directory per cloud
│   ├── .claude-plugin/plugin.json    # plugin manifest — authoritative
│   ├── README.md                     # plugin overview
│   ├── skills/<skill-name>/SKILL.md  # domain skill(s)
│   ├── agents/<agent>.md             # sub-agent(s)
│   └── commands/<command>.md         # slash command(s)
├── .github/workflows/validate.yml    # CI
└── README.md                         # repo-level overview
```

## Adding a new cloud provider

1. **Create the directory** `cloud-<provider>/` and the standard subdirs (`skills/`, `agents/`, `commands/`, `.claude-plugin/`).
2. **Write `plugin.json`** with `name`, `description`, `version`, `author`, `license`, `keywords`, and `prefix`. `prefix` is the slug every skill, agent, and command in your plugin uses (e.g. `aws`, `cf`, `do`). It does not have to match the plugin name — `cloud-cloudflare` uses prefix `cf`.
3. **Regenerate the derived indexes.** Run `npm run regen` — it rebuilds `marketplace.json` (derived from each plugin's `plugin.json`) and the nimbus pack's `providers.json` (derived from the `cloud-*` manifests + skills). Don't edit either by hand.
4. **Write the six skills**: by convention, every cloud covers six domains —
   - `<provider>-compute`
   - `<provider>-storage-and-databases`
   - `<provider>-networking-and-edge` (or equivalent)
   - `<provider>-identity-and-security`
   - `<provider>-observability-and-cost`
   - `<provider>-iac-and-deployment`

   For platforms whose shape diverges (Cloudflare's Zero Trust, Vercel's edge runtime, Supabase's Postgres+Auth model), the six-slot template can flex — see `cloud-cloudflare/`, `cloud-vercel/`, `cloud-supabase/` for divergent-platform examples.
5. **Add two sub-agents**: `<provider>-architect.md` (well-architected reviewer) and `<provider>-security-reviewer.md` (security audit).
6. **Add one slash command**: `<provider>-scaffold-iac.md` (or the closest analog for the platform's IaC story).

## Skill file shape

Every `SKILL.md` follows this anatomy:

```markdown
---
name: <skill-name>
description: What it does + when it fires.
---

# <Skill Title>

## When to use
- triggering conditions

## Defaults (or decision tree)
Per-service production-grade defaults.

## Anti-patterns
| Anti-pattern | What goes wrong |

## Security defaults
## Observability defaults
## Cost considerations
## IaC hints

## Verification checklist
- [ ] Items that gate "done".
```

Length target: 150–250 lines per skill. Agents 100–200. Commands 100–200.

## Agent file shape

```markdown
---
name: <agent-name>
description: One sentence on when the agent should be invoked.
tools: Read, Glob, Grep, ...
model: sonnet
---

# <Agent Title>

You are <role>. Your job: <scope>.
...
```

## Slash command file shape

```markdown
---
description: One sentence on what the command does.
argument-hint: <free-form text the user supplies>
---

# <Command Title>

## What to do
1. ...
2. ...
```

## Quality bar

- **Production-grade defaults.** Encryption at rest, least-privilege identity, private-by-default networking, observability before launch.
- **Cost-aware.** Every skill flags the lines on the bill that grow silently.
- **Honest about limits.** When a provider lacks a feature (no managed DB, no anycast LB, no fine-grained tokens), say so.
- **Anchored to standards.** Reference CIS Benchmarks, vendor well-architected frameworks, or the OWASP Top 10 where appropriate.
- **Version-current.** Pin CLI / provider / SDK versions and call out breaking changes.
- **Original prose.** No vendor sample-repo copying.

## Local development

```sh
git clone <repo>
cd blackrim-nimbus-skills
npm install                            # one-time
npm run check                          # validate everything (CI runs this)
npm run regen                          # rebuild marketplace.json + plugin READMEs + pack provider index
npm run regen:marketplace              # marketplace.json only
npm run regen:plugin-readmes           # plugin READMEs only
npm run regen:pack-providers           # pack/nimbus/providers.json only
npm run rules                          # list every validator rule
npm run checklist cloud-aws            # print verification checklists for a plugin
npm run checklist cloud-aws aws-compute --json  # JSON for one skill

# Preview by installing into a Claude Code session:
# /plugin marketplace add /absolute/path/to/blackrim-nimbus-skills
# /plugin install cloud-<provider>@blackrim-cloud-toolkits
```

## What `npm run check` enforces

The validator is a **rule registry** at `bin/lib/rules.js` — each rule is a named, scoped check with a description. The engine (`bin/check-plugins`) walks the marketplace and invokes every rule against matching contexts. Run `npm run rules` to print the live registry; that output is the authoritative list. CI runs `npm run check` on every PR.

Rules are scoped to one of: `marketplace`, `plugin`, `skill`, `agent`, or `command`. A few highlights:

- **Schema** (`marketplace-schema`, `plugin-schema`): JSON schemas at `schemas/*.schema.json` are the type contract.
- **Plugin shape** (`plugin-has-min-skills`, `plugin-has-architect`, `plugin-has-security-reviewer`, `plugin-has-commands`): every plugin has `>=5` skills, both agent roles, and `>=1` command, all named with the plugin's `prefix`.
- **Skill body** (`skill-has-verification-checklist`, `skill-checklist-has-items`): every `SKILL.md` ends with a `## Verification checklist` section containing at least one `- [ ]` item. This is the load-bearing section — it gates "done."
- **Agent frontmatter** (`agent-tools-match-role`, `agent-model-is-sonnet`): architect uses `tools: Read, Glob, Grep, WebFetch`; security-reviewer uses `tools: Read, Glob, Grep, Bash, WebFetch`; both use `model: sonnet`.
- **Agent structure** (`architect-required-sections`, `security-reviewer-required-sections`): each role has canonical body sections. Architect: `Inputs you expect`, `Review process`, `Output format`, `Rules of engagement`. Security-reviewer: `Inputs`, `Review scope — what you check`, `Output`, `Rules of engagement`. The pillar list and review-scope topics are per-provider.
- **Drift** (`marketplace-in-sync-with-plugins`, `plugin-readme-in-sync`, `pack-providers-in-sync`): generated files match their regen output. `marketplace.json` is derived from each `plugin.json`; every plugin README's `<!-- BEGIN: what's inside -->`…`<!-- END: what's inside -->` region is derived from on-disk skills/agents/commands; and the nimbus pack's `pack/nimbus/providers.json` (its 19-provider breadth index) is derived from the `cloud-*` manifests + skills. Run `npm run regen` after adding or renaming files.

Flags: `npm run check -- --rule <id>` runs one rule; `--skip <id>` skips one; `--json` machine-readable output.

## PR checklist

- [ ] `npm run check` passes locally.
- [ ] `plugin.json` valid (name, description, version, keywords, **prefix**).
- [ ] `npm run regen` run after any add/rename of skills, agents, or commands; resulting changes committed.
- [ ] At least one skill, one agent, and one command per plugin.
- [ ] Frontmatter shapes match existing files; values containing `:` are quoted.
- [ ] Verification checklist present and parseable on each skill (`- [ ]` items under `## Verification checklist`).
- [ ] No verbatim prose from third-party / vendor / sample repos.

## License

MIT. See [LICENSE](LICENSE).
