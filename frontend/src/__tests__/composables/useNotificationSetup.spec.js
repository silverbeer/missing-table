/**
 * useNotificationSetup tests (SB-810).
 *
 * This composable is the single answer to "what does this user still have to
 * do before a match notification can reach them". Before it existed the three
 * prerequisites lived in three unconnected places, which is how a user could
 * tap Follow, see it go green, and never learn that two more steps stood
 * between them and an alert.
 *
 * The states are derived from live sources every time — never from a stored
 * "onboarding done" flag — because a user who revokes permission or deletes
 * the home-screen icon really is back at an earlier step.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { ref, computed } from 'vue';

const pushState = {
  isEnabled: ref(false),
  isBlocked: ref(false),
  isSupported: ref(true),
};
const followsState = {
  follows: ref([]),
  loaded: ref(true),
};

vi.mock('@/composables/usePushNotifications', () => ({
  usePushNotifications: () => ({
    isEnabled: computed(() => pushState.isEnabled.value),
    isBlocked: computed(() => pushState.isBlocked.value),
    isSupported: computed(() => pushState.isSupported.value),
  }),
}));

vi.mock('@/composables/useTeamFollows', () => ({
  useTeamFollows: () => ({
    follows: computed(() => followsState.follows.value),
    followedTeamIds: computed(
      () => new Set(followsState.follows.value.map(f => f.team_id))
    ),
    loaded: computed(() => followsState.loaded.value),
    ensureLoaded: vi.fn().mockResolvedValue(undefined),
  }),
}));

const installState = { canInstall: ref(false) };
vi.mock('@/composables/useInstallPrompt', () => ({
  useInstallPrompt: () => ({
    canInstall: computed(() => installState.canInstall.value),
    prompting: computed(() => false),
    promptInstall: vi.fn(),
  }),
}));

const pwa = { ios: false, standalone: false };
vi.mock('@/utils/pwa', () => ({
  isIos: () => pwa.ios,
  isStandalone: () => pwa.standalone,
  isIosNonStandalone: () => pwa.ios && !pwa.standalone,
}));

import {
  useNotificationSetup,
  wasPromptDismissed,
  _resetNotificationSetupForTest,
} from '@/composables/useNotificationSetup';

const PROMPT_KEY = 'mt.notificationSetup.promptDismissedAt';
const DAY_MS = 1000 * 60 * 60 * 24;

/** Desktop, push supported, nothing enabled, no follows. */
function reset() {
  pushState.isEnabled.value = false;
  pushState.isBlocked.value = false;
  pushState.isSupported.value = true;
  followsState.follows.value = [];
  followsState.loaded.value = true;
  pwa.ios = false;
  pwa.standalone = false;
  installState.canInstall.value = false;
  localStorage.clear();
  _resetNotificationSetupForTest();
}

beforeEach(reset);

describe('currentStep — the wall the user is actually standing at', () => {
  it('install, for an iPhone browsing in a tab', () => {
    pwa.ios = true;
    // iOS hides PushManager outside standalone mode, so support looks false.
    pushState.isSupported.value = false;
    expect(useNotificationSetup().currentStep.value).toBe('install');
  });

  it('does NOT report "unsupported" for an iPhone tab', () => {
    pwa.ios = true;
    pushState.isSupported.value = false;
    // The honest answer is "install it first". Calling it unsupported is a
    // dead end that tells the user to give up when they're two taps away.
    expect(useNotificationSetup().isUnsupported.value).toBe(false);
  });

  it('enable, once installed on iOS', () => {
    pwa.ios = true;
    pwa.standalone = true;
    expect(useNotificationSetup().currentStep.value).toBe('enable');
  });

  it('enable, on desktop where no install is needed', () => {
    expect(useNotificationSetup().currentStep.value).toBe('enable');
  });

  it('blocked, when the user denied permission', () => {
    pushState.isBlocked.value = true;
    expect(useNotificationSetup().currentStep.value).toBe('blocked');
  });

  it('follow, when push works but nothing is followed', () => {
    pushState.isEnabled.value = true;
    expect(useNotificationSetup().currentStep.value).toBe('follow');
  });

  it('done, when push works and a team is followed', () => {
    pushState.isEnabled.value = true;
    followsState.follows.value = [{ team_id: 19 }];
    const s = useNotificationSetup();
    expect(s.currentStep.value).toBe('done');
    expect(s.isComplete.value).toBe(true);
  });

  it('unsupported, on a desktop browser without Web Push', () => {
    pushState.isSupported.value = false;
    expect(useNotificationSetup().currentStep.value).toBe('unsupported');
  });

  it('falls back to an earlier step when permission is later revoked', () => {
    pushState.isEnabled.value = true;
    followsState.follows.value = [{ team_id: 19 }];
    const s = useNotificationSetup();
    expect(s.isComplete.value).toBe(true);

    // User turns notifications off in system settings.
    pushState.isEnabled.value = false;
    expect(s.currentStep.value).toBe('enable');
    expect(s.isComplete.value).toBe(false);
  });
});

describe('steps checklist', () => {
  it('includes the install step only on iOS', () => {
    pwa.ios = true;
    const keys = useNotificationSetup().steps.value.map(s => s.key);
    expect(keys).toEqual(['install', 'enable', 'follow']);
  });

  it('omits install off iOS, where push works in a normal tab', () => {
    const keys = useNotificationSetup().steps.value.map(s => s.key);
    expect(keys).toEqual(['enable', 'follow']);
  });

  it('ticks completed steps so progress is visible', () => {
    pwa.ios = true;
    pwa.standalone = true;
    pushState.isEnabled.value = true;
    const steps = useNotificationSetup().steps.value;
    expect(steps.find(s => s.key === 'install').done).toBe(true);
    expect(steps.find(s => s.key === 'enable').done).toBe(true);
    expect(steps.find(s => s.key === 'follow').done).toBe(false);
  });
});

describe('shouldPromptUnprompted — when we volunteer the guide', () => {
  it('true for a brand new user with work to do', () => {
    pwa.ios = true;
    expect(useNotificationSetup().shouldPromptUnprompted.value).toBe(true);
  });

  it('false when the user is already fully set up', () => {
    pushState.isEnabled.value = true;
    followsState.follows.value = [{ team_id: 19 }];
    expect(useNotificationSetup().shouldPromptUnprompted.value).toBe(false);
  });

  it('false before follows have loaded — an unloaded list looks empty', () => {
    pushState.isEnabled.value = true;
    followsState.loaded.value = false;
    // Prompting here would nag someone who is already following teams.
    expect(useNotificationSetup().shouldPromptUnprompted.value).toBe(false);
  });

  it('false when push is genuinely unsupported — nothing to offer', () => {
    pushState.isSupported.value = false;
    expect(useNotificationSetup().shouldPromptUnprompted.value).toBe(false);
  });

  it('false for 30 days after a "not now"', () => {
    pwa.ios = true;
    localStorage.setItem(PROMPT_KEY, String(Date.now() - 5 * DAY_MS));
    expect(useNotificationSetup().shouldPromptUnprompted.value).toBe(false);
  });

  it('true again once the dismissal has aged out', () => {
    pwa.ios = true;
    localStorage.setItem(PROMPT_KEY, String(Date.now() - 31 * DAY_MS));
    expect(useNotificationSetup().shouldPromptUnprompted.value).toBe(true);
  });
});

describe('dismissPrompt', () => {
  it('closes the guide and records the dismissal', () => {
    pwa.ios = true;
    const s = useNotificationSetup();
    s.open('first-login');
    expect(s.guideOpen.value).toBe(true);

    s.dismissPrompt();

    expect(s.guideOpen.value).toBe(false);
    expect(wasPromptDismissed()).toBe(true);
  });

  it('survives localStorage being unavailable (private mode)', () => {
    const original = Storage.prototype.setItem;
    Storage.prototype.setItem = () => {
      throw new Error('QuotaExceededError');
    };
    const s = useNotificationSetup();
    s.open();
    expect(() => s.dismissPrompt()).not.toThrow();
    expect(s.guideOpen.value).toBe(false);
    Storage.prototype.setItem = original;
  });
});

describe('optional install step (SB-813)', () => {
  it('offers install on Android when the browser makes it available', () => {
    installState.canInstall.value = true;
    const steps = useNotificationSetup().steps.value;
    const install = steps.find(s => s.key === 'install');
    expect(install).toBeDefined();
    expect(install.required).toBe(false);
    expect(install.label).toMatch(/optional/i);
  });

  it('omits it entirely when the browser has not offered one', () => {
    const keys = useNotificationSetup().steps.value.map(s => s.key);
    expect(keys).not.toContain('install');
  });

  it('never blocks completion — push works in a tab on Android', () => {
    installState.canInstall.value = true;
    pushState.isEnabled.value = true;
    followsState.follows.value = [{ team_id: 19 }];
    const s = useNotificationSetup();
    // Uninstalled, but fully set up for notifications. Saying otherwise would
    // invent a barrier Google doesn't impose.
    expect(s.currentStep.value).toBe('done');
    expect(s.isComplete.value).toBe(true);
  });

  it('never becomes the current step outside iOS', () => {
    installState.canInstall.value = true;
    expect(useNotificationSetup().currentStep.value).toBe('enable');
  });

  it('keeps install REQUIRED on iOS, where it really is', () => {
    pwa.ios = true;
    const install = useNotificationSetup().steps.value.find(
      s => s.key === 'install'
    );
    expect(install.required).toBe(true);
  });
});
