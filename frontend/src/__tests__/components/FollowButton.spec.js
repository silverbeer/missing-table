/**
 * FollowButton.vue tests (SB-55).
 *
 * Covers:
 * - Hidden entirely when unauthenticated (v1 decision — no login funnel)
 * - "Follow" label when not following, "Following" when following
 * - Click toggles state optimistically
 * - is-following class applied so the visual state is testable
 * - Disabled while a toggle is in flight (no double-fire)
 * - Mobile tap target — min-height 44px (covered via existing CSS; we just
 *   assert the data-testid exists so the selector is stable for e2e too)
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
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

import FollowButton from '@/components/notifications/FollowButton.vue';
import { _resetTeamFollowsForTest } from '@/composables/useTeamFollows';

beforeEach(() => {
  apiRequestMock.mockReset();
  isAuthenticatedRef.value = true;
  _resetTeamFollowsForTest();
});

const mountButton = (props = {}) =>
  mount(FollowButton, {
    props: { teamId: 42, teamName: 'Test FC', ...props },
  });

describe('FollowButton visibility', () => {
  it('renders nothing when the user is not authenticated', async () => {
    isAuthenticatedRef.value = false;
    apiRequestMock.mockResolvedValue({ follows: [] });

    const wrapper = mountButton();
    await flushPromises();

    expect(wrapper.find('[data-testid="follow-button"]').exists()).toBe(false);
    // No GET fired either (composable bails on unauth).
    expect(apiRequestMock).not.toHaveBeenCalled();
  });

  it('renders the button when the user is authenticated', async () => {
    apiRequestMock.mockResolvedValueOnce({ follows: [] });
    const wrapper = mountButton();
    await flushPromises();

    expect(wrapper.find('[data-testid="follow-button"]').exists()).toBe(true);
  });
});

describe('FollowButton label + state', () => {
  it('shows "Follow" when not currently following the team', async () => {
    apiRequestMock.mockResolvedValueOnce({ follows: [] });
    const wrapper = mountButton({ teamId: 42 });
    await flushPromises();

    const btn = wrapper.find('[data-testid="follow-button"]');
    expect(btn.text()).toContain('Follow');
    expect(btn.classes()).not.toContain('is-following');
    expect(btn.attributes('aria-pressed')).toBe('false');
  });

  it('shows "Following" when the user already follows the team', async () => {
    apiRequestMock.mockResolvedValueOnce({
      follows: [{ team_id: 42, team: { name: 'Test FC' } }],
    });
    const wrapper = mountButton({ teamId: 42 });
    await flushPromises();

    const btn = wrapper.find('[data-testid="follow-button"]');
    expect(btn.text()).toContain('Following');
    expect(btn.classes()).toContain('is-following');
    expect(btn.attributes('aria-pressed')).toBe('true');
  });
});

describe('FollowButton click', () => {
  it('POSTs to /team-follows and flips to Following on success', async () => {
    apiRequestMock.mockResolvedValueOnce({ follows: [] }); // initial GET
    apiRequestMock.mockResolvedValueOnce({ team_id: 42, following: true }); // POST
    apiRequestMock.mockResolvedValueOnce({
      follows: [{ team_id: 42, team: {} }],
    }); // refresh

    const wrapper = mountButton({ teamId: 42 });
    await flushPromises();

    await wrapper.find('[data-testid="follow-button"]').trigger('click');
    await flushPromises();

    expect(apiRequestMock).toHaveBeenNthCalledWith(
      2,
      'http://test.example/api/users/me/team-follows',
      { method: 'POST', body: JSON.stringify({ team_id: 42 }) }
    );
    const btn = wrapper.find('[data-testid="follow-button"]');
    expect(btn.text()).toContain('Following');
    expect(btn.classes()).toContain('is-following');
  });

  it('DELETEs and flips back to Follow when already following', async () => {
    apiRequestMock.mockResolvedValueOnce({
      follows: [{ team_id: 42, team: {} }],
    });
    apiRequestMock.mockResolvedValueOnce(null); // DELETE
    apiRequestMock.mockResolvedValueOnce({ follows: [] }); // refresh

    const wrapper = mountButton({ teamId: 42 });
    await flushPromises();

    await wrapper.find('[data-testid="follow-button"]').trigger('click');
    await flushPromises();

    expect(apiRequestMock).toHaveBeenNthCalledWith(
      2,
      'http://test.example/api/users/me/team-follows/42',
      { method: 'DELETE' }
    );
    const btn = wrapper.find('[data-testid="follow-button"]');
    expect(btn.text()).toContain('Follow');
    expect(btn.classes()).not.toContain('is-following');
  });

  it('reverts to previous state when the toggle request fails', async () => {
    apiRequestMock.mockResolvedValueOnce({ follows: [] });
    apiRequestMock.mockRejectedValueOnce(new Error('network'));

    const wrapper = mountButton({ teamId: 42 });
    await flushPromises();

    await wrapper.find('[data-testid="follow-button"]').trigger('click');
    await flushPromises();

    const btn = wrapper.find('[data-testid="follow-button"]');
    expect(btn.text()).toContain('Follow');
    expect(btn.classes()).not.toContain('is-following');
  });

  it('ignores rapid double-clicks (button disabled while in flight)', async () => {
    apiRequestMock.mockResolvedValueOnce({ follows: [] });
    // POST resolves after a tick so the button is disabled in the window.
    let resolvePost;
    apiRequestMock.mockImplementationOnce(
      () =>
        new Promise(resolve => {
          resolvePost = () => resolve({ team_id: 42, following: true });
        })
    );

    const wrapper = mountButton({ teamId: 42 });
    await flushPromises();

    const btn = wrapper.find('[data-testid="follow-button"]');
    await btn.trigger('click');
    // Second click while busy.
    await btn.trigger('click');

    expect(btn.attributes('disabled')).toBeDefined();
    // Only 2 calls: initial GET + 1 POST (second click was suppressed).
    expect(apiRequestMock).toHaveBeenCalledTimes(2);

    // Drain the in-flight call so subsequent tests don't see a stray promise.
    apiRequestMock.mockResolvedValueOnce({ follows: [] }); // refresh after POST
    resolvePost();
    await flushPromises();
  });
});

describe('FollowButton aria-label', () => {
  it('reads "Follow {teamName}" when not following', async () => {
    apiRequestMock.mockResolvedValueOnce({ follows: [] });
    const wrapper = mountButton({ teamId: 5, teamName: 'IFA' });
    await flushPromises();

    expect(
      wrapper.find('[data-testid="follow-button"]').attributes('aria-label')
    ).toBe('Follow IFA');
  });

  it('reads "Unfollow {teamName}" when already following', async () => {
    apiRequestMock.mockResolvedValueOnce({
      follows: [{ team_id: 5, team: {} }],
    });
    const wrapper = mountButton({ teamId: 5, teamName: 'IFA' });
    await flushPromises();

    expect(
      wrapper.find('[data-testid="follow-button"]').attributes('aria-label')
    ).toBe('Unfollow IFA');
  });
});
