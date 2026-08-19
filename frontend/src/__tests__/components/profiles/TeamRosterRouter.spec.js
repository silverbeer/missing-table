/**
 * TeamRosterRouter — who reaches the team page (SB-668).
 *
 * The tab gate was widened first and this one was missed, so the My Club tab
 * appeared for a manager and the page behind it said "Players Only". Both
 * checks now read the same list, and these pin that they agree.
 */

import { describe, it, expect, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import TeamRosterRouter from '@/components/profiles/TeamRosterRouter.vue';
import { TEAM_PAGE_ROLES, hasAnyRole } from '@/utils/roles';

const profile = { role: 'team-player', team_id: 11, club_id: null };

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    state: {
      get profile() {
        return profile;
      },
      loading: false,
    },
    isAuthenticated: true,
    apiRequest: vi.fn().mockResolvedValue({}),
  }),
}));

vi.mock('@/components/profiles/TeamRosterPage.vue', () => ({
  default: { name: 'TeamRosterPage', template: '<div class="roster-page" />' },
}));
vi.mock('@/components/profiles/PlayerDetailView.vue', () => ({
  default: { template: '<div />' },
}));

const mountRouter = (role, extra = {}) => {
  profile.role = role;
  profile.team_id = 11;
  profile.club_id = null;
  Object.assign(profile, extra);
  return mount(TeamRosterRouter);
};

describe('TeamRosterRouter access (SB-668)', () => {
  it.each(TEAM_PAGE_ROLES)('renders the page for %s', role => {
    const wrapper = mountRouter(role);

    expect(wrapper.find('.roster-page').exists()).toBe(true);
    expect(wrapper.text()).not.toContain('No Squad Access');
  });

  it.each(['club_manager', 'club-fan'])(
    'renders for %s who has a club but no team',
    role => {
      const wrapper = mountRouter(role, { team_id: null, club_id: 3 });

      // TeamRosterPage resolves a squad from the club; demanding a team here
      // would lock these roles out of a page built for them.
      expect(wrapper.find('.roster-page').exists()).toBe(true);
    }
  );

  it('accepts either spelling of a role', () => {
    expect(mountRouter('team_manager').find('.roster-page').exists()).toBe(
      true
    );
    expect(mountRouter('club_fan').find('.roster-page').exists()).toBe(true);
  });

  it('still refuses a role with no stake in a squad', () => {
    const wrapper = mountRouter('some-other-role');

    expect(wrapper.find('.roster-page').exists()).toBe(false);
    expect(wrapper.text()).toContain('No Squad Access');
  });

  it('asks for a team when there is neither team nor club', () => {
    const wrapper = mountRouter('team-player', {
      team_id: null,
      club_id: null,
    });

    expect(wrapper.text()).toContain('No Team Assigned');
  });

  it('agrees with the list the tab is gated on', () => {
    // The regression was these two disagreeing.
    for (const role of TEAM_PAGE_ROLES) {
      expect(hasAnyRole(TEAM_PAGE_ROLES, role)).toBe(true);
    }
  });
});

describe('TeamRosterRouter admin access (SB-792)', () => {
  it('renders the page for an admin with no team and no club', () => {
    // An admin belongs to no squad by design, so every affiliation check is
    // false for them. Before this they hit "No Team Assigned" with no way
    // forward — the role meant to see everything reaching less than a fan.
    const wrapper = mountRouter('admin', { team_id: null, club_id: null });

    expect(wrapper.find('.roster-page').exists()).toBe(true);
    expect(wrapper.text()).not.toContain('No Team Assigned');
  });

  it('still asks a non-admin with no affiliation to get assigned', () => {
    // The admin bypass must not leak to everyone else: a player genuinely
    // waiting on a team assignment should still be told so.
    const wrapper = mountRouter('team-player', {
      team_id: null,
      club_id: null,
      current_teams: [],
    });

    expect(wrapper.find('.roster-page').exists()).toBe(false);
    expect(wrapper.text()).toContain('No Team Assigned');
  });
});
