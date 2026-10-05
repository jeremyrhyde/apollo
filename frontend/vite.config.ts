/// <reference types="vitest/config" />
import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

// Served by FastAPI at /ui/; in dev, Vite serves the UI and forwards /api.
export default defineConfig({
  base: '/ui/',
  plugins: [svelte()],
  server: {
    port: 5173,
    proxy: { '/api': 'http://localhost:8001', '/health': 'http://localhost:8001' },
  },
  build: { outDir: 'dist', emptyOutDir: true },
  test: { include: ['src/**/*.test.ts'], environment: 'node' },
});
