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

// Per-test participation rows returned by GET /api/teams/{id}/match-types.
let participationRows = [];

// On mount AdminTeams loads teams + age-groups/clubs/divisions/leagues/match-types/seasons.
const byUrl = (url, opts) => {
  const method = (opts && opts.method) || 'GET';
  // GET /api/teams/{id}/match-types → current per-age participation.
  if (url.endsWith('/match-types') && method === 'GET') {
    return Promise.resolve(participationRows);
  }
  if (url.includes('/api/teams'))
    return Promise.resolve(TEAMS.map(t => ({ ...t })));
  return Promise.resolve([]);
};

const mountTeams = () => {
  participationRows = [];
  mockAuthStore = {
    userRole: { value: 'admin' },
    userClubId: { value: null },
    apiRequest: vi.fn((url, opts) => byUrl(url, opts)),
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

// Per-age-group match-type participation matrix (SB-362). Each cell is one
// (match_type, age_group) pair, editable independently. Regression guards:
// (1) the correct /match-types route + match_type_id field (never /game-types),
// (2) toggling one age group must not touch the others.
describe('AdminTeams match-type participation matrix', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const callsMatching = pred =>
    mockAuthStore.apiRequest.mock.calls.filter(([url]) => pred(url));

  // U15 = id 10, U14 = id 11. Friendly = 3.
  const TEAM = {
    id: 3,
    name: 'IFA',
    club_id: null,
    academy_team: false,
    age_groups: [
      { id: 10, name: 'U15' },
      { id: 11, name: 'U14' },
    ],
  };

  it('loads current participation into the matrix on edit', async () => {
    const wrapper = mountTeams();
    await flushPromises();

    participationRows = [{ match_type_id: 3, age_group_id: 11 }]; // Friendly @ U14

    await wrapper.vm.editTeam({ ...TEAM });
    await flushPromises();

    expect(wrapper.vm.hasParticipation(3, 11)).toBe(true); // U14 on
    expect(wrapper.vm.hasParticipation(3, 10)).toBe(false); // U15 off
  });

  it('adds Friendly for U15 only, via POST /match-types with match_type_id', async () => {
    const wrapper = mountTeams();
    await flushPromises();

    participationRows = [{ match_type_id: 3, age_group_id: 11 }]; // Friendly @ U14
    await wrapper.vm.editTeam({ ...TEAM });
    await flushPromises();

    wrapper.vm.toggleParticipation(3, 10); // enable Friendly @ U15

    vi.clearAllMocks();
    await wrapper.vm.updateTeam();

    // Never hits the old non-existent route.
    expect(callsMatching(u => u.includes('/game-types'))).toHaveLength(0);

    // Exactly one add, for U15 — U14 (unchanged) is untouched.
    const posts = callsMatching(u =>
      u.endsWith('/api/teams/3/match-types')
    ).filter(([, opts]) => opts?.method === 'POST');
    expect(posts).toHaveLength(1);
    expect(JSON.parse(posts[0][1].body)).toEqual({
      match_type_id: 3,
      age_group_id: 10,
    });
    // No deletes.
    expect(callsMatching(u => /\/match-types\/\d+\/\d+$/.test(u))).toHaveLength(
      0
    );
  });

  it('removes Friendly from one age group via DELETE /match-types/{mt}/{ag}', async () => {
    const wrapper = mountTeams();
    await flushPromises();

    participationRows = [
      { match_type_id: 3, age_group_id: 10 },
      { match_type_id: 3, age_group_id: 11 },
    ];
    await wrapper.vm.editTeam({ ...TEAM });
    await flushPromises();

    wrapper.vm.toggleParticipation(3, 10); // disable Friendly @ U15

    vi.clearAllMocks();
    await wrapper.vm.updateTeam();

    const [url, opts] = callsMatching(u =>
      u.endsWith('/api/teams/3/match-types/3/10')
    )[0];
    expect(url).toBe('http://localhost:8000/api/teams/3/match-types/3/10');
    expect(opts.method).toBe('DELETE');

    // U14 untouched: no POST/DELETE referencing age group 11.
    expect(callsMatching(u => u.endsWith('/3/11'))).toHaveLength(0);
    const posts = callsMatching(u =>
      u.endsWith('/api/teams/3/match-types')
    ).filter(([, o]) => o?.method === 'POST');
    expect(posts).toHaveLength(0);
  });

  it('makes no participation calls when nothing changed', async () => {
    const wrapper = mountTeams();
    await flushPromises();

    participationRows = [{ match_type_id: 3, age_group_id: 10 }];
    await wrapper.vm.editTeam({ ...TEAM });
    await flushPromises();

    vi.clearAllMocks();
    await wrapper.vm.updateTeam();

    // Only the team PUT, no add/remove.
    expect(callsMatching(u => u.includes('/match-types'))).toHaveLength(0);
  });
});
