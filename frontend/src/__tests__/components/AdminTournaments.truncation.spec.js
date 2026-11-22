/**
 * AdminTournaments.vue — the match count is not under-reported (SB-1749).
 *
 * The admin panel loads a tournament through the unpaged detail endpoint,
 * which returns at most one response's worth of rows. It used to overwrite
 * the exact match_count with the number of rows it got. It now keeps the
 * exact total and says plainly when the table is cut short.
 */

import { describe, it, expect, vi } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import AdminTournaments from '@/components/admin/AdminTournaments.vue';

let mockAuthStore;
vi.mock('@/stores/auth', () => ({ useAuthStore: () => mockAuthStore }));
vi.mock('@/config/api', () => ({
  getApiBaseUrl: () => 'http://localhost:8000',
}));

const mkMatch = id => ({
  id,
  match_date: '2026-12-04',
  match_status: 'scheduled',
  home_score: null,
  away_score: null,
  tournament_group: 'HD · A',
  tournament_round: 'group_stage',
  age_group: { id: 5, name: 'U13' },
  home_team: { id: id * 2, name: `Home ${id}` },
  away_team: { id: id * 2 + 1, name: `Away ${id}` },
});

const rows = n => Array.from({ length: n }, (_, i) => mkMatch(i + 1));

async function expand({ matchCount, loaded, counted }) {
  const tournament = {
    id: 6,
    name: 'MLS NEXT Fest',
    start_date: '2026-12-04',
    match_count: matchCount,
    age_groups: [],
  };
  mockAuthStore = {
    apiRequest: vi.fn(url => {
      if (url.endsWith('/api/admin/tournaments')) {
        return Promise.resolve([tournament]);
      }
      if (url.includes('/api/tournaments/6/matches')) {
        return counted instanceof Error
          ? Promise.reject(counted)
          : Promise.resolve(counted);
      }
      if (url.endsWith('/api/tournaments/6')) {
        return Promise.resolve({ ...tournament, matches: rows(loaded) });
      }
      return Promise.resolve([]);
    }),
  };
  const wrapper = mount(AdminTournaments);
  await flushPromises();
  await wrapper.vm.toggleTournament(wrapper.vm.tournaments[0]);
  await flushPromises();
  return wrapper;
}

const note = w => w.find('[data-testid="admin-matches-truncated"]');
const page = total => ({ matches: [], total, limit: 1, offset: 0 });

describe('AdminTournaments — truncated match list', () => {
  it('keeps the exact count and says the list is cut short', async () => {
    const w = await expand({
      matchCount: 2400,
      loaded: 1000,
      counted: page(2400),
    });

    expect(w.vm.tournaments[0].match_count).toBe(2400);
    expect(note(w).exists()).toBe(true);
    expect(note(w).text()).toBe('Showing the first 1000 of 2400 matches.');
    expect(w.text()).toContain('2400 matches');
  });

  it('asks only for the count, one row at most', async () => {
    await expand({ matchCount: 2400, loaded: 1000, counted: page(2400) });
    const counts = mockAuthStore.apiRequest.mock.calls
      .map(([url]) => url)
      .filter(url => url.includes('/matches'));
    expect(counts).toEqual([
      'http://localhost:8000/api/tournaments/6/matches?limit=1',
    ]);
  });

  it('shows no note when every match is loaded', async () => {
    const w = await expand({ matchCount: 12, loaded: 12, counted: page(12) });
    expect(note(w).exists()).toBe(false);
    expect(w.vm.tournaments[0].match_count).toBe(12);
  });

  it('follows the server down when a match was removed', async () => {
    // The list row still says 12; the tournament now has 11.
    const w = await expand({ matchCount: 12, loaded: 11, counted: page(11) });
    expect(w.vm.tournaments[0].match_count).toBe(11);
    expect(note(w).exists()).toBe(false);
  });

  it('falls back to the loaded rows when the count cannot be fetched', async () => {
    const w = await expand({
      matchCount: 12,
      loaded: 12,
      counted: new Error('offline'),
    });
    expect(w.vm.tournaments[0].match_count).toBe(12);
    expect(note(w).exists()).toBe(false);
    expect(w.vm.error).toBe(null);
  });

  it('never reports fewer than the rows it is showing', async () => {
    const w = await expand({ matchCount: 3, loaded: 5, counted: page(3) });
    expect(w.vm.tournaments[0].match_count).toBe(5);
    expect(note(w).exists()).toBe(false);
  });
});
