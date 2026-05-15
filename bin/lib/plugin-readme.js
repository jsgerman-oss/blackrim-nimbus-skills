// Plugin-level README "What's inside" managed region.
//
// The region between <!-- BEGIN: what's inside --> and <!-- END: what's inside -->
// is regenerated from each plugin's on-disk skills, agents, and commands plus
// their frontmatter. Other README sections (Design principles, Conventions)
// stay hand-authored.

import { readMarkdown } from "./skill.js";

export const BEGIN_MARKER = "<!-- BEGIN: what's inside -->";
export const END_MARKER = "<!-- END: what's inside -->";

function rowEscape(s) {
  if (!s) return "";
  return String(s).replace(/\|/g, "\\|").replace(/\n+/g, " ").trim();
}

function frontmatterDescription(path) {
  const r = readMarkdown(path);
  if (r.error) return "";
  return r.data?.description ?? "";
}

// Build the managed region text (without surrounding markers). Reads each
// skill, agent, and command file's frontmatter to populate the tables.
// Each table is preceded by a one-line intro so the section reads cleanly
// without the regen erasing context.
export function buildPluginReadmeRegionContent(plugin) {
  const lines = [];
  lines.push("## What's inside");
  lines.push("");
  lines.push("**Skills** — invoked automatically by description match, or with `/<skill-name>`:");
  lines.push("");
  lines.push("| Skill | Description |");
  lines.push("| --- | --- |");
  for (const skill of plugin.skills) {
    const desc = rowEscape(frontmatterDescription(skill.path));
    lines.push(`| \`${skill.slug}\` | ${desc} |`);
  }
  lines.push("");
  lines.push("**Sub-agents** — call explicitly via `subagent_type`:");
  lines.push("");
  lines.push("| Agent | Description |");
  lines.push("| --- | --- |");
  for (const agent of plugin.agents) {
    const desc = rowEscape(frontmatterDescription(agent.path));
    const name = agent.filename.replace(/\.md$/, "");
    lines.push(`| \`${name}\` | ${desc} |`);
  }
  lines.push("");
  lines.push("**Slash commands:**");
  lines.push("");
  lines.push("| Command | Description |");
  lines.push("| --- | --- |");
  for (const command of plugin.commands) {
    const desc = rowEscape(frontmatterDescription(command.path));
    const name = command.filename.replace(/\.md$/, "");
    lines.push(`| \`/${name}\` | ${desc} |`);
  }
  return lines.join("\n");
}

// Compare an existing README's managed region with what regen would produce.
// Returns { inSync: bool, missing: bool, expected: string, next: string }.
// `missing: true` means the markers aren't present at all.
export function buildPluginReadmeRegion(plugin) {
  const expected = buildPluginReadmeRegionContent(plugin);
  if (!plugin.readmeContent) {
    return { inSync: false, missing: true, expected, next: null };
  }
  const beginIdx = plugin.readmeContent.indexOf(BEGIN_MARKER);
  const endIdx = plugin.readmeContent.indexOf(END_MARKER);
  if (beginIdx === -1 || endIdx === -1 || endIdx < beginIdx) {
    return { inSync: false, missing: true, expected, next: null };
  }
  const current = plugin.readmeContent.slice(beginIdx + BEGIN_MARKER.length, endIdx).trim();
  const inSync = current === expected.trim();
  const next = plugin.readmeContent.slice(0, beginIdx + BEGIN_MARKER.length)
    + "\n" + expected + "\n"
    + plugin.readmeContent.slice(endIdx);
  return { inSync, missing: false, expected, next };
}
