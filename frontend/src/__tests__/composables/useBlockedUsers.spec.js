/**
 * useBlockedUsers — the session's blocked list (SB-1324).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

const apiRequest = vi.fn();
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ apiRequest }) }));
vi.mock('@/config/api', () => ({ getApiBaseUrl: () => 'http://api' }));

import { useBlockedUsers } from '@/composables/useBlockedUsers';

beforeEach(() => {
  apiRequest.mockReset();
  useBlockedUsers().clear();
});

describe('useBlockedUsers', () => {
  it('loads the list into the blocked id set', async () => {
    apiRequest.mockResolvedValueOnce([
      { user_id: 'u1', username: 'one', created_at: 'x' },
    ]);
    const blocked = useBlockedUsers();
    await blocked.load();
    expect(apiRequest).toHaveBeenCalledWith('http://api/api/users/me/blocks');
    expect(blocked.blockedIds.value.has('u1')).toBe(true);
  });

  it('clear() empties it, as on logout', async () => {
    apiRequest.mockResolvedValueOnce([{ user_id: 'u1' }]);
    const blocked = useBlockedUsers();
    await blocked.load();
    blocked.clear();
    expect(blocked.blockedIds.value.size).toBe(0);
    expect(blocked.blocks.value).toEqual([]);
  });

  it('report() hides the author from the response, with no second block call', async () => {
    apiRequest.mockResolvedValueOnce({
      reported: true,
      blocked_user_id: 'author-9',
    });
    const blocked = useBlockedUsers();
    const author = await blocked.report(5, 77, 'spam');

    expect(author).toBe('author-9');
    expect(blocked.blockedIds.value.has('author-9')).toBe(true);
    expect(apiRequest).toHaveBeenCalledTimes(1);
    const [url, opts] = apiRequest.mock.calls[0];
    expect(url).toBe('http://api/api/matches/5/live/events/77/report');
    expect(opts.method).toBe('POST');
    expect(JSON.parse(opts.body)).toEqual({ reason: 'spam', details: null });
  });

  it('block() and unblock() keep the set in step', async () => {
    apiRequest.mockResolvedValue(null);
    const blocked = useBlockedUsers();
    await blocked.block('u2');
    expect(blocked.blockedIds.value.has('u2')).toBe(true);
    expect(apiRequest).toHaveBeenLastCalledWith(
      'http://api/api/users/u2/block',
      {
        method: 'POST',
      }
    );

    await blocked.unblock('u2');
    expect(blocked.blockedIds.value.has('u2')).toBe(false);
    expect(apiRequest).toHaveBeenLastCalledWith(
      'http://api/api/users/u2/block',
      {
        method: 'DELETE',
      }
    );
  });

  it('a failed load leaves the set as it was', async () => {
    apiRequest.mockRejectedValueOnce(new Error('down'));
    const blocked = useBlockedUsers();
    blocked.noteBlocked('u3');
    await blocked.load();
    expect(blocked.blockedIds.value.has('u3')).toBe(true);
    expect(blocked.error.value).toBe('down');
  });
});
