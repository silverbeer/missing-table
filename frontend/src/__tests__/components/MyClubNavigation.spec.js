/**
 * Clicking a club on the Table lands on Matches → My Club with that club's
 * team selected (SB-1114).
 *
 * It used to land with Select Club filled and Select Team empty, which quietly
 * removes everything downstream of the team: the heading, the division chip,
 * the Season Summary, the Fall Segment, Last 5, and the Result / vs-@ columns.
 *
 * The cause was a watcher that cleared the team whenever the club changed.
 * Navigation sets club and team together in one synchronous block, and a
 * watcher flushes a microtask later — so it wiped the team it had just been
 * told about. These tests set both together and let the flush happen, which is
 * the only way to catch it.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ref } from 'vue';
import { mount, flushPromises } from '@vue/test-utils';
import MatchesView from '@/components/MatchesView.vue';

let mockAuthStore;
vi.mock('@/stores/auth', () => ({ useAuthStore: () => mockAuthStore }));
vi.mock('@/config/api', () => ({
  getApiBaseUrl: () => 'http://localhost:8000',
}));

const AGE_GROUPS = [
  { id: 2, name: 'U14' },
  { id: 3, name: 'U15' },
];
const LEAGUES = [
  { id: 1, name: 'Homegrown', match_type_id: 1 },
  // Flex is a child league of Homegrown, and its conferences are its own.
  { id: 9, name: 'Flex', parent_league_id: 1, match_type_id: 2 },
];
const DIVISIONS = [
  { id: 1, name: 'Northeast', league_id: 1 },
  { id: 2, name: 'Empire', league_id: 9 },
];
const SEASONS = [
  {
    id: 184,
    name: '2026-2027',
    start_date: '2026-08-01',
    end_date: '2027-06-01',
    is_current: true,
  },
];
const MATCH_TYPES = [
  { id: 1, name: 'League', counts_for_qualification: true, display_order: 1 },
  { id: 2, name: 'Flex', counts_for_qualification: true, display_order: 2 },
];

/**
 * Metropolitan Oval U15, as production has it: League in Northeast, Flex in
 * Empire. The split across conferences is the whole point — it is why pinning
 * the Table's conference made the Flex fixtures disappear.
 */
const makeMatch = (id, matchTypeId, divisionId) => ({
  id,
  match_date: '2026-09-26',
  division_id: divisionId,
  division: {
    id: divisionId,
    name: divisionId === 1 ? 'Northeast' : 'Empire',
    league_id: divisionId === 1 ? 1 : 9,
  },
  match_type_id: matchTypeId,
  match_type_name: matchTypeId === 1 ? 'League' : 'Flex',
  age_group_id: 3,
  age_group_name: 'U15',
  season_id: 184,
  match_status: 'scheduled',
  home_team_id: 31,
  away_team_id: 44,
  home_team_name: 'Metropolitan Oval',
  away_team_name: 'FC Westchester',
});

const TEAM_MATCHES = [
  ...Array.from({ length: 19 }, (_, i) => makeMatch(100 + i, 1, 1)),
  ...Array.from({ length: 5 }, (_, i) => makeMatch(200 + i, 2, 2)),
];
const CLUBS = [
  { id: 5, name: 'Metropolitan Oval' },
  { id: 6, name: 'FC Westchester' },
];

/** Metropolitan Oval's U15 side, and another club's, to clear against. */
const TEAMS = [
  {
    id: 31,
    name: 'Metropolitan Oval',
    club_id: 5,
    league_id: 1,
    age_groups: AGE_GROUPS,
    divisions_by_age_group: {
      3: { id: 1, name: 'Northeast', league_id: 1, league_name: 'Homegrown' },
    },
  },
  {
    id: 44,
    name: 'FC Westchester',
    club_id: 6,
    league_id: 1,
    age_groups: AGE_GROUPS,
    divisions_by_age_group: {
      3: { id: 1, name: 'Northeast', league_id: 1, league_name: 'Homegrown' },
    },
  },
];

const apiRequest = () =>
  vi.fn(url => {
    if (url.includes('/api/age-groups'))
      return Promise.resolve([...AGE_GROUPS]);
    if (url.includes('/api/match-types'))
      return Promise.resolve([...MATCH_TYPES]);
    if (url.includes('/api/leagues')) return Promise.resolve([...LEAGUES]);
    if (url.includes('/api/divisions')) return Promise.resolve([...DIVISIONS]);
    if (url.includes('/api/seasons')) return Promise.resolve([...SEASONS]);
    if (url.includes('/api/teams')) return Promise.resolve([...TEAMS]);
    if (url.includes('/api/clubs')) return Promise.resolve([...CLUBS]);
    if (url.includes('/api/matches')) return Promise.resolve([...TEAM_MATCHES]);
    return Promise.resolve([]);
  });

/** Tom: an admin with no club of his own, as in the reported case. */
const adminStore = () => ({
  state: {
    loading: false,
    error: null,
    user: { id: 7 },
    profile: { id: 7, role: 'admin' },
  },
  isAuthenticated: { value: true },
  isAdmin: { value: true },
  isClubManager: { value: false },
  isTeamManager: { value: false },
  canBrowseAll: { value: true },
  userClubId: { value: null },
  userTeamId: { value: null },
  userCurrentTeamId: ref(null),
  userAgeGroupId: ref(null),
  userLeagueId: ref(null),
  userDivisionId: ref(null),
  apiRequest: apiRequest(),
});

const mountMatches = (props = {}) =>
  mount(MatchesView, {
    props,
    global: {
      stubs: {
        ClubLogo: true,
        MatchEditModal: true,
        MatchDetailView: true,
        TeamLogo: true,
      },
    },
  });

/** What App.vue passes when a team row on the Table is clicked. */
const NAVIGATION = {
  filterKey: 1,
  initialAgeGroupId: 3,
  initialLeagueId: 1,
  initialDivisionId: 1,
  initialSeasonId: 184,
  initialClubId: 5,
  initialTeamId: 31,
};

beforeEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
  mockAuthStore = adminStore();
});

describe('Table → club click → Matches, My Club', () => {
  it('arrives with the club selected', async () => {
    const wrapper = mountMatches(NAVIGATION);
    await flushPromises();
    expect(wrapper.vm.selectedClubId).toBe(5);
  });

  it('arrives with the team selected, not just the club', async () => {
    const wrapper = mountMatches(NAVIGATION);
    await flushPromises();
    expect(wrapper.vm.selectedTeam).toBe('31');
  });

  it('keeps the team through the watcher flush that used to clear it', async () => {
    const wrapper = mountMatches(NAVIGATION);
    await flushPromises();
    // A second flush: the club watcher runs a microtask after the block that
    // set both, which is exactly where the team used to disappear.
    await flushPromises();
    expect(wrapper.vm.selectedTeam).toBe('31');
  });

  it('lands on the My Club sub-tab', async () => {
    const wrapper = mountMatches(NAVIGATION);
    await flushPromises();
    expect(wrapper.vm.selectedViewTab).toBe('myclub');
  });

  it('resolves the team from the club when no team id is passed', async () => {
    const wrapper = mountMatches({ ...NAVIGATION, initialTeamId: null });
    await flushPromises();
    expect(wrapper.vm.selectedTeam).toBe('31');
  });
});

describe('changing the club by hand', () => {
  it('still clears a team that is not in the new club', async () => {
    const wrapper = mountMatches(NAVIGATION);
    await flushPromises();
    expect(wrapper.vm.selectedTeam).toBe('31');

    wrapper.vm.selectedClubId = 6;
    await flushPromises();

    expect(wrapper.vm.selectedTeam).toBe('');
  });

  it('clears the team when the club is cleared altogether', async () => {
    const wrapper = mountMatches(NAVIGATION);
    await flushPromises();

    wrapper.vm.selectedClubId = null;
    await flushPromises();

    expect(wrapper.vm.selectedTeam).toBe('');
  });
});

describe('a remembered My Club selection (SB-1112)', () => {
  it('comes back with its team, not just its club', async () => {
    window.localStorage.setItem(
      'mt.filters.v1.matches.7',
      JSON.stringify({
        ageGroupId: 3,
        seasonId: 184,
        viewTab: 'myclub',
        clubId: 5,
        teamId: 31,
      })
    );

    const wrapper = mountMatches();
    await flushPromises();

    expect(wrapper.vm.selectedViewTab).toBe('myclub');
    expect(wrapper.vm.selectedClubId).toBe(5);
    expect(wrapper.vm.selectedTeam).toBe('31');
  });
});

describe('the conference the viewer never chose (SB-1116)', () => {
  const chipLabels = vm => vm.matchTypeChips.map(chip => chip.label);
  const chipCount = (vm, label) =>
    vm.matchTypeChips.find(chip => chip.label === label)?.count ?? null;

  it('arrives on All Conferences, not pinned to the one the Table was on', async () => {
    const wrapper = mountMatches(NAVIGATION);
    await flushPromises();
    expect(wrapper.vm.selectedDivisionIds).toEqual([]);
  });

  it('shows every competition the team plays, Flex included', async () => {
    const wrapper = mountMatches(NAVIGATION);
    await flushPromises();
    expect(chipLabels(wrapper.vm)).toContain('Flex');
  });

  it('counts all 24 fixtures, not the 19 that survived a conference filter', async () => {
    const wrapper = mountMatches(NAVIGATION);
    await flushPromises();
    expect(chipCount(wrapper.vm, 'League')).toBe(19);
    expect(chipCount(wrapper.vm, 'Flex')).toBe(5);
    expect(chipCount(wrapper.vm, 'All')).toBe(24);
  });

  it('still filters when a conference is picked by hand', async () => {
    const wrapper = mountMatches(NAVIGATION);
    await flushPromises();

    wrapper.vm.toggleDivision(1);
    await flushPromises();

    expect(chipCount(wrapper.vm, 'All')).toBe(19);
    expect(chipLabels(wrapper.vm)).not.toContain('Flex');
  });

  it('still resolves the team, which is what initialDivisionId is for', async () => {
    const wrapper = mountMatches({ ...NAVIGATION, initialTeamId: null });
    await flushPromises();
    expect(wrapper.vm.selectedTeam).toBe('31');
  });
});
