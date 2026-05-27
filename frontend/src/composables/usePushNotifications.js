/**
 * Push Notifications composable.
 *
 * Wraps the browser Push API + backend subscription registration. Exposes
 * reactive state the NotificationsCard component subscribes to, plus
 * imperative enable/disable/test helpers.
 *
 * The service worker is registered separately by usePwaUpdate.js (PR 2
 * inherits the same registration). This composable only handles the
 * subscription + opt-in flow on top of an already-registered SW.
 */

import { ref, computed } from 'vue';
import { useAuthStore } from '../stores/auth';
import { getApiBaseUrl } from '../config/api';
import { isIosNonStandalone } from '../utils/pwa';

const isSupported = ref(false);
const permission = ref('default'); // 'default' | 'granted' | 'denied' | 'unsupported'
// `null` = unknown (haven't asked backend yet), `true` = backend has at least
// one subscription for this user, `false` = backend has none. We need this
// because Notification.permission flips to 'granted' the instant the user
// clicks Allow — but the actual end-to-end registration (subscribe + POST)
// may still fail downstream. Using permission alone for the "enabled" pill
// caused SB-52 (UI looked enabled while backend had nothing).
const hasBackendSubscription = ref(null);
let initialized = false;

function detectSupport() {
  if (typeof window === 'undefined') return false;
  return (
    'serviceWorker' in navigator &&
    'PushManager' in window &&
    'Notification' in window
  );
}

function init() {
  if (initialized) return;
  initialized = true;
  isSupported.value = detectSupport();
  if (!isSupported.value) {
    permission.value = 'unsupported';
    return;
  }
  permission.value = Notification.permission;
}

/**
 * Convert URL-safe base64 (what VAPID public keys are stored as) to the
 * Uint8Array the browser's PushManager.subscribe() expects.
 */
function urlBase64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const raw = window.atob(base64);
  const output = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) {
    output[i] = raw.charCodeAt(i);
  }
  return output;
}

function detectDeviceLabel() {
  const ua = navigator.userAgent || '';
  let device = 'Device';
  if (/iPhone/.test(ua)) device = 'iPhone';
  else if (/iPad/.test(ua)) device = 'iPad';
  else if (/Pixel/.test(ua)) device = 'Pixel';
  else if (/Android/.test(ua)) device = 'Android';
  else if (/Macintosh/.test(ua)) device = 'Mac';
  else if (/Windows/.test(ua)) device = 'Windows';

  let browser = 'Browser';
  if (/EdgiOS|Edg/.test(ua)) browser = 'Edge';
  else if (/CriOS|Chrome/.test(ua)) browser = 'Chrome';
  else if (/FxiOS|Firefox/.test(ua)) browser = 'Firefox';
  else if (/Safari/.test(ua)) browser = 'Safari';

  return `${device} • ${browser}`;
}

export function usePushNotifications() {
  init();

  const authStore = useAuthStore();
  const loading = ref(false);
  const lastError = ref(null);

  // "Enabled" means the full chain landed: browser permission granted AND
  // the backend confirmed it has a subscription for this user/device. Using
  // permission alone caused SB-52 (pill showed enabled while backend had nothing
  // because the prior POST silently failed).
  const isEnabled = computed(
    () =>
      isSupported.value &&
      permission.value === 'granted' &&
      hasBackendSubscription.value === true
  );
  const isBlocked = computed(() => permission.value === 'denied');
  const isIosBlocked = computed(
    () => isSupported.value && isIosNonStandalone()
  );

  async function fetchVapidPublicKey() {
    const resp = await fetch(`${getApiBaseUrl()}/api/push/vapid-public-key`);
    if (resp.status === 503) {
      throw new Error('Push notifications are not configured on the server.');
    }
    if (!resp.ok) {
      throw new Error(`Failed to fetch VAPID key (HTTP ${resp.status})`);
    }
    const data = await resp.json();
    return data.publicKey;
  }

  async function getRegistration() {
    if (!('serviceWorker' in navigator)) {
      throw new Error('Service worker not available.');
    }
    const reg = await navigator.serviceWorker.ready;
    if (!reg) throw new Error('Service worker not ready.');
    return reg;
  }

  /**
   * End-to-end opt-in:
   *   1. Request OS permission (no-op if already granted).
   *   2. Fetch VAPID public key from backend.
   *   3. Subscribe via PushManager.
   *   4. POST subscription to backend.
   */
  async function enable(deviceLabel = null) {
    lastError.value = null;
    if (!isSupported.value) {
      lastError.value = 'Push notifications are not supported on this browser.';
      return { success: false, error: lastError.value };
    }
    if (isIosNonStandalone()) {
      lastError.value =
        'Install Missing Table to your home screen first, then enable notifications.';
      return { success: false, error: lastError.value };
    }

    loading.value = true;
    try {
      const result = await Notification.requestPermission();
      permission.value = result;
      if (result !== 'granted') {
        lastError.value =
          result === 'denied'
            ? 'Notifications were blocked. Open browser settings to re-enable.'
            : 'Notification permission was not granted.';
        return { success: false, error: lastError.value };
      }

      const vapidPublicKey = await fetchVapidPublicKey();
      const registration = await getRegistration();

      // If an old subscription exists (e.g. from a previous VAPID key), drop it.
      const existing = await registration.pushManager.getSubscription();
      if (existing) {
        await existing.unsubscribe().catch(() => {});
      }

      const subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(vapidPublicKey),
      });

      const subJson = subscription.toJSON();
      const payload = {
        endpoint: subJson.endpoint,
        keys: {
          p256dh: subJson.keys.p256dh,
          auth: subJson.keys.auth,
        },
        device_label: deviceLabel || detectDeviceLabel(),
        user_agent: navigator.userAgent.slice(0, 500),
      };

      const created = await authStore.apiRequest(
        `${getApiBaseUrl()}/api/users/me/push-subscriptions`,
        {
          method: 'POST',
          body: JSON.stringify(payload),
        }
      );

      hasBackendSubscription.value = true;
      return { success: true, subscription: created };
    } catch (err) {
      lastError.value = err.message || String(err);
      return { success: false, error: lastError.value };
    } finally {
      loading.value = false;
    }
  }

  async function disable(subscriptionId) {
    lastError.value = null;
    loading.value = true;
    try {
      await authStore.apiRequest(
        `${getApiBaseUrl()}/api/users/me/push-subscriptions/${subscriptionId}`,
        { method: 'DELETE' }
      );
      // Also clean up the OS-level subscription if it's the active one.
      try {
        const registration = await getRegistration();
        const active = await registration.pushManager.getSubscription();
        if (active) await active.unsubscribe();
      } catch {
        // ignore — backend revoke is the authoritative action.
      }
      hasBackendSubscription.value = false;
      return { success: true };
    } catch (err) {
      lastError.value = err.message || String(err);
      return { success: false, error: lastError.value };
    } finally {
      loading.value = false;
    }
  }

  async function listSubscriptions() {
    try {
      const data = await authStore.apiRequest(
        `${getApiBaseUrl()}/api/users/me/push-subscriptions`
      );
      const subs = data?.subscriptions || [];
      // This is the authoritative truth-source for whether the backend has
      // a subscription for this user. Sync the reactive flag so the UI
      // doesn't trust permission alone.
      hasBackendSubscription.value = subs.length > 0;
      return subs;
    } catch (err) {
      lastError.value = err.message || String(err);
      // On fetch failure, assume no backend subscription so the UI shows
      // Enable instead of a misleading enabled pill.
      hasBackendSubscription.value = false;
      return [];
    }
  }

  async function sendTest() {
    lastError.value = null;
    loading.value = true;
    try {
      const data = await authStore.apiRequest(
        `${getApiBaseUrl()}/api/users/me/notifications/test`,
        { method: 'POST' }
      );
      return { success: true, data };
    } catch (err) {
      lastError.value = err.message || String(err);
      return { success: false, error: lastError.value };
    } finally {
      loading.value = false;
    }
  }

  return {
    // reactive state
    isSupported,
    permission,
    isEnabled,
    isBlocked,
    isIosBlocked,
    loading,
    lastError,
    // imperative
    enable,
    disable,
    listSubscriptions,
    sendTest,
  };
}
