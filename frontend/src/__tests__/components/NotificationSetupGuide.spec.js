/**
 * NotificationSetupGuide.vue tests (SB-810).
 *
 * The guide is the one surface that teaches the whole job: install (iOS only),
 * turn on notifications, follow a team. It has to show the step the user is
 * genuinely on, and — the part that actually caused the support report — it
 * has to give iPhone users instructions precise enough to follow, including
 * the "Add to Home Screen" item that sits below the fold in the share sheet.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { ref, computed, nextTick } from 'vue';
import { mount } from '@vue/test-utils';

const pushState = {
  isEnabled: ref(false),
  isBlocked: ref(false),
  isSupported: ref(true),
};
const followsState = { follows: ref([]), loaded: ref(true) };
const enableMock = vi.fn().mockResolvedValue({ success: true });
const listSubscriptionsMock = vi.fn().mockResolvedValue([]);

vi.mock('@/composables/usePushNotifications', () => ({
  usePushNotifications: () => ({
    isEnabled: computed(() => pushState.isEnabled.value),
    isBlocked: computed(() => pushState.isBlocked.value),
    isSupported: computed(() => pushState.isSupported.value),
    loading: ref(false),
    lastError: ref(null),
    enable: enableMock,
    listSubscriptions: listSubscriptionsMock,
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

const installState = { canInstall: ref(false), prompting: ref(false) };
const promptInstallMock = vi.fn().mockResolvedValue({ outcome: 'accepted' });
vi.mock('@/composables/useInstallPrompt', () => ({
  useInstallPrompt: () => ({
    canInstall: computed(() => installState.canInstall.value),
    prompting: computed(() => installState.prompting.value),
    promptInstall: promptInstallMock,
  }),
}));

const pwa = { ios: false, standalone: false, browser: 'safari' };
vi.mock('@/utils/pwa', async () => {
  const actual = await vi.importActual('@/utils/pwa');
  return {
    ...actual,
    isIos: () => pwa.ios,
    isStandalone: () => pwa.standalone,
    isIosNonStandalone: () => pwa.ios && !pwa.standalone,
    detectBrowser: () => pwa.browser,
    getInstallSteps: () => {
      if (!pwa.ios || pwa.standalone) return null;
      return pwa.browser === 'safari'
        ? {
            browserLabel: 'Safari',
            steps: [
              { title: 'Tap the Share button', detail: 'bottom of the screen' },
              {
                title: 'Scroll down to "Add to Home Screen"',
                detail: 'further down than you expect',
                emphasis: true,
              },
              { title: 'Tap "Add"', detail: 'top right' },
            ],
          }
        : {
            browserLabel: 'Chrome',
            steps: [
              { title: 'Open the Chrome menu', detail: 'the ⋯ button' },
              {
                title: 'Choose Share, then "Add to Home Screen"',
                detail: 'scroll down',
                emphasis: true,
              },
              { title: 'Tap "Add"', detail: 'top right' },
            ],
          };
    },
  };
});

import NotificationSetupGuide from '@/components/notifications/NotificationSetupGuide.vue';
import {
  openSetupGuide,
  _resetNotificationSetupForTest,
} from '@/composables/useNotificationSetup';

const PROMPT_KEY = 'mt.notificationSetup.promptDismissedAt';

beforeEach(() => {
  pushState.isEnabled.value = false;
  pushState.isBlocked.value = false;
  pushState.isSupported.value = true;
  followsState.follows.value = [];
  followsState.loaded.value = true;
  pwa.ios = false;
  pwa.standalone = false;
  pwa.browser = 'safari';
  localStorage.clear();
  installState.canInstall.value = false;
  installState.prompting.value = false;
  promptInstallMock.mockClear();
  enableMock.mockClear();
  listSubscriptionsMock.mockClear();
  _resetNotificationSetupForTest();
});

async function mountGuide({ open = true, reason = 'manual' } = {}) {
  const wrapper = mount(NotificationSetupGuide, {
    global: { stubs: { transition: false } },
  });
  if (open) {
    openSetupGuide(reason);
    await nextTick();
    await nextTick();
  }
  return wrapper;
}

describe('NotificationSetupGuide — visibility', () => {
  it('stays closed until something opens it', async () => {
    const wrapper = await mountGuide({ open: false });
    expect(
      wrapper.find('[data-testid="notification-setup-guide"]').exists()
    ).toBe(false);
  });

  it('opens when the guide is requested', async () => {
    const wrapper = await mountGuide();
    expect(
      wrapper.find('[data-testid="notification-setup-guide"]').exists()
    ).toBe(true);
  });
});

describe('NotificationSetupGuide — install step (iOS)', () => {
  beforeEach(() => {
    pwa.ios = true;
    // iOS hides PushManager outside standalone, so support reads false here.
    pushState.isSupported.value = false;
  });

  it('shows install instructions, not a "browser unsupported" dead end', async () => {
    const wrapper = await mountGuide();
    expect(wrapper.find('[data-testid="setup-detail-install"]').exists()).toBe(
      true
    );
    expect(
      wrapper.find('[data-testid="setup-detail-unsupported"]').exists()
    ).toBe(false);
  });

  it('calls out the below-the-fold share-sheet item users give up on', async () => {
    const wrapper = await mountGuide();
    expect(wrapper.text()).toContain('Add to Home Screen');
    expect(wrapper.find('.is-emphasis').exists()).toBe(true);
  });

  it('names the browser the instructions are for', async () => {
    const wrapper = await mountGuide();
    expect(wrapper.text()).toContain('Safari');
  });

  it('gives Chrome users Chrome instructions', async () => {
    pwa.browser = 'chrome';
    const wrapper = await mountGuide();
    expect(wrapper.text()).toContain('Chrome menu');
  });

  it('explains why install is required at all', async () => {
    const wrapper = await mountGuide();
    expect(wrapper.text()).toMatch(/only allow notifications from apps on/i);
  });
});

describe('NotificationSetupGuide — enable step', () => {
  it('offers a real enable button', async () => {
    const wrapper = await mountGuide();
    expect(wrapper.find('[data-testid="setup-enable-button"]').exists()).toBe(
      true
    );
  });

  it('re-reads backend subscriptions after enabling, not just permission', async () => {
    const wrapper = await mountGuide();
    listSubscriptionsMock.mockClear();
    await wrapper.find('[data-testid="setup-enable-button"]').trigger('click');
    await nextTick();
    // Permission alone lies — SB-52 shipped an "enabled" pill over a backend
    // with no subscription. The server is the authority.
    expect(enableMock).toHaveBeenCalled();
    expect(listSubscriptionsMock).toHaveBeenCalled();
  });

  it('shows the Settings route when permission was denied', async () => {
    pushState.isBlocked.value = true;
    const wrapper = await mountGuide();
    expect(wrapper.find('[data-testid="setup-detail-blocked"]').exists()).toBe(
      true
    );
  });
});

describe('NotificationSetupGuide — follow and done steps', () => {
  it('asks for a follow once push is live but nothing is followed', async () => {
    pushState.isEnabled.value = true;
    const wrapper = await mountGuide();
    expect(wrapper.find('[data-testid="setup-detail-follow"]').exists()).toBe(
      true
    );
  });

  it('confirms completion when everything is in place', async () => {
    pushState.isEnabled.value = true;
    followsState.follows.value = [{ team_id: 19 }];
    const wrapper = await mountGuide();
    expect(wrapper.find('[data-testid="setup-detail-done"]').exists()).toBe(
      true
    );
  });
});

describe('NotificationSetupGuide — checklist', () => {
  it('shows the whole job up front, not one wall at a time', async () => {
    pwa.ios = true;
    const wrapper = await mountGuide();
    expect(wrapper.find('[data-testid="setup-step-install"]').exists()).toBe(
      true
    );
    expect(wrapper.find('[data-testid="setup-step-enable"]').exists()).toBe(
      true
    );
    expect(wrapper.find('[data-testid="setup-step-follow"]').exists()).toBe(
      true
    );
  });

  it('marks finished steps done', async () => {
    pwa.ios = true;
    pwa.standalone = true;
    const wrapper = await mountGuide();
    expect(
      wrapper.find('[data-testid="setup-step-install"]').classes()
    ).toContain('is-done');
    expect(
      wrapper.find('[data-testid="setup-step-enable"]').classes()
    ).not.toContain('is-done');
  });
});

describe('NotificationSetupGuide — dismissal', () => {
  it('records a dismissal when closed unfinished, so it does not re-nag', async () => {
    const wrapper = await mountGuide();
    await wrapper.find('[data-testid="setup-dismiss"]').trigger('click');
    await nextTick();
    expect(localStorage.getItem(PROMPT_KEY)).toBeTruthy();
  });

  it('does not record a dismissal when closed after completing setup', async () => {
    pushState.isEnabled.value = true;
    followsState.follows.value = [{ team_id: 19 }];
    const wrapper = await mountGuide();
    await wrapper.find('[data-testid="setup-dismiss"]').trigger('click');
    await nextTick();
    // Nothing to suppress — they finished, so there is no future nag to mute.
    expect(localStorage.getItem(PROMPT_KEY)).toBeNull();
  });
});

describe('NotificationSetupGuide — native install offer (SB-813)', () => {
  it('is absent when the browser has not offered an install', async () => {
    const wrapper = await mountGuide();
    expect(wrapper.find('[data-testid="setup-native-install"]').exists()).toBe(
      false
    );
  });

  it('offers a one-tap Install when the browser makes it available', async () => {
    installState.canInstall.value = true;
    const wrapper = await mountGuide();
    expect(wrapper.find('[data-testid="setup-native-install"]').exists()).toBe(
      true
    );
  });

  it('fires the native prompt on tap', async () => {
    installState.canInstall.value = true;
    const wrapper = await mountGuide();
    await wrapper
      .find('[data-testid="setup-native-install-button"]')
      .trigger('click');
    expect(promptInstallMock).toHaveBeenCalled();
  });

  it('says plainly that notifications work without it', async () => {
    installState.canInstall.value = true;
    const wrapper = await mountGuide();
    expect(wrapper.text()).toMatch(/notifications work either way/i);
  });

  it('still offers install to a user who is otherwise all set', async () => {
    installState.canInstall.value = true;
    pushState.isEnabled.value = true;
    followsState.follows.value = [{ team_id: 19 }];
    const wrapper = await mountGuide();
    // "You're all set" and "want the icon too?" are not in conflict.
    expect(wrapper.find('[data-testid="setup-detail-done"]').exists()).toBe(
      true
    );
    expect(wrapper.find('[data-testid="setup-native-install"]').exists()).toBe(
      true
    );
  });

  it('marks the optional step Optional in the checklist', async () => {
    installState.canInstall.value = true;
    const wrapper = await mountGuide();
    const step = wrapper.find('[data-testid="setup-step-install"]');
    expect(step.exists()).toBe(true);
    expect(step.text()).toMatch(/optional/i);
  });
});
