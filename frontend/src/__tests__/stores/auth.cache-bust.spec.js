/**
 * Post-write service-worker cache busting in apiCall (SB-902).
 *
 * The SW answers the cached read APIs from its own cache first, so an admin
 * who POSTs a tournament match and immediately re-fetches the tournament gets
 * the pre-write copy back — the new row only shows up after a reload. Every
 * write that goes through the auth store therefore drops that cache; reads
 * must not, or the cache would never serve anything.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { useAuthStore } from '@/stores/auth';
import { bustApiCache } from '@/utils/swCache';

vi.mock('@/utils/swCache', async importOriginal => {
  const actual = await importOriginal();
  return { ...actual, bustApiCache: vi.fn().mockResolvedValue(true) };
});

const jsonResponse = (body = {}, status = 200) => ({
  ok: status >= 200 && status < 300,
  status,
  headers: { get: () => null },
  json: async () => body,
});

describe('auth store — write invalidates the SW read cache (SB-902)', () => {
  let store;

  beforeEach(() => {
    store = useAuthStore();
    store.forceLogout();
    global.fetch.mockReset();
    bustApiCache.mockClear();
  });

  it.each(['POST', 'PUT', 'PATCH', 'DELETE'])(
    'busts the cache after a successful %s',
    async method => {
      global.fetch.mockResolvedValue(jsonResponse({ id: 1 }, 201));
      await store.apiCall('/api/admin/tournaments/6/matches', { method });
      expect(bustApiCache).toHaveBeenCalledTimes(1);
    }
  );

  it('leaves the cache alone on a GET', async () => {
    global.fetch.mockResolvedValue(jsonResponse([{ id: 1 }]));
    await store.apiCall('/api/tournaments/6');
    expect(bustApiCache).not.toHaveBeenCalled();
  });

  it('leaves the cache alone when the write fails', async () => {
    global.fetch.mockResolvedValue(jsonResponse({ detail: 'nope' }, 422));
    await expect(
      store.apiCall('/api/admin/tournaments/6/matches', { method: 'POST' })
    ).rejects.toThrow('nope');
    expect(bustApiCache).not.toHaveBeenCalled();
  });

  it('busts the cache when the write succeeds only after a token refresh', async () => {
    localStorage.setItem('refresh_token', 'r1');
    global.fetch
      .mockResolvedValueOnce(jsonResponse({ detail: 'expired' }, 401))
      // POST /api/auth/refresh
      .mockResolvedValueOnce(
        jsonResponse({
          session: { access_token: 'a2', refresh_token: 'r2' },
        })
      )
      .mockResolvedValueOnce(jsonResponse({ id: 1 }, 201));

    await store.apiCall('/api/admin/tournaments/6/matches', { method: 'POST' });
    expect(bustApiCache).toHaveBeenCalledTimes(1);
  });
});
