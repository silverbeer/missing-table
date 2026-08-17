/**
 * GoldenBoot.vue — team season leaders (SB-433).
 *
 * Rules pinned here:
 *  (a) every player who took part appears; one who never played does not
 *  (b) default sort is goals, descending
 *  (c) ties break on goals then assists before falling back to a name
 *  (d) the top three rank cells carry a medal tint, following the sorted column
 *  (e) clicking a header re-sorts and moves the active-column marker
 *  (f) nothing logged renders an explanatory empty state, never a table of zeroes
 *  (g) no medals when the leader leads on zero
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import GoldenBoot from '@/components/profiles/GoldenBoot.vue';

const SEASONS = [
  { id: 6, name: '2025', is_current: false },
  { id: 7, name: '2026', is_current: true },
];

const MATCH_TYPES = [
  { id: 1, name: 'League' },
  { id: 2, name: 'Friendly' },
  { id: 3, name: 'Tournament' },
];

const player = (id, jersey, first, last, over = {}) => ({
  player_id: id,
  jersey_number: jersey,
  first_name: first,
  last_name: last,
  games_played: 10,
  games_started: 8,
  total_goals: 0,
  total_assists: 0,
  total_yellow_cards: 0,
  total_red_cards: 0,
  ...over,
});

const SQUAD = [
  player(1, 9, 'Gabe', 'Drake', { total_goals: 12, total_assists: 4 }),
  player(2, 8, 'Marcus', 'Chen', { total_goals: 7, total_assists: 9 }),
  player(3, 14, 'Diego', 'Alvarez', {
    total_goals: 5,
    total_assists: 2,
    total_yellow_cards: 3,
  }),
  player(4, 6, 'Sam', 'Okafor', { total_goals: 3, total_assists: 6 }),
  // Assists only.
  player(5, 4, 'Owen', 'Reilly', { total_assists: 3 }),
  // Appearances but nothing else — still belongs in the squad list (SB-670).
  player(6, 2, 'Quiet', 'Defender', { total_yellow_cards: 1 }),
];

const apiRequest = vi.fn();

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    apiRequest,
    state: { profile: { team_id: 42 } },
  }),
}));

vi.mock('@/config/api', () => ({ getApiBaseUrl: () => 'http://test' }));

const mountBoot = (stats = SQUAD) => {
  apiRequest.mockImplementation(url => {
    if (url.includes('/api/seasons')) return Promise.resolve(SEASONS);
    if (url.includes('/api/match-types')) return Promise.resolve(MATCH_TYPES);
    return Promise.resolve({ players: stats });
  });
  return mount(GoldenBoot, { props: { teamId: 42 } });
};

/** The URL of the most recent team-stats request. */
const lastStatsUrl = () =>
  apiRequest.mock.calls
    .map(c => c[0])
    .filter(u => u.includes('/stats'))
    .slice(-1)[0];

const bodyRows = wrapper =>
  wrapper.findAll('tbody tr').map(tr => tr.findAll('td').map(td => td.text()));

beforeEach(() => {
  apiRequest.mockReset();
});

describe('GoldenBoot (SB-433)', () => {
  it('lists everyone who took part, scorer or not', async () => {
    const wrapper = mountBoot();
    await flushPromises();

    const names = bodyRows(wrapper).map(cells => cells[1]);
    expect(names).toHaveLength(6);
    expect(names.join(' ')).toContain('Owen Reilly'); // assists, no goals
    // Appearances are a contribution now that GP is a column.
    expect(names.join(' ')).toContain('Quiet Defender');
  });

  it('leaves out a squad member who has never played', async () => {
    const wrapper = mountBoot([
      player(1, 9, 'Played', 'Once', { games_played: 1 }),
      player(2, 8, 'Never', 'Played', { games_played: 0, games_started: 0 }),
    ]);
    await flushPromises();

    const names = bodyRows(wrapper).map(cells => cells[1]);
    expect(names.join(' ')).toContain('Played Once');
    // A row of zeroes would say something untrue about them.
    expect(names.join(' ')).not.toContain('Never Played');
  });

  it('keeps a scorer whose appearance was never flagged', async () => {
    // Appearance flags and event counters are written by different paths; a
    // scorer missing from the scorers table is the worse failure.
    const wrapper = mountBoot([
      player(1, 9, 'Ghost', 'Scorer', {
        games_played: 0,
        games_started: 0,
        total_goals: 2,
      }),
    ]);
    await flushPromises();

    expect(
      bodyRows(wrapper)
        .map(c => c[1])
        .join(' ')
    ).toContain('Ghost Scorer');
  });

  it('defaults to goals descending', async () => {
    const wrapper = mountBoot();
    await flushPromises();

    const names = bodyRows(wrapper).map(cells => cells[1]);
    expect(names[0]).toContain('Gabe Drake');
    expect(names[1]).toContain('Marcus Chen');
    // Owen has assists but no goals; the defender has neither, so he trails.
    expect(names[names.length - 2]).toContain('Owen Reilly');
    expect(names[names.length - 1]).toContain('Quiet Defender');
  });

  it('breaks a tie on the sorted column with goals, then assists', async () => {
    const wrapper = mountBoot([
      player(1, 9, 'Level', 'Alpha', { total_goals: 2, total_assists: 1 }),
      player(2, 8, 'Level', 'Bravo', { total_goals: 4, total_assists: 1 }),
      player(3, 7, 'Level', 'Charlie', { total_goals: 4, total_assists: 5 }),
    ]);
    await flushPromises();

    // Sorting by assists: Bravo and Alpha are level on 1, so goals separate them.
    await wrapper.findAll('thead .gb-sort-button')[3].trigger('click');
    const names = bodyRows(wrapper).map(cells => cells[1]);
    expect(names[0]).toContain('Charlie'); // 5 assists
    expect(names[1]).toContain('Bravo'); // 1 assist, 4 goals
    expect(names[2]).toContain('Alpha'); // 1 assist, 2 goals
  });

  it('tints the top three rank cells', async () => {
    const wrapper = mountBoot();
    await flushPromises();

    const rankCells = wrapper.findAll('tbody .gb-rank-col');
    expect(rankCells[0].classes()).toContain('gb-medal-gold');
    expect(rankCells[1].classes()).toContain('gb-medal-silver');
    expect(rankCells[2].classes()).toContain('gb-medal-bronze');
    expect(rankCells[3].classes()).not.toContain('gb-medal-gold');
  });

  it('re-sorts when a header is clicked and moves the active marker', async () => {
    const wrapper = mountBoot();
    await flushPromises();

    // Column order is GP, GS, G, A, YC, RC — index 3 is assists.
    await wrapper.findAll('thead .gb-sort-button')[3].trigger('click');

    const names = bodyRows(wrapper).map(cells => cells[1]);
    expect(names[0]).toContain('Marcus Chen'); // 9 assists

    const activeHeaders = wrapper.findAll('thead th.gb-col-active');
    expect(activeHeaders).toHaveLength(1);
    expect(activeHeaders[0].text()).toBe('A');
  });

  it('renders all six stat columns', async () => {
    const wrapper = mountBoot();
    await flushPromises();

    const headers = wrapper.findAll('thead .gb-sort-button').map(b => b.text());
    expect(headers).toEqual(['GP', 'GS', 'G', 'A', 'YC', 'RC']);
  });

  it('explains an unlogged season instead of showing a squad of zeroes', async () => {
    // Nobody took part in anything recorded — not the same as a season in
    // which nobody scored.
    const wrapper = mountBoot([
      player(6, 2, 'Quiet', 'Defender', { games_played: 0, games_started: 0 }),
      player(7, 3, 'Also', 'Quiet', { games_played: 0, games_started: 0 }),
    ]);
    await flushPromises();

    expect(wrapper.find('table').exists()).toBe(false);
    expect(wrapper.text()).toContain('Nothing recorded for this squad yet');
    expect(wrapper.text()).toContain('once matches are scored in the app');
  });

  it('shows the table once anything at all is logged', async () => {
    // Appearances but no goals: honest zeroes, so the table belongs.
    const wrapper = mountBoot([
      player(6, 2, 'Quiet', 'Defender', { games_played: 4, games_started: 2 }),
    ]);
    await flushPromises();

    expect(wrapper.find('table').exists()).toBe(true);
    expect(wrapper.text()).toContain('Quiet Defender');
  });

  it('awards no medals when the leader leads on zero', async () => {
    const wrapper = mountBoot([
      player(1, 9, 'No', 'Goals', { games_played: 5 }),
      player(2, 8, 'Also', 'None', { games_played: 4 }),
      player(3, 7, 'Still', 'None', { games_played: 3 }),
    ]);
    await flushPromises();

    const rankCells = wrapper.findAll('tbody .gb-rank-col');
    expect(rankCells[0].classes()).not.toContain('gb-medal-gold');

    // Sorted by GP, where there is something to lead on, the tint returns.
    await wrapper.findAll('thead .gb-sort-button')[0].trigger('click');
    expect(wrapper.findAll('tbody .gb-rank-col')[0].classes()).toContain(
      'gb-medal-gold'
    );
  });

  it('defaults to the current season and league games only', async () => {
    const wrapper = mountBoot();
    await flushPromises();

    const url = lastStatsUrl();
    expect(url).toContain('season_id=7'); // is_current
    expect(url).toContain('match_type_id=1'); // League

    await wrapper.vm.$nextTick();
    const selects = wrapper.findAll('.gb-filter');
    expect(selects[0].element.value).toBe('7');
    expect(selects[1].element.value).toBe('1');
  });

  it('refetches when the competition changes, and omits the param for All', async () => {
    const wrapper = mountBoot();
    await flushPromises();

    const competition = wrapper.findAll('.gb-filter')[1];
    await competition.findAll('option')[2].setSelected(); // Tournament
    await flushPromises();
    expect(lastStatsUrl()).toContain('match_type_id=3');

    // "All" is the absence of the filter, not a value the API knows.
    await competition.findAll('option')[3].setSelected(); // All
    await flushPromises();
    expect(lastStatsUrl()).not.toContain('match_type_id');
    expect(lastStatsUrl()).toContain('season_id=7');
  });

  it('refetches when the season changes', async () => {
    const wrapper = mountBoot();
    await flushPromises();

    await wrapper.findAll('.gb-filter')[0].findAll('option')[0].setSelected();
    await flushPromises();

    expect(lastStatsUrl()).toContain('season_id=6');
  });

  it('falls back to all competitions when no league type exists', async () => {
    apiRequest.mockImplementation(url => {
      if (url.includes('/api/seasons')) return Promise.resolve(SEASONS);
      if (url.includes('/api/match-types'))
        return Promise.resolve([{ id: 2, name: 'Friendly' }]);
      return Promise.resolve({ players: SQUAD });
    });
    mount(GoldenBoot, { props: { teamId: 42 } });
    await flushPromises();

    // Better a full board than an empty one built on an assumption.
    expect(lastStatsUrl()).not.toContain('match_type_id');
  });

  it('surfaces a load failure rather than an empty leaderboard', async () => {
    apiRequest.mockRejectedValue(new Error('boom'));
    const wrapper = mount(GoldenBoot, { props: { teamId: 42 } });
    await flushPromises();

    expect(wrapper.text()).toContain('Could not load season stats');
    expect(wrapper.find('table').exists()).toBe(false);
  });
});
