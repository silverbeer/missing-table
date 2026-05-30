/**
 * RosterManager.vue — bulk age-group assignment (SB-69).
 *
 * Covers:
 * - Each player row renders an age-group select reflecting its current value
 *   (NULL shows the "—" placeholder).
 * - Select-all + bulk "Assign Age Group" PATCHes every selected player with the
 *   chosen age group and season.
 * - The per-row inline select PATCHes just that one player (quick assign).
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';

const apiRequestMock = vi.fn();

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({ apiRequest: apiRequestMock }),
}));

vi.mock('@/config/api', () => ({
  getApiBaseUrl: () => 'http://test.example',
}));

import RosterManager from '@/components/roster/RosterManager.vue';

const AGE_GROUPS = [
  { id: 2, name: 'U14' },
  { id: 3, name: 'U15' },
];

// Player 1 is untagged (age_group_id null), player 2 already tagged U15.
const ROSTER = [
  { id: 1, jersey_number: 7, display_name: 'Kid Seven', age_group_id: null },
  { id: 2, jersey_number: 10, display_name: 'Kid Ten', age_group_id: 3 },
];

const wireMock = () => {
  apiRequestMock.mockImplementation(url => {
    if (url.includes('/players/age-group')) {
      return Promise.resolve({ success: true, updated_count: 2 });
    }
    if (url.endsWith('/api/age-groups')) {
      return Promise.resolve([...AGE_GROUPS]);
    }
    if (url.includes('/roster')) {
      return Promise.resolve({ roster: ROSTER.map(p => ({ ...p })) });
    }
    return Promise.resolve({});
  });
};

const mountManager = async () => {
  const wrapper = mount(RosterManager, {
    props: { teamId: 42, teamName: 'IFA U14', seasonId: 3, ageGroupId: 2 },
  });
  await flushPromises();
  return wrapper;
};

const patchCall = () =>
  apiRequestMock.mock.calls.find(c => c[0].includes('/players/age-group'));

beforeEach(() => {
  apiRequestMock.mockReset();
  wireMock();
});

describe('RosterManager age-group column (SB-69)', () => {
  it('renders an age-group select per row reflecting the current value', async () => {
    const wrapper = await mountManager();

    const untagged = wrapper.find('[data-testid="row-age-group-1"]');
    const tagged = wrapper.find('[data-testid="row-age-group-2"]');
    expect(untagged.exists()).toBe(true);
    expect(untagged.element.value).toBe(''); // NULL → "—" placeholder
    expect(tagged.element.value).toBe('3'); // already U15
  });

  it('fetches age groups on mount', async () => {
    await mountManager();
    expect(
      apiRequestMock.mock.calls.some(c => c[0].endsWith('/api/age-groups'))
    ).toBe(true);
  });
});

describe('RosterManager bulk assign (SB-69)', () => {
  it('assigns the chosen age group to all selected players', async () => {
    const wrapper = await mountManager();

    // Select all, then choose U14 (id 2) and click Assign.
    await wrapper.find('[data-testid="select-all-checkbox"]').trigger('change');
    await wrapper.find('[data-testid="bulk-age-group-select"]').setValue('2');
    await wrapper
      .find('[data-testid="assign-age-group-button"]')
      .trigger('click');
    await flushPromises();

    const call = patchCall();
    expect(call).toBeTruthy();
    expect(call[1].method).toBe('PATCH');
    const body = JSON.parse(call[1].body);
    expect(body.player_ids.sort()).toEqual([1, 2]);
    expect(body.age_group_id).toBe(2);
    expect(body.season_id).toBe(3);
  });

  it('does not show the bulk bar until a row is selected', async () => {
    const wrapper = await mountManager();
    expect(wrapper.find('[data-testid="bulk-age-group-bar"]').exists()).toBe(
      false
    );
    await wrapper.find('[data-testid="select-player-1"]').setValue(true);
    expect(wrapper.find('[data-testid="bulk-age-group-bar"]').exists()).toBe(
      true
    );
  });
});

describe('RosterManager per-row quick assign (SB-69)', () => {
  it('PATCHes a single player when its inline select changes', async () => {
    const wrapper = await mountManager();

    await wrapper.find('[data-testid="row-age-group-1"]').setValue('2');
    await flushPromises();

    const call = patchCall();
    expect(call).toBeTruthy();
    const body = JSON.parse(call[1].body);
    expect(body.player_ids).toEqual([1]);
    expect(body.age_group_id).toBe(2);
  });
});
