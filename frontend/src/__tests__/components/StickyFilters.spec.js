/**
 * Filters survive leaving the tab (SB-1112).
 *
 * Both tabs are `v-if` in App.vue, so they unmount on leave — set U15 /
 * Northeast + Turnpike, glance at the other tab, and the old behaviour put you
 * back on U14. Unmounting and re-mounting the component is exactly what that
 * round trip does, so these tests do the same.
 *
 * The precedence being pinned, highest first: explicit navigation filters, the
 * viewer's last selection, the personalized roster default (SB-599), the U14
 * fallback.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ref } from 'vue';
import { mount, flushPromises } from '@vue/test-utils';
import LeagueTable from '@/components/LeagueTable.vue';
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
  { id: 2, name: 'Academy', match_type_id: 1 },
];
const DIVISIONS = [
  { id: 1, name: 'Northeast', league_id: 1 },
  { id: 9, name: 'Turnpike', league_id: 1 },
];
const SEASONS = [
  {
    id: 184,
    name: '2026-2027',
    start_date: '2026-08-01',
    end_date: '2027-06-01',
    is_current: true,
  },
  {
    id: 100,
    name: '2025-2026',
    start_date: '2025-08-01',
    end_date: '2026-06-01',
    is_current: false,
  },
];
const MATCH_TYPES = [
  { id: 1, name: 'League', counts_for_qualification: true, display_order: 1 },
  { id: 2, name: 'Flex', counts_for_qualification: true, display_order: 2 },
];

/** One match per division / competition, so every chip under test exists. */
const MATCHES = [
  {
    id: 1,
    match_date: '2026-09-26',
    division_id: 1,
    division: { name: 'Northeast', league_id: 1 },
    match_type_id: 1,
    match_type_name: 'League',
    age_group_name: 'U15',
    match_status: 'scheduled',
    home_team_id: 19,
    away_team_id: 20,
    home_team_name: 'IFA',
    away_team_name: 'NEFC',
  },
  {
    id: 2,
    match_date: '2026-09-26',
    division_id: 9,
    division: { name: 'Turnpike', league_id: 1 },
    match_type_id: 2,
    match_type_name: 'Flex',
    age_group_name: 'U15',
    match_status: 'scheduled',
    home_team_id: 21,
    away_team_id: 22,
    home_team_name: 'Oakwood',
    away_team_name: 'Bolts',
  },
];

const TEAMS = [
  {
    id: 19,
    name: 'IFA',
    club_id: 1,
    league_id: 1,
    age_groups: AGE_GROUPS,
    divisions_by_age_group: {
      2: { id: 1, name: 'Northeast', league_id: 1 },
      3: { id: 1, name: 'Northeast', league_id: 1 },
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
    if (url.includes('/api/clubs'))
      return Promise.resolve([{ id: 1, name: 'IFA' }]);
    if (url.includes('/api/matches')) return Promise.resolve([...MATCHES]);
    if (url.includes('/api/table'))
      return Promise.resolve({
        has_qop_data: false,
        qop_week_of: null,
        standings: [],
      });
    return Promise.resolve([]);
  });

/** An admin: no roster row, so nothing personalizes and U14 is the default. */
const adminStore = () => ({
  state: {
    loading: false,
    error: null,
    user: { id: 7 },
    profile: { id: 7, role: 'admin' },
  },
  isAuthenticated: { value: true },
  isAdmin: { value: true },
  // canEditGame reads all three role flags on every row render, and a render
  // flushed after unmount surfaces a missing one as an unhandled rejection
  // rather than a failing assertion.
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

const mountTable = (props = {}) =>
  mount(LeagueTable, {
    props,
    global: { stubs: { PlayoffBracket: true, ClubLogo: true } },
  });

/** Mount, let the fetches settle, act, then unmount — one visit to a tab. */
const visitMatches = async (act, props = {}) => {
  const wrapper = mountMatches(props);
  await flushPromises();
  if (act) await act(wrapper.vm);
  await flushPromises();
  const seen = { ...wrapper.vm.$data };
  wrapper.unmount();
  return seen;
};

beforeEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
  mockAuthStore = adminStore();
});

describe('Matches tab — filters survive the round trip', () => {
  it('comes back on the age group, season, divisions and competition it left on', async () => {
    await visitMatches(vm => {
      vm.selectAgeGroup(3);
      vm.selectedSeasonId = 100;
      vm.toggleDivision(1);
      vm.toggleDivision(9);
      vm.selectedMatchTypeId = 2;
    });

    const wrapper = mountMatches();
    await flushPromises();

    expect(wrapper.vm.selectedAgeGroupId).toBe(3);
    expect(wrapper.vm.selectedSeasonId).toBe(100);
    expect(wrapper.vm.selectedDivisionIds).toEqual([1, 9]);
    expect(wrapper.vm.selectedMatchTypeId).toBe(2);
  });

  it('comes back on the sub-tab it left on', async () => {
    await visitMatches(vm => {
      vm.selectedViewTab = 'myclub';
    });

    const wrapper = mountMatches();
    await flushPromises();
    expect(wrapper.vm.selectedViewTab).toBe('myclub');
  });

  it('does not remember the week — a matchday opens on this week', async () => {
    await visitMatches(vm => {
      vm.selectAgeGroup(3);
      vm.weekOffset = -2;
    });

    const wrapper = mountMatches();
    await flushPromises();
    expect(wrapper.vm.weekOffset).toBe(0);
  });

  it('yields to an explicit team navigation — that team, not where you were', async () => {
    await visitMatches(vm => {
      vm.selectAgeGroup(3);
      vm.toggleDivision(9);
    });

    const wrapper = mountMatches({
      filterKey: 1,
      initialAgeGroupId: 2,
      initialDivisionId: 1,
    });
    await flushPromises();

    expect(wrapper.vm.selectedAgeGroupId).toBe(2);
    expect(wrapper.vm.selectedDivisionIds).toEqual([1]);
  });

  it('drops a division that is no longer there, and keeps the rest', async () => {
    window.localStorage.setItem(
      'mt.filters.v1.matches.7',
      JSON.stringify({ ageGroupId: 3, divisionIds: [9, 404] })
    );

    const wrapper = mountMatches();
    await flushPromises();
    expect(wrapper.vm.selectedDivisionIds).toEqual([9]);
  });

  it('falls back to every division when none of the saved ones survive', async () => {
    window.localStorage.setItem(
      'mt.filters.v1.matches.7',
      JSON.stringify({ ageGroupId: 3, divisionIds: [404, 405] })
    );

    const wrapper = mountMatches();
    await flushPromises();
    expect(wrapper.vm.selectedDivisionIds).toEqual([]);
  });

  it('ignores a saved age group and season that no longer exist', async () => {
    window.localStorage.setItem(
      'mt.filters.v1.matches.7',
      JSON.stringify({ ageGroupId: 404, seasonId: 405 })
    );

    const wrapper = mountMatches();
    await flushPromises();
    expect(wrapper.vm.selectedAgeGroupId).toBe(2);
    expect(AGE_GROUPS.some(a => a.id === wrapper.vm.selectedAgeGroupId)).toBe(
      true
    );
    expect(SEASONS.some(s => s.id === wrapper.vm.selectedSeasonId)).toBe(true);
  });

  it('ignores a saved competition with no chip — nothing filtered to nothing', async () => {
    window.localStorage.setItem(
      'mt.filters.v1.matches.7',
      JSON.stringify({ ageGroupId: 3, matchTypeId: 404 })
    );

    const wrapper = mountMatches();
    await flushPromises();
    expect(wrapper.vm.selectedMatchTypeId).toBeNull();
  });

  it('does not inherit another viewer’s filters', async () => {
    await visitMatches(vm => {
      vm.selectAgeGroup(3);
      vm.toggleDivision(9);
    });

    mockAuthStore = adminStore();
    mockAuthStore.state.profile = { id: 99, role: 'admin' };
    mockAuthStore.state.user = { id: 99 };

    const wrapper = mountMatches();
    await flushPromises();
    expect(wrapper.vm.selectedAgeGroupId).toBe(2);
    expect(wrapper.vm.selectedDivisionIds).toEqual([]);
  });

  it('works when localStorage throws, on defaults', async () => {
    const getItem = vi
      .spyOn(Storage.prototype, 'getItem')
      .mockImplementation(() => {
        throw new Error('SecurityError');
      });
    const setItem = vi
      .spyOn(Storage.prototype, 'setItem')
      .mockImplementation(() => {
        throw new Error('QuotaExceededError');
      });

    const wrapper = mountMatches();
    await flushPromises();
    wrapper.vm.selectAgeGroup(3);
    await flushPromises();

    expect(wrapper.vm.selectedAgeGroupId).toBe(3);

    getItem.mockRestore();
    setItem.mockRestore();
  });
});

describe('Table tab — filters survive the round trip', () => {
  it('comes back on the age group and season it left on', async () => {
    const first = mountTable();
    await flushPromises();
    first.vm.selectAgeGroup(3);
    first.vm.selectedSeasonId = 100;
    await flushPromises();
    first.unmount();

    const wrapper = mountTable();
    await flushPromises();
    expect(wrapper.vm.selectedAgeGroupId).toBe(3);
    expect(wrapper.vm.selectedSeasonId).toBe(100);
  });

  it('yields to an explicit team navigation', async () => {
    const first = mountTable();
    await flushPromises();
    first.vm.selectAgeGroup(3);
    await flushPromises();
    first.unmount();

    const wrapper = mountTable({
      filterKey: 1,
      initialAgeGroupId: 2,
      initialLeagueId: 1,
      initialDivisionId: 1,
    });
    await flushPromises();
    expect(wrapper.vm.selectedAgeGroupId).toBe(2);
  });

  it('ignores a saved age group that no longer exists', async () => {
    window.localStorage.setItem(
      'mt.filters.v1.table.7',
      JSON.stringify({ ageGroupId: 404, leagueId: 1 })
    );

    const wrapper = mountTable();
    await flushPromises();
    expect(AGE_GROUPS.some(a => a.id === wrapper.vm.selectedAgeGroupId)).toBe(
      true
    );
  });
});
