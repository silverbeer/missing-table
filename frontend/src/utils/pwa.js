/**
 * Shared PWA detection helpers.
 *
 * Used by the install banner, the notification setup guide (SB-810) and
 * NotificationsCard (decides whether to gate push opt-in behind
 * "install to home screen first").
 */

function ua() {
  if (typeof navigator === 'undefined') return '';
  return navigator.userAgent || '';
}

/**
 * Any iOS device, in ANY browser.
 *
 * Every iOS browser is WebKit under the hood, so the PWA and Web Push rules
 * are identical across Safari / Chrome / Firefox / Edge on iPhone. What
 * differs is only *where the Share control lives* — see getInstallSteps().
 * Detection must therefore not be Safari-only (SB-810: it was, so iPhone
 * users on Chrome saw no install banner at all).
 */
export function isIos() {
  if (typeof window === 'undefined' || typeof navigator === 'undefined') {
    return false;
  }
  return (
    /iPad|iPhone|iPod/.test(ua()) ||
    // iPadOS 13+ reports itself as a Mac; touch points give it away.
    (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)
  );
}

/**
 * iOS specifically in Safari (not Chrome/Firefox/Edge on iOS).
 *
 * Kept because the install *instructions* differ per browser — this is a
 * copy-selection helper, NOT a capability check. Use isIos() for anything
 * capability-related, since WebKit makes all iOS browsers behave the same.
 */
export function isIosSafari() {
  if (!isIos()) return false;
  return /Safari/.test(ua()) && !/CriOS|FxiOS|EdgiOS/.test(ua());
}

export function isStandalone() {
  if (typeof window === 'undefined') return false;
  // navigator.standalone is iOS-specific; matchMedia covers other PWAs.
  return (
    window.matchMedia?.('(display-mode: standalone)').matches ||
    window.navigator.standalone === true
  );
}

/**
 * iOS users that aren't yet running as a standalone PWA.
 *
 * On iOS, Web Push requires the site to be installed to the home screen
 * AND iOS 16.4+. A browser tab can't subscribe even if the user grants
 * notification permission — in fact iOS doesn't even expose PushManager
 * outside standalone mode, so a naive support check reports "unsupported
 * browser" when the honest answer is "install it first".
 */
export function isIosNonStandalone() {
  return isIos() && !isStandalone();
}

/** Rough browser family, used only to pick the right install wording. */
export function detectBrowser() {
  const s = ua();
  if (/CriOS|Chrome/.test(s) && !/EdgiOS|Edg/.test(s)) return 'chrome';
  if (/FxiOS|Firefox/.test(s)) return 'firefox';
  if (/EdgiOS|Edg/.test(s)) return 'edge';
  if (/Safari/.test(s)) return 'safari';
  return 'other';
}

/**
 * Step-by-step "add to home screen" instructions for the CURRENT browser.
 *
 * There is no programmatic install on iOS — `beforeinstallprompt` is
 * Chromium-only and Apple never shipped it. No web page can open Add to
 * Home Screen for the user. All we can do is point accurately at the
 * browser's own control, which is in a different place in each browser.
 *
 * Returns null when the current context needs no install (already
 * standalone, or a platform where push works in a normal tab).
 */
export function getInstallSteps() {
  if (isStandalone()) return null;
  if (!isIos()) return null;

  const browser = detectBrowser();

  if (browser === 'safari') {
    return {
      browserLabel: 'Safari',
      steps: [
        {
          title: 'Tap the Share button',
          detail:
            'It’s in the bar at the bottom of the screen — a square with an arrow pointing up. If you don’t see the bar, tap the very bottom of the screen to bring it back.',
        },
        {
          title: 'Scroll down to "Add to Home Screen"',
          // This is the step everyone gives up on — it is genuinely below
          // the fold, under the app row and the copy/bookmark rows.
          detail:
            'You have to scroll the grey menu down past the row of apps and past Copy and Add Bookmark. It’s further down than you expect.',
          emphasis: true,
        },
        {
          title: 'Tap "Add"',
          detail:
            'Top right corner. The Missing Table icon appears on your home screen — open it from there from now on.',
        },
      ],
    };
  }

  const label =
    browser === 'chrome' ? 'Chrome' : browser === 'edge' ? 'Edge' : 'Firefox';

  return {
    browserLabel: label,
    steps: [
      {
        title: `Open the ${label} menu`,
        detail:
          'Tap the ⋯ button. In Chrome and Edge it’s in the bottom-right; in Firefox it’s the ≡ button.',
      },
      {
        title: 'Choose Share, then "Add to Home Screen"',
        detail:
          'You may need to scroll the share menu down to find it — it sits below the row of apps.',
        emphasis: true,
      },
      {
        title: 'Tap "Add"',
        detail:
          'The Missing Table icon appears on your home screen — open it from there from now on.',
      },
    ],
  };
}

/**
 * Phone/tablet, roughly.
 *
 * Used to decide whether to volunteer the notification setup guide on login.
 * Push works on desktop too, but the install step is only a prerequisite on
 * mobile and an unsolicited modal on a laptop is just noise.
 */
export function isTouchDevice() {
  if (typeof window === 'undefined' || typeof navigator === 'undefined') {
    return false;
  }
  if (isIos()) return true;
  if (/Android/.test(ua())) return true;
  return (
    window.matchMedia?.('(pointer: coarse)').matches === true &&
    navigator.maxTouchPoints > 0
  );
}
