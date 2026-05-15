// Shared parsers for SKILL.md / agent.md files. One module so the validator,
// the regen scripts, and any future tooling agree on what a "checklist" is
// and where the load-bearing sections live.

import { readFileSync } from "node:fs";
import matter from "gray-matter";

// Pull the body of a `## <heading>` section out of a markdown document.
// Returns the text between the heading and the next `## ` heading (or end
// of document), or null if the heading is absent.
export function extractSection(markdown, heading) {
  const lines = markdown.split("\n");
  const startRe = new RegExp(`^##\\s+${escapeRegex(heading)}\\s*$`);
  let start = -1;
  for (let i = 0; i < lines.length; i++) {
    if (startRe.test(lines[i])) { start = i + 1; break; }
  }
  if (start === -1) return null;
  let end = lines.length;
  for (let i = start; i < lines.length; i++) {
    if (/^##\s+/.test(lines[i])) { end = i; break; }
  }
  return lines.slice(start, end).join("\n");
}

// Sections every architect.md must contain. Names follow the AWS gold-standard
// (cloud-aws/agents/aws-architect.md). Drift from these is a real signal that
// an agent is structurally different from the rest of the marketplace and
// either needs alignment or a documented exception.
export const ARCHITECT_REQUIRED_SECTIONS = [
  "Inputs you expect",
  "Review process",
  "Output format",
  "Rules of engagement",
];

// Sections every security-reviewer.md must contain. Different shape than the
// architect — the report schema lives in subsections of '## Output' rather
// than a single '## Output format' block.
export const SECURITY_REVIEWER_REQUIRED_SECTIONS = [
  "Inputs",
  "Review scope — what you check",
  "Output",
  "Rules of engagement",
];

// Parse the checklist items out of the load-bearing `## Verification checklist`
// section of a SKILL.md. Returns the list of item texts, or [] if the section
// is absent. Item format is GitHub-style markdown task lists: `- [ ] <text>`.
export function parseChecklist(markdown) {
  const body = extractSection(markdown, "Verification checklist");
  if (body == null) return [];
  const items = [];
  for (const line of body.split("\n")) {
    const m = line.match(/^\s*-\s+\[([ xX])\]\s+(.+?)\s*$/);
    if (m) items.push({ checked: m[1].toLowerCase() === "x", text: m[2] });
  }
  return items;
}

// Read + parse a markdown file with YAML frontmatter. Returns { data, content }
// or { error } if YAML parse fails (commonly: unquoted colon inside a value).
export function readMarkdown(path) {
  const raw = readFileSync(path, "utf8");
  try {
    const parsed = matter(raw);
    return { data: parsed.data, content: parsed.content };
  } catch (e) {
    return { error: e.reason || e.message };
  }
}

function escapeRegex(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
