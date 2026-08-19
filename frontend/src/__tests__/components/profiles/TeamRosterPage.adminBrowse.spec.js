/**
 * TeamRosterPage — admin team browsing (SB-792).
 *
 * An admin has no team_id and no club_id by design, so every fallback in
 * fetchTeamPlayers comes up empty and the page had nothing to show. The role
 * meant to see everything ended up with less reach than a fan: "No Team
 * Assigned", no way forward, no Golden Boot board.
 *
 * They now get the full team list to choose from — and a prompt rather than a
 * default, because auto-loading the first of 183 teams and calling it "My
 * Club" would present a guess as an answer.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import TeamRosterPage from '@/components/profiles/TeamRosterPage.vue';

const ALL_TEAMS = [
  {
    id: 30,
    name: 'New York City FC',
    club: { id: 154, name: 'New York City FC' },
  },
  {
    id: 19,
    name: 'IFA',
    club: { id: 1, name: 'IFA' },
    age_group: { name: 'U15' },
  },
];

const TEAM_PAYLOAD = {
  success: true,
  team: { id: 19, name: 'IFA', club: { id: 1, name: 'IFA' } },
  players: [],
};

const apiRequest = vi.fn();
const profile = { role: 'admin', team_id: null, club_id: null };

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({ apiRequest, state: { profile } }),
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
  profile.role = 'admin';
  profile.team_id = null;
  profile.club_id = null;

  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve(TEAM_PAYLOAD),
  });

  apiRequest.mockImplementation(url => {
    if (url.includes('/teams/current')) {
      return Promise.resolve({ success: true, teams: [] });
    }
    if (url.includes('/api/teams')) return Promise.resolve(ALL_TEAMS);
    return Promise.resolve([]);
  });
});

describe('TeamRosterPage admin browsing (SB-792)', () => {
  it('offers a team picker to an admin with no team or club', async () => {
    const wrapper = mount(TeamRosterPage);
    await flushPromises();

    expect(wrapper.find('[data-testid="admin-team-select"]').exists()).toBe(
      true
    );
  });

  it('prompts for a choice instead of loading an arbitrary team', async () => {
    const wrapper = mount(TeamRosterPage);
    await flushPromises();

    expect(wrapper.find('[data-testid="admin-choose-team"]').exists()).toBe(
      true
    );
    // No roster request at all — nothing has been chosen yet.
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('does not show the "not assigned" error to an admin', async () => {
    // The whole point: the previous behaviour painted an error over a page
    // that was working exactly as intended.
    const wrapper = mount(TeamRosterPage);
    await flushPromises();

    expect(wrapper.text()).not.toContain('not assigned');
  });

  it('loads the chosen team and its Golden Boot board', async () => {
    const wrapper = mount(TeamRosterPage);
    await flushPromises();

    const ifaOption = wrapper
      .find('[data-testid="admin-team-select"]')
      .findAll('option')
      .find(o => o.text().includes('IFA'));
    await ifaOption.setSelected();
    await flushPromises();

    expect(global.fetch.mock.calls[0][0]).toContain('/api/teams/19/players');

    const board = wrapper.findComponent({ name: 'GoldenBoot' });
    expect(board.exists()).toBe(true);
    expect(board.props('teamId')).toBe(19);
  });

  it('sorts the picker by club then team', async () => {
    const wrapper = mount(TeamRosterPage);
    await flushPromises();

    const labels = wrapper
      .find('[data-testid="admin-team-select"]')
      .findAll('option')
      .map(o => o.text())
      .filter(t => !t.includes('Choose a team'));

    expect(labels[0]).toContain('IFA');
    expect(labels[1]).toContain('New York City FC');
  });

  it('leaves non-admins on their existing resolution path', async () => {
    // A team-fan with a squad must not get the admin browser.
    profile.role = 'team-fan';
    profile.team_id = 19;

    const wrapper = mount(TeamRosterPage);
    await flushPromises();

    expect(wrapper.find('[data-testid="admin-team-select"]').exists()).toBe(
      false
    );
    expect(global.fetch.mock.calls[0][0]).toContain('/api/teams/19/players');
  });
});
