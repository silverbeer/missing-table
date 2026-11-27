/**
 * LeaderboardsPanel (SB-1785): the Ranking tab's cross-conference boards over
 * GET /api/leaderboards (SB-1781).
 *
 * What these guard: the coverage note leads every card (a stat board, not a
 * strength ranking); ties read as ties; a board nobody qualifies for says so
 * rather than printing zeros; teams under the minimum are listed once, unranked;
 * and a team click opens Matches with the same filters LeagueTable sends.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { flushPromises, mount } from '@vue/test-utils';

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

import LeaderboardsPanel from '@/components/ranking/LeaderboardsPanel.vue';

const IFA = 19;
const NEFC = 40;
const FUSION = 41;

const team = (id, name, club_name = name) => ({ id, name, club_name });

const row = (over = {}) => ({
  rank: 1,
  team: team(IFA, 'IFA'),
  club_id: 5,
  club_logo_url: 'https://x/ifa.png',
  conference: 'Northeast',
  no_conference: false,
  gp: 10,
  w: 7,
  d: 2,
  l: 1,
  value: 2.3,
  pro_games: null,
  ...over,
});

const board = (key, rows, over = {}) => ({
  key,
  title: `Board ${key}`,
  variant: key === 'ppg' || key.endsWith('_pg') ? 'per_game' : 'total',
  better: key === 'ga_pg' || key === 'ga' ? 'lower' : 'higher',
  rows,
  unranked_count: 0,
  ...over,
});

const NOTE =
  '84 teams from 8 conferences. Conferences only meet at tournaments, so this compares stats across conferences: a stat board, not a ranking.';

const coverage = (over = {}) => ({
  teams: 84,
  matches: 300,
  conferences: 8,
  min_gp: 6,
  competitions_present: ['League', 'Flex'],
  competitions_absent: [],
  teams_without_conference: 1,
  matches_without_score: 0,
  sides_other_age_group: 0,
  note: NOTE,
  ...over,
});

/** A U15 Homegrown answer: every board, the totals the panel must not show. */
const leaderboards = (over = {}) => ({
  league: 'Homegrown',
  age_group: { id: 3, name: 'U15' },
  season: { id: 184, name: '2026-2027' },
  boards: [
    board('pts', [row({ value: 23 })]),
    board('ppg', [
      row({ rank: 1, value: 2.5 }),
      row({
        rank: 1,
        team: team(NEFC, 'NEFC'),
        club_id: 6,
        club_logo_url: null,
        value: 2.5,
      }),
      row({
        rank: 3,
        team: team(FUSION, 'Fusion U15', 'FC Fusion'),
        club_id: 7,
        club_logo_url: null,
        conference: null,
        no_conference: true,
        value: 2,
      }),
    ]),
    board('gf', [row({ value: 30 })]),
    board('gf_pg', [row({ value: 3 })]),
    board('ga', [row({ value: 5 })]),
    board('ga_pg', [row({ value: 0.5 })]),
    board('gd', [row({ value: 25 })]),
    board('gd_pg', [row({ value: 2.5 })]),
    board('unbeaten', [row({ value: 10, w: 8, d: 2, l: 0 })]),
    board('pro_wins', []),
  ],
  unranked: [
    row({ rank: null, value: null, team: team(77, 'Late Starters'), gp: 3 }),
  ],
  unranked_count: 5,
  coverage: coverage(),
  reason: null,
  error: null,
  ...over,
});

const LEAGUES = [
  { id: 1, name: 'Homegrown' },
  { id: 2, name: 'Academy' },
];

const routeApi = (boardsResponse = () => Promise.resolve(leaderboards())) => {
  apiRequest.mockImplementation(url => {
    if (url.includes('/api/leaderboards')) return boardsResponse(url);
    if (url.includes('/api/leagues')) return Promise.resolve(LEAGUES);
    return Promise.resolve([]);
  });
};

const mountPanel = async () => {
  const wrapper = mount(LeaderboardsPanel);
  await flushPromises();
  return wrapper;
};

const boardsCalls = () =>
  apiRequest.mock.calls
    .map(([url]) => url)
    .filter(url => url.includes('/api/leaderboards'));

describe('LeaderboardsPanel (SB-1785)', () => {
  beforeEach(() => {
    apiRequest.mockReset();
    window.localStorage.clear();
  });

  it('asks for U15 Homegrown, top 20, with no season', async () => {
    routeApi();
    await mountPanel();
    const [url] = boardsCalls();
    const params = new URL(url).searchParams;
    expect(params.get('age_group')).toBe('U15');
    expect(params.get('league')).toBe('Homegrown');
    expect(params.get('limit')).toBe('20');
    expect(params.has('season')).toBe(false);
  });

  it('renders the six per-game and record boards in order, and no totals', async () => {
    routeApi();
    const w = await mountPanel();
    const keys = w
      .findAll('[data-testid^="board-"]')
      .map(b => b.attributes('data-testid'))
      .filter(id =>
        /^board-(pts|ppg|gf|gf_pg|ga|ga_pg|gd|gd_pg|unbeaten|pro_wins)$/.test(
          id
        )
      );
    expect(keys).toEqual([
      'board-ppg',
      'board-gf_pg',
      'board-ga_pg',
      'board-gd_pg',
      'board-unbeaten',
      'board-pro_wins',
    ]);
    for (const total of ['pts', 'gf', 'ga', 'gd']) {
      expect(w.find(`[data-testid="board-${total}"]`).exists()).toBe(false);
    }
  });

  it('states the coverage note and denominator once, above the boards (SB-1817)', async () => {
    routeApi();
    const w = await mountPanel();
    const notes = w.findAll('[data-testid="board-coverage-note"]');
    expect(notes).toHaveLength(1);
    expect(notes[0].text()).toBe(NOTE);
    expect(w.findAll('[data-testid="board-coverage"]')).toHaveLength(1);
    // Cards carry only their title now.
    expect(w.get('[data-testid="board-ppg"]').text()).not.toContain(
      'conferences'
    );
    expect(w.get('[data-testid="board-coverage"]').text()).toBe(
      '84 U15 Homegrown teams · 8 conferences · min 6 matches'
    );
  });

  it('marks shared ranks with T: T1, T1, 3', async () => {
    routeApi();
    const w = await mountPanel();
    const ranks = w
      .get('[data-testid="board-ppg"]')
      .findAll('[data-testid="row-rank"]')
      .map(r => r.text());
    expect(ranks).toEqual(['T1', 'T1', '3']);
  });

  it('flags a team with no Homegrown conference and shows its club', async () => {
    routeApi();
    const w = await mountPanel();
    const rows = w
      .get('[data-testid="board-ppg"]')
      .findAll('[data-testid="board-row"]');
    expect(rows[2].find('[data-testid="row-no-conference"]').text()).toBe(
      'No Homegrown conference'
    );
    expect(rows[2].find('[data-testid="row-club"]').text()).toContain(
      'FC Fusion'
    );
    // Same name as the club: no subtitle repeating it.
    expect(rows[0].find('[data-testid="row-club"]').exists()).toBe(false);
  });

  it('formats values per board: 2 places, signed GD, W-D-L', async () => {
    routeApi();
    const w = await mountPanel();
    const value = key =>
      w.get(`[data-testid="board-${key}"] [data-testid="row-value"]`).text();
    expect(value('ppg')).toBe('2.50');
    expect(value('gd_pg')).toBe('+2.50');
    expect(value('unbeaten')).toBe('8-2-0');
  });

  it('shows pro wins as "N of M" and an empty board without zeros', async () => {
    routeApi(() =>
      Promise.resolve(
        leaderboards({
          boards: [
            board('ppg', [row()]),
            board('pro_wins', [row({ value: 2, pro_games: 3 })]),
          ],
        })
      )
    );
    let w = await mountPanel();
    expect(
      w.get('[data-testid="board-pro_wins"] [data-testid="row-value"]').text()
    ).toBe('2 of 3');

    routeApi();
    w = await mountPanel();
    const empty = w.get('[data-testid="board-pro_wins"]');
    expect(empty.find('[data-testid="board-no-rows"]').text()).toBe(
      'No team qualifies yet'
    );
    expect(empty.find('[data-testid="board-row"]').exists()).toBe(false);
    expect(empty.text()).not.toMatch(/\b0 of\b|\b0\.00\b/);
  });

  it('lists unranked teams once, without a rank, with the remainder', async () => {
    routeApi();
    const w = await mountPanel();
    const lists = w.findAll('[data-testid="unranked-list"]');
    expect(lists).toHaveLength(1);
    expect(w.get('[data-testid="unranked-title"]').text()).toBe(
      'Too few matches (under 6) — not ranked · 5 teams'
    );
    const rows = w.findAll('[data-testid="unranked-row"]');
    expect(rows).toHaveLength(1);
    expect(rows[0].text()).toContain('Late Starters');
    expect(rows[0].text()).toContain('3 MP');
    expect(rows[0].find('[data-testid="row-rank"]').exists()).toBe(false);
    expect(w.get('[data-testid="unranked-more"]').text()).toBe('+4 more');
  });

  it('shows "No results yet" with the reason for an age group with nothing played', async () => {
    routeApi(() =>
      Promise.resolve(
        leaderboards({
          boards: [board('ppg', []), board('gf_pg', [])],
          unranked: [],
          unranked_count: 0,
          reason: 'No played League or Flex matches at U19 this season.',
        })
      )
    );
    const w = await mountPanel();
    expect(w.get('[data-testid="leaderboards-empty"]').text()).toContain(
      'No results yet'
    );
    expect(w.get('[data-testid="leaderboards-empty-reason"]').text()).toBe(
      'No played League or Flex matches at U19 this season.'
    );
    expect(w.find('[data-testid="board-ppg"]').exists()).toBe(false);
    expect(w.find('[data-testid="leaderboards-skeleton"]').exists()).toBe(
      false
    );
  });

  it('shows the API detail on failure, and Retry asks again', async () => {
    let fail = true;
    routeApi(() =>
      fail
        ? Promise.reject(new Error('Leaderboards are unavailable right now'))
        : Promise.resolve(leaderboards())
    );
    const w = await mountPanel();
    expect(w.get('[data-testid="leaderboards-error"]').text()).toContain(
      'Leaderboards are unavailable right now'
    );

    fail = false;
    await w.get('[data-testid="leaderboards-retry"]').trigger('click');
    await flushPromises();
    expect(boardsCalls()).toHaveLength(2);
    expect(w.find('[data-testid="leaderboards-error"]').exists()).toBe(false);
    expect(w.find('[data-testid="board-ppg"]').exists()).toBe(true);
  });

  it('Retry also reloads the league list when it never arrived', async () => {
    let down = true;
    apiRequest.mockImplementation(url => {
      if (down) return Promise.reject(new Error('Could not reach the server.'));
      if (url.includes('/api/leaderboards'))
        return Promise.resolve(leaderboards());
      if (url.includes('/api/leagues')) return Promise.resolve(LEAGUES);
      return Promise.resolve([]);
    });
    const w = await mountPanel();
    down = false;
    await w.get('[data-testid="leaderboards-retry"]').trigger('click');
    await flushPromises();
    const leagueCalls = apiRequest.mock.calls.filter(([u]) =>
      u.endsWith('/api/leagues')
    );
    expect(leagueCalls).toHaveLength(2);

    await w
      .get('[data-testid="board-ppg"]')
      .findAll('[data-testid="board-row"]')[0]
      .trigger('click');
    expect(w.emitted('navigate-to-team')[0][0].leagueId).toBe(1);
  });

  it('Retry does not reload a league list it already has', async () => {
    let fail = true;
    routeApi(() =>
      fail ? Promise.reject(new Error('nope')) : Promise.resolve(leaderboards())
    );
    const w = await mountPanel();
    fail = false;
    await w.get('[data-testid="leaderboards-retry"]').trigger('click');
    await flushPromises();
    const leagueCalls = apiRequest.mock.calls.filter(([u]) =>
      u.endsWith('/api/leagues')
    );
    expect(leagueCalls).toHaveLength(1);
  });

  it('shows a skeleton while the request is pending', async () => {
    let resolve;
    routeApi(() => new Promise(r => (resolve = r)));
    const w = mount(LeaderboardsPanel);
    await flushPromises();
    expect(w.find('[data-testid="leaderboards-skeleton"]').exists()).toBe(true);
    expect(w.find('[data-testid="leaderboards-empty"]').exists()).toBe(false);

    resolve(leaderboards());
    await flushPromises();
    expect(w.find('[data-testid="leaderboards-skeleton"]').exists()).toBe(
      false
    );
    expect(w.find('[data-testid="board-ppg"]').exists()).toBe(true);
  });

  it('refetches with age_group=U16 when the age group changes', async () => {
    routeApi();
    const w = await mountPanel();
    await w.get('[data-testid="age-group-U16"]').trigger('click');
    await flushPromises();
    const calls = boardsCalls();
    expect(calls).toHaveLength(2);
    expect(new URL(calls[1]).searchParams.get('age_group')).toBe('U16');
  });

  it('drops a stale answer that lands after a newer one', async () => {
    const pending = [];
    routeApi(url => new Promise(r => pending.push({ url, r })));
    const w = mount(LeaderboardsPanel);
    await flushPromises();
    await w.get('[data-testid="age-group-U16"]').trigger('click');
    await flushPromises();
    expect(pending).toHaveLength(2);

    pending[1].r(
      leaderboards({
        age_group: { id: 4, name: 'U16' },
        coverage: coverage({ teams: 70 }),
      })
    );
    await flushPromises();
    pending[0].r(leaderboards());
    await flushPromises();
    expect(w.get('[data-testid="board-coverage"]').text()).toMatch(
      /^70 U16 Homegrown teams/
    );
  });

  it('offers a board picker for small screens', async () => {
    routeApi();
    const w = await mountPanel();
    const options = w
      .get('[data-testid="board-picker"]')
      .findAll('option')
      .map(o => o.attributes('value'));
    expect(options).toEqual([
      'ppg',
      'gf_pg',
      'ga_pg',
      'gd_pg',
      'unbeaten',
      'pro_wins',
    ]);
  });

  it("uses the row's club logo, and the name alone without one", async () => {
    routeApi();
    const w = await mountPanel();
    const rows = w
      .get('[data-testid="board-ppg"]')
      .findAll('[data-testid="board-row"]');
    expect(rows[0].find('img').attributes('src')).toContain('ifa');
    expect(rows[1].find('img').exists()).toBe(false);
    expect(rows[1].get('[data-testid="row-team"]').text()).toBe('NEFC');
    // Logos ride on the rows: no team or club list is loaded for them.
    const urls = apiRequest.mock.calls.map(([url]) => url);
    expect(urls.some(u => u.includes('/api/teams'))).toBe(false);
    expect(urls.some(u => u.includes('/api/clubs'))).toBe(false);
  });

  it('says "1 team" and "1 conference" in the singular', async () => {
    routeApi(() =>
      Promise.resolve(
        leaderboards({ coverage: coverage({ teams: 1, conferences: 1 }) })
      )
    );
    const w = await mountPanel();
    expect(w.get('[data-testid="board-coverage"]').text()).toBe(
      '1 U15 Homegrown team · 1 conference · min 6 matches'
    );
  });

  it('opens Matches on the team with the ids LeagueTable sends', async () => {
    routeApi();
    const w = await mountPanel();
    await w
      .get('[data-testid="board-ppg"]')
      .findAll('[data-testid="board-row"]')[0]
      .trigger('click');
    expect(w.emitted('navigate-to-team')).toEqual([
      [
        {
          teamId: IFA,
          clubId: 5,
          ageGroupId: 3,
          leagueId: 1,
          divisionId: null,
          seasonId: 184,
        },
      ],
    ]);
  });
});
