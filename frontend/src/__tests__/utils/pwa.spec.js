/**
 * utils/pwa.js tests (SB-121).
 *
 * These helpers decide whether the iOS "Add to Home Screen" tooltip and the
 * "install first" push gating appear. The decision matrix is UA- and
 * display-mode-driven, so we stub navigator/matchMedia per case.
 *
 * Covers:
 * - isIosSafari: true only for real iOS Safari (and iPadOS-on-desktop-UA),
 *   false for iOS Chrome/Firefox/Edge (CriOS/FxiOS/EdgiOS) and non-iOS.
 * - isStandalone: matchMedia(display-mode: standalone) OR navigator.standalone.
 * - isIosNonStandalone: the AND of "iOS Safari" and "not standalone".
 */

import { describe, it, expect, afterEach } from 'vitest';
import {
  isIos,
  isIosSafari,
  isStandalone,
  isIosNonStandalone,
  detectBrowser,
  getInstallSteps,
  isTouchDevice,
} from '@/utils/pwa';

const IOS_SAFARI_UA =
  'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1';
const IOS_CHROME_UA =
  'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/120.0 Mobile/15E148 Safari/604.1';
const MAC_SAFARI_UA =
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15';
const ANDROID_CHROME_UA =
  'Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36';

function stubNavigator({
  userAgent,
  platform = 'iPhone',
  maxTouchPoints = 5,
  standalone,
}) {
  Object.defineProperty(navigator, 'userAgent', {
    value: userAgent,
    configurable: true,
  });
  Object.defineProperty(navigator, 'platform', {
    value: platform,
    configurable: true,
  });
  Object.defineProperty(navigator, 'maxTouchPoints', {
    value: maxTouchPoints,
    configurable: true,
  });
  Object.defineProperty(navigator, 'standalone', {
    value: standalone,
    configurable: true,
  });
}

function stubMatchMedia(standaloneMatches) {
  window.matchMedia = query => ({
    matches: query === '(display-mode: standalone)' ? standaloneMatches : false,
    media: query,
    addEventListener: () => {},
    removeEventListener: () => {},
  });
}

afterEach(() => {
  // Reset to a benign desktop-ish baseline so cases don't leak.
  stubNavigator({
    userAgent: MAC_SAFARI_UA,
    platform: 'MacIntel',
    maxTouchPoints: 0,
    standalone: undefined,
  });
  stubMatchMedia(false);
});

describe('isIosSafari', () => {
  it('true for iOS Safari', () => {
    stubNavigator({ userAgent: IOS_SAFARI_UA });
    expect(isIosSafari()).toBe(true);
  });

  it('false for iOS Chrome (CriOS)', () => {
    stubNavigator({ userAgent: IOS_CHROME_UA });
    expect(isIosSafari()).toBe(false);
  });

  it('true for iPadOS reporting a desktop UA (MacIntel + touch)', () => {
    stubNavigator({
      userAgent: MAC_SAFARI_UA,
      platform: 'MacIntel',
      maxTouchPoints: 5,
    });
    expect(isIosSafari()).toBe(true);
  });

  it('false for a real desktop Mac (MacIntel, no touch)', () => {
    stubNavigator({
      userAgent: MAC_SAFARI_UA,
      platform: 'MacIntel',
      maxTouchPoints: 0,
    });
    expect(isIosSafari()).toBe(false);
  });

  it('false for Android Chrome', () => {
    stubNavigator({
      userAgent: ANDROID_CHROME_UA,
      platform: 'Linux armv8l',
      maxTouchPoints: 5,
    });
    expect(isIosSafari()).toBe(false);
  });
});

describe('isStandalone', () => {
  it('true when display-mode matchMedia matches', () => {
    stubNavigator({ userAgent: IOS_SAFARI_UA, standalone: undefined });
    stubMatchMedia(true);
    expect(isStandalone()).toBe(true);
  });

  it('true when navigator.standalone is set (iOS Safari)', () => {
    stubNavigator({ userAgent: IOS_SAFARI_UA, standalone: true });
    stubMatchMedia(false);
    expect(isStandalone()).toBe(true);
  });

  it('false when neither signal is present', () => {
    stubNavigator({ userAgent: IOS_SAFARI_UA, standalone: false });
    stubMatchMedia(false);
    expect(isStandalone()).toBe(false);
  });
});

describe('isIosNonStandalone', () => {
  it('true for iOS Safari not yet installed', () => {
    stubNavigator({ userAgent: IOS_SAFARI_UA, standalone: false });
    stubMatchMedia(false);
    expect(isIosNonStandalone()).toBe(true);
  });

  it('false once installed (standalone)', () => {
    stubNavigator({ userAgent: IOS_SAFARI_UA, standalone: true });
    stubMatchMedia(true);
    expect(isIosNonStandalone()).toBe(false);
  });

  it('false on non-iOS even when not standalone', () => {
    stubNavigator({
      userAgent: ANDROID_CHROME_UA,
      platform: 'Linux armv8l',
      maxTouchPoints: 5,
      standalone: false,
    });
    stubMatchMedia(false);
    expect(isIosNonStandalone()).toBe(false);
  });
});

// --- SB-810 -----------------------------------------------------------------
// Every iOS browser is WebKit, so the install requirement is identical across
// them. Detection used to be Safari-only, which meant iPhone users on Chrome
// were told nothing at all.

const IOS_FIREFOX_UA =
  'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) FxiOS/120.0 Mobile/15E148 Safari/605.1.15';

describe('isIos — browser-independent', () => {
  it('true for iOS Safari', () => {
    stubNavigator({ userAgent: IOS_SAFARI_UA });
    expect(isIos()).toBe(true);
  });

  it('true for iOS Chrome — same WebKit, same install rules', () => {
    stubNavigator({ userAgent: IOS_CHROME_UA });
    expect(isIos()).toBe(true);
  });

  it('true for iOS Firefox', () => {
    stubNavigator({ userAgent: IOS_FIREFOX_UA });
    expect(isIos()).toBe(true);
  });

  it('false for Android Chrome', () => {
    stubNavigator({
      userAgent: ANDROID_CHROME_UA,
      platform: 'Linux armv8l',
      maxTouchPoints: 5,
    });
    expect(isIos()).toBe(false);
  });
});

describe('isIosNonStandalone — covers non-Safari iOS browsers', () => {
  it('true for iOS Chrome not yet installed (regression: used to be false)', () => {
    stubNavigator({ userAgent: IOS_CHROME_UA, standalone: false });
    stubMatchMedia(false);
    expect(isIosNonStandalone()).toBe(true);
  });

  it('false for iOS Chrome once installed', () => {
    stubNavigator({ userAgent: IOS_CHROME_UA, standalone: true });
    stubMatchMedia(true);
    expect(isIosNonStandalone()).toBe(false);
  });
});

describe('detectBrowser', () => {
  it('identifies iOS Safari', () => {
    stubNavigator({ userAgent: IOS_SAFARI_UA });
    expect(detectBrowser()).toBe('safari');
  });

  it('identifies iOS Chrome (CriOS)', () => {
    stubNavigator({ userAgent: IOS_CHROME_UA });
    expect(detectBrowser()).toBe('chrome');
  });

  it('identifies iOS Firefox (FxiOS)', () => {
    stubNavigator({ userAgent: IOS_FIREFOX_UA });
    expect(detectBrowser()).toBe('firefox');
  });
});

describe('getInstallSteps', () => {
  it('returns Safari-specific steps on iOS Safari', () => {
    stubNavigator({ userAgent: IOS_SAFARI_UA, standalone: false });
    stubMatchMedia(false);
    const guide = getInstallSteps();
    expect(guide.browserLabel).toBe('Safari');
    expect(guide.steps).toHaveLength(3);
    expect(guide.steps[0].detail).toMatch(/bottom/i);
  });

  it('flags the below-the-fold share-sheet step — where users give up', () => {
    stubNavigator({ userAgent: IOS_SAFARI_UA, standalone: false });
    stubMatchMedia(false);
    const emphasised = getInstallSteps().steps.filter(s => s.emphasis);
    expect(emphasised).toHaveLength(1);
    expect(emphasised[0].title).toMatch(/Add to Home Screen/);
  });

  it("gives Chrome users their own menu, not Safari's bottom toolbar", () => {
    stubNavigator({ userAgent: IOS_CHROME_UA, standalone: false });
    stubMatchMedia(false);
    const guide = getInstallSteps();
    expect(guide.browserLabel).toBe('Chrome');
    expect(guide.steps[0].title).toMatch(/Chrome menu/);
  });

  it('returns null once installed — nothing left to teach', () => {
    stubNavigator({ userAgent: IOS_SAFARI_UA, standalone: true });
    stubMatchMedia(true);
    expect(getInstallSteps()).toBeNull();
  });

  it('returns null off iOS — no install step is required there', () => {
    stubNavigator({
      userAgent: ANDROID_CHROME_UA,
      platform: 'Linux armv8l',
      maxTouchPoints: 5,
      standalone: false,
    });
    stubMatchMedia(false);
    expect(getInstallSteps()).toBeNull();
  });
});

describe('isTouchDevice', () => {
  it('true on iPhone', () => {
    stubNavigator({ userAgent: IOS_SAFARI_UA });
    expect(isTouchDevice()).toBe(true);
  });

  it('true on Android', () => {
    stubNavigator({
      userAgent: ANDROID_CHROME_UA,
      platform: 'Linux armv8l',
      maxTouchPoints: 5,
    });
    expect(isTouchDevice()).toBe(true);
  });

  it('false on a desktop Mac — an unsolicited modal there is just noise', () => {
    stubNavigator({
      userAgent: MAC_SAFARI_UA,
      platform: 'MacIntel',
      maxTouchPoints: 0,
    });
    stubMatchMedia(false);
    expect(isTouchDevice()).toBe(false);
  });
});
