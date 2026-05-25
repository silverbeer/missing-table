/**
 * useAdminAttentionCounts tests.
 *
 * The composable is a reactive singleton — module-level state persists
 * across calls within a test file. Each test resets the relevant refs
 * via fetchCounts mocked responses so we don't fight that.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock fetch globally for these tests.
const fetchMock = vi.fn();
global.fetch = fetchMock;

// Mock the auth store so isAdmin is controllable per test.
const isAdminRef = { value: true };
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    isAdmin: isAdminRef,
    getAuthHeaders: () => ({ Authorization: 'Bearer test' }),
  }),
}));

vi.mock('@/config/api', () => ({
  getApiBaseUrl: () => 'http://test.example',
}));

import { useAdminAttentionCounts } from '@/composables/useAdminAttentionCounts';

beforeEach(() => {
  fetchMock.mockReset();
  isAdminRef.value = true;
});

describe('useAdminAttentionCounts.fetchCounts', () => {
  it('hits /api/admin/attention/counts and exposes total + breakdown', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          invite_requests: 3,
          channel_requests: 1,
          support_inbox: 2,
          total: 6,
        }),
    });

    const inbox = useAdminAttentionCounts();
    await inbox.fetchCounts();

    expect(fetchMock).toHaveBeenCalledWith(
      'http://test.example/api/admin/attention/counts',
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: 'Bearer test' }),
      })
    );
    expect(inbox.total.value).toBe(6);
    expect(inbox.breakdown.value).toEqual({
      invite_requests: 3,
      channel_requests: 1,
      support_inbox: 2,
    });
  });

  it('skips the fetch and zeros total when user is not admin', async () => {
    isAdminRef.value = false;
    const inbox = useAdminAttentionCounts();
    await inbox.fetchCounts();
    expect(fetchMock).not.toHaveBeenCalled();
    expect(inbox.total.value).toBe(0);
  });

  it('keeps the prior total when the fetch fails (best-effort badge)', async () => {
    // Seed a non-zero state via a successful call first.
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          total: 5,
          invite_requests: 5,
          channel_requests: 0,
          support_inbox: 0,
        }),
    });
    const inbox = useAdminAttentionCounts();
    await inbox.fetchCounts();
    expect(inbox.total.value).toBe(5);

    // Now the next call fails.
    fetchMock.mockResolvedValueOnce({ ok: false, status: 500 });
    await inbox.fetchCounts();

    // Total stays at the last good value, error is captured.
    expect(inbox.total.value).toBe(5);
    expect(inbox.lastError.value).toBeTruthy();
  });
});

describe('useAdminAttentionCounts.tooltip', () => {
  it('summarizes only the non-zero queues with correct pluralization', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          invite_requests: 1,
          channel_requests: 0,
          support_inbox: 4,
          total: 5,
        }),
    });
    const inbox = useAdminAttentionCounts();
    await inbox.fetchCounts();
    expect(inbox.tooltip.value).toBe(
      '1 invite request · 4 unread support messages'
    );
  });

  it('falls back to a friendly empty message when nothing is pending', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          invite_requests: 0,
          channel_requests: 0,
          support_inbox: 0,
          total: 0,
        }),
    });
    const inbox = useAdminAttentionCounts();
    await inbox.fetchCounts();
    expect(inbox.tooltip.value).toBe('No items need attention');
  });
});
