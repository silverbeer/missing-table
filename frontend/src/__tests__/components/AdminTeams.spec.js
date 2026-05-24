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
