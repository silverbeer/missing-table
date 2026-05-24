/**
 * TournamentBracket.vue Tests
 *
 * Regression guard: the bracket must render Round of 16 (and later rounds) from
 * real match data — not just hardcoded placeholders. Previously only
 * round_of_32 was rendered from data and R16/QF/SF/Final were always empty
 * "—" cells, so loaded R16 matchups never appeared on the bracket.
 */

import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import TournamentBracket from '@/components/TournamentBracket.vue';

const mkMatch = (id, round, home, away, extra = {}) => ({
  id,
  tournament_round: round,
  home_team: { name: home },
  away_team: { name: away },
  match_status: 'scheduled',
  home_score: null,
  away_score: null,
  match_date: '2026-05-25',
  ...extra,
});

describe('TournamentBracket', () => {
  it('shows the empty-state when there are no round_of_32 matches', () => {
    const wrapper = mount(TournamentBracket, { props: { matches: [] } });
    expect(wrapper.text()).toContain('No matches in this bracket yet');
  });

  it('renders round_of_16 matches from data, not just placeholders', () => {
    const matches = [
      mkMatch(1, 'round_of_32', 'Team A', 'Team B'),
      mkMatch(2, 'round_of_32', 'Team C', 'Team D'),
      mkMatch(10, 'round_of_16', 'PDA', 'IFA'),
    ];
    const wrapper = mount(TournamentBracket, { props: { matches } });

    expect(wrapper.text()).toContain('Round of 16');
    // The regression we are guarding: R16 teams come from match data.
    expect(wrapper.text()).toContain('PDA');
    expect(wrapper.text()).toContain('IFA');
  });

  it('pads not-yet-loaded later-round slots with placeholders', () => {
    const matches = [mkMatch(1, 'round_of_32', 'Team A', 'Team B')];
    const wrapper = mount(TournamentBracket, { props: { matches } });
    // No R16/QF/SF/Final loaded -> those slots fall back to "—".
    expect(wrapper.text()).toContain('—');
  });

  it('emits match-click with the match when a round_of_16 cell is clicked', async () => {
    const r16 = mkMatch(10, 'round_of_16', 'PDA', 'IFA');
    const matches = [mkMatch(1, 'round_of_32', 'Team A', 'Team B'), r16];
    const wrapper = mount(TournamentBracket, { props: { matches } });

    const r16Btn = wrapper
      .findAll('button')
      .find(b => b.text().includes('IFA'));
    expect(r16Btn).toBeTruthy();

    await r16Btn.trigger('click');
    expect(wrapper.emitted('match-click')).toBeTruthy();
    expect(wrapper.emitted('match-click')[0][0]).toEqual(r16);
  });
});
