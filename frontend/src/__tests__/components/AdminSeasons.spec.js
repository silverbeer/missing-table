/**
 * AdminSeasons.vue — match counts column (SB-61).
 *
 * Pre-SB-61 this component fetched /api/matches (capped at Supabase's 1000-row
 * default) and counted client-side, so the current season displayed exactly
 * 1000 and older seasons displayed 0. The fix moves counting to a new
 * /api/seasons/match-counts admin endpoint and renames the column.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import AdminSeasons from '@/components/admin/AdminSeasons.vue';

let mockAuthStore;
vi.mock('@/stores/auth', () => ({ useAuthStore: () => mockAuthStore }));
vi.mock('@/config/api', () => ({
  getApiBaseUrl: () => 'http://localhost:8000',
}));

const SEASONS = [
  {
    id: 1,
    name: '2025-2026',
    start_date: '2025-09-01',
    end_date: '2026-06-30',
  },
  {
    id: 2,
    name: '2024-2025',
    start_date: '2024-09-01',
    end_date: '2025-06-30',
  },
  {
    id: 3,
    name: '2023-2024',
    start_date: '2023-09-01',
    end_date: '2024-06-30',
  },
];

const MATCH_COUNTS = [
  { season_id: 1, match_count: 1437 },
  { season_id: 2, match_count: 980 },
  { season_id: 3, match_count: 412 },
];

const mountSeasons = (overrides = {}) => {
  const apiRequest = vi.fn(url => {
    if (url.endsWith('/api/seasons')) {
      return Promise.resolve(overrides.seasons ?? SEASONS);
    }
    if (url.endsWith('/api/seasons/match-counts')) {
      return Promise.resolve(overrides.matchCounts ?? MATCH_COUNTS);
    }
    return Promise.resolve([]);
  });
  mockAuthStore = { apiRequest };
  return mount(AdminSeasons);
};

describe('AdminSeasons match counts (SB-61)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the "Matches Count" column header (not "Games Count")', async () => {
    const wrapper = mountSeasons();
    await flushPromises();

    const header = wrapper.find('[data-testid="matches-count-header"]');
    expect(header.exists()).toBe(true);
    expect(header.text()).toBe('Matches Count');
    expect(wrapper.text()).not.toContain('Games Count');
  });

  it('hits the per-season counts endpoint instead of /api/matches', async () => {
    const wrapper = mountSeasons();
    await flushPromises();

    const calls = mockAuthStore.apiRequest.mock.calls.map(c => c[0]);
    expect(calls.some(u => u.endsWith('/api/seasons/match-counts'))).toBe(true);
    // The legacy fat fetch must not happen — it was the cap bug.
    expect(calls.some(u => u.endsWith('/api/matches'))).toBe(false);
    void wrapper;
  });

  it('renders the count returned for each season', async () => {
    const wrapper = mountSeasons();
    await flushPromises();

    expect(wrapper.find('[data-testid="matches-count-1"]').text()).toBe('1437');
    expect(wrapper.find('[data-testid="matches-count-2"]').text()).toBe('980');
    expect(wrapper.find('[data-testid="matches-count-3"]').text()).toBe('412');
  });

  it('shows 0 for a season the endpoint omitted', async () => {
    const wrapper = mountSeasons({
      matchCounts: [{ season_id: 1, match_count: 5 }],
    });
    await flushPromises();

    expect(wrapper.find('[data-testid="matches-count-1"]').text()).toBe('5');
    expect(wrapper.find('[data-testid="matches-count-2"]').text()).toBe('0');
    expect(wrapper.find('[data-testid="matches-count-3"]').text()).toBe('0');
  });

  it('disables Delete when a season has matches', async () => {
    const wrapper = mountSeasons();
    await flushPromises();

    const deleteButtons = wrapper
      .findAll('button')
      .filter(b => b.text() === 'Delete');
    // All three seasons in fixture data have non-zero counts.
    for (const btn of deleteButtons) {
      expect(btn.attributes('disabled')).toBeDefined();
    }
  });
});
