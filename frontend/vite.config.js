import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import { VitePWA } from 'vite-plugin-pwa';
import { fileURLToPath, URL } from 'node:url';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    VitePWA({
      // injectManifest: we ship a hand-written SW (frontend/src/sw.js) that
      // uses Workbox helpers for precache + runtime cache AND adds custom
      // push + notificationclick event handlers. `generateSW` doesn't allow
      // custom event handlers, hence the migration in SB-47.
      strategies: 'injectManifest',
      srcDir: 'src',
      filename: 'sw.js',
      registerType: 'prompt', // UpdateAvailablePrompt handles new versions
      includeAssets: [
        'pwa/apple-touch-icon-180.png',
        'pwa/pwa-icon-master.png',
        'hero-goal.png',
      ],
      manifest: {
        name: 'Missing Table',
        short_name: 'MT',
        description:
          'MLS Next league standings, schedules, and live match scoring',
        start_url: '/',
        scope: '/',
        display: 'standalone',
        orientation: 'any',
        background_color: '#f8fafc',
        theme_color: '#0257fe',
        lang: 'en-US',
        categories: ['sports'],
        icons: [
          {
            src: '/pwa/icon-192.png',
            sizes: '192x192',
            type: 'image/png',
            purpose: 'any',
          },
          {
            src: '/pwa/icon-256.png',
            sizes: '256x256',
            type: 'image/png',
            purpose: 'any',
          },
          {
            src: '/pwa/icon-384.png',
            sizes: '384x384',
            type: 'image/png',
            purpose: 'any',
          },
          {
            src: '/pwa/icon-512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'any maskable',
          },
        ],
      },
      injectManifest: {
        // Precache the build output (app shell). Workbox builds the manifest
        // from these globs at build time and injects it into sw.js via
        // self.__WB_MANIFEST.
        globPatterns: ['**/*.{js,css,html,ico,png,svg,woff,woff2}'],
        // Don't precache the giant master icon source (only used for SB-45 swap).
        globIgnores: ['**/pwa/pwa-icon-master.png'],
      },
      devOptions: {
        // Don't enable the SW in `vite dev` by default. SW + HMR fight each
        // other; turn this on temporarily if you need to debug the SW locally.
        enabled: false,
      },
    }),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 8080,
    host: '0.0.0.0',
  },
  preview: {
    port: 8080,
    host: '0.0.0.0',
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    // Reduce chunk size warnings threshold
    chunkSizeWarningLimit: 1000,
  },
});
