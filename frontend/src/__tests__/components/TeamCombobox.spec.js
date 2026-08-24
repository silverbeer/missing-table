/**
 * TeamCombobox.vue tests (SB-817).
 *
 * The point of the component is that an opponent already in MT gets picked
 * rather than retyped, and that creating a brand-new team is a deliberate act
 * instead of the side effect of a typo.
 *
 * Covers:
 * - Filtering by typed text, and by age group
 * - Selecting a team emits its id and clears any pending create name
 * - The create row only appears when nothing matches exactly, and emits the name
 * - Editing after a selection invalidates that selection
 * - Keyboard: arrows move the active option, Enter selects
 * - Lightweight (no-league) teams are badged so they are distinguishable
 */

import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';

import TeamCombobox from '@/components/ui/TeamCombobox.vue';

const TEAMS = [
  {
    id: 1,
    name: 'Cedar Stars Academy',
    league_id: 2,
    league_name: 'MLS Next',
    age_groups: [{ id: 3, name: 'U15' }],
  },
  {
    id: 2,
    name: 'Cedar Stars Bergen',
    league_id: null,
    age_groups: [{ id: 3, name: 'U15' }],
  },
  {
    id: 3,
    name: 'Oakwood SC',
    league_id: 2,
    league_name: 'MLS Next',
    age_groups: [{ id: 4, name: 'U16' }],
  },
];

const mountBox = (props = {}) =>
  mount(TeamCombobox, { props: { teams: TEAMS, ...props } });

// The row renders "<name><badge>" with no separator, so read the name span.
const optionText = wrapper =>
  wrapper
    .findAll('[data-testid="team-combobox-option"]')
    .map(n => n.findAll('span')[0].text().trim());

const type = async (wrapper, text) => {
  const input = wrapper.find('[data-testid="team-combobox-input"]');
  await input.setValue(text);
  return input;
};

describe('TeamCombobox filtering', () => {
  it('lists teams matching the typed text', async () => {
    const wrapper = mountBox();
    await type(wrapper, 'cedar');

    expect(optionText(wrapper)).toEqual([
      'Cedar Stars Academy',
      'Cedar Stars Bergen',
    ]);
  });

  it('narrows the list to the selected age group', async () => {
    const wrapper = mountBox({ ageGroupId: 4 });
    await type(wrapper, 'a');

    expect(optionText(wrapper)).toEqual(['Oakwood SC']);
  });

  it('keeps teams whose age groups are unknown rather than hiding them', async () => {
    const wrapper = mountBox({
      teams: [{ id: 9, name: 'Mystery FC', league_id: null }],
      ageGroupId: 3,
    });
    await type(wrapper, 'mystery');

    expect(optionText(wrapper)).toEqual(['Mystery FC']);
  });

  it('badges a team with no league as tournament-only', async () => {
    const wrapper = mountBox();
    await type(wrapper, 'cedar');

    const rows = wrapper.findAll('[data-testid="team-combobox-option"]');
    expect(rows[0].text()).toContain('MLS Next');
    expect(rows[1].text()).toContain('tournament');
  });
});

describe('TeamCombobox selection', () => {
  it('emits the team id and fills the input with its name', async () => {
    const wrapper = mountBox();
    await type(wrapper, 'oak');
    await wrapper
      .find('[data-testid="team-combobox-option"]')
      .trigger('mousedown');

    expect(wrapper.emitted('update:modelValue').at(-1)).toEqual([3]);
    expect(wrapper.emitted('update:createName').at(-1)).toEqual(['']);
  });

  it('shows the confirmed selection', async () => {
    const wrapper = mountBox({ modelValue: 1 });

    expect(
      wrapper.find('[data-testid="team-combobox-selected"]').text()
    ).toContain('Cedar Stars Academy');
  });

  it('clears a prior selection as soon as the text is edited', async () => {
    const wrapper = mountBox({ modelValue: 3 });
    await type(wrapper, 'oakwood united');

    expect(wrapper.emitted('update:modelValue').at(-1)).toEqual([null]);
  });
});

describe('TeamCombobox create path', () => {
  it('offers a create row when nothing matches', async () => {
    const wrapper = mountBox();
    await type(wrapper, 'Brand New FC');

    const create = wrapper.find('[data-testid="team-combobox-create"]');
    expect(create.exists()).toBe(true);
    expect(create.text()).toContain('Brand New FC');
  });

  it('does not offer to create a name that already exists exactly', async () => {
    const wrapper = mountBox();
    await type(wrapper, 'Oakwood SC');

    expect(wrapper.find('[data-testid="team-combobox-create"]').exists()).toBe(
      false
    );
  });

  it('emits the name only when the create row is clicked', async () => {
    const wrapper = mountBox();
    await type(wrapper, 'Brand New FC');

    // Typing alone must not propose creating anything: with nothing selected
    // there is nothing to clear, so the component stays silent.
    expect(wrapper.emitted('update:createName')).toBeUndefined();

    await wrapper
      .find('[data-testid="team-combobox-create"]')
      .trigger('mousedown');

    expect(wrapper.emitted('update:createName').at(-1)).toEqual([
      'Brand New FC',
    ]);
    expect(wrapper.emitted('update:modelValue').at(-1)).toEqual([null]);
  });

  it('suppresses the create row when creating is not allowed', async () => {
    const wrapper = mountBox({ allowCreate: false });
    await type(wrapper, 'Brand New FC');

    expect(wrapper.find('[data-testid="team-combobox-create"]').exists()).toBe(
      false
    );
  });

  it('shows the pending create state', () => {
    const wrapper = mountBox({ createName: 'Brand New FC' });

    expect(
      wrapper.find('[data-testid="team-combobox-create-pending"]').text()
    ).toContain('Brand New FC');
  });
});

describe('TeamCombobox keyboard', () => {
  it('moves through options with the arrow keys and selects with Enter', async () => {
    const wrapper = mountBox();
    const input = await type(wrapper, 'cedar');

    await input.trigger('keydown', { key: 'ArrowDown' });
    await input.trigger('keydown', { key: 'Enter' });

    expect(wrapper.emitted('update:modelValue').at(-1)).toEqual([2]);
  });

  it('closes the list on Escape without selecting', async () => {
    const wrapper = mountBox();
    const input = await type(wrapper, 'cedar');

    await input.trigger('keydown', { key: 'Escape' });

    expect(wrapper.find('[data-testid="team-combobox-list"]').exists()).toBe(
      false
    );
    // Escape abandons the list without picking anything.
    expect(wrapper.emitted('update:modelValue')).toBeUndefined();
  });
});
