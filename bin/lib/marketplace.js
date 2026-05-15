// Shared helpers for the validator and the marketplace.json regen script.
// One source of truth for: how to find plugins on disk, and how to project
// each plugin's metadata into a marketplace entry.

import { readFileSync, readdirSync, existsSync, statSync } from "node:fs";
import { join } from "node:path";

export function loadPluginManifests(repoRoot) {
  const out = [];
  for (const entry of readdirSync(repoRoot).sort()) {
    if (!entry.startsWith("cloud-")) continue;
    const dir = join(repoRoot, entry);
    if (!statSync(dir).isDirectory()) continue;
    const path = join(dir, ".claude-plugin", "plugin.json");
    if (!existsSync(path)) continue;
    const manifest = JSON.parse(readFileSync(path, "utf8"));
    out.push({ dir, path, manifest });
  }
  return out;
}

export function pluginToMarketplaceEntry(manifest) {
  return {
    name: manifest.name,
    source: `./${manifest.name}`,
    description: manifest.description,
    version: manifest.version,
  };
}

// Build the canonical marketplace.json shape from plugin manifests.
// Order is preserved from `existing.plugins` (curated by category in
// README.md). New plugins not yet listed are appended alphabetically.
// Top-level fields (name, owner, metadata) are sourced from `existing` so
// the regen never clobbers the marketplace's own identity.
export function buildMarketplaceFromPlugins(pluginManifests, existing = {}) {
  const byName = new Map(pluginManifests.map(({ manifest }) => [manifest.name, manifest]));
  const existingOrder = (existing.plugins ?? []).map((p) => p.name);
  const ordered = [];
  const seen = new Set();
  for (const name of existingOrder) {
    if (byName.has(name)) {
      ordered.push(byName.get(name));
      seen.add(name);
    }
  }
  for (const { manifest } of pluginManifests) {
    if (!seen.has(manifest.name)) {
      ordered.push(manifest);
    }
  }
  return {
    name: existing.name ?? "blackrim-cloud-toolkits",
    owner: existing.owner ?? { name: "Blackrim.dev" },
    metadata: existing.metadata ?? {
      description: "Cloud-development plugins for Claude Code.",
    },
    plugins: ordered.map(pluginToMarketplaceEntry),
  };
}
