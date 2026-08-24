/**
 * FollowButton — notification honesty (SB-810).
 *
 * Following a team writes a follow record. It does NOT turn on push, and
 * before this change nothing said so: a user tapped Follow, saw it go green,
 * and waited for alerts that were never coming. That is the failure a real
 * user hit and reported.
 *
 * So the button has two new jobs:
 *   - never let "Following" imply alerts are live when they aren't
 *   - on the user's FIRST follow, point at what's still missing while the
 *     intent is fresh — and only then, because a modal on every follow is
 *     nagging rather than teaching
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ref, computed } from 'vue';
import { mount, flushPromises } from '@vue/test-utils';

const isAuthenticatedRef = { value: true };
const apiRequestMock = vi.fn();

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    isAuthenticated: isAuthenticatedRef,
    apiRequest: apiRequestMock,
  }),
}));

vi.mock('@/config/api', () => ({
  getApiBaseUrl: () => 'http://test.example',
}));

// Push state is driven per-test; the real composable would hit the browser.
const pushState = {
  isEnabled: ref(false),
  isBlocked: ref(false),
  isSupported: ref(true),
};
vi.mock('@/composables/usePushNotifications', () => ({
  usePushNotifications: () => ({
    isEnabled: computed(() => pushState.isEnabled.value),
    isBlocked: computed(() => pushState.isBlocked.value),
    isSupported: computed(() => pushState.isSupported.value),
  }),
}));

const pwa = { ios: false, standalone: false };
vi.mock('@/utils/pwa', () => ({
  isIos: () => pwa.ios,
  isStandalone: () => pwa.standalone,
  isIosNonStandalone: () => pwa.ios && !pwa.standalone,
}));

import FollowButton from '@/components/notifications/FollowButton.vue';
import { _resetTeamFollowsForTest } from '@/composables/useTeamFollows';
import {
  useNotificationSetup,
  _resetNotificationSetupForTest,
} from '@/composables/useNotificationSetup';

beforeEach(() => {
  apiRequestMock.mockReset();
  isAuthenticatedRef.value = true;
  pushState.isEnabled.value = false;
  pushState.isBlocked.value = false;
  pushState.isSupported.value = true;
  pwa.ios = false;
  pwa.standalone = false;
  localStorage.clear();
  _resetTeamFollowsForTest();
  _resetNotificationSetupForTest();
});

const mountButton = (props = {}) =>
  mount(FollowButton, {
    props: { teamId: 42, teamName: 'IFA U15', ...props },
  });

const hint = w => w.find('[data-testid="follow-alerts-hint"]');

describe('FollowButton — the alerts hint', () => {
  it('shows no hint when the user is not following the team', async () => {
    apiRequestMock.mockResolvedValueOnce({ follows: [] });
    const wrapper = mountButton();
    await flushPromises();

    expect(hint(wrapper).exists()).toBe(false);
  });

  it('warns that alerts are off once following but not set up', async () => {
    apiRequestMock.mockResolvedValueOnce({ follows: [{ team_id: 42 }] });
    const wrapper = mountButton();
    await flushPromises();

    expect(hint(wrapper).exists()).toBe(true);
    expect(hint(wrapper).text()).toMatch(/aren.t on yet/i);
  });

  it('drops the hint once notifications can actually arrive', async () => {
    pushState.isEnabled.value = true;
    apiRequestMock.mockResolvedValueOnce({ follows: [{ team_id: 42 }] });
    const wrapper = mountButton();
    await flushPromises();

    expect(hint(wrapper).exists()).toBe(false);
  });

  it('opens the setup guide when the hint is tapped', async () => {
    apiRequestMock.mockResolvedValueOnce({ follows: [{ team_id: 42 }] });
    const wrapper = mountButton();
    await flushPromises();

    await hint(wrapper).trigger('click');
    expect(useNotificationSetup().guideOpen.value).toBe(true);
  });
});

describe('FollowButton — first-follow prompt', () => {
  it('opens the guide on the first ever follow when alerts cannot arrive', async () => {
    apiRequestMock.mockResolvedValueOnce({ follows: [] }); // initial load
    const wrapper = mountButton();
    await flushPromises();

    apiRequestMock.mockResolvedValueOnce({}); // POST
    apiRequestMock.mockResolvedValueOnce({ follows: [{ team_id: 42 }] });
    await wrapper.find('[data-testid="follow-button"]').trigger('click');
    await flushPromises();

    expect(useNotificationSetup().guideOpen.value).toBe(true);
  });

  it('stays quiet when the user is already fully set up', async () => {
    pushState.isEnabled.value = true;
    apiRequestMock.mockResolvedValueOnce({ follows: [] });
    const wrapper = mountButton();
    await flushPromises();

    apiRequestMock.mockResolvedValueOnce({});
    apiRequestMock.mockResolvedValueOnce({ follows: [{ team_id: 42 }] });
    await wrapper.find('[data-testid="follow-button"]').trigger('click');
    await flushPromises();

    expect(useNotificationSetup().guideOpen.value).toBe(false);
  });

  it('does not re-open on a second follow — that would be nagging', async () => {
    apiRequestMock.mockResolvedValueOnce({ follows: [{ team_id: 7 }] });
    const wrapper = mountButton({ teamId: 42 });
    await flushPromises();

    apiRequestMock.mockResolvedValueOnce({});
    apiRequestMock.mockResolvedValueOnce({
      follows: [{ team_id: 7 }, { team_id: 42 }],
    });
    await wrapper.find('[data-testid="follow-button"]').trigger('click');
    await flushPromises();

    expect(useNotificationSetup().guideOpen.value).toBe(false);
  });

  it('does not open on unfollow', async () => {
    apiRequestMock.mockResolvedValueOnce({ follows: [{ team_id: 42 }] });
    const wrapper = mountButton();
    await flushPromises();

    apiRequestMock.mockResolvedValueOnce({});
    apiRequestMock.mockResolvedValueOnce({ follows: [] });
    await wrapper.find('[data-testid="follow-button"]').trigger('click');
    await flushPromises();

    expect(useNotificationSetup().guideOpen.value).toBe(false);
  });

  it('stays quiet if the user recently dismissed the guide', async () => {
    localStorage.setItem(
      'mt.notificationSetup.promptDismissedAt',
      String(Date.now())
    );
    apiRequestMock.mockResolvedValueOnce({ follows: [] });
    const wrapper = mountButton();
    await flushPromises();

    apiRequestMock.mockResolvedValueOnce({});
    apiRequestMock.mockResolvedValueOnce({ follows: [{ team_id: 42 }] });
    await wrapper.find('[data-testid="follow-button"]').trigger('click');
    await flushPromises();

    expect(useNotificationSetup().guideOpen.value).toBe(false);
  });

  it('does not open when the follow request failed', async () => {
    apiRequestMock.mockResolvedValueOnce({ follows: [] });
    const wrapper = mountButton();
    await flushPromises();

    apiRequestMock.mockRejectedValueOnce(new Error('offline'));
    await wrapper.find('[data-testid="follow-button"]').trigger('click');
    await flushPromises();

    expect(useNotificationSetup().guideOpen.value).toBe(false);
  });
});
