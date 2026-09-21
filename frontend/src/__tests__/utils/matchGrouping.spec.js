/**
 * Day bucketing for the phone match list (SB-1101).
 */

import { describe, it, expect } from 'vitest';
import { formatDayHeading, groupMatchesByDate } from '@/utils/matchGrouping';

const match = (id, match_date) => ({ id, match_date });

// A fixed "now" so "Today"/"Tomorrow" are deterministic.
const NOW = new Date('2026-09-20T12:00:00');

describe('formatDayHeading', () => {
  it('names the weekday and date for a day that is not near now', () => {
    expect(formatDayHeading('2026-10-03', NOW)).toBe('Sat, Oct 3');
  });

  it('keeps the date alongside Today, so a screenshot still says when', () => {
    expect(formatDayHeading('2026-09-20', NOW)).toBe('Today · Sun, Sep 20');
  });

  it('labels tomorrow and yesterday', () => {
    expect(formatDayHeading('2026-09-21', NOW)).toBe('Tomorrow · Mon, Sep 21');
    expect(formatDayHeading('2026-09-19', NOW)).toBe('Yesterday · Sat, Sep 19');
  });

  it('reads a date column as local midnight, not UTC', () => {
    // `new Date('2026-09-20')` is UTC midnight, which is Sep 19 evening in
    // every US timezone — the off-by-one that would head a Sunday group with
    // "Sat, Sep 19".
    expect(formatDayHeading('2026-09-20', NOW)).toContain('Sep 20');
  });

  it('says so rather than guessing when there is no date', () => {
    expect(formatDayHeading(null, NOW)).toBe('Date TBD');
    expect(formatDayHeading('not-a-date', NOW)).toBe('Date TBD');
  });
});

describe('groupMatchesByDate', () => {
  it('returns no groups for no matches', () => {
    expect(groupMatchesByDate([], NOW)).toEqual([]);
    expect(groupMatchesByDate(null, NOW)).toEqual([]);
    expect(groupMatchesByDate(undefined, NOW)).toEqual([]);
  });

  it('collects consecutive matches on the same day into one group', () => {
    const groups = groupMatchesByDate(
      [match(1, '2026-09-19'), match(2, '2026-09-19'), match(3, '2026-09-20')],
      NOW
    );

    expect(groups).toHaveLength(2);
    expect(groups[0].matches.map(m => m.id)).toEqual([1, 2]);
    expect(groups[1].matches.map(m => m.id)).toEqual([3]);
  });

  it('preserves the order the caller sorted the matches into', () => {
    const groups = groupMatchesByDate(
      [match(1, '2026-09-20'), match(2, '2026-09-19')],
      NOW
    );
    expect(groups.map(g => g.date)).toEqual(['2026-09-20', '2026-09-19']);
  });

  it('opens a second group rather than reordering a date that recurs', () => {
    const groups = groupMatchesByDate(
      [match(1, '2026-09-19'), match(2, '2026-09-20'), match(3, '2026-09-19')],
      NOW
    );

    expect(groups).toHaveLength(3);
    // Distinct keys, or Vue would reuse the DOM of the first group for the third.
    expect(new Set(groups.map(g => g.key)).size).toBe(3);
  });

  it('buckets a timestamp with the plain date for the same day', () => {
    const groups = groupMatchesByDate(
      [match(1, '2026-09-20'), match(2, '2026-09-20T18:30:00Z')],
      NOW
    );
    expect(groups).toHaveLength(1);
  });

  it('groups undated matches together under Date TBD', () => {
    const groups = groupMatchesByDate([match(1, null), match(2, null)], NOW);
    expect(groups).toHaveLength(1);
    expect(groups[0].label).toBe('Date TBD');
    expect(groups[0].date).toBeNull();
  });
});
