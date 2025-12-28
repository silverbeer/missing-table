import { defineConfig } from 'vitest/config';
import vue from '@vitejs/plugin-vue';
import { fileURLToPath, URL } from 'node:url';

// Vitest configuration for Vue component testing
// Docs: https://vitest.dev/config/
export default defineConfig({
  plugins: [vue()],

  // Path aliases - must match vite.config.js so imports like '@/stores/auth' work
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },

  test: {
    // Use happy-dom for fast DOM simulation (alternative: 'jsdom' is slower but more complete)
    environment: 'happy-dom',

    // Global test APIs - makes describe, it, expect available without importing
    globals: true,

    // Setup file runs before each test file
    setupFiles: ['./src/__tests__/setup.js'],

    // Where to look for test files
    include: ['src/**/*.{test,spec}.{js,ts}'],

    // Coverage configuration (optional, for 'npm run test:coverage')
    coverage: {
      provider: 'v8', // Uses V8's built-in coverage (fast)
      reporter: ['text', 'html'], // Output formats: terminal + HTML report
      include: ['src/**/*.{js,vue}'],
      exclude: [
        'src/__tests__/**', // Don't measure coverage of test files themselves
        'src/main.js', // Entry point, not much to test
        'src/faro.js', // Observability setup
      ],
    },
  },
});
