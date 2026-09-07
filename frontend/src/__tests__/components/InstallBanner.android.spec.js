/**
 * InstallBanner — the native (Android / Chromium) path (SB-813).
 *
 * On iPhone the banner can only ever point at Safari's Share control, because
 * Apple ships no install API. On Android the browser hands us a real prompt,
 * so the banner offers a genuine one-tap Install button instead.
 *
 * The pitch differs too, and has to: notifications already work in a tab on
 * Android, so borrowing the iOS line ("we can only alert you if you install")
 * would invent a barrier Google doesn't impose.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { ref, computed, nextTick } from 'vue';
import { mount } from '@vue/test-utils';

const pwa = { ios: false, touch: true };
vi.mock('@/utils/pwa', () => ({
  isIosNonStandalone: () => pwa.ios,
  isTouchDevice: () => pwa.touch,
  isStandalone: () => false,
  isIos: () => pwa.ios,
}));

const installState = { canInstall: ref(false), prompting: ref(false) };
const promptInstallMock = vi.fn().mockResolvedValue({ outcome: 'accepted' });
vi.mock('@/composables/useInstallPrompt', () => ({
  useInstallPrompt: () => ({
    canInstall: computed(() => installState.canInstall.value),
    prompting: computed(() => installState.prompting.value),
    promptInstall: promptInstallMock,
  }),
}));

import InstallBanner from '@/components/InstallBanner.vue';
import { _resetNotificationSetupForTest } from '@/composables/useNotificationSetup';

beforeEach(() => {
  pwa.ios = false;
  pwa.touch = true;
  installState.canInstall.value = false;
  installState.prompting.value = false;
  promptInstallMock.mockClear();
  localStorage.clear();
  _resetNotificationSetupForTest();
});

async function mountBanner() {
  const wrapper = mount(InstallBanner, {
    global: { stubs: { transition: false } },
  });
  await nextTick();
  return wrapper;
}

const banner = w => w.find('[data-testid="install-banner"]');

describe('InstallBanner — native install path', () => {
  it('stays hidden when the browser has not offered an install', async () => {
    expect(banner(await mountBanner()).exists()).toBe(false);
  });

  it('appears on Android once the browser offers an install', async () => {
    installState.canInstall.value = true;
    const wrapper = await mountBanner();
    expect(banner(wrapper).exists()).toBe(true);
    expect(banner(wrapper).attributes('data-mode')).toBe('native');
  });

  it('offers a real Install button, not instructions', async () => {
    installState.canInstall.value = true;
    const wrapper = await mountBanner();
    expect(
      wrapper.find('[data-testid="install-banner-install"]').exists()
    ).toBe(true);
    expect(wrapper.find('[data-testid="install-banner-action"]').exists()).toBe(
      false
    );
  });

  it('fires the native prompt when Install is tapped', async () => {
    installState.canInstall.value = true;
    const wrapper = await mountBanner();
    await wrapper
      .find('[data-testid="install-banner-install"]')
      .trigger('click');
    expect(promptInstallMock).toHaveBeenCalled();
  });

  it('does not claim notifications require installing — they do not on Android', async () => {
    installState.canInstall.value = true;
    const wrapper = await mountBanner();
    expect(wrapper.text()).not.toMatch(/can only send them/i);
    expect(wrapper.text()).toMatch(/home screen/i);
  });

  it('stays off laptops — a fixed bottom banner there is just noise', async () => {
    installState.canInstall.value = true;
    pwa.touch = false;
    expect(banner(await mountBanner()).exists()).toBe(false);
  });

  it('retires once the install offer is withdrawn (app installed)', async () => {
    installState.canInstall.value = true;
    const wrapper = await mountBanner();
    expect(banner(wrapper).exists()).toBe(true);

    installState.canInstall.value = false;
    await nextTick();

    expect(banner(wrapper).exists()).toBe(false);
  });

  it('honours the shared dismissal record', async () => {
    installState.canInstall.value = true;
    localStorage.setItem(
      'mt.notificationSetup.promptDismissedAt',
      String(Date.now())
    );
    expect(banner(await mountBanner()).exists()).toBe(false);
  });
});

describe('InstallBanner — iOS still gets instructions', () => {
  it('routes to the guide, since no install API exists there', async () => {
    pwa.ios = true;
    const wrapper = await mountBanner();
    expect(banner(wrapper).attributes('data-mode')).toBe('ios');
    expect(wrapper.find('[data-testid="install-banner-action"]').exists()).toBe(
      true
    );
    expect(
      wrapper.find('[data-testid="install-banner-install"]').exists()
    ).toBe(false);
  });

  it('prefers instructions over a native prompt if somehow both apply', async () => {
    pwa.ios = true;
    installState.canInstall.value = true;
    const wrapper = await mountBanner();
    expect(banner(wrapper).attributes('data-mode')).toBe('ios');
  });
});
