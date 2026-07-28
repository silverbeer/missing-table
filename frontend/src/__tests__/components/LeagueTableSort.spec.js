/**
 * LeagueTable.vue — sortable standings columns (SB-427).
 *
 * The table used to render in league order only, so answering "who scored the
 * most goals" meant reading every row. These cover the sort cycle, that league
 * position survives re-ordering, and that ties stay stable.
 *
 * apiRequest is routed by URL so the component's several mount-time fetches
 * (age groups, leagues, divisions, seasons) resolve without fighting the one
 * call we care about, /api/table.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import LeagueTable from '@/components/LeagueTable.vue';

let mockAuthStore;
vi.mock('@/stores/auth', () => ({ useAuthStore: () => mockAuthStore }));
vi.mock('@/config/api', () => ({
  getApiBaseUrl: () => 'http://localhost:8000',
}));

// Deliberately not in goal order: league position and GF disagree, which is the
// whole point of the feature.
const STANDINGS = [
  {
    team: 'Alpha',
    team_id: 1,
    played: 10,
    wins: 7,
    draws: 1,
    losses: 2,
    goals_for: 20,
    goals_against: 8,
    goal_difference: 12,
    points: 22,
    form: [],
  },
  {
    team: 'Bravo',
    team_id: 2,
    played: 10,
    wins: 6,
    draws: 2,
    losses: 2,
    goals_for: 31,
    goals_against: 14,
    goal_difference: 17,
    points: 20,
    form: [],
  },
  {
    team: 'Charlie',
    team_id: 3,
    played: 10,
    wins: 5,
    draws: 1,
    losses: 4,
    goals_for: 12,
    goals_against: 15,
    goal_difference: -3,
    points: 16,
    form: [],
  },
  // Same GF as Charlie — used to prove ties keep league order.
  {
    team: 'Delta',
    team_id: 4,
    played: 10,
    wins: 3,
    draws: 2,
    losses: 5,
    goals_for: 12,
    goals_against: 22,
    goal_difference: -10,
    points: 11,
    form: [],
  },
];

const mountTable = () => {
  mockAuthStore = {
    isAuthenticated: { value: false },
    userRole: { value: null },
    // The component reads these on mount (filterLeaguesByClub, team preselect).
    // Omitting them throws inside an un-awaited promise, which vitest reports as
    // an unhandled rejection and fails the run even with every test green.
    isAdmin: { value: false },
    userClubId: { value: null },
    userTeamId: { value: null },
    apiRequest: vi.fn(url => {
      if (url.includes('/api/table')) {
        return Promise.resolve({
          has_qop_data: false,
          qop_week_of: null,
          standings: STANDINGS.map(t => ({ ...t })),
        });
      }
      if (url.includes('/api/seasons')) {
        return Promise.resolve([
          {
            id: 1,
            name: '2026-2027',
            start_date: '2026-08-01',
            end_date: '2027-06-01',
          },
        ]);
      }
      if (url.includes('/api/age-groups'))
        return Promise.resolve([{ id: 1, name: 'U15' }]);
      if (url.includes('/api/divisions'))
        return Promise.resolve([{ id: 1, name: 'Northeast' }]);
      if (url.includes('/api/leagues'))
        return Promise.resolve([{ id: 1, name: 'MLS Next' }]);
      return Promise.resolve([]);
    }),
  };
  return mount(LeagueTable, {
    global: { stubs: { PlayoffBracket: true, ClubLogo: true } },
  });
};

const teamOrder = wrapper =>
  wrapper
    .findAll('[data-testid="standings-row"]')
    .map(r => r.text().match(/Alpha|Bravo|Charlie|Delta/)?.[0]);

describe('LeagueTable sorting', () => {
  beforeEach(() => vi.clearAllMocks());

  it('defaults to league position, unchanged from before the feature', async () => {
    const wrapper = mountTable();
    await flushPromises();
    expect(teamOrder(wrapper)).toEqual(['Alpha', 'Bravo', 'Charlie', 'Delta']);
  });

  it('sorts by goals for, highest first — the "who scored most" question', async () => {
    const wrapper = mountTable();
    await flushPromises();

    await wrapper.find('[data-testid="sort-goals-for"]').trigger('click');

    expect(teamOrder(wrapper)[0]).toBe('Bravo'); // 31 goals, 2nd in the table
  });

  it('reverses on a second click, then returns to league position on a third', async () => {
    const wrapper = mountTable();
    await flushPromises();
    const btn = () => wrapper.find('[data-testid="sort-goals-for"]');

    await btn().trigger('click');
    expect(teamOrder(wrapper)[0]).toBe('Bravo');

    await btn().trigger('click');
    expect(teamOrder(wrapper)[0]).toBe('Charlie'); // 12, tied but ahead in the table

    await btn().trigger('click');
    expect(teamOrder(wrapper)).toEqual(['Alpha', 'Bravo', 'Charlie', 'Delta']);
  });

  it('keeps league position in the rank column while sorted', async () => {
    const wrapper = mountTable();
    await flushPromises();

    await wrapper.find('[data-testid="sort-goals-for"]').trigger('click');

    // Bravo now renders first but is still 2nd in the league.
    const firstRow = wrapper.findAll('[data-testid="standings-row"]')[0];
    expect(firstRow.text()).toContain('Bravo');
    expect(firstRow.findAll('td')[0].text()).toBe('2');
  });

  it('breaks ties by league position so equal rows never shuffle', async () => {
    const wrapper = mountTable();
    await flushPromises();

    await wrapper.find('[data-testid="sort-goals-for"]').trigger('click');

    const order = teamOrder(wrapper);
    // Charlie and Delta both have 12; Charlie is higher in the table.
    expect(order.indexOf('Charlie')).toBeLessThan(order.indexOf('Delta'));
  });

  it('exposes sort state to screen readers via aria-sort', async () => {
    const wrapper = mountTable();
    await flushPromises();

    const header = () =>
      wrapper.find('[data-testid="sort-points"]').element.closest('th');
    expect(header().getAttribute('aria-sort')).toBe('none');

    await wrapper.find('[data-testid="sort-points"]').trigger('click');
    expect(header().getAttribute('aria-sort')).toBe('descending');

    await wrapper.find('[data-testid="sort-points"]').trigger('click');
    expect(header().getAttribute('aria-sort')).toBe('ascending');
  });
});
