/**
 * utils/swCache.js tests (SB-902).
 *
 * The service worker serves the read APIs with StaleWhileRevalidate, so a
 * re-fetch right after a write is answered from the pre-write cache and the
 * admin's own change appears to have been dropped. bustApiCache() is what makes
 * a write read-your-write, so it has to be both effective and unfailing: a
 * browser with no Cache API, or a cache that throws, must not break the write.
 */

import { describe, it, expect, afterEach, vi } from 'vitest';
import { bustApiCache, API_CACHE_NAME } from '@/utils/swCache';

const originalCaches = globalThis.caches;

function stubCaches(value) {
  Object.defineProperty(globalThis, 'caches', {
    value,
    configurable: true,
    writable: true,
  });
}

afterEach(() => {
  stubCaches(originalCaches);
  vi.restoreAllMocks();
});

describe('bustApiCache', () => {
  it('deletes the service worker runtime cache', async () => {
    const del = vi.fn().mockResolvedValue(true);
    stubCaches({ delete: del });

    await expect(bustApiCache()).resolves.toBe(true);
    expect(del).toHaveBeenCalledWith(API_CACHE_NAME);
  });

  it('targets the same cache name the service worker writes', () => {
    // Keep in sync with the runtime route in src/sw.js.
    expect(API_CACHE_NAME).toBe('mt-reference-and-standings-v1');
  });

  it('reports false when there was no cache to delete', async () => {
    stubCaches({ delete: vi.fn().mockResolvedValue(false) });
    await expect(bustApiCache()).resolves.toBe(false);
  });

  it('is a no-op without the Cache API', async () => {
    stubCaches(undefined);
    await expect(bustApiCache()).resolves.toBe(false);
  });

  it('is a no-op when caches exists but cannot delete', async () => {
    stubCaches({});
    await expect(bustApiCache()).resolves.toBe(false);
  });

  it('swallows a failing delete so the write it followed still succeeds', async () => {
    stubCaches({
      delete: vi.fn().mockRejectedValue(new Error('QuotaExceededError')),
    });
    await expect(bustApiCache()).resolves.toBe(false);
  });
});
