import { defineConfig } from 'vite';
import { resolve } from 'node:path';

// GitHub Pages serves project sites from /<repo>/, custom domains from /.
// SITE_BASE lets the deploy workflow set the right prefix; inter-page links
// are relative (base-agnostic), so only hashed asset URLs depend on this.
const base = process.env.SITE_BASE || '/';

const root = import.meta.dirname;

export default defineConfig({
  base,
  appType: 'mpa',
  build: {
    target: 'es2022',
    outDir: 'dist',
    emptyOutDir: true,
    rollupOptions: {
      input: {
        home: resolve(root, 'index.html'),
        providers: resolve(root, 'providers/index.html'),
        pack: resolve(root, 'pack/index.html')
      }
    }
  },
  test: {
    environment: 'node',
    include: ['tests/**/*.test.js']
  }
});
