import { describe, it, expect } from 'vitest';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, extname } from 'node:path';

const siteRoot = join(import.meta.dirname, '..');

/** Collect site source files whose copy ships to users. */
function sourceFiles() {
  const out = [
    join(siteRoot, 'index.html'),
    join(siteRoot, 'providers', 'index.html'),
    join(siteRoot, 'pack', 'index.html'),
    join(siteRoot, 'README.md')
  ];
  const walk = (dir) => {
    for (const name of readdirSync(dir)) {
      const p = join(dir, name);
      if (statSync(p).isDirectory()) {
        walk(p);
      } else if (['.js', '.css'].includes(extname(p))) {
        out.push(p);
      }
    }
  };
  walk(join(siteRoot, 'src'));
  return out;
}

describe('house style: no em-dashes', () => {
  // Acceptance criterion: copy has zero em-dashes. We also forbid the en-dash
  // used as punctuation; ranges read as "x to y" instead.
  const banned = { '—': 'em-dash', '–': 'en-dash' };

  for (const file of sourceFiles()) {
    it(`is clean: ${file.replace(siteRoot + '/', '')}`, () => {
      const text = readFileSync(file, 'utf8');
      for (const [char, label] of Object.entries(banned)) {
        const idx = text.indexOf(char);
        if (idx !== -1) {
          const around = text.slice(Math.max(0, idx - 40), idx + 40);
          expect.fail(`found ${label} (${JSON.stringify(char)}) near: ...${around}...`);
        }
      }
    });
  }
});
