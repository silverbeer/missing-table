/**
 * Remembered filter state for the Table and Matches tabs (SB-1112).
 *
 * The validation helpers carry the risk here: a stored id is a claim about
 * data that may have moved, and restoring a stale one strands the viewer on
 * an empty list with nothing on screen explaining why.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import {
  useFilterMemory,
  keepKnownIds,
  knownId,
  knownName,
  flushFilterMemory,
  SYNC_DEBOUNCE_MS,
} from '@/composables/useFilterMemory';

const DIVISIONS = [
  { id: 1, name: 'Northeast' },
  { id: 7, name: 'New England' },
  { id: 9, name: 'Turnpike' },
];

// The key useFilterMemory('matches', () => 42) writes under.
const STORED_KEY = 'mt.filters.v1.matches.42';

beforeEach(() => window.localStorage.clear());

describe('keepKnownIds', () => {
  it('keeps the ids the list still has', () => {
    expect(keepKnownIds([1, 9], DIVISIONS)).toEqual([1, 9]);
  });

  it('drops the ones it does not, and keeps the rest', () => {
    expect(keepKnownIds([1, 404, 9], DIVISIONS)).toEqual([1, 9]);
  });

  it('is empty — every division — when none survive, not a broken filter', () => {
    expect(keepKnownIds([404, 405], DIVISIONS)).toEqual([]);
  });

  it('tolerates a stored value that is not a list', () => {
    expect(keepKnownIds(null, DIVISIONS)).toEqual([]);
    expect(keepKnownIds('1,2', DIVISIONS)).toEqual([]);
  });

  it('compares as numbers, since JSON can hand back strings', () => {
    expect(keepKnownIds(['1', '7'], DIVISIONS)).toEqual([1, 7]);
  });
});

describe('knownId', () => {
  it('returns the id when the list still has it', () => {
    expect(knownId(7, DIVISIONS)).toBe(7);
    expect(knownId('7', DIVISIONS)).toBe(7);
  });

  it('is null for an id that is gone, and for nothing stored', () => {
    expect(knownId(404, DIVISIONS)).toBeNull();
    expect(knownId(null, DIVISIONS)).toBeNull();
    expect(knownId('', DIVISIONS)).toBeNull();
  });

  it('is null when the list has not loaded', () => {
    expect(knownId(7, [])).toBeNull();
    expect(knownId(7, undefined)).toBeNull();
  });
});

describe('knownName', () => {
  it('returns the name when the list still has it', () => {
    expect(knownName('Flex', [{ name: 'League' }, { name: 'Flex' }])).toBe(
      'Flex'
    );
  });

  it('is null for a name that is gone', () => {
    expect(knownName('Flex', [{ name: 'League' }])).toBeNull();
    expect(knownName(null, [{ name: 'League' }])).toBeNull();
  });
});

describe('useFilterMemory', () => {
  it('hands back what it stored', () => {
    const memory = useFilterMemory('matches', () => 42);
    memory.save({ ageGroupId: 3, divisionIds: [1, 9] });
    expect(memory.load()).toEqual({ ageGroupId: 3, divisionIds: [1, 9] });
  });

  it('is null before anything is stored', () => {
    expect(useFilterMemory('matches', () => 42).load()).toBeNull();
  });

  it('keeps each tab separate', () => {
    useFilterMemory('matches', () => 42).save({ ageGroupId: 3 });
    expect(useFilterMemory('table', () => 42).load()).toBeNull();
  });

  it('keeps each viewer separate — one iPad, two people', () => {
    useFilterMemory('matches', () => 42).save({ ageGroupId: 3 });
    expect(useFilterMemory('matches', () => 99).load()).toBeNull();
    expect(useFilterMemory('matches', () => null).load()).toBeNull();
  });

  it('follows the viewer when they sign in mid-session', () => {
    let userId = null;
    const memory = useFilterMemory('matches', () => userId);
    memory.save({ ageGroupId: 2 });
    userId = 42;
    expect(memory.load()).toBeNull();
  });

  it('forgets on clear', () => {
    const memory = useFilterMemory('matches', () => 42);
    memory.save({ ageGroupId: 3 });
    memory.clear();
    expect(memory.load()).toBeNull();
  });

  it('treats corrupt stored JSON as no memory', () => {
    const memory = useFilterMemory('matches', () => 42);
    memory.save({ ageGroupId: 3 });
    window.localStorage.setItem(STORED_KEY, '{not json');
    expect(memory.load()).toBeNull();
  });

  it('treats stored JSON that is not an object as no memory', () => {
    const memory = useFilterMemory('matches', () => 42);
    memory.save({ ageGroupId: 3 });
    window.localStorage.setItem(STORED_KEY, '"U15"');
    expect(memory.load()).toBeNull();
  });
});

describe('useFilterMemory when storage throws (private mode)', () => {
  let getItem;
  let setItem;

  beforeEach(() => {
    getItem = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('SecurityError');
    });
    setItem = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('QuotaExceededError');
    });
  });

  afterEach(() => {
    getItem.mockRestore();
    setItem.mockRestore();
  });

  it('saves without throwing — a filter memory is not worth a blank tab', () => {
    const memory = useFilterMemory('matches', () => 42);
    expect(() => memory.save({ ageGroupId: 3 })).not.toThrow();
  });

  it('loads as no memory rather than throwing', () => {
    expect(useFilterMemory('matches', () => 42).load()).toBeNull();
  });
});

/**
 * Account sync (SB-1715). A fake account side stands in for the auth store:
 * `memory` is what /api/auth/me returned, `puts` what was sent.
 */
describe('useFilterMemory account sync (SB-1715)', () => {
  const fakeAccount = (memory = {}, { active = true } = {}) => {
    const puts = [];
    return {
      puts,
      memory,
      active: () => active,
      entry: view => memory[view],
      remember: (view, patch) => {
        memory[view] = { ...(memory[view] || {}), ...patch };
      },
      put: (view, body) => {
        puts.push({ view, body });
        return Promise.resolve();
      },
    };
  };

  beforeEach(() => vi.useFakeTimers());
  afterEach(() => {
    flushFilterMemory();
    vi.useRealTimers();
  });

  it('a new device with no browser copy gets the account copy', () => {
    const account = fakeAccount({
      matches: { filters: { ageGroupId: 3, savedAt: 1000 }, saved_at: 1000 },
    });
    const memory = useFilterMemory('matches', () => 42, { remote: account });
    expect(memory.load()).toEqual({ ageGroupId: 3 });
    // …and keeps it locally from then on.
    expect(JSON.parse(window.localStorage.getItem(STORED_KEY)).ageGroupId).toBe(
      3
    );
  });

  it('the newer copy wins, whichever side it is on', () => {
    window.localStorage.setItem(
      STORED_KEY,
      JSON.stringify({ ageGroupId: 2, savedAt: 2000 })
    );
    const older = fakeAccount({
      matches: { filters: { ageGroupId: 3, savedAt: 1000 }, saved_at: 1000 },
    });
    expect(
      useFilterMemory('matches', () => 42, { remote: older }).load()
    ).toEqual({ ageGroupId: 2 });

    const newer = fakeAccount({
      matches: { filters: { ageGroupId: 4, savedAt: 3000 }, saved_at: 3000 },
    });
    expect(
      useFilterMemory('matches', () => 42, { remote: newer }).load()
    ).toEqual({ ageGroupId: 4 });
  });

  it('a pre-sync browser copy (no stamp) loses to any account copy', () => {
    window.localStorage.setItem(STORED_KEY, JSON.stringify({ ageGroupId: 2 }));
    const account = fakeAccount({
      matches: { filters: { ageGroupId: 3, savedAt: 1 }, saved_at: 1 },
    });
    expect(
      useFilterMemory('matches', () => 42, { remote: account }).load()
    ).toEqual({ ageGroupId: 3 });
  });

  it('cleared on another device, newer than here: forgotten here too', () => {
    window.localStorage.setItem(
      STORED_KEY,
      JSON.stringify({ ageGroupId: 2, savedAt: 1000 })
    );
    const account = fakeAccount({
      matches: { filters: null, saved_at: 2000 },
    });
    expect(
      useFilterMemory('matches', () => 42, { remote: account }).load()
    ).toBeNull();
    expect(window.localStorage.getItem(STORED_KEY)).toBeNull();
  });

  it('a burst of changes is one request, after the debounce', () => {
    const account = fakeAccount();
    const memory = useFilterMemory('matches', () => 42, { remote: account });
    memory.save({ ageGroupId: 2 });
    memory.save({ ageGroupId: 3 });
    memory.save({ ageGroupId: 4 });
    expect(account.puts).toHaveLength(0);

    vi.advanceTimersByTime(SYNC_DEBOUNCE_MS);
    return Promise.resolve().then(() => {
      expect(account.puts).toHaveLength(1);
      expect(account.puts[0].view).toBe('matches');
      expect(account.puts[0].body.filters.ageGroupId).toBe(4);
      expect(typeof account.puts[0].body.saved_at).toBe('number');
    });
  });

  it('panel and filters changes in one burst merge into one request', async () => {
    const account = fakeAccount();
    const memory = useFilterMemory('table', () => 42, { remote: account });
    memory.save({ ageGroupId: 2 });
    memory.savePanel(false);
    vi.advanceTimersByTime(SYNC_DEBOUNCE_MS);
    await Promise.resolve();
    expect(account.puts).toHaveLength(1);
    expect(account.puts[0].body.panel_open).toBe(false);
    expect(account.puts[0].body.filters.ageGroupId).toBe(2);
  });

  it('clear tells the account to forget', async () => {
    const account = fakeAccount();
    useFilterMemory('matches', () => 42, { remote: account }).clear();
    vi.advanceTimersByTime(SYNC_DEBOUNCE_MS);
    await Promise.resolve();
    expect(account.puts[0].body.filters).toBeNull();
    expect(account.memory.matches.filters).toBeNull();
  });

  it('signed out: browser only, nothing sent', async () => {
    const account = fakeAccount({}, { active: false });
    const memory = useFilterMemory('matches', () => null, { remote: account });
    memory.save({ ageGroupId: 2 });
    vi.advanceTimersByTime(SYNC_DEBOUNCE_MS);
    await Promise.resolve();
    expect(account.puts).toHaveLength(0);
    expect(memory.load()).toEqual({ ageGroupId: 2 });
  });

  it('a failed request costs nothing — the browser copy stands', async () => {
    const account = fakeAccount();
    account.put = () => Promise.reject(new Error('503'));
    const memory = useFilterMemory('matches', () => 42, { remote: account });
    memory.save({ ageGroupId: 2 });
    vi.advanceTimersByTime(SYNC_DEBOUNCE_MS);
    await Promise.resolve();
    expect(memory.load()).toEqual({ ageGroupId: 2 });
  });

  it('flush sends queued writes now (the tab is closing)', async () => {
    const account = fakeAccount();
    useFilterMemory('matches', () => 42, { remote: account }).save({
      ageGroupId: 2,
    });
    flushFilterMemory();
    await Promise.resolve();
    expect(account.puts).toHaveLength(1);
  });
});

describe('panel memory (SB-1714, per viewer since SB-1715)', () => {
  it('is open until first closed', () => {
    expect(
      useFilterMemory('table', () => 42, { remote: null }).loadPanel()
    ).toBe(true);
  });

  it('is per viewer — one iPad, two people', () => {
    useFilterMemory('table', () => 42, { remote: null }).savePanel(false);
    expect(
      useFilterMemory('table', () => 99, { remote: null }).loadPanel()
    ).toBe(true);
    expect(
      useFilterMemory('table', () => 42, { remote: null }).loadPanel()
    ).toBe(false);
  });

  it('the old per-browser choice goes to the first viewer who reads it', () => {
    window.localStorage.setItem('mt.filterPanel.v1.table', 'closed');
    expect(
      useFilterMemory('table', () => 42, { remote: null }).loadPanel()
    ).toBe(false);
    expect(
      useFilterMemory('table', () => 99, { remote: null }).loadPanel()
    ).toBe(true);
  });

  it('a new device takes the account choice', () => {
    const remote = {
      active: () => true,
      entry: () => ({ panel_open: false }),
    };
    expect(useFilterMemory('table', () => 42, { remote }).loadPanel()).toBe(
      false
    );
  });
});
