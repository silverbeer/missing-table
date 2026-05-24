/**
 * AdminClubs.vue — club name search/filter.
 *
 * Mocks the auth store's apiRequest (the only data source on mount) and asserts
 * the client-side name filter narrows the rendered club cards and surfaces a
 * no-results message.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import AdminClubs from '@/components/admin/AdminClubs.vue';

let mockAuthStore;
vi.mock('@/stores/auth', () => ({ useAuthStore: () => mockAuthStore }));
vi.mock('@/config/api', () => ({
  getApiBaseUrl: () => 'http://localhost:8000',
}));

const CLUBS = [
  { id: 1, name: 'Players Development Academy', city: 'Somerset, NJ' },
  { id: 2, name: 'AC River', city: 'Riverside' },
  { id: 3, name: 'AFC Lightning', city: 'Atlanta' },
].map(c => ({
  logo_url: null,
  primary_color: '#3B82F6',
  secondary_color: '#1E40AF',
  pro_academy: false,
  team_count: 1,
  is_active: true,
  ...c,
}));

const mountClubs = () => {
  mockAuthStore = {
    userRole: { value: 'admin' },
    userClubId: { value: null },
    apiRequest: vi.fn(() => Promise.resolve(CLUBS.map(c => ({ ...c })))),
  };
  return mount(AdminClubs);
};

describe('AdminClubs search', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders all clubs before searching', async () => {
    const wrapper = mountClubs();
    await flushPromises();
    expect(wrapper.text()).toContain('Players Development Academy');
    expect(wrapper.text()).toContain('AC River');
    expect(wrapper.text()).toContain('AFC Lightning');
  });

  it('filters clubs by name, case-insensitively', async () => {
    const wrapper = mountClubs();
    await flushPromises();

    await wrapper.find('[data-testid="club-search"]').setValue('PLAYER');

    expect(wrapper.text()).toContain('Players Development Academy');
    expect(wrapper.text()).not.toContain('AC River');
    expect(wrapper.text()).not.toContain('AFC Lightning');
  });

  it('shows a no-results message when nothing matches', async () => {
    const wrapper = mountClubs();
    await flushPromises();

    await wrapper.find('[data-testid="club-search"]').setValue('zzzzz');

    expect(wrapper.find('[data-testid="club-search-empty"]').exists()).toBe(
      true
    );
    expect(wrapper.text()).toContain('No clubs match');
  });
});
