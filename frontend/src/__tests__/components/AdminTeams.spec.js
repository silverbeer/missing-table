/**
 * AdminTeams.vue — team name / parent-club search/filter.
 *
 * Mocks the auth store's apiRequest (dispatching per URL — teams list plus the
 * reference-data fetches on mount) and asserts the client-side filter narrows
 * the rendered team rows and surfaces a no-results row.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import AdminTeams from '@/components/admin/AdminTeams.vue';

let mockAuthStore;
vi.mock('@/stores/auth', () => ({ useAuthStore: () => mockAuthStore }));
vi.mock('@/config/api', () => ({
  getApiBaseUrl: () => 'http://localhost:8000',
}));

const TEAMS = [
  {
    id: 1,
    name: 'ALBION SC Colorado',
    parent_club: { name: 'ALBION SC Colorado' },
    league_name: 'Homegrown',
    age_groups: [],
  },
  {
    id: 2,
    name: 'AC River',
    parent_club: { name: 'AC River' },
    league_name: 'Homegrown',
    age_groups: [],
  },
  {
    id: 3,
    name: 'PDA Tigers',
    parent_club: { name: 'Players Development Academy' },
    league_name: 'Homegrown',
    age_groups: [],
  },
];

// On mount AdminTeams loads teams + age-groups/clubs/divisions/leagues/match-types/seasons.
const byUrl = url => {
  if (url.includes('/api/teams'))
    return Promise.resolve(TEAMS.map(t => ({ ...t })));
  return Promise.resolve([]);
};

const mountTeams = () => {
  mockAuthStore = {
    userRole: { value: 'admin' },
    userClubId: { value: null },
    apiRequest: vi.fn(url => byUrl(url)),
  };
  return mount(AdminTeams);
};

describe('AdminTeams search', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders all teams before searching', async () => {
    const wrapper = mountTeams();
    await flushPromises();
    expect(wrapper.findAll('[data-team-row]')).toHaveLength(3);
  });

  it('filters by team name', async () => {
    const wrapper = mountTeams();
    await flushPromises();

    await wrapper.find('[data-testid="team-search"]').setValue('albion');

    const rows = wrapper.findAll('[data-team-row]');
    expect(rows).toHaveLength(1);
    expect(rows[0].text()).toContain('ALBION SC Colorado');
  });

  it('also matches on parent club name', async () => {
    const wrapper = mountTeams();
    await flushPromises();

    // "PDA Tigers" team belongs to the "Players Development Academy" club.
    await wrapper
      .find('[data-testid="team-search"]')
      .setValue('players development');

    const rows = wrapper.findAll('[data-team-row]');
    expect(rows).toHaveLength(1);
    expect(rows[0].text()).toContain('PDA Tigers');
  });

  it('shows a no-results row when nothing matches', async () => {
    const wrapper = mountTeams();
    await flushPromises();

    await wrapper.find('[data-testid="team-search"]').setValue('zzzzz');

    expect(wrapper.find('[data-testid="team-search-empty"]').exists()).toBe(
      true
    );
    expect(wrapper.findAll('[data-team-row]')).toHaveLength(0);
  });
});

// Regression: the Edit Team "Game Types" checkboxes must hit the backend's
// /match-types route with a match_type_id field. A prior bug called a
// non-existent /game-types route with game_type_id, so saves 404'd and
// participation silently never persisted.
describe('AdminTeams game-type participation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const callsMatching = pred =>
    mockAuthStore.apiRequest.mock.calls.filter(([url]) => pred(url));

  it('adds new game types via /match-types with match_type_id', async () => {
    const wrapper = mountTeams();
    await flushPromises();

    const vm = wrapper.vm;
    vm.editingTeam = {
      id: 3,
      name: 'PDA Tigers',
      age_groups: [{ id: 10 }],
      team_game_types: [],
    };
    vm.formData.name = 'PDA Tigers';
    vm.formData.gameTypeIds = [3]; // Friendly

    vi.clearAllMocks();
    await vm.updateTeam();

    // No call to the non-existent /game-types route.
    expect(callsMatching(u => u.includes('/game-types'))).toHaveLength(0);

    const [url, opts] = callsMatching(u =>
      u.endsWith('/api/teams/3/match-types')
    )[0];
    expect(url).toBe('http://localhost:8000/api/teams/3/match-types');
    expect(opts.method).toBe('POST');
    expect(JSON.parse(opts.body)).toEqual({
      match_type_id: 3,
      age_group_id: 10,
    });
  });

  it('removes deselected game types via DELETE on /match-types', async () => {
    const wrapper = mountTeams();
    await flushPromises();

    const vm = wrapper.vm;
    vm.editingTeam = {
      id: 3,
      name: 'PDA Tigers',
      age_groups: [{ id: 10 }],
      team_game_types: [{ game_type_id: 3 }],
    };
    vm.formData.name = 'PDA Tigers';
    vm.formData.gameTypeIds = []; // unchecked Friendly

    vi.clearAllMocks();
    await vm.updateTeam();

    expect(callsMatching(u => u.includes('/game-types'))).toHaveLength(0);

    const [url, opts] = callsMatching(u =>
      u.endsWith('/api/teams/3/match-types/3/10')
    )[0];
    expect(url).toBe('http://localhost:8000/api/teams/3/match-types/3/10');
    expect(opts.method).toBe('DELETE');
  });
});
