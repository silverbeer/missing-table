/**
 * PowerRatingPanel (SB-1809): the Ranking tab's Power Rating list over
 * GET /api/rankings (SB-1808).
 *
 * What these guard: the national list sits under tier headers and never
 * interleaves teams outside the main island; a run that is not comparable
 * nationally shows one list per conference with the reason; movement that was
 * not measured renders nothing (never "▲0"); teams under 6 matches are listed
 * apart as "4 of 6 matches"; no run is an empty state, a failure is an error
 * with Retry; and the copy says matches, never games.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { flushPromises, mount } from '@vue/test-utils';
import {
  formatDelta,
  formatMover,
  formatMovement,
  formatRating,
  formatSos,
  groupByTier,
  ordinal,
  sparkline,
} from '@/utils/powerRating';

const apiRequest = vi.fn();
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    apiRequest,
    isAuthenticated: { value: false },
    state: {},
  }),
}));
vi.mock('@/config/api', () => ({
  getApiBaseUrl: () => 'http://localhost:8000',
}));

import PowerRatingPanel from '@/components/ranking/PowerRatingPanel.vue';

const TIERS = [
  { key: 'elite', label: 'Elite', min: 1700 },
  { key: 'contender', label: 'Contender', min: 1600 },
  { key: 'above_average', label: 'Above average', min: 1500 },
];

const NOTE =
  'MT Power Rating from 5 Homegrown U17 teams in MT, rated on 40 matches; 4 with 6 or more matches are ranked. Conferences meet only at Flex and national events.';

const team = (over = {}) => ({
  rank: 1,
  team_id: 21,
  team: 'IFA U17',
  club_id: 5,
  club_logo_url: null,
  rating: 1754,
  rank_change_7d: 2,
  rating_change_7d: 12,
  w: 10,
  d: 1,
  l: 1,
  mp: 12,
  conference: 'Northeast',
  conference_rank: 1,
  tier: 'elite',
  badges: [],
  xconf_mp: 4,
  pro_academy: false,
  comparable_nationally: true,
  ...over,
});

const national = (over = {}) => ({
  league: 'Homegrown',
  age_group: 'U17',
  season: '2026-2027',
  view: 'national',
  conference: null,
  conferences: ['Mid-Atlantic', 'Northeast'],
  run: {
    id: 412,
    computed_at: '2026-12-15T10:00:04Z',
    through_date: '2026-12-14',
    matches_counted: 40,
    params_version: 'elo-v1',
  },
  movement_since: { run_id: 400, computed_at: '2026-12-08T10:00:00Z' },
  publication: { national: true, reason: null },
  coverage: {
    teams_in_pool: 5,
    ranked: 4,
    unranked_count: 1,
    matches_counted: 40,
    matches_excluded: {},
    min_matches: 6,
    note: NOTE,
  },
  tiers: TIERS,
  teams: [
    team(),
    team({
      rank: 2,
      team_id: 22,
      team: 'NEFC U17',
      rating: 1642,
      rank_change_7d: -1,
      rating_change_7d: -8,
      conference_rank: 2,
      tier: 'contender',
      badges: ['provisional', 'low_cross_conference'],
      pro_academy: true,
      mp: 7,
      w: 4,
      d: 2,
      l: 1,
    }),
    team({
      rank: 3,
      team_id: 23,
      team: 'Low Club U17',
      rating: 1410,
      rank_change_7d: null,
      rating_change_7d: null,
      conference: 'Mid-Atlantic',
      conference_rank: 1,
      tier: null,
    }),
    team({
      rank: null,
      team_id: 24,
      team: 'Island FC U17',
      rating: 1580,
      tier: null,
      conference: 'Mid-Atlantic',
      conference_rank: 2,
      comparable_nationally: false,
    }),
  ],
  unranked: [
    {
      team_id: 77,
      team: 'Late Starters',
      conference: 'Northeast',
      mp: 4,
      needed: 6,
    },
  ],
  reason: null,
  error: null,
  ...over,
});

const conferenceView = (over = {}) =>
  national({
    age_group: 'U15',
    view: 'conference',
    publication: {
      national: false,
      reason: 'U15 has 8 separate groups of conferences that have not met.',
    },
    tiers: [],
    teams: [
      team({
        rank: null,
        team_id: 31,
        team: 'Mid One',
        conference: 'Mid-Atlantic',
        conference_rank: 1,
        tier: null,
        comparable_nationally: false,
      }),
      team({
        rank: null,
        team_id: 32,
        team: 'NE One',
        conference: 'Northeast',
        conference_rank: 1,
        tier: null,
        comparable_nationally: false,
      }),
      team({
        rank: null,
        team_id: 33,
        team: 'NE Two',
        conference: 'Northeast',
        conference_rank: 2,
        tier: null,
        comparable_nationally: false,
      }),
    ],
    ...over,
  });

const noRun = () => ({
  league: 'Homegrown',
  age_group: 'U15',
  season: '2026-2027',
  view: null,
  conferences: [],
  run: null,
  publication: { national: false, reason: 'No Power Rating yet.' },
  coverage: null,
  tiers: [],
  teams: [],
  unranked: [],
  reason:
    'No Power Rating has been computed for Homegrown U15 in 2026-2027 yet.',
  error: null,
});

// GET /api/rankings/teams/{id} (SB-1808 build_team) for IFA U17.
const mover = (over = {}) => ({
  match_id: 901,
  match_date: '2026-11-02',
  opponent_id: 22,
  opponent: 'NEFC U17',
  result: 'W',
  goals_for: 3,
  goals_against: 0,
  penalties_for: null,
  penalties_against: null,
  expected: 0.41,
  delta: 24.4,
  ...over,
});

const teamWhy = (over = {}) => ({
  league: 'Homegrown',
  age_group: 'U17',
  season: '2026-2027',
  team_id: 21,
  team: 'IFA U17',
  club_id: 5,
  club_logo_url: null,
  pro_academy: false,
  run: national().run,
  in_run: true,
  rating: 1754,
  rank: 1,
  conference: 'Northeast',
  conference_rank: 1,
  tier: 'elite',
  badges: [],
  ranked: true,
  needed: null,
  mp: 12,
  w: 10,
  d: 1,
  l: 1,
  xconf_mp: 4,
  sos: { rating: 1538, rank: 12, of: 147, scope: 'national' },
  biggest_movers: [
    mover(),
    mover({
      match_id: 902,
      match_date: '2026-11-09',
      opponent_id: 23,
      opponent: 'Low Club U17',
      result: 'L',
      goals_for: 1,
      goals_against: 4,
      expected: 0.78,
      delta: -57.2,
    }),
    mover({
      match_id: 903,
      match_date: '2026-11-16',
      opponent_id: 24,
      opponent: 'Island FC U17',
      result: 'D',
      goals_for: 1,
      goals_against: 1,
      expected: 0.55,
      delta: -3.1,
    }),
  ],
  deltas: [],
  history: [
    { run_id: 380, computed_at: '2026-09-07T10:00:00Z', rating: 1500 },
    { run_id: 395, computed_at: '2026-10-05T10:00:00Z', rating: 1688 },
    { run_id: 412, computed_at: '2026-12-15T10:00:04Z', rating: 1754 },
  ],
  reason: null,
  error: null,
  ...over,
});

const LOOKUPS = {
  '/api/age-groups': [
    { id: 3, name: 'U15' },
    { id: 5, name: 'U17' },
  ],
  '/api/leagues': [{ id: 1, name: 'Homegrown' }],
  '/api/seasons': [{ id: 184, name: '2026-2027' }],
};

const routeApi = (
  rankings = () => Promise.resolve(national()),
  teamAnswer = () => Promise.resolve(teamWhy())
) => {
  apiRequest.mockImplementation(url => {
    if (url.includes('/api/rankings/teams/')) return teamAnswer(url);
    if (url.includes('/api/rankings')) return rankings(url);
    const path = Object.keys(LOOKUPS).find(p => url.endsWith(p));
    return Promise.resolve(path ? LOOKUPS[path] : []);
  });
};

const mountPanel = async () => {
  const wrapper = mount(PowerRatingPanel);
  await flushPromises();
  return wrapper;
};

const rankingCalls = () =>
  apiRequest.mock.calls
    .map(c => c[0])
    .filter(u => u.includes('/api/rankings') && !u.includes('/teams/'));

const teamCalls = () =>
  apiRequest.mock.calls
    .map(c => c[0])
    .filter(u => u.includes('/api/rankings/teams/'));

describe('Power Rating formatting (SB-1809)', () => {
  it('formats a rating with a thousands separator, and keeps null absent', () => {
    expect(formatRating(1642)).toBe('1,642');
    expect(formatRating(987)).toBe('987');
    expect(formatRating(null)).toBeNull();
  });

  it('writes ordinals, teens included', () => {
    expect([1, 2, 3, 4, 11, 12, 13, 21, 22, 111].map(ordinal)).toEqual([
      '1st',
      '2nd',
      '3rd',
      '4th',
      '11th',
      '12th',
      '13th',
      '21st',
      '22nd',
      '111th',
    ]);
  });

  it('formats movement up and down, and absent as nothing or New', () => {
    const since = { run_id: 1 };
    expect(formatMovement(2, 12, since)).toEqual({
      text: '▲2 · +12',
      direction: 'up',
    });
    expect(formatMovement(-1, -8, since)).toEqual({
      text: '▼1 · −8',
      direction: 'down',
    });
    // No run a week before: nothing at all.
    expect(formatMovement(null, null, null)).toBeNull();
    // A run a week before that did not have the team: new, not zero.
    expect(formatMovement(null, null, since)).toEqual({
      text: 'New',
      direction: 'new',
    });
    // A held place drops the arrow: never "▲0".
    expect(formatMovement(0, 5, since).text).toBe('+5');
    expect(formatMovement(0, 0, since).text).toBe('±0');
  });

  it('groups by tier in order, then Others, then teams apart from the island', () => {
    const groups = groupByTier(national().teams, TIERS);
    expect(groups.map(g => [g.key, g.rows.map(r => r.team_id)])).toEqual([
      ['elite', [21]],
      ['contender', [22]],
      ['others', [23]],
      ['not_comparable', [24]],
    ]);
    expect(groups[0].hint).toBe('1,700+');
    expect(groups[2].hint).toBe('below 1,500');
  });
});

describe('PowerRatingPanel (SB-1809)', () => {
  beforeEach(() => {
    apiRequest.mockReset();
  });

  it('asks for Homegrown U15 and lets the API pick the view', async () => {
    routeApi();
    await mountPanel();
    const [url] = rankingCalls();
    const params = new URL(url).searchParams;
    expect(params.get('league')).toBe('Homegrown');
    expect(params.get('age_group')).toBe('U15');
    expect(params.has('view')).toBe(false);
  });

  it('leads with the update date and the coverage note', async () => {
    routeApi();
    const w = await mountPanel();
    expect(w.get('[data-testid="pr-updated"]').text()).toBe(
      'Updated Dec 15, 2026'
    );
    expect(w.get('[data-testid="pr-coverage-note"]').text()).toBe(NOTE);
  });

  it('groups the national view under tier headers with their cut-offs', async () => {
    routeApi();
    const w = await mountPanel();
    const headers = w
      .findAll('[data-testid="pr-tier-header"]')
      .map(h => h.text());
    expect(headers).toEqual([
      'Elite · 1,700+',
      'Contender · 1,600+',
      'Others · below 1,500',
      'Not yet comparable nationally · shown with their conference',
    ]);
    const elite = w.get('[data-testid="pr-tier-elite"]');
    expect(elite.get('[data-testid="pr-team"]').text()).toBe('IFA U17');
    // Outside the island: no national rank, never placed in the order.
    const apart = w.get('[data-testid="pr-tier-not_comparable"]');
    expect(apart.get('[data-testid="pr-rank"]').text()).toBe('—');
  });

  it('renders a row: rank, conference place, MP and record, rating, movement', async () => {
    routeApi();
    const w = await mountPanel();
    const rows = w.findAll('[data-testid="pr-row"]');
    const first = rows[0];
    expect(first.get('[data-testid="pr-rank"]').text()).toBe('1');
    expect(first.get('[data-testid="pr-conference"]').text()).toBe(
      'Northeast · 1st'
    );
    expect(first.get('[data-testid="pr-record"]').text()).toBe(
      '· MP 12 · 10-1-1'
    );
    expect(first.get('[data-testid="pr-rating"]').text()).toBe('1,754');
    expect(first.get('[data-testid="pr-movement"]').text()).toBe('▲2 · +12');

    const second = rows[1];
    expect(second.get('[data-testid="pr-rating"]').text()).toBe('1,642');
    expect(second.get('[data-testid="pr-movement"]').text()).toBe('▼1 · −8');
  });

  it('shows "New" for a team the earlier run did not have, and nothing without an earlier run', async () => {
    routeApi();
    const w = await mountPanel();
    const low = w.findAll('[data-testid="pr-row"]')[2];
    expect(low.get('[data-testid="pr-movement"]').text()).toBe('New');

    routeApi(() =>
      Promise.resolve(
        national({
          movement_since: null,
          teams: national().teams.map(t => ({
            ...t,
            rank_change_7d: null,
            rating_change_7d: null,
          })),
        })
      )
    );
    const fresh = await mountPanel();
    expect(fresh.find('[data-testid="pr-movement"]').exists()).toBe(false);
    expect(fresh.text()).not.toMatch(/▲0|▼0/);
  });

  it('shows badges as short chips with the full rule in the title', async () => {
    routeApi();
    const w = await mountPanel();
    const row = w.findAll('[data-testid="pr-row"]')[1];
    expect(row.get('[data-testid="pr-badge-provisional"]').text()).toBe(
      'Provisional'
    );
    const low = row.get('[data-testid="pr-badge-low_cross_conference"]');
    expect(low.attributes('title')).toContain('Low cross-conference data');
    expect(row.get('[data-testid="pr-badge-pro_academy"]').text()).toBe(
      'Pro academy'
    );
    const first = w.findAll('[data-testid="pr-row"]')[0];
    expect(first.find('[data-testid="pr-badges"]').exists()).toBe(false);
  });

  it('lists unranked teams apart as "4 of 6 matches"', async () => {
    routeApi();
    const w = await mountPanel();
    const rows = w.findAll('[data-testid="pr-unranked-row"]');
    expect(rows).toHaveLength(1);
    expect(rows[0].text()).toContain('Late Starters');
    expect(rows[0].text()).toContain('4 of 6 matches');
    expect(w.get('[data-testid="pr-unranked"]').text()).toContain(
      'under 6 matches'
    );
  });

  it('shows one tab per conference with the reason when not comparable nationally', async () => {
    routeApi(() => Promise.resolve(conferenceView()));
    const w = await mountPanel();
    expect(w.find('[data-testid="pr-tier-header"]').exists()).toBe(false);
    expect(w.find('[data-testid="pr-view-filter"]').exists()).toBe(false);
    const tabs = w.findAll('[data-testid="pr-conference-tab"]');
    expect(tabs.map(t => t.text())).toEqual(['Mid-Atlantic', 'Northeast']);
    expect(w.get('[data-testid="pr-publication-reason"]').text()).toBe(
      'Not yet comparable nationally: U15 has 8 separate groups of conferences that have not met.'
    );
    // First conference by default.
    expect(w.findAll('[data-testid="pr-team"]').map(t => t.text())).toEqual([
      'Mid One',
    ]);
    // The unranked Northeast team is not listed under Mid-Atlantic.
    expect(w.find('[data-testid="pr-unranked"]').exists()).toBe(false);

    await tabs[1].trigger('click');
    expect(w.findAll('[data-testid="pr-team"]').map(t => t.text())).toEqual([
      'NE One',
      'NE Two',
    ]);
    expect(w.findAll('[data-testid="pr-rank"]').map(r => r.text())).toEqual([
      '1',
      '2',
    ]);
    expect(w.get('[data-testid="pr-unranked"]').text()).toContain(
      'Late Starters'
    );
  });

  it('offers National and By conference on a national run, and asks for the one picked', async () => {
    routeApi(url =>
      Promise.resolve(
        url.includes('view=conference')
          ? conferenceView({ publication: { national: true, reason: null } })
          : national()
      )
    );
    const w = await mountPanel();
    await w.get('[data-testid="pr-view-conference"]').trigger('click');
    await flushPromises();
    expect(rankingCalls().at(-1)).toContain('view=conference');
    expect(w.find('[data-testid="pr-conference-tabs"]').exists()).toBe(true);
    // Chosen, not forced: no "not comparable" line.
    expect(w.find('[data-testid="pr-publication-reason"]').exists()).toBe(
      false
    );
  });

  it('shows the API reason for an age group with no run, not an error', async () => {
    routeApi(() => Promise.resolve(noRun()));
    const w = await mountPanel();
    expect(w.find('[data-testid="pr-error"]').exists()).toBe(false);
    expect(w.get('[data-testid="pr-empty"]').text()).toContain(
      'No Power Rating yet'
    );
    expect(w.get('[data-testid="pr-empty-reason"]').text()).toBe(
      noRun().reason
    );
  });

  it('shows the API detail on failure, and Retry asks again', async () => {
    let fail = true;
    routeApi(() =>
      fail
        ? Promise.reject(new Error('The Power Rating is unavailable right now'))
        : Promise.resolve(national())
    );
    const w = await mountPanel();
    expect(w.get('[data-testid="pr-error"]').text()).toContain(
      'The Power Rating is unavailable right now'
    );
    fail = false;
    await w.get('[data-testid="pr-retry"]').trigger('click');
    await flushPromises();
    expect(w.find('[data-testid="pr-error"]').exists()).toBe(false);
    expect(w.findAll('[data-testid="pr-row"]').length).toBeGreaterThan(0);
  });

  it('refetches with age_group=U17 when the age group changes', async () => {
    routeApi();
    const w = await mountPanel();
    await w.get('[data-testid="pr-age-group-U17"]').trigger('click');
    await flushPromises();
    expect(rankingCalls().at(-1)).toContain('age_group=U17');
  });

  it('drops a stale answer that lands after a newer one', async () => {
    let resolveFirst;
    let call = 0;
    routeApi(() => {
      call += 1;
      if (call === 1) return new Promise(r => (resolveFirst = r));
      return Promise.resolve(national());
    });
    const w = mount(PowerRatingPanel);
    await w.get('[data-testid="pr-age-group-U17"]').trigger('click');
    await flushPromises();
    resolveFirst(noRun());
    await flushPromises();
    expect(w.find('[data-testid="pr-empty"]').exists()).toBe(false);
    expect(w.findAll('[data-testid="pr-row"]').length).toBeGreaterThan(0);
  });

  it('says matches, never games', async () => {
    routeApi();
    const w = await mountPanel();
    expect(w.text()).toMatch(/matches/);
    expect(w.text()).not.toMatch(/\bgames?\b/i);

    routeApi(() => Promise.resolve(conferenceView()));
    const c = await mountPanel();
    expect(c.text()).not.toMatch(/\bgames?\b/i);
  });

  it('opens Matches on the team with the ids LeaderboardsPanel sends', async () => {
    routeApi();
    const w = await mountPanel();
    await w.findAll('[data-testid="pr-row"]')[0].trigger('click');
    await flushPromises();
    // The row opens the why panel first (SB-1810); View matches navigates.
    expect(w.emitted('navigate-to-team')).toBeUndefined();
    await w.find('[data-testid="pr-why-view-matches"]').trigger('click');
    expect(w.emitted('navigate-to-team')).toEqual([
      [
        {
          teamId: 21,
          clubId: 5,
          ageGroupId: 5,
          leagueId: 1,
          divisionId: null,
          seasonId: 184,
        },
      ],
    ]);
  });
});

/**
 * The team's "why" panel (SB-1810), inline under its row, over
 * GET /api/rankings/teams/{id}. What these guard: one panel at a time; the
 * movers read as results with signed changes and the expected share of the
 * points; a shoot-out keeps its regulation score and says it was rated as a
 * draw; strength of schedule never states a rank without its denominator;
 * the sparkline needs 2 points; and a team with no rated match is an answer.
 */
describe('Power Rating why-panel formatting (SB-1810)', () => {
  it('signs deltas in whole points, with a real minus and ±0', () => {
    expect(formatDelta(24.4)).toBe('+24');
    expect(formatDelta(-57.2)).toBe('−57');
    expect(formatDelta(0.3)).toBe('±0');
    expect(formatDelta(null)).toBeNull();
  });

  it('writes a win, a loss and a draw from the team side', () => {
    expect(formatMover(mover())).toMatchObject({
      headline: 'Beat NEFC U17 3–0',
      delta: '+24',
      direction: 'up',
      detail: 'Nov 2 · expected to take 41% of the points',
    });
    expect(
      formatMover(
        mover({ result: 'L', goals_for: 1, goals_against: 4, delta: -57 })
      )
    ).toMatchObject({ headline: 'Lost to NEFC U17 1–4', delta: '−57' });
    expect(
      formatMover(mover({ result: 'D', goals_for: 1, goals_against: 1 }))
        .headline
    ).toBe('Drew with NEFC U17 1–1');
  });

  it('keeps the regulation score of a shoot-out and says it was rated a draw', () => {
    const m = formatMover(
      mover({
        result: 'D',
        goals_for: 2,
        goals_against: 2,
        penalties_for: 4,
        penalties_against: 3,
        delta: 2,
      })
    );
    expect(m.headline).toBe('Drew with NEFC U17 2–2');
    expect(m.detail).toContain('Won 4–3 on penalties, rated as a draw');
  });

  it('leaves out a score the match row no longer has, never 0–0', () => {
    const m = formatMover(
      mover({ match_date: null, goals_for: null, goals_against: null })
    );
    expect(m.headline).toBe('Beat NEFC U17');
    expect(m.detail).toBe('expected to take 41% of the points');
  });

  it('states SOS with its denominator, or the average alone', () => {
    expect(formatSos({ rating: 1538, rank: 12, of: 147 })).toBe(
      'Average opponent 1,538 — 12th toughest of 147'
    );
    expect(
      formatSos(
        { rating: 1490, rank: 3, of: 14, scope: 'conference' },
        'Northeast'
      )
    ).toBe('Average opponent 1,490 — 3rd toughest of 14 in Northeast');
    expect(formatSos({ rating: 1538, rank: null })).toBe(
      'Average opponent 1,538'
    );
    expect(formatSos(null)).toBeNull();
  });

  it('draws a sparkline from 2 points, not from 1', () => {
    expect(sparkline([{ rating: 1500 }])).toBeNull();
    const s = sparkline([{ rating: 1500 }, { rating: 1600 }], 200, 40, 0);
    expect(s.points).toBe('0,40 200,0');
  });
});

describe('PowerRatingPanel why panel (SB-1810)', () => {
  beforeEach(() => {
    apiRequest.mockReset();
  });

  const openFirst = async (team = () => Promise.resolve(teamWhy())) => {
    routeApi(undefined, team);
    const w = await mountPanel();
    await w.findAll('[data-testid="pr-row"]')[0].trigger('click');
    await flushPromises();
    return w;
  };

  it('opens under the tapped row and closes on a second tap', async () => {
    const w = await openFirst();
    const row = w.findAll('[data-testid="pr-row"]')[0];
    expect(row.attributes('aria-expanded')).toBe('true');
    expect(w.findAll('[data-testid="pr-why"]')).toHaveLength(1);
    expect(row.attributes('aria-controls')).toBe(
      w.find('[data-testid="pr-why"]').attributes('id')
    );
    await row.trigger('click');
    expect(w.find('[data-testid="pr-why"]').exists()).toBe(false);
    expect(row.attributes('aria-expanded')).toBe('false');
  });

  it('keeps one panel open at a time', async () => {
    const w = await openFirst();
    await w.findAll('[data-testid="pr-row"]')[1].trigger('click');
    await flushPromises();
    const panels = w.findAll('[data-testid="pr-why"]');
    expect(panels).toHaveLength(1);
    expect(panels[0].attributes('id')).toBe('pr-why-22');
  });

  it('closes with the Close button and with Escape', async () => {
    const w = await openFirst();
    await w.find('[data-testid="pr-why-close"]').trigger('click');
    expect(w.find('[data-testid="pr-why"]').exists()).toBe(false);

    await w.findAll('[data-testid="pr-row"]')[0].trigger('click');
    await flushPromises();
    await w
      .find('[data-testid="pr-why"]')
      .trigger('keydown', { key: 'Escape' });
    expect(w.find('[data-testid="pr-why"]').exists()).toBe(false);
  });

  it('asks for the team at the age group, league and season the run rated', async () => {
    await openFirst();
    const [url] = teamCalls();
    const u = new URL(url);
    expect(u.pathname).toBe('/api/rankings/teams/21');
    expect(u.searchParams.get('age_group')).toBe('U17');
    expect(u.searchParams.get('league')).toBe('Homegrown');
    expect(u.searchParams.get('season')).toBe('2026-2027');
  });

  it('reopening a team in the same session is not a request', async () => {
    const w = await openFirst();
    const row = w.findAll('[data-testid="pr-row"]')[0];
    await row.trigger('click');
    await row.trigger('click');
    await flushPromises();
    expect(w.find('[data-testid="pr-why-movers"]').exists()).toBe(true);
    expect(teamCalls()).toHaveLength(1);
  });

  it('shows a skeleton while the team loads', async () => {
    let resolve;
    const w = await openFirst(
      () =>
        new Promise(r => {
          resolve = r;
        })
    );
    expect(w.find('[data-testid="pr-why-skeleton"]').exists()).toBe(true);
    resolve(teamWhy());
    await flushPromises();
    expect(w.find('[data-testid="pr-why-skeleton"]').exists()).toBe(false);
  });

  it('lists the 3 movers as results with signed changes and expected share', async () => {
    const w = await openFirst();
    const movers = w.findAll('[data-testid="pr-why-mover"]');
    expect(movers).toHaveLength(3);
    expect(movers[0].text()).toContain('Beat NEFC U17 3–0');
    expect(movers[0].text()).toContain('+24');
    expect(movers[0].text()).toContain('expected to take 41% of the points');
    expect(movers[1].text()).toContain('Lost to Low Club U17 1–4');
    expect(movers[1].text()).toContain('−57');
    expect(movers[2].text()).toContain('Drew with Island FC U17 1–1');
    expect(movers[2].text()).toContain('−3');
  });

  it('notes a shoot-out on the mover and rates it as a draw', async () => {
    const w = await openFirst(() =>
      Promise.resolve(
        teamWhy({
          biggest_movers: [
            mover({
              result: 'D',
              goals_for: 0,
              goals_against: 0,
              penalties_for: 2,
              penalties_against: 4,
              delta: -6,
            }),
          ],
        })
      )
    );
    const text = w.find('[data-testid="pr-why-mover"]').text();
    expect(text).toContain('Drew with NEFC U17 0–0');
    expect(text).toContain('Lost 2–4 on penalties, rated as a draw');
  });

  it('states SOS with "of N", and only the average with no rank', async () => {
    const w = await openFirst();
    expect(w.find('[data-testid="pr-why-sos-text"]').text()).toBe(
      'Average opponent 1,538 — 12th toughest of 147'
    );

    apiRequest.mockReset();
    const u = await openFirst(() =>
      Promise.resolve(teamWhy({ sos: { rating: 1538, rank: null, of: null } }))
    );
    const text = u.find('[data-testid="pr-why-sos-text"]').text();
    expect(text).toBe('Average opponent 1,538');
    expect(text).not.toMatch(/\bof\b/);
  });

  it('draws the rating over time with first and last labelled', async () => {
    const w = await openFirst();
    const spark = w.find('[data-testid="pr-why-sparkline"]');
    expect(spark.exists()).toBe(true);
    expect(spark.find('polyline').attributes('points').split(' ')).toHaveLength(
      3
    );
    expect(w.find('[data-testid="pr-why-history-first"]').text()).toBe('1,500');
    expect(w.find('[data-testid="pr-why-history-last"]').text()).toBe('1,754');
    expect(spark.attributes('role')).toBe('img');
    expect(spark.attributes('aria-label')).toBe(
      'Rating over 3 weeks, from 1,500 on Sep 7 to 1,754 on Dec 15'
    );
  });

  it('shows one week of history as the value, with no line', async () => {
    const w = await openFirst(() =>
      Promise.resolve(
        teamWhy({
          history: [
            { run_id: 412, computed_at: '2026-12-15T10:00:04Z', rating: 1754 },
          ],
        })
      )
    );
    expect(w.find('[data-testid="pr-why-sparkline"]').exists()).toBe(false);
    expect(w.find('polyline').exists()).toBe(false);
    expect(w.find('[data-testid="pr-why-history-single"]').text()).toContain(
      '1,754'
    );
  });

  it('explains badges in words', async () => {
    const w = await openFirst(() =>
      Promise.resolve(
        teamWhy({
          badges: ['provisional', 'low_cross_conference'],
          pro_academy: true,
        })
      )
    );
    const text = w.find('[data-testid="pr-why-badges"]').text();
    expect(text).toContain('fewer than 8 matches');
    expect(text).toContain('fewer than 3 matches against teams outside');
    expect(text).toContain('does not change the rating');
  });

  it('shows the reason for a team with no rated match, not an error', async () => {
    const reason = 'IFA U17 has no rated match at U17 Homegrown in 2026-2027.';
    const w = await openFirst(() =>
      Promise.resolve(teamWhy({ in_run: false, reason, biggest_movers: null }))
    );
    expect(w.find('[data-testid="pr-why-reason"]').text()).toBe(reason);
    expect(w.find('[data-testid="pr-why-error"]').exists()).toBe(false);
    expect(w.find('[data-testid="pr-why-sos"]').exists()).toBe(false);
    expect(w.text()).not.toMatch(/\b0 G\b|\b0–0\b/);
  });

  it('shows the failure with Retry, which asks again and is not cached', async () => {
    let fail = true;
    const w = await openFirst(() =>
      fail
        ? Promise.reject(new Error('The Power Rating is unavailable right now'))
        : Promise.resolve(teamWhy())
    );
    expect(w.find('[data-testid="pr-why-error"]').text()).toContain(
      'unavailable right now'
    );
    fail = false;
    await w.find('[data-testid="pr-why-retry"]').trigger('click');
    await flushPromises();
    expect(teamCalls()).toHaveLength(2);
    expect(w.find('[data-testid="pr-why-movers"]').exists()).toBe(true);
  });

  it('closes the panel when the age group changes', async () => {
    const w = await openFirst();
    await w.find('[data-testid="pr-age-group-U16"]').trigger('click');
    await flushPromises();
    expect(w.find('[data-testid="pr-why"]').exists()).toBe(false);
  });

  it('says matches, never games', async () => {
    const w = await openFirst(() =>
      Promise.resolve(teamWhy({ badges: ['provisional'], needed: 2 }))
    );
    expect(w.find('[data-testid="pr-why"]').text()).toMatch(/matches/);
    expect(w.text()).not.toMatch(/\bgames?\b/i);
  });
});
