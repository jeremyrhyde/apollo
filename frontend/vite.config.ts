/// <reference types="vitest/config" />
import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

// Served by FastAPI at /ui/; in dev, Vite serves the UI and forwards /api.
export default defineConfig({
  base: '/ui/',
  plugins: [svelte()],
  server: {
    port: 5173,
    proxy: { '/api': 'http://localhost:8000' },
  },
  build: { outDir: 'dist', emptyOutDir: true },
  // passWithNoTests: this scaffold predates any *.test.ts files (Task 2 adds
  // the first ones); without it vitest exits non-zero on an empty suite.
  test: { include: ['src/**/*.test.ts'], environment: 'node', passWithNoTests: true },
});
