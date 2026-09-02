/**
 * SearchSelect.vue tests (SB-964).
 *
 * The generic combobox shell TeamCombobox and ClubCombobox both wrap: it owns
 * the query text, open state and keyboard handling, and takes an
 * already-filtered/capped `options` array from the parent so it stays
 * domain-agnostic.
 *
 * Covers:
 * - Rendering the parent-supplied, already-filtered options (no filtering
 *   logic of its own)
 * - Selecting an option emits its id and shows the confirmed selection
 * - Typing after a selection clears it
 * - Keyboard: arrows move, Enter selects, Escape closes
 * - Custom #option/#selected slots render instead of the plain label
 */

import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import { h } from 'vue';

import SearchSelect from '@/components/ui/SearchSelect.vue';

const OPTIONS = [
  { id: 1, name: 'Alpha' },
  { id: 2, name: 'Beta' },
  { id: 3, name: 'Gamma' },
];

const mountBox = (props = {}) =>
  mount(SearchSelect, {
    props: { options: OPTIONS, testidPrefix: 'search-select', ...props },
  });

const type = async (wrapper, text) => {
  const input = wrapper.find('[data-testid="search-select-input"]');
  await input.setValue(text);
  return input;
};

describe('SearchSelect rendering', () => {
  it('renders the options it is given, unfiltered', async () => {
    const wrapper = mountBox();
    await type(wrapper, 'anything'); // opens the list; filtering is the parent's job

    const rows = wrapper.findAll('[data-testid="search-select-option"]');
    expect(rows.map(r => r.text())).toEqual(['Alpha', 'Beta', 'Gamma']);
  });

  it('stays closed until the input is focused or edited', () => {
    const wrapper = mountBox();
    expect(wrapper.find('[data-testid="search-select-list"]').exists()).toBe(
      false
    );
  });
});

describe('SearchSelect selection', () => {
  it('emits the option id and fills the input with its label', async () => {
    const wrapper = mountBox();
    await type(wrapper, 'be');
    await wrapper
      .findAll('[data-testid="search-select-option"]')[1]
      .trigger('mousedown');

    expect(wrapper.emitted('update:modelValue').at(-1)).toEqual([2]);
    expect(
      wrapper.find('[data-testid="search-select-input"]').element.value
    ).toBe('Beta');
  });

  it('shows the confirmed selection', () => {
    const wrapper = mountBox({ modelValue: 3 });

    expect(
      wrapper.find('[data-testid="search-select-selected"]').text()
    ).toContain('Gamma');
  });

  it('clears a prior selection as soon as the text is edited', async () => {
    const wrapper = mountBox({ modelValue: 1 });
    await type(wrapper, 'Alphabet');

    expect(wrapper.emitted('update:modelValue').at(-1)).toEqual([null]);
  });

  it('emits the typed text via update:query', async () => {
    const wrapper = mountBox();
    await type(wrapper, 'gam');

    expect(wrapper.emitted('update:query').at(-1)).toEqual(['gam']);
  });
});

describe('SearchSelect keyboard', () => {
  it('moves through options with the arrow keys and selects with Enter', async () => {
    const wrapper = mountBox();
    const input = await type(wrapper, 'a');

    await input.trigger('keydown', { key: 'ArrowDown' });
    await input.trigger('keydown', { key: 'Enter' });

    expect(wrapper.emitted('update:modelValue').at(-1)).toEqual([2]);
  });

  it('wraps backwards with the up arrow', async () => {
    const wrapper = mountBox();
    const input = await type(wrapper, 'a');

    // From the default active index (0), one step up should wrap to the
    // last option (Gamma, id 3) rather than going negative.
    await input.trigger('keydown', { key: 'ArrowUp' });
    await input.trigger('keydown', { key: 'Enter' });

    expect(wrapper.emitted('update:modelValue').at(-1)).toEqual([3]);
  });

  it('closes the list on Escape without selecting', async () => {
    const wrapper = mountBox();
    const input = await type(wrapper, 'a');

    await input.trigger('keydown', { key: 'Escape' });

    expect(wrapper.find('[data-testid="search-select-list"]').exists()).toBe(
      false
    );
    expect(wrapper.emitted('update:modelValue')).toBeUndefined();
  });
});

describe('SearchSelect resolveLabel', () => {
  // Regression for a known SB-964 edge case: a parent's `options` array can
  // be capped (ClubCombobox/TeamCombobox both slice to maxOptions), so a
  // pre-selected id from outside that cap isn't always findable in it.
  // `resolveLabel` lets the parent resolve the label from its full,
  // unfiltered list instead.
  it('prefers resolveLabel over searching the (possibly capped) options array', () => {
    const wrapper = mount(SearchSelect, {
      props: {
        options: [{ id: 1, name: 'Alpha' }], // does not contain id 99
        testidPrefix: 'search-select',
        modelValue: 99,
        resolveLabel: id => (id === 99 ? 'Outside The Cap' : undefined),
      },
    });

    expect(
      wrapper.find('[data-testid="search-select-input"]').element.value
    ).toBe('Outside The Cap');
  });

  it('falls back to searching options when resolveLabel finds nothing', () => {
    const wrapper = mount(SearchSelect, {
      props: {
        options: OPTIONS,
        testidPrefix: 'search-select',
        modelValue: 2,
        resolveLabel: () => undefined,
      },
    });

    expect(
      wrapper.find('[data-testid="search-select-input"]').element.value
    ).toBe('Beta');
  });

  it('does not clobber a keystroke made right after a resolveLabel pre-fill', async () => {
    // The bug this guards against: resolving the label by folding the
    // selected item into `options` (rather than via this separate prop)
    // caused the label-resolution watch to refire on every keystroke
    // (since `options` also drives filtering) and overwrite the very first
    // character the user typed.
    const wrapper = mount(SearchSelect, {
      props: {
        options: [{ id: 1, name: 'Alpha' }],
        testidPrefix: 'search-select',
        modelValue: 99,
        resolveLabel: id => (id === 99 ? 'Outside The Cap' : undefined),
      },
    });
    const input = wrapper.find('[data-testid="search-select-input"]');
    expect(input.element.value).toBe('Outside The Cap');

    await input.setValue('x');

    expect(input.element.value).toBe('x');
  });

  it('re-resolves query.value when options change even though resolveLabel still resolves (SB-964 stale label)', async () => {
    // Regression: the options-change watch used to bail out as soon as
    // resolveLabel resolved *anything*, on the assumption a resolvable label
    // meant nothing to do. But resolveLabel can resolve a different, freshly
    // correct label for the same still-valid id (e.g. TeamCombobox's
    // labelFormatter after an age-group filter change) — that label must
    // still get written to query.value.
    let label = 'Old Label';
    const wrapper = mount(SearchSelect, {
      props: {
        options: [{ id: 1, name: 'Alpha' }],
        testidPrefix: 'search-select',
        modelValue: 1,
        resolveLabel: () => label,
      },
    });

    expect(
      wrapper.find('[data-testid="search-select-input"]').element.value
    ).toBe('Old Label');

    label = 'New Label';
    await wrapper.setProps({ options: [{ id: 1, name: 'Alpha' }] });

    expect(
      wrapper.find('[data-testid="search-select-input"]').element.value
    ).toBe('New Label');
  });
});

describe('SearchSelect resolveOption', () => {
  // Regression for the sibling of the resolveLabel edge case above: the
  // "✓ selected" confirmation line used to look the id up only in the
  // (possibly capped) `options` array, so it could disappear for a
  // pre-selected item that resolveLabel still correctly displays in the
  // input itself.
  it('prefers resolveOption over searching the (possibly capped) options array', () => {
    const wrapper = mount(SearchSelect, {
      props: {
        options: [{ id: 1, name: 'Alpha' }], // does not contain id 99
        testidPrefix: 'search-select',
        modelValue: 99,
        resolveLabel: id => (id === 99 ? 'Outside The Cap' : undefined),
        resolveOption: id =>
          id === 99 ? { id: 99, name: 'Outside The Cap' } : null,
      },
    });

    expect(
      wrapper.find('[data-testid="search-select-selected"]').text()
    ).toContain('Outside The Cap');
  });

  it('falls back to searching options when resolveOption finds nothing', () => {
    const wrapper = mount(SearchSelect, {
      props: {
        options: OPTIONS,
        testidPrefix: 'search-select',
        modelValue: 2,
        resolveOption: () => null,
      },
    });

    expect(
      wrapper.find('[data-testid="search-select-selected"]').text()
    ).toContain('Beta');
  });
});

describe('SearchSelect dark mode', () => {
  // SB-964 replaced a bare native <select> (no dark-mode styling at all,
  // SB-940) with this control specifically so Matches -> My Club picks up
  // theming. Assert the input and option rows use theme tokens (bg-card,
  // text-fg, border-line, bg-brand-*) rather than hardcoded Tailwind grays
  // that would only look right in light mode.
  it('styles the input with theme tokens, not hardcoded colors', () => {
    const wrapper = mountBox();
    const input = wrapper.find('[data-testid="search-select-input"]');

    expect(input.classes()).toEqual(
      expect.arrayContaining(['bg-card', 'text-fg', 'border-line'])
    );
    expect(input.classes().join(' ')).not.toMatch(/bg-white|bg-gray-\d/);
  });

  it('styles the active option row with a dark-mode variant', async () => {
    const wrapper = mountBox();
    const input = await type(wrapper, 'a');
    await input.trigger('keydown', { key: 'ArrowDown' });

    const active = wrapper.findAll('[data-testid="search-select-option"]')[1];
    expect(active.classes().join(' ')).toMatch(/dark:bg-brand-500\/15/);
  });
});

describe('SearchSelect slots', () => {
  it('renders custom #option and #selected slot content in place of the label', async () => {
    const wrapper = mount(SearchSelect, {
      props: { options: OPTIONS, testidPrefix: 'search-select', modelValue: 1 },
      slots: {
        option: props => h('span', `Row: ${props.option.name}`),
        selected: props => h('span', `Picked: ${props.option.name}`),
      },
    });
    await type(wrapper, 'a');

    expect(
      wrapper.find('[data-testid="search-select-selected"]').text()
    ).toContain('Picked: Alpha');
    expect(wrapper.text()).toContain('Row: Alpha');
  });
});
