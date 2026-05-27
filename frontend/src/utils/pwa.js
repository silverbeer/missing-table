/**
 * Shared PWA detection helpers.
 *
 * Used by both IosInstallTooltip (decides whether to show the iOS-specific
 * install instructions) and NotificationsCard (decides whether to gate push
 * opt-in behind "install to home screen first").
 */

export function isIosSafari() {
  if (typeof window === 'undefined' || typeof navigator === 'undefined') {
    return false;
  }
  const ua = navigator.userAgent;
  const isIos =
    /iPad|iPhone|iPod/.test(ua) ||
    (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  if (!isIos) return false;
  // Exclude in-app browsers (Chrome on iOS / Firefox on iOS / Edge on iOS)
  // — they share WebKit but don't get the same PWA install affordances.
  const isSafari = /Safari/.test(ua) && !/CriOS|FxiOS|EdgiOS/.test(ua);
  return isSafari;
}

export function isStandalone() {
  if (typeof window === 'undefined') return false;
  // navigator.standalone is iOS-Safari-specific; matchMedia covers other PWAs.
  return (
    window.matchMedia?.('(display-mode: standalone)').matches ||
    window.navigator.standalone === true
  );
}

/**
 * iOS Safari users that aren't yet running as a standalone PWA.
 *
 * On iOS, Web Push requires the site to be installed to the home screen
 * AND iOS 16.4+. Browsers that aren't standalone can't subscribe even if
 * the user grants notification permission. UI should surface "install first"
 * instead of an enable button that silently fails.
 */
export function isIosNonStandalone() {
  return isIosSafari() && !isStandalone();
}
