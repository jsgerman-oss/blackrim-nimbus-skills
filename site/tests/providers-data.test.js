import { describe, it, expect } from 'vitest';
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { providers, goldenStack } from '../src/lib/providers-data.js';

const siteRoot = join(import.meta.dirname, '..');
const repoRoot = join(siteRoot, '..');

describe('provider data', () => {
  it('lists exactly 19 clouds', () => {
    expect(providers).toHaveLength(19);
  });

  it('has unique ids', () => {
    const ids = providers.map((p) => p.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it('lights Cloudflare as the single golden-path target', () => {
    const golden = providers.filter((p) => p.path === 'golden');
    expect(golden).toHaveLength(1);
    expect(golden[0].id).toBe('cloudflare');
  });

  it('ids match the cloud-<id> plugin directories at the repo root', () => {
    const dirIds = readdirSync(repoRoot)
      .filter((n) => n.startsWith('cloud-'))
      .map((n) => n.slice('cloud-'.length))
      .sort();
    const dataIds = providers.map((p) => p.id).sort();
    expect(dataIds).toEqual(dirIds);
  });

  it('describes the golden stack: vite, voidzero, Cloudflare, Convex', () => {
    expect(goldenStack.map((s) => s.name)).toEqual(['Vite', 'voidzero', 'Cloudflare', 'Convex']);
  });
});

describe('cloud matrix markup stays in sync with the data', () => {
  const html = readFileSync(join(siteRoot, 'providers', 'index.html'), 'utf8');

  for (const p of providers) {
    it(`renders ${p.id}: label, best-for line, and data attribute`, () => {
      expect(html).toContain(`data-provider="${p.id}"`);
      expect(html).toContain(p.label);
      expect(html).toContain(p.best);
    });
  }

  it('marks Cloudflare as the golden-path cell', () => {
    expect(html).toContain('data-provider="cloudflare" data-path="golden"');
  });
});
