/**
 * Privacy policy page (SB-1310)
 *
 * /privacy is linked from the App Store / TestFlight listing, so Apple's
 * reviewer arrives with no session. App.vue must render the policy for a
 * deep-linked, logged-out visitor — and must not hold it behind the auth
 * loading spinner or swap it for the invite-only landing page.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import { createUnauthenticatedStore } from '../helpers/matchFactories';

let mockAuthStore;

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => mockAuthStore,
}));

// usePwaUpdate imports the PWA plugin's virtual module, which only exists
// under the Vite build.
vi.mock('@/composables/usePwaUpdate', () => ({
  usePwaUpdate: () => ({}),
}));

const CHROME_STUBS = {
  AuthNav: true,
  VersionFooter: true,
  InstallBanner: true,
  NotificationSetupGuide: true,
  OfflineIndicator: true,
  UpdateAvailablePrompt: true,
  LeagueTable: true,
  LandingPreview: true,
};

const unauthenticatedStore = ({ loading = false } = {}) => {
  const store = createUnauthenticatedStore();
  store.state.loading = loading;
  store.userRole = { value: null };
  store.initialize = vi.fn(() => new Promise(() => {}));
  store.handleOAuthCallback = vi.fn();
  store.clearError = vi.fn();
  return store;
};

const mountAppAt = async pathname => {
  window.location.pathname = pathname;
  window.location.hash = '';
  const { default: App } = await import('@/App.vue');
  const wrapper = mount(App, { global: { stubs: CHROME_STUBS } });
  await flushPromises();
  return wrapper;
};

describe('Privacy policy route', () => {
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

  it('renders the policy at /privacy for a logged-out visitor', async () => {
    mockAuthStore = unauthenticatedStore();
    const wrapper = await mountAppAt('/privacy');

    // PrivacyPolicy is a lazy chunk; wait for the dynamic import to land.
    await vi.waitFor(() =>
      expect(wrapper.find('[data-testid="privacy-policy"]').exists()).toBe(true)
    );
    const policy = wrapper.find('[data-testid="privacy-policy"]');
    expect(policy.text()).toContain('Privacy Policy');
    expect(policy.text()).toContain('October 10, 2026');
    expect(policy.text()).toContain('support@contact.missingtable.com');
    // Not the invite-only landing page.
    expect(wrapper.text()).not.toContain('Request Invite');
  });

  it('does not wait for auth to finish loading', async () => {
    mockAuthStore = unauthenticatedStore({ loading: true });
    const wrapper = await mountAppAt('/privacy/');

    await vi.waitFor(() =>
      expect(wrapper.find('[data-testid="privacy-policy"]').exists()).toBe(true)
    );
    expect(wrapper.find('.loading-container').exists()).toBe(false);
  });

  it('shows the landing page, not the policy, at /', async () => {
    mockAuthStore = unauthenticatedStore();
    const wrapper = await mountAppAt('/');

    expect(wrapper.find('[data-testid="privacy-policy"]').exists()).toBe(false);
    expect(wrapper.text()).toContain('Request Invite');
  });
});
