/**
 * TournamentStandings.vue Tests
 *
 * Covers the standings computation (points, GD, PK-shootout wins,
 * regulation-only GF/GA, tiebreak sorting) and the head-to-head cross-table,
 * plus the mobile-responsive column behavior: the GF/GA columns are dropped on
 * phones (`hidden sm:table-cell`) so the essential MP/W/D/L/GD/PTS set fits
 * without horizontal scrolling.
 */

import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import TournamentStandings from '@/components/TournamentStandings.vue';

const team = (id, name) => ({ id, name });

// Completed match factory. PK scores optional (only valid on a draw).
const mkMatch = (id, home, away, hs, as, extra = {}) => ({
  id,
  home_team: home,
  away_team: away,
  home_score: hs,
  away_score: as,
  home_penalty_score: null,
  away_penalty_score: null,
  match_status: 'completed',
  match_date: '2026-06-05',
  tournament_round: 'group_stage',
  tournament_group: 'Bracket A',
  ...extra,
});

const A = team(1, 'Team Alpha');
const B = team(2, 'Team Bravo');
const C = team(3, 'Team Charlie');

describe('TournamentStandings', () => {
  it('shows the empty-state when there are no matches', () => {
    const wrapper = mount(TournamentStandings, { props: { matches: [] } });
    expect(wrapper.text()).toContain('No group-stage matches in this bracket');
  });

  it('computes points, GD and orders teams by points then GD', () => {
    // A beats B 3-1; A draws C 2-2; B beats C 1-0.
    // A: W1 D1 -> 4 pts, GF5 GA3 GD+2
    // B: W1 L1 -> 3 pts, GF2 GA3 GD-1
    // C: D1 L1 -> 1 pt,  GF2 GA3 GD-1
    const matches = [
      mkMatch(1, A, B, 3, 1),
      mkMatch(2, A, C, 2, 2),
      mkMatch(3, B, C, 1, 0),
    ];
    const wrapper = mount(TournamentStandings, { props: { matches } });

    // The h2h table is a separate <table>, so scope to the first one.
    const standingsRows = wrapper.findAll('table')[0].findAll('tbody tr');

    // Three teams ranked, leader is Team Alpha (4 pts).
    expect(standingsRows).toHaveLength(3);
    expect(standingsRows[0].text()).toContain('Team Alpha');
    // Last cell of the leader row is PTS = 4.
    const leaderCells = standingsRows[0].findAll('td');
    expect(leaderCells[leaderCells.length - 1].text()).toBe('4');
  });

  it('counts a PK-shootout win as a win but keeps GF/GA at regulation', () => {
    // A and B draw 1-1 in regulation; A wins 4-3 on penalties.
    const matches = [
      mkMatch(1, A, B, 1, 1, {
        home_penalty_score: 4,
        away_penalty_score: 3,
      }),
    ];
    const wrapper = mount(TournamentStandings, { props: { matches } });
    const standingsRows = wrapper.findAll('table')[0].findAll('tbody tr');

    // A should be first with 3 points (PK win), B second with 0.
    expect(standingsRows[0].text()).toContain('Team Alpha');
    const aCells = standingsRows[0].findAll('td');
    // PTS column (last) = 3 for the shootout winner.
    expect(aCells[aCells.length - 1].text()).toBe('3');
    // GD column (second-to-last) is 0 — regulation was a draw.
    expect(aCells[aCells.length - 2].text()).toBe('0');
  });

  it('drops GF/GA columns on mobile via hidden sm:table-cell', () => {
    const matches = [mkMatch(1, A, B, 2, 0)];
    const wrapper = mount(TournamentStandings, { props: { matches } });

    const headers = wrapper.findAll('table')[0].findAll('thead th');
    const byLabel = Object.fromEntries(
      headers.map(h => [h.text(), h.classes().join(' ')])
    );

    // GF and GA are mobile-hidden; MP / GD / PTS always visible.
    expect(byLabel['GF']).toContain('hidden');
    expect(byLabel['GF']).toContain('sm:table-cell');
    expect(byLabel['GA']).toContain('hidden');
    expect(byLabel['PTS']).not.toContain('hidden');
    expect(byLabel['MP']).not.toContain('hidden');
    expect(byLabel['GD']).not.toContain('hidden');
  });

  it('renders the head-to-head result from the row team perspective', () => {
    // A beat B 3-1. In B's row vs A's column the score is shown from B's
    // perspective: 1-3.
    const matches = [mkMatch(1, A, B, 3, 1)];
    const wrapper = mount(TournamentStandings, { props: { matches } });

    const h2hTable = wrapper.findAll('table')[1];
    expect(h2hTable.text()).toContain('3-1');
    expect(h2hTable.text()).toContain('1-3');
  });
});
