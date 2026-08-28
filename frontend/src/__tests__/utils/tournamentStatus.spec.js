/**
 * tournamentStatus.js — the vocabulary behind the Tournaments tab (SB-886).
 *
 * These are pure functions of (tournament, matches, now), so every case below
 * pins the clock explicitly rather than depending on when the suite runs.
 */

import { describe, it, expect } from 'vitest';
import {
  compareByStatus,
  daysBetween,
  isMissingResult,
  formatCountdown,
  groupMatchesByDay,
  isMyMatch,
  nextKickoff,
  parseDateOnly,
  relativeDayLabel,
  tournamentStatus,
} from '@/utils/tournamentStatus';

// Local noon, so no case is sitting on a midnight or DST boundary by accident.
const at = (y, m, d, hh = 12, mm = 0) => new Date(y, m - 1, d, hh, mm, 0);

const tourn = (start, end, extra = {}) => ({
  id: 1,
  name: 'Copa Rayados East Coast',
  start_date: start,
  end_date: end,
  ...extra,
});

const match = (over = {}) => ({
  id: 1,
  match_date: '2026-08-29',
  scheduled_kickoff: '2026-08-29T14:10:00Z',
  match_status: 'scheduled',
  home_team: { id: 19, name: 'IFA' },
  away_team: { id: 40, name: 'Northern Virginia Alliance' },
  home_team_club: { id: 1, name: 'IFA' },
  away_team_club: { id: 7, name: 'NVA' },
  home_score: null,
  away_score: null,
  ...over,
});

describe('parseDateOnly', () => {
  it('parses a date column at LOCAL midnight, not UTC', () => {
    // The bug this guards: new Date('2026-08-29') is UTC midnight, which is
    // Aug 28 in every US timezone — so a Saturday tournament would announce
    // "Starts today" on Friday evening.
    const d = parseDateOnly('2026-08-29');
    expect(d.getFullYear()).toBe(2026);
    expect(d.getMonth()).toBe(7);
    expect(d.getDate()).toBe(29);
    expect(d.getHours()).toBe(0);
  });

  it('tolerates a full timestamp and returns null for junk', () => {
    expect(parseDateOnly('2026-08-29T14:10:00Z').getDate()).toBe(29);
    expect(parseDateOnly(null)).toBeNull();
    expect(parseDateOnly('')).toBeNull();
  });
});

describe('daysBetween', () => {
  it('counts calendar days, not 24h blocks', () => {
    // 11pm to 1am the next day is two hours but one calendar day.
    expect(daysBetween(at(2026, 8, 28, 23), at(2026, 8, 29, 1))).toBe(1);
    expect(daysBetween(at(2026, 8, 29, 1), at(2026, 8, 29, 23))).toBe(0);
  });
});

describe('relativeDayLabel', () => {
  const now = at(2026, 8, 28);

  it('names today, tomorrow and yesterday', () => {
    expect(relativeDayLabel('2026-08-28', now)).toBe('Today');
    expect(relativeDayLabel('2026-08-29', now)).toBe('Tomorrow');
    expect(relativeDayLabel('2026-08-27', now)).toBe('Yesterday');
  });

  it('returns null further out, so the caller shows a weekday instead', () => {
    expect(relativeDayLabel('2026-08-30', now)).toBeNull();
    expect(relativeDayLabel(null, now)).toBeNull();
  });
});

describe('formatCountdown', () => {
  it('tightens resolution as the moment approaches', () => {
    expect(formatCountdown(21 * 86400000)).toBe('3 weeks');
    expect(formatCountdown(3 * 86400000)).toBe('3 days');
    expect(formatCountdown(22 * 3600000 + 14 * 60000)).toBe('22h 14m');
    expect(formatCountdown(3 * 3600000)).toBe('3h');
    expect(formatCountdown(9 * 60000)).toBe('9m');
    expect(formatCountdown(30 * 1000)).toBe('any moment');
  });

  it('returns null for a span that has already elapsed', () => {
    expect(formatCountdown(0)).toBeNull();
    expect(formatCountdown(-5000)).toBeNull();
    expect(formatCountdown(null)).toBeNull();
  });
});

describe('nextKickoff', () => {
  const now = at(2026, 8, 29, 12);

  it('returns the earliest kickoff still ahead', () => {
    const matches = [
      match({ id: 2, scheduled_kickoff: '2026-08-29T21:30:00Z' }),
      match({ id: 3, scheduled_kickoff: '2026-08-30T13:50:00Z' }),
    ];
    expect(nextKickoff(matches, now)).toBe('2026-08-29T21:30:00Z');
  });

  it('skips matches with no kickoff rather than guessing one', () => {
    expect(nextKickoff([match({ scheduled_kickoff: null })], now)).toBeNull();
    expect(nextKickoff([], now)).toBeNull();
  });
});

describe('tournamentStatus', () => {
  it('says "Starts tomorrow" the day before', () => {
    const s = tournamentStatus(
      tourn('2026-08-29', '2026-08-30'),
      [match()],
      at(2026, 8, 28)
    );
    expect(s.state).toBe('soon');
    expect(s.label).toBe('Starts tomorrow');
    expect(s.countdownTo).toBe('2026-08-29T14:10:00Z');
  });

  it('counts down in days inside the week', () => {
    const s = tournamentStatus(
      tourn('2026-08-29', '2026-08-30'),
      [],
      at(2026, 8, 25)
    );
    expect(s.state).toBe('soon');
    expect(s.label).toBe('Starts in 4 days');
  });

  it('is live on any day inside the date range', () => {
    const s = tournamentStatus(
      tourn('2026-08-29', '2026-08-30'),
      [],
      at(2026, 8, 30, 9)
    );
    expect(s.state).toBe('live');
    expect(s.label).toBe('Happening today');
  });

  it('a match in progress beats the calendar', () => {
    // Dates say the tournament ended, but a match is still being played —
    // e.g. a fixture that ran past midnight, or a stale end_date.
    const s = tournamentStatus(
      tourn('2026-08-29', '2026-08-30'),
      [match({ match_status: 'in_progress' })],
      at(2026, 9, 2)
    );
    expect(s.state).toBe('live');
    expect(s.label).toBe('Live now');
  });

  it('is completed after the end date', () => {
    const s = tournamentStatus(
      tourn('2026-08-29', '2026-08-30'),
      [match({ match_status: 'completed' })],
      at(2026, 9, 1)
    );
    expect(s.state).toBe('completed');
    expect(s.countdownTo).toBeNull();
  });

  it('shows weeks and no countdown when far out', () => {
    const s = tournamentStatus(
      tourn('2026-09-19', '2026-09-20'),
      [match({ scheduled_kickoff: '2026-09-19T14:00:00Z' })],
      at(2026, 8, 28)
    );
    expect(s.state).toBe('upcoming');
    expect(s.label).toBe('In 3 weeks');
    // A ticking clock on something three weeks away is decoration.
    expect(s.countdownTo).toBeNull();
  });

  it('renders as absent — not "upcoming" — when dates are unknown', () => {
    expect(tournamentStatus(tourn(null, null), [], at(2026, 8, 28))).toBeNull();
    expect(tournamentStatus(null, [], at(2026, 8, 28))).toBeNull();
  });

  it('treats a single-day tournament as live on its one day', () => {
    const s = tournamentStatus(
      tourn('2026-08-28', null),
      [],
      at(2026, 8, 28, 9)
    );
    expect(s.state).toBe('live');
  });
});

describe('compareByStatus', () => {
  it('sorts live first, then soon, then upcoming, then completed', () => {
    const now = at(2026, 8, 28);
    const live = tourn('2026-08-27', '2026-08-29', { id: 1 });
    const soon = tourn('2026-08-30', '2026-08-31', { id: 2 });
    const upcoming = tourn('2026-10-01', '2026-10-02', { id: 3 });
    const done = tourn('2026-07-01', '2026-07-02', { id: 4 });

    const sorted = [done, upcoming, soon, live]
      .slice()
      .sort((a, b) => compareByStatus(a, b, now))
      .map(t => t.id);

    expect(sorted).toEqual([1, 2, 3, 4]);
  });

  it('puts the most recently finished tournament ahead of older ones', () => {
    // Ascending would surface last autumn's event above the one that ended
    // on Saturday, which is the opposite of what anyone is looking for.
    const now = at(2026, 8, 28);
    const older = tourn('2026-03-01', '2026-03-02', { id: 10 });
    const recent = tourn('2026-08-01', '2026-08-02', { id: 11 });

    const sorted = [older, recent]
      .slice()
      .sort((a, b) => compareByStatus(a, b, now))
      .map(t => t.id);

    expect(sorted).toEqual([11, 10]);
  });

  it('still puts the soonest upcoming tournament first', () => {
    const now = at(2026, 8, 28);
    const later = tourn('2026-12-01', '2026-12-02', { id: 20 });
    const sooner = tourn('2026-10-01', '2026-10-02', { id: 21 });

    const sorted = [later, sooner]
      .slice()
      .sort((a, b) => compareByStatus(a, b, now))
      .map(t => t.id);

    expect(sorted).toEqual([21, 20]);
  });
});

describe('groupMatchesByDay', () => {
  it('groups by date and preserves the order it was handed', () => {
    const days = groupMatchesByDay([
      match({ id: 1, match_date: '2026-08-29' }),
      match({ id: 2, match_date: '2026-08-29' }),
      match({ id: 3, match_date: '2026-08-30' }),
    ]);
    expect(days.map(d => d.date)).toEqual(['2026-08-29', '2026-08-30']);
    expect(days[0].matches.map(m => m.id)).toEqual([1, 2]);
    expect(days[1].matches).toHaveLength(1);
  });

  it('keeps undated matches instead of dropping them', () => {
    const days = groupMatchesByDay([match({ id: 9, match_date: null })]);
    expect(days).toHaveLength(1);
    expect(days[0].date).toBeNull();
    expect(days[0].matches[0].id).toBe(9);
  });
});

describe('isMyMatch', () => {
  it('matches on club id, home or away', () => {
    expect(isMyMatch(match(), { clubId: 1 })).toBe(true);
    expect(isMyMatch(match(), { clubId: 7 })).toBe(true);
    expect(isMyMatch(match(), { clubId: 999 })).toBe(false);
  });

  it('falls back to team id for profiles that carry only that', () => {
    expect(isMyMatch(match(), { teamId: 19 })).toBe(true);
    expect(isMyMatch(match(), { teamId: 999 })).toBe(false);
  });

  it('is a silent no-op when signed out', () => {
    expect(isMyMatch(match(), {})).toBe(false);
    expect(isMyMatch(match(), { clubId: null, teamId: null })).toBe(false);
    expect(isMyMatch(null, { clubId: 1 })).toBe(false);
  });
});

describe('isMissingResult', () => {
  const now = at(2026, 8, 28);

  it('flags a fixture whose date has passed and never got a result', () => {
    // Match 3327: FC Westchester vs FC Greater Boston Bolts U13, played on
    // 5 June, still `scheduled` in late August.
    expect(
      isMissingResult(
        { match_status: 'scheduled', match_date: '2026-06-05' },
        now
      )
    ).toBe(true);
  });

  it('leaves a future fixture alone', () => {
    expect(
      isMissingResult(
        { match_status: 'scheduled', match_date: '2026-08-29' },
        now
      )
    ).toBe(false);
  });

  it('leaves a match played TODAY alone, whatever the hour', () => {
    // The boundary is the calendar day, not kickoff. A match that started two
    // hours ago and has not been updated is normal mid-tournament; flipping it
    // during the day would flicker while someone is live-scoring.
    const evening = at(2026, 8, 28, 23, 30);
    expect(
      isMissingResult(
        { match_status: 'scheduled', match_date: '2026-08-28' },
        evening
      )
    ).toBe(false);
  });

  it('flips the very next day', () => {
    expect(
      isMissingResult(
        { match_status: 'scheduled', match_date: '2026-08-27' },
        now
      )
    ).toBe(true);
  });

  it('covers tbd as well as scheduled', () => {
    expect(
      isMissingResult({ match_status: 'tbd', match_date: '2026-06-05' }, now)
    ).toBe(true);
  });

  it('never flags a resolved outcome', () => {
    // cancelled is a real, known outcome -- not a missing one -- and should
    // keep saying so however old it gets.
    for (const status of [
      'completed',
      'cancelled',
      'in_progress',
      'forfeit',
      'postponed',
    ]) {
      expect(
        isMissingResult({ match_status: status, match_date: '2026-06-05' }, now)
      ).toBe(false);
    }
  });

  it('does not flag a match with no date', () => {
    expect(
      isMissingResult({ match_status: 'scheduled', match_date: null }, now)
    ).toBe(false);
    expect(isMissingResult(null, now)).toBe(false);
  });
});
