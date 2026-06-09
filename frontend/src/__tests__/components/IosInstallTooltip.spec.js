/**
 * IosInstallTooltip.vue tests (SB-121).
 *
 * The tooltip nudges iOS Safari users to "Add to Home Screen" (Apple gives
 * PWAs no automatic install prompt). It must appear ONLY for iOS Safari users
 * who haven't installed yet and haven't recently dismissed it.
 *
 * We drive the real utils/pwa helpers via stubbed navigator/matchMedia (those
 * helpers have their own unit tests in utils/pwa.spec.js) rather than mocking
 * the module — this exercises the component + helpers together.
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { nextTick } from 'vue';
import { mount } from '@vue/test-utils';
import IosInstallTooltip from '@/components/IosInstallTooltip.vue';

const STORAGE_KEY = 'mt.iosInstallTooltip.dismissedAt';
const DAY_MS = 1000 * 60 * 60 * 24;

const IOS_SAFARI_UA =
  'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1';
const ANDROID_CHROME_UA =
  'Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36';

function stubEnv({
  userAgent,
  platform,
  maxTouchPoints,
  standalone,
  standaloneMatches,
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

const iosSafariNotInstalled = () =>
  stubEnv({
    userAgent: IOS_SAFARI_UA,
    platform: 'iPhone',
    maxTouchPoints: 5,
    standalone: false,
    standaloneMatches: false,
  });
const iosSafariInstalled = () =>
  stubEnv({
    userAgent: IOS_SAFARI_UA,
    platform: 'iPhone',
    maxTouchPoints: 5,
    standalone: true,
    standaloneMatches: true,
  });
const androidChrome = () =>
  stubEnv({
    userAgent: ANDROID_CHROME_UA,
    platform: 'Linux armv8l',
    maxTouchPoints: 5,
    standalone: false,
    standaloneMatches: false,
  });

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  iosSafariNotInstalled(); // benign reset
});

const banner = wrapper => wrapper.find('.ios-install-banner');

// shouldShow is flipped in onMounted, so the banner appears on the tick after
// mount — await nextTick before asserting visibility.
async function mountTip() {
  const wrapper = mount(IosInstallTooltip, {
    global: { stubs: { transition: false } },
  });
  await nextTick();
  return wrapper;
}

describe('IosInstallTooltip — when it shows', () => {
  it('shows for iOS Safari, not installed, never dismissed', async () => {
    iosSafariNotInstalled();
    const wrapper = await mountTip();
    expect(banner(wrapper).exists()).toBe(true);
    expect(wrapper.text()).toContain('Add to Home Screen');
  });

  it('shows again once an old dismissal has aged out (>30 days)', async () => {
    iosSafariNotInstalled();
    localStorage.setItem(STORAGE_KEY, String(Date.now() - 31 * DAY_MS));
    const wrapper = await mountTip();
    expect(banner(wrapper).exists()).toBe(true);
  });

  it('treats a corrupt dismissal timestamp as "not dismissed"', async () => {
    iosSafariNotInstalled();
    localStorage.setItem(STORAGE_KEY, 'not-a-number');
    const wrapper = await mountTip();
    expect(banner(wrapper).exists()).toBe(true);
  });
});

describe('IosInstallTooltip — when it stays hidden', () => {
  it('hidden when already installed (standalone)', async () => {
    iosSafariInstalled();
    const wrapper = await mountTip();
    expect(banner(wrapper).exists()).toBe(false);
  });

  it('hidden on non-iOS-Safari (Android)', async () => {
    androidChrome();
    const wrapper = await mountTip();
    expect(banner(wrapper).exists()).toBe(false);
  });

  it('hidden when dismissed within the last 30 days', async () => {
    iosSafariNotInstalled();
    localStorage.setItem(STORAGE_KEY, String(Date.now() - 5 * DAY_MS));
    const wrapper = await mountTip();
    expect(banner(wrapper).exists()).toBe(false);
  });
});

describe('IosInstallTooltip — dismissal', () => {
  it('hides and persists a timestamp when the close button is clicked', async () => {
    iosSafariNotInstalled();
    const wrapper = await mountTip();
    expect(banner(wrapper).exists()).toBe(true);

    await wrapper.find('.ios-install-close').trigger('click');
    await wrapper.vm.$nextTick();

    expect(banner(wrapper).exists()).toBe(false);
    const stored = Number(localStorage.getItem(STORAGE_KEY));
    expect(Number.isFinite(stored)).toBe(true);
    expect(stored).toBeGreaterThan(0);
  });
});
