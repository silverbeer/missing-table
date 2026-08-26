/**
 * LeagueTable.vue — competition selection and coverage (SB-835).
 *
 * The League selector already listed Flex and the division dropdown already
 * cascaded off it. What was missing is that /api/table was called without a
 * match_type, so it defaulted to League — and a Flex bracket holds no League
 * matches. Picking Flex rendered an empty table in production.
 *
 * These cover the three things that fixes it: the request carries a
 * competition, the competition is chosen from the data rather than from the
 * league's name, and a combined view says what it is.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import LeagueTable from '@/components/LeagueTable.vue';

let mockAuthStore;
vi.mock('@/stores/auth', () => ({ useAuthStore: () => mockAuthStore }));
vi.mock('@/config/api', () => ({
  getApiBaseUrl: () => 'http://localhost:8000',
}));

const STANDINGS = [
  {
    team: 'IFA',
    team_id: 11,
    played: 2,
    wins: 2,
    draws: 0,
    losses: 0,
    goals_for: 5,
    goals_against: 1,
    goal_difference: 4,
    points: 6,
    form: [],
  },
];

// Northeast: its own matches are League, and its teams also play Flex under a
// Flex bracket id. Both flagged as counting for qualification.
const NORTHEAST_COMPETITIONS = [
  {
    id: 1,
    name: 'League',
    counts_for_qualification: true,
    display_order: 1,
    matches: 190,
    played: 42,
    in_division: 190,
  },
  {
    id: 5,
    name: 'Flex',
    counts_for_qualification: true,
    display_order: 2,
    matches: 6,
    played: 1,
    in_division: 0,
  },
];

// A Flex bracket. Its own matches are Flex; no team's home division is ever a
// Flex bracket, which is why in_division is what identifies the owner.
const TURNPIKE_COMPETITIONS = [
  {
    id: 5,
    name: 'Flex',
    counts_for_qualification: true,
    display_order: 2,
    matches: 31,
    played: 4,
    in_division: 31,
  },
];

const DIVISIONS = [
  { id: 1, name: 'Northeast', league_id: 1 },
  { id: 309, name: 'Turnpike', league_id: 290 },
];

const mountTable = ({
  competitions = NORTHEAST_COMPETITIONS,
  coverage = null,
} = {}) => {
  const calls = [];
  mockAuthStore = {
    isAuthenticated: { value: false },
    userRole: { value: null },
    isAdmin: { value: false },
    userClubId: { value: null },
    userTeamId: { value: null },
    apiRequest: vi.fn(url => {
      calls.push(url);
      if (url.includes('/api/match-types/available')) {
        return Promise.resolve(
          typeof competitions === 'function'
            ? competitions(url)
            : competitions.map(c => ({ ...c }))
        );
      }
      if (url.includes('/api/table')) {
        return Promise.resolve({
          has_qop_data: false,
          qop_week_of: null,
          standings: STANDINGS.map(t => ({ ...t })),
          coverage,
        });
      }
      if (url.includes('/api/seasons'))
        return Promise.resolve([
          {
            id: 1,
            name: '2026-2027',
            start_date: '2026-08-01',
            end_date: '2027-06-01',
          },
        ]);
      if (url.includes('/api/age-groups'))
        return Promise.resolve([{ id: 1, name: 'U15' }]);
      if (url.includes('/api/divisions'))
        return Promise.resolve(DIVISIONS.map(d => ({ ...d })));
      if (url.includes('/api/leagues'))
        return Promise.resolve([
          { id: 1, name: 'Homegrown' },
          { id: 290, name: 'Flex' },
        ]);
      return Promise.resolve([]);
    }),
  };
  const wrapper = mount(LeagueTable, {
    global: { stubs: { PlayoffBracket: true, ClubLogo: true } },
  });
  return { wrapper, calls };
};

const tableCalls = calls => calls.filter(u => u.includes('/api/table'));

describe('LeagueTable competition selection', () => {
  beforeEach(() => vi.clearAllMocks());

  it('sends a match_type with the table request', async () => {
    // Omitting it let the API default to League — the whole bug.
    const { calls } = mountTable();
    await flushPromises();
    expect(tableCalls(calls).at(-1)).toContain('match_type=League');
  });

  it('asks which competitions this division plays before asking for the table', async () => {
    const { calls } = mountTable();
    await flushPromises();
    const available = calls.findIndex(u =>
      u.includes('/api/match-types/available')
    );
    const table = calls.findIndex(u => u.includes('/api/table'));
    expect(available).toBeGreaterThanOrEqual(0);
    expect(available).toBeLessThan(table);
  });

  it('opens on the competition the division owns, not on League', async () => {
    // Turnpike is a Flex bracket. `in_division` says so; nothing here maps a
    // league name to a competition.
    const { calls } = mountTable({ competitions: TURNPIKE_COMPETITIONS });
    await flushPromises();
    expect(tableCalls(calls).at(-1)).toContain('match_type=Flex');
  });

  it('renders one chip per competition present', async () => {
    const { wrapper } = mountTable();
    await flushPromises();
    expect(wrapper.find('[data-testid="competition-1"]').text()).toContain(
      'League'
    );
    expect(wrapper.find('[data-testid="competition-5"]').text()).toContain(
      'Flex'
    );
  });

  it('offers Qualifying when more than one qualifying competition is present', async () => {
    const { wrapper } = mountTable();
    await flushPromises();
    expect(
      wrapper.find('[data-testid="competition-qualifying"]').exists()
    ).toBe(true);
  });

  it('does not offer Qualifying when it would restate a single chip', async () => {
    const { wrapper } = mountTable({ competitions: TURNPIKE_COMPETITIONS });
    await flushPromises();
    expect(
      wrapper.find('[data-testid="competition-qualifying"]').exists()
    ).toBe(false);
  });

  it('shows no competition control at all when there is only one', async () => {
    const { wrapper } = mountTable({ competitions: TURNPIKE_COMPETITIONS });
    await flushPromises();
    expect(wrapper.find('[data-testid="competition-5"]').exists()).toBe(false);
  });

  it('refetches the table when a competition is picked', async () => {
    const { wrapper, calls } = mountTable();
    await flushPromises();

    await wrapper
      .find('[data-testid="competition-qualifying"]')
      .trigger('click');
    await flushPromises();

    expect(tableCalls(calls).at(-1)).toContain('match_type=qualifying');
  });

  it('picking a single competition asks for exactly that one', async () => {
    const { wrapper, calls } = mountTable();
    await flushPromises();
    await wrapper.find('[data-testid="competition-5"]').trigger('click');
    await flushPromises();
    expect(tableCalls(calls).at(-1)).toContain('match_type=Flex');
  });
});

describe('LeagueTable competition cascade', () => {
  beforeEach(() => vi.clearAllMocks());

  // Which competitions exist depends on the division, so changing division has
  // to re-ask and then reconcile the selection.
  const byDivision = url =>
    url.includes('division_id=309')
      ? TURNPIKE_COMPETITIONS.map(c => ({ ...c }))
      : NORTHEAST_COMPETITIONS.map(c => ({ ...c }));

  // The League selector is the way in: picking Flex narrows the Division
  // dropdown to the Flex brackets and auto-selects the first one. That cascade
  // already worked — what follows it is what did not.
  const switchToTurnpike = async wrapper => {
    const flex = wrapper
      .findAll('button')
      .find(b => b.text().trim() === 'Flex' && !b.attributes('data-testid'));
    await flex.trigger('click');
    await flushPromises();
  };

  it('re-reads the competitions when the division changes', async () => {
    const { wrapper, calls } = mountTable({ competitions: byDivision });
    await flushPromises();
    const before = calls.filter(u =>
      u.includes('/api/match-types/available')
    ).length;

    await switchToTurnpike(wrapper);

    expect(
      calls.filter(u => u.includes('/api/match-types/available')).length
    ).toBeGreaterThan(before);
  });

  it('falls back to the new division own competition when the old one is not played there', async () => {
    const { wrapper, calls } = mountTable({ competitions: byDivision });
    await flushPromises();
    expect(tableCalls(calls).at(-1)).toContain('match_type=League');

    // Turnpike plays no League. Leaving the filter on League is what rendered
    // an empty table.
    await switchToTurnpike(wrapper);

    expect(tableCalls(calls).at(-1)).toContain('match_type=Flex');
    expect(tableCalls(calls).at(-1)).not.toContain('match_type=League');
  });

  it('drops the Qualifying chip when the new division has only one competition', async () => {
    const { wrapper } = mountTable({ competitions: byDivision });
    await flushPromises();
    expect(
      wrapper.find('[data-testid="competition-qualifying"]').exists()
    ).toBe(true);

    await switchToTurnpike(wrapper);

    expect(
      wrapper.find('[data-testid="competition-qualifying"]').exists()
    ).toBe(false);
  });
});

describe('LeagueTable coverage caption', () => {
  beforeEach(() => vi.clearAllMocks());

  it('says so when the table counts matches against teams outside it', async () => {
    const { wrapper } = mountTable({
      coverage: {
        match_type: 'qualifying',
        competitions: ['Flex', 'League'],
        matches_counted: 25,
        matches_vs_outside_table: 6,
        teams_outside_table: 5,
      },
    });
    await flushPromises();

    const note = wrapper.find('[data-testid="coverage-note"]');
    expect(note.exists()).toBe(true);
    expect(note.text()).toContain('6 matches');
    expect(note.text()).toContain('5 teams outside this table');
    // The point of the caption: this is a record, not a standing.
    expect(note.text()).toContain('record, not a standing');
  });

  it('stays silent for a real standing', async () => {
    // Every match in a single-competition table was played inside it, so
    // there is nothing to disclose and a permanent caption would be noise.
    const { wrapper } = mountTable({
      coverage: {
        match_type: 'League',
        competitions: ['League'],
        matches_counted: 190,
        matches_vs_outside_table: 0,
        teams_outside_table: 0,
      },
    });
    await flushPromises();
    expect(wrapper.find('[data-testid="coverage-note"]').exists()).toBe(false);
  });

  it('is absent entirely when the API sends no coverage', async () => {
    const { wrapper } = mountTable({ coverage: null });
    await flushPromises();
    expect(wrapper.find('[data-testid="coverage-note"]').exists()).toBe(false);
  });

  it('uses singular wording for a single match and team', async () => {
    const { wrapper } = mountTable({
      coverage: {
        match_type: 'qualifying',
        competitions: ['Flex', 'League'],
        matches_counted: 20,
        matches_vs_outside_table: 1,
        teams_outside_table: 1,
      },
    });
    await flushPromises();
    const text = wrapper.find('[data-testid="coverage-note"]').text();
    expect(text).toContain('1 match against 1 team');
  });
});
