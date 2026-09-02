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

describe('TeamCombobox pre-selection beyond the cap', () => {
  // Regression for the same SB-964 edge case covered in ClubCombobox: a
  // pre-selected team (SB-599 auto-select) can sort outside the first
  // `maxOptions` rows once a club fields more teams than the cap.
  const manyTeams = Array.from({ length: 12 }, (_, i) => ({
    id: i + 1,
    name: `Team ${String(i + 1).padStart(2, '0')}`,
    league_id: 2,
    league_name: 'MLS Next',
  }));

  it('shows the pre-selected team name even when it sorts past maxOptions', () => {
    const wrapper = mountBox({
      teams: manyTeams,
      maxOptions: 8,
      modelValue: 12,
    });

    expect(
      wrapper.find('[data-testid="team-combobox-input"]').element.value
    ).toBe('Team 12');
    // Regression: the checkmark line used to look the id up only in the
    // capped `options` array, so it vanished even though the input above
    // (resolved separately via resolveLabel) still showed the right name.
    expect(
      wrapper.find('[data-testid="team-combobox-selected"]').text()
    ).toContain('Team 12');
  });

  it('honors labelFormatter for a pre-selected team beyond the cap', () => {
    const wrapper = mountBox({
      teams: manyTeams,
      maxOptions: 8,
      modelValue: 12,
      labelFormatter: team => `${team.name} (context)`,
    });

    expect(
      wrapper.find('[data-testid="team-combobox-input"]').element.value
    ).toBe('Team 12 (context)');
    expect(
      wrapper.find('[data-testid="team-combobox-selected"]').text()
    ).toContain('Team 12 (context)');
  });
});

describe('TeamCombobox stale label after context change', () => {
  // Regression: MatchesView's My Club tab selects a team via labelFormatter
  // (getTeamDisplayWithContext), which renders differently depending on the
  // currently-selected age group. Clicking a different age-group filter
  // button leaves the team selected (still present in the recomputed team
  // list) but recomputes that list to a new array reference; the displayed
  // label used to only get rewritten to query.value on the "resolveLabel
  // found nothing" fallback path, so a still-resolvable label whose *content*
  // had changed (a different age group's league/division) was never
  // re-written and stayed stale.
  it('re-resolves the selected team label when the label-formatter context changes', async () => {
    let context = 'Homegrown - Northeast';
    const wrapper = mountBox({
      modelValue: 1,
      labelFormatter: team => `${team.name} (${context})`,
    });

    expect(
      wrapper.find('[data-testid="team-combobox-input"]').element.value
    ).toBe('Cedar Stars Academy (Homegrown - Northeast)');

    // Simulate an age-group filter change: the label-formatter's own context
    // shifts (mirrors selectedAgeGroupId in MatchesView) and the parent hands
    // down a new `teams` array reference (mirrors filteredTeamsByLeague
    // recomputing) even though the same teams are still in it.
    context = 'Homegrown - Southeast';
    await wrapper.setProps({ teams: [...TEAMS] });

    expect(
      wrapper.find('[data-testid="team-combobox-input"]').element.value
    ).toBe('Cedar Stars Academy (Homegrown - Southeast)');
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
