/**
 * The MT AI chat tab (SB-1500) is listed only for a signed-in user, and only
 * when GET /api/ai/status says the feature is enabled. A failed status check
 * leaves it hidden: the tab is an extra, never a blocker.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import {
  createAuthenticatedUserStore,
  createUnauthenticatedStore,
} from '../../helpers/matchFactories';

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
// usePwaUpdate imports the PWA plugin's virtual module, which only exists
// under the Vite build.
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
  AiChat: { template: '<div data-testid="ai-chat-stub" />' },
};

const storeWithStatus = status => {
  const store = createAuthenticatedUserStore();
  store.userRole = { value: 'team-fan' };
  store.initialize = vi.fn(() => Promise.resolve());
  store.handleOAuthCallback = vi.fn();
  store.clearError = vi.fn();
  store.apiRequest = vi.fn(url => {
    if (url.endsWith('/api/ai/status')) {
      return status instanceof Error
        ? Promise.reject(status)
        : Promise.resolve(status);
    }
    return Promise.resolve([]);
  });
  return store;
};

const mountApp = async (pathname = '/') => {
  window.location.pathname = pathname;
  window.location.hash = '';
  const { default: App } = await import('@/App.vue');
  const wrapper = mount(App, { global: { stubs: STUBS } });
  await flushPromises();
  return wrapper;
};

const tabNames = wrapper =>
  wrapper.findAll('nav[aria-label="Tabs"] button').map(b => b.text());

describe('MT AI chat entry point', () => {
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

  it('shows the Ask tab when signed in and enabled, and opens the chat', async () => {
    mockAuthStore = storeWithStatus({
      enabled: true,
      backend: 'in-app',
      web_chat: true,
    });
    const wrapper = await mountApp();

    expect(mockAuthStore.apiRequest).toHaveBeenCalledWith(
      'http://localhost:8000/api/ai/status'
    );
    const tab = wrapper
      .findAll('nav[aria-label="Tabs"] button')
      .find(b => b.text().startsWith('Ask'));
    expect(tab).toBeTruthy();

    await tab.trigger('click');
    await vi.waitFor(() =>
      expect(wrapper.find('[data-testid="ai-chat-stub"]').exists()).toBe(true)
    );
  });

  it('hides the tab when the feature is disabled', async () => {
    mockAuthStore = storeWithStatus({ enabled: false, backend: null });
    const wrapper = await mountApp();

    expect(tabNames(wrapper).some(n => n.startsWith('Ask'))).toBe(false);
  });

  it('hides the tab while the web chat is not launched (web_chat false)', async () => {
    mockAuthStore = storeWithStatus({
      enabled: true,
      backend: 'in-app',
      web_chat: false,
    });
    const wrapper = await mountApp();

    expect(tabNames(wrapper).some(n => n.startsWith('Ask'))).toBe(false);
  });

  it('hides the tab when the status check fails', async () => {
    mockAuthStore = storeWithStatus(
      Object.assign(new Error('nope'), { status: 503 })
    );
    const wrapper = await mountApp();

    expect(tabNames(wrapper).some(n => n.startsWith('Ask'))).toBe(false);
  });

  it('does not ask, or show the tab, when signed out', async () => {
    mockAuthStore = createUnauthenticatedStore();
    mockAuthStore.userRole = { value: null };
    mockAuthStore.initialize = vi.fn(() => Promise.resolve());
    mockAuthStore.clearError = vi.fn();
    const wrapper = await mountApp();

    expect(mockAuthStore.apiRequest).not.toHaveBeenCalledWith(
      'http://localhost:8000/api/ai/status'
    );
    expect(wrapper.find('nav[aria-label="Tabs"]').exists()).toBe(false);
  });

  it('opens the chat directly at /chat when enabled', async () => {
    mockAuthStore = storeWithStatus({
      enabled: true,
      backend: 'sb-agents',
      web_chat: true,
    });
    const wrapper = await mountApp('/chat');

    await vi.waitFor(() =>
      expect(wrapper.find('[data-testid="ai-chat-stub"]').exists()).toBe(true)
    );
  });
});
