import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import VersionFooter from '@/components/VersionFooter.vue';
import {
  createMockAuthStore,
  createAuthenticatedUserStore,
  createUnauthenticatedStore,
} from '../helpers/matchFactories';

let mockAuthStore;

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => mockAuthStore,
}));

const mountFooter = async () => {
  const wrapper = mount(VersionFooter, {
    global: {
      stubs: {
        SupportEmailLink: true,
        Teleport: true,
      },
    },
  });
  await flushPromises();
  return wrapper;
};

describe('VersionFooter visibility gating', () => {
  beforeEach(() => {
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({ version: '1.6.9.1118', status: 'healthy' }),
      })
    );
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('hides version and health badge for anonymous visitors', async () => {
    mockAuthStore = createUnauthenticatedStore();
    const wrapper = await mountFooter();

    expect(wrapper.find('[data-testid="whats-new-trigger"]').exists()).toBe(
      false
    );
    expect(wrapper.find('.status-indicator').text()).toBe('');
    expect(wrapper.text()).not.toContain('1.6.9.1118');
    expect(wrapper.text()).not.toContain('Healthy');
  });

  it('shows version but not health badge for regular members', async () => {
    mockAuthStore = createAuthenticatedUserStore();
    const wrapper = await mountFooter();

    expect(wrapper.find('[data-testid="whats-new-trigger"]').text()).toBe(
      '1.6.9.1118'
    );
    expect(wrapper.text()).not.toContain('Healthy');
  });

  it('shows version and health badge for admins', async () => {
    mockAuthStore = createMockAuthStore();
    const wrapper = await mountFooter();

    expect(wrapper.find('[data-testid="whats-new-trigger"]').text()).toBe(
      '1.6.9.1118'
    );
    expect(wrapper.text()).toContain('Healthy');
  });

  it('keeps copyright and support link for everyone', async () => {
    mockAuthStore = createUnauthenticatedStore();
    const wrapper = await mountFooter();

    expect(wrapper.text()).toContain('Missing Table');
    expect(wrapper.text()).toContain('Need help?');
  });

  it('hides the Android install button from anonymous visitors (invite-only)', async () => {
    mockAuthStore = createUnauthenticatedStore();
    const wrapper = await mountFooter();

    expect(wrapper.find('[data-testid="android-install-link"]').exists()).toBe(
      false
    );
  });

  it('shows the Android install button to authenticated users', async () => {
    mockAuthStore = createAuthenticatedUserStore();
    const wrapper = await mountFooter();

    const btn = wrapper.find('[data-testid="android-install-link"]');
    expect(btn.exists()).toBe(true);
    // No public URL is embedded — it's a button that fetches a presigned URL.
    expect(btn.attributes('href')).toBeUndefined();
  });

  it('fetches a presigned URL from the backend when the install button is clicked', async () => {
    mockAuthStore = createAuthenticatedUserStore();
    mockAuthStore.apiRequest = vi.fn(() =>
      Promise.resolve({ download_url: 'https://r2.example/signed/app.apk' })
    );
    const wrapper = await mountFooter();

    await wrapper.find('[data-testid="android-install-link"]').trigger('click');
    expect(mockAuthStore.apiRequest).toHaveBeenCalledWith(
      expect.stringContaining('/api/android/apk-url')
    );
  });

  it('still emits open-whats-new from the version button for members', async () => {
    mockAuthStore = createAuthenticatedUserStore();
    const wrapper = await mountFooter();

    await wrapper.find('[data-testid="whats-new-trigger"]').trigger('click');
    expect(wrapper.emitted('open-whats-new')).toHaveLength(1);
  });
});
