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
