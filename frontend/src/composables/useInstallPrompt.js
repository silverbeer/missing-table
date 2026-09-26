/**
 * Native install prompt (SB-813).
 *
 * Chromium fires `beforeinstallprompt` when a site meets the installability
 * criteria. Suppressing the default mini-infobar and stashing the event lets us
 * offer install at a moment that makes sense, with a real one-tap button.
 *
 * This is Android/desktop only, and it is the mirror image of the iOS problem:
 * there we have no install API and must hand-write instructions (SB-810);
 * here the browser hands us a working one and MT simply never used it.
 *
 * Two rules the API imposes:
 *   - `prompt()` must be called from a user gesture, so the event is stored
 *     rather than fired on arrival
 *   - each captured event is single-use; after prompting it must be discarded
 *
 * Listeners attach at module load, not inside a component: the event fires
 * early in page life and is offered exactly once, so a listener registered
 * after mount can miss it entirely. main.js imports this for that reason.
 */

import { ref, computed } from 'vue';
import { isStandalone } from '../utils/pwa';

// The stashed BeforeInstallPromptEvent. Deliberately not a ref — it's a
// non-reactive browser object; `canInstall` carries the reactive signal.
let deferredPrompt = null;

const promptAvailable = ref(false);
const installed = ref(false);
const prompting = ref(false);

function onBeforeInstallPrompt(event) {
  // Stops Chrome's own mini-infobar so we control placement and timing.
  event.preventDefault();
  deferredPrompt = event;
  promptAvailable.value = true;
}

function onAppInstalled() {
  installed.value = true;
  promptAvailable.value = false;
  deferredPrompt = null;
}

if (typeof window !== 'undefined') {
  window.addEventListener('beforeinstallprompt', onBeforeInstallPrompt);
  window.addEventListener('appinstalled', onAppInstalled);
}

export function useInstallPrompt() {
  // Already running as an installed app: nothing to offer. Checked live rather
  // than cached, since a session can start in a tab and continue standalone.
  const canInstall = computed(
    () => promptAvailable.value && !installed.value && !isStandalone()
  );

  /**
   * Fire the native install dialog. Must be called from a user gesture.
   *
   * Returns the user's choice. A dismissal is not a failure — Chrome may hand
   * us another event later, but this particular one is spent either way.
   */
  async function promptInstall() {
    if (!deferredPrompt || prompting.value) {
      return { outcome: 'unavailable' };
    }
    prompting.value = true;
    try {
      const event = deferredPrompt;
      // Discard before awaiting: the event is single-use, and leaving it in
      // place would let a second tap call prompt() on a spent event.
      deferredPrompt = null;
      promptAvailable.value = false;

      event.prompt();
      const choice = await event.userChoice;
      if (choice?.outcome === 'accepted') installed.value = true;
      return { outcome: choice?.outcome || 'dismissed' };
    } catch {
      // A spent or invalidated event throws; treat it as nothing to offer.
      return { outcome: 'unavailable' };
    } finally {
      prompting.value = false;
    }
  }

  return {
    canInstall,
    installed: computed(() => installed.value),
    prompting: computed(() => prompting.value),
    promptInstall,
  };
}

// Test-only: reset module-level singleton between tests.
export function _resetInstallPromptForTest() {
  deferredPrompt = null;
  promptAvailable.value = false;
  installed.value = false;
  prompting.value = false;
}

// Test-only: inject a fake BeforeInstallPromptEvent without dispatching.
export function _setDeferredPromptForTest(event) {
  deferredPrompt = event;
  promptAvailable.value = !!event;
}
