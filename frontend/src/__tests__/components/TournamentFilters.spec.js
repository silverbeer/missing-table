/**
 * TournamentFilters.vue — Age Group and Group controls for a large
 * tournament (SB-1749).
 *
 * The Group control has three states and only one of them renders: a list
 * shows it; an empty list (this age has no groups) and null (not known) both
 * hide it. A count is shown only when there is one — never "(0)" for unknown.
 */

import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import TournamentFilters from '@/components/TournamentFilters.vue';

const AGES = [
  { id: 5, name: 'U13', matches: 412 },
  { id: 7, name: 'U15', matches: 380 },
];
const GROUPS = [
  { key: 'AD · A', division: 'AD', label: 'A', matches: 5 },
  { key: 'HD · A', division: 'HD', label: 'A', matches: 6 },
];

const mountWith = props =>
  mount(TournamentFilters, {
    props: { ageGroups: AGES, selectedAgeGroupId: 5, ...props },
  });

const ageSelect = w => w.find('[data-testid="tournament-age-group-select"]');
const groupSelect = w => w.find('[data-testid="tournament-group-select"]');

describe('TournamentFilters — Age Group', () => {
  it('lists every age group with its match count and no "all ages"', () => {
    const w = mountWith({ groups: [] });
    const options = ageSelect(w).findAll('option');
    expect(options.map(o => o.text())).toEqual(['U13 (412)', 'U15 (380)']);
    expect(ageSelect(w).element.value).toBe('5');
  });

  it('emits the chosen age group id as a number', async () => {
    const w = mountWith({ groups: [] });
    await ageSelect(w).setValue('7');
    expect(w.emitted('update:ageGroup')).toEqual([[7]]);
  });

  it('shows no number when the count is unknown', () => {
    const w = mountWith({
      ageGroups: [
        { id: 5, name: 'U13', matches: null },
        { id: 7, name: 'U15' },
      ],
      groups: null,
    });
    expect(
      ageSelect(w)
        .findAll('option')
        .map(o => o.text())
    ).toEqual(['U13', 'U15']);
    expect(w.text()).not.toContain('0');
  });

  it('shows a real zero when the server counted none', () => {
    const w = mountWith({
      ageGroups: [{ id: 5, name: 'U13', matches: 0 }],
      groups: [],
    });
    expect(ageSelect(w).find('option').text()).toBe('U13 (0)');
  });
});

describe('TournamentFilters — Group', () => {
  it('lists groups by their namespaced key', () => {
    const w = mountWith({ groups: GROUPS });
    expect(
      groupSelect(w)
        .findAll('option')
        .map(o => o.text())
    ).toEqual(['All groups', 'AD · A (5)', 'HD · A (6)']);
  });

  it('emits the group key, and null for "All groups"', async () => {
    const w = mountWith({ groups: GROUPS, selectedGroup: null });
    await groupSelect(w).setValue('HD · A');
    await groupSelect(w).setValue('');
    expect(w.emitted('update:group')).toEqual([['HD · A'], [null]]);
  });

  it('reflects the selected group', () => {
    const w = mountWith({ groups: GROUPS, selectedGroup: 'AD · A' });
    expect(groupSelect(w).element.value).toBe('AD · A');
  });

  it('is hidden when the age group has no groups', () => {
    const w = mountWith({ groups: [] });
    expect(groupSelect(w).exists()).toBe(false);
    expect(w.find('label[for="tournament-group"]').exists()).toBe(false);
  });

  it('is hidden when the groups are unknown, without claiming there are none', () => {
    const w = mountWith({ groups: null });
    expect(groupSelect(w).exists()).toBe(false);
    expect(w.text().toLowerCase()).not.toContain('no groups');
  });

  it('shows a group without a count when it was not counted', () => {
    const w = mountWith({
      groups: [{ key: 'HD · A', division: 'HD', label: 'A', matches: null }],
    });
    expect(groupSelect(w).findAll('option')[1].text()).toBe('HD · A');
  });
});
