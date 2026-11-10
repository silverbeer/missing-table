/**
 * ClubNotificationChannels.vue Tests
 *
 * Covers:
 * - Render both rows (telegram, discord) from GET response
 * - Configured state shows hint + reset/test/toggle controls
 * - Toggle PATCHes `enabled` and never deletes the destination
 * - Setup steps from the registry, open until configured
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

const PLATFORMS = [
  {
    id: 'telegram',
    label: 'Telegram',
    icon: '✈️',
    placeholder: 'chat id',
    hint: 'hint',
    setup_steps: ['Add the bot to your group.', 'Paste the chat ID.'],
    destination_pattern: '^(@\\w+|-?\\d+)$',
    destination_error: 'Telegram destination is invalid',
    capabilities: [],
  },
  {
    id: 'discord',
    label: 'Discord',
    icon: '💬',
    placeholder: 'webhook',
    hint: 'hint',
    destination_pattern:
      '^https://discord(app)?\\.com/api/webhooks/\\d+/[\\w-]+$',
    destination_error: 'Discord destination is invalid',
    capabilities: [],
  },
];

const mkMount = (initialChannels = []) => {
  globalThis.fetch = vi
    .fn()
    .mockImplementation(async url =>
      String(url).endsWith('/api/notifications/platforms')
        ? mockResponse(200, PLATFORMS)
        : mockResponse(200, initialChannels)
    );
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

    it('renders whatever platforms the registry serves', async () => {
      globalThis.fetch = vi
        .fn()
        .mockImplementation(async url =>
          String(url).endsWith('/api/notifications/platforms')
            ? mockResponse(200, [{ ...PLATFORMS[0], id: 'newchat' }])
            : mockResponse(200, [])
        );
      const wrapper = mount(ClubNotificationChannels, {
        props: { clubId: 42 },
      });
      await flushPromises();

      expect(wrapper.find('[data-testid="row-newchat"]').exists()).toBe(true);
      expect(wrapper.find('[data-testid="row-telegram"]').exists()).toBe(false);
    });

    it('shows an error with retry when platforms cannot load', async () => {
      globalThis.fetch = vi
        .fn()
        .mockImplementation(async url =>
          String(url).endsWith('/api/notifications/platforms')
            ? mockResponse(500, {})
            : mockResponse(200, [])
        );
      const wrapper = mount(ClubNotificationChannels, {
        props: { clubId: 42 },
      });
      await flushPromises();

      expect(wrapper.text()).toContain('Failed to load platforms');
      expect(wrapper.find('button.link').exists()).toBe(true);
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

  describe('setup steps', () => {
    it('shows numbered steps, open while the platform is unconfigured', async () => {
      const wrapper = mkMount([]);
      await flushPromises();

      const setup = wrapper.find('[data-testid="setup-telegram"]');
      expect(setup.attributes('open')).toBeDefined();
      expect(setup.findAll('li').map(li => li.text())).toEqual([
        'Add the bot to your group.',
        'Paste the chat ID.',
      ]);
    });

    it('collapses the steps once configured', async () => {
      const wrapper = mkMount([
        { platform: 'telegram', enabled: true, configured: true, hint: '7890' },
      ]);
      await flushPromises();

      expect(
        wrapper.find('[data-testid="setup-telegram"]').attributes('open')
      ).toBeUndefined();
    });

    it('falls back to the one-line hint when a platform has no steps', async () => {
      const wrapper = mkMount([]);
      await flushPromises();

      const row = wrapper.find('[data-testid="row-discord"]');
      expect(row.find('[data-testid="setup-discord"]').exists()).toBe(false);
      expect(row.find('.hint-text').text()).toBe('hint');
    });
  });

  describe('enable toggle (PATCH)', () => {
    it('pauses with PATCH and keeps the destination', async () => {
      const wrapper = mkMount([
        { platform: 'telegram', enabled: true, configured: true, hint: '7890' },
      ]);
      await flushPromises();

      await wrapper.find('[data-testid="toggle-telegram"]').setValue(false);
      await flushPromises();

      const patch = fetch.mock.calls.find(c => c[1]?.method === 'PATCH');
      expect(patch[0]).toBe(
        'http://localhost:8000/api/clubs/42/notifications/telegram'
      );
      expect(JSON.parse(patch[1].body)).toEqual({ enabled: false });
      expect(fetch.mock.calls.some(c => c[1]?.method === 'DELETE')).toBe(false);
    });

    it('resumes with PATCH, no destination needed', async () => {
      const wrapper = mkMount([
        {
          platform: 'telegram',
          enabled: false,
          configured: true,
          hint: '7890',
        },
      ]);
      await flushPromises();

      await wrapper.find('[data-testid="toggle-telegram"]').setValue(true);
      await flushPromises();

      const patch = fetch.mock.calls.find(c => c[1]?.method === 'PATCH');
      expect(JSON.parse(patch[1].body)).toEqual({ enabled: true });
    });

    it('labels a disabled channel as paused, not configured', async () => {
      const wrapper = mkMount([
        {
          platform: 'telegram',
          enabled: false,
          configured: true,
          hint: '7890',
        },
      ]);
      await flushPromises();

      const status = wrapper.find('[data-testid="status-telegram"]').text();
      expect(status).toContain('Paused');
      expect(status).toContain('7890');
    });

    it('shows the server error when the PATCH fails', async () => {
      const wrapper = mkMount([
        { platform: 'telegram', enabled: true, configured: true, hint: '7890' },
      ]);
      await flushPromises();
      fetch.mockImplementation(async (url, opts) =>
        opts?.method === 'PATCH'
          ? mockResponse(404, { detail: 'No channel configured' })
          : mockResponse(200, [])
      );

      await wrapper.find('[data-testid="toggle-telegram"]').setValue(false);
      await flushPromises();

      expect(wrapper.find('[data-testid="flash-error"]').text()).toContain(
        'No channel configured'
      );
    });
  });

  describe('heading', () => {
    it('can hide its own title where the page has one', async () => {
      globalThis.fetch = vi.fn(async url =>
        String(url).endsWith('/api/notifications/platforms')
          ? mockResponse(200, PLATFORMS)
          : mockResponse(200, [])
      );
      const wrapper = mount(ClubNotificationChannels, {
        props: { clubId: 42, showTitle: false },
      });
      await flushPromises();

      expect(wrapper.find('.title').exists()).toBe(false);
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
      // Only the two load GETs (platforms, channels). No PUT.
      expect(globalThis.fetch).toHaveBeenCalledTimes(2);
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
      expect(globalThis.fetch).toHaveBeenCalledTimes(2);
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
