/**
 * Row-level formatting for the desktop match tables (SB-1121).
 *
 * Both sub-tabs render the same row through MatchTableRow, so the rules that
 * decide what a row *says* live here rather than in the template — one place
 * for a spec to pin, and no way for All Matches and My Club to drift apart
 * again.
 */

/**
 * The calendar date as written, never shifted by a timezone.
 *
 * `match_date` arrives as `2026-09-06` or `2026-09-06T04:00:00.000Z`. Handing
 * either to `new Date()` and formatting locally renders the previous day for
 * every viewer west of Greenwich — which is all of them. Reading the
 * year/month/day out of the string and building a local date keeps Sep 6 on
 * Sep 6.
 */
export const parseMatchDate = value => {
  if (!value) return null;
  const parts = String(value).match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!parts) return null;
  const date = new Date(
    Number(parts[1]),
    Number(parts[2]) - 1,
    Number(parts[3])
  );
  return Number.isNaN(date.getTime()) ? null : date;
};

/**
 * The two lines of the date cell: `Sun 6` over `Sep`.
 *
 * `2026-09-06` tells a parent nothing they can act on; the weekday is the
 * thing they are actually looking for on a fixture list.
 */
export const formatRowDate = value => {
  const date = parseMatchDate(value);
  if (!date) return null;
  // Composed rather than asked for as one pattern: en-US renders
  // weekday+day as "6 Sun", and the weekday is the part being led with here.
  const weekday = date.toLocaleDateString('en-US', { weekday: 'short' });
  return {
    day: `${weekday} ${date.getDate()}`,
    month: date.toLocaleDateString('en-US', { month: 'short' }),
  };
};

/**
 * The divider label, carrying the year.
 *
 * A season runs September to May, so a list holds two calendar years and
 * "March" alone is ambiguous about which one.
 */
export const monthLabel = value => {
  const date = parseMatchDate(value);
  if (!date) return null;
  return date.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
};

/**
 * Interleave month dividers into a chronological list.
 *
 * Returns a flat array of `{ type: 'month' }` and `{ type: 'match' }` rows.
 * A divider is only ever emitted immediately before a match, so an empty
 * month cannot produce a heading with nothing under it. Matches whose date
 * will not parse keep their place in the order and get no divider, rather
 * than being dropped from a schedule.
 */
export const withMonthDividers = (matches, { dividers = true } = {}) => {
  const rows = [];
  let current = null;

  for (const match of matches || []) {
    if (dividers) {
      const label = monthLabel(match?.match_date);
      if (label && label !== current) {
        current = label;
        rows.push({ type: 'month', key: `month-${label}`, label });
      }
    }
    rows.push({ type: 'match', key: `match-${match?.id}`, match });
  }

  return rows;
};

/** Statuses under which a scoreline is a real result. Mirrors MatchListRow. */
export const SCORABLE = ['completed', 'live', 'in_progress', 'forfeit'];

/**
 * What the score cell says, and which of the four things it means.
 *
 * A single dash used to cover all of them. The distinction that matters most
 * is the one CLAUDE.md calls out: a fixture still to come and a fixture
 * played with nobody entering a score are opposite problems, and only the
 * second is something an admin has to chase.
 *
 * `mode` picks the reading order so the numbers line up with how the teams
 * are named: All Matches says "Away @ Home", My Club says home first.
 */
export const scoreCell = (match, mode = 'myclub') => {
  const status = match?.match_status;
  const scorable = SCORABLE.includes(status);
  const hasScore =
    scorable && match?.home_score != null && match?.away_score != null;

  if (hasScore) {
    const [first, second] =
      mode === 'all'
        ? [match.away_score, match.home_score]
        : [match.home_score, match.away_score];
    return { kind: 'score', text: `${first} - ${second}` };
  }

  // Played, and nobody reported it — what `mt coverage` exists to find.
  if (scorable) return { kind: 'unreported', text: 'No score' };

  if (status === 'scheduled' || status === 'tbd') {
    return { kind: 'upcoming', text: 'Not played' };
  }

  // Postponed, cancelled, or a status this build does not know: the status
  // chip is already saying it, so the score cell stays quiet.
  return { kind: 'none', text: '—' };
};
