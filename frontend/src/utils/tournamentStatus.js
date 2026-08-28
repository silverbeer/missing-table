/**
 * Tournament status vocabulary (SB-886).
 *
 * The Tournaments tab used to state only what a tournament *is* (a name, a
 * crest, a match count). These helpers let it state where the tournament is in
 * its own life — "Starts tomorrow", "Live now", "Completed" — which is the
 * difference between a schedule tracker and a companion.
 *
 * Everything here is a pure function of (tournament, matches, now) so it can be
 * unit-tested without a database or a clock.
 */

/** Statuses under which a match has a real scoreline. */
export const SCORED_STATUSES = ['completed', 'in_progress', 'forfeit'];

/** Statuses that count as "this tournament is happening right now". */
const LIVE_STATUSES = ['in_progress'];

const MS_PER_DAY = 86400000;

/**
 * Parse a `YYYY-MM-DD` date column as local midnight.
 *
 * `new Date('2026-08-29')` parses as UTC midnight, which is the previous
 * evening in every US timezone — the classic off-by-one that makes a Saturday
 * tournament say "Starts today" on Friday night. Appending a time forces local.
 */
export function parseDateOnly(value) {
  if (!value) return null;
  const d = new Date(`${String(value).slice(0, 10)}T00:00:00`);
  return Number.isNaN(d.getTime()) ? null : d;
}

/** Local midnight at the start of whatever day `date` falls on. */
export function startOfDay(date) {
  const d = new Date(date);
  d.setHours(0, 0, 0, 0);
  return d;
}

/** Whole days from `from` to `to`, counted in calendar days, not 24h blocks. */
export function daysBetween(from, to) {
  return Math.round((startOfDay(to) - startOfDay(from)) / MS_PER_DAY);
}

/**
 * "Today" / "Tomorrow" / "Yesterday" for a match date, or null when the day is
 * far enough away that the weekday alone reads better.
 */
export function relativeDayLabel(dateValue, now = new Date()) {
  const date = parseDateOnly(dateValue);
  if (!date) return null;
  const delta = daysBetween(now, date);
  if (delta === 0) return 'Today';
  if (delta === 1) return 'Tomorrow';
  if (delta === -1) return 'Yesterday';
  return null;
}

/**
 * Human countdown for a span in milliseconds.
 *
 * Resolution tightens as the moment approaches: weeks far out, days inside a
 * fortnight, hours and minutes inside two days. A parent three weeks out does
 * not want to see 503 hours; a parent the night before wants the minutes.
 */
export function formatCountdown(ms) {
  if (ms == null || Number.isNaN(ms) || ms <= 0) return null;

  const minutes = Math.floor(ms / 60000);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);

  if (days >= 14) {
    const weeks = Math.round(days / 7);
    return `${weeks} weeks`;
  }
  if (days >= 2) return `${days} days`;
  if (hours >= 1) {
    const m = minutes % 60;
    return m > 0 ? `${hours}h ${m}m` : `${hours}h`;
  }
  if (minutes >= 1) return `${minutes}m`;
  return 'any moment';
}

/**
 * The earliest kickoff still in the future, as an ISO string, or null.
 * Matches with no `scheduled_kickoff` are skipped — a date alone cannot drive a
 * countdown, and guessing a kickoff time is worse than showing none.
 */
export function nextKickoff(matches = [], now = new Date()) {
  const upcoming = matches
    .map(m => m.scheduled_kickoff)
    .filter(Boolean)
    .filter(k => new Date(k) > now)
    .sort();
  return upcoming[0] ?? null;
}

/**
 * Where a tournament sits in its own life.
 *
 * Returns `{ state, label, countdownTo }`:
 *   state       'upcoming' | 'soon' | 'live' | 'completed'
 *   label       display string for the status ribbon and selector chip
 *   countdownTo ISO kickoff to tick against, or null when a countdown would
 *               be noise (too far out, or nothing left to start)
 *
 * `null` is returned when the tournament has no dates at all — the caller
 * renders no ribbon rather than inventing a state. A tournament with dates we
 * cannot parse is not "upcoming"; it is unknown, and unknown renders as absent.
 */
export function tournamentStatus(tournament, matches = [], now = new Date()) {
  if (!tournament) return null;

  const start = parseDateOnly(tournament.start_date);
  const end = parseDateOnly(tournament.end_date) ?? start;
  if (!start) return null;

  // A match in progress beats any date arithmetic: the tournament is live
  // whatever the calendar says.
  const hasLiveMatch = matches.some(m =>
    LIVE_STATUSES.includes(m.match_status)
  );

  const today = startOfDay(now);
  const daysToStart = daysBetween(now, start);
  const daysAfterEnd = daysBetween(end, now);

  if (
    hasLiveMatch ||
    (today >= startOfDay(start) && today <= startOfDay(end))
  ) {
    return {
      state: 'live',
      label: hasLiveMatch ? 'Live now' : 'Happening today',
      countdownTo: nextKickoff(matches, now),
    };
  }

  if (daysAfterEnd > 0) {
    return { state: 'completed', label: 'Completed', countdownTo: null };
  }

  if (daysToStart <= 7) {
    let label;
    if (daysToStart <= 0) label = 'Starts today';
    else if (daysToStart === 1) label = 'Starts tomorrow';
    else label = `Starts in ${daysToStart} days`;
    return { state: 'soon', label, countdownTo: nextKickoff(matches, now) };
  }

  const weeks = Math.round(daysToStart / 7);
  return {
    state: 'upcoming',
    label: daysToStart <= 13 ? `In ${daysToStart} days` : `In ${weeks} weeks`,
    // No countdown this far out — a ticking clock on something three weeks
    // away is decoration, not information.
    countdownTo: null,
  };
}

/**
 * Sort order for the tournament selector chips: live first, then what is about
 * to start, then the rest of the calendar, then what is finished.
 *
 * Within a state the tie-break follows what the reader is looking for: for
 * anything still ahead, soonest first; for anything finished, most recent
 * first, because the tournament someone wants to revisit is the one that just
 * ended, not the one from last autumn.
 */
const STATE_RANK = { live: 0, soon: 1, upcoming: 2, completed: 3 };

export function compareByStatus(a, b, now = new Date()) {
  const sa = tournamentStatus(a, a?.matches ?? [], now);
  const sb = tournamentStatus(b, b?.matches ?? [], now);
  const ra = STATE_RANK[sa?.state] ?? 2;
  const rb = STATE_RANK[sb?.state] ?? 2;
  if (ra !== rb) return ra - rb;

  const da = a?.start_date ?? '';
  const db = b?.start_date ?? '';
  if (da !== db) {
    const ascending = da < db ? -1 : 1;
    return ra === STATE_RANK.completed ? -ascending : ascending;
  }
  return (a?.id ?? 0) - (b?.id ?? 0);
}

/**
 * Group matches by their `match_date`, preserving the order they arrive in.
 *
 * Callers pass already-sorted matches, so day order and within-day order both
 * come from the caller's sort rather than being re-derived here. Matches with
 * no date collect under a `null` key so they still render somewhere instead of
 * silently vanishing.
 */
export function groupMatchesByDay(matches = []) {
  const days = new Map();
  for (const m of matches) {
    const key = m.match_date ? String(m.match_date).slice(0, 10) : null;
    if (!days.has(key)) days.set(key, []);
    days.get(key).push(m);
  }
  return [...days.entries()].map(([date, dayMatches]) => ({
    date,
    matches: dayMatches,
  }));
}

/**
 * Statuses that mean "no result has been recorded yet".
 *
 * `cancelled` is deliberately absent: that is a real, known outcome, not a
 * missing one, and it should keep saying so however old it gets.
 */
const UNRESOLVED_STATUSES = ['scheduled', 'tbd'];

/**
 * A match whose date has passed but which never received a result (SB-889).
 *
 * "Scheduled" is a claim about the future. On a fixture that kicked off in
 * June it is simply false — the match was played, and the score never reached
 * us. Callers render these as "Not reported": that states what we hold without
 * claiming the match was unplayed (we have no evidence of that) or promising a
 * result is still coming (the oldest of these dates from 2024).
 *
 * The boundary is the calendar day, not kickoff time. A match that started two
 * hours ago and has not been updated is normal mid-tournament; flipping it
 * during the day would be wrong, and would flicker while someone is
 * live-scoring. Only a date strictly before today counts.
 */
export function isMissingResult(match, now = new Date()) {
  if (!match) return false;
  if (!UNRESOLVED_STATUSES.includes(match.match_status)) return false;
  const date = parseDateOnly(match.match_date);
  if (!date) return false;
  return startOfDay(date) < startOfDay(now);
}

/**
 * Does this match involve the signed-in user's club or team?
 *
 * Club is checked first because a parent follows a club across age groups;
 * team is the fallback for accounts whose profile carries only `team_id`.
 * Signed out (both ids null) this is always false — the highlight is a silent
 * no-op rather than a state the page has to branch on.
 */
export function isMyMatch(match, { clubId = null, teamId = null } = {}) {
  if (!match) return false;
  if (clubId != null) {
    if (match.home_team_club?.id === clubId) return true;
    if (match.away_team_club?.id === clubId) return true;
  }
  if (teamId != null) {
    if (match.home_team?.id === teamId) return true;
    if (match.away_team?.id === teamId) return true;
  }
  return false;
}
