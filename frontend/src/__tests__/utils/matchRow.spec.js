/**
 * Row formatting for the desktop match tables (SB-1121).
 *
 * Two things here are easy to get wrong and invisible when you do: a date
 * that silently shifts a day, and a score cell that collapses four different
 * states into one dash.
 */

import { describe, it, expect } from 'vitest';
import {
  parseMatchDate,
  formatRowDate,
  monthLabel,
  withMonthDividers,
  scoreCell,
} from '@/utils/matchRow';

describe('parseMatchDate', () => {
  it('keeps the calendar date as written, whatever the timezone', () => {
    // The API sends UTC midnight for a match played in New York. Parsed as a
    // real instant and formatted locally, Sep 6 renders as Sep 5 for every
    // viewer west of Greenwich — which is all of them.
    const date = parseMatchDate('2026-09-06T04:00:00.000Z');
    expect(date.getFullYear()).toBe(2026);
    expect(date.getMonth()).toBe(8);
    expect(date.getDate()).toBe(6);
  });

  it('reads a plain date string the same way', () => {
    expect(parseMatchDate('2026-09-06').getDate()).toBe(6);
  });

  it('is null for nothing and for junk', () => {
    expect(parseMatchDate(null)).toBeNull();
    expect(parseMatchDate('')).toBeNull();
    expect(parseMatchDate('not a date')).toBeNull();
  });
});

describe('formatRowDate', () => {
  it('gives the weekday and day over the month', () => {
    expect(formatRowDate('2026-09-06')).toEqual({ day: 'Sun 6', month: 'Sep' });
  });

  it('is null when the date will not parse', () => {
    expect(formatRowDate(undefined)).toBeNull();
  });
});

describe('monthLabel', () => {
  it('carries the year, because a season spans two of them', () => {
    expect(monthLabel('2026-11-08')).toBe('November 2026');
    expect(monthLabel('2027-03-07')).toBe('March 2027');
  });
});

const match = (id, date) => ({ id, match_date: date });

describe('withMonthDividers', () => {
  it('puts a divider before each new month, in order', () => {
    const rows = withMonthDividers([
      match(1, '2026-09-06'),
      match(2, '2026-09-20'),
      match(3, '2026-10-04'),
    ]);

    expect(rows.map(r => r.type)).toEqual([
      'month',
      'match',
      'match',
      'month',
      'match',
    ]);
    expect(rows[0].label).toBe('September 2026');
    expect(rows[3].label).toBe('October 2026');
  });

  it('never emits a divider with no match under it', () => {
    const rows = withMonthDividers([]);
    expect(rows).toEqual([]);
  });

  it('keeps one divider per month even when the month repeats a year later', () => {
    const rows = withMonthDividers([
      match(1, '2026-03-07'),
      match(2, '2027-03-07'),
    ]);
    expect(rows.filter(r => r.type === 'month').map(r => r.label)).toEqual([
      'March 2026',
      'March 2027',
    ]);
  });

  it('keeps a match whose date will not parse, rather than dropping a fixture', () => {
    const rows = withMonthDividers([match(1, null), match(2, '2026-09-06')]);
    expect(rows.filter(r => r.type === 'match')).toHaveLength(2);
  });

  it('can be asked for no dividers at all', () => {
    const rows = withMonthDividers([match(1, '2026-09-06')], {
      dividers: false,
    });
    expect(rows.every(r => r.type === 'match')).toBe(true);
  });
});

describe('scoreCell', () => {
  const played = { match_status: 'completed', home_score: 7, away_score: 1 };

  it('reads home first on My Club, matching how the teams are named', () => {
    expect(scoreCell(played, 'myclub')).toEqual({
      kind: 'score',
      text: '7 - 1',
    });
  });

  it('reads away first on All Matches, matching "Away @ Home"', () => {
    expect(scoreCell(played, 'all')).toEqual({ kind: 'score', text: '1 - 7' });
  });

  it('distinguishes a fixture still to come from one nobody scored', () => {
    const upcoming = scoreCell({ match_status: 'scheduled' });
    const unreported = scoreCell({
      match_status: 'completed',
      home_score: null,
      away_score: null,
    });

    expect(upcoming.kind).toBe('upcoming');
    expect(unreported.kind).toBe('unreported');
    expect(upcoming.text).not.toBe(unreported.text);
  });

  it('never renders an unplayed match as a zero', () => {
    expect(scoreCell({ match_status: 'scheduled' }).text).not.toContain('0');
  });

  it('shows a live score', () => {
    expect(
      scoreCell({ match_status: 'live', home_score: 1, away_score: 0 }).kind
    ).toBe('score');
  });

  it('stays quiet for postponed and cancelled — the status chip says it', () => {
    expect(scoreCell({ match_status: 'postponed' }).kind).toBe('none');
    expect(scoreCell({ match_status: 'cancelled' }).kind).toBe('none');
  });

  it('treats a half-entered score as unreported', () => {
    expect(
      scoreCell({ match_status: 'completed', home_score: 2, away_score: null })
        .kind
    ).toBe('unreported');
  });
});
