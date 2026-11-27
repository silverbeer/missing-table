/**
 * Formatting for the Power Rating list (SB-1809), kept pure so the rules that
 * matter — absent is never zero, a rating reads like a rating — are tested
 * without mounting anything.
 */

// The two badges the run stores (`PowerRatingDAO`), short on the chip with
// the rule in the title. Pro academy is a row flag, not a stored badge.
export const BADGES = {
  provisional: {
    label: 'Provisional',
    title: 'Provisional: 6 or 7 matches, so the rating still moves quickly',
  },
  low_cross_conference: {
    label: 'Low cross-conf.',
    title:
      'Low cross-conference data: fewer than 3 matches against other conferences',
  },
};

const MINUS = '−';

/** 1642 -> "1,642". Null stays null: no rating is not a rating of 0. */
export const formatRating = rating =>
  rating == null ? null : Number(rating).toLocaleString('en-US');

/** 1 -> "1st", 12 -> "12th", 22 -> "22nd". */
export const ordinal = n => {
  if (n == null) return null;
  const mod100 = n % 100;
  if (mod100 >= 11 && mod100 <= 13) return `${n}th`;
  return `${n}${{ 1: 'st', 2: 'nd', 3: 'rd' }[n % 10] || 'th'}`;
};

/**
 * Movement over 7 days, as places and points: "▲2 · +12", "▼1 · −8".
 *
 * Null is absent, never "▲0": no run a week earlier (`movementSince` null)
 * renders nothing, and a team that was not in that run reads "New". A rank
 * that held drops its arrow and keeps the points; an unchanged rating is ±0.
 * Returns `{ text, direction }` or null; direction is 'up' | 'down' | 'flat'
 * | 'new'.
 */
export const formatMovement = (rankChange, ratingChange, movementSince) => {
  if (rankChange == null && ratingChange == null) {
    return movementSince ? { text: 'New', direction: 'new' } : null;
  }
  const parts = [];
  if (rankChange > 0) parts.push(`▲${rankChange}`);
  else if (rankChange < 0) parts.push(`▼${Math.abs(rankChange)}`);
  if (ratingChange != null) {
    if (ratingChange > 0) parts.push(`+${ratingChange}`);
    else if (ratingChange < 0) parts.push(`${MINUS}${Math.abs(ratingChange)}`);
    else parts.push('±0');
  }
  // Places lead; with no place change the points decide the colour.
  const lead = rankChange || ratingChange || 0;
  const direction = lead > 0 ? 'up' : lead < 0 ? 'down' : 'flat';
  return { text: parts.join(' · '), direction };
};

/** "2026-12-15T10:00:04Z" -> "Dec 15, 2026"; null for nothing usable. */
export const formatUpdated = computedAt => {
  if (!computedAt) return null;
  const d = new Date(computedAt);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
};

/**
 * The national list under its tier headers, in the order `tiers` gives.
 * Ranked teams below the lowest cut-off go under "Others"; teams outside the
 * main island (`comparable_nationally` false, no national rank) go last,
 * under their own header, never interleaved into the order.
 */
export const groupByTier = (teams, tiers) => {
  const groups = (tiers || []).map(t => ({
    key: t.key,
    label: t.label,
    hint: `${formatRating(t.min)}+`,
    rows: [],
  }));
  const byKey = Object.fromEntries(groups.map(g => [g.key, g]));
  const lowest = (tiers || []).reduce(
    (min, t) => (min == null || t.min < min ? t.min : min),
    null
  );
  const others = {
    key: 'others',
    label: 'Others',
    hint: lowest == null ? null : `below ${formatRating(lowest)}`,
    rows: [],
  };
  const apart = {
    key: 'not_comparable',
    label: 'Not yet comparable nationally',
    hint: 'shown with their conference',
    rows: [],
  };
  for (const row of teams || []) {
    if (row.comparable_nationally === false || row.rank == null) {
      apart.rows.push(row);
    } else if (row.tier && byKey[row.tier]) {
      byKey[row.tier].rows.push(row);
    } else {
      others.rows.push(row);
    }
  }
  return [...groups, others, apart].filter(g => g.rows.length > 0);
};
