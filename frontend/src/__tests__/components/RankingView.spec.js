/**
 * The Ranking tab (SB-1785): listed only for a signed-in viewer, opens on
 * Leaderboards, and hands a team click to App's Matches navigation.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import {
  createAuthenticatedUserStore,
  createUnauthenticatedStore,
} from '../helpers/matchFactories';

let mockAuthStore;
vi.mock('@/stores/auth', () => ({ useAuthStore: () => mockAuthStore }));
vi.mock('@/config/api', () => ({
  getApiBaseUrl: () => 'http://localhost:8000',
}));
// Switching tabs records a page view; the shared setup mock has no such export.
vi.mock('@/faro', () => ({
  recordPageView: vi.fn(),
  recordInviteRequest: vi.fn(),
  recordHttpRequest: vi.fn(),
}));
vi.mock('@/composables/usePwaUpdate', () => ({ usePwaUpdate: () => ({}) }));
vi.mock('@/composables/useNotificationSetup', () => ({
  useNotificationSetup: () => ({
    ensureFollowsLoaded: vi.fn(),
    shouldPromptUnprompted: { value: false },
    open: vi.fn(),
  }),
}));

const signedIn = () => {
  const store = createAuthenticatedUserStore();
  store.userRole = { value: 'team-fan' };
  store.initialize = vi.fn(() => Promise.resolve());
  store.handleOAuthCallback = vi.fn();
  store.clearError = vi.fn();
  store.apiRequest = vi.fn(() => Promise.resolve([]));
  return store;
};

describe('RankingView (SB-1785)', () => {
  beforeEach(() => {
    mockAuthStore = signedIn();
  });

  it('opens on Leaderboards with no sub-nav while it is the only view', async () => {
    const { default: RankingView } =
      await import('@/components/ranking/RankingView.vue');
    const w = mount(RankingView, {
      global: {
        stubs: {
          LeaderboardsPanel: {
            template: '<div data-testid="leaderboards-stub" />',
          },
        },
      },
    });
    expect(w.find('[data-testid="leaderboards-stub"]').exists()).toBe(true);
    expect(w.find('[data-testid="ranking-subnav"]').exists()).toBe(false);
  });

  it('re-emits navigate-to-team from the panel', async () => {
    const { default: RankingView } =
      await import('@/components/ranking/RankingView.vue');
    const w = mount(RankingView, {
      global: {
        stubs: {
          LeaderboardsPanel: {
            emits: ['navigate-to-team'],
            template:
              '<button data-testid="go" @click="$emit(\'navigate-to-team\', { teamId: 19 })" />',
          },
        },
      },
    });
    await w.get('[data-testid="go"]').trigger('click');
    expect(w.emitted('navigate-to-team')).toEqual([[{ teamId: 19 }]]);
  });
});

describe('Ranking tab in App', () => {
  const STUBS = {
    AuthNav: true,
    VersionFooter: true,
    InstallBanner: true,
    NotificationSetupGuide: true,
    OfflineIndicator: true,
    UpdateAvailablePrompt: true,
    LeagueTable: true,
    LandingPreview: true,
    RankingView: { template: '<div data-testid="ranking-stub" />' },
  };

  const mountApp = async () => {
    window.location.pathname = '/';
    window.location.hash = '';
    const { default: App } = await import('@/App.vue');
    const wrapper = mount(App, { global: { stubs: STUBS } });
    await flushPromises();
    return wrapper;
  };

  const tabs = w => w.findAll('nav[aria-label="Tabs"] button');

  beforeEach(() => {
    vi.resetModules();
    global.fetch = vi.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve({}) })
    );
  });

  afterEach(() => {
    delete window.location.pathname;
    delete window.location.hash;
    vi.restoreAllMocks();
  });

  it('lists Ranking after Tournaments for a signed-in viewer, and opens it', async () => {
    mockAuthStore = signedIn();
    const w = await mountApp();
    const names = tabs(w).map(b => b.text());
    const at = names.indexOf('Ranking');
    expect(at).toBeGreaterThan(-1);
    expect(names[at - 1]).toBe('Tournaments');

    await tabs(w)[at].trigger('click');
    await vi.waitFor(() =>
      expect(w.find('[data-testid="ranking-stub"]').exists()).toBe(true)
    );
  });

  it('is not offered when signed out', async () => {
    mockAuthStore = createUnauthenticatedStore();
    mockAuthStore.userRole = { value: null };
    mockAuthStore.initialize = vi.fn(() => Promise.resolve());
    mockAuthStore.clearError = vi.fn();
    const w = await mountApp();
    expect(tabs(w).some(b => b.text() === 'Ranking')).toBe(false);
  });
});

describe('Ranking tab — Power Rating coming soon (SB-1803)', () => {
  it('announces the Power Rating without promising a date', async () => {
    const { default: RankingView } =
      await import('@/components/ranking/RankingView.vue');
    const w = mount(RankingView, {
      global: { stubs: { LeaderboardsPanel: true } },
    });
    const note = w.get('[data-testid="power-rating-coming-soon"]');
    expect(note.text()).toContain('Coming soon');
    expect(note.text()).toContain('Power Rating');
    expect(note.text()).toContain('U15 to U19');
    expect(note.text()).toContain('MLS NEXT Fest');
    expect(note.text()).not.toMatch(/\bgames?\b/i);
    expect(note.text()).not.toMatch(/\b(19|20)\d\d\b|Dec(ember)?\s+\d/);
  });
});
