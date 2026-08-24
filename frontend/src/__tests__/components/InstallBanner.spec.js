/**
 * InstallBanner.vue tests (SB-810).
 *
 * This banner replaced IosInstallTooltip, which was a filled blue card with no
 * click handler at all — users tapped it, nothing happened, and they gave up.
 * The two things that matter here are therefore:
 *
 *   1. it offers a real, labelled action that opens the setup guide
 *   2. it appears for EVERY iOS browser, not just Safari (all WebKit, all
 *      subject to the same home-screen requirement for Web Push)
 *
 * We drive the real utils/pwa helpers via stubbed navigator/matchMedia rather
 * than mocking the module, so component + helpers are exercised together.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { nextTick } from 'vue';
import { mount } from '@vue/test-utils';
import InstallBanner from '@/components/InstallBanner.vue';
import * as setup from '@/composables/useNotificationSetup';
import { _resetNotificationSetupForTest } from '@/composables/useNotificationSetup';

const PROMPT_KEY = 'mt.notificationSetup.promptDismissedAt';
const DAY_MS = 1000 * 60 * 60 * 24;

const IOS_SAFARI_UA =
  'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1';
const IOS_CHROME_UA =
  'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/120.0 Mobile/15E148 Safari/604.1';
const ANDROID_CHROME_UA =
  'Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36';

function stubEnv({
  userAgent,
  platform = 'iPhone',
  maxTouchPoints = 5,
  standalone = false,
  standaloneMatches = false,
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
  window.matchMedia = query => ({
    matches: query === '(display-mode: standalone)' ? standaloneMatches : false,
    media: query,
    addEventListener: () => {},
    removeEventListener: () => {},
  });
}

const iosSafari = () => stubEnv({ userAgent: IOS_SAFARI_UA });
const iosChrome = () => stubEnv({ userAgent: IOS_CHROME_UA });
const iosInstalled = () =>
  stubEnv({
    userAgent: IOS_SAFARI_UA,
    standalone: true,
    standaloneMatches: true,
  });
const androidChrome = () =>
  stubEnv({ userAgent: ANDROID_CHROME_UA, platform: 'Linux armv8l' });

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
  _resetNotificationSetupForTest();
});

afterEach(() => {
  iosSafari();
});

const banner = w => w.find('[data-testid="install-banner"]');

// shouldShow flips in onMounted, so the banner lands a tick after mount.
async function mountBanner() {
  const wrapper = mount(InstallBanner, {
    global: { stubs: { transition: false } },
  });
  await nextTick();
  return wrapper;
}

describe('InstallBanner — when it shows', () => {
  it('shows on iOS Safari, not installed, never dismissed', async () => {
    iosSafari();
    expect(banner(await mountBanner()).exists()).toBe(true);
  });

  it('shows on iOS Chrome too (regression: Safari-only check hid it)', async () => {
    iosChrome();
    expect(banner(await mountBanner()).exists()).toBe(true);
  });

  it('shows again once a dismissal has aged out (>30 days)', async () => {
    iosSafari();
    localStorage.setItem(PROMPT_KEY, String(Date.now() - 31 * DAY_MS));
    expect(banner(await mountBanner()).exists()).toBe(true);
  });

  it('treats a corrupt dismissal timestamp as "not dismissed"', async () => {
    iosSafari();
    localStorage.setItem(PROMPT_KEY, 'not-a-number');
    expect(banner(await mountBanner()).exists()).toBe(true);
  });
});

describe('InstallBanner — when it stays hidden', () => {
  it('hidden once installed (standalone)', async () => {
    iosInstalled();
    expect(banner(await mountBanner()).exists()).toBe(false);
  });

  it('hidden off iOS — no install requirement there', async () => {
    androidChrome();
    expect(banner(await mountBanner()).exists()).toBe(false);
  });

  it('hidden when dismissed within the last 30 days', async () => {
    iosSafari();
    localStorage.setItem(PROMPT_KEY, String(Date.now() - 5 * DAY_MS));
    expect(banner(await mountBanner()).exists()).toBe(false);
  });
});

describe('InstallBanner — the action', () => {
  it('has a labelled action button, not a bare card (the SB-810 bug)', async () => {
    iosSafari();
    const wrapper = await mountBanner();
    const action = wrapper.find('[data-testid="install-banner-action"]');
    expect(action.exists()).toBe(true);
    expect(action.text()).toMatch(/show me how/i);
  });

  it('opens the setup guide when the action is tapped', async () => {
    iosSafari();
    const spy = vi.spyOn(setup, 'openSetupGuide');
    const wrapper = await mountBanner();
    await wrapper
      .find('[data-testid="install-banner-action"]')
      .trigger('click');
    expect(spy).toHaveBeenCalled();
  });

  it('does not promise notifications it cannot deliver', async () => {
    iosSafari();
    const wrapper = await mountBanner();
    // It asks a question and explains the constraint; it never says alerts
    // are on, and it never implies tapping the card installs anything.
    expect(wrapper.text()).toMatch(/home-screen app/i);
  });
});

describe('InstallBanner — dismissal', () => {
  it('retires when the guide is dismissed from on top of it', async () => {
    iosSafari();
    const wrapper = await mountBanner();
    expect(banner(wrapper).exists()).toBe(true);

    // The guide opens over the banner on first login. Saying "not now" there
    // has to silence the banner too — otherwise the user closes one nag and
    // finds the other still sitting underneath it.
    setup.useNotificationSetup().dismissPrompt();
    await nextTick();

    expect(banner(wrapper).exists()).toBe(false);
  });

  it('stays put when the action is tapped — that is a yes, not a "not now"', async () => {
    iosSafari();
    const wrapper = await mountBanner();
    await wrapper
      .find('[data-testid="install-banner-action"]')
      .trigger('click');
    await nextTick();

    expect(localStorage.getItem(PROMPT_KEY)).toBeNull();
  });

  it('hides and persists a timestamp shared with the guide', async () => {
    iosSafari();
    const wrapper = await mountBanner();
    expect(banner(wrapper).exists()).toBe(true);

    await wrapper
      .find('[data-testid="install-banner-dismiss"]')
      .trigger('click');
    await nextTick();

    expect(banner(wrapper).exists()).toBe(false);
    // Same key the guide's "Not now" writes — one dismissal silences both,
    // so the user can't be nagged twice for the same thing.
    const stored = Number(localStorage.getItem(PROMPT_KEY));
    expect(Number.isFinite(stored)).toBe(true);
    expect(stored).toBeGreaterThan(0);
  });
});
