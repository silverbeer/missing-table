/**
 * AdminMatches edit modal: per-side "Plays at" (SB-1444).
 *
 * A side that played up records its own age group. The picker shows where
 * teams play up (Friendly, Tournament) or wherever a side already records
 * one; otherwise the fields are left out of the PUT so the API keeps what is
 * stored.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import AdminMatches from '@/components/admin/AdminMatches.vue';
import {
  createMockAuthStore,
  createMockSeasons,
  createMockAgeGroups,
  createMockMatchTypes,
  createMockLeagues,
  createMockTeams,
} from '../helpers/matchFactories';

let mockAuthStore;

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => mockAuthStore,
}));

vi.mock('@/config/api', () => ({
  getApiBaseUrl: () => 'http://localhost:8000',
}));

// U14 (id 3) friendly: Blue Stars at home, Red Hawks' U16 (id 4) side away.
const friendly = (overrides = {}) => ({
  id: 10106,
  match_date: '2026-10-28',
  scheduled_kickoff: null,
  home_team_id: 1,
  away_team_id: 2,
  home_team_name: 'Blue Stars U14',
  away_team_name: 'Red Hawks U14',
  home_score: 0,
  away_score: 0,
  match_type_id: 3,
  match_type_name: 'Friendly',
  season_id: 1,
  age_group_id: 3,
  home_age_group_id: null,
  away_age_group_id: null,
  division_id: null,
  match_status: 'scheduled',
  ...overrides,
});

const routes = match => url => {
  if (url.includes('/api/teams')) return createMockTeams();
  if (url.includes('/api/seasons')) return createMockSeasons();
  if (url.includes('/api/match-types')) return createMockMatchTypes();
  if (url.includes('/api/age-groups')) return createMockAgeGroups();
  if (url.includes('/api/leagues')) return createMockLeagues();
  if (url.includes('/api/matches')) return [match];
  return [];
};

const openEditor = async match => {
  const respond = routes(match);
  mockAuthStore = createMockAuthStore({
    apiRequest: vi.fn((url, opts) =>
      Promise.resolve(opts?.method === 'PUT' ? {} : respond(url))
    ),
  });
  const wrapper = mount(AdminMatches);
  await flushPromises();
  wrapper.vm.editMatch(match);
  await flushPromises();
  return wrapper;
};

const putBody = () => {
  const call = mockAuthStore.apiRequest.mock.calls.find(
    ([, opts]) => opts?.method === 'PUT'
  );
  return JSON.parse(call[1].body);
};

describe('AdminMatches edit — Plays at (SB-1444)', () => {
  beforeEach(() => vi.clearAllMocks());

  it('shows a picker per side for a Friendly, defaulting to the match age group', async () => {
    const wrapper = await openEditor(friendly());

    const away = wrapper.find('[data-testid="edit-away-age-group-select"]');
    expect(away.exists()).toBe(true);
    expect(away.element.value).toBe('');
    expect(away.text()).toContain('Plays at U14 (same)');
    expect(
      wrapper.find('[data-testid="edit-home-age-group-select"]').exists()
    ).toBe(true);
  });

  it('loads a recorded playing-up side', async () => {
    const wrapper = await openEditor(friendly({ away_age_group_id: 4 }));

    expect(wrapper.vm.editFormData.away_age_group_id).toBe(4);
  });

  it('sends the chosen side and clears the other', async () => {
    const wrapper = await openEditor(friendly());
    wrapper.vm.editFormData.away_age_group_id = 4;
    await wrapper.vm.updateMatch();
    await flushPromises();

    const body = putBody();
    expect(body.away_age_group_id).toBe(4);
    expect(body.home_age_group_id).toBeNull();
  });

  it('hides the picker for League and leaves the fields out of the PUT', async () => {
    const wrapper = await openEditor(
      friendly({ match_type_id: 1, match_type_name: 'League', division_id: 1 })
    );

    expect(
      wrapper.find('[data-testid="edit-away-age-group-select"]').exists()
    ).toBe(false);

    await wrapper.vm.updateMatch();
    await flushPromises();
    const body = putBody();
    expect(body).not.toHaveProperty('home_age_group_id');
    expect(body).not.toHaveProperty('away_age_group_id');
  });

  it('still shows the picker on a League match that records a side, so it can be undone', async () => {
    const wrapper = await openEditor(
      friendly({ match_type_id: 1, division_id: 1, away_age_group_id: 4 })
    );

    expect(
      wrapper.find('[data-testid="edit-away-age-group-select"]').exists()
    ).toBe(true);
  });
});
