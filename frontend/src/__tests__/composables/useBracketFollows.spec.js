/**
 * useBracketFollows tests.
 *
 * Singleton composable mirroring useTeamFollows, keyed by the bracket tuple
 * (tournament_id, tournament_group, age_group_id). Reset via
 * _resetBracketFollowsForTest between cases.
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
  useBracketFollows,
  _resetBracketFollowsForTest,
} from '@/composables/useBracketFollows';

beforeEach(() => {
  apiRequestMock.mockReset();
  isAuthenticatedRef.value = true;
  _resetBracketFollowsForTest();
});

describe('useBracketFollows.ensureLoaded', () => {
  it('hits GET /bracket-follows once and populates followed keys', async () => {
    apiRequestMock.mockResolvedValueOnce({
      follows: [
        { tournament_id: 6, tournament_group: 'Bracket A', age_group_id: 2 },
        { tournament_id: 6, tournament_group: 'Bracket B', age_group_id: 2 },
      ],
    });

    const { ensureLoaded, isFollowing, loaded } = useBracketFollows();
    await ensureLoaded();

    expect(apiRequestMock).toHaveBeenCalledWith(
      'http://test.example/api/users/me/bracket-follows'
    );
    expect(loaded.value).toBe(true);
    expect(isFollowing(6, 'Bracket A', 2)).toBe(true);
    expect(isFollowing(6, 'Bracket B', 2)).toBe(true);
    // Wrong age group / group misses.
    expect(isFollowing(6, 'Bracket A', 3)).toBe(false);
    expect(isFollowing(6, 'Bracket C', 2)).toBe(false);
  });

  it('skips the fetch when user is not authenticated', async () => {
    isAuthenticatedRef.value = false;
    const { ensureLoaded, loaded } = useBracketFollows();
    await ensureLoaded();
    expect(apiRequestMock).not.toHaveBeenCalled();
    expect(loaded.value).toBe(true);
  });
});

describe('useBracketFollows.follow', () => {
  it('optimistically marks following + POSTs the tuple', async () => {
    apiRequestMock.mockResolvedValueOnce({ follows: [] }); // initial GET
    apiRequestMock.mockResolvedValueOnce({ following: true }); // POST
    apiRequestMock.mockResolvedValueOnce({
      follows: [
        { tournament_id: 6, tournament_group: 'Bracket A', age_group_id: 2 },
      ],
    }); // background refresh

    const { ensureLoaded, follow, isFollowing } = useBracketFollows();
    await ensureLoaded();

    const result = await follow(6, 'Bracket A', 2);
    expect(result).toEqual({ success: true });
    expect(isFollowing(6, 'Bracket A', 2)).toBe(true);

    expect(apiRequestMock).toHaveBeenNthCalledWith(
      2,
      'http://test.example/api/users/me/bracket-follows',
      {
        method: 'POST',
        body: JSON.stringify({
          tournament_id: 6,
          tournament_group: 'Bracket A',
          age_group_id: 2,
        }),
      }
    );
  });

  it('reverts optimistic state when POST fails', async () => {
    apiRequestMock.mockResolvedValueOnce({ follows: [] });
    apiRequestMock.mockRejectedValueOnce(new Error('boom'));

    const { ensureLoaded, follow, isFollowing, error } = useBracketFollows();
    await ensureLoaded();

    const result = await follow(6, 'Bracket A', 2);
    expect(result.success).toBe(false);
    expect(result.error).toBe('boom');
    expect(isFollowing(6, 'Bracket A', 2)).toBe(false);
    expect(error.value).toBe('boom');
  });
});

describe('useBracketFollows.unfollow', () => {
  it('optimistically clears + DELETEs with composite query params', async () => {
    apiRequestMock.mockResolvedValueOnce({
      follows: [
        { tournament_id: 6, tournament_group: 'Bracket A', age_group_id: 2 },
      ],
    });
    apiRequestMock.mockResolvedValueOnce(null); // DELETE 204 → null
    apiRequestMock.mockResolvedValueOnce({ follows: [] }); // refresh

    const { ensureLoaded, unfollow, isFollowing } = useBracketFollows();
    await ensureLoaded();
    expect(isFollowing(6, 'Bracket A', 2)).toBe(true);

    await unfollow(6, 'Bracket A', 2);
    expect(isFollowing(6, 'Bracket A', 2)).toBe(false);

    const [url, opts] = apiRequestMock.mock.calls[1];
    expect(opts).toEqual({ method: 'DELETE' });
    expect(url).toContain('/api/users/me/bracket-follows?');
    expect(url).toContain('tournament_id=6');
    // URLSearchParams encodes the space in "Bracket A".
    expect(url).toContain('tournament_group=Bracket+A');
    expect(url).toContain('age_group_id=2');
  });

  it('is a no-op when not currently following', async () => {
    apiRequestMock.mockResolvedValueOnce({ follows: [] });

    const { ensureLoaded, unfollow } = useBracketFollows();
    await ensureLoaded();
    await unfollow(6, 'Bracket A', 2);

    expect(apiRequestMock).toHaveBeenCalledTimes(1); // only initial GET
  });
});

describe('useBracketFollows.toggle', () => {
  it('follows then unfollows on successive calls', async () => {
    apiRequestMock.mockResolvedValueOnce({ follows: [] });
    apiRequestMock.mockResolvedValueOnce({ following: true });
    apiRequestMock.mockResolvedValueOnce({
      follows: [
        { tournament_id: 6, tournament_group: 'Bracket A', age_group_id: 2 },
      ],
    });
    apiRequestMock.mockResolvedValueOnce(null);
    apiRequestMock.mockResolvedValueOnce({ follows: [] });

    const { ensureLoaded, toggle, isFollowing } = useBracketFollows();
    await ensureLoaded();

    await toggle(6, 'Bracket A', 2);
    expect(isFollowing(6, 'Bracket A', 2)).toBe(true);

    await toggle(6, 'Bracket A', 2);
    expect(isFollowing(6, 'Bracket A', 2)).toBe(false);
  });
});
