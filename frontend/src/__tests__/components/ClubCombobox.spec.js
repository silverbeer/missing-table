/**
 * ClubCombobox.vue tests (SB-964).
 *
 * Matches → My Club replaced its bare native <select> with this type-and-search
 * control (the same pattern as TeamCombobox/Add Match), which is also how this
 * screen picks up dark-mode theming it never had as a native <select> (SB-940).
 *
 * Covers:
 * - Filtering by typed text, case-insensitive, with a capped option list
 * - Selecting a club emits its id and fills the input with its name
 * - Clearing the input clears the selection
 * - Keyboard: arrows move the active option, Enter selects, Escape closes
 */

import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';

import ClubCombobox from '@/components/ui/ClubCombobox.vue';

const CLUBS = [
  { id: 1, name: 'Blue Stars FC' },
  { id: 2, name: 'Red Hawks SC' },
  { id: 3, name: 'Green Valley United' },
];

const mountBox = (props = {}) =>
  mount(ClubCombobox, { props: { clubs: CLUBS, ...props } });

const optionText = wrapper =>
  wrapper
    .findAll('[data-testid="club-combobox-option"]')
    .map(n => n.text().trim());

const type = async (wrapper, text) => {
  const input = wrapper.find('[data-testid="club-combobox-input"]');
  await input.setValue(text);
  return input;
};

describe('ClubCombobox filtering', () => {
  it('stays closed until the input is focused or edited', () => {
    const wrapper = mountBox();
    expect(wrapper.find('[data-testid="club-combobox-list"]').exists()).toBe(
      false
    );
  });

  it('lists every club once opened with nothing typed', async () => {
    const wrapper = mountBox();
    await type(wrapper, '');

    expect(optionText(wrapper)).toEqual([
      'Blue Stars FC',
      'Red Hawks SC',
      'Green Valley United',
    ]);
  });

  it('filters clubs matching the typed text, case-insensitively', async () => {
    const wrapper = mountBox();
    await type(wrapper, 'star');

    expect(optionText(wrapper)).toEqual(['Blue Stars FC']);
  });

  it('caps the number of options offered', async () => {
    const manyClubs = Array.from({ length: 12 }, (_, i) => ({
      id: i + 1,
      name: `Club ${i + 1}`,
    }));
    const wrapper = mountBox({ clubs: manyClubs, maxOptions: 5 });
    await type(wrapper, 'club');

    expect(wrapper.findAll('[data-testid="club-combobox-option"]').length).toBe(
      5
    );
  });
});

describe('ClubCombobox pre-selection beyond the cap', () => {
  // Regression for a known SB-964 edge case: a club fan/manager can be
  // pre-selected (SB-599) into a club that sorts outside the first
  // `maxOptions` entries. SearchSelect resolves the displayed label from the
  // options array it is handed, so ClubCombobox must guarantee the selected
  // club is present in that array even before any query is typed — otherwise
  // the input renders blank despite the underlying id being correct.
  const manyClubs = Array.from({ length: 12 }, (_, i) => ({
    id: i + 1,
    name: `Club ${String(i + 1).padStart(2, '0')}`,
  }));

  it('shows the pre-selected club name even when it sorts past maxOptions', () => {
    const wrapper = mountBox({
      clubs: manyClubs,
      maxOptions: 8,
      modelValue: 12,
    });

    expect(
      wrapper.find('[data-testid="club-combobox-input"]').element.value
    ).toBe('Club 12');
    // Regression: the checkmark line used to look the id up only in the
    // capped `options` array, so it vanished even though the input above
    // (resolved separately via resolveLabel) still showed the right name.
    expect(
      wrapper.find('[data-testid="club-combobox-selected"]').text()
    ).toContain('Club 12');
  });

  it('still lists the pre-selected club in the open dropdown', async () => {
    const wrapper = mountBox({
      clubs: manyClubs,
      maxOptions: 8,
      modelValue: 12,
    });
    await wrapper.find('[data-testid="club-combobox-input"]').trigger('focus');

    expect(optionText(wrapper)).toContain('Club 12');
  });

  it('does not disturb the cap once the user starts typing', async () => {
    const wrapper = mountBox({
      clubs: manyClubs,
      maxOptions: 8,
      modelValue: 12,
    });
    await type(wrapper, 'club');

    expect(wrapper.findAll('[data-testid="club-combobox-option"]').length).toBe(
      8
    );
  });
});

describe('ClubCombobox selection', () => {
  it('emits the club id and fills the input with its name', async () => {
    const wrapper = mountBox();
    await type(wrapper, 'red');
    await wrapper
      .find('[data-testid="club-combobox-option"]')
      .trigger('mousedown');

    expect(wrapper.emitted('update:modelValue').at(-1)).toEqual([2]);
    expect(
      wrapper.find('[data-testid="club-combobox-input"]').element.value
    ).toBe('Red Hawks SC');
  });

  it('shows the confirmed selection', () => {
    const wrapper = mountBox({ modelValue: 3 });

    expect(
      wrapper.find('[data-testid="club-combobox-selected"]').text()
    ).toContain('Green Valley United');
  });

  it('clears the selection as soon as the text is edited', async () => {
    const wrapper = mountBox({ modelValue: 2 });
    await type(wrapper, 'red hawks united');

    expect(wrapper.emitted('update:modelValue').at(-1)).toEqual([null]);
  });

  it('clearing the input clears the selection', async () => {
    const wrapper = mountBox({ modelValue: 2 });
    await type(wrapper, '');

    expect(wrapper.emitted('update:modelValue').at(-1)).toEqual([null]);
  });
});

describe('ClubCombobox keyboard', () => {
  it('moves through options with the arrow keys and selects with Enter', async () => {
    const wrapper = mountBox();
    const input = await type(wrapper, '');

    await input.trigger('keydown', { key: 'ArrowDown' });
    await input.trigger('keydown', { key: 'Enter' });

    expect(wrapper.emitted('update:modelValue').at(-1)).toEqual([2]);
  });

  it('closes the list on Escape without selecting', async () => {
    const wrapper = mountBox();
    const input = await type(wrapper, 'blue');

    await input.trigger('keydown', { key: 'Escape' });

    expect(wrapper.find('[data-testid="club-combobox-list"]').exists()).toBe(
      false
    );
    expect(wrapper.emitted('update:modelValue')).toBeUndefined();
  });
});
