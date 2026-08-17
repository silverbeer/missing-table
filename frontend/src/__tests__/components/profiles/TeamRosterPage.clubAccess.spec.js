/**
 * TeamRosterPage — club-scoped access (SB-668).
 *
 * The backend already allows any team inside your own club. The page did not:
 * it resolved a target team from the profile's team_id only, so a club manager
 * or club fan — who carry club_id and no team_id — hit "You are not assigned to
 * a team" on the very page the role gate was widened to admit them to.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import TeamRosterPage from '@/components/profiles/TeamRosterPage.vue';

const CLUB_TEAMS = [
  { id: 11, name: 'IFA U15 HG' },
  { id: 12, name: 'IFA U16 HG' },
];

const TEAM_PAYLOAD = {
  success: true,
  team: { id: 11, name: 'IFA U15 HG', club: { id: 3, name: 'IFA' } },
  players: [],
};

const apiRequest = vi.fn();
const profile = { team_id: null, club_id: 3 };

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    apiRequest,
    state: { profile },
  }),
}));

vi.mock('@/config/api', () => ({ getApiBaseUrl: () => 'http://test' }));

vi.mock('@/components/profiles/PlayerCard.vue', () => ({
  default: { template: '<div />' },
}));
vi.mock('@/components/profiles/GoldenBoot.vue', () => ({
  default: { name: 'GoldenBoot', props: ['teamId'], template: '<div />' },
}));
vi.mock('@/components/notifications/FollowButton.vue', () => ({
  default: { template: '<div />' },
}));

beforeEach(() => {
  apiRequest.mockReset();
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve(TEAM_PAYLOAD),
  });
  apiRequest.mockImplementation(url => {
    if (url.includes('/teams/current')) {
      return Promise.resolve({ success: true, teams: [] });
    }
    if (url.includes('/api/clubs/')) return Promise.resolve(CLUB_TEAMS);
    return Promise.resolve([]);
  });
});

describe('TeamRosterPage club access (SB-668)', () => {
  it('resolves a team from the club when the profile has no team', async () => {
    profile.team_id = null;
    profile.club_id = 3;

    const wrapper = mount(TeamRosterPage);
    await flushPromises();

    // Asked the club for its teams, then loaded the first one.
    const clubCall = apiRequest.mock.calls.find(c =>
      c[0].includes('/api/clubs/3/teams')
    );
    expect(clubCall).toBeDefined();
    expect(global.fetch.mock.calls[0][0]).toContain('/api/teams/11/players');
    expect(wrapper.text()).not.toContain('not assigned');
  });

  it('passes the resolved team to the Golden Boot board', async () => {
    profile.team_id = null;
    profile.club_id = 3;

    const wrapper = mount(TeamRosterPage);
    await flushPromises();

    const board = wrapper.findComponent({ name: 'GoldenBoot' });
    expect(board.exists()).toBe(true);
    expect(board.props('teamId')).toBe(11);
  });

  it('still prefers the profile team when there is one', async () => {
    profile.team_id = 99;
    profile.club_id = 3;

    mount(TeamRosterPage);
    await flushPromises();

    // Straight to their own squad — the club is not consulted to choose one.
    // (The club endpoint is still called afterwards to fill the team dropdown,
    // which is why this asserts on the roster request rather than on it.)
    expect(global.fetch.mock.calls[0][0]).toContain('/api/teams/99/players');
    expect(global.fetch.mock.calls[0][0]).not.toContain('/api/teams/11/');
  });

  it('explains when the user has neither a team nor a club', async () => {
    profile.team_id = null;
    profile.club_id = null;

    const wrapper = mount(TeamRosterPage);
    await flushPromises();

    expect(wrapper.text()).toContain('not assigned to a team or club');
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('describes a 403 as a club boundary, not a team one', async () => {
    profile.team_id = 99;
    profile.club_id = 3;
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 403 });

    const wrapper = mount(TeamRosterPage);
    await flushPromises();

    // The server permits any team in your own club, so 403 means another club.
    expect(wrapper.text()).toContain('teams in your own club');
  });
});
