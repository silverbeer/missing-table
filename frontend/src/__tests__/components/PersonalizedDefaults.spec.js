/**
 * Personalized filter defaults (SB-599).
 *
 * A signed-in player used to land on the app-wide U14 default and had to change
 * the age group on every visit. Their current-season roster row now drives the
 * age group, league and division on the Table and Matches views, and the team on
 * the My Club tab. Anonymous visitors and admins keep the old U14 fallback.
 *
 * apiRequest is routed by URL so the components' several mount-time fetches
 * resolve without fighting each other.
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
  { id: 1, name: 'Homegrown' },
  { id: 2, name: 'Academy' },
];
const DIVISIONS = [
  { id: 1, name: 'Northeast', league_id: 1 },
  { id: 7, name: 'New England', league_id: 2 },
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
// IFA is an umbrella club team carrying more than one age group, which is why
// the team-level lookup can't answer "which age group is this viewer in".
const TEAMS = [
  {
    id: 19,
    name: 'IFA',
    club_id: 1,
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
    if (url.includes('/api/leagues')) return Promise.resolve([...LEAGUES]);
    if (url.includes('/api/divisions')) return Promise.resolve([...DIVISIONS]);
    if (url.includes('/api/seasons')) return Promise.resolve([...SEASONS]);
    if (url.includes('/api/teams')) return Promise.resolve([...TEAMS]);
    if (url.includes('/api/clubs'))
      return Promise.resolve([{ id: 1, name: 'IFA' }]);
    if (url.includes('/api/table'))
      return Promise.resolve({
        has_qop_data: false,
        qop_week_of: null,
        standings: [],
      });
    if (url.includes('/api/match-types'))
      return Promise.resolve([{ id: 1, name: 'League' }]);
    return Promise.resolve([]);
  });

/** Gabe: U15, Homegrown, Northeast, IFA — the ticket's worked example. */
const playerStore = () => ({
  state: {
    loading: false,
    error: null,
    user: { id: 1 },
    profile: { role: 'team-player', team_id: 19, club_id: 1 },
  },
  isAuthenticated: { value: true },
  isAdmin: { value: false },
  isTeamManager: { value: false },
  canBrowseAll: { value: true },
  userClubId: { value: 1 },
  userTeamId: { value: 19 },
  userCurrentTeamId: { value: 19 },
  userAgeGroupId: { value: 3 },
  userLeagueId: { value: 1 },
  userDivisionId: { value: 1 },
  apiRequest: apiRequest(),
});

/**
 * Logged out — nothing to personalize from. The roster-context fields are real
 * refs so a test can push a value in mid-flight and the components' watchers
 * actually see it, the way the reactive store behaves on a cold load.
 */
const anonStore = () => ({
  state: { loading: false, error: null, user: null, profile: null },
  isAuthenticated: { value: false },
  isAdmin: { value: false },
  isTeamManager: { value: false },
  canBrowseAll: { value: false },
  userClubId: { value: null },
  userTeamId: { value: null },
  userCurrentTeamId: ref(null),
  userAgeGroupId: ref(null),
  userLeagueId: ref(null),
  userDivisionId: ref(null),
  apiRequest: apiRequest(),
});

const mountTable = () =>
  mount(LeagueTable, {
    global: { stubs: { PlayoffBracket: true, ClubLogo: true } },
  });

const mountMatches = () =>
  mount(MatchesView, {
    global: {
      stubs: {
        ClubLogo: true,
        MatchEditModal: true,
        MatchDetailView: true,
        TeamLogo: true,
      },
    },
  });

describe('LeagueTable — personalized defaults', () => {
  beforeEach(() => vi.clearAllMocks());

  it("opens on the viewer's own age group, not the U14 fallback", async () => {
    mockAuthStore = playerStore();
    const wrapper = mountTable();
    await flushPromises();

    expect(wrapper.vm.selectedAgeGroupId).toBe(3); // U15
  });

  it('takes league and division from the roster row, which is age-specific', async () => {
    mockAuthStore = playerStore();
    const wrapper = mountTable();
    await flushPromises();

    expect(wrapper.vm.selectedLeagueId).toBe(1); // Homegrown
    expect(wrapper.vm.selectedDivisionId).toBe(1); // Northeast
  });

  it('still lands on U14 for a logged-out visitor', async () => {
    mockAuthStore = anonStore();
    const wrapper = mountTable();
    await flushPromises();

    expect(wrapper.vm.selectedAgeGroupId).toBe(2); // U14
  });

  it("keeps the viewer's own pick when the profile resolves late", async () => {
    // Cold load: the component mounts before /api/auth/me comes back.
    mockAuthStore = anonStore();
    const wrapper = mountTable();
    await flushPromises();

    wrapper.vm.selectAgeGroup(2);
    mockAuthStore.userAgeGroupId.value = 3; // profile lands afterwards
    await flushPromises();

    expect(wrapper.vm.selectedAgeGroupId).toBe(2);
  });

  it('applies the age group when the profile resolves late and nothing was picked', async () => {
    mockAuthStore = anonStore();
    const wrapper = mountTable();
    await flushPromises();

    mockAuthStore.userAgeGroupId.value = 3;
    await flushPromises();

    expect(wrapper.vm.selectedAgeGroupId).toBe(3);
  });
});

describe('MatchesView — personalized defaults', () => {
  beforeEach(() => vi.clearAllMocks());

  it("opens on the viewer's own age group", async () => {
    mockAuthStore = playerStore();
    const wrapper = mountMatches();
    await flushPromises();

    expect(wrapper.vm.selectedAgeGroupId).toBe(3); // U15
  });

  it("preselects the viewer's club and team so My Club is not an empty picker", async () => {
    mockAuthStore = playerStore();
    const wrapper = mountMatches();
    await flushPromises();

    expect(wrapper.vm.selectedTeam).toBe('19');
    expect(wrapper.vm.selectedClubId).toBe(1);
    expect(wrapper.vm.selectedLeagueId).toBe(1); // Homegrown
  });

  it('still lands on U14 for a logged-out visitor', async () => {
    mockAuthStore = anonStore();
    const wrapper = mountMatches();
    await flushPromises();

    expect(wrapper.vm.selectedAgeGroupId).toBe(2);
    expect(wrapper.vm.selectedTeam).toBe('');
  });
});
