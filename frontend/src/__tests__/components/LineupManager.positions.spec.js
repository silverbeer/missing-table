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
  it('suggests only goalkeepers for the GK slot, others remain selectable', async () => {
    const wrapper = mountLineup();
    await openSlot(wrapper, 'GK');

    const suggested = wrapper
      .findAll('.player-option.suggested')
      .map(b => b.text());
    expect(suggested).toHaveLength(1);
    expect(suggested[0]).toContain('Keeper One');

    // Everyone else, including the no-positions player, stays selectable.
    const others = wrapper
      .findAll('.player-option:not(.suggested):not(.clear-option)')
      .map(b => b.text());
    expect(others.some(t => t.includes('Blank Five'))).toBe(true);
    expect(others.some(t => t.includes('Def Two'))).toBe(true);
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
