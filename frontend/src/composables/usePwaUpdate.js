/**
 * Service-worker update + offline-ready hooks for vite-plugin-pwa.
 *
 * Registers the SW once on module load. New builds AUTO-UPDATE: when a new
 * service worker is waiting, we immediately activate it and reload so users
 * never linger on a stale cached bundle after a deploy. Still exposes a
 * reactive `needsRefresh` flag + `reload()` helper (used by
 * UpdateAvailablePrompt as a fallback if auto-update can't run).
 *
 * In dev (vite-plugin-pwa devOptions.enabled = false), `registerSW` is a no-op
 * but the import is still safe — the virtual module always resolves.
 */
import { ref } from 'vue';

const needsRefresh = ref(false);
const offlineReady = ref(false);

let updateSWFn = null;

// Eager register: importing this composable triggers SW registration.
// Wrapped in a try/catch so test environments that stub the virtual module
// don't blow up.
async function init() {
  try {
    const { registerSW } = await import('virtual:pwa-register');
    updateSWFn = registerSW({
      onNeedRefresh() {
        needsRefresh.value = true;
        // Auto-update: activate the new service worker and reload as soon as a
        // new build is available, so nobody lingers on a stale cached bundle
        // (which previously left old markup/links — e.g. a hardcoded download
        // URL — live after a deploy). updateSWFn(true) posts SKIP_WAITING to
        // sw.js and reloads once the new SW takes control. The
        // UpdateAvailablePrompt remains as a fallback if the update fn is
        // unavailable.
        if (typeof updateSWFn === 'function') {
          updateSWFn(true);
        }
      },
      onOfflineReady() {
        offlineReady.value = true;
      },
    });
  } catch {
    // virtual:pwa-register unavailable (test env, dev with devOptions disabled).
    // Reload still works via the fallback in reload() below.
  }
}

// Fire-and-forget — caller doesn't need to await.
init();

export function usePwaUpdate() {
  return {
    needsRefresh,
    offlineReady,
    reload() {
      if (typeof updateSWFn === 'function') {
        // Tells Workbox to skipWaiting + reload the page.
        updateSWFn(true);
      } else {
        window.location.reload();
      }
    },
  };
}
