/**
 * AdminTournaments.vue — the announcement field (SB-1797).
 *
 * One line, at most 160 characters. It is always sent on save, trimmed; an
 * empty field is sent as "" so the server clears it (None would mean
 * "leave unchanged").
 */

import { describe, it, expect, vi } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import AdminTournaments from '@/components/admin/AdminTournaments.vue';

let mockAuthStore;
vi.mock('@/stores/auth', () => ({ useAuthStore: () => mockAuthStore }));
vi.mock('@/config/api', () => ({
  getApiBaseUrl: () => 'http://localhost:8000',
}));

const LINE = 'Every MLS NEXT Fest match scored';
const FEST = {
  id: 6,
  name: 'MLS NEXT Fest',
  season_id: 184,
  start_date: '2026-12-04',
  is_active: true,
  announcement: LINE,
  age_groups: [],
};

async function mountAdmin() {
  mockAuthStore = {
    apiRequest: vi.fn((url, opts) => {
      if (opts?.method === 'POST') return Promise.resolve({ id: 7 });
      if (url.endsWith('/api/admin/tournaments'))
        return Promise.resolve([FEST]);
      return Promise.resolve([]);
    }),
  };
  const wrapper = mount(AdminTournaments);
  await flushPromises();
  return wrapper;
}

const sent = method => {
  const call = mockAuthStore.apiRequest.mock.calls.find(
    ([, opts]) => opts?.method === method
  );
  return JSON.parse(call[1].body);
};

describe('AdminTournaments — announcement', () => {
  it('loads the current announcement into the field, with a counter', async () => {
    const w = await mountAdmin();
    w.vm.openEditTournament(FEST);
    await flushPromises();

    const input = w.find('[data-testid="tournament-announcement-input"]');
    expect(input.element.value).toBe(LINE);
    expect(input.attributes('maxlength')).toBe('160');
    expect(w.find('[data-testid="tournament-announcement-count"]').text()).toBe(
      `${LINE.length}/160`
    );
    expect(w.text()).toContain(
      'One line shown on the tournament card and banner. Leave empty for none.'
    );
  });

  it('sends the edited announcement, trimmed, on update', async () => {
    const w = await mountAdmin();
    w.vm.openEditTournament(FEST);
    await flushPromises();
    await w
      .find('[data-testid="tournament-announcement-input"]')
      .setValue('  Live scores all weekend  ');
    await w.vm.saveTournament();
    await flushPromises();

    expect(sent('PUT').announcement).toBe('Live scores all weekend');
  });

  it('sends an empty string to clear it on update', async () => {
    const w = await mountAdmin();
    w.vm.openEditTournament(FEST);
    await flushPromises();
    await w
      .find('[data-testid="tournament-announcement-input"]')
      .setValue('   ');
    await w.vm.saveTournament();
    await flushPromises();

    expect(sent('PUT').announcement).toBe('');
  });

  it('a tournament with none opens with an empty field', async () => {
    const w = await mountAdmin();
    w.vm.openEditTournament({ ...FEST, announcement: null });
    await flushPromises();
    expect(
      w.find('[data-testid="tournament-announcement-input"]').element.value
    ).toBe('');
  });

  it('sends the announcement on create', async () => {
    const w = await mountAdmin();
    w.vm.openCreateTournament();
    await flushPromises();
    w.vm.tForm.name = 'Winter Cup';
    w.vm.tForm.start_date = '2027-01-10';
    await w
      .find('[data-testid="tournament-announcement-input"]')
      .setValue(LINE);
    await w.vm.saveTournament();
    await flushPromises();

    expect(sent('POST').announcement).toBe(LINE);
  });
});
