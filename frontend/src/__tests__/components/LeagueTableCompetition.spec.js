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
    has_standings: true,
    display_order: 1,
    matches: 190,
    played: 42,
    in_division: 190,
  },
  {
    id: 5,
    name: 'Flex',
    counts_for_qualification: true,
    has_standings: true,
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
    has_standings: true,
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

const LEAGUES = [
  { id: 1, name: 'Homegrown', display_order: 1 },
  { id: 290, name: 'Flex', display_order: 2 },
];

const mountTable = ({
  competitions = NORTHEAST_COMPETITIONS,
  coverage = null,
  divisions = DIVISIONS,
  leagues = LEAGUES,
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
      if (url.includes('/api/divisions/available')) {
        // Only the selected league's divisions that have fixtures (SB-1035).
        const leagueId = Number(new URL(url).searchParams.get('league_id'));
        return Promise.resolve(
          (typeof divisions === 'function' ? divisions(url) : divisions)
            .filter(d => d.league_id === leagueId)
            .map(d => ({ ...d }))
        );
      }
      if (url.includes('/api/leagues'))
        return Promise.resolve(leagues.map(l => ({ ...l })));
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

  it('explains shootout points when a counted competition scores them', async () => {
    // Flex has no draws: level after regulation goes to penalties, and the
    // shootout is worth points. Without this a reader sees 1W 2D = 7 and
    // concludes the table is wrong (SB-1027).
    const { wrapper } = mountTable({
      coverage: {
        match_type: 'Flex',
        competitions: ['Flex'],
        matches_counted: 31,
        matches_vs_outside_table: 0,
        teams_outside_table: 0,
        shootout_points: ['Flex'],
      },
    });
    await flushPromises();
    const note = wrapper.find('[data-testid="shootout-note"]');
    expect(note.exists()).toBe(true);
    expect(note.text()).toContain('Flex');
    expect(note.text()).toContain('winner 2');
    expect(note.text()).toContain('loser 1');
  });

  it('says nothing about shootouts in a League table', async () => {
    // A League draw is a draw. A permanent caption about penalties on a
    // table that never awards them would be noise.
    const { wrapper } = mountTable({
      coverage: {
        match_type: 'League',
        competitions: ['League'],
        matches_counted: 190,
        matches_vs_outside_table: 0,
        teams_outside_table: 0,
        shootout_points: [],
      },
    });
    await flushPromises();
    expect(wrapper.find('[data-testid="shootout-note"]').exists()).toBe(false);
  });

  it('survives an API that predates the shootout field', async () => {
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
    expect(wrapper.find('[data-testid="shootout-note"]').exists()).toBe(false);
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

describe('LeagueTable division dropdown', () => {
  beforeEach(() => vi.clearAllMocks());

  const optionNames = wrapper =>
    wrapper
      .find('[data-testid="division-filter"]')
      .findAll('option')
      .map(o => o.text());

  it('asks for the divisions with fixtures in this league, season and age group', async () => {
    const { calls } = mountTable();
    await flushPromises();
    const url = calls.find(u => u.includes('/api/divisions/available'));
    expect(url).toBeDefined();
    const params = new URL(url).searchParams;
    expect(params.get('league_id')).toBe('1');
    expect(params.get('season_id')).toBe('1');
    // The mock offers only U15 and the anonymous default is U14, so the
    // component keeps its initial age group; what matters is that it is sent.
    expect(params.get('age_group_id')).toBeTruthy();
    // The unfiltered list is never asked for.
    expect(calls.some(u => /\/api\/divisions(\?|$)/.test(u))).toBe(false);
  });

  it('offers only what the API offers', async () => {
    // 2026-2027 U15 Homegrown: the API returns Northeast alone — Florida and
    // the Pathway divisions have no fixtures and are not in the list.
    const { wrapper } = mountTable({
      divisions: [
        { id: 1, name: 'Northeast', league_id: 1, matches: 190, played: 42 },
        { id: 309, name: 'Turnpike', league_id: 290, matches: 31, played: 4 },
      ],
    });
    await flushPromises();
    expect(optionNames(wrapper)).toEqual(['Northeast']);
  });

  it('narrows to the new league and re-selects when the league changes', async () => {
    const { wrapper, calls } = mountTable();
    await flushPromises();
    expect(optionNames(wrapper)).toEqual(['Northeast']);

    const flex = wrapper
      .findAll('button')
      .find(b => b.text().trim() === 'Flex' && !b.attributes('data-testid'));
    await flex.trigger('click');
    await flushPromises();

    expect(optionNames(wrapper)).toEqual(['Turnpike']);
    expect(tableCalls(calls).at(-1)).toContain('division_id=309');
  });

  it('keeps the current division when it is still offered', async () => {
    const { wrapper, calls } = mountTable({
      divisions: [
        { id: 1, name: 'Northeast', league_id: 1, matches: 190, played: 42 },
        { id: 8, name: 'Florida', league_id: 1, matches: 12, played: 0 },
        { id: 309, name: 'Turnpike', league_id: 290, matches: 31, played: 4 },
      ],
    });
    await flushPromises();
    wrapper.vm.selectedDivisionId = 8;
    await flushPromises();
    expect(tableCalls(calls).at(-1)).toContain('division_id=8');

    // An age-group change re-reads the list; Florida is still in it, so the
    // viewer stays where they were.
    const before = calls.filter(u =>
      u.includes('/api/divisions/available')
    ).length;
    wrapper.vm.selectedAgeGroupId = 1;
    await flushPromises();
    expect(
      calls.filter(u => u.includes('/api/divisions/available')).length
    ).toBeGreaterThan(before);
    expect(wrapper.vm.selectedDivisionId).toBe(8);
    expect(tableCalls(calls).at(-1)).toContain('division_id=8');
  });

  it('moves off a division that is no longer offered', async () => {
    // Florida has U15 fixtures and none at U16: on the age-group change the
    // API stops offering it, and the selection falls back to Northeast rather
    // than pointing at a blank table.
    const byAge = url =>
      url.includes('age_group_id=1')
        ? [
            { id: 1, name: 'Northeast', league_id: 1, matches: 190, played: 0 },
            { id: 8, name: 'Florida', league_id: 1, matches: 12, played: 0 },
          ]
        : [{ id: 1, name: 'Northeast', league_id: 1, matches: 200, played: 0 }];
    const { wrapper, calls } = mountTable({ divisions: byAge });
    await flushPromises();
    wrapper.vm.selectedAgeGroupId = 1;
    await flushPromises();
    wrapper.vm.selectedDivisionId = 8;
    await flushPromises();
    expect(tableCalls(calls).at(-1)).toContain('division_id=8');

    wrapper.vm.selectedAgeGroupId = 2;
    await flushPromises();
    expect(wrapper.vm.selectedDivisionId).toBe(1);
    expect(tableCalls(calls).at(-1)).toContain('division_id=1');
  });
});

describe('LeagueTable league order', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders the leagues in the order the API sends them', async () => {
    // display_order lives on the row (SB-1035). Alphabetical would put
    // Academy first and Homegrown third.
    const { wrapper } = mountTable({
      leagues: [
        { id: 1, name: 'Homegrown', display_order: 1 },
        { id: 290, name: 'Flex', display_order: 2 },
        { id: 2, name: 'Academy', display_order: 3 },
        { id: 90, name: 'TSC League 1', display_order: null },
      ],
    });
    await flushPromises();
    const chips = wrapper
      .findAll('button')
      .map(b => b.text().trim())
      .filter(t =>
        ['Homegrown', 'Flex', 'Academy', 'TSC League 1'].includes(t)
      );
    // The competition row also has a Flex chip; the league row comes first.
    expect(chips.slice(0, 4)).toEqual([
      'Homegrown',
      'Flex',
      'Academy',
      'TSC League 1',
    ]);
  });
});

describe('LeagueTable competition row offers only competitions with a table', () => {
  beforeEach(() => vi.clearAllMocks());

  const WITH_EXTRAS = [
    ...NORTHEAST_COMPETITIONS,
    {
      id: 2,
      name: 'Tournament',
      counts_for_qualification: false,
      has_standings: false,
      display_order: 3,
      matches: 12,
      played: 8,
      in_division: 0,
    },
    {
      id: 3,
      name: 'Friendly',
      counts_for_qualification: false,
      has_standings: false,
      display_order: 4,
      matches: 4,
      played: 4,
      in_division: 0,
    },
  ];

  const chipLabels = wrapper =>
    wrapper
      .findAll('button[data-testid^="competition-"]')
      .map(b => b.text().trim());

  it('hides Tournament and Friendly even though they are played here', async () => {
    // A friendly table is nonsense and a tournament table across every
    // tournament in a division is meaningless — the Tournaments tab has the
    // real ones (SB-1037).
    const { wrapper } = mountTable({ competitions: WITH_EXTRAS });
    await flushPromises();
    expect(chipLabels(wrapper)).toEqual(['League', 'Flex', 'League + Flex']);
  });

  it('labels the combined chip with what it combines', async () => {
    const { wrapper } = mountTable();
    await flushPromises();
    const chip = wrapper.find('[data-testid="competition-qualifying"]');
    expect(chip.text()).toBe('League + Flex');
    expect(chip.attributes('title')).toContain('League + Flex');
    expect(chip.attributes('title')).toContain('not a standing');
    // The value the API understands is unchanged.
    await chip.trigger('click');
    await flushPromises();
  });

  it('still offers everything when the API predates the flag', async () => {
    // has_standings absent, not false. Hiding every competition on a missing
    // field would be the worse failure.
    const legacy = WITH_EXTRAS.map(c => {
      const copy = { ...c };
      delete copy.has_standings;
      return copy;
    });
    const { wrapper } = mountTable({ competitions: legacy });
    await flushPromises();
    expect(chipLabels(wrapper)).toEqual([
      'League',
      'Flex',
      'League + Flex',
      'Tournament',
      'Friendly',
    ]);
  });
});
