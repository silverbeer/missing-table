/**
 * TournamentMatchCenter.vue — the Fest rounds do not switch on the bracket (SB-1752).
 *
 * `showcase`, `consolation` and `placement_final` are real rounds but not an
 * elimination tree, so a tournament whose only "finals" are placement finals
 * must keep the plain list: no Bracket toggle. A real knockout round still
 * turns it on (control).
 *
 * Fixtures are scraped matches with no user data (no scores, no rosters).
 */

import { describe, it, expect, vi } from 'vitest';
import { flushPromises, mount } from '@vue/test-utils';

const apiRequest = vi.fn();
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({ apiRequest, isAuthenticated: { value: false } }),
}));

import TournamentMatchCenter from '@/components/TournamentMatchCenter.vue';

const SEASONS = [
  {
    id: 4,
    name: '2026-2027',
    start_date: '2026-09-01',
    end_date: '2027-06-30',
  },
];

const mkMatch = (id, round, group = 'A') => ({
  id,
  match_date: '2026-06-05',
  scheduled_kickoff: null,
  match_status: 'scheduled',
  home_score: null,
  away_score: null,
  home_penalty_score: null,
  away_penalty_score: null,
  tournament_group: group,
  tournament_round: round,
  tournament_round_order: null,
  age_group: { id: 2, name: 'U14' },
  home_team: { id: id * 2, name: `Home ${id}` },
  away_team: { id: id * 2 + 1, name: `Away ${id}` },
  home_team_club: null,
  away_team_club: null,
});

async function mountWith(rounds) {
  const tournament = {
    id: 6,
    name: 'MLS NEXT Fest',
    start_date: '2026-06-05',
    end_date: '2026-06-07',
    matches: rounds.map((r, i) => mkMatch(100 + i, r)),
    age_groups: [{ id: 2, name: 'U14' }],
  };
  apiRequest.mockReset();
  apiRequest.mockImplementation(url => {
    if (url.includes('/api/seasons')) return Promise.resolve(SEASONS);
    if (url.includes('/motd')) return Promise.resolve({ picks: [] });
    if (/\/api\/tournaments\/\d+/.test(url)) return Promise.resolve(tournament);
    if (url.includes('/api/tournaments')) return Promise.resolve([tournament]);
    return Promise.resolve(null);
  });
  const wrapper = mount(TournamentMatchCenter, {
    global: { stubs: { MatchDetailView: true } },
  });
  await flushPromises();
  return wrapper;
}

const hasBracketToggle = wrapper =>
  wrapper.findAll('button').some(b => b.text() === 'Bracket');

describe('TournamentMatchCenter — Fest rounds and the bracket toggle', () => {
  it('shows no Bracket toggle when the only finals are placement finals', async () => {
    const wrapper = await mountWith(['group_stage', 'placement_final']);
    expect(hasBracketToggle(wrapper)).toBe(false);
    expect(wrapper.vm.hasBracketRounds).toBe(false);
  });

  it.each(['showcase', 'consolation', 'placement_final'])(
    'a tournament of only %s matches has no Bracket toggle',
    async round => {
      const wrapper = await mountWith([round, round]);
      expect(hasBracketToggle(wrapper)).toBe(false);
    }
  );

  it('still shows the Bracket toggle when a real knockout round is present', async () => {
    const wrapper = await mountWith(['group_stage', 'semifinal']);
    expect(hasBracketToggle(wrapper)).toBe(true);
  });

  it('placement finals alongside a real final keep the Bracket toggle on', async () => {
    const wrapper = await mountWith(['placement_final', 'final']);
    expect(hasBracketToggle(wrapper)).toBe(true);
  });
});
