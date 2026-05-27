/**
 * useTeamFollows tests (SB-55).
 *
 * Singleton composable — module-level reactive state persists across calls.
 * Reset via _resetTeamFollowsForTest between cases.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

const isAuthenticatedRef = { value: true };
const apiRequestMock = vi.fn();

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    isAuthenticated: isAuthenticatedRef,
    apiRequest: apiRequestMock,
  }),
}));

vi.mock('@/config/api', () => ({
  getApiBaseUrl: () => 'http://test.example',
}));

import {
  useTeamFollows,
  _resetTeamFollowsForTest,
} from '@/composables/useTeamFollows';

beforeEach(() => {
  apiRequestMock.mockReset();
  isAuthenticatedRef.value = true;
  _resetTeamFollowsForTest();
});

describe('useTeamFollows.ensureLoaded', () => {
  it('hits GET /team-follows once and populates followedTeamIds', async () => {
    apiRequestMock.mockResolvedValueOnce({
      follows: [
        { team_id: 7, team: { name: 'A' } },
        { team_id: 9, team: { name: 'B' } },
      ],
    });

    const { ensureLoaded, isFollowing, loaded } = useTeamFollows();
    await ensureLoaded();

    expect(apiRequestMock).toHaveBeenCalledWith(
      'http://test.example/api/users/me/team-follows'
    );
    expect(loaded.value).toBe(true);
    expect(isFollowing(7)).toBe(true);
    expect(isFollowing(9)).toBe(true);
    expect(isFollowing(11)).toBe(false);
  });

  it('does not refetch when already loaded', async () => {
    apiRequestMock.mockResolvedValueOnce({ follows: [] });

    const a = useTeamFollows();
    await a.ensureLoaded();
    await a.ensureLoaded();

    expect(apiRequestMock).toHaveBeenCalledTimes(1);
  });

  it('coalesces concurrent ensureLoaded calls into one fetch', async () => {
    apiRequestMock.mockImplementationOnce(
      () =>
        new Promise(resolve => setTimeout(() => resolve({ follows: [] }), 5))
    );

    const a = useTeamFollows();
    await Promise.all([a.ensureLoaded(), a.ensureLoaded(), a.ensureLoaded()]);

    expect(apiRequestMock).toHaveBeenCalledTimes(1);
  });

  it('skips the fetch when user is not authenticated', async () => {
    isAuthenticatedRef.value = false;
    const { ensureLoaded, loaded } = useTeamFollows();
    await ensureLoaded();
    expect(apiRequestMock).not.toHaveBeenCalled();
    expect(loaded.value).toBe(true);
  });
});

describe('useTeamFollows.follow', () => {
  it('optimistically marks following + POSTs the team_id', async () => {
    apiRequestMock.mockResolvedValueOnce({ follows: [] }); // initial GET
    apiRequestMock.mockResolvedValueOnce({ team_id: 42, following: true }); // POST
    apiRequestMock.mockResolvedValueOnce({
      follows: [{ team_id: 42, team: { name: 'X' } }],
    }); // background refresh

    const { ensureLoaded, follow, isFollowing } = useTeamFollows();
    await ensureLoaded();

    const result = await follow(42);
    expect(result).toEqual({ success: true });
    expect(isFollowing(42)).toBe(true);

    expect(apiRequestMock).toHaveBeenNthCalledWith(
      2,
      'http://test.example/api/users/me/team-follows',
      { method: 'POST', body: JSON.stringify({ team_id: 42 }) }
    );
  });

  it('reverts optimistic state and returns error when POST fails', async () => {
    apiRequestMock.mockResolvedValueOnce({ follows: [] });
    apiRequestMock.mockRejectedValueOnce(new Error('boom'));

    const { ensureLoaded, follow, isFollowing, error } = useTeamFollows();
    await ensureLoaded();

    const result = await follow(7);
    expect(result.success).toBe(false);
    expect(result.error).toBe('boom');
    expect(isFollowing(7)).toBe(false);
    expect(error.value).toBe('boom');
  });

  it('is idempotent — no second POST when already following', async () => {
    apiRequestMock.mockResolvedValueOnce({
      follows: [{ team_id: 3, team: {} }],
    });

    const { ensureLoaded, follow } = useTeamFollows();
    await ensureLoaded();
    expect(apiRequestMock).toHaveBeenCalledTimes(1);

    await follow(3);
    // Still only the initial GET — no POST fired.
    expect(apiRequestMock).toHaveBeenCalledTimes(1);
  });

  it('accepts string team ids and normalizes to number', async () => {
    apiRequestMock.mockResolvedValueOnce({ follows: [] });
    apiRequestMock.mockResolvedValueOnce({ team_id: 5, following: true });
    apiRequestMock.mockResolvedValueOnce({
      follows: [{ team_id: 5, team: {} }],
    });

    const { ensureLoaded, follow, isFollowing } = useTeamFollows();
    await ensureLoaded();
    await follow('5');

    expect(isFollowing(5)).toBe(true);
    expect(isFollowing('5')).toBe(true);
    expect(apiRequestMock).toHaveBeenNthCalledWith(
      2,
      expect.any(String),
      expect.objectContaining({ body: JSON.stringify({ team_id: 5 }) })
    );
  });
});

describe('useTeamFollows.unfollow', () => {
  it('optimistically clears + DELETEs /team-follows/{id}', async () => {
    apiRequestMock.mockResolvedValueOnce({
      follows: [{ team_id: 8, team: {} }],
    });
    apiRequestMock.mockResolvedValueOnce(null); // DELETE returns 204 → null
    apiRequestMock.mockResolvedValueOnce({ follows: [] }); // refresh

    const { ensureLoaded, unfollow, isFollowing } = useTeamFollows();
    await ensureLoaded();
    expect(isFollowing(8)).toBe(true);

    await unfollow(8);
    expect(isFollowing(8)).toBe(false);

    expect(apiRequestMock).toHaveBeenNthCalledWith(
      2,
      'http://test.example/api/users/me/team-follows/8',
      { method: 'DELETE' }
    );
  });

  it('restores state when DELETE fails', async () => {
    apiRequestMock.mockResolvedValueOnce({
      follows: [{ team_id: 8, team: {} }],
    });
    apiRequestMock.mockRejectedValueOnce(new Error('nope'));

    const { ensureLoaded, unfollow, isFollowing } = useTeamFollows();
    await ensureLoaded();

    const result = await unfollow(8);
    expect(result.success).toBe(false);
    expect(isFollowing(8)).toBe(true);
  });

  it('is a no-op when not currently following', async () => {
    apiRequestMock.mockResolvedValueOnce({ follows: [] });

    const { ensureLoaded, unfollow } = useTeamFollows();
    await ensureLoaded();
    await unfollow(99);

    expect(apiRequestMock).toHaveBeenCalledTimes(1); // only initial GET
  });
});

describe('useTeamFollows.toggle', () => {
  it('follows then unfollows on successive calls', async () => {
    apiRequestMock.mockResolvedValueOnce({ follows: [] });
    apiRequestMock.mockResolvedValueOnce({ team_id: 1, following: true });
    apiRequestMock.mockResolvedValueOnce({
      follows: [{ team_id: 1, team: {} }],
    });
    apiRequestMock.mockResolvedValueOnce(null);
    apiRequestMock.mockResolvedValueOnce({ follows: [] });

    const { ensureLoaded, toggle, isFollowing } = useTeamFollows();
    await ensureLoaded();

    await toggle(1);
    expect(isFollowing(1)).toBe(true);

    await toggle(1);
    expect(isFollowing(1)).toBe(false);
  });
});

describe('useTeamFollows singleton behavior', () => {
  it('shares state across multiple useTeamFollows() callers', async () => {
    apiRequestMock.mockResolvedValueOnce({
      follows: [{ team_id: 12, team: {} }],
    });

    const a = useTeamFollows();
    await a.ensureLoaded();

    const b = useTeamFollows();
    expect(b.isFollowing(12)).toBe(true);
    expect(b.follows.value).toHaveLength(1);
  });
});
