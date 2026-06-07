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

describe('TournamentBracket — tournament_round_order placement', () => {
  // Same helper as above, copied for locality.
  const slotOf = (wrapper, roundPrefix, matchName) => {
    const cells = wrapper.findAll('.bracket-cell');
    for (const cell of cells) {
      if (!cell.text().includes(matchName)) continue;
      const cls = [...cell.element.classList];
      const slotClass = cls.find(c => c.startsWith(`${roundPrefix}-`));
      if (slotClass) return parseInt(slotClass.split('-')[1], 10);
    }
    return null;
  };

  it('places R32 matches at their explicit tournament_round_order, ignoring id', () => {
    /**
     * Match ids are inserted out of canonical order (e.g. an MLS NEXT Cup
     * R32 that was loaded later). tournament_round_order is the source of
     * truth.
     */
    const matches = [
      // id=300 but should go at slot 0 (top of bracket)
      mkMatch(300, 'round_of_32', 'Top of bracket', 'Opponent A', {
        tournament_round_order: 0,
      }),
      // id=100 but should go at slot 5
      mkMatch(100, 'round_of_32', 'Middle bracket', 'Opponent B', {
        tournament_round_order: 5,
      }),
    ];
    const wrapper = mount(TournamentBracket, { props: { matches } });

    expect(slotOf(wrapper, 'r32', 'Top of bracket')).toBe(0);
    expect(slotOf(wrapper, 'r32', 'Middle bracket')).toBe(5);
  });

  it('explicit tournament_round_order on R16 wins over feeder-derived slot', () => {
    /**
     * Feeder math would put PDA vs IFA at slot floor(min(4, 15)/2) = 2,
     * but the data says it lives at slot 3 (e.g. non-standard bracket
     * pairing). Explicit field wins.
     */
    const matches = [
      mkMatch(
        1,
        'round_of_32',
        { name: 'A', id: 1 },
        { name: 'B', id: 2 },
        { tournament_round_order: 0 }
      ),
      mkMatch(
        2,
        'round_of_32',
        { name: 'C', id: 3 },
        { name: 'D', id: 4 },
        { tournament_round_order: 1 }
      ),
      mkMatch(
        3,
        'round_of_32',
        { name: 'E', id: 5 },
        { name: 'F', id: 6 },
        { tournament_round_order: 2 }
      ),
      mkMatch(
        4,
        'round_of_32',
        { name: 'G', id: 7 },
        { name: 'H', id: 8 },
        { tournament_round_order: 3 }
      ),
      mkMatch(
        5,
        'round_of_32',
        { name: 'I', id: 9 },
        { name: 'J', id: 10 },
        { tournament_round_order: 4 }
      ),
      mkMatch(
        6,
        'round_of_32',
        { name: 'PDA team', id: 11 },
        { name: 'X', id: 12 },
        { tournament_round_order: 5 }
      ),
      mkMatch(
        7,
        'round_of_32',
        { name: 'IFA team', id: 13 },
        { name: 'Y', id: 14 },
        { tournament_round_order: 15 }
      ),
      mkMatch(
        50,
        'round_of_16',
        { name: 'PDA team', id: 11 },
        { name: 'IFA team', id: 13 },
        { tournament_round_order: 3 }
      ),
    ];
    const wrapper = mount(TournamentBracket, { props: { matches } });

    expect(slotOf(wrapper, 'r16', 'PDA team')).toBe(3);
  });

  it('mixes explicit order on some matches with feeder/id-order on others', () => {
    /**
     * Match A has explicit order=4, match B has no order — explicit takes
     * the named slot, B falls back to the next available slot in id order.
     */
    const matches = [
      mkMatch(
        1,
        'round_of_32',
        { name: 'A', id: 1 },
        { name: 'B', id: 2 },
        { tournament_round_order: 4 }
      ),
      mkMatch(2, 'round_of_32', { name: 'C', id: 3 }, { name: 'D', id: 4 }),
    ];
    const wrapper = mount(TournamentBracket, { props: { matches } });

    expect(slotOf(wrapper, 'r32', 'A')).toBe(4);
    // Match without explicit order takes the first empty slot (0).
    expect(slotOf(wrapper, 'r32', 'C')).toBe(0);
  });

  it('empty-state still shows when there are no R32 matches at all', () => {
    const wrapper = mount(TournamentBracket, { props: { matches: [] } });
    expect(wrapper.text()).toContain('No matches in this bracket yet');
  });
});

// ── SB-119: compact bracket (smaller than 32 teams) ──────────────────────────
// These tests guard the new compact rendering path introduced so brackets that
// start at the Semifinals or Final (e.g. NAC BU15 HG) no longer fall through
// to the empty state.

describe('TournamentBracket — SB-119 compact path', () => {
  // Reuse mkMatch from the outer scope (same module).

  // Case 1: completely empty matches array → empty state.
  it('renders empty state when matches is empty', () => {
    const wrapper = mount(TournamentBracket, { props: { matches: [] } });
    expect(wrapper.text()).toContain('No matches in this bracket yet.');
    expect(wrapper.find('.bracket-grid-compact').exists()).toBe(false);
    expect(wrapper.find('.bracket-grid').exists()).toBe(false);
  });

  // Case 2: only group_stage / wildcard rounds → still empty state (excluded
  // from bracket computation entirely).
  it('renders empty state when only group_stage/wildcard matches are present', () => {
    const matches = [
      mkMatch(1, 'group_stage', 'Alpha', 'Bravo'),
      mkMatch(2, 'wildcard', 'Charlie', 'Delta'),
    ];
    const wrapper = mount(TournamentBracket, { props: { matches } });
    expect(wrapper.text()).toContain('No matches in this bracket yet.');
    expect(wrapper.find('.bracket-grid-compact').exists()).toBe(false);
  });

  // Case 3: SF + Final only (NAC BU15 HG scenario).
  it('renders compact grid for SF + Final bracket, not full grid, not empty', () => {
    const matches = [
      mkMatch(10, 'semifinal', 'Red FC', 'Blue SC', {
        tournament_round_order: 0,
      }),
      mkMatch(11, 'semifinal', 'Green United', 'Yellow City', {
        tournament_round_order: 1,
      }),
      mkMatch(20, 'final', 'Red FC', 'Green United'),
    ];
    const wrapper = mount(TournamentBracket, { props: { matches } });

    // Not empty state.
    expect(wrapper.text()).not.toContain('No matches in this bracket yet.');

    // Compact grid rendered, full grid absent.
    expect(wrapper.find('.bracket-grid-compact').exists()).toBe(true);
    expect(wrapper.find('.bracket-grid').exists()).toBe(false);

    // Exactly 2 column headers: "Semifinals" and "Final".
    const headers = wrapper.findAll('.bracket-header');
    expect(headers).toHaveLength(2);
    expect(headers[0].text()).toBe('Semifinals');
    expect(headers[1].text()).toBe('Final');

    // All 3 matches produce a populated cell.
    const cells = wrapper.findAll('.bracket-cell-compact');
    expect(cells).toHaveLength(3);

    // All four team names appear somewhere in the compact grid.
    const gridText = wrapper.find('.bracket-grid-compact').text();
    expect(gridText).toContain('Red FC');
    expect(gridText).toContain('Blue SC');
    expect(gridText).toContain('Green United');
    expect(gridText).toContain('Yellow City');

    // The final cell is the last compact cell and carries isFinal styling
    // (the BracketCell renders a button for real matches; verify the final
    // match teams appear in the final column position).
    expect(gridText).toContain('Red FC');
    expect(gridText).toContain('Green United');
  });

  // Case 4: Final-only bracket (BU15 HG edge case with single match).
  it('renders compact grid for a Final-only bracket', () => {
    const matches = [mkMatch(99, 'final', 'Finale Home', 'Finale Away')];
    const wrapper = mount(TournamentBracket, { props: { matches } });

    expect(wrapper.text()).not.toContain('No matches in this bracket yet.');
    expect(wrapper.find('.bracket-grid-compact').exists()).toBe(true);
    expect(wrapper.find('.bracket-grid').exists()).toBe(false);

    // Only 1 column header.
    const headers = wrapper.findAll('.bracket-header');
    expect(headers).toHaveLength(1);
    expect(headers[0].text()).toBe('Final');

    // Both teams visible.
    const gridText = wrapper.find('.bracket-grid-compact').text();
    expect(gridText).toContain('Finale Home');
    expect(gridText).toContain('Finale Away');
  });

  // Case 5: when R32 matches are present the existing FULL bracket path
  // still wins — compact must not take over.
  it('renders the full bracket grid (not compact) when R32 matches are present', () => {
    const matches = [
      mkMatch(1, 'round_of_32', 'Team A', 'Team B'),
      mkMatch(2, 'semifinal', 'Team X', 'Team Y'),
    ];
    const wrapper = mount(TournamentBracket, { props: { matches } });

    expect(wrapper.find('.bracket-grid').exists()).toBe(true);
    expect(wrapper.find('.bracket-grid-compact').exists()).toBe(false);
    expect(wrapper.text()).not.toContain('No matches in this bracket yet.');
  });

  // Case 6: compactLayout geometry assertions via wrapper.vm for SF + Final.
  it('computes correct compactLayout geometry for SF+Final bracket', () => {
    const matches = [
      mkMatch(10, 'semifinal', 'Alpha FC', 'Beta SC', {
        tournament_round_order: 0,
      }),
      mkMatch(11, 'semifinal', 'Gamma United', 'Delta City', {
        tournament_round_order: 1,
      }),
      mkMatch(20, 'final', 'Alpha FC', 'Gamma United'),
    ];
    const wrapper = mount(TournamentBracket, { props: { matches } });

    const layout = wrapper.vm.compactLayout;
    expect(layout).not.toBeNull();

    // 2 SFs → firstRoundIdx points at 'semifinal' (index 3 in roundCells),
    // so rounds.length = 2 (SF + Final).
    expect(layout.nCols).toBe(2);
    expect(layout.headers).toEqual(['Semifinals', 'Final']);

    // firstSlots = 2 (two SF cells), totalRows = 2 * 2 = 4.
    expect(layout.totalRows).toBe(4);

    // items: 2 SF items + 1 Final item = 3 total.
    expect(layout.items).toHaveLength(3);

    // SF items: rowsPerCell = 4/2 = 2.
    const sf0 = layout.items.find(it => it.key === 'semifinal-0');
    const sf1 = layout.items.find(it => it.key === 'semifinal-1');
    const fin = layout.items.find(it => it.key === 'final-0');

    expect(sf0).toBeDefined();
    expect(sf1).toBeDefined();
    expect(fin).toBeDefined();

    // SF0: col 1, rowStart 2 (header at row 1), rowSpan 2.
    expect(sf0.col).toBe(1);
    expect(sf0.rowStart).toBe(2);
    expect(sf0.rowSpan).toBe(2);

    // SF1: col 1, rowStart 4, rowSpan 2.
    expect(sf1.col).toBe(1);
    expect(sf1.rowStart).toBe(4);
    expect(sf1.rowSpan).toBe(2);

    // Final: col 2, rowStart 2, rowSpan 4 (totalRows).
    expect(fin.col).toBe(2);
    expect(fin.rowStart).toBe(2);
    expect(fin.rowSpan).toBe(4);
    expect(fin.isFinal).toBe(true);

    // showBridge: exactly one item has showBridge true — the top SF (d=0, i=0).
    const bridgeItems = layout.items.filter(it => it.showBridge);
    expect(bridgeItems).toHaveLength(1);
    expect(bridgeItems[0].key).toBe('semifinal-0');
  });
});
