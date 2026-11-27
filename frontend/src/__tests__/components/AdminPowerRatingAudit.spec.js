/**
 * Power Rating audit (SB-1812): the admin view over
 * GET /api/admin/power-rating/audit.
 *
 * What these guard: the section is admin only (a club manager never sees
 * it); the summary and the flagged rows render, with the gap's sign spelled
 * out; "Recompute now" posts, is disabled while it runs, and shows what it
 * did; no run is the API's reason, and nothing flagged says so.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ref } from 'vue';
import { flushPromises, mount, shallowMount } from '@vue/test-utils';

let mockAuthStore;
const apiRequest = vi.fn();
vi.mock('@/stores/auth', () => ({ useAuthStore: () => mockAuthStore }));
vi.mock('@/config/api', () => ({
  getApiBaseUrl: () => 'http://localhost:8000',
}));

import AdminPanel from '@/components/AdminPanel.vue';
import AdminPowerRatingAudit from '@/components/admin/AdminPowerRatingAudit.vue';

const NOTE =
  "Investigate, don't auto-fix: a large gap usually means few matches or few cross-conference matches.";

const row = (over = {}) => ({
  team_id: 21,
  team: 'IFA U17',
  conference: 'Northeast',
  island: 1,
  elo_rating: 1642,
  elo_rank: 4,
  massey_rank: 40,
  gap: 36,
  mp: 7,
  xconf_mp: 1,
  badges: ['provisional', 'low_cross_conference'],
  ...over,
});

const audit = (over = {}) => ({
  league: 'Homegrown',
  age_group: 'U15',
  season: '2026-2027',
  run: {
    id: 412,
    computed_at: '2026-12-15T10:00:04Z',
    through_date: '2026-12-14',
    matches_counted: 1122,
    params_version: 'elo-v1',
  },
  min_gap: 30,
  scope: 'Within each island: ranked teams (6+ matches) ...',
  note: NOTE,
  teams_compared: 147,
  flagged_count: 2,
  rank_correlation: 0.953,
  islands: [],
  teams: [row(), row({ team_id: 22, team: 'NEFC U17', gap: -33 })],
  reason: null,
  ...over,
});

const SUMMARY = {
  season_id: 184,
  league: 'Homegrown',
  computed_at: '2026-12-15T11:00:00Z',
  age_groups: [
    { age_group: 'U15', status: 'unchanged', run_id: 412, teams: 147 },
    { age_group: 'U16', status: 'written', run_id: 413, teams: 120 },
  ],
};

const mountAudit = () => mount(AdminPowerRatingAudit);

beforeEach(() => {
  apiRequest.mockReset();
  mockAuthStore = {
    apiRequest,
    isAdmin: ref(true),
    isClubManager: ref(false),
  };
});

describe('Admin panel gating', () => {
  const sectionOptions = wrapper =>
    wrapper
      .findAll('[data-testid="admin-section-select"] option')
      .map(o => o.attributes('value'));

  it('is listed for an admin', () => {
    const wrapper = shallowMount(AdminPanel);
    expect(sectionOptions(wrapper)).toContain('power-rating-audit');
  });

  it('is hidden from a club manager', () => {
    mockAuthStore.isAdmin = ref(false);
    mockAuthStore.isClubManager = ref(true);
    const wrapper = shallowMount(AdminPanel);
    expect(sectionOptions(wrapper).length).toBeGreaterThan(0);
    expect(sectionOptions(wrapper)).not.toContain('power-rating-audit');
    expect(
      wrapper.find('[data-testid="admin-section-power-rating-audit"]').exists()
    ).toBe(false);
  });
});

describe('AdminPowerRatingAudit', () => {
  it('reads the audit for the age group with the default gap of 30', async () => {
    apiRequest.mockResolvedValue(audit());
    mountAudit();
    await flushPromises();
    const url = new URL(apiRequest.mock.calls[0][0]);
    expect(url.pathname).toBe('/api/admin/power-rating/audit');
    expect(Object.fromEntries(url.searchParams)).toEqual({
      league: 'Homegrown',
      age_group: 'U15',
      min_gap: '30',
    });
  });

  it('renders the summary, the note and the flagged rows', async () => {
    apiRequest.mockResolvedValue(audit());
    const wrapper = mountAudit();
    await flushPromises();
    const summary = wrapper.find('[data-testid="pr-audit-summary"]').text();
    expect(summary).toContain('Run #412');
    expect(summary).toContain('147 teams compared');
    expect(summary).toContain('2 flagged above 30 places');
    expect(summary).toContain('rank correlation 0.95');
    expect(wrapper.find('[data-testid="pr-audit-note"]').text()).toBe(NOTE);

    const rows = wrapper.findAll('[data-testid="pr-audit-row"]');
    expect(rows).toHaveLength(2);
    expect(rows[0].text()).toContain('IFA U17');
    expect(rows[0].text()).toContain('1,642');
    expect(rows[0].text()).toContain('+36 Elo higher');
    expect(rows[0].text()).toContain('Provisional, Low cross-conf.');
    expect(rows[1].text()).toContain('−33 Massey higher');
    // The stacked mobile rows carry the same teams.
    expect(wrapper.findAll('[data-testid="pr-audit-item"]')).toHaveLength(2);
  });

  it('refetches on an age group and a new gap; a negative gap is ignored', async () => {
    apiRequest.mockResolvedValue(audit());
    const wrapper = mountAudit();
    await flushPromises();
    await wrapper.find('[data-testid="pr-audit-age-U17"]').trigger('click');
    await flushPromises();
    let params = new URL(apiRequest.mock.calls.at(-1)[0]).searchParams;
    expect(params.get('age_group')).toBe('U17');

    const input = wrapper.find('[data-testid="pr-audit-min-gap"]');
    await input.setValue('10');
    await input.trigger('change');
    await flushPromises();
    params = new URL(apiRequest.mock.calls.at(-1)[0]).searchParams;
    expect(params.get('min_gap')).toBe('10');

    const calls = apiRequest.mock.calls.length;
    await input.setValue('-5');
    await input.trigger('change');
    await flushPromises();
    expect(apiRequest.mock.calls.length).toBe(calls);
    expect(input.element.value).toBe('10');
  });

  it('Recompute now posts, is disabled while running, and shows the summary', async () => {
    let finish;
    apiRequest.mockImplementation((url, opts) => {
      if (opts?.method === 'POST') {
        return new Promise(resolve => {
          finish = () => resolve(SUMMARY);
        });
      }
      return Promise.resolve(audit());
    });
    const wrapper = mountAudit();
    await flushPromises();
    const button = wrapper.find('[data-testid="pr-audit-recompute"]');
    await button.trigger('click');
    expect(button.attributes('disabled')).toBeDefined();
    expect(button.text()).toBe('Recomputing...');

    const post = apiRequest.mock.calls.find(c => c[1]?.method === 'POST');
    expect(new URL(post[0]).pathname).toBe('/api/admin/power-rating/recompute');

    const reads = apiRequest.mock.calls.length;
    finish();
    await flushPromises();
    expect(button.attributes('disabled')).toBeUndefined();
    const shown = wrapper.find('[data-testid="pr-audit-recompute-summary"]');
    expect(shown.text()).toContain('U15: unchanged · run #412 · 147 teams');
    expect(shown.text()).toContain('U16: written · run #413 · 120 teams');
    // The audit is read again, from the new run.
    expect(apiRequest.mock.calls.length).toBe(reads + 1);
  });

  it('a failed recompute shows the error and re-enables the button', async () => {
    apiRequest.mockImplementation((url, opts) =>
      opts?.method === 'POST'
        ? Promise.reject(new Error('Could not recompute the power rating'))
        : Promise.resolve(audit())
    );
    const wrapper = mountAudit();
    await flushPromises();
    await wrapper.find('[data-testid="pr-audit-recompute"]').trigger('click');
    await flushPromises();
    expect(
      wrapper.find('[data-testid="pr-audit-recompute-error"]').text()
    ).toBe('Could not recompute the power rating');
    expect(
      wrapper.find('[data-testid="pr-audit-recompute"]').attributes('disabled')
    ).toBeUndefined();
  });

  it('no run yet shows the reason, not a table', async () => {
    apiRequest.mockResolvedValue(
      audit({
        run: null,
        teams: [],
        teams_compared: 0,
        flagged_count: 0,
        rank_correlation: null,
        reason:
          'No Power Rating has been computed for Homegrown U15 in 2026-2027 yet.',
      })
    );
    const wrapper = mountAudit();
    await flushPromises();
    expect(wrapper.find('[data-testid="pr-audit-empty"]').text()).toBe(
      'No Power Rating has been computed for Homegrown U15 in 2026-2027 yet.'
    );
    expect(wrapper.find('[data-testid="pr-audit-summary"]').exists()).toBe(
      false
    );
    expect(wrapper.find('[data-testid="pr-audit-table"]').exists()).toBe(false);
  });

  it('nothing flagged says so', async () => {
    apiRequest.mockResolvedValue(audit({ teams: [], flagged_count: 0 }));
    const wrapper = mountAudit();
    await flushPromises();
    expect(wrapper.find('[data-testid="pr-audit-none-flagged"]').text()).toBe(
      'No gaps above 30 places.'
    );
  });

  it('a failed read is an error', async () => {
    apiRequest.mockRejectedValue(
      new Error('The Power Rating audit is unavailable right now')
    );
    const wrapper = mountAudit();
    await flushPromises();
    expect(wrapper.find('[data-testid="pr-audit-error"]').text()).toBe(
      'The Power Rating audit is unavailable right now'
    );
  });
});
