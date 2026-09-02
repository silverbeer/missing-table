/**
 * Leagues worth offering, in both places they are offered (SB-851).
 *
 * `/api/leagues` returns every league. So the League filter on the table
 * offered **Kick Futsal** — inactive since its only season ended — on every
 * season, and the Matches → My Club team picker showed IFA's four Kick Futsal
 * teams alongside its three real ones, two seasons after that league stopped
 * running.
 *
 * The rule is: **active, or the selected season has matches in it.** Both
 * halves are load-bearing, and each has a test here that fails without it.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import LeagueTable from '@/components/LeagueTable.vue';
import MatchesView from '@/components/MatchesView.vue';

let mockAuthStore;
vi.mock('@/stores/auth', () => ({ useAuthStore: () => mockAuthStore }));
vi.mock('@/config/api', () => ({
  getApiBaseUrl: () => 'http://localhost:8000',
}));

const SEASONS = [
  {
    id: 184,
    name: '2026-2027',
    start_date: '2026-08-01',
    end_date: '2027-06-01',
    is_current: true,
  },
  {
    id: 3,
    name: '2025-2026',
    start_date: '2025-08-01',
    end_date: '2026-06-01',
  },
];

// What /api/leagues/available returns for 2026-2027: Kick Futsal is gone.
const CURRENT_SEASON_LEAGUES = [
  { id: 1, name: 'Homegrown', is_active: true, matches_this_season: 190 },
  { id: 2, name: 'Academy', is_active: true, matches_this_season: 0 },
  { id: 290, name: 'Flex', is_active: true, matches_this_season: 68 },
];

// ...and for 2025-2026, where it has 24 matches and comes back.
const PAST_SEASON_LEAGUES = [
  ...CURRENT_SEASON_LEAGUES.map(l => ({ ...l, matches_this_season: 100 })),
  { id: 34, name: 'Kick Futsal', is_active: false, matches_this_season: 24 },
];

const leaguesFor = url =>
  url.includes('season_id=3') ? PAST_SEASON_LEAGUES : CURRENT_SEASON_LEAGUES;

describe('LeagueTable — League filter', () => {
  beforeEach(() => vi.clearAllMocks());

  const mountTable = () => {
    const calls = [];
    mockAuthStore = {
      isAuthenticated: { value: false },
      userRole: { value: null },
      isAdmin: { value: false },
      userClubId: { value: null },
      userTeamId: { value: null },
      apiRequest: vi.fn(url => {
        calls.push(url);
        if (url.includes('/api/leagues/available'))
          return Promise.resolve(leaguesFor(url).map(l => ({ ...l })));
        if (url.includes('/api/leagues')) return Promise.resolve([]);
        if (url.includes('/api/match-types/available'))
          return Promise.resolve([
            {
              id: 1,
              name: 'League',
              counts_for_qualification: true,
              display_order: 1,
              matches: 190,
              played: 0,
              in_division: 190,
            },
          ]);
        if (url.includes('/api/table'))
          return Promise.resolve({
            has_qop_data: false,
            qop_week_of: null,
            standings: [],
            coverage: null,
          });
        if (url.includes('/api/seasons'))
          return Promise.resolve(SEASONS.map(s => ({ ...s })));
        if (url.includes('/api/age-groups'))
          return Promise.resolve([{ id: 3, name: 'U15' }]);
        if (url.includes('/api/divisions'))
          return Promise.resolve([{ id: 1, name: 'Northeast', league_id: 1 }]);
        return Promise.resolve([]);
      }),
    };
    const wrapper = mount(LeagueTable, {
      global: { stubs: { PlayoffBracket: true, ClubLogo: true } },
    });
    return { wrapper, calls };
  };

  const leagueButtons = wrapper =>
    wrapper
      .findAll('button')
      .map(b => b.text().trim())
      .filter(t => ['Homegrown', 'Academy', 'Flex', 'Kick Futsal'].includes(t));

  it('asks only for the leagues worth offering this season', async () => {
    const { calls } = mountTable();
    await flushPromises();
    expect(
      calls.some(u => u.includes('/api/leagues/available?season_id=184'))
    ).toBe(true);
  });

  it('does not offer a dormant league in a season it did not play', async () => {
    const { wrapper } = mountTable();
    await flushPromises();
    expect(leagueButtons(wrapper)).not.toContain('Kick Futsal');
  });

  it('still offers an active league with no matches yet', async () => {
    // Academy has 0 matches in 2026-2027. Presence alone would drop it, and
    // with it three legitimate IFA teams.
    const { wrapper } = mountTable();
    await flushPromises();
    expect(leagueButtons(wrapper)).toContain('Academy');
  });

  it('re-reads the leagues when the season changes', async () => {
    const { wrapper, calls } = mountTable();
    await flushPromises();

    wrapper.vm.selectedSeasonId = 3;
    await flushPromises();

    expect(calls.some(u => u.includes('season_id=3'))).toBe(true);
  });

  it('brings a dormant league back for the season it played', async () => {
    const { wrapper } = mountTable();
    await flushPromises();

    wrapper.vm.selectedSeasonId = 3;
    await flushPromises();

    // 24 matches in 2025-2026 — hiding it would make real history unreachable.
    expect(leagueButtons(wrapper)).toContain('Kick Futsal');
  });
});

describe('MatchesView — My Club team picker', () => {
  beforeEach(() => vi.clearAllMocks());

  const division = (id, name, leagueId, leagueName) => ({
    id,
    name,
    league_id: leagueId,
    league_name: leagueName,
  });

  // IFA's real teams and its defunct futsal ones, all at U14.
  const TEAMS = [
    {
      id: 19,
      name: 'IFA',
      club_id: 5,
      age_groups: [{ id: 2, name: 'U14' }],
      divisions_by_age_group: { 2: division(1, 'Northeast', 1, 'Homegrown') },
    },
    {
      id: 123,
      name: 'IFA Academy',
      club_id: 5,
      age_groups: [{ id: 2, name: 'U14' }],
      divisions_by_age_group: { 2: division(7, 'New England', 2, 'Academy') },
    },
    {
      id: 183,
      name: 'IFA Elite Futsal 2012 Blue',
      club_id: 5,
      age_groups: [{ id: 2, name: 'U14' }],
      divisions_by_age_group: {
        2: division(60, 'Bracket B', 34, 'Kick Futsal'),
      },
    },
    {
      id: 185,
      name: 'IFA Futsal South 2012 Boys',
      club_id: 5,
      age_groups: [{ id: 2, name: 'U14' }],
      divisions_by_age_group: {
        2: division(61, 'Bracket A', 34, 'Kick Futsal'),
      },
    },
    {
      id: 999,
      name: 'IFA Mystery',
      club_id: 5,
      age_groups: [{ id: 2, name: 'U14' }],
      divisions_by_age_group: {},
    },
  ];

  const mountMatches = () => {
    mockAuthStore = {
      isAuthenticated: { value: true },
      userRole: { value: 'admin' },
      isAdmin: { value: true },
      canBrowseAll: { value: true },
      userClubId: { value: null },
      userTeamId: { value: null },
      userCurrentTeamId: { value: null },
      userLeagueId: { value: null },
      userDivisionId: { value: null },
      apiRequest: vi.fn(url => {
        if (url.includes('/api/leagues/available'))
          return Promise.resolve(leaguesFor(url).map(l => ({ ...l })));
        if (url.includes('/api/teams'))
          return Promise.resolve(TEAMS.map(t => ({ ...t })));
        if (url.includes('/api/clubs'))
          return Promise.resolve([{ id: 5, name: 'IFA' }]);
        if (url.includes('/api/seasons'))
          return Promise.resolve(SEASONS.map(s => ({ ...s })));
        if (url.includes('/api/age-groups'))
          return Promise.resolve([{ id: 2, name: 'U14' }]);
        return Promise.resolve([]);
      }),
    };
    return mount(MatchesView, {
      global: {
        stubs: {
          ClubLogo: true,
          FollowButton: true,
          ScorePill: true,
          RouterLink: true,
        },
      },
    });
  };

  // TeamCombobox (SB-964) only renders its option rows once open, so read
  // them after focusing its input rather than a native <select>'s <option>s.
  const teamOptions = async wrapper => {
    const selector = wrapper.find('[data-testid="team-selector"]');
    if (!selector.exists()) return [];
    await selector.find('input').trigger('focus');
    await flushPromises();
    return selector
      .findAll('[data-testid="team-combobox-option"]')
      .map(o => o.text().trim());
  };

  it('hides teams whose league is not offered this season', async () => {
    const wrapper = mountMatches();
    await flushPromises();
    wrapper.vm.selectedViewTab = 'myclub';
    wrapper.vm.selectedClubId = 5;
    wrapper.vm.selectedAgeGroupId = 2;
    await flushPromises();

    const options = (await teamOptions(wrapper)).join(' ');
    expect(options).not.toContain('Futsal');
  });

  it('keeps the club real teams', async () => {
    const wrapper = mountMatches();
    await flushPromises();
    wrapper.vm.selectedViewTab = 'myclub';
    wrapper.vm.selectedClubId = 5;
    wrapper.vm.selectedAgeGroupId = 2;
    await flushPromises();

    const options = (await teamOptions(wrapper)).join(' ');
    expect(options).toContain('IFA');
    expect(options).toContain('IFA Academy');
  });

  it('keeps a team whose division is unknown', async () => {
    // Missing metadata is not evidence that a team is defunct, and hiding a
    // real team is the worse error.
    const wrapper = mountMatches();
    await flushPromises();
    wrapper.vm.selectedViewTab = 'myclub';
    wrapper.vm.selectedClubId = 5;
    wrapper.vm.selectedAgeGroupId = 2;
    await flushPromises();

    const options = (await teamOptions(wrapper)).join(' ');
    expect(options).toContain('IFA Mystery');
  });
});
