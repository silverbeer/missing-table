/**
 * useInstallPrompt tests (SB-813).
 *
 * The mirror image of the iOS problem. On iPhone there is no install API at
 * all and we hand-write instructions (SB-810); on Android and desktop Chromium
 * hands us a real one-tap prompt, and MT simply never used it — a repo-wide
 * grep for `beforeinstallprompt` returned nothing.
 *
 * The API has two sharp edges this composable exists to handle:
 *   - prompt() must be called from a user gesture, so the event is stashed
 *   - each captured event is single-use and must not be replayed
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';

const pwa = { standalone: false };
vi.mock('@/utils/pwa', () => ({
  isStandalone: () => pwa.standalone,
}));

import {
  useInstallPrompt,
  _resetInstallPromptForTest,
  _setDeferredPromptForTest,
} from '@/composables/useInstallPrompt';

/** Minimal stand-in for a BeforeInstallPromptEvent. */
function fakeEvent(outcome = 'accepted') {
  return {
    preventDefault: vi.fn(),
    prompt: vi.fn(),
    userChoice: Promise.resolve({ outcome }),
  };
}

function fireBeforeInstallPrompt(event) {
  const e = new Event('beforeinstallprompt');
  Object.assign(e, event);
  e.preventDefault = event.preventDefault;
  window.dispatchEvent(e);
  return e;
}

beforeEach(() => {
  pwa.standalone = false;
  _resetInstallPromptForTest();
});

describe('capturing the event', () => {
  it('offers install once the browser says the site is installable', () => {
    expect(useInstallPrompt().canInstall.value).toBe(false);
    fireBeforeInstallPrompt(fakeEvent());
    expect(useInstallPrompt().canInstall.value).toBe(true);
  });

  it('suppresses Chrome’s own mini-infobar so we control placement', () => {
    const event = fakeEvent();
    fireBeforeInstallPrompt(event);
    expect(event.preventDefault).toHaveBeenCalled();
  });

  it('offers nothing when already running as an installed app', () => {
    fireBeforeInstallPrompt(fakeEvent());
    pwa.standalone = true;
    expect(useInstallPrompt().canInstall.value).toBe(false);
  });

  it('stops offering after the app is installed', () => {
    fireBeforeInstallPrompt(fakeEvent());
    window.dispatchEvent(new Event('appinstalled'));
    expect(useInstallPrompt().canInstall.value).toBe(false);
  });
});

describe('promptInstall', () => {
  it('fires the native dialog and reports acceptance', async () => {
    const event = fakeEvent('accepted');
    _setDeferredPromptForTest(event);

    const result = await useInstallPrompt().promptInstall();

    expect(event.prompt).toHaveBeenCalled();
    expect(result.outcome).toBe('accepted');
  });

  it('reports a dismissal without treating it as an error', async () => {
    _setDeferredPromptForTest(fakeEvent('dismissed'));
    const result = await useInstallPrompt().promptInstall();
    expect(result.outcome).toBe('dismissed');
  });

  it('never replays a spent event — the API allows exactly one use', async () => {
    const event = fakeEvent('dismissed');
    _setDeferredPromptForTest(event);

    await useInstallPrompt().promptInstall();
    const second = await useInstallPrompt().promptInstall();

    expect(event.prompt).toHaveBeenCalledTimes(1);
    expect(second.outcome).toBe('unavailable');
  });

  it('withdraws the offer as soon as it is used', async () => {
    _setDeferredPromptForTest(fakeEvent('accepted'));
    const install = useInstallPrompt();
    await install.promptInstall();
    expect(install.canInstall.value).toBe(false);
  });

  it('returns "unavailable" when nothing was ever captured', async () => {
    const result = await useInstallPrompt().promptInstall();
    expect(result.outcome).toBe('unavailable');
  });

  it('survives a browser that throws on a stale event', async () => {
    _setDeferredPromptForTest({
      prompt: () => {
        throw new Error('The prompt() method may only be called once.');
      },
      userChoice: Promise.resolve({ outcome: 'accepted' }),
    });
    const result = await useInstallPrompt().promptInstall();
    expect(result.outcome).toBe('unavailable');
  });
});
