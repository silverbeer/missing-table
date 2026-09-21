/**
 * Day buckets for a match list (SB-1101).
 *
 * The mobile list repeated the date on every match card. A matchday is the
 * natural unit a parent scans by, so the date moves up into a sticky header
 * over its own group and comes off the rows entirely.
 *
 * Pure functions of (matches, now) so the bucketing is testable without
 * mounting anything.
 */

import { parseDateOnly, relativeDayLabel } from './tournamentStatus';

/**
 * "Today" / "Tomorrow" / "Yesterday" when the day is close enough for that to
 * mean something, otherwise the weekday and date: "Sat, Sep 20".
 *
 * The year is deliberately absent — the season filter already fixes it, and a
 * header repeated down a long list pays for every character.
 */
export function formatDayHeading(dateValue, now = new Date()) {
  const date = parseDateOnly(dateValue);
  if (!date) return 'Date TBD';

  const relative = relativeDayLabel(dateValue, now);
  const absolute = date.toLocaleDateString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
  });

  // Both, when relative applies: "Today" alone loses the date a reader needs
  // to orient a screenshot, and the date alone buries which day is now.
  return relative ? `${relative} · ${absolute}` : absolute;
}

/**
 * Bucket an already-sorted match list into consecutive day groups.
 *
 * Consecutive, not keyed-and-collected: the caller has sorted by date already,
 * so walking the list preserves that order and never invents a group ordering
 * of its own. A list that somehow returns to an earlier date opens a second
 * group for it rather than silently reordering the matches.
 *
 * @param {Array<object>} matches  matches carrying `match_date`
 * @param {Date} [now]             injected for tests
 * @returns {Array<{key: string, date: string|null, label: string, matches: Array<object>}>}
 */
export function groupMatchesByDate(matches, now = new Date()) {
  const groups = [];
  let current = null;

  for (const match of matches ?? []) {
    // A date-only column, sliced so a timestamp ('2026-09-20T00:00:00Z') and a
    // plain date both land in the same bucket.
    const date = match?.match_date
      ? String(match.match_date).slice(0, 10)
      : null;

    if (!current || current.date !== date) {
      current = {
        // The index disambiguates a date that appears in two separate runs, so
        // Vue never sees duplicate keys.
        key: `${date ?? 'undated'}-${groups.length}`,
        date,
        label: date ? formatDayHeading(date, now) : 'Date TBD',
        matches: [],
      };
      groups.push(current);
    }

    current.matches.push(match);
  }

  return groups;
}
