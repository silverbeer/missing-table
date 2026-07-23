// SB-288+: Auto-fill XI, grouped bench, and out-of-position flagging.
import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import LineupManager from '@/components/live/LineupManager.vue';

const ROSTER = [
  { id: 1, jersey_number: 1, display_name: 'Keeper One', positions: ['GK'] },
  { id: 2, jersey_number: 4, display_name: 'Def Two', positions: ['CB', 'RB'] },
  { id: 3, jersey_number: 8, display_name: 'Mid Three', positions: ['CM'] },
  { id: 4, jersey_number: 9, display_name: 'Fwd Four', positions: ['ST'] },
  { id: 5, jersey_number: 13, display_name: 'Blank Five', positions: null },
  { id: 6, jersey_number: 7, display_name: 'Legacy Six', positions: ['LCB'] },
];

const mountLineup = () =>
  mount(LineupManager, {
    props: { teamId: 19, roster: ROSTER }, // default 4-3-3 soccer formation
  });

const lastChange = wrapper => {
  const events = wrapper.emitted('change');
  return events[events.length - 1][0];
};

const posFor = (change, slot) =>
  change.positions.find(p => p.position === slot);

describe('LineupManager auto-fill (SB-288+)', () => {
  it('fills open slots best-fit-first: GK slot gets the keeper, DEF slots get defenders', async () => {
    const wrapper = mountLineup();
    await wrapper.find('.suggest-button').trigger('click');

    const change = lastChange(wrapper);
    // Keeper claims GK; a defender (primary DEF) claims a back-line slot.
    expect(posFor(change, 'GK').player_id).toBe(1);
    expect([2, 6]).toContain(posFor(change, 'LB').player_id);
    expect([2, 6]).toContain(posFor(change, 'LCB').player_id);
  });

  it('keeps existing assignments and only fills the empty slots', async () => {
    const wrapper = mountLineup();
    // Pre-assign the striker to GK (deliberately wrong) via the modal path.
    wrapper
      .findComponent({ name: 'FormationField' })
      .vm.$emit('position-clicked', 'GK');
    await wrapper.vm.$nextTick();
    await wrapper.findAll('.player-option')[1].trigger('click'); // first real player

    const before = posFor(lastChange(wrapper), 'GK').player_id;
    await wrapper.find('.suggest-button').trigger('click');
    expect(posFor(lastChange(wrapper), 'GK').player_id).toBe(before);
  });

  it('flags out-of-position assignments (group mismatch) but not players with no positions set', async () => {
    const wrapper = mountLineup();
    await wrapper.find('.suggest-button').trigger('click');

    const warn = wrapper
      .findComponent({ name: 'FormationField' })
      .props('warnPositions');

    // With only 6 players for 11 slots, outfielders backfill defensive slots.
    const change = lastChange(wrapper);
    for (const slot of warn) {
      const assigned = ROSTER.find(
        p => p.id === posFor(change, slot).player_id
      );
      expect(assigned.positions?.length ?? 0).toBeGreaterThan(0);
    }
    // The keeper in the GK slot is a correct fit, so it is never flagged.
    expect(warn).not.toContain('GK');
    // A player with no positions set is never flagged.
    const blankSlot = change.positions.find(p => p.player_id === 5);
    if (blankSlot) expect(warn).not.toContain(blankSlot.position);
  });

  it('groups the bench by position category with an "No position set" bucket', () => {
    const wrapper = mountLineup();
    const labels = wrapper.findAll('.bench-group-label').map(el => el.text());
    expect(labels).toEqual([
      'Goalkeepers',
      'Defenders',
      'Midfielders',
      'Forwards',
      'No position set',
    ]);
  });
});
