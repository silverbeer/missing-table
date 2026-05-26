/**
 * Service-worker update + offline-ready hooks for vite-plugin-pwa.
 *
 * Registers the SW once on module load. Exposes a reactive `needsRefresh`
 * flag that the UpdateAvailablePrompt component watches, plus a `reload()`
 * helper that activates the waiting SW and reloads the page.
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
