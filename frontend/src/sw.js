/* eslint-env serviceworker */
/**
 * Missing Table service worker.
 *
 * Generated into dist/sw.js by vite-plugin-pwa in `injectManifest` mode. The
 * plugin injects `self.__WB_MANIFEST` with the precache list at build time;
 * the rest is hand-written so we can attach push + notificationclick handlers
 * that `generateSW` doesn't allow.
 *
 * What this SW does:
 *  1. Precaches the app shell (HTML, JS, CSS, icons).
 *  2. Runtime-caches read-only API responses (standings, teams, etc.) with
 *     stale-while-revalidate.
 *  3. Runtime-caches Google Fonts cache-first.
 *  4. Serves /index.html for SPA navigation requests when offline.
 *  5. Receives Web Push messages and displays notifications.
 *  6. Routes notification clicks to the live match view (or app root).
 *
 * Deliberately NOT done here:
 *  - clientsClaim / skipWaiting on install — UpdateAvailablePrompt handles
 *    new versions explicitly via user click, no surprise reloads.
 */

import { precacheAndRoute, createHandlerBoundToURL } from 'workbox-precaching';
import { registerRoute, NavigationRoute } from 'workbox-routing';
import { CacheFirst, StaleWhileRevalidate } from 'workbox-strategies';
import { CacheableResponsePlugin } from 'workbox-cacheable-response';
import { ExpirationPlugin } from 'workbox-expiration';

// ---------------------------------------------------------------------------
// Precache (app shell)
// ---------------------------------------------------------------------------

precacheAndRoute(self.__WB_MANIFEST);

// SPA navigation fallback — any client-side route serves /index.html so the
// Vue router can render the right view. /api/* is denylisted so we never
// shadow real API responses.
registerRoute(
  new NavigationRoute(createHandlerBoundToURL('/index.html'), {
    denylist: [/^\/api\//],
  })
);

// ---------------------------------------------------------------------------
// Runtime caching
// ---------------------------------------------------------------------------

// Read-only reference + standings APIs. Stale-while-revalidate: serve cache
// instantly, refresh in background, next render is fresh. NOT cached: auth,
// writes, live-match state — those need to be live.
registerRoute(
  ({ url, request }) =>
    request.method === 'GET' &&
    /\/api\/(standings|teams|match-types|seasons|age-groups|divisions|leagues|tournaments|clubs)(\/|\?|$)/.test(
      url.pathname + url.search
    ),
  new StaleWhileRevalidate({
    cacheName: 'mt-reference-and-standings-v1',
    plugins: [
      new ExpirationPlugin({ maxEntries: 50, maxAgeSeconds: 60 * 60 * 24 * 7 }),
      new CacheableResponsePlugin({ statuses: [0, 200] }),
    ],
  }),
  'GET'
);

// Google Fonts — versioned URLs, rarely change, cache-first.
registerRoute(
  ({ url }) => /^https:\/\/fonts\.(googleapis|gstatic)\.com\/.*/.test(url.href),
  new CacheFirst({
    cacheName: 'google-fonts-v1',
    plugins: [
      new ExpirationPlugin({
        maxEntries: 20,
        maxAgeSeconds: 60 * 60 * 24 * 365,
      }),
      new CacheableResponsePlugin({ statuses: [0, 200] }),
    ],
  })
);

// ---------------------------------------------------------------------------
// Update flow
// ---------------------------------------------------------------------------

// When the page asks us to activate immediately (from UpdateAvailablePrompt's
// reload button), do it. Otherwise wait for the next natural page load.
self.addEventListener('message', event => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});

// ---------------------------------------------------------------------------
// Push notifications (SB-47)
// ---------------------------------------------------------------------------

self.addEventListener('push', event => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch {
    data = { title: 'Missing Table', body: event.data?.text?.() ?? '' };
  }

  const {
    title = 'Missing Table',
    body = '',
    icon = '/pwa/icon-192.png',
    badge = '/pwa/icon-192.png',
    tag,
    data: payloadData,
  } = data;

  event.waitUntil(
    self.registration.showNotification(title, {
      body,
      icon,
      badge,
      tag,
      data: payloadData,
      // Match events are time-sensitive — don't sit silent in the background.
      requireInteraction: false,
      renotify: false,
    })
  );
});

self.addEventListener('notificationclick', event => {
  event.notification.close();
  const targetUrl = event.notification.data?.url || '/';

  event.waitUntil(
    clients
      .matchAll({ type: 'window', includeUncontrolled: true })
      .then(windowClients => {
        // If an MT window is already open, focus it and navigate inside.
        const scope = self.registration.scope;
        const existing = windowClients.find(client =>
          client.url.startsWith(scope)
        );
        if (existing) {
          existing.focus();
          if ('navigate' in existing) {
            return existing.navigate(targetUrl);
          }
          return;
        }
        // Otherwise open a new window/tab at the target URL.
        return clients.openWindow(targetUrl);
      })
  );
});
