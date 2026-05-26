import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import { VitePWA } from 'vite-plugin-pwa';
import { fileURLToPath, URL } from 'node:url';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    VitePWA({
      // generateSW: Workbox generates the service worker for us. injectManifest
      // mode is only needed if we want to ship custom SW code; for slice 3 the
      // generated SW covers precache + runtime cache cleanly.
      strategies: 'generateSW',
      registerType: 'prompt', // shows our UpdateAvailablePrompt instead of auto-reloading
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
      workbox: {
        // Precache the build output (app shell). Workbox builds the manifest
        // from these globs at build time.
        globPatterns: ['**/*.{js,css,html,ico,png,svg,woff,woff2}'],
        // Don't try to precache the giant master icon source (only used for SB-45 swap).
        globIgnores: ['**/pwa/pwa-icon-master.png'],
        // SPA fallback: any navigation request not matched by a precached file
        // should serve /index.html (so client-side routes work offline).
        navigateFallback: '/index.html',
        navigateFallbackDenylist: [/^\/api\//],
        // Runtime caching for read-only API endpoints. Stale-while-revalidate:
        // serve cache instantly, refresh in background, next render is fresh.
        // Skipped: auth, write endpoints, live-match state (push keeps that fresh).
        runtimeCaching: [
          {
            urlPattern: ({ url, request }) =>
              request.method === 'GET' &&
              /\/api\/(standings|teams|match-types|seasons|age-groups|divisions|leagues|tournaments|clubs)(\/|\?|$)/.test(
                url.pathname + url.search
              ),
            handler: 'StaleWhileRevalidate',
            options: {
              cacheName: 'mt-reference-and-standings-v1',
              expiration: { maxEntries: 50, maxAgeSeconds: 60 * 60 * 24 * 7 }, // 7 days
              cacheableResponse: { statuses: [0, 200] },
            },
          },
          {
            // Google Fonts — cache-first since they're versioned URLs and rarely change.
            urlPattern: /^https:\/\/fonts\.(googleapis|gstatic)\.com\/.*/,
            handler: 'CacheFirst',
            options: {
              cacheName: 'google-fonts-v1',
              expiration: { maxEntries: 20, maxAgeSeconds: 60 * 60 * 24 * 365 },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
        ],
        // Don't take over the page immediately on first install — let it become
        // the controller on the next nav. UpdateAvailablePrompt handles new
        // versions explicitly.
        clientsClaim: false,
        skipWaiting: false,
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
