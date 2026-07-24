// SB-288: lineup player-selector position-group filtering.
import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import LineupManager from '@/components/live/LineupManager.vue';
import { SLOT_TO_GROUP } from '@/constants/positions';
import { getFormations, FUTSAL_FORMATIONS } from '@/config/formations';

const ROSTER = [
  { id: 1, jersey_number: 1, display_name: 'Keeper One', positions: ['GK'] },
  { id: 2, jersey_number: 4, display_name: 'Def Two', positions: ['CB', 'RB'] },
  { id: 3, jersey_number: 8, display_name: 'Mid Three', positions: ['CM'] },
  { id: 4, jersey_number: 9, display_name: 'Fwd Four', positions: ['ST'] },
  { id: 5, jersey_number: 13, display_name: 'Blank Five', positions: null },
  {
    id: 6,
    jersey_number: 7,
    display_name: 'Legacy Six',
    positions: ['LCB'], // legacy code -> CB -> DEF
  },
];

const mountLineup = () =>
  mount(LineupManager, {
    props: { teamId: 19, roster: ROSTER },
  });

const openSlot = async (wrapper, position) => {
  wrapper
    .findComponent({ name: 'FormationField' })
    .vm.$emit('position-clicked', position);
  await wrapper.vm.$nextTick();
};

describe('LineupManager position filtering (SB-288)', () => {
  it('shows only goalkeepers for the GK slot (hard filter)', async () => {
    const wrapper = mountLineup();
    await openSlot(wrapper, 'GK');

    const suggested = wrapper
      .findAll('.player-option.suggested')
      .map(b => b.text());
    expect(suggested).toHaveLength(1);
    expect(suggested[0]).toContain('Keeper One');

    // Hard filter: non-goalkeepers (incl. the no-positions player) are hidden.
    const others = wrapper.findAll(
      '.player-option:not(.suggested):not(.clear-option)'
    );
    expect(others).toHaveLength(0);
  });

  it('falls back to the full list when no roster player fits the slot', async () => {
    // Roster of only a defender + a forward, click the GK slot -> nobody fits.
    const wrapper = mount(LineupManager, {
      props: {
        teamId: 19,
        roster: [
          {
            id: 2,
            jersey_number: 4,
            display_name: 'Def Two',
            positions: ['CB'],
          },
          {
            id: 4,
            jersey_number: 9,
            display_name: 'Fwd Four',
            positions: ['ST'],
          },
        ],
      },
    });
    await openSlot(wrapper, 'GK');

    // No suggested (nobody is a GK), but both are offered as a fallback.
    expect(wrapper.findAll('.player-option.suggested')).toHaveLength(0);
    const fallback = wrapper
      .findAll('.player-option:not(.suggested):not(.clear-option)')
      .map(b => b.text());
    expect(fallback.some(t => t.includes('Def Two'))).toBe(true);
    expect(fallback.some(t => t.includes('Fwd Four'))).toBe(true);
  });

  it('maps side-specific slot codes to groups (LCB slot suggests defenders, incl. legacy codes)', async () => {
    const wrapper = mountLineup();
    await openSlot(wrapper, 'LCB');

    const suggested = wrapper
      .findAll('.player-option.suggested')
      .map(b => b.text());
    expect(suggested.some(t => t.includes('Def Two'))).toBe(true);
    // Legacy 'LCB' player position remaps to CB -> DEF group.
    expect(suggested.some(t => t.includes('Legacy Six'))).toBe(true);
    expect(suggested.some(t => t.includes('Keeper One'))).toBe(false);
  });

  it('suggests forwards for the ST slot', async () => {
    const wrapper = mountLineup();
    await openSlot(wrapper, 'ST');

    const suggested = wrapper
      .findAll('.player-option.suggested')
      .map(b => b.text());
    expect(suggested).toHaveLength(1);
    expect(suggested[0]).toContain('Fwd Four');
  });

  it('jersey entry: a known number picks that roster player', async () => {
    const wrapper = mountLineup();
    await openSlot(wrapper, 'ST');
    await wrapper.find('.jersey-input').setValue('9'); // Fwd Four
    await wrapper.find('.jersey-add').trigger('click');

    const events = wrapper.emitted('change');
    const last = events[events.length - 1][0];
    const st = last.positions.find(p => p.position === 'ST');
    expect(st.player_id).toBe(4);
  });

  it('jersey entry: an unknown number becomes a placeholder (negative id)', async () => {
    const wrapper = mountLineup();
    await openSlot(wrapper, 'ST');
    await wrapper.find('.jersey-input').setValue('77'); // not on the roster
    await wrapper.find('.jersey-add').trigger('click');

    const events = wrapper.emitted('change');
    const last = events[events.length - 1][0];
    const st = last.positions.find(p => p.position === 'ST');
    expect(st.player_id).toBe(-77);
    expect(st.jersey_number).toBe(77);
  });

  it('every formation slot code (soccer + futsal) has a SLOT_TO_GROUP entry', () => {
    const slotCodes = new Set();
    for (const formations of [getFormations('soccer'), FUTSAL_FORMATIONS]) {
      for (const formation of Object.values(formations)) {
        for (const slot of formation.positions ?? formation) {
          if (slot?.position) slotCodes.add(slot.position);
        }
      }
    }
    expect(slotCodes.size).toBeGreaterThan(0);
    for (const code of slotCodes) {
      expect(
        SLOT_TO_GROUP[code],
        `missing SLOT_TO_GROUP for ${code}`
      ).toBeTruthy();
    }
  });
});
