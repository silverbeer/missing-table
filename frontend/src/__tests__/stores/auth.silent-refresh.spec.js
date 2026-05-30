/**
 * Silent-refresh behavior of the auth store (SB-78).
 *
 * Covers the three mechanisms that keep a user logged in without re-entering
 * their password:
 *   1. expires_at is persisted so the proactive refresh can schedule itself
 *   2. a single-flight guard prevents the refresh-token rotation race
 *   3. the proactive timer refreshes a token before it expires
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { useAuthStore } from '@/stores/auth';

// Build an unsigned JWT carrying the given `exp` (epoch seconds). When `exp`
// is null the payload omits it, exercising the "unknown expiry" path.
const makeJwt = exp => {
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }));
  const payload = btoa(JSON.stringify(exp === null ? {} : { exp }));
  return `${header}.${payload}.sig`;
};

const nowSec = () => Math.floor(Date.now() / 1000);

describe('auth store — silent refresh (SB-78)', () => {
  let store;

  beforeEach(() => {
    store = useAuthStore();
    // Reset shared module-level state (session + any armed timer) between tests.
    store.forceLogout();
    global.fetch.mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
    store.forceLogout();
  });

  describe('setSession persists expires_at', () => {
    it('stores the explicit expires_at from the login/refresh response', () => {
      const exp = nowSec() + 3600;
      store.setSession({
        access_token: makeJwt(exp),
        refresh_token: 'r1',
        expires_at: exp,
      });
      expect(localStorage.getItem('token_expires_at')).toBe(String(exp));
      expect(store.state.session.expires_at).toBe(exp);
    });

    it('falls back to decoding exp from the JWT when expires_at is absent', () => {
      const exp = nowSec() + 3600;
      // Mimics initialize(): only the access_token survives a reload.
      store.setSession({ access_token: makeJwt(exp) });
      expect(store.state.session.expires_at).toBe(exp);
      expect(localStorage.getItem('token_expires_at')).toBe(String(exp));
    });

    it('clears token_expires_at when the session is cleared', () => {
      store.setSession({ access_token: makeJwt(nowSec() + 3600) });
      store.setSession(null);
      expect(localStorage.getItem('token_expires_at')).toBeNull();
    });
  });

  describe('isTokenExpiringSoon', () => {
    it('is false when expiry is far away', () => {
      store.setSession({
        access_token: makeJwt(nowSec() + 3600),
        expires_at: nowSec() + 3600,
      });
      expect(store.isTokenExpiringSoon()).toBe(false);
    });

    it('is true within the 5-minute window', () => {
      store.setSession({
        access_token: makeJwt(nowSec() + 120),
        expires_at: nowSec() + 120,
      });
      expect(store.isTokenExpiringSoon()).toBe(true);
    });

    it('is true once the token has already expired', () => {
      store.setSession({
        access_token: makeJwt(nowSec() - 10),
        expires_at: nowSec() - 10,
      });
      expect(store.isTokenExpiringSoon()).toBe(true);
    });

    it('is false when expiry is unknown (no exp claim, no expires_at)', () => {
      store.setSession({ access_token: makeJwt(null) });
      expect(store.isTokenExpiringSoon()).toBe(false);
    });
  });

  describe('refreshSession single-flight guard', () => {
    it('coalesces concurrent refreshes into one network call', async () => {
      let resolveFetch;
      global.fetch.mockImplementation(
        () =>
          new Promise(res => {
            resolveFetch = res;
          })
      );
      localStorage.setItem('refresh_token', 'r1');

      const p1 = store.refreshSession();
      const p2 = store.refreshSession();

      expect(global.fetch).toHaveBeenCalledTimes(1);

      const exp = nowSec() + 3600;
      resolveFetch({
        ok: true,
        json: async () => ({
          session: {
            access_token: makeJwt(exp),
            refresh_token: 'r2',
            expires_at: exp,
          },
        }),
      });

      const [a, b] = await Promise.all([p1, p2]);
      expect(a.success).toBe(true);
      expect(b.success).toBe(true);

      // The in-flight guard is released once settled: a fresh refresh makes a
      // new call rather than returning the old (now-resolved) promise.
      const exp2 = nowSec() + 3600;
      global.fetch.mockResolvedValue({
        ok: true,
        json: async () => ({
          session: {
            access_token: makeJwt(exp2),
            refresh_token: 'r3',
            expires_at: exp2,
          },
        }),
      });
      localStorage.setItem('refresh_token', 'r2');
      await store.refreshSession();
      expect(global.fetch).toHaveBeenCalledTimes(2);
    });
  });

  describe('proactive refresh timer', () => {
    it('refreshes the token when it is about to expire', async () => {
      vi.useFakeTimers();
      const future = nowSec() + 3600;
      global.fetch.mockResolvedValue({
        ok: true,
        json: async () => ({
          session: {
            access_token: makeJwt(future),
            refresh_token: 'r2',
            expires_at: future,
          },
        }),
      });

      // Arm the timer with a token already inside the 5-minute window.
      const soon = nowSec() + 120;
      store.setSession({
        access_token: makeJwt(soon),
        refresh_token: 'r1',
        expires_at: soon,
      });
      global.fetch.mockClear();

      await vi.advanceTimersByTimeAsync(60 * 1000);

      expect(global.fetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/auth/refresh',
        expect.objectContaining({ method: 'POST' })
      );
    });
  });
});
