// Validator rule registry.
//
// Each rule is a plain object: { id, description, severity, scope, check(ctx) }.
// The engine in bin/check-plugins walks the marketplace, builds scoped
// contexts, and invokes each rule's check() against matching contexts.
// Rules return arrays of { label, message } — the engine adds id + severity.
//
// Scopes:
//   'marketplace'  — runs once with { marketplace, plugins, repoRoot, regenerated }
//   'plugin'       — runs per plugin with { plugin, repoRoot }
//   'skill'        — runs per skill with { skill, plugin, repoRoot }
//   'agent'        — runs per agent with { agent, plugin, repoRoot }
//   'command'      — runs per command with { command, plugin, repoRoot }
//
// Adding a new rule: append to the array. The validator picks it up automatically;
// `npm run rules` prints the registry; CONTRIBUTING.md can reference rule IDs.

import {
  ARCHITECT_REQUIRED_SECTIONS,
  SECURITY_REVIEWER_REQUIRED_SECTIONS,
  extractSection,
  parseChecklist,
} from "./skill.js";

export const ARCHITECT_TOOLS = "Read, Glob, Grep, WebFetch";
export const SECURITY_REVIEWER_TOOLS = "Read, Glob, Grep, Bash, WebFetch";

export const rules = [
  // --- Marketplace -------------------------------------------------------
  {
    id: "marketplace-schema",
    scope: "marketplace",
    severity: "error",
    description: "marketplace.json matches schemas/marketplace.schema.json.",
    check({ marketplace, validateMarketplace }) {
      if (!marketplace) return [];
      if (validateMarketplace(marketplace)) return [];
      return (validateMarketplace.errors ?? []).map((e) => ({
        label: "marketplace.json",
        message: `${e.instancePath || "(root)"} ${e.message}`,
      }));
    },
  },
  {
    id: "marketplace-references-match-disk",
    scope: "marketplace",
    severity: "error",
    description: "Every plugin listed in marketplace.json exists on disk and vice versa.",
    check({ marketplace, plugins }) {
      if (!marketplace?.plugins) return [];
      const issues = [];
      const listed = new Set(marketplace.plugins.map((p) => p.name));
      const onDisk = new Set(plugins.map((p) => p.manifest.name));
      for (const name of listed) {
        if (!onDisk.has(name)) {
          issues.push({ label: "marketplace.json", message: `lists '${name}' but no matching directory on disk` });
        }
      }
      for (const name of onDisk) {
        if (!listed.has(name)) {
          issues.push({ label: "marketplace.json", message: `directory '${name}' exists but is not listed` });
        }
      }
      return issues;
    },
  },
  {
    id: "marketplace-in-sync-with-plugins",
    scope: "marketplace",
    severity: "error",
    description: "marketplace.json equals the regen output (plugin.json is authoritative).",
    check({ marketplace, regenerated }) {
      if (!marketplace || !regenerated) return [];
      if (JSON.stringify(marketplace, null, 2) === JSON.stringify(regenerated, null, 2)) return [];
      return [{
        label: "marketplace.json",
        message: "out of sync with plugin manifests — run 'npm run regen:marketplace' to update.",
      }];
    },
  },

  // --- Plugin manifest ---------------------------------------------------
  {
    id: "plugin-schema",
    scope: "plugin",
    severity: "error",
    description: "Each plugin.json matches schemas/plugin.schema.json.",
    check({ plugin, validatePlugin }) {
      if (validatePlugin(plugin.manifest)) return [];
      return (validatePlugin.errors ?? []).map((e) => ({
        label: plugin.manifestRelPath,
        message: `${e.instancePath || "(root)"} ${e.message}`,
      }));
    },
  },
  {
    id: "plugin-name-matches-dir",
    scope: "plugin",
    severity: "error",
    description: "plugin.json 'name' must equal the directory name.",
    check({ plugin }) {
      if (plugin.manifest.name === plugin.dirName) return [];
      return [{
        label: plugin.manifestRelPath,
        message: `'name' (${plugin.manifest.name}) must equal directory name (${plugin.dirName})`,
      }];
    },
  },
  {
    id: "plugin-has-min-skills",
    scope: "plugin",
    severity: "error",
    description: "Each plugin has at least 5 skills.",
    check({ plugin }) {
      if (plugin.skills.length >= 5) return [];
      return [{ label: plugin.dirRelPath, message: `expected >=5 skills, found ${plugin.skills.length}` }];
    },
  },
  {
    id: "plugin-has-architect",
    scope: "plugin",
    severity: "error",
    description: "Each plugin has an <prefix>-architect.md agent.",
    check({ plugin }) {
      const want = `${plugin.prefix}-architect.md`;
      if (plugin.agents.some((a) => a.filename === want)) return [];
      return [{ label: `${plugin.dirRelPath}/agents`, message: `missing '${want}'` }];
    },
  },
  {
    id: "plugin-has-security-reviewer",
    scope: "plugin",
    severity: "error",
    description: "Each plugin has an <prefix>-security-reviewer.md agent.",
    check({ plugin }) {
      const want = `${plugin.prefix}-security-reviewer.md`;
      if (plugin.agents.some((a) => a.filename === want)) return [];
      return [{ label: `${plugin.dirRelPath}/agents`, message: `missing '${want}'` }];
    },
  },
  {
    id: "plugin-has-commands",
    scope: "plugin",
    severity: "error",
    description: "Each plugin has at least 1 slash command.",
    check({ plugin }) {
      if (plugin.commands.length >= 1) return [];
      return [{ label: `${plugin.dirRelPath}/commands`, message: "expected >=1 command" }];
    },
  },

  // --- Skills ------------------------------------------------------------
  {
    id: "skill-frontmatter-parses",
    scope: "skill",
    severity: "error",
    description: "Skill SKILL.md frontmatter parses as YAML (values containing ':' must be quoted).",
    check({ skill }) {
      if (!skill.parseError) return [];
      return [{ label: skill.relPath, message: `frontmatter YAML parse failed — ${skill.parseError}. Likely an unquoted colon inside a value.` }];
    },
  },
  {
    id: "skill-slug-has-prefix",
    scope: "skill",
    severity: "error",
    description: "Skill directory slug starts with the plugin's prefix.",
    check({ skill, plugin }) {
      if (skill.slug.startsWith(`${plugin.prefix}-`)) return [];
      return [{ label: skill.dirRelPath, message: `skill slug must start with prefix '${plugin.prefix}-'` }];
    },
  },
  {
    id: "skill-frontmatter-name-matches-slug",
    scope: "skill",
    severity: "error",
    description: "Skill frontmatter 'name' equals the directory slug.",
    check({ skill }) {
      if (!skill.frontmatter) return [];
      if (skill.frontmatter.name === skill.slug) return [];
      return [{
        label: skill.relPath,
        message: `frontmatter name '${skill.frontmatter.name}' must match directory slug '${skill.slug}'`,
      }];
    },
  },
  {
    id: "skill-frontmatter-description-min",
    scope: "skill",
    severity: "error",
    description: "Skill frontmatter 'description' is at least 20 characters.",
    check({ skill }) {
      if (!skill.frontmatter) return [];
      const d = skill.frontmatter.description;
      if (typeof d === "string" && d.length >= 20) return [];
      return [{ label: skill.relPath, message: "frontmatter 'description' missing or too short (need >=20 chars)" }];
    },
  },
  {
    id: "skill-has-verification-checklist",
    scope: "skill",
    severity: "error",
    description: "Skill has a '## Verification checklist' section.",
    check({ skill }) {
      if (!skill.content) return [];
      if (extractSection(skill.content, "Verification checklist") != null) return [];
      return [{ label: skill.relPath, message: "missing '## Verification checklist' section" }];
    },
  },
  {
    id: "skill-checklist-has-items",
    scope: "skill",
    severity: "error",
    description: "Verification checklist contains at least one '- [ ]' item.",
    check({ skill }) {
      if (!skill.content) return [];
      if (extractSection(skill.content, "Verification checklist") == null) return [];
      const items = parseChecklist(skill.content);
      if (items.length >= 1) return [];
      return [{ label: skill.relPath, message: "'## Verification checklist' has no '- [ ]' items" }];
    },
  },
  {
    id: "skill-checklist-min-items",
    scope: "skill",
    severity: "warning",
    description: "Verification checklist has at least 3 items (warning only).",
    check({ skill }) {
      if (!skill.content) return [];
      const items = parseChecklist(skill.content);
      if (items.length === 0 || items.length >= 3) return [];
      return [{ label: skill.relPath, message: `'## Verification checklist' has only ${items.length} items (consider >=3)` }];
    },
  },

  // --- Agents ------------------------------------------------------------
  {
    id: "agent-frontmatter-parses",
    scope: "agent",
    severity: "error",
    description: "Agent .md frontmatter parses as YAML (values containing ':' must be quoted).",
    check({ agent }) {
      if (!agent.parseError) return [];
      return [{ label: agent.relPath, message: `frontmatter YAML parse failed — ${agent.parseError}. Likely an unquoted colon inside a value.` }];
    },
  },
  {
    id: "agent-frontmatter-name-matches",
    scope: "agent",
    severity: "error",
    description: "Agent frontmatter 'name' equals '<prefix>-<role>'.",
    check({ agent }) {
      if (!agent.frontmatter) return [];
      const want = `${agent.prefix}-${agent.role}`;
      if (agent.frontmatter.name === want) return [];
      return [{ label: agent.relPath, message: `frontmatter name '${agent.frontmatter.name}' must equal '${want}'` }];
    },
  },
  {
    id: "agent-description-min",
    scope: "agent",
    severity: "error",
    description: "Agent frontmatter 'description' is at least 20 characters.",
    check({ agent }) {
      if (!agent.frontmatter) return [];
      const d = agent.frontmatter.description;
      if (typeof d === "string" && d.length >= 20) return [];
      return [{ label: agent.relPath, message: "frontmatter 'description' missing or too short" }];
    },
  },
  {
    id: "agent-model-is-sonnet",
    scope: "agent",
    severity: "error",
    description: "Agent frontmatter 'model' is 'sonnet'.",
    check({ agent }) {
      if (!agent.frontmatter) return [];
      if (agent.frontmatter.model === "sonnet") return [];
      return [{ label: agent.relPath, message: `frontmatter model must be 'sonnet' (was '${agent.frontmatter.model}')` }];
    },
  },
  {
    id: "agent-tools-match-role",
    scope: "agent",
    severity: "error",
    description: "Architect tools = 'Read, Glob, Grep, WebFetch'; security-reviewer adds 'Bash'.",
    check({ agent }) {
      if (!agent.frontmatter) return [];
      const want = agent.role === "architect" ? ARCHITECT_TOOLS : SECURITY_REVIEWER_TOOLS;
      if (agent.frontmatter.tools === want) return [];
      return [{
        label: agent.relPath,
        message: `tools must be '${want}' (was '${agent.frontmatter.tools ?? "<missing>"}')`,
      }];
    },
  },
  {
    id: "architect-required-sections",
    scope: "agent",
    severity: "error",
    description: "Architect agents have the four canonical sections (Inputs you expect, Review process, Output format, Rules of engagement).",
    check({ agent }) {
      if (agent.role !== "architect" || !agent.content) return [];
      const issues = [];
      for (const section of ARCHITECT_REQUIRED_SECTIONS) {
        if (extractSection(agent.content, section) == null) {
          issues.push({ label: agent.relPath, message: `missing '## ${section}' section` });
        }
      }
      return issues;
    },
  },
  {
    id: "security-reviewer-required-sections",
    scope: "agent",
    severity: "error",
    description: "Security-reviewer agents have the four canonical sections (Inputs, Review scope — what you check, Output, Rules of engagement).",
    check({ agent }) {
      if (agent.role !== "security-reviewer" || !agent.content) return [];
      const issues = [];
      for (const section of SECURITY_REVIEWER_REQUIRED_SECTIONS) {
        if (extractSection(agent.content, section) == null) {
          issues.push({ label: agent.relPath, message: `missing '## ${section}' section` });
        }
      }
      return issues;
    },
  },

  // --- Commands ----------------------------------------------------------
  {
    id: "command-frontmatter-parses",
    scope: "command",
    severity: "error",
    description: "Command .md frontmatter parses as YAML (values containing ':' must be quoted — this caught the cloud-scaleway scaffold-iac drift).",
    check({ command }) {
      if (!command.parseError) return [];
      return [{ label: command.relPath, message: `frontmatter YAML parse failed — ${command.parseError}. Likely an unquoted colon inside a value.` }];
    },
  },
  {
    id: "command-filename-has-prefix",
    scope: "command",
    severity: "error",
    description: "Command filename starts with the plugin's prefix.",
    check({ command, plugin }) {
      if (command.filename.startsWith(`${plugin.prefix}-`)) return [];
      return [{ label: command.relPath, message: `command filename must start with prefix '${plugin.prefix}-'` }];
    },
  },
  {
    id: "command-description-min",
    scope: "command",
    severity: "error",
    description: "Command frontmatter 'description' is at least 10 characters.",
    check({ command }) {
      if (!command.frontmatter) return [];
      const d = command.frontmatter.description;
      if (typeof d === "string" && d.length >= 10) return [];
      return [{ label: command.relPath, message: "frontmatter 'description' missing or too short" }];
    },
  },
  {
    id: "command-argument-hint-present",
    scope: "command",
    severity: "error",
    description: "Command frontmatter has 'argument-hint'.",
    check({ command }) {
      if (!command.frontmatter) return [];
      const a = command.frontmatter["argument-hint"];
      if (typeof a === "string" && a.length >= 3) return [];
      return [{ label: command.relPath, message: "frontmatter 'argument-hint' missing or too short" }];
    },
  },

  // --- Plugin README -----------------------------------------------------
  {
    id: "plugin-readme-in-sync",
    scope: "plugin",
    severity: "error",
    description: "Each plugin README's managed 'What's inside' region matches the regen output (file tree is authoritative).",
    check({ plugin, buildPluginReadmeRegion }) {
      if (!buildPluginReadmeRegion) return []; // helper injected by engine
      const result = buildPluginReadmeRegion(plugin);
      if (result.inSync) return [];
      if (result.missing) {
        return [{
          label: plugin.readmeRelPath,
          message: "missing managed region — add '<!-- BEGIN: what's inside -->' / '<!-- END: what's inside -->' markers (run 'npm run regen:plugin-readmes').",
        }];
      }
      return [{
        label: plugin.readmeRelPath,
        message: "managed 'What's inside' region out of sync — run 'npm run regen:plugin-readmes' to update.",
      }];
    },
  },
];

export function rulesByScope(scope) {
  return rules.filter((r) => r.scope === scope);
}

export function ruleById(id) {
  return rules.find((r) => r.id === id);
}
