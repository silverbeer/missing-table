/**
 * Default age group preference (SB-1286).
 *
 * Table and Matches open on: the remembered pick in this browser (SB-1112),
 * then the account's saved preference, then the team's age group (SB-599),
 * then U14. Last pick wins.
 *
 * The default fixture is an account with no team and no preference — a club
 * manager like tom_club, who landed on U14 on every fresh device.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ref } from 'vue';
import { mount, flushPromises } from '@vue/test-utils';
import LeagueTable from '@/components/LeagueTable.vue';
import MatchesView from '@/components/MatchesView.vue';
import PreferencesCard from '@/components/profiles/PreferencesCard.vue';

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
// U15 plays Homegrown/Northeast, U14 plays Academy/New England — different
// per age group, so a roster row's league applied to the wrong age shows.
const TEAMS = [
  {
    id: 19,
    name: 'IFA',
    club_id: 1,
    age_groups: AGE_GROUPS,
    divisions_by_age_group: {
      2: { id: 7, name: 'New England', league_id: 2 },
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

/** A club manager with no team: the default fixture. */
const store = ({ preferred = null, teamAgeGroup = null } = {}) => {
  const hasTeam = teamAgeGroup !== null;
  return {
    state: {
      loading: false,
      error: null,
      user: { id: 'u-1' },
      profile: {
        role: hasTeam ? 'team-player' : 'club_manager',
        team_id: hasTeam ? 19 : null,
        club_id: 1,
        preferences:
          preferred === null ? {} : { default_age_group_id: preferred },
      },
    },
    isAuthenticated: { value: true },
    isAdmin: { value: false },
    isTeamManager: { value: false },
    canBrowseAll: { value: true },
    userClubId: { value: 1 },
    userTeamId: { value: hasTeam ? 19 : null },
    userCurrentTeamId: ref(hasTeam ? 19 : null),
    userAgeGroupId: ref(teamAgeGroup),
    userLeagueId: ref(hasTeam ? 1 : null),
    userDivisionId: ref(hasTeam ? 1 : null),
    preferredAgeGroupId: ref(preferred),
    apiRequest: apiRequest(),
    updatePreferences: vi.fn(() => Promise.resolve({ success: true })),
  };
};

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

const remember = (view, filters) =>
  window.localStorage.setItem(
    `mt.filters.v1.${view}.u-1`,
    JSON.stringify(filters)
  );

describe('LeagueTable — default age group preference', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
  });

  it('opens on U14 with no preference and no team', async () => {
    mockAuthStore = store();
    const wrapper = mountTable();
    await flushPromises();
    expect(wrapper.vm.selectedAgeGroupId).toBe(2);
  });

  it('opens on the preference for an account with no team', async () => {
    mockAuthStore = store({ preferred: 3 });
    const wrapper = mountTable();
    await flushPromises();
    expect(wrapper.vm.selectedAgeGroupId).toBe(3);
  });

  it("beats the team's age group, and does not borrow that row's league", async () => {
    // Team is U15 (roster row: Homegrown/Northeast); preference is U14.
    mockAuthStore = store({ preferred: 2, teamAgeGroup: 3 });
    const wrapper = mountTable();
    await flushPromises();
    expect(wrapper.vm.selectedAgeGroupId).toBe(2);
    // U14's own division for this team, not the U15 roster row's.
    expect(wrapper.vm.selectedLeagueId).toBe(2);
    expect(wrapper.vm.selectedDivisionId).toBe(7);
  });

  it('falls through a preference for an age group that no longer exists', async () => {
    mockAuthStore = store({ preferred: 99 });
    const wrapper = mountTable();
    await flushPromises();
    expect(wrapper.vm.selectedAgeGroupId).toBe(2);
  });

  it('loses to the pick remembered in this browser — last pick wins', async () => {
    remember('table', { ageGroupId: 3 });
    mockAuthStore = store({ preferred: 2 });
    const wrapper = mountTable();
    await flushPromises();
    expect(wrapper.vm.selectedAgeGroupId).toBe(3);
  });

  it('applies a preference that arrives after mount', async () => {
    mockAuthStore = store();
    const wrapper = mountTable();
    await flushPromises();
    mockAuthStore.preferredAgeGroupId.value = 3;
    await flushPromises();
    expect(wrapper.vm.selectedAgeGroupId).toBe(3);
  });
});

describe('MatchesView — default age group preference', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
  });

  it('opens on U14 with no preference and no team', async () => {
    mockAuthStore = store();
    const wrapper = mountMatches();
    await flushPromises();
    expect(wrapper.vm.selectedAgeGroupId).toBe(2);
  });

  it('opens on the preference', async () => {
    mockAuthStore = store({ preferred: 3 });
    const wrapper = mountMatches();
    await flushPromises();
    expect(wrapper.vm.selectedAgeGroupId).toBe(3);
  });

  it("beats the team's age group and takes that age group's league", async () => {
    mockAuthStore = store({ preferred: 2, teamAgeGroup: 3 });
    const wrapper = mountMatches();
    await flushPromises();
    expect(wrapper.vm.selectedAgeGroupId).toBe(2);
    expect(wrapper.vm.selectedLeagueId).toBe(2);
  });

  it('falls through a preference for an age group that no longer exists', async () => {
    mockAuthStore = store({ preferred: 99 });
    const wrapper = mountMatches();
    await flushPromises();
    expect(wrapper.vm.selectedAgeGroupId).toBe(2);
  });
});

describe('PreferencesCard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
  });

  const select = wrapper =>
    wrapper.find('[data-testid="default-age-group-select"]');

  it('shows Automatic as the U14 fallback for an account with no team', async () => {
    mockAuthStore = store();
    const wrapper = mount(PreferencesCard);
    await flushPromises();
    const options = select(wrapper).findAll('option');
    expect(options.map(o => o.text())).toEqual([
      'Automatic (U14)',
      'U14',
      'U15',
    ]);
    expect(select(wrapper).element.value).toBe('');
  });

  it("names the team's age group in the Automatic option", async () => {
    mockAuthStore = store({ teamAgeGroup: 3 });
    const wrapper = mount(PreferencesCard);
    await flushPromises();
    expect(select(wrapper).find('option').text()).toBe(
      'Automatic (my team: U15)'
    );
  });

  it('saves the choice and drops remembered picks so it shows next visit', async () => {
    remember('table', { ageGroupId: 2 });
    remember('matches', { ageGroupId: 2 });
    mockAuthStore = store();
    const wrapper = mount(PreferencesCard);
    await flushPromises();

    await select(wrapper).setValue('3');
    await flushPromises();

    expect(mockAuthStore.updatePreferences).toHaveBeenCalledWith({
      default_age_group_id: 3,
    });
    expect(window.localStorage.getItem('mt.filters.v1.table.u-1')).toBeNull();
    expect(window.localStorage.getItem('mt.filters.v1.matches.u-1')).toBeNull();
    expect(wrapper.find('[data-testid="preference-status"]').text()).toBe(
      'Saved'
    );
  });

  it('sends null to clear the preference', async () => {
    mockAuthStore = store({ preferred: 3 });
    const wrapper = mount(PreferencesCard);
    await flushPromises();
    expect(select(wrapper).element.value).toBe('3');

    await select(wrapper).setValue('');
    await flushPromises();

    expect(mockAuthStore.updatePreferences).toHaveBeenCalledWith({
      default_age_group_id: null,
    });
  });

  it('reverts and says so when the save fails, keeping remembered picks', async () => {
    remember('table', { ageGroupId: 2 });
    mockAuthStore = store({ preferred: 2 });
    mockAuthStore.updatePreferences = vi.fn(() =>
      Promise.resolve({ success: false, error: 'Unknown age group: 3' })
    );
    const wrapper = mount(PreferencesCard);
    await flushPromises();

    await select(wrapper).setValue('3');
    await flushPromises();

    expect(select(wrapper).element.value).toBe('2');
    expect(wrapper.find('[data-testid="preference-status"]').text()).toBe(
      'Unknown age group: 3'
    );
    expect(
      window.localStorage.getItem('mt.filters.v1.table.u-1')
    ).not.toBeNull();
  });
});
