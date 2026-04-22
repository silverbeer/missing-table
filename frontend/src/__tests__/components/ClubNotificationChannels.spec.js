/**
 * ClubNotificationChannels.vue Tests
 *
 * Covers:
 * - Render both rows (telegram, discord) from GET response
 * - Configured state shows hint + reset/test/toggle controls
 * - Unconfigured state shows input + save with client-side validation
 * - PUT on save; DELETE on reset; POST on test-send
 * - Rate limit (429), kill switch (503), Phase 3 stub (501) surface as warnings
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import ClubNotificationChannels from '@/components/notifications/ClubNotificationChannels.vue';

let mockAuthStore;

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => mockAuthStore,
}));

vi.mock('@/config/api', () => ({
  getApiBaseUrl: () => 'http://localhost:8000',
}));

const mockResponse = (status, body) => ({
  ok: status >= 200 && status < 300,
  status,
  json: async () => body,
});

const mkMount = (initialChannels = []) => {
  globalThis.fetch = vi
    .fn()
    .mockResolvedValue(mockResponse(200, initialChannels));
  return mount(ClubNotificationChannels, {
    props: { clubId: 42 },
  });
};

describe('ClubNotificationChannels', () => {
  beforeEach(() => {
    mockAuthStore = {
      getAuthHeaders: () => ({ Authorization: 'Bearer test-token' }),
    };
    // jsdom doesn't define confirm by default
    globalThis.confirm = vi.fn(() => true);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('rendering', () => {
    it('renders both telegram and discord rows', async () => {
      const wrapper = mkMount([]);
      await flushPromises();

      expect(wrapper.find('[data-testid="row-telegram"]').exists()).toBe(true);
      expect(wrapper.find('[data-testid="row-discord"]').exists()).toBe(true);
    });

    it('shows "Not configured" when the backend returns no channels', async () => {
      const wrapper = mkMount([]);
      await flushPromises();

      expect(wrapper.find('[data-testid="input-telegram"]').exists()).toBe(
        true
      );
      expect(wrapper.find('[data-testid="save-telegram"]').exists()).toBe(true);
    });

    it('shows configured state with hint when backend returns a channel', async () => {
      const wrapper = mkMount([
        { platform: 'telegram', enabled: true, configured: true, hint: '7890' },
      ]);
      await flushPromises();

      const status = wrapper.find('[data-testid="status-telegram"]');
      expect(status.exists()).toBe(true);
      expect(status.text()).toContain('7890');
      expect(wrapper.find('[data-testid="reset-telegram"]').exists()).toBe(
        true
      );
      expect(wrapper.find('[data-testid="test-telegram"]').exists()).toBe(true);
    });
  });

  describe('save (PUT)', () => {
    it('rejects invalid telegram input with inline error', async () => {
      const wrapper = mkMount([]);
      await flushPromises();

      await wrapper
        .find('[data-testid="input-telegram"]')
        .setValue('not-a-chat');
      await wrapper.find('[data-testid="save-telegram"]').trigger('click');
      await flushPromises();

      expect(wrapper.find('[data-testid="error-telegram"]').exists()).toBe(
        true
      );
      // fetch was called once (the initial GET). No second fetch for PUT.
      expect(globalThis.fetch).toHaveBeenCalledTimes(1);
    });

    it('rejects invalid discord input with inline error', async () => {
      const wrapper = mkMount([]);
      await flushPromises();

      await wrapper
        .find('[data-testid="input-discord"]')
        .setValue('https://example.com/x');
      await wrapper.find('[data-testid="save-discord"]').trigger('click');
      await flushPromises();

      expect(wrapper.find('[data-testid="error-discord"]').exists()).toBe(true);
      expect(globalThis.fetch).toHaveBeenCalledTimes(1);
    });

    it('PUTs valid telegram destination and re-fetches', async () => {
      const wrapper = mkMount([]);
      await flushPromises();

      // Subsequent fetches: PUT success, then GET updated list
      globalThis.fetch
        .mockResolvedValueOnce(
          mockResponse(200, {
            platform: 'telegram',
            enabled: true,
            configured: true,
            hint: '7890',
          })
        )
        .mockResolvedValueOnce(
          mockResponse(200, [
            {
              platform: 'telegram',
              enabled: true,
              configured: true,
              hint: '7890',
            },
          ])
        );

      await wrapper
        .find('[data-testid="input-telegram"]')
        .setValue('-1001234567890');
      await wrapper.find('[data-testid="save-telegram"]').trigger('click');
      await flushPromises();

      const calls = globalThis.fetch.mock.calls;
      const putCall = calls.find(c => c[1]?.method === 'PUT');
      expect(putCall).toBeDefined();
      expect(putCall[0]).toContain('/api/clubs/42/notifications/telegram');
      expect(JSON.parse(putCall[1].body)).toEqual({
        destination: '-1001234567890',
        enabled: true,
      });

      expect(wrapper.find('[data-testid="flash-success"]').exists()).toBe(true);
    });

    it('accepts a valid discord webhook URL', async () => {
      const wrapper = mkMount([]);
      await flushPromises();

      globalThis.fetch
        .mockResolvedValueOnce(
          mockResponse(200, {
            platform: 'discord',
            enabled: true,
            configured: true,
            hint: 'n123',
          })
        )
        .mockResolvedValueOnce(mockResponse(200, []));

      await wrapper
        .find('[data-testid="input-discord"]')
        .setValue('https://discord.com/api/webhooks/12345/abc-DEF_token123');
      await wrapper.find('[data-testid="save-discord"]').trigger('click');
      await flushPromises();

      const putCall = globalThis.fetch.mock.calls.find(
        c => c[1]?.method === 'PUT'
      );
      expect(putCall[0]).toContain('/api/clubs/42/notifications/discord');
    });
  });

  describe('reset (DELETE)', () => {
    it('DELETEs the channel and re-fetches on reset', async () => {
      const wrapper = mkMount([
        { platform: 'telegram', enabled: true, configured: true, hint: '7890' },
      ]);
      await flushPromises();

      globalThis.fetch
        .mockResolvedValueOnce(mockResponse(204, null))
        .mockResolvedValueOnce(mockResponse(200, []));

      await wrapper.find('[data-testid="reset-telegram"]').trigger('click');
      await flushPromises();

      const deleteCall = globalThis.fetch.mock.calls.find(
        c => c[1]?.method === 'DELETE'
      );
      expect(deleteCall).toBeDefined();
      expect(deleteCall[0]).toContain('/api/clubs/42/notifications/telegram');
    });

    it('no-ops reset when user declines confirm', async () => {
      globalThis.confirm = vi.fn(() => false);
      const wrapper = mkMount([
        { platform: 'telegram', enabled: true, configured: true, hint: '7890' },
      ]);
      await flushPromises();

      await wrapper.find('[data-testid="reset-telegram"]').trigger('click');
      await flushPromises();

      const deleteCall = globalThis.fetch.mock.calls.find(
        c => c[1]?.method === 'DELETE'
      );
      expect(deleteCall).toBeUndefined();
    });
  });

  describe('test send (POST)', () => {
    it('POSTs to /test and shows success flash when sender succeeds', async () => {
      const wrapper = mkMount([
        { platform: 'telegram', enabled: true, configured: true, hint: '7890' },
      ]);
      await flushPromises();

      globalThis.fetch.mockResolvedValueOnce(
        mockResponse(200, { success: true, error: null })
      );

      await wrapper.find('[data-testid="test-telegram"]').trigger('click');
      await flushPromises();

      const postCall = globalThis.fetch.mock.calls.find(
        c => c[1]?.method === 'POST'
      );
      expect(postCall[0]).toContain(
        '/api/clubs/42/notifications/telegram/test'
      );
      expect(wrapper.find('[data-testid="flash-success"]').exists()).toBe(true);
    });

    it('surfaces 429 as rate-limit warning flash', async () => {
      const wrapper = mkMount([
        { platform: 'telegram', enabled: true, configured: true, hint: '7890' },
      ]);
      await flushPromises();

      globalThis.fetch.mockResolvedValueOnce(
        mockResponse(429, { detail: 'rate limit' })
      );

      await wrapper.find('[data-testid="test-telegram"]').trigger('click');
      await flushPromises();

      const flash = wrapper.find('[data-testid="flash-warning"]');
      expect(flash.exists()).toBe(true);
      expect(flash.text()).toMatch(/rate limit/i);
    });

    it('surfaces 503 as kill-switch warning flash', async () => {
      const wrapper = mkMount([
        { platform: 'telegram', enabled: true, configured: true, hint: '7890' },
      ]);
      await flushPromises();

      globalThis.fetch.mockResolvedValueOnce(mockResponse(503, {}));

      await wrapper.find('[data-testid="test-telegram"]').trigger('click');
      await flushPromises();

      const flash = wrapper.find('[data-testid="flash-warning"]');
      expect(flash.exists()).toBe(true);
      expect(flash.text()).toMatch(/disabled/i);
    });

    it('surfaces 501 from Phase 3 stub as warning flash', async () => {
      const wrapper = mkMount([
        { platform: 'telegram', enabled: true, configured: true, hint: '7890' },
      ]);
      await flushPromises();

      globalThis.fetch.mockResolvedValueOnce(mockResponse(501, {}));

      await wrapper.find('[data-testid="test-telegram"]').trigger('click');
      await flushPromises();

      expect(wrapper.find('[data-testid="flash-warning"]').exists()).toBe(true);
    });
  });
});
