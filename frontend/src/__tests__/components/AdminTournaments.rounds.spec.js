/**
 * AdminTournaments.vue — the round select offers every round key (SB-1752).
 *
 * The select used to hard-code seven <option>s, so the Fest rounds could not
 * be chosen in the admin UI. It now renders from ROUND_LABELS_LONG.
 * Fixture: a tournament with no matches yet (scraped/empty state).
 */

import { describe, it, expect, vi } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import AdminTournaments from '@/components/admin/AdminTournaments.vue';
import { ROUND_LABELS_LONG } from '@/utils/tournamentRounds';

let mockAuthStore;
vi.mock('@/stores/auth', () => ({ useAuthStore: () => mockAuthStore }));
vi.mock('@/config/api', () => ({
  getApiBaseUrl: () => 'http://localhost:8000',
}));

async function openAddMatchModal() {
  mockAuthStore = { apiRequest: vi.fn(() => Promise.resolve([])) };
  const wrapper = mount(AdminTournaments);
  await flushPromises();
  wrapper.vm.openAddMatch({ id: 1 });
  await flushPromises();
  return wrapper;
}

const roundSelect = wrapper =>
  wrapper
    .findAll('select')
    .find(s =>
      s.findAll('option').some(o => o.element.value === 'group_stage')
    );

describe('AdminTournaments — round select', () => {
  it('offers showcase, consolation and placement_final', async () => {
    const select = roundSelect(await openAddMatchModal());
    expect(select).toBeTruthy();
    const options = Object.fromEntries(
      select.findAll('option').map(o => [o.element.value, o.text()])
    );
    expect(options.showcase).toBe('Showcase');
    expect(options.consolation).toBe('Consolation');
    expect(options.placement_final).toBe('Placement Final');
  });

  it('keeps the existing rounds and the empty "none" choice', async () => {
    const select = roundSelect(await openAddMatchModal());
    const values = select.findAll('option').map(o => o.element.value);
    expect(values[0]).toBe('');
    for (const key of Object.keys(ROUND_LABELS_LONG)) {
      expect(values).toContain(key);
    }
    for (const key of [
      'group_stage',
      'round_of_32',
      'round_of_16',
      'quarterfinal',
      'semifinal',
      'third_place',
      'final',
    ]) {
      expect(values).toContain(key);
    }
  });
});
