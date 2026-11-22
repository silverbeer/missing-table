/**
 * `/tournaments/<id>` at the App level (SB-1767).
 *
 * Signed in, the link lands on the Tournaments tab with that tournament open.
 * Signed out — Missing Table is invite-only — it shows the normal landing and
 * the login prompt and nothing else: no Tournaments component, and not one
 * `/api/tournaments` request. Signing in then lands on the tournament, and the
 * Google sign-in round trip (which returns to /auth/callback) comes back to it.
 *
 * Harness follows ai/AiChatEntry.spec.js. window.location is a plain object
 * in this suite, so history writes are faked to update its pathname.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import { reactive, ref } from 'vue';

let mockAuthStore;
vi.mock('@/stores/auth', () => ({ useAuthStore: () => mockAuthStore }));
vi.mock('@/config/api', () => ({
  getApiBaseUrl: () => 'http://localhost:8000',
}));
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

const STUBS = {
  AuthNav: true,
  VersionFooter: true,
  InstallBanner: true,
  NotificationSetupGuide: true,
  OfflineIndicator: true,
  UpdateAvailablePrompt: true,
  LeagueTable: true,
  LandingPreview: true,
  MatchDetailView: true,
  LoginForm: { template: '<div data-testid="login-form-stub" />' },
};

const SEASONS = [
  {
    id: 4,
    name: '2026-2027',
    start_date: '2026-08-01',
    end_date: '2027-07-31',
    is_current: true,
  },
];
const CUP = {
  id: 12,
  season_id: 4,
  name: 'Thanksgiving Cup',
  start_date: '2026-11-27',
  end_date: '2026-11-29',
  location: 'Bradenton, FL',
  logo_url: null,
  match_count: 2,
  age_groups: [],
};
const OTHER = { ...CUP, id: 14, name: 'Winter Showcase' };

const routeApi = url => {
  const path = new URL(url).pathname;
  if (path === '/api/seasons') return Promise.resolve(SEASONS);
  if (path === '/api/tournaments') return Promise.resolve([CUP, OTHER]);
  if (path.endsWith('/motd')) return Promise.resolve({ picks: [] });
  if (path === '/api/tournaments/12') {
    return Promise.resolve({ ...CUP, matches: [] });
  }
  if (path === '/api/ai/status') return Promise.resolve({ enabled: false });
  return Promise.resolve([]);
};
const apiRequest = vi.fn(routeApi);

// Reactive, so signing in mid-test drives App's watchers as the real store.
const makeStore = ({ signedIn }) => {
  const session = signedIn ? { access_token: 'test-token' } : null;
  const store = {
    state: reactive({
      loading: false,
      error: null,
      user: signedIn ? { id: 1 } : null,
      session,
      profile: signedIn ? { role: 'team-fan' } : null,
    }),
    isAuthenticated: ref(signedIn),
    isAdmin: { value: false },
    isTeamManager: { value: false },
    isClubManager: { value: false },
    canBrowseAll: { value: false },
    userRole: { value: signedIn ? 'team-fan' : null },
    // Plain ids: TournamentMatchCenter unrefs these.
    userTeamId: null,
    userClubId: null,
    apiRequest,
    initialize: vi.fn(() => Promise.resolve()),
    handleOAuthCallback: vi.fn(),
    clearError: vi.fn(),
  };
  store.signIn = () => {
    store.state.user = { id: 1 };
    store.state.session = { access_token: 'test-token' };
    store.state.profile = { role: 'team-fan' };
    store.userRole.value = 'team-fan';
    store.isAuthenticated.value = true;
  };
  // Logout or an expired session: the session goes, and with it the tabs.
  store.signOut = () => {
    store.state.user = null;
    store.state.session = null;
    store.state.profile = null;
    store.userRole.value = null;
    store.isAuthenticated.value = false;
  };
  return store;
};

const fakeHistory = () => {
  const set = (_s, _t, url) => {
    window.location.pathname = url;
  };
  return {
    push: vi.spyOn(window.history, 'pushState').mockImplementation(set),
    replace: vi.spyOn(window.history, 'replaceState').mockImplementation(set),
  };
};

let wrapper = null;

const mountApp = async (pathname, hash = '') => {
  window.location.pathname = pathname;
  window.location.hash = hash;
  const { default: App } = await import('@/App.vue');
  wrapper = mount(App, { global: { stubs: STUBS } });
  await flushPromises();
  return wrapper;
};

const tournamentRequests = () =>
  apiRequest.mock.calls.filter(([url]) => url.includes('/api/tournaments'));
const fetchedTournaments = () =>
  global.fetch.mock.calls.filter(([url]) =>
    String(url).includes('/api/tournaments')
  );
const activeTab = w =>
  w
    .findAll('nav[aria-label="Tabs"] button')
    .find(b => b.classes().includes('border-brand-500'))
    ?.text();
const heroName = w => w.find('[data-testid="tournament-hero"] h2');

describe('a tournament link', () => {
  beforeEach(() => {
    vi.resetModules();
    apiRequest.mockClear();
    apiRequest.mockImplementation(routeApi);
    global.fetch = vi.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve({}) })
    );
    window.sessionStorage.clear();
    fakeHistory();
  });

  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = null;
    vi.restoreAllMocks();
    delete window.location.pathname;
    delete window.location.hash;
    window.sessionStorage.clear();
    window.history.replaceState(null, '', '/');
  });

  it('signed in, lands on the Tournaments tab with that tournament open', async () => {
    mockAuthStore = makeStore({ signedIn: true });
    const w = await mountApp('/tournaments/12');

    await vi.waitFor(() =>
      expect(heroName(w).exists() && heroName(w).text()).toBe(
        'Thanksgiving Cup'
      )
    );
    expect(activeTab(w)).toBe('Tournaments');
    expect(window.location.pathname).toBe('/tournaments/12');
    expect(w.find('.modal-overlay').exists()).toBe(false);
  });

  it('signed out, shows the login prompt and nothing about the tournament', async () => {
    mockAuthStore = makeStore({ signedIn: false });
    const w = await mountApp('/tournaments/12');
    await flushPromises();

    // The normal logged-out landing, with the login prompt open over it.
    expect(w.text()).toContain("The table you've been missing.");
    expect(w.find('.modal-overlay').exists()).toBe(true);
    expect(w.find('[data-testid="login-form-stub"]').exists()).toBe(true);
    // Nothing tournament-related mounted, rendered or requested.
    expect(w.findComponent({ name: 'TournamentMatchCenter' }).exists()).toBe(
      false
    );
    expect(w.find('nav[aria-label="Tabs"]').exists()).toBe(false);
    expect(w.text()).not.toContain('Thanksgiving Cup');
    expect(tournamentRequests()).toHaveLength(0);
    expect(fetchedTournaments()).toHaveLength(0);
    // The page title is never the tournament's.
    expect(document.title).not.toContain('Thanksgiving Cup');
    // The URL stays, so sign-in can come back to it.
    expect(window.location.pathname).toBe('/tournaments/12');
    expect(window.sessionStorage.getItem('mt_return_path')).toBe(
      '/tournaments/12'
    );
  });

  it('signing in from there lands on that tournament', async () => {
    mockAuthStore = makeStore({ signedIn: false });
    const w = await mountApp('/tournaments/12');
    expect(tournamentRequests()).toHaveLength(0);

    mockAuthStore.signIn();
    await flushPromises();

    await vi.waitFor(() =>
      expect(heroName(w).exists() && heroName(w).text()).toBe(
        'Thanksgiving Cup'
      )
    );
    expect(activeTab(w)).toBe('Tournaments');
    expect(window.location.pathname).toBe('/tournaments/12');
    expect(window.sessionStorage.getItem('mt_return_path')).toBe(null);
  });

  it('the Google sign-in round trip returns to the tournament', async () => {
    window.sessionStorage.setItem('mt_return_path', '/tournaments/12');
    mockAuthStore = makeStore({ signedIn: false });
    mockAuthStore.handleOAuthCallback = vi.fn(async () => {
      mockAuthStore.signIn();
      return { success: true };
    });
    const w = await mountApp('/auth/callback', '#access_token=abc');

    await vi.waitFor(() =>
      expect(heroName(w).exists() && heroName(w).text()).toBe(
        'Thanksgiving Cup'
      )
    );
    expect(activeTab(w)).toBe('Tournaments');
    expect(window.location.pathname).toBe('/tournaments/12');
    expect(window.sessionStorage.getItem('mt_return_path')).toBe(null);
  });

  it('a stored return path that is not a tournaments path is ignored', async () => {
    window.sessionStorage.setItem('mt_return_path', 'https://evil.test/');
    mockAuthStore = makeStore({ signedIn: false });
    mockAuthStore.handleOAuthCallback = vi.fn(async () => {
      mockAuthStore.signIn();
      return { success: true };
    });
    const w = await mountApp('/auth/callback', '#access_token=abc');

    expect(window.location.pathname).toBe('/');
    expect(activeTab(w)).toBe('Profile');
  });

  it('leaving the tab resets the URL', async () => {
    mockAuthStore = makeStore({ signedIn: true });
    const w = await mountApp('/tournaments/12');
    await vi.waitFor(() => expect(heroName(w).exists()).toBe(true));

    const table = w
      .findAll('nav[aria-label="Tabs"] button')
      .find(b => b.text() === 'Table');
    await table.trigger('click');
    await flushPromises();

    expect(activeTab(w)).toBe('Table');
    expect(window.location.pathname).toBe('/');
  });

  it('browser back onto a tournaments path opens the tab; off it leaves', async () => {
    mockAuthStore = makeStore({ signedIn: true });
    const w = await mountApp('/');
    expect(activeTab(w)).toBe('Table');

    window.location.pathname = '/tournaments/12';
    window.dispatchEvent(new PopStateEvent('popstate', { state: null }));
    await vi.waitFor(() =>
      expect(heroName(w).exists() && heroName(w).text()).toBe(
        'Thanksgiving Cup'
      )
    );
    expect(activeTab(w)).toBe('Tournaments');

    window.location.pathname = '/';
    window.dispatchEvent(new PopStateEvent('popstate', { state: null }));
    await flushPromises();
    expect(activeTab(w)).toBe('Table');
  });

  it('signed out, back / forward onto a tournaments path fetches nothing', async () => {
    mockAuthStore = makeStore({ signedIn: false });
    const w = await mountApp('/');

    window.location.pathname = '/tournaments/12';
    window.dispatchEvent(new PopStateEvent('popstate', { state: null }));
    await flushPromises();

    expect(w.findComponent({ name: 'TournamentMatchCenter' }).exists()).toBe(
      false
    );
    expect(w.text()).not.toContain('Thanksgiving Cup');
    expect(tournamentRequests()).toHaveLength(0);
    expect(fetchedTournaments()).toHaveLength(0);
  });

  it('signing out on a tournament returns the URL to / and fetches nothing more', async () => {
    mockAuthStore = makeStore({ signedIn: true });
    const w = await mountApp('/tournaments/12');
    await vi.waitFor(() => expect(heroName(w).exists()).toBe(true));

    const before = apiRequest.mock.calls.length;
    mockAuthStore.signOut();
    await flushPromises();

    expect(window.location.pathname).toBe('/');
    expect(w.findComponent({ name: 'TournamentMatchCenter' }).exists()).toBe(
      false
    );
    expect(w.text()).not.toContain('Thanksgiving Cup');
    const after = apiRequest.mock.calls
      .slice(before)
      .map(([url]) => url)
      .filter(url => url.includes('/api/tournaments'));
    expect(after).toEqual([]);
  });

  it('signing out while the list is in flight sends no request afterwards', async () => {
    let releaseList;
    const listGate = new Promise(resolve => {
      releaseList = () => resolve([CUP, OTHER]);
    });
    apiRequest.mockImplementation(url =>
      new URL(url).pathname === '/api/tournaments' ? listGate : routeApi(url)
    );
    mockAuthStore = makeStore({ signedIn: true });
    const w = await mountApp('/tournaments/12');
    await vi.waitFor(() =>
      expect(w.findComponent({ name: 'TournamentMatchCenter' }).exists()).toBe(
        true
      )
    );
    await vi.waitFor(() =>
      expect(
        tournamentRequests().some(
          ([url]) => new URL(url).pathname === '/api/tournaments'
        )
      ).toBe(true)
    );

    mockAuthStore.signOut();
    await flushPromises();
    const before = apiRequest.mock.calls.length;

    releaseList();
    await flushPromises();

    expect(
      apiRequest.mock.calls
        .slice(before)
        .map(([url]) => url)
        .filter(url => url.includes('/api/tournaments'))
    ).toEqual([]);
    expect(window.location.pathname).toBe('/');
  });

  it('a normal home load clears a stored return path', async () => {
    window.sessionStorage.setItem('mt_return_path', '/tournaments/12');
    mockAuthStore = makeStore({ signedIn: false });
    await mountApp('/');
    expect(window.sessionStorage.getItem('mt_return_path')).toBe(null);
  });

  it('a failed Google sign-in clears a stored return path and lands on /', async () => {
    window.sessionStorage.setItem('mt_return_path', '/tournaments/12');
    mockAuthStore = makeStore({ signedIn: false });
    mockAuthStore.handleOAuthCallback = vi.fn(async () => ({
      success: false,
      error: 'denied',
    }));
    const w = await mountApp('/auth/callback', '#access_token=abc');

    expect(window.sessionStorage.getItem('mt_return_path')).toBe(null);
    expect(window.location.pathname).toBe('/');
    expect(w.findComponent({ name: 'TournamentMatchCenter' }).exists()).toBe(
      false
    );
    expect(tournamentRequests()).toHaveLength(0);
  });
});
