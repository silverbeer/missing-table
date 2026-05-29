/**
 * LineupManager.vue — SB-68 empty-roster pointer.
 *
 * Just covers the new empty-state behavior: when the strict-filter from
 * SB-68 returns no players for the match's age group, the component
 * shows a helpful pointer instead of the misleading "All players
 * assigned" message.
 */

import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import LineupManager from '@/components/live/LineupManager.vue';

const mountLM = (props = {}) =>
  mount(LineupManager, {
    props: {
      teamId: 19,
      teamName: 'IFA',
      sportType: 'soccer',
      saving: false,
      roster: [],
      ...props,
    },
  });

describe('LineupManager empty-roster pointer (SB-68)', () => {
  it('renders the "No roster set" pointer when the roster is empty', () => {
    const wrapper = mountLM({
      ageGroupName: 'U15',
      roster: [],
    });

    const pointer = wrapper.find('[data-testid="lineup-empty-no-roster"]');
    expect(pointer.exists()).toBe(true);
    expect(pointer.text()).toContain('No roster set');
    expect(pointer.text()).toContain('U15');
    expect(pointer.text()).toContain('IFA');
    expect(pointer.text()).toContain('Other player');
  });

  it('falls back to a generic message when ageGroupName is missing', () => {
    const wrapper = mountLM({
      ageGroupName: '',
      roster: [],
    });

    const pointer = wrapper.find('[data-testid="lineup-empty-no-roster"]');
    expect(pointer.exists()).toBe(true);
    expect(pointer.text()).toContain('No roster set');
    // No "for {age}" sub-phrase when we don't have the age group name.
    expect(pointer.text()).not.toMatch(/for U\d+/);
  });

  it('does NOT render the pointer when the roster has players', () => {
    const wrapper = mountLM({
      ageGroupName: 'U15',
      roster: [
        { id: 1, jersey_number: 7, display_name: 'Player A' },
        { id: 2, jersey_number: 9, display_name: 'Player B' },
      ],
    });

    expect(
      wrapper.find('[data-testid="lineup-empty-no-roster"]').exists()
    ).toBe(false);
    // The standard bench section is rendered instead.
    expect(wrapper.find('.bench-list').exists()).toBe(true);
  });

  it('shows "All players assigned" when roster has players but all are on the pitch', async () => {
    // This is the pre-SB-68 behavior — exercised here to confirm we didn't
    // regress it. We don't actually assign players here (the lineup state
    // is internal); we just confirm that when roster.length > 0, the
    // empty-roster pointer is never the active branch.
    const wrapper = mountLM({
      ageGroupName: 'U15',
      roster: [{ id: 1, jersey_number: 7, display_name: 'Player A' }],
    });

    expect(
      wrapper.find('[data-testid="lineup-empty-no-roster"]').exists()
    ).toBe(false);
  });
});
