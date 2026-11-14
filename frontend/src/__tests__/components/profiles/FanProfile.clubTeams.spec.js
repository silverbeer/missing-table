/**
 * FanProfile club teams list (SB-1675): one line per league · division with
 * age groups as chips; tapping a chip shows that squad's Table and Matches.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import FanProfile from '@/components/profiles/FanProfile.vue';
import { _resetTeamFollowsForTest } from '@/composables/useTeamFollows';

const push = vi.fn();
vi.mock('vue-router', () => ({ useRouter: () => ({ push }) }));

const mapping = (divId, divName, agId, agName) => ({
  divisions: { id: divId, name: divName },
  age_groups: { id: agId, name: agName },
});

const TEAMS = [
  {
    id: 1,
    leagues: { id: 10, name: 'Academy' },
    team_mappings: [
      mapping(100, 'New England', 13, 'U13'),
      mapping(100, 'New England', 14, 'U14'),
    ],
  },
  {
    id: 2,
    leagues: { id: 20, name: 'Homegrown' },
    team_mappings: [
      mapping(200, 'New England', 15, 'U15'),
      mapping(201, 'Northeast', 13, 'U13'),
      mapping(201, 'Northeast', 15, 'U15'),
    ],
  },
];

let teams;
let mockAuthStore;
const apiRequest = vi.fn();

vi.mock('@/stores/auth', () => ({ useAuthStore: () => mockAuthStore }));
vi.mock('@/config/api', () => ({ getApiBaseUrl: () => 'http://test' }));

beforeEach(() => {
  teams = TEAMS;
  _resetTeamFollowsForTest();
  push.mockReset();
  mockAuthStore = {
    isAuthenticated: { value: true },
    state: { profile: { role: 'club-fan', club_id: 1 } },
    apiRequest,
    fetchProfile: vi.fn().mockResolvedValue({}),
  };
  apiRequest.mockReset();
  apiRequest.mockImplementation(url => {
    if (url.endsWith('/api/clubs/1'))
      return Promise.resolve({ id: 1, name: 'IFA' });
    if (url.endsWith('/api/clubs/1/teams')) return Promise.resolve(teams);
    if (url.endsWith('/api/users/me/team-follows'))
      return Promise.resolve({ follows: [] });
    if (url.endsWith('/api/me/team-options'))
      return Promise.resolve({
        status: 'ok',
        club: { id: 1, name: 'IFA' },
        options: [],
      });
    return Promise.resolve({ success: true });
  });
  vi.stubGlobal(
    'fetch',
    vi.fn(() => Promise.resolve({ ok: true, json: () => [] }))
  );
});

const mountProfile = async () => {
  const wrapper = mount(FanProfile, {
    global: {
      stubs: {
        LiveUpdatesTeaser: true,
        TeamChannelsCard: true,
        NotificationsCard: true,
      },
    },
  });
  await flushPromises();
  return wrapper;
};

const lines = w =>
  w.findAll('[data-testid="club-team-line"]').map(l => ({
    label: l.find('.line-label').text(),
    ages: l.findAll('[data-testid="age-chip"]').map(c => c.text()),
  }));

describe('FanProfile club teams (SB-1675)', () => {
  it('shows one line per league · division with its age groups', async () => {
    const w = await mountProfile();
    expect(w.find('[data-testid="club-teams"] h3').text()).toBe('IFA Teams');
    expect(lines(w)).toEqual([
      { label: 'Academy · New England', ages: ['U13', 'U14'] },
      { label: 'Homegrown · New England', ages: ['U15'] },
      { label: 'Homegrown · Northeast', ages: ['U13', 'U15'] },
    ]);
    expect(w.find('[data-testid="squad-actions"]').exists()).toBe(false);
  });

  it('a chip shows Table and Matches for that squad only; tapping again hides them', async () => {
    const w = await mountProfile();
    const northeast = w.findAll('[data-testid="club-team-line"]')[2];
    const u15 = northeast.findAll('[data-testid="age-chip"]')[1];
    await u15.trigger('click');

    expect(w.findAll('[data-testid="squad-actions"]')).toHaveLength(1);
    expect(northeast.find('[data-testid="squad-actions"]').text()).toContain(
      'U15'
    );
    expect(u15.attributes('aria-expanded')).toBe('true');

    await u15.trigger('click');
    expect(w.find('[data-testid="squad-actions"]').exists()).toBe(false);
  });

  it('picking a squad on another line moves the actions there', async () => {
    const w = await mountProfile();
    const [academy, , northeast] = w.findAll('[data-testid="club-team-line"]');
    await academy.find('[data-testid="age-chip"]').trigger('click');
    await northeast.find('[data-testid="age-chip"]').trigger('click');
    expect(academy.find('[data-testid="squad-actions"]').exists()).toBe(false);
    expect(northeast.find('[data-testid="squad-actions"]').exists()).toBe(true);
  });

  it('keeps match alerts, notifications and chat channels together (SB-1675)', async () => {
    const w = await mountProfile();
    const html = w.html();
    const order = [
      'data-testid="my-team-card"',
      'notifications-card-stub',
      'team-channels-card-stub',
      'data-testid="club-teams"',
    ].map(m => html.indexOf(m));
    expect(order.every(i => i >= 0)).toBe(true);
    expect([...order].sort((a, b) => a - b)).toEqual(order);
  });

  it('has no filler sections', async () => {
    const w = await mountProfile();
    expect(w.find('.features-section').exists()).toBe(false);
    expect(w.find('.quick-access-section').exists()).toBe(false);
  });

  it('has no section when the club has no teams', async () => {
    teams = [];
    const w = await mountProfile();
    expect(w.find('[data-testid="club-teams"]').exists()).toBe(false);
  });
});
