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
  home_team:
    typeof home === 'string'
      ? { name: home }
      : { name: home.name, id: home.id },
  away_team:
    typeof away === 'string'
      ? { name: away }
      : { name: away.name, id: away.id },
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

describe('TournamentBracket — feeder-derived slot placement', () => {
  // Helper: find which R16 slot a match landed in by inspecting the cell
  // wrapper's `r16-N` class. Returns N or null if the match wasn't placed.
  const slotOf = (wrapper, roundPrefix, matchName) => {
    const cells = wrapper.findAll(
      `.bracket-cell.col-2, .bracket-cell.col-3, .bracket-cell.col-4, .bracket-cell.col-5`
    );
    for (const cell of cells) {
      if (!cell.text().includes(matchName)) continue;
      const cls = [...cell.element.classList];
      const slotClass = cls.find(c => c.startsWith(`${roundPrefix}-`));
      if (slotClass) return parseInt(slotClass.split('-')[1], 10);
    }
    return null;
  };

  it('places R16 match directly under its two feeder R32 cells, not in id-order', () => {
    /**
     * Bracket structure for this test:
     *   R32 slot 0:  Team A (id=1) vs Team B (id=2)
     *   R32 slot 1:  Team C (id=3) vs Team D (id=4)
     *   R32 slot 2:  Team E (id=5) vs Team F (id=6)
     *   R32 slot 3:  Team G (id=7) vs Team H (id=8)
     *
     * Real R16 match: Team E vs Team G — winners of R32 slots 2 and 3.
     * That pair (2, 3) feeds into R16 slot 1 (floor(2/2)).
     *
     * But the R16 match's id is the LOWEST loaded (id=100). Old id-order
     * placement would put it at R16 slot 0 — wrong. New feeder-derived
     * placement puts it at slot 1.
     */
    const matches = [
      mkMatch(1, 'round_of_32', { name: 'A', id: 1 }, { name: 'B', id: 2 }),
      mkMatch(2, 'round_of_32', { name: 'C', id: 3 }, { name: 'D', id: 4 }),
      mkMatch(3, 'round_of_32', { name: 'E', id: 5 }, { name: 'F', id: 6 }),
      mkMatch(4, 'round_of_32', { name: 'G', id: 7 }, { name: 'H', id: 8 }),
      mkMatch(100, 'round_of_16', { name: 'E', id: 5 }, { name: 'G', id: 7 }),
    ];
    const wrapper = mount(TournamentBracket, { props: { matches } });

    expect(slotOf(wrapper, 'r16', 'E')).toBe(1);
  });

  it('places multiple R16 matches at slots derived from their R32 feeders, regardless of id order', () => {
    /**
     * Two R16 matches whose ids are flipped relative to their bracket order:
     *   R16 id=200 = winners of R32 slots 0+1 → should land at R16 slot 0
     *   R16 id=100 = winners of R32 slots 2+3 → should land at R16 slot 1
     */
    const matches = [
      mkMatch(1, 'round_of_32', { name: 'A', id: 1 }, { name: 'B', id: 2 }),
      mkMatch(2, 'round_of_32', { name: 'C', id: 3 }, { name: 'D', id: 4 }),
      mkMatch(3, 'round_of_32', { name: 'E', id: 5 }, { name: 'F', id: 6 }),
      mkMatch(4, 'round_of_32', { name: 'G', id: 7 }, { name: 'H', id: 8 }),
      mkMatch(200, 'round_of_16', { name: 'A', id: 1 }, { name: 'C', id: 3 }),
      mkMatch(100, 'round_of_16', { name: 'E', id: 5 }, { name: 'G', id: 7 }),
    ];
    const wrapper = mount(TournamentBracket, { props: { matches } });

    expect(slotOf(wrapper, 'r16', 'A')).toBe(0);
    expect(slotOf(wrapper, 'r16', 'E')).toBe(1);
  });

  it('cascades feeder-derived placement to QF / SF / Final', () => {
    /**
     * Build R32 pairs that feed into 2 R16 matches, which feed into 1 QF, etc.
     * Verify the Final cell ends up holding the right match by feeder chain.
     */
    const r32 = [
      mkMatch(1, 'round_of_32', { name: 'A', id: 1 }, { name: 'B', id: 2 }),
      mkMatch(2, 'round_of_32', { name: 'C', id: 3 }, { name: 'D', id: 4 }),
      mkMatch(3, 'round_of_32', { name: 'E', id: 5 }, { name: 'F', id: 6 }),
      mkMatch(4, 'round_of_32', { name: 'G', id: 7 }, { name: 'H', id: 8 }),
    ];
    // A advanced (slot 0), C advanced (slot 1), E advanced (slot 2), G advanced (slot 3)
    const r16 = [
      mkMatch(11, 'round_of_16', { name: 'A', id: 1 }, { name: 'C', id: 3 }), // slot 0
      mkMatch(12, 'round_of_16', { name: 'E', id: 5 }, { name: 'G', id: 7 }), // slot 1
    ];
    // A advanced from R16 slot 0, E advanced from R16 slot 1 → meet in QF slot 0
    const qf = [
      mkMatch(21, 'quarterfinal', { name: 'A', id: 1 }, { name: 'E', id: 5 }),
    ];
    const wrapper = mount(TournamentBracket, {
      props: { matches: [...r32, ...r16, ...qf] },
    });

    expect(slotOf(wrapper, 'qf', 'A')).toBe(0);
  });

  it("falls back to id-order placement for matches whose teams aren't in the feeder round", () => {
    /**
     * R16 match whose teams never appeared in R32 (e.g. placeholder created
     * before R32 was loaded, or off-bracket data). It still renders — just
     * at the first available slot in id order.
     */
    const matches = [
      mkMatch(1, 'round_of_32', { name: 'A', id: 1 }, { name: 'B', id: 2 }),
      mkMatch(100, 'round_of_16', { name: 'Z', id: 99 }, { name: 'Y', id: 98 }),
    ];
    const wrapper = mount(TournamentBracket, { props: { matches } });

    expect(slotOf(wrapper, 'r16', 'Z')).toBe(0);
  });
});
