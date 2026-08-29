/**
 * MatchEditModal identity + score labels (SB-911, SB-912).
 *
 * Teams are multi-age: one canonical "IFA" row covers U13-U19, so the same
 * clubs can meet twice on the same day at different age groups. The modal has
 * to say which of those it is editing, and its score inputs have to name the
 * team they belong to — "Home Score" alone made a 2-1 land as home 1 / away 2.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import MatchEditModal from '@/components/MatchEditModal.vue';

let mockAuthStore;

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => mockAuthStore,
}));

vi.mock('@/config/api', () => ({
  getApiBaseUrl: () => 'http://localhost:8000',
}));

const TEAMS = [
  { id: 19, name: 'IFA' },
  { id: 601, name: 'Northern Virginia Alliance' },
];

const match = (overrides = {}) => ({
  id: 6004,
  match_date: '2026-08-29',
  scheduled_kickoff: null,
  home_team_id: 19,
  away_team_id: 601,
  home_team_name: 'IFA',
  away_team_name: 'Northern Virginia Alliance',
  home_score: null,
  away_score: null,
  season_id: 184,
  age_group_id: 2,
  age_group_name: 'U14',
  match_type_id: 2,
  match_type_name: 'Tournament',
  division_id: null,
  match_status: 'scheduled',
  ...overrides,
});

const mountModal = (matchProp = match()) =>
  mount(MatchEditModal, {
    props: {
      show: true,
      match: matchProp,
      teams: TEAMS,
      seasons: [{ id: 184, name: '2026-2027' }],
      ageGroups: [
        { id: 2, name: 'U14' },
        { id: 3, name: 'U15' },
      ],
      matchTypes: [{ id: 2, name: 'Tournament' }],
      divisions: [],
    },
  });

beforeEach(() => {
  mockAuthStore = {
    isAdmin: { value: true },
    apiRequest: vi.fn().mockResolvedValue(TEAMS),
  };
});

describe('MatchEditModal identity', () => {
  it('names the fixture, age group and date being edited', async () => {
    const wrapper = mountModal();
    await flushPromises();

    const subtitle = wrapper.get('[data-testid="edit-modal-subtitle"]').text();
    expect(subtitle).toContain('IFA vs Northern Virginia Alliance');
    expect(subtitle).toContain('U14');
    expect(subtitle).toContain('2026-08-29');
  });

  it('labels each score input with its team and side', async () => {
    const wrapper = mountModal();
    await flushPromises();

    const home = wrapper.get('[data-testid="home-score-label"]').text();
    const away = wrapper.get('[data-testid="away-score-label"]').text();
    expect(home).toContain('IFA');
    expect(home).toContain('(home)');
    expect(away).toContain('Northern Virginia Alliance');
    expect(away).toContain('(away)');
  });

  it('follows the dropdowns when the sides are swapped', async () => {
    const wrapper = mountModal();
    await flushPromises();

    // Strings: a select's DOM value is a string, and vue-test-utils matches
    // the option by it — setValue(601) selects nothing.
    await wrapper.get('[data-testid="home-team-select"]').setValue('601');
    await wrapper.get('[data-testid="away-team-select"]').setValue('19');

    expect(wrapper.get('[data-testid="home-score-label"]').text()).toContain(
      'Northern Virginia Alliance'
    );
    expect(wrapper.get('[data-testid="away-score-label"]').text()).toContain(
      'IFA'
    );
  });

  it('falls back to the match names before the team list loads', async () => {
    mockAuthStore.apiRequest = vi.fn(() => new Promise(() => {}));
    const wrapper = mountModal();

    expect(wrapper.get('[data-testid="home-score-label"]').text()).toContain(
      'IFA'
    );
  });

  it('omits the age group when the match carries none', async () => {
    const wrapper = mountModal(match({ age_group_name: undefined }));
    await flushPromises();

    const subtitle = wrapper.get('[data-testid="edit-modal-subtitle"]').text();
    expect(subtitle).toContain('IFA vs Northern Virginia Alliance');
    expect(subtitle).not.toContain('U14');
  });
});
